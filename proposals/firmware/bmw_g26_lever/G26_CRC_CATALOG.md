# BMW G-chassis CRC catalog (2022 i4 G26)

Empirically determined CRC8 parameters for every CAN frame in the
[archive/captures/](../../../archive/captures/) iX4 captures that uses the
BMW E2E protection pattern (byte 0 = CRC, byte 1 low nibble = counter,
byte 1 high nibble fixed).

**24 frames validated 100% across the captures — every one uses CRC8 with
polynomial `0x1D`, init `0x00`, no reflection, byte 0 holds the CRC, data
range starts at byte 1, per-ID xorout.**

| CAN ID | DLC | xorout | range | frames | confidence |
|---|---|---|---|---|---|
| `0x032` | 8 | `0x55` | `[1..7]` |    269 | 100% |
| `0x064` | 8 | `0x7C` | `[1..7]` |    269 | 100% |
| `0x065` | 8 | `0xE8` | `[1..7]` |  2 805 | 100% |
| `0x0A5` | 8 | `0x6A` | `[1..7]` | 13 289 | 100% |
| `0x0A7` | 7 | `0x23` | `[1..6]` | 11 082 | 100% |
| `0x0AB` | 8 | `0x61` | `[1..7]` |  1 112 | 100% |
| `0x163` | 8 | `0xCE` | `[1..7]` |  2 658 | 100% |
| `0x173` | 8 | `0x5E` | `[1..7]` |  5 354 | 100% |
| `0x199` | 6 | `0x5F` | `[1..5]` | 13 280 | 100% |
| `0x19A` | 6 | `0xE5` | `[1..5]` | 13 280 | 100% |
| `0x19F` | 6 | `0x01` | `[1..5]` | 13 281 | 100% |
| `0x1A1` | 5 | `0x0F` | `[1..4]` | 13 279 | 100% |
| `0x1C0` | 8 | `0xBE` | `[1..7]` |  6 930 | 100% |
| `0x1E1` | 6 | `0xC7` | `[1..5]` |  1 396 | 100% |
| `0x1E4` | 8 | `0x07` | `[1..7]` |  5 547 | 100% |
| `0x2BB` | 5 | `0x78` | `[1..4]` |  2 656 | 100% |
| `0x2EB` | 8 | `0xF4` | `[1..7]` |  5 564 | 100% |
| `0x301` | 7 | `0x27` | `[1..6]` |  1 328 | 100% |
| `0x302` | 7 | `0x3A` | `[1..6]` |  6 640 | 100% |
| `0x36E` | 5 | `0x7E` | `[1..4]` |  1 659 | 100% — iDrive event frame |
| `0x36F` | 5 | `0xB1` | `[1..4]` |  1 661 | 100% — paired with 0x36E |
| `0x378` | 8 | `0x90` | `[1..7]` |    472 | 100% |
| **`0x3F9`** | **8** | **`0x04`** | **`[1..7]`** | **553** | **100% — gear lever (used by `iX4_Lever`)** |
| **`0x3FD`** | **5** | **`0x70`** | **`[1..4]`** | **2 672** | **100% — gear status (matches `F30_Lever::sendcan`)** |

## Key observations

- **Universal poly: `0x1D`.** Every CRC-protected frame on the bus uses the
  same CRC8 polynomial. F-chassis F30 used `0x1D`; G-chassis G26 still uses
  `0x1D`. Per-ID variation is via the final XOR byte.
- **Range is always `[1..N-1]`** — every byte after the CRC byte itself,
  but never the CAN ID and never the CRC byte. Same convention across all 24.
- **`0x3FD` is unchanged** between F-chassis and G-chassis. The xorout
  `0x70` over bytes [1..4] is exactly what `F30_Lever::sendcan` does today.
  An OI VCU running the F30_Lever `sendcan` will produce frames a G26
  receiver accepts.
- **`0x3F9` is new on G-chassis** — it doesn't appear in the F30 codebase,
  so it's a G-chassis-only frame. That's why a new shifter implementation
  is needed (covered in [`iX4_Lever`](INTEGRATION.md)).
- **iDrive controller frames `0x36E` / `0x36F`** are paired (similar frame
  counts, both 5-byte, both CRC-protected). Decoding these would let an OI
  VCU drive infotainment functions on a G-chassis donor (volume, mode
  buttons, scroll). Out of scope for the 8HP TCU itself but a free side
  effect of the analysis.

## Frames where CRC search came up empty

```
0x083, 0x0D9, 0x254, 0x265, 0x328, 0x32B, 0x393, 0x402, 0x40F
```

These pass the surface heuristic (high-variability byte 0 + small byte-1
set) but no `(poly, xorout, range)` validates 100% under the BMW pattern
we tried. Three explanations are likely:

1. **No CRC** — byte 0 is a sequence number, multiplexer index, or the low
   byte of a 16-bit counter. Common for high-frequency vehicle-dynamics
   frames.
2. **Different range** — some frames may protect non-contiguous bytes
   (e.g. CAN-ID prefix included; or skip a "type" byte).
3. **AUTOSAR E2E Profile 2/4/etc.** — uses a longer counter and different
   CRC inputs. Not searched here.

Worth a deeper look if anyone needs to spoof or filter these frames; not
worth blocking the TCU work on.

## Reproducing this catalog

```bash
python3 proposals/firmware/bmw_g26_lever/find_crc_batch.py
```

Runs the same brute-force search across every CAN ID in
`archive/captures/` that matches the BMW E2E surface pattern. Prints the
table above; ~10 s on a 2024 MacBook.

## Why this is useful

Anyone building openinverter (or other) integrations against a G-chassis
BMW now has the CRC parameters for two dozen frames as a starting table,
without having to capture and brute-force their own. F-chassis code that
already uses `F30_Lever::get_crc8` works directly on G26 by passing the
right `final` byte and length; no new CRC routine, no AUTOSAR E2E library
required.

The catalog also empirically refutes the question of whether BMW changed
their CRC scheme at the F → G transition: they didn't. The polynomial,
init value, byte ordering, and per-ID-xorout convention are stable.
