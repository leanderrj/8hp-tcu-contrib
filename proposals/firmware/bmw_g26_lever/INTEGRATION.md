# iX4_Lever — Stm32-vcu integration patch

Three files to add to `Stm32-vcu/`, plus four small line additions.

## Files

```
include/iX4_Lever.h          (new)
src/iX4_Lever.cpp            (new)
test/test_iX4_Lever.cpp      (new)
test/test_fixtures.h         (new)
test/canhardware_stub.cpp    (new — links the host-side test binary
                              without dragging in libopencm3 deps)
```

## Patch 1 — `test/test_list.h`

```diff
 class ThrottleTest : public IUnitTest {
 public:
   virtual void RunTest();
 };

+class iX4LeverTest : public IUnitTest {
+public:
+  virtual void RunTest();
+};
+
 #ifdef EXPORT_TESTLIST
-IUnitTest *testList[] = {new ThrottleTest(), NULL};
+IUnitTest *testList[] = {new ThrottleTest(), new iX4LeverTest(), NULL};
 #endif
```

## Patch 2 — `test/Makefile`

```diff
-OBJS = test_main.o my_string.o params.o throttle.o test_throttle.o
+OBJS = test_main.o my_string.o params.o throttle.o test_throttle.o iX4_Lever.o test_iX4_Lever.o canhardware_stub.o
+
+%.o: %.cpp
+	$(CPP) $(CPPFLAGS) -o $@ -c $<
```

The added pattern rule is needed because the upstream Makefile only knows how to compile `../%.cpp` (sources in `src/`), but `test_iX4_Lever.cpp` and `canhardware_stub.cpp` live in `test/` itself.

`iX4_Lever.cpp` is picked up automatically via the existing `VPATH = ../src ../libopeninv/src`.

## Patch 3 — `src/stm32_vcu.cpp`

Wire the new lever into the `UpdateShifter()` switch like the other levers:

```diff
 #include "E65_Lever.h"
 #include "F30_Lever.h"
+#include "iX4_Lever.h"

 …

 static no_Lever NoGearLever;
 static F30_Lever F30GearLever;
 static E65_Lever E65GearLever;
+static iX4_Lever iX4GearLever;

 …

 case ShifterModes::BMWE65:
   selectedShifter = &E65GearLever;
   break;
+case ShifterModes::BMWiX4:
+  selectedShifter = &iX4GearLever;
+  break;
```

And add the corresponding entry to the `ShifterModes` enum and the parameter table.

## Run the tests

```
$ cd Stm32-vcu
$ make Test
$ ./test/test_vcu
Starting unit Tests
Test … passed.
…
```

## What this PR proves

- 100 % CRC validation on **553 frames** sampled from a 2022 i4 G26 across four real-world capture sessions.
- Same CRC8/0x1D algorithm as `F30_Lever`, just `xorout = 0x04` over bytes [1..7] instead of `xorout = 0x70` over bytes [1..4]. The empirical result is recorded in `proposals/dbc/CRC_NOTES.md` along with the brute-force search code so anyone can reproduce it.
- Static, instance-free CRC entry point (`iX4_Lever::ComputeCrc8`) lets future shifter implementations and any factory ZF 8HP capture work reuse the same routine without spinning up a class.

## Open ground-truth question

The 0x32 vs 0x35 mapping (Reverse vs Drive) is a hypothesis; the captures don't disambiguate. The iX4_Lever code carries an unambiguous comment marking these as "hypothesis." A one-line forum confirmation from Damien resolves it — and even if R/D are swapped, only two `case` labels in `iX4_Lever::DecodeCAN` need to flip; the CRC, counter, and frame-shape work stands.
