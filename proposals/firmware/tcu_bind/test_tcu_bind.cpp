#include "tcu_bind.h"
#include "test_list.h"
#include "zf8hp_tcu.h"

#include <cstring>
#include <iostream>
#include <vector>

using namespace std;
using namespace zf8hp;

/* ------------------------------------------------------------------ */
/* Recording stubs for the four IO callbacks                          */
/* ------------------------------------------------------------------ */

namespace {

struct SpiCall {
    uint8_t chip;
    uint8_t bytes[4];
};

vector<SpiCall> g_spi_writes;
vector<uint32_t> g_can_ids_sent;
vector<vector<uint8_t>> g_can_payloads_sent;
ParkSensors g_park_sensors{true, false, 0};   // engaged + stationary
uint32_t g_fault_status_chip0 = 0;
uint32_t g_fault_status_chip1 = 0;

void spi_write(uint8_t chip, const uint8_t bytes[4]) {
    SpiCall c;
    c.chip = chip;
    memcpy(c.bytes, bytes, 4);
    g_spi_writes.push_back(c);
}

uint32_t spi_read_fault(uint8_t chip) {
    return chip == 0 ? g_fault_status_chip0 : g_fault_status_chip1;
}

void can_send(uint32_t id, const uint8_t bytes[8], uint8_t /*dlc*/) {
    g_can_ids_sent.push_back(id);
    vector<uint8_t> v(bytes, bytes + 8);
    g_can_payloads_sent.push_back(v);
}

ParkSensors read_park() { return g_park_sensors; }

void reset_stubs() {
    g_spi_writes.clear();
    g_can_ids_sent.clear();
    g_can_payloads_sent.clear();
    g_park_sensors = ParkSensors{true, false, 0};
    g_fault_status_chip0 = 0;
    g_fault_status_chip1 = 0;
}

TcuIo make_io() {
    TcuIo io{};
    io.spi_write_max22200    = spi_write;
    io.spi_read_fault_status = spi_read_fault;
    io.can_send              = can_send;
    io.read_park_sensors     = read_park;
    return io;
}

SolenoidCalibration make_cal() {
    SolenoidCalibration c{};
    for (uint8_t i = 0; i < static_cast<uint8_t>(SolenoidId::COUNT); ++i) {
        c.hit_ma_per_solenoid[i]  = 800;
        c.hold_ma_per_solenoid[i] = 400;
    }
    return c;
}

uint8_t make_gear_request(uint8_t target, uint8_t* out) {
    zf8hp_tcu_vcu_gear_request_t r{};
    r.target_gear = target;
    r.drive_mode  = 0;
    r.vcu_ready   = 1;
    return zf8hp_tcu_vcu_gear_request_pack(out, &r, 8);
}

} // namespace

/* ------------------------------------------------------------------ */
/* Tests                                                              */
/* ------------------------------------------------------------------ */

static void TestTickEmitsStatus1At20ms() {
    reset_stubs();
    TcuBind bind(make_io(), make_cal());

    /* First tick at t=0 emits Status1 (first emission counts). */
    bind.Tick(0);
    bool seen_status1 = false;
    for (auto id : g_can_ids_sent) {
        if (id == ZF8HP_TCU_TCU_STATUS1_FRAME_ID) seen_status1 = true;
    }
    ASSERT(seen_status1);
}

static void TestStatus1FrequencyIs50Hz() {
    reset_stubs();
    TcuBind bind(make_io(), make_cal());

    /* Tick for 200 ms. Status1 should fire at most every 20 ms,
     * so we should see ~10 emissions, not more. */
    for (uint32_t t = 0; t <= 200; ++t) {
        bind.Tick(t);
    }

    int count = 0;
    for (auto id : g_can_ids_sent) {
        if (id == ZF8HP_TCU_TCU_STATUS1_FRAME_ID) ++count;
    }
    ASSERT(count >= 9 && count <= 11);
}

static void TestStatus2FrequencyIs10Hz() {
    reset_stubs();
    TcuBind bind(make_io(), make_cal());
    for (uint32_t t = 0; t <= 1000; ++t) bind.Tick(t);

    int count = 0;
    for (auto id : g_can_ids_sent) {
        if (id == ZF8HP_TCU_TCU_STATUS2_FRAME_ID) ++count;
    }
    ASSERT(count >= 9 && count <= 11);
}

static void TestVcuRequestForDriveStartsShift() {
    reset_stubs();
    TcuBind bind(make_io(), make_cal());

    bind.Tick(0);
    /* Inject D request from VCU. */
    uint8_t req[8];
    make_gear_request(ZF8HP_TCU_VCU_GEAR_REQUEST_TARGET_GEAR_D_CHOICE, req);
    bind.OnCanRx(ZF8HP_TCU_VCU_GEAR_REQUEST_FRAME_ID, req, 8);

    /* Tick forward enough to clear the Neutral->Forward1 shift. */
    for (uint32_t t = 1; t < 500; ++t) bind.Tick(t);

    ASSERT(bind.current_gear() == Gear::Forward1);
}

static void TestVcuRequestForParkAtRestEngagesPark() {
    reset_stubs();
    g_park_sensors = ParkSensors{false, true, 0};   // currently disengaged
    TcuBind bind(make_io(), make_cal());

    /* Drive a few ticks to escape Init. */
    for (uint32_t t = 0; t < 10; ++t) bind.Tick(t);

    uint8_t req[8];
    make_gear_request(ZF8HP_TCU_VCU_GEAR_REQUEST_TARGET_GEAR_P_CHOICE, req);
    bind.OnCanRx(ZF8HP_TCU_VCU_GEAR_REQUEST_FRAME_ID, req, 8);

    /* Park engagement requires several ticks because of the pulse
     * timing in ParkLock. Step until something happens. */
    for (uint32_t t = 11; t < 200; ++t) bind.Tick(t);

    ASSERT(bind.park_state() == ParkState::Engaging ||
           bind.park_state() == ParkState::Engaged);
}

static void TestSolenoidLoopFiresAt100Hz() {
    reset_stubs();
    TcuBind bind(make_io(), make_cal());
    for (uint32_t t = 0; t <= 100; ++t) bind.Tick(t);

    /* Solenoid loop runs every 10 ms. Each loop emits 9 SPI frames
     * (7 chip0 channels + 2 chip1 channels for the bound solenoids).
     * 100 ms / 10 ms = 10 loops, ~90 SPI writes. */
    ASSERT(g_spi_writes.size() >= 80 && g_spi_writes.size() <= 120);
}

static void TestSolenoidWritesAreDistributedAcrossBothChips() {
    reset_stubs();
    TcuBind bind(make_io(), make_cal());
    for (uint32_t t = 0; t <= 50; ++t) bind.Tick(t);

    bool seen_chip0 = false, seen_chip1 = false;
    for (const auto& c : g_spi_writes) {
        if (c.chip == 0) seen_chip0 = true;
        if (c.chip == 1) seen_chip1 = true;
    }
    ASSERT(seen_chip0);
    ASSERT(seen_chip1);
}

static void TestMaxFaultPropagatesToTcuStatus2Bits() {
    reset_stubs();
    /* Pre-load chip 0 channel 2 with an open-load fault before the
     * fault poll fires. */
    g_fault_status_chip0 = (1u << 6); /* channel 2 bit 0 = open-load */

    TcuBind bind(make_io(), make_cal());
    for (uint32_t t = 0; t <= 150; ++t) bind.Tick(t);

    uint16_t bits = bind.fault_bits_for_status2();
    ASSERT((bits & (1u << 0)) != 0);  /* FB_SOL_OPEN_LOAD */
}

static void TestVcuSilenceRaisesCanStaleAfter200ms() {
    reset_stubs();
    TcuBind bind(make_io(), make_cal());

    /* Send one VCU request to start the staleness clock, then go silent. */
    uint8_t req[8];
    make_gear_request(ZF8HP_TCU_VCU_GEAR_REQUEST_TARGET_GEAR_N_CHOICE, req);
    bind.Tick(0);
    bind.OnCanRx(ZF8HP_TCU_VCU_GEAR_REQUEST_FRAME_ID, req, 8);

    /* Now tick for 300 ms with no further CAN. Stale threshold is 200 ms. */
    for (uint32_t t = 1; t <= 300; ++t) bind.Tick(t);

    uint16_t bits = bind.fault_bits_for_status2();
    /* Bit 6 = CanStale per the fault-bit layout. */
    ASSERT((bits & (1u << 6)) != 0);
}

static void TestShiftActiveBitTracksShiftPhase() {
    reset_stubs();
    TcuBind bind(make_io(), make_cal());
    bind.Tick(0);

    uint8_t req[8];
    make_gear_request(ZF8HP_TCU_VCU_GEAR_REQUEST_TARGET_GEAR_D_CHOICE, req);
    bind.OnCanRx(ZF8HP_TCU_VCU_GEAR_REQUEST_FRAME_ID, req, 8);

    /* Sample a shift in progress. */
    bool saw_active = false;
    for (uint32_t t = 1; t < 500; ++t) {
        bind.Tick(t);
        if (bind.shift_phase() != ShiftPhase::Idle) saw_active = true;
    }
    ASSERT(saw_active);
}

void TcuBindTest::RunTest() {
    TestTickEmitsStatus1At20ms();
    TestStatus1FrequencyIs50Hz();
    TestStatus2FrequencyIs10Hz();
    TestVcuRequestForDriveStartsShift();
    TestVcuRequestForParkAtRestEngagesPark();
    TestSolenoidLoopFiresAt100Hz();
    TestSolenoidWritesAreDistributedAcrossBothChips();
    TestMaxFaultPropagatesToTcuStatus2Bits();
    TestVcuSilenceRaisesCanStaleAfter200ms();
    TestShiftActiveBitTracksShiftPhase();
}
