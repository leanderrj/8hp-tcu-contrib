## Summary

Adds a `Shifter` implementation for the BMW G-chassis (G26 i4) iDrive
rotary gear selector — a sibling to the existing `F30_Lever` /
`E65_Lever` / `no_Lever` family. Two commits, ~350 lines added, no
existing files removed, only additive edits to `param_prj.h`,
`stm32_vcu.cpp`, and the test scaffolding.

## What's in it

**Production code:**
- `include/iX4_Lever.h` — class declaration following the existing
  shifter pattern.
- `src/iX4_Lever.cpp` — decode logic. Reuses the F30 CRC8 algorithm
  (poly `0x1D`) with G26-specific parameters: `xorout = 0x04` over
  bytes `[1..7]`. CAN ID `0x3F9`, ~5 Hz idle plus event bursts. The
  byte-6 gear field maps to `Sgear` per the comments.
- `BMWiX4 = 5` added to `ShifterModes` in `param_prj.h`; one new case
  in the `UpdateShifter()` switch in `stm32_vcu.cpp`.

**Tests:**
- `test/test_iX4_Lever.cpp` + `test/test_fixtures.h` — drops into the
  existing `IUnitTest` pattern. 33 host assertions covering CRC
  validation across 12 captured frames, mutated-CRC rejection, gear
  mapping for each observed byte-6 value, bad-CRC-doesn't-change-gear,
  bad-counter rejection.
- `test/canhardware_stub.cpp` — provides a single `RegisterUserMessage`
  symbol the linker needs but the host test binary should not pull
  the libopencm3-flavoured implementation for. `SetCanInterface` isn't
  called from the unit tests themselves.
- `test/Makefile` adds the new objects to `OBJS` plus a pattern rule
  so test-local `.cpp` files compile.

Run with `make Test && ./test/test_vcu` — all assertions pass on
upstream master.

## Where the data came from

Source: the captures Damien posted to openinverter forum thread
[#7028](https://openinverter.org/forum/viewtopic.php?t=7028)
(2022 BMW i4 G26 Gran Coupe AWD, 500 kbit/s CAN, 19 200 baud LIN —
attachments `ix4_shifter1rnd.csv`, `ix4_shifter2rndbuttons.csv`,
`ix4_shifteridrivebuttons.csv`, `ix4_shiftpoweroff.csv`).

553 frames of `0x3F9` total across the four sessions. The CRC
parameters were brute-forced against the full corpus (~5 s on a
laptop): `poly=0x1D, init=0x00, xorout=0x04, bytes [1..7]`, no
reflection — unique fit. The same scheme that `F30_Lever::sendcan`
already emits at `0x3FD` is unchanged on G26 (verified incidentally;
also in the corpus). So `F30_Lever::get_crc8` is reused as-is — only
the `final` and `nBytes` arguments differ.

## Byte-6 gear mapping

| Value | Mapped to | Confidence |
|---|---|---|
| `0x33` | `PARK` | confirmed — sole value in the poweroff and idrive-buttons capture sessions |
| `0x31` | `NEUTRAL` | high — appears as transient between every rotation |
| `0x32` | `REVERSE` | hypothesis |
| `0x35` | `DRIVE` | hypothesis |
| `0x34` | unobserved | held at last good gear; likely Sport |

### One open question

The R-vs-D assignment for `0x32` / `0x35` is a hypothesis — both
directions of lever movement involve the encoder rising above rest, so
the captures alone don't disambiguate them. If anyone has a labelled
clip showing which gear was selected at a given timestamp, the two
case labels in `iX4_Lever::DecodeCAN` flip to resolve it. Marked in
the source comment so it's easy to spot.

## What this enables

Adds support for 2022+ G-chassis BMW donor vehicles to the entire
ZombieVerter VCU ecosystem — useful for any conversion that picks an
i4 / iX / G-series shifter as the gear-selector input, not just 8HP
TCU work.

## Verified against

Cloned `damienmaguire/Stm32-vcu` master as of the date of this PR,
applied these changes, ran `make Test`. All 33 new assertions pass
plus the existing throttle suite. No production code path is
modified — `selectedShifter` only changes when `Param::GearLvr` is
set to the new `BMWiX4` value.

## License

Same GPLv3 as the rest of the project; new files carry the
ZombieVerter license header.

## Wider context

The full reverse-engineering write-up (CRC search reproducibility,
G-chassis CRC catalog of 24 BMW frames, capture corpus index, Python
reference implementation that mirrors this C++ class) lives at
[`leanderrj/8hp-tcu-contrib`](https://github.com/leanderrj/8hp-tcu-contrib),
in case anyone hits a related G-chassis CAN question. Not required
to review this PR.
