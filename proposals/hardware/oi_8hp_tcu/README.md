# OI 8HP TCU — proposed in-Mechatronik replacement TCM

Schematic spec for the replacement board that goes inside the OEM ZF
G8P75HZ Mechatronik case in place of the BMW board. STM32F103C8T6 +
two MAX22200 daisy-chained on SPI + TJA1043 CAN xcvr + TJA1027 LIN
xcvr + AP63203 buck + AP2112 LDO. External world sees only GND, +12 V,
CAN-H, CAN-L (plus LIN to the aux pump on hybrid 'boxes).

**Status: design intent, not a fab-ready PCB.** Every net is
documented; every component cited. PCB layout, footprint selection,
and bench validation are downstream work.

## Files

```
components.csv         BOM with reference designators, packages, datasheet pointers
nets.csv               authoritative net list — every (component, pin) pair
gen_netlist.py         deterministic generator
oi_8hp_tcu.net         KiCad legacy netlist (importable into Pcbnew)
SCHEMATIC.md           block diagram, power tree, pin allocation, design rationale
```

## Use in KiCad

```
KiCad → New Project (empty) → Pcbnew (PCB Editor) → File → Import → Specctra Netlist
  Choose oi_8hp_tcu.net
```

The PCB editor materialises every component with its declared package
footprint and every net as a ratsnest line. From there it's
footprint-to-symbol matching and routing work.

## Drift detection

24 host-runnable pytest assertions in
`proposals/test_harness/tests/test_oi_8hp_tcu_schematic.py`:

**Structural:**
- Every component referenced in `nets.csv` is declared in `components.csv`.
- Every component declared in `components.csv` is wired into at least one net.
- No duplicate component refs.
- The `.net` file regenerates byte-identically.
- Output is recognisable as a KiCad legacy netlist.

**OEM connector consistency:**
- Every J1 pin used in the netlist is a real pin in the OEM pinout.
- All 49 OEM connector pins are accounted for (used or NC-anchored).

**Firmware ↔ hardware drift:**
- The 9 solenoid nets connect the MAX22200 chip+channel that
  `solenoids.h::kSolenoidBinding[]` says they should, to the TCM pin
  that same firmware table says they should. If a future edit moves
  `ClutchA` from chip 0 channel 0 to chip 0 channel 5 in C++ without
  also editing this CSV, the test fails.
- Each of the 9 solenoid outputs has its flyback diode in the netlist.

**Power rails:**
- All STM32 VDD pins receive 3V3.
- All STM32 VSS pins receive GND.
- Both MAX22200 chips receive both VBAT (motor) and 5V (logic).
- Both CAN/LIN transceivers receive 5V (bus side) and 3V3 (logic side).

**STM32 pin allocation:**
- No two signal nets are assigned to the same STM32 pin.
  (This caught 3 real conflicts in the first draft — PA8/PA9 between
  CAN sleep-control and shaft-RPM timer captures, and PB10 between
  T15 wake and USART3 debug.)

`pytest tests/test_oi_8hp_tcu_schematic.py` — 24 passes in <100 ms.

## Honest scope

**What this is:** a fully cross-checked **design specification** —
every connection auditable against firmware, OEM pinout, and the
local datasheets in `archive/references/`.

**What this isn't:**
- Not a PCB layout. Layout requires the OEM Mechatronik 3D scan
  (Damien has it) and bench iteration we can't do.
- Not a finalised power tree. The buck inductor / output cap values
  follow the AP63203 reference design but assume nominal load — a
  real layout may need tighter EMC components.
- Not a connector footprint. The 49-pin OEM Mechatronik plug is
  proprietary; we model the *symbol* (pin map) not the *footprint*
  (physical pad geometry).
- Not a recreation of the BMW circuit. This replaces it.

## Cross-references

- OEM connector model — `proposals/hardware/oem_interface/`
- Solenoid binding table — `proposals/firmware/solenoid_driver/solenoids.h`
- CAN protocol — `proposals/dbc/zf8hp-tcu.dbc`
- HARA — `proposals/safety/hara.py` (T001/T002 ASIL-D rationale for
  two-chip layout)
- MAX22200 datasheet — `archive/references/MAX22200_datasheet.pdf`
- ZF 8HP gearset patent (gear ratios) — `archive/references/US7789799B2_zf8hp.pdf`
