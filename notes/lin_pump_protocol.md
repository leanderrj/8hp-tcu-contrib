# ZF GA8P75HZ Aux 12 V Oil Pump — LIN Protocol

Reverse-engineered by Damien Maguire, openinverter forum thread #7103
(Apr 28 – May 7, 2026). Distilled from posts 1 and 7.

## Bus

- **LIN 2.x, 19200 baud, 8-byte data frames.**
- **Master ID `0x30`** — controller → pump (every 25 ms).
- **Slave IDs `0x32`, `0x33`, `0x34`** — pump → controller.
- `0x32` is the only one with motion/state info; `0x33`/`0x34` are diagnostic registers.

## Master frame `0x30` (8 bytes)

```
byte 0  command          0xAA = idle/coldstart, 0x55 = run, others ignored
byte 1  ?                strong effect on behaviour, function unknown  (TBD)
byte 2  phase            0x0A = phase 1 (cold), 0x42 = phase 2 (run-ready)
byte 3  ?                role unknown
byte 4  ?                role unknown
byte 5  ?                role unknown
byte 6  watchdog echo    must mirror byte 6 of the most recent 0x32 response
byte 7  alive counter    rolling 0..15 in low nibble, increment every frame
```

Open: bytes 1, 3, 4, 5 — likely target speed / target pressure / mode.
Worth fuzzing once we have a stable run.

## Slave frame `0x32` (8 bytes)

```
byte 0  status           0x00 = OK, 0x40 = watchdog/comm fault, 0x50 = alt fault
byte 1  static           0x00 or 0xAA, no useful info
byte 2  run flag         0xAA = standby, 0x55 = run acknowledged
byte 3  speed            RPM = value × 32  (0..8160 rpm)
byte 4  supply voltage   V   = value × 0.1 (0..25.5 V)
byte 5  current?         scaling TBD (hint: changes with byte 3 during spin)
byte 6  echo seed        controller MUST copy this into next 0x30 byte 6
byte 7  counter          rolling low nibble
```

A fault state `byte 0 == 0x40` means the watchdog tripped; no useful data
behind it until LIN goes silent ~5 s and the pump self-resets.

## Startup / run state machine

```
              power on
                 │
                 ▼
      ┌──────────────────────┐
      │     COLDSTART        │  TX:  AA 00 0A 00 00 00 73 [ctr]
      │  (≥ 900 ms)          │       every 25 ms
      └──────────┬───────────┘
                 │  after ≥ 900 ms
                 ▼
      ┌──────────────────────┐
      │  PHASE 2 (READY)     │  TX:  AA 00 42 00 00 00 73 [ctr]
      │                      │       every 25 ms
      └──────────┬───────────┘
                 │  pump RX shows 0x32.byte0 == 0x00
                 ▼
      ┌──────────────────────┐
      │       RUN            │  TX:  55 00 42 00 00 00 73 [ctr]
      │  echo seed every     │  with byte 6 = last 0x32.byte6
      │  frame, ctr++        │  every 25 ms (≤ 20 ms settle)
      └──────────┬───────────┘
                 │ on 0x32.byte0 in {0x40, 0x50}
                 ▼
      ┌──────────────────────┐
      │       FAULT          │  hold LIN silent ≥ 5 s
      │                      │  → pump sleeps, restart from COLDSTART
      └──────────────────────┘
```

## Critical rules (the things that bit Damien for 9 days)

1. `byte 6` of the next `0x30` **must equal** byte 6 of the most recent `0x32`.
   Without this echo, the pump faults within one frame.
2. Coldstart is mandatory and ≥ 900 ms long. Skipping it = pump never wakes.
3. Counter (byte 7 low nibble) must increment every frame. Stalled counter = fault.
4. Settle delay between frames ≥ 20 ms; tighter than that and faults appear intermittently.

## Implementation notes for the 8HP-TCU

- The new in-Mechatronik board carries a **LIN transceiver**; it is the LIN master to the pump and **publishes the pump state on CAN** (frame `0x542 TCU_PumpStatus` in our DBC).
- Map directly:
  - `0x32` byte 0 → `PumpFault` flag + `PumpState` enum
  - `0x32` byte 2 → `PumpState` (Standby vs Run)
  - `0x32` byte 3 × 32 → `PumpRPM` (uint16 rpm)
  - `0x32` byte 4 × 0.1 → `PumpVoltage` (V)
  - `0x32` byte 5 → `PumpCurrent` (raw, scale TBD)
- Non-hybrid 8HP variants don't have this pump; the TCU should detect "no LIN response after coldstart × N retries" and disable the pump frame entirely rather than reporting a permanent fault.

## Reference attachments (forum)

These live behind Anubis on the forum; download manually if needed:
- `LIN_TCM_Pump_Coldstart1.txt` — initial bench captures (post 1)
- `8hp_pump_v10.ino` — 4-byte fuzzing Arduino program (post 3)
- `LIN_Pump_Info.pdf` — Damien's distilled write-up (post 7)
- `8hp_LinRunnerV4.ino` — final working bench runner, Arduino Due + LIN xcvr on Serial1 (post 9)
- NHTSA PDF (post 2, URL truncated in source — `static.oemdtc.com/NHTSA-PDFs/MC*4-0001.pdf`)
