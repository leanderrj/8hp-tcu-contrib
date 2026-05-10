# shift_logic — integration

ZF 8HP shift state machine + clutch engagement table. Pure C++17, no
hardware dependencies, host-testable.

## Files

```
include/clutch_table.h       (new)  cited engagement table + invariants
include/shift_logic.h        (new)
src/shift_logic.cpp          (new)
test/test_shift_logic.cpp    (new)  12 host assertions
```

## Invariants enforced at compile time

`clutch_table.h` carries three `static_assert`s that fail the build if
the engagement table is edited into an inconsistent state:

- Every adjacent forward-gear pair (1↔2 .. 7↔8) differs by exactly one
  shift element. This is the defining ZF 8HP design property.
- Every forward gear engages exactly three of the five elements.
- Reverse engages exactly three; Neutral engages zero.

A bench-confirmed table that violates any of these is not a valid 8HP
table — the static_assert will catch the typo at build time.

## Patches

### `test/test_list.h`

```diff
+class ShiftLogicTest : public IUnitTest {
+public:
+  virtual void RunTest();
+};
+
 #ifdef EXPORT_TESTLIST
-IUnitTest *testList[] = {new ThrottleTest(), new iX4LeverTest(), new Can_ZF8HPTest(), NULL};
+IUnitTest *testList[] = {new ThrottleTest(), new iX4LeverTest(),
+                          new Can_ZF8HPTest(), new ShiftLogicTest(), NULL};
 #endif
```

### `test/Makefile`

```diff
-OBJS = ... test_Can_ZF8HP.o
+OBJS = ... test_Can_ZF8HP.o shift_logic.o test_shift_logic.o
```

(`shift_logic.cpp` is in `src/` so the existing `VPATH` rule picks it up.)

## Validated against `make Test`

Built and ran the full test suite against unmodified
`damienmaguire/Stm32-vcu` master with the patches above. All 12
assertions in `test_shift_logic.cpp` pass:

```
TestEachForwardGearEngagesThreeElements
TestReverseEngagesThreeElements
TestNeutralEngagesNothing
TestAdjacentForwardShiftsAreSingleElement
TestStartsInNeutralIdle
TestNeutralToFirstSkipsTorqueCut
TestSingleStepShiftFollowsPhaseSequence
TestTorqueCutTimeoutAbortsShift
TestSkipShift1to3WalksThroughGear2
TestKickdown6to3WalksDownThroughGear5and4
TestForwardToReverseGoesViaNeutral
TestInvalidTargetGearRaisesFault
```

## Outputs the bind layer must consume

`ShiftLogic::Tick(now_ms)` returns a `ShiftCommand` with fields the
firmware uses to drive the MAX22200 and the CAN protocol:

| Field | Maps to |
|---|---|
| `current_gear`, `target_gear` | DBC `TCU_Status1.CurrentGear` / `TargetGearEcho` |
| `phase` | DBC `TCU_Status1.TcuState` |
| `engaged_set`, `ramping_in_set`, `ramping_out_set` | per-channel MAX22200 HIT/HOLD targets |
| `ramp_progress` | bind layer chooses pressure ramp shape |
| `torque_cut_request` | DBC `TCU_Status1` new bit (or status2 bit — see torque_handshake/ when built) |
| `shift_active` | DBC `TCU_Status1.ShiftInProgress` |
| `fault` | DBC `TCU_Status2.FaultBits` mapping |

## What this is NOT

- **Not a complete TCU.** This is the orchestration brain — gear
  selection and overlap-window timing. The bind layer (Solenoids.cpp,
  CanLink.cpp) is separate work.
- **Not calibrated.** `ShiftCalibration` defaults are conservative
  starting points based on Greiner & Grumbach 2009's published 200 ms
  total shift time. Actual numbers come from the bench: HIT/HOLD
  currents per solenoid, real overlap timing per gear, oil-temp
  compensation curves.
- **Not adaptation-aware.** A shipping TCU learns clutch fill volumes
  and shift-quality offsets over time. That belongs above this layer
  and is not in scope here.
