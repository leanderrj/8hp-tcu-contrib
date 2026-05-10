# ZF 8HP — openinverter contribution workspace

Workspace supporting Damien Maguire's open-source [ZF 8HP TCU](https://github.com/damienmaguire/8HP-TCU)
project ([openinverter.org](https://openinverter.org)). The project is mid-design as of May 2026:
the aux LIN pump just came up after a nine-day reverse-engineering effort, the in-Mechatronik PCB
is being redesigned around the MAX22200 solenoid driver, and the TCM ↔ VCU CAN protocol does not
yet exist. This repo is the work that goes alongside that, in the gaps.

## What's in here

| Layer | Path | Status |
|---|---|---|
| Forum threads, captures, video transcript | `archive/` | snapshot of thread #6047 / #6926 / #7028 / #7103 + Damien's TCM pinout PDF + 553 BMW i4 G26 CAN frames + LIN A/C log |
| LIN aux-pump protocol distilled | `notes/lin_pump_protocol.md` | from forum #7103 RE |
| iX4 0x3F9 shifter analysis | `notes/ix4_can_analysis.md` | derived from the captures |
| Contribution plan | `notes/contribution_plan.md` | what's open and where |
| TCU↔VCU CAN protocol *(draft)* | `proposals/dbc/` | 5 frames, 41 signals, validated with `cantools` |
| BMW G26 0x3F9 CRC8 *(empirically solved)* | `proposals/firmware/bmw_g26_lever/` | 553/553 frames, reproducible with `find_crc.py` |
| iX4_Lever Stm32-vcu PR *(verified building)* | `proposals/firmware/bmw_g26_lever/` | 33 host assertions pass on real upstream |
| Can_ZF8HP codec PR *(verified building)* | `proposals/firmware/can_codegen/` | 24 host assertions pass on real upstream |
| TCM pinout × MAX22200 design analysis | `proposals/tcm_max22200_binding/` | flags the 9-vs-8 channel issue, four-option tradeoff |
| Pytest capture-replay harness | `proposals/test_harness/` | 30 assertions, replays all 553 frames |
| Cloned upstream repos | `repo/` *(gitignored)* | local context |

## Test totals (May 10 2026)

| Suite | Where | Assertions | Status |
|---|---|---|---|
| C++ on `make Test` (Stm32-vcu host) | `proposals/firmware/bmw_g26_lever/` | 33 | passing |
| C++ on `make Test` (Stm32-vcu host) | `proposals/firmware/can_codegen/` | 24 | passing |
| pytest (full corpus replay) | `proposals/test_harness/` | 30 | passing |
| **Total** | | **87** | passing |

All three suites build and run against unmodified upstream `damienmaguire/Stm32-vcu` master.

## Two PRs ready to land

### `iX4_Lever` — G-chassis BMW shifter for Stm32-vcu

Adds a `Shifter` implementation for the 2022+ BMW G-chassis iDrive rotary selector
(CAN ID `0x3F9`). Empirically-determined CRC8 parameters (poly `0x1D`, xorout
`0x04`, bytes [1..7] — same algorithm family as `F30_Lever`, different per-ID
xorout). Patches in `proposals/firmware/bmw_g26_lever/INTEGRATION.md`; verified
to build and pass 33 host assertions on upstream master.

Open: 0x32-vs-0x35 R/D mapping is a hypothesis pending one forum reply; flipping
two `case` labels resolves it either way.

### `Can_ZF8HP` — DBC-driven codec for the TCU↔VCU protocol

The DBC at `proposals/dbc/zf8hp-tcu.dbc` is the protocol; `proposals/firmware/can_codegen/zf8hp_tcu.{h,c}`
is the cantools-generated C99 encoder/decoder; `Can_ZF8HP.{h,cpp}` is the C++
wrapper bridging into the VCU's `Param` and `CanHardware` world. Schema changes
go in the DBC; `bash proposals/firmware/can_codegen/generate.sh` regenerates the
C source. Both sides of the link consume the same generated code.

Open: protocol is **draft v0.1** — five points called out in `proposals/dbc/PROTOCOL.md`
need community input (counter+CRC adoption, ID band reservations, torque-reduction
handshake during shifts, where adaptation values live, manual gear range).

## Reproducing the empirical work

```bash
# 1. Re-derive the BMW G26 0x3F9 CRC parameters from the captures
python3 -m venv .venv && source .venv/bin/activate
pip install cantools pytest
python3 proposals/firmware/bmw_g26_lever/find_crc.py
# -> "range=b1..7  poly=0x1D  init^xorout=0x04  refin=False refout=False"

# 2. Run the full pytest harness
cd proposals/test_harness && pip install -e . && pytest
# -> 30 passed in ~4s

# 3. Apply both PRs and run the C++ host tests
git clone https://github.com/damienmaguire/Stm32-vcu.git
cd Stm32-vcu && git submodule update --init --depth 1
# (apply the patches per each INTEGRATION.md)
make Test && ./test/test_vcu
# -> "All tests passed"
```

## Layout

```
archive/                          raw research material
  captures/                         BMW iX4 G26 CAN/LIN logs (forum #7028)
  forum/                            archived openinverter threads + TCM pinout PDF
  video/                            yt-dlp subtitles for "Project 03" video
notes/                            distilled research, ready to read
  transcript.md                     "Project 03" video transcript
  lin_pump_protocol.md              LIN aux pump protocol distilled from #7103
  ix4_can_analysis.md               0x3F9 shifter analysis
  contribution_plan.md              where the gaps are
proposals/                        PR-ready artifacts and design analysis
  dbc/                              draft TCU↔VCU CAN protocol
  firmware/
    bmw_g26_lever/                  iX4_Lever shifter PR (33 tests)
    can_codegen/                    Can_ZF8HP codec PR (24 tests)
  tcm_max22200_binding/             pinout decode + 9-vs-8 channel analysis
  test_harness/                     pytest full-corpus replay (30 tests)
repo/                             cloned upstream repos (gitignored)
```

## Scope honesty

This repo is **not** the TCU firmware. The TCU firmware is greenfield and
needs the bench (oscilloscope on solenoid currents, LIN xcvr connected to
the pump, real Mechatronik in front of you) — none of which we have.

What this repo *does* contribute:

- **One closed empirical question** (the BMW G26 CRC algorithm)
- **One net-new shifter implementation** (`iX4_Lever`) that drops into Stm32-vcu and adds G-chassis BMW donor cars to the openinverter ecosystem
- **One protocol draft and codec** (`zf8hp-tcu.dbc` + `Can_ZF8HP`) for the still-unwritten TCM↔VCU link
- **One design-time finding** (9 solenoids vs 8 MAX22200 channels) with a four-option tradeoff analysis and a recommended fix
- **Test infrastructure** (`pytest` harness + 87 host-runnable assertions across C++ and Python) that every future PR can plug into

What it deliberately does not do:

- Write the TCU firmware (no hardware to validate against)
- Fuzz the LIN aux pump bytes 1/3/4/5 (needs Damien's bench)
- Reverse-engineer factory BMW PT-CAN traffic (needs an F-/G-chassis donor)

## Active references

- Master 8HP TCU thread: https://openinverter.org/forum/viewtopic.php?t=6047
- "Pump of Doom" LIN reverse engineering: https://openinverter.org/forum/viewtopic.php?t=7103
- BMW i4 G26 CAN/LIN captures: https://openinverter.org/forum/viewtopic.php?t=7028
- ZombieVerter VCU V1.2/1.3 hardware: https://openinverter.org/forum/viewtopic.php?t=6926
- 8HP-TCU hardware repo: https://github.com/damienmaguire/8HP-TCU
- Stm32-vcu firmware: https://github.com/damienmaguire/Stm32-vcu
