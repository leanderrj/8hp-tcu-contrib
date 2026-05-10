# openinverter.org thread #7028 — "BMW i4 2022 CAN and LIN Logs"

Source: https://openinverter.org/forum/viewtopic.php?t=7028
Forum: OEM specific topics → BMW
Captured: 2026-05-10 (pasted by user; forum behind Anubis)

---

## Post 1 — Jack Bauer, Sat Mar 21, 2026 6:35 pm

> Can log from gear shifter going through gears and creeping. LIN log from Aircon compressor. **LIN at 19200 kbps. CAN at 500k.**
> **2022 i4 G26 Gran Coupe AWD.**

**Attachments:**
- `ix4_shiftpoweroff.csv` (505 KiB) — shifter use during power-off
- `ix4_shifteridrivebuttons.csv` (2.68 MiB) — iDrive buttons during shifter use
- `ix4_shifter2rndbuttons.csv` (5.25 MiB) — second rotation + buttons
- `ix4_shifter1rnd.csv` (11.32 MiB) — first rotation through gears
- `bmw_ix4_ac_lin1.txt` (104 KiB) — LIN log from A/C compressor
- 4 photos

All five attachments are now in `archive/captures/`.

## Post 2 — EdAtki, Wed Apr 01, 2026 6:41 pm

> I've picked up one of these AC compressors and will see if I can get it running with these logs.
> Part number 5B31E59, but many interchangeable iterations exist:
> https://www.realoem.com/bmw/enUS/partxref?q=5B31E59
> The i4 is either 400 V nominal (BMW) or 430 V nominal (Wikipedia) — either way suitable for 108S projects.

---

## Relevance to the 8HP TCU project

- **CAN at 500 kbps** ✓ matches the bus rate we picked for the TCU↔VCU protocol.
- **LIN at 19200 baud** ✓ same as the aux 12 V gearbox pump (different device, same physical layer / framing).
- The shifter CAN frames give us the modern BMW G-chassis "iDrive rotary gear selector" vocabulary, which we can implement as a new `iX4_Lever.cpp` (or similar) in `Stm32-vcu` alongside the existing `F30_Lever`/`E65_Lever`. This is a clean **platform-fill-the-gaps** contribution that's independent of the 8HP TCU work but uses the same `Shifter` abstraction.
- The A/C compressor LIN log is unrelated to the gearbox pump but useful as a **second LIN protocol example** when validating our LIN driver.
