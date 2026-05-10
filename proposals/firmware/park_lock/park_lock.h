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

#ifndef ZF8HP_PARK_LOCK_H
#define ZF8HP_PARK_LOCK_H

#include <stdint.h>

/*
 * ZF G8P75HZ Park-lock state machine.
 *
 * Park is the safety-critical subsystem on the TCM. The mechanical
 * detent is held / released by two solenoids:
 *
 *   TCM pin 5  — Park Hold solenoid
 *   TCM pin 48 — Park Release solenoid
 *
 * and sensed by a two-position switch:
 *
 *   TCM pin 12 — sense ground
 *   TCM pin 13 — Park Pos 1 contact
 *   TCM pin 14 — Park Pos 2 contact
 *
 * The two switch positions disambiguate "pawl mechanically engaged"
 * (Park Pos 1) from "pawl free" (Park Pos 2). Reading both as 0
 * is a wiring fault; reading both as 1 is also a wiring fault.
 *
 * Default-safe behaviour:
 *  - On reset / power loss: solenoids de-energised. The mechanical
 *    detent is sprung to "engaged" so the gearbox lands in Park
 *    naturally; release requires actively energising the Release
 *    solenoid.
 *  - Park Hold and Park Release are NEVER simultaneously commanded.
 *    The state machine enforces mutual exclusion at the output level.
 *  - Engagement request is only honoured if vehicle speed ≤
 *    kEngageMaxKmh; this guards the pawl against a bow-tying impact
 *    if the lever is mishandled at speed.
 *
 * The class doesn't drive solenoids directly — it produces an
 * intent-level command that the bind layer converts into MAX22200
 * channel writes. Same pattern as ShiftLogic.
 */

namespace zf8hp {

enum class ParkState : uint8_t {
    Engaged = 0,        // pawl down, hold solenoid de-energised (sprung)
    Disengaged,         // pawl up, vehicle free to roll / drive
    Engaging,           // briefly energising Hold to assist detent
    Disengaging,        // pulsing Release to lift the pawl
    Fault,              // sense reading impossible — refuse to act
    Init,               // power-on / pre-sense; default-safe assume Engaged
};

enum class ParkFault : uint8_t {
    None = 0,
    SensorImpossibleReading,    // both contacts 0 or both 1
    DisengageBlockedBySpeed,    // requested release while moving
    EngageBlockedByMotion,      // requested engage while moving
    DisengageTimeout,           // pulsed Release for max budget, no transition
    EngageTimeout,              // pulsed Hold for max budget, no transition
};

struct ParkCalibration {
    uint16_t engage_pulse_ms      = 200;   // hold solenoid energising time
    uint16_t disengage_pulse_ms   = 200;   // release solenoid pulse time
    uint16_t engage_budget_ms     = 1000;  // total time before EngageTimeout
    uint16_t disengage_budget_ms  = 1000;  // total before DisengageTimeout
    uint16_t engage_max_kmh_x100  = 200;   // max speed for engage (2.00 km/h)
};

struct ParkSensors {
    bool pos1_contact;        // TCM pin 13 — engaged contact
    bool pos2_contact;        // TCM pin 14 — disengaged contact
    uint16_t vehicle_speed_kmh_x100;  // 0.01 km/h units, matches DBC scale
};

struct ParkCommand {
    bool      hold_energise;     // drive Park Hold solenoid (TCM pin 5)
    bool      release_energise;  // drive Park Release solenoid (TCM pin 48)
    ParkState state;
    ParkFault fault;
    bool      park_lock_engaged; // safe to publish on CAN as ParkLock bit
};

class ParkLock {
public:
    explicit ParkLock(ParkCalibration cal = {});

    /* Driver intent. true = pawl down (Park engaged); false = pawl up. */
    void RequestEngaged(bool engaged) { request_engaged_ = engaged; }

    /* External fault clear (e.g. operator pressed "clear DTCs" on the
     * VCU web UI). Doesn't move the pawl on its own. */
    void ClearFault() { fault_ = ParkFault::None; }

    /* 1 ms tick. Sensors are sampled every call. */
    ParkCommand Tick(uint32_t now_ms, const ParkSensors& sensors);

    /* Test access. */
    ParkState  state()  const { return state_; }
    ParkFault  fault()  const { return fault_; }

private:
    ParkState DecodeSenseState(const ParkSensors& s) const;
    bool      VehicleStationaryEnough(const ParkSensors& s) const;

    const ParkCalibration cal_;
    ParkState state_           = ParkState::Init;
    ParkFault fault_           = ParkFault::None;
    bool      request_engaged_ = true;     // safe default
    uint32_t  phase_started_ms_= 0;
};

} // namespace zf8hp

#endif // ZF8HP_PARK_LOCK_H
