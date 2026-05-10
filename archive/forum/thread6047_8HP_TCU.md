# openinverter.org thread #6047 — "OI 8HP TCU Project"

Source: https://openinverter.org/forum/viewtopic.php?t=6047
Forum: OEM specific topics → BMW
Captured: 2026-05-10 (pasted by user; forum behind Anubis)

This is **the main project thread**. Started Jan 2025; the active reverse-engineering work in thread #7103 ("Pump Of Doom") is a sub-tree of this.

---

## Post 1 — Jack Bauer, Sun Jan 19, 2025 10:10 am — *project kickoff*

Github repo set up: https://github.com/damienmaguire/8HP-TCU/tree/main

> Primary goal is to control the valve block in the GA8P75HZ gearbox for EV conversions. Should work also with traditional ICE 8HP setups.

Test vehicle originally a '97 E39, now considering a 2008 E92.

## Post 2 — mengu190, Mon May 26, 2025 — "any progress?"
## Post 3 — Jack Bauer, Wed May 28, 2025 — "Little busy :)"

## Post 4 — kyle, Thu Oct 30, 2025

Asks about ICE compatibility — notes the board has no TPS / MAP inputs, no shift up/down outputs, no speed input.

## Post 5 — Neomaximus55, Fri Nov 14, 2025

Wants to use the controller on a Toyota AA80E automatic. Offered to test/solder/assemble.

## Post 6 — Brody, Mon Jan 05, 2026

> The git repo only has the kicad files for the adapter and not the tcu pcb, does anyone have these or know where I could find them

*(The Software/ folder was still a placeholder at this time and the in-Mechatronik board didn't exist yet.)*

## Post 7 — Jack Bauer, Mon Apr 20, 2026 — **redesign + adapter plate**

> Re the TCU I am in the midst of a **redesign as the first version did not have closed loop current control of the solenoids which is a requirement**. Currently looking at the **MAX22200** IC for this purpose.

> Also did a **3D scan of the bellhousing** and cut out a basic adapter plate.

Got the matching inverter at a reasonable price with plugs still attached, has DC-DC built in, will get an OI board.

**Attachments:** `20260420_144611.jpg`, `20260418_130300.jpg`, `20260418_125726.jpg`

## Post 8 — P.S.Mangelsdorf, Mon Apr 20, 2026 — **cross-platform reference**

> I think, but don't know, that this is or is highly related to, the transmission used in the **Jeep Wrangler 4xe** here in the States. Having an OI solution for it would be awesome.

References Nivlac57 YouTube videos, **TurboLamik** bypass option, and **MaxxECU** aftermarket controller (which uses different firmware allowing more control). MaxxECU has technical documentation and a YouTube video on flashing the TCU using a Chinese tool. Speculates a new firmware could be created.

## Post 9 — Jack Bauer, Tue Apr 21, 2026 — "Messy work bench today"

**Attachment:** `messy_bench.jpg`

## Post 10 — jrbe, Wed Apr 22, 2026 — **why this matters**

> 200 kW (250 hp) is what some of the hybrid variant electric motors are rated to but couple that with 8 speeds. For reference, the gs450h is rated to 147 kW and has 2 speeds.

> The 8HP was designed with fuel economy in mind … also designed to target dual clutch transmission shift speed of **0.2 seconds**, it's not a slushbox.

> https://en.wikipedia.org/wiki/ZF_8HP_transmission

> This specific reverse engineering is targeting the BMW hybrid transmission but the controls will likely cross over to other variants as well.

Calls for community support via Patreon (https://www.patreon.com/evbmw) and likes.

## Post 11 — P.S.Mangelsdorf, Wed Apr 22, 2026 — **cross-platform confirmed**

Confirms Jeep Wrangler 4xe PHEV and Grand Cherokee 4xe PHEV use what is essentially the same transmission, Stellantis code **8P75HP**. Recently traded a Challenger (8HP ICE variant) and regrets not getting CAN logs; might know someone with a 4xe to log.

## Post 12 — Jack Bauer, Thu Apr 23, 2026 — **first LIN findings (predates thread #7103)**

> Got the aux 12 V oil pump, valve body and TCM removed. Got to work on the pump. Naturally no info available. Discovered the following:
> - Uses LIN V2 at 19200 baud
> - Responds to ids 0x32, 0x33 and 0x34
> - Command id is 0x30. byte 7 is a counter from 0x00 to 0x0f.

> So far I have not had the pump run but managed to trick the OEM TCM into communicating with the pump via an OBD adapter.

**Attachments:** 6 photos of valve body / pump teardown.

## Post 13 — 007007, Mon Apr 27, 2026

Asks: own TCU or just CAN-talk to OEM ZF controller? References MaxxECU and CanTCU "use the ZF Controller and give them the right CAN telegrams" approach.

## Post 14 — P.S.Mangelsdorf, Fri May 01, 2026 — **transmission internals reference**

Shares Prof. Kelly (Weber State) YouTube video on the Jeep variant.

> Beyond the electric motor, it's just a normal 8HP, and … the one difference is an extra solenoid to turn on the engine input clutch (which would mean there should be no need to lock any input shaft, or even block it off, so long as that clutch isn't applied)

## Post 15 — Jack Bauer, Sat May 02, 2026

Points to the LIN sub-thread: https://openinverter.org/forum/viewtopic.php?t=7103

## Post 16/17 — Jack Bauer, Sun May 03, 2026 — *(empty posts, likely video links)*

## Post 18 — muehlpower, Sun May 03, 2026

> My transmission doesn't have an oil pump or a hybrid drive system. All that's left is controlling the valves and reading the two speed sensors. On GitHub, I see a controller in an external housing. It looks like there are MOSFETs for the valves in there. The small board probably replaces the control unit in the oil pan. Is there a video showing this replacement?

## Post 19 — Jack Bauer, Sun May 03, 2026 — *(empty)*
## Post 20 — Jack Bauer, Sun May 03, 2026 4:33 pm

> I don't have the design for the tcu and replacement pcb finalised as yet so please bear with me.

## Post 21 — LaurelSGX, Mon May 04, 2026

> Has anyone found information on maximum input torque rating of the K0 clutch?

*(Unanswered.)*

## Post 22 — Jack Bauer, Thu May 07, 2026 — **architecture decision (matches video)**

> So in terms of the 8hp tcm am thinking of going a different way. My original plan was to put the jumper PCB in place of the OEM TCM as the folks running external controllers but now I'm thinking **why not design the OI TCM to fit on the jumper board and put it in the OEM TCM case. Control via CAN from zom or whatever.**

> If you wanted to it could even run stand alone with a CAN shifter.

## Post 23 — Jack Bauer, Sun May 10, 2026 7:58 am — *(empty / video?)*

## Post 24 — Jack Bauer, Sun May 10, 2026 10:02 am — **TCM PINOUT PDF — CRITICAL**

> Pinout of the TCM to solenoids, sensors and external connector.

**Attachment:** `TCM_Pinout.pdf` (555.45 KiB)

This document is required for our work. **TODO:** download manually in browser (forum needs Anubis pass) and place at `archive/forum/TCM_Pinout.pdf`.
