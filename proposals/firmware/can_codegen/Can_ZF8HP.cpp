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

#include "Can_ZF8HP.h"

Can_ZF8HP::Can_ZF8HP() {
    /* Default request: TCU, please park. Conservative startup state. */
    txGearReq.target_gear  = ZF8HP_TCU_VCU_GEAR_REQUEST_TARGET_GEAR_P_CHOICE;
    txGearReq.drive_mode   = ZF8HP_TCU_VCU_GEAR_REQUEST_DRIVE_MODE_COMFORT_CHOICE;
    txGearReq.vcu_ready    = 0;
}

bool Can_ZF8HP::DecodeRx(uint32_t canId, const uint8_t bytes[8], uint8_t dlc) {
    if (dlc < 8) { ++decodeErrors; return false; }

    int rc = -1;
    switch (canId) {
    case ZF8HP_TCU_TCU_STATUS1_FRAME_ID:
        rc = zf8hp_tcu_tcu_status1_unpack(&latchedStatus1, bytes, dlc);
        if (rc >= 0) { ++s1Decodes; return true; }
        break;

    case ZF8HP_TCU_TCU_STATUS2_FRAME_ID:
        rc = zf8hp_tcu_tcu_status2_unpack(&latchedStatus2, bytes, dlc);
        if (rc >= 0) { ++s2Decodes; return true; }
        break;

    case ZF8HP_TCU_TCU_PUMP_STATUS_FRAME_ID:
        rc = zf8hp_tcu_tcu_pump_status_unpack(&latchedPump, bytes, dlc);
        if (rc >= 0) { ++pumpDecodes; pumpFrameSeen = true; return true; }
        break;

    case ZF8HP_TCU_TCU_SHIFT_STATUS_FRAME_ID:
        rc = zf8hp_tcu_tcu_shift_status_unpack(&latchedShift, bytes, dlc);
        if (rc >= 0) { ++shiftDecodes; shiftFrameSeen = true; return true; }
        break;

    /* The TCU side (i.e. the bind layer running on the in-Mechatronik
     * board) listens for VCU frames so it can forward driver intent
     * to the shift / park logic. */
    case ZF8HP_TCU_VCU_GEAR_REQUEST_FRAME_ID:
        rc = zf8hp_tcu_vcu_gear_request_unpack(&latchedGearReq, bytes, dlc);
        if (rc >= 0) return true;
        break;

    case ZF8HP_TCU_VCU_VEHICLE_INFO_FRAME_ID:
        rc = zf8hp_tcu_vcu_vehicle_info_unpack(&latchedVehInfo, bytes, dlc);
        if (rc >= 0) return true;
        break;

    default:
        return false; /* not one of ours */
    }
    ++decodeErrors;
    return false;
}

uint8_t Can_ZF8HP::PackTx(uint32_t canId, uint8_t bytes[8]) {
    int rc = -1;
    switch (canId) {
    case ZF8HP_TCU_VCU_GEAR_REQUEST_FRAME_ID:
        txGearReq.counter520 = (uint8_t)(cnt520 & 0x0F);
        rc = zf8hp_tcu_vcu_gear_request_pack(bytes, &txGearReq, 8);
        if (rc < 0) return 0;
        cnt520 = (uint8_t)((cnt520 + 1) & 0x0F);
        return 8;

    case ZF8HP_TCU_VCU_VEHICLE_INFO_FRAME_ID:
        txVehInfo.counter521 = (uint8_t)(cnt521 & 0x0F);
        rc = zf8hp_tcu_vcu_vehicle_info_pack(bytes, &txVehInfo, 8);
        if (rc < 0) return 0;
        cnt521 = (uint8_t)((cnt521 + 1) & 0x0F);
        return 8;

    case ZF8HP_TCU_TCU_STATUS1_FRAME_ID:
        rc = zf8hp_tcu_tcu_status1_pack(bytes, &txStatus1, 8);
        return (rc < 0) ? 0 : 8;

    case ZF8HP_TCU_TCU_STATUS2_FRAME_ID:
        rc = zf8hp_tcu_tcu_status2_pack(bytes, &txStatus2, 8);
        return (rc < 0) ? 0 : 8;

    case ZF8HP_TCU_TCU_SHIFT_STATUS_FRAME_ID:
        rc = zf8hp_tcu_tcu_shift_status_pack(bytes, &txShift, 8);
        return (rc < 0) ? 0 : 8;

    case ZF8HP_TCU_TCU_PUMP_STATUS_FRAME_ID:
        rc = zf8hp_tcu_tcu_pump_status_pack(bytes, &txPump, 8);
        return (rc < 0) ? 0 : 8;

    default:
        return 0;
    }
}

void Can_ZF8HP::SetStatus1Telemetry(uint8_t current_gear, uint8_t target_gear_echo,
                                     uint8_t tcu_state, bool shift_in_progress,
                                     bool tcu_ready, bool any_fault,
                                     bool park_lock) {
    txStatus1.current_gear        = current_gear;
    txStatus1.target_gear_echo    = target_gear_echo;
    txStatus1.tcu_state           = tcu_state;
    txStatus1.shift_in_progress   = shift_in_progress ? 1 : 0;
    txStatus1.tcu_ready           = tcu_ready ? 1 : 0;
    txStatus1.any_fault           = any_fault ? 1 : 0;
    txStatus1.park_lock           = park_lock ? 1 : 0;
}

void Can_ZF8HP::SetStatus1Sensors(uint16_t input_rpm, uint16_t output_rpm,
                                    int8_t oil_temp_c, uint8_t line_pressure_raw) {
    txStatus1.input_shaft_rpm  = input_rpm;
    txStatus1.output_shaft_rpm = output_rpm;
    txStatus1.oil_temp         = oil_temp_c;
    txStatus1.line_pressure    = line_pressure_raw;
}

void Can_ZF8HP::SetStatus2Telemetry(uint16_t fault_bits, uint8_t shift_count,
                                      int8_t hw_temp_c,
                                      uint16_t sol_a_current_ma,
                                      uint16_t sol_b_current_ma) {
    txStatus2.fault_bits     = fault_bits;
    txStatus2.shift_count    = shift_count;
    txStatus2.tcu_hw_temp    = hw_temp_c;
    txStatus2.sol_a_current  = sol_a_current_ma;
    txStatus2.sol_b_current  = sol_b_current_ma;
}

void Can_ZF8HP::SetShiftStatusTelemetry(uint8_t shift_phase, bool torque_cut_request,
                                          bool shift_active, uint8_t shift_fault_code,
                                          uint8_t ramp_percent, uint16_t elapsed_ms,
                                          uint8_t current_clutch_set,
                                          uint8_t target_clutch_set,
                                          uint8_t ramping_in_set,
                                          uint8_t ramping_out_set) {
    txShift.shift_phase             = shift_phase;
    txShift.torque_cut_request      = torque_cut_request ? 1 : 0;
    txShift.shift_active            = shift_active ? 1 : 0;
    txShift.shift_fault_code        = shift_fault_code;
    txShift.shift_ramp_percent      = ramp_percent;
    txShift.shift_elapsed_ms        = elapsed_ms;
    txShift.current_clutch_set      = current_clutch_set;
    txShift.target_clutch_set       = target_clutch_set;
    txShift.ramping_in_clutch_set   = ramping_in_set;
    txShift.ramping_out_clutch_set  = ramping_out_set;
}

void Can_ZF8HP::SetPumpStatusTelemetry(uint8_t pump_state, bool run_ack,
                                         bool lin_fault, bool alt_fault,
                                         uint16_t pump_rpm, uint8_t voltage_raw,
                                         uint8_t current_raw, uint8_t retry_count) {
    txPump.pump_state       = pump_state;
    txPump.pump_run_ack     = run_ack ? 1 : 0;
    txPump.pump_lin_fault   = lin_fault ? 1 : 0;
    txPump.pump_alt_fault   = alt_fault ? 1 : 0;
    txPump.pump_rpm         = pump_rpm;
    txPump.pump_voltage     = voltage_raw;
    txPump.pump_current_raw = current_raw;
    txPump.pump_retry_count = retry_count;
}

void Can_ZF8HP::SetTargetGear(uint8_t gearChoice) {
    txGearReq.target_gear = gearChoice;
}

void Can_ZF8HP::SetDriveMode(uint8_t modeChoice) {
    txGearReq.drive_mode = modeChoice;
}

void Can_ZF8HP::SetAccelPedal(float pct) {
    if (pct < 0.f) pct = 0.f;
    if (pct > 100.f) pct = 100.f;
    /* DBC scale 0.5 → raw = pct / 0.5 */
    txGearReq.accel_pedal = (uint8_t)(pct * 2.0f + 0.5f);
}

void Can_ZF8HP::SetTorqueRequest(int16_t nm) {
    txGearReq.torque_request = nm;
}

void Can_ZF8HP::SetVehicleSpeed(float kmh) {
    if (kmh < 0.f) kmh = 0.f;
    if (kmh > 655.35f) kmh = 655.35f;
    /* DBC scale 0.01 */
    txGearReq.vehicle_speed = (uint16_t)(kmh * 100.0f + 0.5f);
}

void Can_ZF8HP::SetBrakePressed(bool b) {
    txGearReq.brake_pressed = b ? 1 : 0;
}

void Can_ZF8HP::SetVcuReady(bool r) {
    txGearReq.vcu_ready = r ? 1 : 0;
}

void Can_ZF8HP::SetActualTorque(int16_t nm) {
    txVehInfo.actual_torque = nm;
}

void Can_ZF8HP::SetMotorRpm(int16_t rpm) {
    txVehInfo.motor_rpm = rpm;
}

void Can_ZF8HP::SetTorqueCutAck(bool ack) {
    txVehInfo.torque_cut_ack = ack ? 1 : 0;
}
