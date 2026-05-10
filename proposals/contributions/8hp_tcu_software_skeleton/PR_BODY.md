## Summary

Two complementary additions, scoped to be additive only — nothing in
your existing `Hardware/` or `README.md` is modified.

1. **`Hardware/OEM_Connector_Model/`** — CSV-driven KiCad symbol library
   for the 49-pin TCM internal connector and the 16-pin OEM external
   connector, derived from the `TCM_Pinout.pdf` you posted to forum
   thread #6047.
2. **`Software/`** — three pure-C++17 firmware modules
   (`shift_logic`, `park_lock`, `solenoid_driver`) plus a host-runnable
   test harness using the same `IUnitTest` pattern as `Stm32-vcu/test/`.
   Replaces the placeholder `Software/test.a`.

Two commits, ~3 000 lines added, no peripheral / `libopencm3` /
`libopeninv` dependencies anywhere — everything is host-buildable
with stock `g++ -std=c++17`.

## Where it came from

I spent some weeks digging into the 8HP for an unrelated EV-conversion
project of mine and ended up with a pile of capture analysis and
firmware-skeleton code that's tangentially useful here. Repo with the
full context (553-frame BMW i4 G26 capture corpus, BMW G-chassis CRC
catalog, Python plant model, formal HARA, etc.) lives at
[leanderrj/8hp-tcu-contrib](https://github.com/leanderrj/8hp-tcu-contrib).
This PR is just the bits that fit cleanly into your repo's structure;
the rest stays in the contrib repo as reference.

## Hardware/ — `OEM_Connector_Model/`

The structured / machine-readable companion to your `TCM_Pinout.pdf`:

```
Hardware/OEM_Connector_Model/
├── tcm_pinout.csv         single source of truth, 49 pins
├── external_pinout.csv    16-pin external connector + TCM-pin map
├── gen_kicad_sym.py       deterministic generator
├── oem_tcm.kicad_sym      KiCad 7+ symbol library (importable)
└── README.md
```

Anyone designing a replacement-board schematic can drop the connector
in as `J1`. The generator produces byte-identical output every run; a
sibling test suite in the contrib repo asserts the `.kicad_sym`
matches the CSV.

This is purely additive — nothing in `Hardware/` is touched.

## Software/ — firmware skeleton

Three modules. Each is **state-machine logic only**: produces *intent*
outputs, doesn't touch peripherals. Binding those intents to real
SPI/CAN is downstream work that depends on integration choices I'm
deliberately not making for you.

### `shift_logic/`

Sequential shift orchestration with the single-element-per-shift rule
that defines the 8HP design (Greiner & Grumbach, SAE 2009-01-1083).
Five-phase choreography: `Idle → PreFill → TorqueCut → Overlap →
Complete`. The clutch engagement table is guarded by three compile-time
`static_assert`s so a typo in the table doesn't compile.

12 host assertions covering single-step shifts, multi-gear paths
(skip-shift / kickdown / forward-to-reverse-via-Neutral), torque-cut
timeout, invalid-target rejection.

### `park_lock/`

Safety-critical pawl state machine. Drives Park Hold (TCM pin 5) and
Park Release (TCM pin 48); reads Park Pos 1/2 sense from TCM pins
13/14. Hold and Release are **never** simultaneously commanded —
property-tested across 5 000 simulated ticks of mixed scenarios.
Engage / disengage gated on vehicle speed; sensor wiring faults
flagged; default-safe (solenoids high-Z) on reset.

10 host assertions.

### `solenoid_driver/`

MAX22200 register layout (cited line-by-line against the datasheet),
SPI frame construction, fault decode. `kSolenoidBinding[]` maps each
`SolenoidId` (`ClutchA..ParkRelease`) to a MAX22200 chip+channel and
a TCM connector pin — same allocation as the `tcm_pinout.csv` in
`Hardware/OEM_Connector_Model/` (drift-tested in the contrib repo so
firmware vs hardware can't disagree silently).

13 host assertions.

### `test/`

Mirrors the `IUnitTest` framework you already use in `Stm32-vcu/test/`
so the testing style is consistent across the openinverter project
family.

```
cd Software/test
make
./test_8hp
```

35 host assertions: 12 shift_logic + 10 park_lock + 13 solenoid_driver.
Stock `g++` ≥ 9, no extra dependencies, builds + runs in under a
second.

## What's deliberately not here

- **No CAN protocol / DBC.** That's an integration choice; it belongs
  with you. The modules above don't depend on any specific protocol.
- **No bind layer / SPI driver.** Those need MCU and peripheral
  decisions that belong with the bench, not with me.
- **No calibration values.** HIT/HOLD currents per solenoid, shift
  timing, oil-temp curves — bench data, not paper data.
- **No PCB layout.** Hardware design proper is your work.

## Honest framing

I was in the middle of replying to your post on forum thread #6047
with the repo URL anyway. Some of the work happens to fit your
folder structure cleanly, so I figured it's worth offering as a PR
rather than just a forum link. Pull, ignore, or tell me to scope it
down further — happy with any of those.

## License

Same GPLv3 as the rest of the project.
