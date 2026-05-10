# openinverter.org thread #7103 — "The Pump Of Doom"

Source: https://openinverter.org/forum/viewtopic.php?t=7103
Forum: Drive trains (motors and inverters)
Captured: 2026-05-10 (forum was behind Anubis bot challenge — content pasted by user)

---

## Post 1 — Jack Bauer (Damien Maguire), Tue Apr 28, 2026 5:27 pm

Welcome folks to my nemesis, the pump of Doom!! Also known as the auxiliary 12 V oil pump in the PHEV version of the ZF 8HP gearbox. I'm 4 days in so far and have managed the amazing feat of making it run reliably for 300 ms!

### ZF GA8P75HZ 12 V Aux Oil Pump — Project Summary (April 2026)

**Hardware & Protocol Basics**

- LIN @ 19200 baud, 8-byte frames (LIN V2)
- Master request on `0x30`, slave responses on `0x32` / `0x33` / `0x34`
- Byte 7 = rolling 4-bit counter (must increment each frame)
- All three status frames bytes 0 and 1 must be `0x00` for the pump to be "happy"

**Mandatory Coldstart Sequence in 0x30**

1. `byte0 = 0xAA, byte2 = 0x0A` (Phase 1)
2. After ~900–1000 ms, change `byte2` to `0x42` (Phase 2)
3. Only after this will the pump respond to any command

**Run Trigger**

- Only `byte0 = 0x55` will make the pump spin
- `0x55` is the bitwise inverse of `0xAA` (classic safety pattern)
- Any other value for `byte0` is ignored

**Key Observations**

- Byte 1 has the strongest effect on behavior (ticking speed, how long it stays happy)
- Almost every `0x55` command eventually triggers `0x40` fault in status frames byte 0
- The pump is extremely safety-paranoid and has a watchdog (~330–770 ms typical)

**Run procedure used**

- TCM sends `AA 00 0A 00 00 00 73 xx` at first.
- Switches to `AA 00 42 00 00 00 73 xx` after approx 900 ms.
- Setting `55 00 42 00 00 00 73 xx` causes a spin for ~300 ms then pump faults until next power cycle or LIN pause for ~5 seconds causes the pump to sleep and reset.

### ZF GA8P75HZ Pump — 0x32 Feedback Summary

`0x32` is the pump's main status & motion report (8-byte LIN slave response).

| Byte | Meaning | Observed values | What it tells us |
|---|---|---|---|
| 0 | Status | `0x00` = Normal, `0x40` = Fault (most common), `0x50` = Alternate fault | `0x00` = pump accepting command, `0x40`/`0x50` = immediate shutdown |
| 1 | Usually static | `0x00` or `0xAA` | Not useful for motion |
| 2 | Safety / Run flag | `0xAA` = Standby/reset/coldstart, `0x55` = Run acknowledged | **Critical**: clearest "pump in run mode" flag |
| 3 | Motion / Speed indicator | `0x00`/`0xAA` = stopped; `0x2A`, `0x17`, `0x3A`, `0x55` etc. = spinning | **Best motion signature** — non-zero + non-AA = motor physically kicking |
| 4 | Secondary motion / torque | Changes with byte 3 during spin | Supports byte 3 (less consistent) |
| 5–7 | Counters / checksum | Rolling low nibble in byte 7 | Mostly housekeeping |

**Core behavioural pattern (every time)**

1. Coldstart finishes (`AA 00 42 …`)
2. First good `0x55` command → 0x32 instantly becomes `00 00 55 2A 14 xx xx xx` (motor spins briefly)
3. Second/any subsequent `0x55` frame → 0x32 changes to `40 00 AA 00 00 xx xx xx` (fault + reset)
4. Pump makes rapid ticking sound and goes silent ("Slave not responding" on PeakLIN)

→ Pump accepts exactly one valid `0x55` frame before its safety watchdog kills the command.

**Proven so far**

- Only `byte0 = 0x55` ever produces motion in 0x32.
- The brief spin is real (audible + byte 3 changes).
- The watchdog is extremely strict — looks at the second 0x55 frame and decides "this is not a valid sustained command".
- 0x32 is the only frame that reliably shows the motor turning (bytes 2 + 3 together are the smoking gun).
- 0x33 and 0x34 are basically status / temperature / version registers — no useful motion data.

**Attachments:** `LIN_TCM_Pump_Coldstart1.txt`, `pump1.jpg`–`pump4.jpg`

---

## Post 2 — Jack Bauer, Wed Apr 29, 2026 9:43 am

I see everyone is as super excited about this as I am and can't wait for an update. I was sent this link which has some useful photos and other info:

https://static.oemdtc.com/NHTSA-PDFs/MC...4-0001.pdf  *(URL truncated in source — appears to be an NHTSA recall doc)*

---

## Post 3 — Jack Bauer, Wed Apr 29, 2026 6:12 pm

The update nobody was waiting for. Now trying all possible 4 byte combos with this nifty program. Gonna take about 5 days it seems.

**Attachment:** `8hp_pump_v10.ino` (8.69 KiB) — brute-force Arduino program

---

## Post 4 — MattsAwesomeStuff, Thu Apr 30, 2026 12:38 am

> Brute forcing CAN? Well alright, I'm here for it.

---

## Post 5 — Jack Bauer, Thu Apr 30, 2026 8:06 am

LIN actually but yay for the bump :)

---

## Post 6 — Ruudi S, Thu Apr 30, 2026 12:03 pm

You are always so many years ahead of most of us that's why at least I cannot understand what's all that and why. I am in the process of trying to make civic hybrid inverter work according to forum descriptions. I believe some day I also make it to the hp8 gearbox and be very thankful that Damien hacked it and made it work, all I need is to buy the controller from evbmw and it works as in the original car.

---

## Post 7 — Jack Bauer, Wed May 06, 2026 6:09 pm — **THE BREAKTHROUGH**

Once again the update none of you needed or indeed wanted: **The Pump Of Doom is Alive!!!**

Seven days of the Condor? Nope. **Nine days of the LinBus.**

### Hardware & Bus Basics

- ZF (Schaeffler) integrated electric oil pump used in the hybrid version of the 8HP automatic transmissions.
- Communicates exclusively over LIN bus at 19200 baud (LIN 2.x).
- Controller (master) sends 8-byte commands on LIN ID `0x30` every ~25 ms.
- Pump replies on three IDs: `0x32` (main status), `0x33`, `0x34` (additional status / sensor data).

### Control Strategy

**1. Coldstart Phase**
Send commands starting with `AA 00 0A 00 00 00 73 xx` (xx = alive counter 0–F).
After ~900 ms, change byte 2 from `0A` to `42` ("Phase 2").

**2. Enter Run Mode**
- Send the first command starting with `55 00 42 00 00 00 73 xx`.
- Wait for the next `0x32` response (status byte 0 = `00`).
- **From this point on, copy the exact value of byte 6 received in the last 0x32 back into byte 6 of every future 0x30 command (live echo).**
- Keep incrementing the alive counter (byte 7, 0–15).

This **live-echo of byte 6** keeps the pump's internal watchdog happy. Without it the pump quickly sends a `0x40` communication fault. *(This was the missing piece for 9 days.)*

### Signals We Can Decode Today (0x32 frame)

| Byte | Meaning | Scaling |
|---|---|---|
| 0 | Status | `00` = normal/good, `40` = communication/watchdog fault |
| 3 | Pump speed | RPM = `value × 32` |
| 4 | Supply voltage | Volts = `value × 0.1` (0–25.5 V range) |
| 6 | **Echo byte** | Must be returned in the next command |

Bytes 5 and 6 also carry raw current and temperature values (exact scaling unknown).
Frames `0x33` and `0x34` contain further sensor data, counters, and detailed error bits.

### Current Status & Limitations

- Starting and sustained running now work reliably with a **20 ms settle delay**.
- Occasional `0x40` faults still appear if timing is marginal.
- The pump is very strict about the echo byte and timing.

Next phase: decode temperature, current draw, and detailed error flags from `0x32/33/34` for safety monitoring (low-voltage cutoff, over-temp protection, etc.).

**Attachment:** `LIN_Pump_Info.pdf` (438.29 KiB)

---

## Post 8 — muehlpower, Wed May 06, 2026 6:37 pm

Bytes 0, 2, 6, and 7 of `0x30` are clear, but what do the others do? Does one of them specify the target speed or the desired pressure?

---

## Post 9 — Jack Bauer, Thu May 07, 2026 5:09 pm

I have no idea so far what if any function those bytes provide. Here is my last bench testing program. Runs on a Due with a LIN transceiver on Serial1. Decodes some useful feedback data from the pump.

**Attachments:** `pump_running.png`, `8hp_LinRunnerV4.ino` (5.43 KiB)
