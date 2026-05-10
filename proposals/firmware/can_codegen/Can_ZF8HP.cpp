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

    default:
        return 0;
    }
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
