# ZF G8P75HZ TCM — full pinout (49 pins)

Source: `archive/forum/TCM_Pinout.pdf` posted by Damien Maguire to openinverter
forum thread #6047 on 2026-05-10. The TCM pin numbering follows the photograph
in the PDF (pins 1–18 on the left edge, 19–36 along the bottom, 37–49 along
the top of the connector window).

## Pins by function

### Solenoids (driver outputs)

| TCM pin | Function | Drive type | Role |
|---|---|---|---|
| 5  | Park Hold Solenoid    | ON/OFF latching | engages park lock |
| 41 | A Clutch Solenoid     | proportional    | clutch element A (PWM with current control) |
| 42 | D Clutch Solenoid     | proportional    | clutch element D |
| 43 | B Clutch Solenoid     | proportional    | clutch element B |
| 44 | E Clutch Solenoid     | proportional    | clutch element E |
| 45 | C Clutch Solenoid     | proportional    | clutch element C |
| 46 | TCC Solenoid          | proportional    | torque converter lockup clutch |
| 47 | Line Pressure Solenoid| proportional    | main hydraulic line pressure regulator |
| 48 | Park Release Solenoid | ON/OFF latching | releases park lock |

**9 solenoids total. 7 proportional + 2 latching.**

### Solenoid power
| Pins 37, 38, 39, 40 | +12 V supply to solenoids (paralleled for current capacity) |

### Sensors

| TCM pin | Function | Notes |
|---|---|---|
| 6  | Thermistor (oil temp) | NTC, paired with pin 7 |
| 7  | Thermistor (oil temp) | second wire of the NTC pair |
| 12 | Park Lock Sense Ground| common return for park-lock position switches |
| 13 | Park Pos 1            | park-lock position switch contact 1 |
| 14 | Park Pos 2            | park-lock position switch contact 2 |
| 15 | Speed sensor +5 V supply | excitation (red wire — annotated `?` in source PDF) |
| 16 | Input shaft speed sensor | turbine RPM |
| 17 | Output shaft speed sensor| transmission output RPM |

### Aux pump LIN bus

| TCM pin | Function |
|---|---|
| 2 | LIN bus to aux 12 V oil pump (the "Pump of Doom" — see `notes/lin_pump_protocol.md`) |

### External connector (the BMW Mechatronik OEM connector exposed to the vehicle)

The external connector has 16 pins. The TCM-to-Ext-Conn map (with OEM signal
labels where known):

| Ext Conn Pin | TCM pin(s) | OEM signal |
|---|---|---|
| 1  | 32         | (unlabeled) |
| 2  | 29         | (unlabeled) |
| 3  | 34         | **PT CAN 2 LOW** |
| 4  | 33         | **PT CAN 2 HIGH** |
| 5  | 31         | **PT CAN 1 HIGH** |
| 6  | 30         | **PT CAN 1 LOW** |
| 7  | 27         | (unlabeled) |
| 8  | 35         | (unlabeled) |
| 9  | 26         | **T15 — ignition wakeup** |
| 10 | 36         | (unlabeled) |
| 11 | 19         | (unlabeled) |
| 12 | 28         | (unlabeled) |
| 13 | 22, **23** | **T30 — +12 V battery** (pin 23 carries the official OEM label; 22 is paralleled) |
| 14 | **24**, 25 | **T31 — chassis ground** (pin 24 carries the official OEM label; 25 is paralleled) |
| 15 | 20         | (unlabeled) |
| 16 | 21         | (unlabeled) |

### Unassigned in source PDF

Pins **1, 3, 4, 8, 9, 10, 11, 18, 49** had no function called out. Pins 22, 25 are paralleled signals already covered by 23, 24. Likely candidates for the unmarked pins: regulated 5 V rail to sensors, additional sensor returns, a second thermistor return. Worth confirming on the bench before laying out the replacement PCB.

## Two CAN buses — confirmed

The OEM Mechatronik talks to the BMW vehicle on **two separate PT-CAN buses**
exposed at the external connector:
- PT-CAN 1 on Ext Conn pins 5/6 (TCM 31/30)
- PT-CAN 2 on Ext Conn pins 3/4 (TCM 34/33)

This validates the architectural assumption in `proposals/dbc/PROTOCOL.md`
that the openinverter TCM ↔ VCU protocol can sit on its own dedicated CAN
bus separate from any OEM PT-CAN traffic.

## Wakeup behaviour

T15 (Ext Conn pin 9, TCM pin 26) is the ignition wakeup line. The replacement
TCM should sleep when T15 is de-asserted and the bus is idle, draining
~milliamps from T30. The ZombieVerter VCU V1.2 has `CAN1_WAKE_OUT` for
exactly this kind of bus-level wake — useful if we want the TCM to also wake
on CAN traffic without T15.

## Park-lock subsystem

Park is the only system on the TCM with both a sense and a drive path:
- **Sense:** pins 12 (ground), 13 (Pos 1), 14 (Pos 2) — a two-position switch reporting whether the park pawl is engaged
- **Drive:** pins 5 (Hold) and 48 (Release)

Park is safety-critical: the firmware needs to (a) verify position from the
switches before reporting "in Park" on CAN, (b) not energise Hold and Release
simultaneously, and (c) hold Park asserted on power-loss (the latching coil
is normally de-energised once the pawl engages).
