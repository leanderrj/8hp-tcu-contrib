# BMW iX4 G26 (2022) — CAN/LIN Capture Analysis

Source: openinverter forum thread #7028, Damien Maguire's Mar 21 2026 captures.
Vehicle: 2022 BMW i4 G26 Gran Coupe AWD, **CAN @ 500 kbps, LIN @ 19200 baud**.

Files (all in `archive/captures/`):
- `ix4_shifter1rnd.csv` — full rotation P→D→...→P (208k frames, ~152 s)
- `ix4_shifter2rndbuttons.csv` — second rotation with iDrive buttons
- `ix4_shifteridrivebuttons.csv` — iDrive buttons only (gear stayed in P)
- `ix4_shiftpoweroff.csv` — short poweroff event (gear in P)
- `bmw_ix4_ac_lin1.txt` — A/C compressor LIN bus capture (23 slave IDs)

---

## CAN ID 0x3F9 — gear-selector status frame **(primary finding)**

8-byte frame, ~5 Hz idle + event bursts when shifter is moved. Constant `0x33` in byte 6 across the iDrive-buttons and power-off captures (gear in P), cycles through four values only when the shifter is rotated.

| Byte | Role | Notes |
|---|---|---|
| 0 | CRC | every frame unique; almost certainly BMW CRC8 poly 0x1D — same scheme `F30_Lever.cpp` already uses |
| 1 | Counter | low-nibble rolling 0xF0…0xFF (so the high nibble is reserved/F) |
| 2 | Status flag | flips `0x80 → 0x00` mid-capture; likely ignition / vehicle-stationary phase |
| 3 | Constant `0x73` | message-id / version padding |
| 4 | Lever encoder | analog 0x3B–0x46, rests near 0x3F, peaks ±~7 when held |
| 5 | Constant `0x30` | padding |
| **6** | **Latched gear** | **0x33 = P (confirmed)**, **0x31 / 0x32 / 0x35 = R / N / D** (assignment hypothesis below), 0x34 unobserved (probably S) |
| 7 | Constant `0x00` | padding |

### Gear-byte mapping (hypothesis — needs ground-truth confirmation)

| byte 6 | mapped | confidence | reasoning |
|---|---|---|---|
| `0x33` | **P** | high | sole value when car is parked & in iDrive-buttons / power-off captures |
| `0x31` | N | medium | appears as transient between every gear change — center / rest position of the rotary selector |
| `0x32` | R | medium | reached via short lever throws, paired with `0x35` |
| `0x35` | D | medium | reached via lever throws in the opposite direction |
| `0x34` | S? | low | never observed; gap in sequence is suspicious; G-chassis selectors have a separate "S" notch |

Damien shifted P→[gear-cycling]→P; the observed transitions:
```
P → 0x35 → 0x31 → 0x32 → 0x31 → 0x35 → 0x31 → 0x32 → 0x31 → P
```
Confirming whether `0x32` is R or D needs a one-line comment from Damien.

### Skeleton openinverter integration

This drops cleanly into the existing `Shifter` family in `Stm32-vcu/include/`:

```cpp
// iX4_Lever.h  (G-chassis BMW iDrive rotary selector)
class iX4_Lever : public Shifter {
public:
    void DecodeCAN(int id, uint32_t* data) override;
    bool GetGear(Sgear& outGear) override;
private:
    Sgear gear = PARK;
};

// iX4_Lever.cpp
void iX4_Lever::DecodeCAN(int id, uint32_t* data) {
    if (id != 0x3F9) return;
    const uint8_t* d = (const uint8_t*)data;
    // TODO: validate d[0] CRC8 (poly 0x1D, same as F30_Lever)
    // TODO: validate d[1] low-nibble counter monotonic
    switch (d[6]) {
        case 0x33: gear = PARK;    break;
        case 0x32: gear = REVERSE; break;  // hypothesis
        case 0x31: gear = NEUTRAL; break;
        case 0x35: gear = DRIVE;   break;  // hypothesis
        default:   /* hold last */ break;
    }
}
```

The CRC8 routine and `Sgear` enum already exist in `F30_Lever.{h,cpp}`. This is a one-day contribution, modulo the R/D ground-truth check.

---

## CAN ID 0x36E — iDrive controller event frame *(secondary finding)*

5-byte frame. In the iDrive-buttons capture: 224 frames, byte 2 mostly idle at `0xFE` with brief excursions to `{0x50, 0x3A, 0xBD}` (7 frames each), byte 3 mostly `0xFF` with brief `{0x00, 0x01, 0x03}`. Each excursion is 7 frames ≈ one button press.

Not gear-related — useful for general iDrive integration in `Stm32-vcu` (volume, mode, scroll). Out of scope for the 8HP TCU itself.

---

## A/C compressor LIN catalog (`bmw_ix4_ac_lin1.txt`)

19200 baud LIN 2.x, 23 distinct slave IDs over 2359 responses. Master commands on **`0x30`** — same canonical master-ID as the gearbox aux pump (different physical bus, same BMW convention). Worth noting: this **validates `notes/lin_pump_protocol.md`** — `0x30` is BMW's standard master ID across LIN domains.

Most frequent slave IDs:

| ID | count | sample first bytes | likely role |
|---|---|---|---|
| `0x25` | 169 | `cb d1 92 49 ff 33 03 7c` | sensor/status pack |
| `0x26` | 168 | `cb ff` | short status |
| `0x30` | 168 | `cf 14 00 00 00 51 04 44` | A/C compressor command/echo |
| `0x11` | 168 | `4f 00 c8 56` | sensor |
| `0x12` | 168 | `00 c8 f0 ff` | sensor |
| `0x1C` | 168 | `00 3a 41 f0 ff ff ff ff` | sensor |
| `0x32` | 127 | `04 00 74 00 00 ff ff ff` | A/C compressor primary status — **note: same ID as gearbox pump status, different bus and different protocol** |

Useful as a second LIN protocol example when validating any LIN driver code we write for the 8HP TCU.

---

## What this unlocks for the 8HP / VCU contribution work

1. **`iX4_Lever.cpp`** — small concrete PR to `Stm32-vcu` adding a G-chassis shifter. Plays nicely with all the existing 8HP TCU work because the 8HP TCU's `VCU_GearRequest` frame (DBC ID 0x520) takes its `TargetGear` value from whichever `Shifter` is selected. Modern BMW donor cars suddenly become viable VCU targets.
2. **CRC8 verification fixture** — these captures are good test data for whatever CRC8 routine we implement. We can replay 0x3F9 frames in unit tests and assert the CRC matches.
3. **Counter rollover behavior** — 0x3F9 byte 1 cycles 0xF0–0xFF, not 0x00–0xFF. Implementer trap worth catching in tests (i.e., the counter is in the *low* nibble with an `0xF` upper nibble fixed — a naive "is this counter the previous + 1?" check needs to mask properly).
4. **A/C compressor RE** — independent contribution surface (EdAtki on the forum is starting work on the iX4 A/C compressor for HV use, May 2026).

## Open items

- Ground-truth R vs D in 0x3F9 byte 6 — ask Damien on the forum thread or look at his Arduino bench code if he posts one.
- 0x3F9 byte 0 is *probably* CRC8 with poly 0x1D, but verify by running the existing `F30_Lever::get_crc8` on each frame and checking match rate.
- 0x3F9 byte 2 status flag — what triggered the `0x80 → 0x00` transition mid-capture? Worth correlating against a known event (ignition phase, motor wake) by looking at other simultaneous frames.
- 0x36E precise mapping — three button-press values (`0x50/0x3A/0xBD` in byte 2 paired with `0x01/0x00/0x03` in byte 3) likely correspond to specific iDrive buttons. Need a labeled capture to map them.
