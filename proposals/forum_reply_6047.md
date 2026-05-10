# Draft forum reply — openinverter.org thread #6047 ("OI 8HP TCU Project")

**Status:** draft, ready for the user to review and post. Not yet posted.

---

Hi — been working on the CAN side of this on a separate workspace. Sharing
the artifacts in case any of it's useful; happy to rework or drop pieces
that aren't.

**`iX4_Lever` — G-chassis BMW shifter for `Stm32-vcu`.**
Brute-forced the CRC8 against your iX4 captures from #7028:

```
poly = 0x1D    (same as F30_Lever)
init = 0x00, xorout = 0x04
bytes [1..7], no reflection
-> 553 / 553 captured frames validate
```

So the `F30_Lever::get_crc8` algorithm carries over to G26 with two
parameter changes. Wrote up a `Shifter` implementation that drops in
alongside F30/E65/no_Lever. 33 host-runnable assertions on
`make Test`, verified building against current upstream master.

One open question I can't resolve from captures — the four observed
gear-byte values are 0x33 (Park, confirmed by the poweroff and
idrive-buttons captures) and {0x31, 0x32, 0x35} for N/R/D in some
order. If you remember which way you twisted for which gear in the
shifter1rnd session, that resolves it; otherwise I'll wait for a
labelled clip.

**G-chassis CRC catalog.**
While I had the brute-forcer up, ran it across every BMW-E2E-looking
frame in the captures. 24 frames validated, all CRC8/0x1D, all per-ID
xorout. Notable: `0x3FD` xorout `0x70` over bytes [1..4] matches what
`F30_Lever::sendcan` already emits — so F30 TX format is unchanged on
G26. Catalog is in the repo for whoever else hits this.

**A draft DBC and codec for a TCU↔VCU CAN protocol.**
Five frames, 500 kbit/s, openinverter style — modelled on
`oi-inverter.dbc`. Pump fields are grounded in your post 7 from #7103
(RPM = byte3 × 32, V = byte4 × 0.1, the state-machine values).
Generated a C99 codec via cantools, wrote a thin C++ wrapper
(`Can_ZF8HP`) so both sides of the link consume the same generated
source. 24 host assertions. Open questions in the protocol doc — IDs,
counter/CRC, torque-handshake during shifts — none have a strong
opinion attached, just wanted concrete decisions to react to rather
than nothing.

**Test harness.**
Pytest harness that replays the full 553-frame corpus through a Python
ref decoder + LIN pump simulator + DBC encode/decode property tests.
40+ assertions. Mostly built it for my own sanity but it picks up new
captures with one line in `conftest.py`.

**Repo:** *(leander to fill in URL)*

Three things deliberately not in this — the LIN pump (your work),
factory PT-CAN integration (your call whether that's a goal), and the
TCU firmware itself (no hardware on my end). All independent of each
other; pull or ignore freely.

---

## Notes for posting

- Repo URL needs filling in once a remote exists.
- Tone is intentionally low-pressure: "here's what I built, decide
  whether it's useful." No prescriptions about timing or roadmap.
- The original draft (preserved in commit history) had two phrases —
  "before episode 04" and "before the next PCB revision locks" — that
  presumed Damien's schedule. Removed; not our place.
- Length ~450 words, scannable in 2 minutes.
- Three things deliberately omitted as per scope hygiene:
  1. The LIN aux pump beyond a citation — Damien owns that thread.
  2. PT-CAN integration speculation.
  3. Funds / Patreon asks.
