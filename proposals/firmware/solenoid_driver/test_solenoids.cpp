#include "solenoids.h"
#include "test_list.h"

#include <iostream>

using namespace std;
using namespace zf8hp;

/* ----------------------------------------------------------------- */
/* Current / time encoding                                           */
/* ----------------------------------------------------------------- */

static void TestMaToCodeEncodesFullScale() {
    /* 1000 mA must encode as the maximum 7-bit code (127). */
    ASSERT(max22200::MaToCode(1000) == 127);
    ASSERT(max22200::MaToCode(2000) == 127);  // clamped
    ASSERT(max22200::MaToCode(0) == 0);
}

static void TestMaToCodeIsApproximatelyLinear() {
    /* 500 mA should be in the middle of the range, ±2 codes. */
    uint8_t mid = max22200::MaToCode(500);
    ASSERT(mid >= 60 && mid <= 67);
}

static void TestCodeToMaInvertsMaToCode() {
    /* round-trip the boundary values and a sample mid-range. */
    ASSERT(max22200::CodeToMa(0) == 0);
    ASSERT(max22200::CodeToMa(127) == 1000);
    /* 500 mA -> code -> back: should be within one LSB (~7.87 mA). */
    uint16_t back = max22200::CodeToMa(max22200::MaToCode(500));
    ASSERT(back >= 492 && back <= 508);
}

static void TestMsToHitCodeEncodesFullScale() {
    ASSERT(max22200::MsToHitCode(0) == 0);
    ASSERT(max22200::MsToHitCode(200) == 127);
    ASSERT(max22200::MsToHitCode(500) == 127);
}

/* ----------------------------------------------------------------- */
/* Channel config write frame                                        */
/* ----------------------------------------------------------------- */

static void TestBuildConfigWriteSetsAddressBits() {
    SolenoidCommand cmd{};
    cmd.channel    = 3;
    cmd.enable     = true;
    cmd.i_hit_ma   = 800;
    cmd.i_hold_ma  = 400;
    cmd.t_hit_ms   = 30;
    cmd.topology   = max22200::Topology::LowSide;

    auto f = Solenoids::BuildConfigWrite(cmd);
    /* Address byte: write bit 0, addr = Cfg_Ch3 = 0x04, shifted left by 1. */
    uint8_t expected_addr_byte = max22200::CMD_WRITE_BIT |
                                  (static_cast<uint8_t>(max22200::Reg::Cfg_Ch3) << 1);
    ASSERT(f.bytes[0] == expected_addr_byte);
}

static void TestBuildConfigWriteEncodesCurrents() {
    SolenoidCommand cmd{};
    cmd.channel    = 0;
    cmd.enable     = true;
    cmd.i_hit_ma   = 800;
    cmd.i_hold_ma  = 400;
    cmd.t_hit_ms   = 30;
    cmd.topology   = max22200::Topology::LowSide;

    auto f = Solenoids::BuildConfigWrite(cmd);
    uint32_t v = max22200::DecodeReadResponse(f.bytes);

    uint8_t hit_code  = (v & max22200::CFG_IHIT_MASK)  >> max22200::CFG_IHIT_SHIFT;
    uint8_t hold_code = (v & max22200::CFG_IHOLD_MASK) >> max22200::CFG_IHOLD_SHIFT;
    ASSERT(hit_code  == max22200::MaToCode(800));
    ASSERT(hold_code == max22200::MaToCode(400));
    ASSERT((v & max22200::CFG_ENABLE) != 0);
}

static void TestBuildDisableProducesZeroPayload() {
    auto f = Solenoids::BuildDisable(0, 5);
    /* Address byte for Cfg_Ch5. Payload bytes all zero. */
    uint8_t expected_addr_byte = max22200::CMD_WRITE_BIT |
                                  (static_cast<uint8_t>(max22200::Reg::Cfg_Ch5) << 1);
    ASSERT(f.bytes[0] == expected_addr_byte);
    ASSERT(f.bytes[1] == 0);
    ASSERT(f.bytes[2] == 0);
    ASSERT(f.bytes[3] == 0);
}

/* ----------------------------------------------------------------- */
/* Per-chip mask -> frame batch                                      */
/* ----------------------------------------------------------------- */

static void TestBuildFramesForChip0PicksOnlyChip0Solenoids() {
    /* Engagement mask: ClutchA, ClutchD, ClutchE engaged
     * (gear 1 in our cited table) — all on chip 0. */
    uint8_t engaged = SolenoidBit(SolenoidId::ClutchA) |
                       SolenoidBit(SolenoidId::ClutchD) |
                       SolenoidBit(SolenoidId::ClutchE);
    uint16_t hit[9]; uint16_t hold[9];
    for (int i = 0; i < 9; ++i) { hit[i] = 800; hold[i] = 400; }

    max22200::SpiFrame out[8];
    uint8_t ids[8];
    uint8_t n = Solenoids::BuildFramesForChipMask(0, engaged, hit, hold, out, ids);

    /* Chip 0 carries 7 solenoids (A..E + TCC + LinePressure) per the
     * binding table, so we should get exactly 7 frames regardless of
     * how many are engaged. */
    ASSERT(n == 7);
}

static void TestBuildFramesForChip1PicksOnlyChip1Solenoids() {
    uint8_t engaged = SolenoidBit(SolenoidId::ParkHold);
    uint16_t hit[9]; uint16_t hold[9];
    for (int i = 0; i < 9; ++i) { hit[i] = 800; hold[i] = 800; }

    max22200::SpiFrame out[8];
    uint8_t ids[8];
    uint8_t n = Solenoids::BuildFramesForChipMask(1, engaged, hit, hold, out, ids);

    /* Chip 1 carries Park Hold + Park Release. */
    ASSERT(n == 2);
    /* The first frame should be for ParkHold which is enabled. */
    bool found_engaged = false;
    bool found_disabled = false;
    for (uint8_t i = 0; i < n; ++i) {
        uint32_t v = max22200::DecodeReadResponse(out[i].bytes);
        bool en = (v & max22200::CFG_ENABLE) != 0;
        if (en && ids[i] == static_cast<uint8_t>(SolenoidId::ParkHold))
            found_engaged = true;
        if (!en && ids[i] == static_cast<uint8_t>(SolenoidId::ParkRelease))
            found_disabled = true;
    }
    ASSERT(found_engaged);
    ASSERT(found_disabled);
}

/* ----------------------------------------------------------------- */
/* Fault decoding                                                    */
/* ----------------------------------------------------------------- */

static void TestDecodeFaultsExtractsPerChannel() {
    /* Channel 2 has open-load (bit 6 = 1, 3*2+0 = 6 -> 1<<6 = 0x40).
     * Channel 5 has over-current (bit 17 = 1, 3*5+2 = 17 -> 1<<17 = 0x20000). */
    uint32_t fault_reg = (1u << 6) | (1u << 17);
    ChannelFault out[8];
    Solenoids::DecodeFaults(fault_reg, out);

    ASSERT(out[2].open_load);
    ASSERT(!out[2].short_to_supply);
    ASSERT(!out[2].over_current);

    ASSERT(out[5].over_current);
    ASSERT(!out[5].open_load);

    /* All others should be clean. */
    for (uint8_t c = 0; c < 8; ++c) {
        if (c == 2 || c == 5) continue;
        ASSERT(!out[c].open_load);
        ASSERT(!out[c].short_to_supply);
        ASSERT(!out[c].over_current);
    }
}

static void TestFaultsToTcuStatus2Bits() {
    ChannelFault chip0[8] = {};
    ChannelFault chip1[8] = {};
    chip0[2].open_load = true;
    chip1[1].over_current = true;

    uint16_t bits = Solenoids::FaultsToTcuStatus2Bits(chip0, chip1);
    /* bit 0 = open-load, bit 7 = over-current per the documented layout. */
    ASSERT(bits & (1u << 0));
    ASSERT(bits & (1u << 7));
    ASSERT((bits & (1u << 1)) == 0);
}

/* ----------------------------------------------------------------- */
/* Binding table sanity                                              */
/* ----------------------------------------------------------------- */

static void TestBindingTableHasNineSolenoids() {
    ASSERT(static_cast<uint8_t>(SolenoidId::COUNT) == 9);
}

static void TestNoTwoSolenoidsShareAChannelOnSameChip() {
    /* The cardinal safety property: no two TCM pins drive the same
     * MAX22200 channel on the same chip. The compile-time table is
     * the authoritative source; this test guards against a bad edit. */
    for (uint8_t i = 0; i < 9; ++i) {
        for (uint8_t j = i + 1; j < 9; ++j) {
            const auto& a = kSolenoidBinding[i];
            const auto& b = kSolenoidBinding[j];
            ASSERT(!(a.chip_index == b.chip_index && a.channel == b.channel));
        }
    }
}

void SolenoidsTest::RunTest() {
    TestMaToCodeEncodesFullScale();
    TestMaToCodeIsApproximatelyLinear();
    TestCodeToMaInvertsMaToCode();
    TestMsToHitCodeEncodesFullScale();
    TestBuildConfigWriteSetsAddressBits();
    TestBuildConfigWriteEncodesCurrents();
    TestBuildDisableProducesZeroPayload();
    TestBuildFramesForChip0PicksOnlyChip0Solenoids();
    TestBuildFramesForChip1PicksOnlyChip1Solenoids();
    TestDecodeFaultsExtractsPerChannel();
    TestFaultsToTcuStatus2Bits();
    TestBindingTableHasNineSolenoids();
    TestNoTwoSolenoidsShareAChannelOnSameChip();
}
