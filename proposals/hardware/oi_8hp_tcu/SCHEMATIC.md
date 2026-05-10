# OI 8HP TCU — schematic specification

In-Mechatronik replacement TCM for the ZF G8P75HZ. Replaces the BMW
board on top of the OEM jumper PCB. External world sees only GND,
+12 V, CAN-H, CAN-L (plus LIN to the aux pump on hybrid 'boxes).

**Status: draft for review.** This is the design *intent* expressed
as CSVs (`components.csv` + `nets.csv`). The netlist generator emits
a KiCad-compatible file from them; tests cross-check against the OEM
pinout and the firmware's `kSolenoidBinding[]`. Schematic capture
visualisation, footprint selection, and PCB layout are downstream work
that needs bench iteration we haven't done.

## Block diagram

```
                +12 V (T30) ── ferrite ── TVS40 ── ┬────┬────┬────────────────────┐
                                                    │    │    │                    │
                  GDA (gas-discharge arrestor) ─────┘    │    │                    │
                                                         │    │                    │
                                AP63203 buck (12→5V/2A) ─┘    │                    │
                                       │                      │                    │
                                       ├─→ AP2112 LDO (5→3V3) │                    │
                                       │              │       │                    │
                                       │              │       │                    │
                          STM32F103C8T6 (LQFP-48) ←── 3V3     │                    │
                          ┌────────────┐                      │                    │
                          │            ├ SPI1 ──────────►  MAX22200 #0 ─┐          │
                          │            │  (daisy chain)    (chip 0)     │ ──────┐  │
                          │            │                       │        │       │  │
                          │            │                       └────►  MAX22200 #1
                          │            │                                (chip 1)
                          │            ├ CAN1 ──────────► TJA1043T  ──► CAN-H/L
                          │            ├ USART2 ────────► TJA1027T  ──► LIN-bus
                          │            │
                          │            ├ TIM1.CH1/CH2 ◄── input/output shaft RPM
                          │            ├ ADC1_IN0    ◄── oil temp NTC
                          │            ├ GPIO        ◄── park position 1/2
                          │            ├ GPIO        ◄── T15 wake
                          │            └ SWD/UART ──── J2/J3 (programming/debug)
                          └────────────┘
                                                       │        │
                                  +12V solenoid bank ──┴────────┴── 7+2 outputs
                                                       │        │
                                          ↓ (low-side per channel) ↓
                                    Clutches A/B/C/D/E + TCC + Line P
                                    Park Hold + Park Release
                                                       │
                                                       └── back into J1 (49-pin OEM connector)
```

## Power tree

| Rail  | Source                | Sink (peak)                                                                   |
|-------|-----------------------|-------------------------------------------------------------------------------|
| VBAT  | TCM pin 23 (+22 paralleled) | MAX22200 chips' VBAT, AP63203 input, bulk cap, TVS, GDA                |
| VBAT_SOL | TCM pins 37–40 (paralleled) | All nine flyback diode anodes (path back to VBAT through bulk + ferrite) |
| +5 V  | AP63203 buck (12→5V/2A) | MAX22200 logic VDD ×2, TJA1043 VBAT, TJA1027 VSUP, AP2112 input, sensor exc. via polyfuse |
| +3V3  | AP2112 LDO (5→3.3V/600mA) | STM32 VDD/VDDA/VBAT, TJA1043 VIO, TJA1027 VIO, SWD header                 |
| SENSE_5V | +5V via 500 mA polyfuse | TCM pin 15 (VR sensor excitation)                                       |

## STM32F103C8T6 pin allocation

Allocations chosen to keep peripheral functions on default-remap pins
where possible.

| Pin | Function | Net |
|---|---|---|
| OSC_IN/OSC_OUT | 8 MHz HSE | HSE_IN / HSE_OUT |
| NRST | reset (button + SWD) | NRST |
| BOOT0 | tied LOW for flash boot | GND |
| PA0 | ADC1_IN0 | OIL_TEMP_NTC (divider) |
| PA2 / PA3 | USART2 TX/RX | LIN_TX / LIN_RX |
| PA4 / PA5 / PA6 / PA7 | SPI1 NSS/SCK/MISO/MOSI | SPI_CS / SCK / MISO / MOSI |
| PA8 | TIM1 CH1 (input capture) | INPUT_SHAFT_RPM |
| PA9 | TIM1 CH2 (input capture) | OUTPUT_SHAFT_RPM |
| PA11 / PA12 | bxCAN RX/TX | CAN_RX / CAN_TX |
| PA13 / PA14 | SWDIO/SWCLK | J2 |
| PA15 | GPIO | CAN_STBN (TJA1043 standby) |
| PB1 | GPIO (open-drain input, wired-OR) | MAX_FAULT |
| PB6 | GPIO | CAN_EN (TJA1043 enable) |
| PB7 | GPIO with EXTI | CAN_INH (wake from CAN) |
| PB8 | GPIO with EXTI | T15_WAKE |
| PB10 / PB11 | USART3 TX/RX | DEBUG_TX / DEBUG_RX |
| PB12 | GPIO | LIN_SLP (TJA1027 sleep) |
| PB13 / PB14 | GPIO with internal pull-up | PARK_POS_1 / PARK_POS_2 |
| PC13 | GPIO active-low | LED_STATUS |

The `test_no_stm32_pin_is_double_claimed` test enforces this allocation
— any future edit that puts two signal nets on the same STM32 pin
fails CI. (An earlier draft caught three real conflicts: PA8/PA9
between CAN sleep-control and shaft-RPM timer captures, and PB10
between T15 wake and USART3 debug. Resolved as recorded above.)

## Solenoid binding (cross-checked vs `solenoids.h`)

| MAX22200 | OUT | Solenoid | TCM pin |
|---|---|---|---|
| #0 | OUT0 | ClutchA | 41 |
| #0 | OUT1 | ClutchB | 43 |
| #0 | OUT2 | ClutchC | 45 |
| #0 | OUT3 | ClutchD | 42 |
| #0 | OUT4 | ClutchE | 44 |
| #0 | OUT5 | TCC | 46 |
| #0 | OUT6 | LinePressure | 47 |
| #0 | OUT7 | *spare* | — |
| #1 | OUT0 | ParkHold | 5 |
| #1 | OUT1 | ParkRelease | 48 |
| #1 | OUT2..7 | *spare* | — |

Two-chip daisy-chain on a single SPI / single CS, per
`proposals/tcm_max22200_binding/SOLENOID_BINDING.md` Option A. Park
subsystem on its own chip — keeps the safety-critical channel pair off
the same silicon as the proportional clutches (HARA T001 / T002,
ASIL C–D coverage in `proposals/safety/hara.py`).

## Per-solenoid current calibration

Empty slots filled by bench measurement on Damien's setup. The
`SolenoidCalibration` struct in `proposals/firmware/tcu_bind/tcu_bind.h`
loads the table at boot from a YAML/NVM source; the schematic doesn't
hard-code anything irreversible, just provides the wiring + flyback
diodes that any HIT/HOLD profile needs.

## What this schematic deliberately does NOT do

- **No PCB layout.** Mechanical fit inside the OEM Mechatronik case
  needs Damien's 3D scan; copper pours, return paths, EMC are real
  iteration work.
- **No vehicle-side PT-CAN 2 termination.** The OEM Mechatronik talks
  to two PT-CAN buses; we only hang TCU communication off PT-CAN 1
  (or a dedicated CAN, depending on installation). PT-CAN 2 is
  passed through to the external connector untouched.
- **No fault-current monitoring on the buck/LDO.** A safety-case
  upgrade later would add INA214-class shunt monitors on each rail
  to flag rail droop.
- **No connector footprints.** The OEM 49-pin Mechatronik plug is
  proprietary; the symbol exists (`oem_interface/oem_tcm.kicad_sym`)
  but a footprint requires measurement of a real harness.

## Files

| File | Role |
|---|---|
| `components.csv` | reference designators, part numbers, packages, datasheet pointers |
| `nets.csv` | every connection (`net,component,pin,note`) |
| `gen_netlist.py` | reads the CSVs, emits `oi_8hp_tcu.net` (KiCad legacy netlist format) |
| `oi_8hp_tcu.net` | generated; importable into KiCad's PCB editor via "Import Netlist" |
| `SCHEMATIC.md` | this document |

## Drift detection

`proposals/test_harness/tests/test_oi_8hp_tcu_schematic.py` enforces:

- Every component referenced in `nets.csv` exists in `components.csv`.
- Every J1 (OEM connector) pin used in the netlist matches the OEM
  pinout in `proposals/hardware/oem_interface/tcm_pinout.csv`.
- The nine solenoid output nets connect the MAX22200 chip+channel to
  the TCM pin specified by the firmware's `kSolenoidBinding[]`.
- No STM32 pin is double-claimed by two different signal nets except
  where annotated as a known conflict.
- The .net file regenerates byte-identically from the CSVs.

## Reproducing

```bash
cd proposals/hardware/oi_8hp_tcu
python3 gen_netlist.py
# -> oi_8hp_tcu.net (deterministic; SHA-256 invariant unless CSVs change)
```

Import into a fresh KiCad PCB:

```
KiCad → New Project → Empty
  PCB Editor → File → Import → Specctra Netlist (or Pcbnew menu Import)
  Choose oi_8hp_tcu.net
```

The netlist gives you all components + all connections without a
visual schematic. From there it's footprint-assignment + layout work
that we deliberately leave to whoever is closest to the bench.
