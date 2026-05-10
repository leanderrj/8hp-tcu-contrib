# OEM 8HP Mechatronik connector model

KiCad symbols + machine-checked CSV pinout for the BMW ZF G8P75HZ
Mechatronik's two connectors. This is the foundation any replacement
PCB design starts from — ours, Damien's, anyone else's.

## Files

| File | What |
|---|---|
| `tcm_pinout.csv` | 49-pin internal connector — single source of truth |
| `external_pinout.csv` | 16-pin OEM external connector (vehicle harness side) |
| `gen_kicad_sym.py` | reads CSVs, emits `oem_tcm.kicad_sym` |
| `oem_tcm.kicad_sym` | KiCad 7+ symbol library (importable) |

The two CSVs are the authoritative description. The `.kicad_sym` is
generated from them deterministically — `gen_kicad_sym.py` writes the
same bytes every time.

## Source

Damien Maguire's `TCM_Pinout.pdf` posted to openinverter forum thread
#6047 on 2026-05-10. Archived locally at `archive/forum/TCM_Pinout.pdf`.

Cross-referenced with `proposals/tcm_max22200_binding/PINOUT.md` for
function decoding.

## Use in KiCad

```
KiCad → Preferences → Manage Symbol Libraries → Add
  Nickname: OEM_8HP
  Library Path: ${KIPRJMOD}/oem_interface/oem_tcm.kicad_sym
```

Then in the schematic editor, pick `BMW_8HP_TCM_49pin` or
`BMW_8HP_External_16pin` from the OEM_8HP library.

## Regenerating

```
python3 gen_kicad_sym.py
```

Idempotent. If the output ever changes without a corresponding CSV
edit, that's a bug — the test suite catches it
(`test_symbol_library_is_deterministic`).

## Verifying

16 host-runnable pytest assertions in
`proposals/test_harness/tests/test_oem_pinout.py`:

- 49 contiguous pins on the internal connector, 16 on the external
- Every pin has a name and a valid KiCad electrical type
- External-pin → TCM-pin mapping is bijective
- PT-CAN pin pairs are wired consistently with each other
- The nine solenoid pins match the binding table in `solenoids.h`
- All NC pins are typed `no_connect`
- T30 / T31 paralleled-pair pins (22+23, 24+25) are exactly two each
- The four solenoid +12 V supply pins (37-40) are all `VBAT_SOL_*`
- Every pin number from each CSV appears exactly once in the symbol
- No pin number appears twice in the same symbol
- The generator output is byte-identical across runs (determinism)

`pytest tests/test_oem_pinout.py` — passes in <100 ms.

## What this enables

- **Schematic design** for any replacement TCU (ours, Damien's, etc.)
  starts by placing this symbol; every connection is documented.
- **Drift detection** — if the firmware's `kSolenoidBinding[]` and the
  hardware's pin assignments disagree, a test fails.
- **Bench-test wiring** — the CSV is also a wiring chart; printing it
  out gives you a known reference for probing the harness.

## What this does NOT include

- **Footprints / mechanical model.** The KiCad symbol is for schematic
  capture only. The physical connector — Tyco / Molex part number,
  pin pitch, latch shape — is OEM-specific and would need to be
  measured from a real harness or sourced from a Mechatronik service
  document.
- **The OEM TCM circuit.** This is a connector model, not a recreation
  of the BMW board's contents.
- **PCB layout.** Any layout of a replacement board needs to be done
  with the OEM Mechatronik case 3D scan in hand (Damien has it).

## Provenance

Where each pin assignment came from:

| TCM pins | Source |
|---|---|
| 1, 3, 4, 8-11, 18, 49 | Unassigned in source PDF — typed `no_connect` |
| 2 | LIN aux pump (forum #7103, archive/forum/thread7103.md) |
| 5, 41-48 | Solenoid drive lines (TCM_Pinout.pdf) |
| 6, 7 | Oil temperature thermistor pair (TCM_Pinout.pdf) |
| 12-14 | Park-position switch + ground (TCM_Pinout.pdf) |
| 15-17 | Shaft speed sensors (TCM_Pinout.pdf) |
| 19-36 | External-connector routing (TCM_Pinout.pdf) |
| 37-40 | +12 V solenoid supply, paralleled (TCM_Pinout.pdf) |
| External 1-16 | Same source, decoded into `external_pinout.csv` |
