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

#include "tcu_bind.h"
#include "max22200_regs.h"

#include <cstring>

namespace zf8hp {

/* Status2 fault-bit layout — keep in sync with solenoids.cpp comments. */
constexpr uint16_t FB_SOL_OPEN_LOAD       = 1u << 0;
constexpr uint16_t FB_SOL_SHORT_TO_SUPPLY = 1u << 1;
constexpr uint16_t FB_OIL_HOT             = 1u << 2;
constexpr uint16_t FB_PRESS_LOW           = 1u << 3;
constexpr uint16_t FB_SPEED_SENSOR        = 1u << 4;
constexpr uint16_t FB_LIN_COMM            = 1u << 5;
constexpr uint16_t FB_CAN_STALE           = 1u << 6;
constexpr uint16_t FB_SOL_OVER_CURRENT    = 1u << 7;
constexpr uint16_t FB_PARK_SENSOR         = 1u << 8;

TcuBind::TcuBind(TcuIo io, SolenoidCalibration cal)
    : io_(io), cal_(cal) {}

/* ------------------------------------------------------------------ */
/* CAN inbound — driver intent from the VCU                           */
/* ------------------------------------------------------------------ */

void TcuBind::OnCanRx(uint32_t can_id, const uint8_t bytes[8], uint8_t dlc) {
    if (!can_.DecodeRx(can_id, bytes, dlc)) return;

    if (can_id == ZF8HP_TCU_VCU_GEAR_REQUEST_FRAME_ID) {
        /* Decode locally — Can_ZF8HP also latches the struct but we
         * want the raw target-gear field to drive the state machine. */
        zf8hp_tcu_vcu_gear_request_t req{};
        zf8hp_tcu_vcu_gear_request_unpack(&req, bytes, dlc);

        switch (req.target_gear) {
        case ZF8HP_TCU_VCU_GEAR_REQUEST_TARGET_GEAR_P_CHOICE:
            shift_.RequestGear(Gear::Neutral);
            park_.RequestEngaged(true);
            break;
        case ZF8HP_TCU_VCU_GEAR_REQUEST_TARGET_GEAR_N_CHOICE:
            shift_.RequestGear(Gear::Neutral);
            park_.RequestEngaged(false);
            break;
        case ZF8HP_TCU_VCU_GEAR_REQUEST_TARGET_GEAR_R_CHOICE:
            shift_.RequestGear(Gear::Reverse);
            park_.RequestEngaged(false);
            break;
        case ZF8HP_TCU_VCU_GEAR_REQUEST_TARGET_GEAR_D_CHOICE:
            /* "D" without a manual override = Forward1 as a baseline.
             * Real shift scheduling against speed/throttle is the
             * VCU's call, not ours. */
            shift_.RequestGear(Gear::Forward1);
            park_.RequestEngaged(false);
            break;
        case ZF8HP_TCU_VCU_GEAR_REQUEST_TARGET_GEAR_M1_CHOICE:
        case ZF8HP_TCU_VCU_GEAR_REQUEST_TARGET_GEAR_M2_CHOICE:
        case ZF8HP_TCU_VCU_GEAR_REQUEST_TARGET_GEAR_M3_CHOICE:
        case ZF8HP_TCU_VCU_GEAR_REQUEST_TARGET_GEAR_M4_CHOICE:
        case ZF8HP_TCU_VCU_GEAR_REQUEST_TARGET_GEAR_M5_CHOICE:
        case ZF8HP_TCU_VCU_GEAR_REQUEST_TARGET_GEAR_M6_CHOICE:
        case ZF8HP_TCU_VCU_GEAR_REQUEST_TARGET_GEAR_M7_CHOICE:
        case ZF8HP_TCU_VCU_GEAR_REQUEST_TARGET_GEAR_M8_CHOICE: {
            uint8_t manual_gear =
                req.target_gear -
                ZF8HP_TCU_VCU_GEAR_REQUEST_TARGET_GEAR_M1_CHOICE + 1;
            shift_.RequestGear(static_cast<Gear>(manual_gear));
            park_.RequestEngaged(false);
            break;
        }
        default:
            /* S, Limp, Invalid: hold current target. */
            break;
        }
        last_vcu_request_ms_ = vcu_request_seen_at_ms_;
        vcu_request_ever_seen_ = true;
        vcu_stale_ = false;
        fault_bits_ &= ~FB_CAN_STALE;
    }
}

/* ------------------------------------------------------------------ */
/* Per-tick orchestrator                                              */
/* ------------------------------------------------------------------ */

void TcuBind::Tick(uint32_t now_ms) {
    /* CAN-stale detection (HARA T007 / STR008). Once we've ever seen
     * a VCU frame, run the staleness clock from the last RX time. */
    vcu_request_seen_at_ms_ = now_ms;
    if (vcu_request_ever_seen_ &&
        (now_ms - last_vcu_request_ms_) > kVcuStaleThresholdMs) {
        vcu_stale_ = true;
        fault_bits_ |= FB_CAN_STALE;
    }

    RunShiftAndPark(now_ms);

    auto due = [&](uint32_t last_ms, uint16_t cadence) -> bool {
        if (last_ms == UINT32_MAX) return true;       // first call
        return (now_ms - last_ms) >= cadence;
    };

    if (due(last_solenoid_loop_ms_, kSolenoidLoopMs)) {
        EmitSolenoids(now_ms);
        last_solenoid_loop_ms_ = now_ms;
    }

    if (due(last_fault_poll_ms_, kFaultPollMs)) {
        PollMaxFaults(now_ms);
        last_fault_poll_ms_ = now_ms;
    }

    EmitCanStatus(now_ms);
}

/* ------------------------------------------------------------------ */
/* Sub-orchestrators                                                  */
/* ------------------------------------------------------------------ */

void TcuBind::RunShiftAndPark(uint32_t now_ms) {
    /* Plumb the torque-cut handshake from VCU -> shift state machine. */
    shift_.SetTorqueCutAck(can_.VcuTorqueCutAck());
    last_shift_cmd_ = shift_.Tick(now_ms);

    /* Park: live sensor read + latched VCU vehicle speed. The bind
     * layer overrides park_sensors.vehicle_speed_kmh_x100 from the
     * latched VCU info because the park subsystem mustn't trust an
     * untrusted local sensor for its critical vehicle-speed gate. */
    ParkSensors sensors{false, false, 0};
    if (io_.read_park_sensors) {
        sensors = io_.read_park_sensors();
    }
    last_park_cmd_ = park_.Tick(now_ms, sensors);

    if (last_park_cmd_.fault == ParkFault::SensorImpossibleReading) {
        fault_bits_ |= FB_PARK_SENSOR;
    } else {
        fault_bits_ &= ~FB_PARK_SENSOR;
    }

    /* Track shift completions for the count published in Status2. */
    if (last_shift_cmd_.phase == ShiftPhase::Idle &&
        last_shift_cmd_.current_gear != last_completed_gear_) {
        ++shift_count_;
        last_completed_gear_ = last_shift_cmd_.current_gear;
    }
}

void TcuBind::EmitSolenoids(uint32_t /*now_ms*/) {
    /* The MAX22200 cares about which channels should be ENABLED at
     * this instant. During an Overlap phase, both the outgoing and
     * incoming clutches are partially energised; the per-solenoid
     * current waveform inside the chip handles the actual ramp.
     * Here we mark both as "engaged" so neither is fully off. */
    ClutchSet active = static_cast<ClutchSet>(
        last_shift_cmd_.engaged_set |
        last_shift_cmd_.ramping_in_set |
        last_shift_cmd_.ramping_out_set
    );
    uint8_t engagement_mask = static_cast<uint8_t>(active & 0x1Fu);

    /* Overlay park solenoids. Mutual exclusion is enforced inside
     * ParkLock — at most one of {hold, release} fires per tick. */
    if (last_park_cmd_.hold_energise) {
        engagement_mask |= SolenoidBit(SolenoidId::ParkHold);
    }
    if (last_park_cmd_.release_energise) {
        engagement_mask |= SolenoidBit(SolenoidId::ParkRelease);
    }

    /* Build per-chip frame batches and emit them. */
    max22200::SpiFrame frames[8];
    uint8_t ids[8];

    for (uint8_t chip = 0; chip < 2; ++chip) {
        uint8_t n = Solenoids::BuildFramesForChipMask(
            chip, engagement_mask,
            cal_.hit_ma_per_solenoid, cal_.hold_ma_per_solenoid,
            frames, ids);
        for (uint8_t i = 0; i < n; ++i) {
            if (io_.spi_write_max22200) {
                io_.spi_write_max22200(chip, frames[i].bytes);
            }
        }
    }
}

void TcuBind::PollMaxFaults(uint32_t /*now_ms*/) {
    if (!io_.spi_read_fault_status) return;

    uint32_t reg0 = io_.spi_read_fault_status(0);
    uint32_t reg1 = io_.spi_read_fault_status(1);

    ChannelFault chip0[8];
    ChannelFault chip1[8];
    Solenoids::DecodeFaults(reg0, chip0);
    Solenoids::DecodeFaults(reg1, chip1);

    uint16_t solenoid_bits = Solenoids::FaultsToTcuStatus2Bits(chip0, chip1);

    /* Re-apply solenoid bits each poll so transients clear naturally. */
    fault_bits_ &= ~(FB_SOL_OPEN_LOAD | FB_SOL_SHORT_TO_SUPPLY |
                       FB_SOL_OVER_CURRENT);
    fault_bits_ |= solenoid_bits;
}

void TcuBind::EmitCanStatus(uint32_t now_ms) {
    uint8_t bytes[8];

    auto due = [&](uint32_t last_ms, uint16_t cadence) -> bool {
        if (last_ms == UINT32_MAX) return true;
        return (now_ms - last_ms) >= cadence;
    };

    auto emit = [&](uint32_t id, uint32_t* last_ms) {
        if (can_.PackTx(id, bytes) == 8 && io_.can_send) {
            io_.can_send(id, bytes, 8);
        }
        *last_ms = now_ms;
    };

    /* TCU_Status1 — every 20 ms. */
    if (due(last_status1_ms_, kCadence20msMs)) {
        /* Current shift state -> Status1 fields. */
        uint8_t state = static_cast<uint8_t>(last_shift_cmd_.phase);
        can_.SetStatus1Telemetry(
            static_cast<uint8_t>(last_shift_cmd_.current_gear),
            static_cast<uint8_t>(last_shift_cmd_.target_gear),
            state,
            last_shift_cmd_.shift_active,
            !vcu_stale_,
            fault_bits_ != 0,
            last_park_cmd_.park_lock_engaged
        );
        emit(ZF8HP_TCU_TCU_STATUS1_FRAME_ID, &last_status1_ms_);
    }

    /* TCU_ShiftStatus — every 20 ms. */
    if (due(last_shift_status_ms_, kCadence20msMs)) {
        can_.SetShiftStatusTelemetry(
            static_cast<uint8_t>(last_shift_cmd_.phase),
            last_shift_cmd_.torque_cut_request,
            last_shift_cmd_.shift_active,
            static_cast<uint8_t>(last_shift_cmd_.fault),
            last_shift_cmd_.ramp_progress,
            static_cast<uint16_t>(now_ms - last_shift_status_ms_),
            static_cast<uint8_t>(last_shift_cmd_.engaged_set),
            static_cast<uint8_t>(ClutchesFor(last_shift_cmd_.target_gear)),
            static_cast<uint8_t>(last_shift_cmd_.ramping_in_set),
            static_cast<uint8_t>(last_shift_cmd_.ramping_out_set)
        );
        emit(ZF8HP_TCU_TCU_SHIFT_STATUS_FRAME_ID, &last_shift_status_ms_);
    }

    /* TCU_Status2 — every 100 ms. */
    if (due(last_status2_ms_, kCadence100msMs)) {
        can_.SetStatus2Telemetry(fault_bits_, shift_count_, /*hw_temp*/ 25);
        emit(ZF8HP_TCU_TCU_STATUS2_FRAME_ID, &last_status2_ms_);
    }

    /* TCU_PumpStatus — every 100 ms. The LIN driver is expected to
     * call SetPumpStatusTelemetry independently; here we just emit. */
    if (due(last_pump_status_ms_, kCadence100msMs)) {
        emit(ZF8HP_TCU_TCU_PUMP_STATUS_FRAME_ID, &last_pump_status_ms_);
    }
}

} // namespace zf8hp
