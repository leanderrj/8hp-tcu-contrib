# ZF 8HP — openinverter contribution workspace

Workspace for contributing CAN-bus functionality to Damien Maguire's open-source
[ZF 8HP TCU](https://github.com/damienmaguire/8HP-TCU) project on
[openinverter.org](https://openinverter.org).

## Status (2026-05-10)

- LIN aux 12 V pump protocol distilled from forum thread #7103.
- TCU↔VCU CAN protocol drafted as a DBC and validated round-trip with `cantools`.
- BMW G26 `0x3F9` shifter CRC8 reverse-engineered and verified against 553 captured frames.
- Two PR-ready contributions to `Stm32-vcu`, both passing host-runnable unit tests
  against the real upstream `make Test` harness:
  - `iX4_Lever` — G-chassis BMW iDrive shifter implementation (33 assertions).
  - `Can_ZF8HP` — DBC-driven C99 codec + C++ wrapper for the TCU↔VCU protocol (24 assertions).

## Layout

```
archive/                 raw research material (not transformed)
  captures/                BMW iX4 G26 CAN/LIN captures (forum #7028)
  forum/                   archived openinverter threads as markdown
  video/                   yt-dlp subtitles
notes/                   distilled research and analysis
  transcript.md            "Project 03" video transcript
  lin_pump_protocol.md     LIN aux pump protocol distilled from forum #7103
  ix4_can_analysis.md      0x3F9 shifter analysis
  contribution_plan.md     where the gaps are and what to fill
proposals/               PR-ready artifacts
  dbc/
    zf8hp-tcu.dbc          5 frames, 41 signals, 500 kbit/s
    PROTOCOL.md
  firmware/
    bmw_g26_lever/         iX4_Lever shifter (drop-in for Stm32-vcu)
    can_codegen/           DBC-driven C99 codec + C++ wrapper
repo/                    cloned upstream repos (gitignored — local context)
```

## Reproducing the deliverables

```bash
# 1. Clone Stm32-vcu and pull libopeninv submodule
git clone https://github.com/damienmaguire/Stm32-vcu.git
cd Stm32-vcu
git submodule update --init --depth 1

# 2. Apply the iX4_Lever PR
cp ../proposals/firmware/bmw_g26_lever/iX4_Lever.{h,cpp} src/
cp ../proposals/firmware/bmw_g26_lever/iX4_Lever.h include/
cp ../proposals/firmware/bmw_g26_lever/{test_iX4_Lever.cpp,test_fixtures.h,canhardware_stub.cpp} test/
# Apply test_list.h + Makefile patches per proposals/firmware/bmw_g26_lever/INTEGRATION.md

# 3. Apply the Can_ZF8HP PR (similar — see can_codegen/INTEGRATION.md)

# 4. Build + run host tests
make Test && ./test/test_vcu
```

Re-deriving the empirical CRC search:

```bash
python3 -m venv venv && source venv/bin/activate
pip install cantools
python3 proposals/firmware/bmw_g26_lever/find_crc.py
```

## References

- Master 8HP TCU thread: https://openinverter.org/forum/viewtopic.php?t=6047
- "Pump Of Doom" LIN reverse engineering: https://openinverter.org/forum/viewtopic.php?t=7103
- BMW i4 G26 CAN/LIN captures: https://openinverter.org/forum/viewtopic.php?t=7028
- ZombieVerter VCU V1.2 hardware: https://openinverter.org/forum/viewtopic.php?t=6926
- 8HP-TCU hardware repo: https://github.com/damienmaguire/8HP-TCU
- Stm32-vcu firmware: https://github.com/damienmaguire/Stm32-vcu
