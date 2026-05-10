# MAX22200 ↔ ZF G8P75HZ solenoid binding

Cross-reference of the solenoid count, type, and drive requirements pulled
from the TCM pinout (`PINOUT.md`) against the MAX22200 octal solenoid driver
that Damien chose for the redesign (forum thread #6047, post 7).

## The headline problem

> **9 solenoids. 8 channels. We need a plan.**

The ZF G8P75HZ has nine independent solenoids; the MAX22200 is an 8-channel
device. This is a real design constraint that the firmware architecture has
to address, not paper over.

| | Count | Source |
|---|---|---|
| Solenoids on the TCM | 9 | TCM pinout PDF (pins 5, 41–48) |
| Channels per MAX22200 | 8 | [MAX22200 datasheet (Analog Devices)](https://www.analog.com/en/products/max22200.html) |

## MAX22200 capabilities relevant to the 8HP

- **8× independent half-bridges**, 36 V supply, **1 A RMS per channel**, 200 mΩ on-resistance, push-pull (high-side or low-side or full-bridge by configuration).
- **Per-channel HIT/HOLD current profile** — energise the solenoid hard for `t_HIT` to overcome static friction, then drop to `I_HOLD` for steady state. This is exactly the behaviour every proportional clutch solenoid in an automatic transmission needs and is a major reason MAX22200 is a good fit.
- **Pairs of channels can be paralleled** to 2 A peak (one pair of solenoids needing more current) or configured as a full-bridge (one latched valve from two channels).
- **SPI control with daisy-chain support** — two MAX22200s sit on one chip-select with one shared SPI transaction.
- **Per-channel diagnostics:** open-load, short-to-supply, short-to-ground, over-temperature, under-voltage. Maps directly onto our `TCU_Status2.FaultBits` field.

## The four design options for "9 into 8"

### Option A — Two MAX22200 daisy-chained on SPI *(recommended)*

```
SPI master (STM32) ──CS──┬── MAX22200 #1  channels 0..7
                         │     A, B, C, D, E clutches (5)
                         │     TCC, Line Pressure (2)
                         │     spare (1)
                         └── MAX22200 #2  channels 0..3 used
                               Park Hold, Park Release (2)
                               spare (2)
```

**Pros:** clean firmware abstraction (every solenoid is a `MAX22200_Channel`); spare channels for ZF 9HP/heavy-duty variants and for future bench fuzzing of unidentified solenoids; SPI daisy-chain is a single transaction so software complexity is unchanged from one chip.

**Cons:** ~$3–5 extra BOM, ~6 × 6 mm of board area. Negligible at the project's scale.

**Recommended.** Headroom is cheap; wedging logic to fit 9 into 8 isn't.

### Option B — Single MAX22200 + discrete drivers for Park

The Park system (Pin 5 Hold, Pin 48 Release) is fundamentally different from the clutch solenoids:
- ON/OFF latching, not proportional — no PWM, no current regulation needed
- Mutually exclusive — Hold and Release are never simultaneously energised
- Safety-critical — must default to "engaged" on power loss

A pair of low-side MOSFETs with a flyback diode each (or a small two-channel low-side driver like MAX14913) handles Park entirely; the eight MAX22200 channels then map cleanly to the seven proportional solenoids plus one spare.

**Pros:** Single MAX22200, slightly simpler PCB.

**Cons:** Two solenoid drive topologies in firmware (proportional and on/off). Mostly aesthetic — Park is a different subsystem in the state machine anyway.

### Option C — Channel sharing with external mux

Logically OR Park Hold and Park Release through one MAX22200 channel with external steering. **Don't.** Crosses a safety boundary (loss of mux switch loses both Park-lock states), saves nothing meaningful versus Option B.

### Option D — Time-multiplexed exclusive solenoids

Pair up solenoids that are mutually exclusive (e.g. TCC + Park Hold — TCC engages only in Drive at speed; Park Hold engages only in Park) and route them to one channel via a steering FET. **Don't.** Same safety-coupling argument as Option C, plus you re-introduce the problem when the firmware needs to drive both during a fault recovery sequence.

## Recommended channel assignment (Option A)

### MAX22200 #1 — clutch / pressure / TCC (proportional)

| Channel | TCM Pin | Solenoid | HIT current | HOLD current | Notes |
|---|---|---|---|---|---|
| 0 | 41 | A Clutch        | TBD bench | TBD bench | proportional, ~2 A peak typ |
| 1 | 42 | D Clutch        | TBD       | TBD       | |
| 2 | 43 | B Clutch        | TBD       | TBD       | |
| 3 | 44 | E Clutch        | TBD       | TBD       | |
| 4 | 45 | C Clutch        | TBD       | TBD       | |
| 5 | 46 | TCC             | TBD       | TBD       | full lock-up requires sustained ~1 A |
| 6 | 47 | Line Pressure   | TBD       | TBD       | always energised in Drive; high duty cycle |
| 7 | — | spare           | —         | —         | reserve for 9HP / fuzzing |

The HIT/HOLD currents are deliberately TBD here: published ZF figures vary by 'box revision and rebuild kit, and the safest source is the OEM Mechatronik's own behaviour captured on a current probe. Damien's bench setup is the natural place to measure them.

### MAX22200 #2 — Park (latching) + spare

| Channel | TCM Pin | Solenoid | Drive style | Notes |
|---|---|---|---|---|
| 0 | 5  | Park Hold    | latched ON | de-energise once park engaged (sense via pin 13/14) |
| 1 | 48 | Park Release | pulsed     | energise briefly to release pawl, then off |
| 2 | — | spare | — | |
| 3 | — | spare | — | |
| 4..7 | — | unused | — | could daisy off if not loaded |

Park is *technically* on/off, but using MAX22200 channels for it gives us the same diagnostic story (open-load, short, over-current) we get on the clutches — worth the channel cost.

## Caveats

- **MAX22200's 1 A RMS per channel** is enough for typical 8HP solenoids (which run in the 0.5–1.5 A range proportional, with occasional 2 A HIT peaks). For solenoids that need >1 A continuous (Line Pressure under hard launch?), the **paralleled-channel mode** doubles current — at the cost of one channel slot. A confident decision needs the bench-measured HIT/HOLD currents.
- The Park system **must default safe** on MCU reset. MAX22200 outputs are high-Z on reset, which is what we want for Park Release (don't release on reset). Park Hold is harder — the OEM design probably uses a normally-engaged mechanical detent so the solenoid only needs energising when transitioning *out* of Park. Confirm on the bench.

## Wiring map for layout

```
+12V (TCM pins 37–40, all paralleled)
         │
         ▼
   ┌─────────┐
   │MAX22200 │── ch0 ──▶ TCM pin 41 (A Clutch)
   │   #1    │── ch1 ──▶ TCM pin 42 (D Clutch)
   │         │── ch2 ──▶ TCM pin 43 (B Clutch)
   │         │── ch3 ──▶ TCM pin 44 (E Clutch)
   │         │── ch4 ──▶ TCM pin 45 (C Clutch)
   │         │── ch5 ──▶ TCM pin 46 (TCC)
   │         │── ch6 ──▶ TCM pin 47 (Line Pressure)
   │         │── ch7    spare
   └─────────┘
         │ SPI daisy-chain (DOUT → DIN)
         ▼
   ┌─────────┐
   │MAX22200 │── ch0 ──▶ TCM pin 5  (Park Hold)
   │   #2    │── ch1 ──▶ TCM pin 48 (Park Release)
   │         │── ch2..7 spare
   └─────────┘
              GND ◀── TCM pins 24, 25 (T31)
```

## Firmware implications

In the TCU firmware (`Solenoids.cpp`, when written), this structure suggests:

```cpp
enum SolenoidId {
    SOL_A = 0, SOL_B, SOL_C, SOL_D, SOL_E,
    SOL_TCC, SOL_LINE_PRESSURE,
    SOL_PARK_HOLD, SOL_PARK_RELEASE,
    SOL_COUNT  // == 9
};

struct SolenoidBinding {
    uint8_t  chip;       // 0 or 1
    uint8_t  channel;    // 0..7 within the chip
    bool     proportional;
    uint16_t hit_ma;     // peak current target
    uint16_t hold_ma;
    uint16_t hit_us;     // hit duration
};

constexpr SolenoidBinding solenoidBinding[SOL_COUNT] = {
    /* SOL_A           */ { 0, 0, true,  /*hit*/ 0, /*hold*/ 0, /*hit_us*/ 0 },
    /* SOL_D           */ { 0, 1, true,  0, 0, 0 },
    /* SOL_B           */ { 0, 2, true,  0, 0, 0 },
    /* SOL_E           */ { 0, 3, true,  0, 0, 0 },
    /* SOL_C           */ { 0, 4, true,  0, 0, 0 },
    /* SOL_TCC         */ { 0, 5, true,  0, 0, 0 },
    /* SOL_LINE_P      */ { 0, 6, true,  0, 0, 0 },
    /* SOL_PARK_HOLD   */ { 1, 0, false, 0, 0, 0 },
    /* SOL_PARK_RELEASE*/ { 1, 1, false, 0, 0, 0 },
};
```

The HIT/HOLD/HIT-time fields stay zero until they're measured on the bench, then this single table becomes the entire calibration story for the gearbox. That's the right place for it — out of code, easy to override per-vehicle in the openinverter web parameter system.

## Open items

1. **Bench-measure HIT/HOLD currents** for each clutch by clamping the OEM Mechatronik's outputs and current-probing while shifting through gears. Damien's bench setup can produce this directly. Without it, the table above is shape-only.
2. **Confirm Park Hold default-safe behaviour** — is the mechanical detent latching such that de-energised = engaged, or does it need continuous current to hold?
3. **Confirm Line Pressure peak current** under hard-launch / cold conditions. If it spikes >1 A RMS, that channel needs the paralleled-channel mode (steals one spare).
4. **Validate the unassigned pins** (1, 3, 4, 8, 9, 10, 11, 18, 49) on the bench before PCB layout — could be a 5 V rail, sensor returns, or a cluster-display feedback line.
