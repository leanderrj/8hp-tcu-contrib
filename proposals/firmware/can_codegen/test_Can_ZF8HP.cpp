/* Drop-in unit test for Stm32-vcu's existing test/ harness.
 *
 * Verifies the cantools-generated codec round-trips every frame in our
 * DBC, and that the C++ wrapper (Can_ZF8HP) latches received status
 * correctly and clamps inputs on the TX side.
 */

#include "Can_ZF8HP.h"
#include "test_list.h"

#include <cstring>
#include <iostream>

using namespace std;

static void TestGearRequestRoundTrip() {
    Can_ZF8HP can;
    can.SetTargetGear(ZF8HP_TCU_VCU_GEAR_REQUEST_TARGET_GEAR_D_CHOICE);
    can.SetDriveMode(ZF8HP_TCU_VCU_GEAR_REQUEST_DRIVE_MODE_SPORT_CHOICE);
    can.SetAccelPedal(47.5f);
    can.SetTorqueRequest(-120);
    can.SetVehicleSpeed(88.42f);
    can.SetBrakePressed(false);
    can.SetVcuReady(true);

    uint8_t bytes[8] = {0};
    uint8_t len = can.PackTx(ZF8HP_TCU_VCU_GEAR_REQUEST_FRAME_ID, bytes);
    ASSERT(len == 8);

    /* Decode the same bytes via the underlying C codec to verify the
     * binary representation. */
    zf8hp_tcu_vcu_gear_request_t round = {};
    int rc = zf8hp_tcu_vcu_gear_request_unpack(&round, bytes, 8);
    ASSERT(rc >= 0);
    ASSERT(round.target_gear == ZF8HP_TCU_VCU_GEAR_REQUEST_TARGET_GEAR_D_CHOICE);
    ASSERT(round.drive_mode == ZF8HP_TCU_VCU_GEAR_REQUEST_DRIVE_MODE_SPORT_CHOICE);
    ASSERT(round.accel_pedal == 95);    /* 47.5 / 0.5 */
    ASSERT(round.torque_request == -120);
    ASSERT(round.vehicle_speed == 8842); /* 88.42 / 0.01 */
    ASSERT(round.brake_pressed == 0);
    ASSERT(round.vcu_ready == 1);
}

static void TestStatus1DecodeLatchesValues() {
    Can_ZF8HP can;

    /* Synthesize a known status frame: gear 4, target D, state Drive,
     * input 2400 rpm, output 1800 rpm, oil 78 °C, line 12.4 bar. */
    zf8hp_tcu_tcu_status1_t s1 = {};
    s1.current_gear      = ZF8HP_TCU_TCU_STATUS1_CURRENT_GEAR_G4_CHOICE;
    s1.target_gear_echo  = ZF8HP_TCU_TCU_STATUS1_TARGET_GEAR_ECHO_D_CHOICE;
    s1.tcu_state         = ZF8HP_TCU_TCU_STATUS1_TCU_STATE_DRIVE_CHOICE;
    s1.shift_in_progress = 0;
    s1.tcu_ready         = 1;
    s1.input_shaft_rpm   = 2400;
    s1.output_shaft_rpm  = 1800;
    s1.oil_temp          = 78;
    s1.line_pressure     = 124; /* raw — DBC scale 0.1 → 12.4 bar */

    uint8_t bytes[8] = {0};
    int len = zf8hp_tcu_tcu_status1_pack(bytes, &s1, 8);
    ASSERT(len == 8);

    bool ok = can.DecodeRx(ZF8HP_TCU_TCU_STATUS1_FRAME_ID, bytes, 8);
    ASSERT(ok);
    ASSERT(can.CurrentGear() == ZF8HP_TCU_TCU_STATUS1_CURRENT_GEAR_G4_CHOICE);
    ASSERT(can.InputShaftRpm() == 2400);
    ASSERT(can.OutputShaftRpm() == 1800);
    ASSERT(can.OilTemp() == 78);
    ASSERT(can.LinePressureBar() > 12.39f && can.LinePressureBar() < 12.41f);
    ASSERT(can.Status1Decodes() == 1);
    ASSERT(can.DecodeErrors() == 0);
}

static void TestPumpStatusDecode() {
    Can_ZF8HP can;
    ASSERT(!can.PumpFrameSeen()); /* default false until first decode */

    zf8hp_tcu_tcu_pump_status_t p = {};
    p.pump_state    = ZF8HP_TCU_TCU_PUMP_STATUS_PUMP_STATE_RUN_CHOICE;
    p.pump_run_ack  = 1;
    p.pump_rpm      = 4256;
    p.pump_voltage  = 136; /* 13.6 V */

    uint8_t bytes[8] = {0};
    zf8hp_tcu_tcu_pump_status_pack(bytes, &p, 8);
    can.DecodeRx(ZF8HP_TCU_TCU_PUMP_STATUS_FRAME_ID, bytes, 8);

    ASSERT(can.PumpFrameSeen());
    ASSERT(can.PumpRpm() == 4256);
    ASSERT(can.PumpVoltage() > 13.59f && can.PumpVoltage() < 13.61f);
}

static void TestUnknownIdIsIgnored() {
    Can_ZF8HP can;
    uint8_t junk[8] = {0xDE, 0xAD, 0xBE, 0xEF, 0x12, 0x34, 0x56, 0x78};
    bool ok = can.DecodeRx(0x123, junk, 8);
    ASSERT(!ok);
    ASSERT(can.DecodeErrors() == 0); /* not a decode error - just not ours */
}

static void TestShortFrameIsRejected() {
    Can_ZF8HP can;
    uint8_t bytes[8] = {0};
    bool ok = can.DecodeRx(ZF8HP_TCU_TCU_STATUS1_FRAME_ID, bytes, 4);
    ASSERT(!ok);
    ASSERT(can.DecodeErrors() == 1);
}

static void TestAccelPedalIsClampedAndScaled() {
    Can_ZF8HP can;
    can.SetAccelPedal(150.0f);
    can.SetVcuReady(true);
    uint8_t bytes[8] = {0};
    can.PackTx(ZF8HP_TCU_VCU_GEAR_REQUEST_FRAME_ID, bytes);
    zf8hp_tcu_vcu_gear_request_t round = {};
    zf8hp_tcu_vcu_gear_request_unpack(&round, bytes, 8);
    ASSERT(round.accel_pedal == 200); /* 100% / 0.5 = 200 */

    can.SetAccelPedal(-5.0f);
    can.PackTx(ZF8HP_TCU_VCU_GEAR_REQUEST_FRAME_ID, bytes);
    zf8hp_tcu_vcu_gear_request_unpack(&round, bytes, 8);
    ASSERT(round.accel_pedal == 0);
}

static void TestCounterIncrementsOnEachPack() {
    Can_ZF8HP can;
    uint8_t bytes[8] = {0};

    can.PackTx(ZF8HP_TCU_VCU_GEAR_REQUEST_FRAME_ID, bytes);
    zf8hp_tcu_vcu_gear_request_t r = {};
    zf8hp_tcu_vcu_gear_request_unpack(&r, bytes, 8);
    uint8_t c0 = r.counter520;

    can.PackTx(ZF8HP_TCU_VCU_GEAR_REQUEST_FRAME_ID, bytes);
    zf8hp_tcu_vcu_gear_request_unpack(&r, bytes, 8);
    uint8_t c1 = r.counter520;

    ASSERT(((c0 + 1) & 0x0F) == c1);
}

void Can_ZF8HPTest::RunTest() {
    TestGearRequestRoundTrip();
    TestStatus1DecodeLatchesValues();
    TestPumpStatusDecode();
    TestUnknownIdIsIgnored();
    TestShortFrameIsRejected();
    TestAccelPedalIsClampedAndScaled();
    TestCounterIncrementsOnEachPack();
}
