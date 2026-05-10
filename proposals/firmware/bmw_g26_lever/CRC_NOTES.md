# BMW G26 0x3F9 CRC8 — empirical determination

**TL;DR — the CRC scheme is identical to F-chassis F30_Lever (poly 0x1D), with `xorout = 0x04` over data bytes [1..7]. Verified across 553 frames, 100% match.**

## Inputs

553 frames of CAN ID `0x3F9` from a 2022 BMW i4 G26 Gran Coupe AWD, captured by Damien Maguire and posted on openinverter forum thread #7028 (Mar 21 2026). Four sessions: pure shifter rotation, rotation + iDrive buttons, iDrive buttons only, and a power-off event. All four are in `archive/captures/`.

## What was already known

`Stm32-vcu/src/F30_Lever.cpp` implements a CRC8 with `POLYNOMIAL 0x1D`, init = 0x00, no reflection, and per-frame final XOR. For the F30 status frame `0x3FD` it uses `xorout = 0x70` over bytes [1..4]. Damien's source comment cites `https://openinverter.org/wiki/BMW_F-Series_Gear_Lever`.

Whether the same scheme generalises to G26 was an open question.

## Search

Brute force over the parameter space:
- Polynomial: all 256 values
- Reflection of input bits: yes / no
- Reflection of output bits: yes / no
- Byte range: bytes [1..7], [1..6], [1..5], [1..4], [2..7], plus three variants that prefix or append the CAN ID bytes
- `init` and `xorout`: searched as a single combined `offset = init ^ xorout` (the CRC is linear in this XOR, so `(init, xorout)` pairs sharing the same XOR are indistinguishable from frame data alone — `init = 0` is the natural choice)

The first frame fixes a candidate offset; the remaining 552 frames are the test set.

## Result

```
range = bytes [1..7]    (the seven bytes after the CRC byte)
poly  = 0x1D            (same as F30_Lever)
init  = 0x00
xorout = 0x04           (per-ID; F30_Lever 0x3FD uses 0x70)
refin = false
refout = false
```

Validates **553 / 553** captured frames. The two other "matches" reported by the brute-forcer (with CAN-ID bytes prefixed) are spurious — adding constant prefix bytes just shifts the offset by a constant, so they collapse to the same algorithm with a different `init ^ xorout` constant. The minimal interpretation (no prefix, `init = 0`, `xorout = 0x04`) is the one to ship.

## Reproducing this

```bash
# From the repo root (assumes capture files are in archive/captures/)
python3 -m venv venv && source venv/bin/activate
pip install cantools  # not strictly needed for the CRC search itself
python3 proposals/firmware/bmw_g26_lever/find_crc.py
```

The brute-force script (`find_crc.py`) is the same one that produced the result above; run time on a 2024 MacBook is < 5 s. It will print the unique (poly, offset, range) tuple plus a sample of validated frames.

## Verifying the C implementation against captures

```bash
cd repo/Stm32-vcu
git submodule update --init --depth 1   # pulls libopeninv

# Stage the patch
cp ../../proposals/firmware/bmw_g26_lever/iX4_Lever.h     include/
cp ../../proposals/firmware/bmw_g26_lever/iX4_Lever.cpp   src/
cp ../../proposals/firmware/bmw_g26_lever/test_iX4_Lever.cpp \
   ../../proposals/firmware/bmw_g26_lever/test_fixtures.h \
   ../../proposals/firmware/bmw_g26_lever/canhardware_stub.cpp test/
# Apply the test_list.h + Makefile patches in INTEGRATION.md
make Test && ./test/test_vcu
```

Expected output ends with `All tests passed` after 33 assertions across 5 test methods.

## Counter byte (byte 1) observation

Across 553 frames:
- High nibble: always `0xF` (0 exceptions).
- Low nibble: cycles 0..14 (15 distinct values; 0xF in the low nibble was never observed).

The 0xF reservation is recorded in the `iX4_Lever::DecodeCAN` counter check, which rejects any frame whose byte-1 high nibble isn't 0xF. The "0xF low nibble unused" finding is held as a soft assumption: if such a frame ever shows up it's reported as a counter fault but doesn't desynchronise the chain.

## What's still open

- **R vs D mapping of byte-6 values 0x32 vs 0x35.** Captures don't disambiguate. A one-line forum confirmation from Damien resolves this and only requires flipping two `case` labels in `iX4_Lever::DecodeCAN`.
- **Byte 6 = 0x34 (Sport?)** — never observed; reserved.
- **Byte 2 = 0x80 → 0x00 transition** — happens once mid-capture in `shifter1rnd`. Likely an ignition-phase or wake state. Worth correlating against simultaneous frames on the bus, but not a CRC concern.
