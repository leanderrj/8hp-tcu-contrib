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

#ifndef ZF8HP_TCU_BIND_H
#define ZF8HP_TCU_BIND_H

#include "Can_ZF8HP.h"
#include "park_lock.h"
#include "shift_logic.h"
#include "solenoids.h"
#include <stdint.h>

namespace zf8hp {

/*
 * Bind layer — wires together the four firmware modules into a single
 * per-tick orchestrator. The TCU firmware's main loop calls
 * `bind.Tick(now_ms)` every 1 ms; the bind layer then:
 *
 *   1. Runs ShiftLogic with the latched gear request from CAN.
 *   2. Runs ParkLock with the latched park request and the live
 *      sensor inputs (provided by the ParkSensorReader callback).
 *   3. Translates the resulting clutch / park state into per-channel
 *      MAX22200 commands and emits them via the SpiWriter callback.
 *   4. Latches the resulting status into Can_ZF8HP and emits the four
 *      TCU->VCU CAN frames at their cyclic cadences via the CanWriter
 *      callback.
 *
 * Everything is callback-injected — no peripheral access. That keeps
 * tcu_bind.cpp host-testable: a unit test wires up four std::function
 * stubs that record calls and assert on them.
 *
 * The frame-rate scheduler is intentionally simple: hot frames go out
 * every 20 ms, slow ones every 100 ms, the SPI loop fires every 10 ms.
 * The main loop calls Tick(now_ms); the dispatcher inside decides what
 * to actually publish based on elapsed time since the last emission.
 */

/* Callback signatures. Caller binds these to libopencm3 SPI3, bxCAN,
 * and GPIO reads in the production target; the unit test binds them
 * to recording stubs. */
struct TcuIo {
    /* Called from inside Tick() whenever a per-channel SPI frame
     * should be transmitted. The bind layer batches multiple channel
     * writes into a single Tick() call; the IO layer is expected to
     * emit them in order. `chip_index` selects which MAX22200 (0 or 1)
     * via chip-select. */
    void (*spi_write_max22200)(uint8_t chip_index, const uint8_t bytes[4]);

    /* Read the current FaultStatus register from a chip. Called by
     * the bind layer once per ~100 ms loop. The IO layer should
     * perform a SPI read transaction and return the 24-bit register
     * value. */
    uint32_t (*spi_read_fault_status)(uint8_t chip_index);

    /* Transmit one CAN frame. dlc is always 8 in this protocol. */
    void (*can_send)(uint32_t can_id, const uint8_t bytes[8], uint8_t dlc);

    /* Read the live park-position sensors (TCM pins 13/14) and
     * vehicle speed (latched from the most recent VCU_VehicleInfo
     * frame). */
    ParkSensors (*read_park_sensors)();
};

/* Per-solenoid HIT/HOLD calibration the bind layer applies on top of
 * the kSolenoidBinding defaults. Loaded at boot from a YAML or NVM
 * page; can be overridden per-vehicle without recompiling. */
struct SolenoidCalibration {
    uint16_t hit_ma_per_solenoid[static_cast<uint8_t>(SolenoidId::COUNT)];
    uint16_t hold_ma_per_solenoid[static_cast<uint8_t>(SolenoidId::COUNT)];
};

/* Frame cadences — match the DBC. */
constexpr uint16_t kCadence20msMs  = 20;
constexpr uint16_t kCadence100msMs = 100;
constexpr uint16_t kSolenoidLoopMs = 10;
constexpr uint16_t kFaultPollMs    = 100;

/*
 * The orchestrator. One instance per TCU.
 */
class TcuBind {
public:
    TcuBind(TcuIo io, SolenoidCalibration cal);

    /* Per-tick call from main(). 1 ms granularity. */
    void Tick(uint32_t now_ms);

    /* Inbound CAN frame from the bus. Called from a CAN ISR / RX
     * queue handler. Decodes into Can_ZF8HP and forwards driver
     * intent to ShiftLogic / ParkLock. */
    void OnCanRx(uint32_t can_id, const uint8_t bytes[8], uint8_t dlc);

    /* Test introspection. */
    Gear current_gear() const         { return shift_.current_gear(); }
    Gear target_gear()  const         { return shift_.target_gear(); }
    ShiftPhase shift_phase() const    { return shift_.phase(); }
    ParkState park_state() const      { return park_.state(); }
    uint16_t fault_bits_for_status2() const { return fault_bits_; }
    Can_ZF8HP& can_layer()            { return can_; }

private:
    void RunShiftAndPark(uint32_t now_ms);
    void EmitSolenoids(uint32_t now_ms);
    void PollMaxFaults(uint32_t now_ms);
    void EmitCanStatus(uint32_t now_ms);

    /* Compose engaged + ramping clutch sets into the
     * per-solenoid engagement bitmask the Solenoids layer expects. */
    uint8_t ClutchSetToSolenoidMask(ClutchSet engaged) const;

    TcuIo io_;
    SolenoidCalibration cal_;
    ShiftLogic shift_;
    ParkLock park_;
    Can_ZF8HP can_;

    /* Cadence trackers. Initialized so the first Tick triggers a
     * fire-on-first-call for every periodic emission. */
    uint32_t last_solenoid_loop_ms_ = ~0u;
    uint32_t last_fault_poll_ms_    = ~0u;
    uint32_t last_status1_ms_       = ~0u;
    uint32_t last_status2_ms_       = ~0u;
    uint32_t last_shift_status_ms_  = ~0u;
    uint32_t last_pump_status_ms_   = ~0u;

    /* CAN-stale tracker: explicit "ever seen" flag instead of using
     * 0 as a sentinel, since a real first frame can land at t=0. */
    bool     vcu_request_ever_seen_ = false;
    uint32_t last_vcu_request_ms_   = 0;
    uint32_t vcu_request_seen_at_ms_ = 0;

    uint16_t fault_bits_  = 0;
    uint8_t  shift_count_ = 0;
    Gear     last_completed_gear_ = Gear::Neutral;
    ShiftCommand last_shift_cmd_{};
    ParkCommand  last_park_cmd_{};

    /* CAN-stale detection (HARA T007 / STR008): if we don't see a
     * VCU_GearRequest for 200 ms, hold gear and set FaultBits[CanStale]. */
    static constexpr uint32_t kVcuStaleThresholdMs = 200;
    bool vcu_stale_ = false;
};

} // namespace zf8hp

#endif // ZF8HP_TCU_BIND_H
