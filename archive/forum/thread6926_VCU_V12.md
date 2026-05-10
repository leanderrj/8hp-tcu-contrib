# openinverter.org thread #6926 — "ZombieVerter VCU V1.2"

Source: https://openinverter.org/forum/viewtopic.php?t=6926
Forum: Vehicle Control (VCU) → ZombieVerter VCU
Captured: 2026-05-10 (pasted by user; forum behind Anubis)

Relevance: this is the VCU the 8HP TCU will talk to. New hardware capabilities (4 CAN channels, sleep/wake, ESP32) shape what's possible on our side. Firmware does **not** yet support the new HW features — open contribution surface.

---

## Post 1 — Jack Bauer, Sun Feb 01, 2026 — V1.2 announcement

V1.1 stays supported and pin-compatible (except RS232). Highlights of V1.2:

- **Sleep mode** with main 5 V supply shutdown by STM32; wake via T15, HVReq, or CAN1.
- **All IO** has TVS protection. Main 12 V also has Gas Discharge Arrestor. Supply outputs poly-fused.
- **CAN1 transceiver → TJA1043T** for wake-on-CAN.
- **DigiPots → constant-current driver**, emulating ~50–400 Ω to ground (analog fuel/temp gauges).
- **DAC amp → TCA0372**, gain 4×, 0–12 V at up to 1 A/channel.
- **Onboard KXTJ3-1057 3-axis accelerometer.**
- **Onboard NTC temp sensor.**
- **CAN-FD via MCP251863T → 4 CAN channels total.**
- **Real-time clock** (CR1220 backup, runs in sleep).
- ESD protection on all CAN/LIN.
- Hardware-revision detect resistor (firmware can distinguish V1.1 / V1.2).
- KiCad 9; 6-layer with dedicated 3V3 layer.
- Removed: RS232.

**Attachment:** `Zom_V1_2.pdf` (1.38 MiB) — schematic.

## Posts 2–6 — early reactions, prototype boards ordered, in production.

## Post 7 — modellfan, Tue Feb 10, 2026

Asks about the gas-discharge arrestor (unusual for automotive ECU PSU), why 4 different CAN transceivers instead of two pairs, suggests V1.2 should also kick off "very special functions e.g. for450 transmission".

## Post 8 — tom91, Wed Feb 11, 2026 — **NO** to scope creep on the GS450H stuff; cites Damien's pin-compatibility constraint.

## Posts 9–11 — gentle scope-creep argument; Damien defends pin-compat.

## Post 14 — danjulio, Fri Feb 13, 2026 — **TJA1043 wake question**

Detailed read of the schematic — questions whether `CAN1_WAKE_OUT` will work as wired given the TJA1043 INH behaviour:
- Standby (EN=0, STBN=0): INH = High (VBAT)
- Sleep (EN=1, STBN=0): INH = Low (GND)

Asks whether the chip will actually enter Sleep vs Standby, and whether wake on a single CAN packet (e.g. Leaf OBC `0x679`) is feasible (ISO 11898-2 wake usually wants two packets).

## Post 15 — marcexec — redirects Leaf-specific question to Nissan forum.

## Post 16 — danjulio rephrases: what's the intended use of the wake feature?

## Post 17 — modellfan, Sat Feb 21, 2026 — feature wishlist

> - Why not take over FOCCCI power module? It not only allows to be woken up on Ignition but also wake others up on the same line
> - Add an EEPROM? I would really like to implement freeze frames into ZombieVerter universe. This would make debugging of rare problems so much easier

## Posts 18–19 — Jack Bauer, Thu Feb 26 / Fri Feb 27 2026

> Prototype V1.2 boards arrived. Initial tests in the Red Arrow are looking good. Core functions working as well as basic wakeup.

> Zom 1.2 will now be shipping for all orders.

## Post 21 — Jack Bauer, Sat Mar 07, 2026 — **ESP32 swap**

> ESP8266 wifi modules are proving no longer capable of dealing with the amount of data (JSON) going to and from zombie. Drop-in ESP32 version of the Wemos module: https://www.aliexpress.com/item/1005006026692511.html

## Posts 22–24 — marcexec sends Damien a spare; Damien validates.

## Post 25 — tom91, Fri Mar 13, 2026 — ESP32 web flashing instructions.

## Post 27 — wimboone, Sun Mar 29, 2026 — **firmware hasn't caught up to V1.2**

> Got the new V2 revision. Was using the digipots on hardware rev1 for driving the fuel level signals on BMW E90 — worked great but doesn't work on the new V2 board. The firmware does not yet include the changes.

## Post 28 — Jack Bauer

> The firmware does not yet support the new features. There are only a few of us working on this project and those that are have other commitments.

## Posts 29–32 — wimboone reverse-engineers V1.2 digipot

The new constant-current driver needs SPI commands of `(channel_byte, value_byte)`:

```cpp
// channel 0
spi_xfer(SPI3, 0x00);
spi_xfer(SPI3, Param::GetInt(Param::DigiPot1Step));
// channel 1
spi_xfer(SPI3, 0x10);
spi_xfer(SPI3, Param::GetInt(Param::DigiPot2Step));
```

Calibration on E90: 130 = 100 %, 190 = 75 %, 222 = 50 %, 252 = 25 %. Non-linear, doesn't reach 0 %.

## Post 33 — Jack Bauer, Wed Apr 29, 2026 — **V1.3 design released**

> V1.3 design now available on Github : https://github.com/damienmaguire/Stm32-vcu/tree/master/Hardware/Zombie

Full KiCad 9 source on Patreon at €10 level (personal use only).

## Post 36 — wimboone, Sat May 09, 2026 — **fix for fuel gauge range on V1.2/1.3**

To get full BMW E90 fuel-gauge range, swap **R87 / R88** (V1.2) — `R17` / `R19` in V1.3 — from 966 Ω to 100 Ω.

```c
static const int fuelGaugeMap[8][2] = {
    {   0, 255 },
    {   2, 255 },
    {   5, 250 },
    {  10, 245 },
    {  25, 227 },
    {  50, 194 },
    {  75, 158 },
    { 100,  95 },
};
```

## Posts 37–39 — JLCPCB build issue (TDK ACM2012H-900-2P-T03 inductor stock), resolved.
