# 8hp-tcu-contrib

Adjacent-contribution workspace for the openinverter [ZF 8HP TCU
project](https://github.com/damienmaguire/8HP-TCU) and the wider
[`Stm32-vcu`](https://github.com/damienmaguire/Stm32-vcu) ecosystem.
Research, analysis, drift-tested firmware modules, KiCad connector
model, draft schematic netlist, ISO 26262-3 HARA, capture corpus.

This repo is not a fork. See
[`docs/upstream-relationship.md`](#upstream-relationship) below for the
shape.

## Upstream relationship

```
                          tracks via submodule
                    ┌──────────────────────────────────┐
                    ▼                                  │
leanderrj/8hp-tcu-contrib (standalone)              upstream
                    │                                  ▲
                    │ pinned at upstream/8HP-TCU       │
                    │ pinned at upstream/Stm32-vcu     │
                    │                                  │
                    │ separate work-area forks for PRs:│
                    ▼                                  │
leanderrj/8HP-TCU   (fork) ─────PR──▶ damienmaguire/8HP-TCU
leanderrj/Stm32-vcu (fork) ─────PR──▶ damienmaguire/Stm32-vcu
```

| Repo | Role |
|---|---|
| `leanderrj/8hp-tcu-contrib` | research + analysis + reference |
| `leanderrj/Stm32-vcu` | PR-staging fork |
| `leanderrj/8HP-TCU` | PR-staging fork |
| `upstream/8HP-TCU/` (submodule) | pinned upstream of `damienmaguire/8HP-TCU` |
| `upstream/Stm32-vcu/` (submodule) | pinned upstream of `damienmaguire/Stm32-vcu` |

## Layout

```
archive/
  captures/                 553-frame BMW i4 G26 CAN log + LIN A/C log
  forum/                    archived openinverter threads (markdown) + TCM_Pinout.pdf
  references/               MAX22200 datasheet + ZF gearset patent + SHA256SUMS
  video/                    yt-dlp subtitles for "Project 03"
notes/                      distilled research
  transcript.md             video transcript
  lin_pump_protocol.md      LIN aux pump protocol (from forum #7103)
  ix4_can_analysis.md       0x3F9 shifter frame analysis
  contribution_plan.md
proposals/
  dbc/
    zf8hp-tcu.dbc           draft TCU↔VCU CAN protocol (6 frames, 54 signals)
    PROTOCOL.md
  firmware/
    bmw_g26_lever/          iX4_Lever shifter (PR-ready for Stm32-vcu)
    can_codegen/            cantools-driven C99 codec + Can_ZF8HP wrapper
    shift_logic/            8HP shift state machine + clutch table
    park_lock/              safety-critical pawl state machine
    solenoid_driver/        MAX22200 register layout + frame builder
    tcu_bind/               per-tick orchestrator wiring the modules together
  hardware/
    oem_interface/          KiCad symbol library for the 49+16 pin OEM connectors
    oi_8hp_tcu/             draft schematic netlist for the in-Mechatronik board
  safety/
    hara.py                 ISO 26262-3 HARA, 12 hazards, 13 derived requirements
    HARA_REPORT.txt         pre-generated formatted report
  tcm_max22200_binding/     pinout decode + 9-vs-8 channel design analysis
  test_harness/             pytest full-corpus replay + scenario tests + plant model
  contributions/
    stm32_vcu_ix4_lever/    PR draft for damienmaguire/Stm32-vcu
    8hp_tcu_software_skeleton/  PR draft for damienmaguire/8HP-TCU
  forum_reply_6047.md       drafted reply for the openinverter master thread
upstream/
  8HP-TCU/                  submodule pinned to damienmaguire/8HP-TCU
  Stm32-vcu/                submodule pinned to damienmaguire/Stm32-vcu
```

## Tests

Total: **219 host-runnable assertions** (104 C++ via `make Test`, 115
pytest), all passing. No bench, no peripheral access, no STM32
toolchain required for any of them.

| Suite | Path | Assertions |
|---|---|---|
| C++ — iX4_Lever | `proposals/firmware/bmw_g26_lever/` | 33 |
| C++ — Can_ZF8HP codec | `proposals/firmware/can_codegen/` | 26 |
| C++ — shift_logic | `proposals/firmware/shift_logic/` | 12 |
| C++ — park_lock | `proposals/firmware/park_lock/` | 10 |
| C++ — solenoid_driver | `proposals/firmware/solenoid_driver/` | 13 |
| C++ — tcu_bind | `proposals/firmware/tcu_bind/` | 10 |
| pytest — full-corpus replay + DBC roundtrip | `proposals/test_harness/` | 55 |
| pytest — LIN pump simulator | `proposals/test_harness/` | 10 |
| pytest — HARA validation | `proposals/test_harness/tests/test_hara.py` | 12 |
| pytest — scenario drive cycles | `proposals/test_harness/tests/scenarios/` | 8 |
| pytest — plant model | `proposals/test_harness/tests/test_plant_model.py` | 11 |
| pytest — OEM connector model | `proposals/test_harness/tests/test_oem_pinout.py` | 16 |
| pytest — schematic netlist | `proposals/test_harness/tests/test_oi_8hp_tcu_schematic.py` | 24 |

C++ tests build against unmodified `damienmaguire/Stm32-vcu` master
via the `upstream/Stm32-vcu` submodule. pytest runs from
`proposals/test_harness/` after `pip install -e .`.

## PR drafts

Branches prepared, builds verified, **not yet pushed or opened**.

### `iX4_Lever` for `damienmaguire/Stm32-vcu`

- Working clone: `/tmp/Stm32-vcu-fork` on branch `feat/ix4-lever-bmw-g26`
- Diff: 9 files, 351 insertions
- Body: [`proposals/contributions/stm32_vcu_ix4_lever/PR_BODY.md`](proposals/contributions/stm32_vcu_ix4_lever/PR_BODY.md)
- Status: 33 host assertions pass on upstream master

### Firmware skeleton + connector model for `damienmaguire/8HP-TCU`

- Working clone: `/tmp/8HP-TCU-fork` on branch
  `feat/firmware-skeleton-and-connector-model`
- Diff: 26 files, ~3 000 insertions
- Body: [`proposals/contributions/8hp_tcu_software_skeleton/PR_BODY.md`](proposals/contributions/8hp_tcu_software_skeleton/PR_BODY.md)
- Status: 35 host assertions pass

Each subdirectory's `README.md` has the exact `gh pr create` command
to open the corresponding PR.

## Reproducing

```bash
# Clone with submodules
git clone --recurse-submodules https://github.com/leanderrj/8hp-tcu-contrib.git
cd 8hp-tcu-contrib

# Re-derive the BMW G26 0x3F9 CRC parameters from the captures
python3 proposals/firmware/bmw_g26_lever/find_crc.py
# → range=b1..7  poly=0x1D  init^xorout=0x04  refin=False refout=False

# Sweep CRC across every BMW E2E frame in the captures
python3 proposals/firmware/bmw_g26_lever/find_crc_batch.py
# → 24 / 33 candidates fit BMW CRC8/0x1D, full table in G26_CRC_CATALOG.md

# Run the full pytest harness
python3 -m venv .venv && source .venv/bin/activate
pip install cantools pytest pyyaml
cd proposals/test_harness && pip install -e . && pytest
# → 115 passed (8 skipped if optional caros_integration profile absent)

# Run the C++ host tests against upstream Stm32-vcu master
# (procedure documented in proposals/firmware/*/INTEGRATION.md)
cd ../../upstream/Stm32-vcu
git submodule update --init --depth 1   # pulls libopeninv
# Apply patches from each INTEGRATION.md, then:
make Test && ./test/test_vcu
# → All tests passed

# Verify reference PDFs against archived SHA-256
shasum -c archive/references/SHA256SUMS
# → US7789799B2_zf8hp.pdf: OK
# → MAX22200_datasheet.pdf: OK
```

## License

Project is GPLv3 to match the upstream openinverter projects this
contributes to. Reference PDFs in `archive/references/` retain their
original publishers' copyright (cite-only).

## References

- 8HP-TCU project: https://github.com/damienmaguire/8HP-TCU
- ZombieVerter VCU: https://github.com/damienmaguire/Stm32-vcu
- Master 8HP TCU forum thread: https://openinverter.org/forum/viewtopic.php?t=6047
- "Pump of Doom" LIN RE: https://openinverter.org/forum/viewtopic.php?t=7103
- BMW i4 G26 CAN/LIN captures: https://openinverter.org/forum/viewtopic.php?t=7028
- ZombieVerter VCU V1.2/1.3: https://openinverter.org/forum/viewtopic.php?t=6926
- ZF 8HP family: https://en.wikipedia.org/wiki/ZF_8HP_transmission
- SAE 2009-01-1083 (Greiner & Grumbach): clutch engagement schedule
- US 7,789,799 B2 (Diosi et al., ZF): Ravigneaux gearset disclosure
