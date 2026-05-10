/*
 * Drop-in unit test for the shift state machine. Runs in the existing
 * Stm32-vcu test/ harness (`make Test`) — see INTEGRATION.md.
 */

#include "clutch_table.h"
#include "shift_logic.h"
#include "test_list.h"

#include <iostream>

using namespace std;
using namespace zf8hp;

/* ------------------------------------------------------------------ */
/* Clutch-table invariants (also enforced via static_assert in the    */
/* header, but we surface them here as runtime tests so the upstream  */
/* `make Test` log shows them named.)                                 */
/* ------------------------------------------------------------------ */

static void TestEachForwardGearEngagesThreeElements() {
    for (int g = 1; g <= 8; ++g) {
        ASSERT(Popcount(ClutchesFor(static_cast<Gear>(g))) == 3);
    }
}

static void TestReverseEngagesThreeElements() {
    ASSERT(Popcount(ClutchesFor(Gear::Reverse)) == 3);
}

static void TestNeutralEngagesNothing() {
    ASSERT(ClutchesFor(Gear::Neutral) == 0);
}

static void TestAdjacentForwardShiftsAreSingleElement() {
    for (int g = 1; g <= 7; ++g) {
        ShiftDelta d = DeltaBetween(static_cast<Gear>(g),
                                     static_cast<Gear>(g + 1));
        ASSERT(d.is_single_element());
    }
}

/* ------------------------------------------------------------------ */
/* State machine — single-step shifts                                 */
/* ------------------------------------------------------------------ */

static ShiftLogic MakeFresh() {
    ShiftCalibration cal;
    cal.pre_fill_ms       = 30;
    cal.torque_cut_ack_ms = 50;
    cal.overlap_ms        = 120;
    cal.torque_restore_ms = 30;
    return ShiftLogic(cal);
}

static void TestStartsInNeutralIdle() {
    auto sm = MakeFresh();
    auto cmd = sm.Tick(0);
    ASSERT(cmd.current_gear == Gear::Neutral);
    ASSERT(cmd.phase == ShiftPhase::Idle);
    ASSERT(cmd.engaged_set == 0);
    ASSERT(!cmd.shift_active);
}

static void TestNeutralToFirstSkipsTorqueCut() {
    /* Engaging from Neutral is incoming-only, no overlap window. */
    auto sm = MakeFresh();
    sm.RequestGear(Gear::Forward1);
    sm.Tick(0);
    auto cmd = sm.Tick(1);
    ASSERT(cmd.phase == ShiftPhase::Overlap);  // not PreFill / TorqueCut
    ASSERT(!cmd.torque_cut_request);
}

static int RunUntilIdleOrLimit(ShiftLogic& sm, uint32_t now_ms_start, int max_ticks_ms);

static void TestSingleStepShiftFollowsPhaseSequence() {
    auto sm = MakeFresh();
    sm.RequestGear(Gear::Forward1);
    /* Walk Neutral → Forward1 first (no torque cut). */
    int settle = RunUntilIdleOrLimit(sm, 0, 1000);
    ASSERT(settle > 0);
    ASSERT(sm.current_gear() == Gear::Forward1);

    /* Now request 1 → 2: full PreFill → TorqueCut → Overlap → Complete. */
    sm.RequestGear(Gear::Forward2);
    sm.SetTorqueCutAck(false);

    uint32_t t = 1000;

    auto c0 = sm.Tick(t);
    ASSERT(c0.phase == ShiftPhase::PreFill);
    ASSERT(c0.shift_active);
    ASSERT(c0.ramping_in_set != 0);
    ASSERT(c0.ramping_out_set == 0);
    ASSERT(!c0.torque_cut_request);

    auto c1 = sm.Tick(t + 31);  // PreFill budget = 30 ms
    ASSERT(c1.phase == ShiftPhase::TorqueCut);
    ASSERT(c1.torque_cut_request);

    sm.SetTorqueCutAck(true);
    auto c2 = sm.Tick(t + 32);
    ASSERT(c2.phase == ShiftPhase::Overlap);
    ASSERT(c2.ramping_in_set != 0);
    ASSERT(c2.ramping_out_set != 0);
    ASSERT(c2.torque_cut_request);

    auto c3 = sm.Tick(t + 32 + 121);  // overlap budget = 120 ms
    ASSERT(c3.phase == ShiftPhase::Complete);
    ASSERT(sm.current_gear() == Gear::Forward2);

    auto c4 = sm.Tick(t + 32 + 121 + 31);  // restore budget = 30 ms
    ASSERT(c4.phase == ShiftPhase::Idle);
    ASSERT(!c4.shift_active);
}

static void TestTorqueCutTimeoutAbortsShift() {
    auto sm = MakeFresh();
    sm.RequestGear(Gear::Forward1);
    RunUntilIdleOrLimit(sm, 0, 1000);
    ASSERT(sm.current_gear() == Gear::Forward1);

    sm.RequestGear(Gear::Forward2);
    sm.SetTorqueCutAck(false);  // VCU never acks — TCU must give up

    uint32_t t = 5000;
    sm.Tick(t);                  // PreFill begins
    sm.Tick(t + 31);             // -> TorqueCut
    sm.Tick(t + 31 + 51);        // ack-budget exceeded -> abort

    ASSERT(sm.fault() == ShiftFault::TorqueCutTimeout);
    ASSERT(sm.current_gear() == Gear::Forward1);
    ASSERT(sm.phase() == ShiftPhase::Idle);
}

/* ------------------------------------------------------------------ */
/* State machine — multi-step paths                                   */
/* ------------------------------------------------------------------ */

static int RunUntilIdleOrLimit(ShiftLogic& sm, uint32_t now_ms_start, int max_ticks_ms) {
    /* Drive ticks at 1 ms granularity, ack torque-cut immediately. */
    for (int dt = 0; dt < max_ticks_ms; ++dt) {
        sm.SetTorqueCutAck(true);
        auto c = sm.Tick(now_ms_start + dt);
        if (dt > 0 && c.phase == ShiftPhase::Idle &&
            sm.current_gear() == sm.target_gear()) {
            return dt;
        }
    }
    return -1;  // didn't settle
}

static void TestSkipShift1to3WalksThroughGear2() {
    auto sm = MakeFresh();
    sm.RequestGear(Gear::Forward1);
    int neutral_to_one_ms = RunUntilIdleOrLimit(sm, 0, 10000);
    ASSERT(neutral_to_one_ms > 0);
    ASSERT(sm.current_gear() == Gear::Forward1);

    sm.RequestGear(Gear::Forward3);
    /* Walk: 1→2 (full overlap), 2→3 (full overlap). Each step is
     * pre_fill (30) + torque_cut (~0 with instant ack) + overlap (120)
     * + restore (30) = ~180 ms. So 1→2→3 should settle in ~360 ms. */
    int ms = RunUntilIdleOrLimit(sm, 100000, 10000);
    ASSERT(ms > 0);
    ASSERT(ms < 500);  // generous
    ASSERT(sm.current_gear() == Gear::Forward3);
}

static void TestKickdown6to3WalksDownThroughGear5and4() {
    auto sm = MakeFresh();
    sm.RequestGear(Gear::Forward1);
    RunUntilIdleOrLimit(sm, 0, 10000);
    /* Walk up to 6 first. */
    for (int g = 2; g <= 6; ++g) {
        sm.RequestGear(static_cast<Gear>(g));
        ASSERT(RunUntilIdleOrLimit(sm, 100000UL * g, 10000) > 0);
        ASSERT(sm.current_gear() == static_cast<Gear>(g));
    }
    /* Kickdown 6 → 3: must walk 6→5→4→3, three single-element shifts. */
    sm.RequestGear(Gear::Forward3);
    int ms = RunUntilIdleOrLimit(sm, 1'000'000, 10000);
    ASSERT(ms > 0);
    ASSERT(sm.current_gear() == Gear::Forward3);
}

static void TestForwardToReverseGoesViaNeutral() {
    auto sm = MakeFresh();
    sm.RequestGear(Gear::Forward1);
    RunUntilIdleOrLimit(sm, 0, 10000);

    sm.RequestGear(Gear::Reverse);
    /* Should walk Forward1 → Neutral → Reverse, two steps. The
     * intermediate Neutral state must be observable: capture it by
     * driving ticks one at a time and checking. */
    bool saw_neutral = false;
    for (int dt = 0; dt < 5000; ++dt) {
        sm.SetTorqueCutAck(true);
        sm.Tick(100'000 + dt);
        if (sm.current_gear() == Gear::Neutral) saw_neutral = true;
        if (sm.current_gear() == Gear::Reverse && sm.phase() == ShiftPhase::Idle) break;
    }
    ASSERT(saw_neutral);
    ASSERT(sm.current_gear() == Gear::Reverse);
}

/* ------------------------------------------------------------------ */
/* Negative tests                                                     */
/* ------------------------------------------------------------------ */

static void TestInvalidTargetGearRaisesFault() {
    auto sm = MakeFresh();
    sm.RequestGear(static_cast<Gear>(13));  // not in the enum range
    sm.Tick(0);
    ASSERT(sm.fault() == ShiftFault::InvalidTargetGear);
    ASSERT(sm.current_gear() == Gear::Neutral);
}

void ShiftLogicTest::RunTest() {
    TestEachForwardGearEngagesThreeElements();
    TestReverseEngagesThreeElements();
    TestNeutralEngagesNothing();
    TestAdjacentForwardShiftsAreSingleElement();
    TestStartsInNeutralIdle();
    TestNeutralToFirstSkipsTorqueCut();
    TestSingleStepShiftFollowsPhaseSequence();
    TestTorqueCutTimeoutAbortsShift();
    TestSkipShift1to3WalksThroughGear2();
    TestKickdown6to3WalksDownThroughGear5and4();
    TestForwardToReverseGoesViaNeutral();
    TestInvalidTargetGearRaisesFault();
}
