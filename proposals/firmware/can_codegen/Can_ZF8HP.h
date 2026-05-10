/*
 * This file is part of the Zombieverter project.
 *
 * Copyright (C) 2026 ZF_8HP contributor
 *
 * This program is free software: you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation, either version 3 of the License, or
 * (at your option) any later version.
 *
 * Thin C++ wrapper around the cantools-generated C99 codec for the
 * ZF 8HP TCU CAN protocol. The codec lives in zf8hp_tcu.{h,c} and is
 * regenerated from proposals/dbc/zf8hp-tcu.dbc; do not edit it by hand.
 * All glue between the codec and the rest of the VCU (Shifter, Param,
 * CanHardware) belongs in this file.
 */

#ifndef CAN_ZF8HP_H
#define CAN_ZF8HP_H

#include <stdint.h>
extern "C" {
#include "zf8hp_tcu.h"
}

class Can_ZF8HP {
public:
    Can_ZF8HP();

    /* Decode a frame received from the bus. Returns true if the frame
     * matched a known TCU status ID and was successfully unpacked. */
    bool DecodeRx(uint32_t canId, const uint8_t bytes[8], uint8_t dlc);

    /* Pack the most recent VCU→TCU command into bytes ready for transmit.
     * Returns the frame length (always 8 for our protocol) on success or
     * 0 on failure. The caller passes the requested CAN ID to select. */
    uint8_t PackTx(uint32_t canId, uint8_t bytes[8]);

    /* Setters used by the VCU side to populate the next TX. */
    void SetTargetGear(uint8_t gearChoice);
    void SetDriveMode(uint8_t modeChoice);
    void SetAccelPedal(float pct);
    void SetTorqueRequest(int16_t nm);
    void SetVehicleSpeed(float kmh);
    void SetBrakePressed(bool b);
    void SetVcuReady(bool r);
    void SetActualTorque(int16_t nm);
    void SetMotorRpm(int16_t rpm);
    void SetTorqueCutAck(bool ack);

    /* Latched view of the most recent TCU status frames, scaled to
     * physical units. Stays at last-known-good if the TCU stops sending. */
    uint8_t  CurrentGear()      const { return latchedStatus1.current_gear;     }
    uint8_t  TcuState()         const { return latchedStatus1.tcu_state;        }
    bool     ShiftInProgress()  const { return latchedStatus1.shift_in_progress; }
    uint16_t InputShaftRpm()    const { return latchedStatus1.input_shaft_rpm;  }
    uint16_t OutputShaftRpm()   const { return latchedStatus1.output_shaft_rpm; }
    int8_t   OilTemp()          const { return latchedStatus1.oil_temp;         }
    float    LinePressureBar()  const { return latchedStatus1.line_pressure * 0.1f; }
    uint16_t FaultBits()        const { return latchedStatus2.fault_bits;       }
    uint16_t SolACurrentMa()    const { return latchedStatus2.sol_a_current;    }
    uint16_t SolBCurrentMa()    const { return latchedStatus2.sol_b_current;    }
    uint8_t  PumpState()        const { return latchedPump.pump_state;          }
    uint16_t PumpRpm()          const { return latchedPump.pump_rpm;            }
    float    PumpVoltage()      const { return latchedPump.pump_voltage * 0.1f; }
    bool     PumpFrameSeen()    const { return pumpFrameSeen; }

    /* TCU shift handshake (TCU_ShiftStatus, 0x543). */
    uint8_t  ShiftPhase()         const { return latchedShift.shift_phase; }
    bool     TorqueCutRequest()   const { return latchedShift.torque_cut_request; }
    bool     ShiftActive()        const { return latchedShift.shift_active; }
    uint8_t  ShiftFaultCode()     const { return latchedShift.shift_fault_code; }
    uint8_t  ShiftRampPercent()   const { return latchedShift.shift_ramp_percent; }
    uint16_t ShiftElapsedMs()     const { return latchedShift.shift_elapsed_ms; }
    uint8_t  CurrentClutchSet()   const { return latchedShift.current_clutch_set; }
    uint8_t  TargetClutchSet()    const { return latchedShift.target_clutch_set; }
    uint8_t  RampingInClutchSet() const { return latchedShift.ramping_in_clutch_set; }
    uint8_t  RampingOutClutchSet() const { return latchedShift.ramping_out_clutch_set; }
    bool     ShiftFrameSeen()     const { return shiftFrameSeen; }

    /* Per-frame counter / decode statistics — exposable as VCU params. */
    uint16_t Status1Decodes()   const { return s1Decodes; }
    uint16_t Status2Decodes()   const { return s2Decodes; }
    uint16_t ShiftDecodes()     const { return shiftDecodes; }
    uint16_t PumpDecodes()      const { return pumpDecodes; }
    uint16_t DecodeErrors()     const { return decodeErrors; }

private:
    zf8hp_tcu_tcu_status1_t      latchedStatus1{};
    zf8hp_tcu_tcu_status2_t      latchedStatus2{};
    zf8hp_tcu_tcu_shift_status_t latchedShift{};
    zf8hp_tcu_tcu_pump_status_t  latchedPump{};
    zf8hp_tcu_vcu_gear_request_t txGearReq{};
    zf8hp_tcu_vcu_vehicle_info_t txVehInfo{};

    bool     pumpFrameSeen   = false;
    bool     shiftFrameSeen  = false;
    uint16_t s1Decodes       = 0;
    uint16_t s2Decodes       = 0;
    uint16_t shiftDecodes    = 0;
    uint16_t pumpDecodes     = 0;
    uint16_t decodeErrors    = 0;
    uint8_t  cnt520          = 0;
    uint8_t  cnt521          = 0;
};

#endif // CAN_ZF8HP_H
