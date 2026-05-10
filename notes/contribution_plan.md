# 8HP-TCU — CAN Bus Contribution Plan

## Where we are (May 10, 2026)

Confirmed from forum threads #6047 (master 8HP TCU thread, started Jan 2025) and #7103 ("Pump Of Doom") plus the Project 03 video:

- **Aux 12 V LIN pump runs reliably.** Watchdog echo on byte 6 of `0x30` was the breakthrough. Distilled protocol: `notes/lin_pump_protocol.md`. Bytes 1/3/4/5 of the master frame still unknown — likely speed/pressure/mode targets.
- **Architecture decided** (Damien, May 7 2026, thread #6047 post 22 — same conclusion as the video): the OI TCM goes *inside* the OEM Mechatronik case, sitting on top of the jumper PCB. External world only sees GND, 12 V, CAN-H, CAN-L (plus LIN to the aux pump on hybrid 'boxes). Optional standalone mode with a CAN shifter.
- **Solenoid driver chosen: MAX22200.** First TCU revision lacked closed-loop current control of the solenoids — Damien is redesigning around the MAX22200 (Maxim 8-channel solenoid driver with current sense per channel). This implies the TCU firmware will need a per-solenoid current-control loop in the new module.
- **Bellhousing 3D-scanned**, basic adapter plate cut. Test vehicle is now likely the 2008 E92 (was '97 E39).
- **TCM Pinout PDF posted May 10** in thread #6047 post 24 (`TCM_Pinout.pdf`, 555 KiB) — solenoids, sensors, external connector. **TODO: download manually** (Anubis); place at `archive/forum/TCM_Pinout.pdf`. We need this before writing anything that touches solenoid IDs.
- **Hardware repo** `damienmaguire/8HP-TCU` is KiCad-only; `Software/` is a placeholder. Firmware will live in/alongside `damienmaguire/Stm32-vcu`. That repo has zero `8HP/ZF/GA8P75` references — greenfield.

## Cross-platform value (from thread #6047)

Same gearbox or close cousin lives in:
- BMW PHEV F-chassis (GA8P75HZ — the immediate target).
- **Jeep Wrangler 4xe** PHEV and **Grand Cherokee 4xe** PHEV (Stellantis code 8P75HP). Confirmed by P.S.Mangelsdorf.
- The wider ZF 8HP family covers a *very* large list of RWD/AWD vehicles ([wiki](https://en.wikipedia.org/wiki/ZF_8HP_transmission)).

Anything we design should keep the hybrid extras (engine-input clutch K0 solenoid, aux pump LIN) optional so the firmware also runs on plain ICE 8HPs and reaches that bigger audience.

## VCU side (from thread #6926)

The VCU we're talking to has just had a hardware bump — useful constraints for our protocol design:

- **V1.2 / V1.3 has 4 CAN channels** (CAN-FD via MCP251863T). Means we don't have to share PT-CAN with everything else; the TCU can sit on its own dedicated CAN if useful.
- **CAN1 has wake-on-CAN** via TJA1043T. If the TCU sleeps, a single canonical "VCU is awake" frame can wake it.
- **The new HW features are largely unsupported in firmware right now** (Damien, thread #6926 post 28). DigiPot V2 needed a community fix; freeze frames, RTC, accelerometer, the 4th CAN channel — all open contribution surface, separate from but adjacent to our 8HP work.

## Existing scaffolding in Stm32-vcu we can lean on

- `include/shifter.h` — abstract `Shifter` class (Task1Ms/10Ms/100Ms/200Ms + `DecodeCAN` + `GetGear`). `F30_Lever`, `E65_Lever`, `no_Lever` are the implementations.
- `Documentation/CAN dbcs/oi-inverter.dbc` — openinverter DBC style we mirrored in `proposals/dbc/zf8hp-tcu.dbc`.
- `src/Can_OI.cpp`, `src/Can_VAG.cpp` — bidirectional CAN class examples.
- `test/` — host-runnable unit tests (`make Test`), dummy `Param::Change`. Already enough to test frame encode/decode and state machines without hardware.

## Concrete contribution targets (in order of leverage)

### 1. CAN protocol draft (DONE, in review)
`proposals/dbc/zf8hp-tcu.dbc` + `proposals/dbc/PROTOCOL.md`. Five frames, validated with `cantools`, pump fields grounded in thread #7103 RE. Open questions called out in `PROTOCOL.md`.

### 2. `ZF8HP.{h,cpp}` skeleton in Stm32-vcu *(next)*
VCU consumer side. Subscribes to the existing `Shifter` for driver intent, transmits `0x520 VCU_GearRequest` + `0x521 VCU_VehicleInfo`, decodes the three TCU status frames, exposes `oilTemp`, `currentGear`, `lineP`, `pumpRPM`, etc. as VCU params (so they auto-show in the web UI).

### 3. `CanHardwareLinux` backend in Stm32-vcu *(parallel)*
A new `CanHardware` implementation that talks to Linux SocketCAN `vcan0` instead of libopencm3 bxCAN. Lets the entire VCU app run as a desktop binary. This unblocks every contributor — the existing test/ scaffolding gets paired with real CAN traffic.

### 4. TCU firmware skeleton (separate project)
Greenfield. Targets the in-Mechatronik board. Modules:
- `Pump.cpp` — LIN master state machine (cold-start → phase 2 → run, byte-6 echo, retries).
- `Solenoids.cpp` — MAX22200 driver with closed-loop per-channel current control.
- `Sensors.cpp` — input/output shaft speed, oil temp, line pressure read.
- `Shift.cpp` — gear-shift state machine (target ↔ current, hand-shake with VCU during torque-cut shift).
- `CanLink.cpp` — DBC producer/consumer, mirror of (2).
- Reuse `libopeninv` for params, web interface, and OTA.

### 5. Aux pump LIN byte fuzzing
Bytes 1/3/4/5 of `0x30` are still mystery. Bench the pump on a Linux box with a USB-LIN tool, vary one byte at a time while running, log RPM via byte 3 of `0x32`. Cheap, well-bounded — the kind of thing that produces a single-post forum contribution Damien would welcome.

### 6. Reverse-engineer factory ZF 8HP CAN *(longer term)*
For drop-in compatibility on stock BMW PT-CAN. Needs an F-chassis donor or community CAN dumps. `repo/BMW-E65-CANBUS/` (E65 = ZF 6HP) shows BMW message taxonomy but is not the same gearbox. The Jeep 4xe community angle (P.S.Mangelsdorf has a possible donor) could shortcut this.

## Hardware-free dev stack (recap)

Layer 1 (`make Test` host unit tests) — already exists.
Layer 2 (SocketCAN `vcan0` + `CanHardwareLinux`) — target #3 above.
Layer 3 (Python "virtual Mechatronik" simulator on `vcan0`, `pytest` shift integration tests) — needs LIN sim too once #4 has shape.
Layer 4 (Renode emulation of STM32F1 + bxCAN) — only if/when ISR/DMA timing testing is needed.

## Files in this archive

```
archive/
  video/89P2md4vqlg.en.srt              raw subtitles, Project 03
  forum/thread7103.md                   "Pump Of Doom" full text
  forum/thread6047_8HP_TCU.md           master 8HP TCU thread
  forum/thread6926_VCU_V12.md           VCU V1.2/V1.3 hardware update
  forum/TCM_Pinout.pdf                  *missing — download manually*
notes/
  transcript.md                         clean Project 03 transcript
  transcript_timestamped.md             with timestamps
  lin_pump_protocol.md                  distilled LIN pump protocol
  contribution_plan.md                  this file
proposals/dbc/
  zf8hp-tcu.dbc                         draft CAN protocol (validated)
  PROTOCOL.md                           protocol rationale + open questions
repo/
  8HP-TCU/                              hardware (KiCad)
  Stm32-vcu/                            VCU firmware (target codebase)
  BMW-E65-CANBUS/                       E65/6HP reference dumps
  node-bmw-ref/                         BMW DBUS/IBUS/KBUS notes
```
