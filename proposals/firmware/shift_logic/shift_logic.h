/*
 * This file is part of the Zombieverter project.
 *
 * Copyright (C) 2026 ZF_8HP contributor
 *
 * This program is free software: you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation, either version 3 of the License, or
 * (at your option) any later version.
 */

#ifndef ZF8HP_SHIFT_LOGIC_H
#define ZF8HP_SHIFT_LOGIC_H

#include "clutch_table.h"
#include <stdint.h>

namespace zf8hp {

/*
 * Shift orchestration state machine for the OI 8HP TCU.
 *
 * Drives a single-step shift between adjacent gears (e.g. 3→4, 5→4) by
 * orchestrating the ZF 8HP "single-element-per-shift" overlap window:
 *
 *   PRE_FILL    — incoming clutch is filled to kiss-point, no torque yet
 *   TORQUE_CUT  — request VCU to pull engine/motor torque (handshake)
 *   OVERLAP     — outgoing element drains while incoming element ramps
 *                 to full pressure; this is the ~150 ms window where slip
 *                 actually happens
 *   COMPLETE    — incoming clutch at hold pressure, outgoing fully released
 *
 * Multi-gear requests (e.g. 6→2 kickdown, 1→3 skip-shift) are walked one
 * step at a time through Plan(): each Tick() advances at most one
 * single-element shift. The state machine never attempts a multi-element
 * shift directly because the 8HP hydraulic system is not designed for it
 * (would require multiple proportional valves to coordinate beyond what
 * the controller can guarantee in real time).
 *
 * No CAN dependencies. The state machine produces *intent* outputs
 * (target ClutchSet, torque-cut request, fault flags); a higher layer
 * binds those intents to the MAX22200 driver and the CAN protocol.
 */

enum class ShiftPhase : uint8_t {
    Idle = 0,        // engaged in a stable gear; not shifting
    PreFill,         // filling incoming clutch to kiss-point
    TorqueCut,       // waiting for VCU ack of torque pull
    Overlap,         // outgoing draining + incoming ramping
    Complete,        // last step done, going back to Idle
    Limp,            // unrecoverable fault — fall to safe gear
};

enum class ShiftFault : uint8_t {
    None = 0,
    InvalidTargetGear,        // request went to a gear we can't reach
    TorqueCutTimeout,         // VCU didn't ack TorqueCut within budget
    OverlapTimeout,           // overlap window exceeded budget (real slip
                              // would have damaged the clutch by now)
    ClutchTableInconsistent,  // ground-truth check failed at runtime
};

/*
 * Calibration. All times are milliseconds; firmware tick is expected at
 * 1 ms granularity. Defaults below are conservative starting points
 * derived from published 8HP shift-time figures (Greiner & Grumbach 2009
 * cite ~200 ms total shift time including torque blending).
 */
struct ShiftCalibration {
    uint16_t pre_fill_ms        = 30;   // clutch fill to kiss-point
    uint16_t torque_cut_ack_ms  = 50;   // budget for VCU torque-cut ack
    uint16_t overlap_ms         = 120;  // outgoing-drain / incoming-ramp
    uint16_t torque_restore_ms  = 30;   // after Complete, before back to Idle
    uint16_t pre_fill_pct       = 30;   // incoming-clutch pressure during PreFill
    uint16_t hold_pct           = 100;  // steady-state pressure once engaged
};

/*
 * Outputs the shift state machine produces every Tick(). The TCU firmware
 * binds these to the actual MAX22200 channel commands and to the CAN TX
 * frames; nothing in the state machine itself touches hardware or CAN.
 */
struct ShiftCommand {
    Gear        current_gear;     // gear number to publish on CAN
    Gear        target_gear;      // ditto
    ShiftPhase  phase;
    ClutchSet   engaged_set;      // elements at full hold pressure
    ClutchSet   ramping_in_set;   // elements being filled / pressurised
    ClutchSet   ramping_out_set;  // elements being drained
    uint8_t     ramp_progress;    // 0..100 % through the current ramp
    bool        torque_cut_request;
    bool        shift_active;     // for the CAN ShiftInProgress bit
    ShiftFault  fault;
};

class ShiftLogic {
public:
    explicit ShiftLogic(ShiftCalibration cal = {});

    /* Driver intent. May ask for any reachable gear; multi-step paths are
     * walked sequentially. Calling RequestGear() during an active shift
     * updates the latched target — the current single-step shift completes
     * before the new path is planned. */
    void RequestGear(Gear target);

    /* Inputs from elsewhere in the firmware. */
    void SetTorqueCutAck(bool ack)         { torque_cut_ack_ = ack; }
    void SetVehicleStationary(bool stat)   { vehicle_stationary_ = stat; }

    /* 1 ms tick. Returns the current command that the bind layer should
     * project onto solenoids and CAN. */
    ShiftCommand Tick(uint32_t now_ms);

    /* Convenience accessors for tests. */
    Gear        current_gear() const { return current_; }
    Gear        target_gear()  const { return target_; }
    ShiftPhase  phase()        const { return phase_; }
    ShiftFault  fault()        const { return fault_; }

private:
    Gear PlanNextStep() const;     // single-element step from current_ toward target_
    void EnterPhase(ShiftPhase p, uint32_t now_ms);
    bool PhaseElapsed(uint32_t now_ms, uint16_t budget_ms) const {
        return (now_ms - phase_started_ms_) >= budget_ms;
    }

    const ShiftCalibration cal_;
    Gear        current_  = Gear::Neutral;
    Gear        target_   = Gear::Neutral;
    Gear        next_step_ = Gear::Neutral;
    ShiftPhase  phase_    = ShiftPhase::Idle;
    ShiftFault  fault_    = ShiftFault::None;
    uint32_t    phase_started_ms_ = 0;

    bool        torque_cut_ack_     = false;
    bool        vehicle_stationary_ = false;
};

} // namespace zf8hp

#endif // ZF8HP_SHIFT_LOGIC_H
