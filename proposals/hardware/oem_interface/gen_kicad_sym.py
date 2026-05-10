#!/usr/bin/env python3
"""Generate a KiCad 7+ symbol library from the OEM TCM pinout CSVs.

Reads:
    tcm_pinout.csv          49-pin internal connector
    external_pinout.csv     16-pin OEM external connector

Writes:
    oem_tcm.kicad_sym       symbol library importable into KiCad 7+

The output is deterministic: same inputs → byte-identical .kicad_sym.
That property is asserted by tests/test_oem_pinout.py so any drift
between the CSVs and the symbol file fails CI.

Run from this directory:
    python3 gen_kicad_sym.py

Mapping CSV electrical_type → KiCad pin electrical type:
    power_in       -> power_in
    power_out      -> power_out
    passive        -> passive
    input          -> input
    output         -> output
    bidirectional  -> bidirectional
    no_connect     -> no_connect

Reference: KiCad 7 file format, "Symbol Library File Format"
https://dev-docs.kicad.org/en/file-formats/sexpr-symbol-lib/
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path
from textwrap import indent


HERE = Path(__file__).resolve().parent

# --- KiCad pin-type and orientation helpers ----------------------------------

# Orientation in tenths of a degree per the KiCad spec; we use angle 0 for
# pins on the LEFT side (drawn pointing right into the body) and angle 180
# for pins on the RIGHT side. A non-trivial connector benefits from
# splitting pins into two columns; the OEM TCM has 49 pins, which is
# clearer in two columns of ~25 each.

PIN_PITCH = 2.54        # 100 mil grid
PIN_LENGTH = 2.54       # standard 100 mil pin length


def pin_block(number: int, name: str, etype: str, x: float, y: float,
               angle: int) -> str:
    """One (pin ...) S-expression."""
    name_clean = name.replace("\n", " ").strip()
    return (
        f'    (pin {etype} line\n'
        f'      (at {x:g} {y:g} {angle})\n'
        f'      (length {PIN_LENGTH})\n'
        f'      (name "{name_clean}" (effects (font (size 1.27 1.27))))\n'
        f'      (number "{number}" (effects (font (size 1.27 1.27))))\n'
        f'    )'
    )


def symbol(name: str,
            description: str,
            pins: list[tuple[int, str, str]]) -> str:
    """Build one (symbol ...) S-expression for a connector with `pins`
    arranged as a left/right two-column connector. Each tuple is
    (pin_number, pin_name, electrical_type)."""
    n = len(pins)
    half = (n + 1) // 2
    left = pins[:half]
    right = pins[half:]

    # Coordinates: rows centred, body width sized to fit the longest name
    body_left = -10.16
    body_right = 10.16
    body_top = (half + 1) * PIN_PITCH
    body_bottom = -PIN_PITCH

    pin_blocks: list[str] = []
    # Left column: pins point left (angle 0 means pin at -X grows left).
    # KiCad convention: angle = direction the pin extends OUT. For a pin
    # on the LEFT side of a body, the pin comes from outside and points
    # right; orientation 0 means "extends to the right". So a left-side
    # pin gets angle 180 (extends left). That's the opposite of what most
    # diagrams suggest; verify by experiment if confused.
    for i, (num, pname, etype) in enumerate(left):
        y = body_top - PIN_PITCH * (i + 1)
        pin_blocks.append(pin_block(num, pname, etype,
                                      body_left - PIN_LENGTH, y, 0))
    for i, (num, pname, etype) in enumerate(right):
        y = body_top - PIN_PITCH * (i + 1)
        pin_blocks.append(pin_block(num, pname, etype,
                                      body_right + PIN_LENGTH, y, 180))

    rect = (
        f'    (rectangle\n'
        f'      (start {body_left:g} {body_top:g})\n'
        f'      (end {body_right:g} {body_bottom:g})\n'
        f'      (stroke (width 0.254) (type default))\n'
        f'      (fill (type background))\n'
        f'    )'
    )

    pins_text = "\n".join(pin_blocks)

    return (
        f'  (symbol "{name}"\n'
        f'    (pin_numbers hide)\n'
        f'    (pin_names (offset 0.508))\n'
        f'    (in_bom yes) (on_board yes)\n'
        f'    (property "Reference" "J" (id 0)\n'
        f'      (at 0 {body_top + 2:g} 0)\n'
        f'      (effects (font (size 1.27 1.27)))\n'
        f'    )\n'
        f'    (property "Value" "{name}" (id 1)\n'
        f'      (at 0 {body_bottom - 2:g} 0)\n'
        f'      (effects (font (size 1.27 1.27)))\n'
        f'    )\n'
        f'    (property "Footprint" "" (id 2)\n'
        f'      (at 0 0 0)\n'
        f'      (effects (font (size 1.27 1.27)) hide)\n'
        f'    )\n'
        f'    (property "Datasheet" "" (id 3)\n'
        f'      (at 0 0 0)\n'
        f'      (effects (font (size 1.27 1.27)) hide)\n'
        f'    )\n'
        f'    (property "Description" "{description}" (id 4)\n'
        f'      (at 0 0 0)\n'
        f'      (effects (font (size 1.27 1.27)) hide)\n'
        f'    )\n'
        f'{rect}\n'
        f'{pins_text}\n'
        f'  )'
    )


def load_csv(path: Path) -> list[tuple[int, str, str]]:
    """Yield (pin_number, name, electrical_type) tuples from one of our pinout CSVs."""
    out: list[tuple[int, str, str]] = []
    with open(path, newline="") as fh:
        reader = csv.DictReader(filter(lambda r: not r.startswith("#"), fh))
        for row in reader:
            out.append((int(row["pin"]), row["name"], row["electrical_type"]))
    out.sort(key=lambda r: r[0])
    return out


def main() -> int:
    tcm = load_csv(HERE / "tcm_pinout.csv")
    ext = load_csv(HERE / "external_pinout.csv")

    if [r[0] for r in tcm] != list(range(1, 50)):
        print(f"tcm_pinout.csv is not a contiguous 1..49 range:"
              f" {[r[0] for r in tcm]}", file=sys.stderr)
        return 2
    if [r[0] for r in ext] != list(range(1, 17)):
        print(f"external_pinout.csv is not a contiguous 1..16 range:"
              f" {[r[0] for r in ext]}", file=sys.stderr)
        return 2

    # Header — KiCad 7 / 8 / 9 all accept (version 20211014).
    parts = [
        '(kicad_symbol_lib (version 20211014) (generator "8hp_tcu_contrib")',
        symbol(
            "BMW_8HP_TCM_49pin",
            "ZF G8P75HZ Mechatronik internal connector (49-pin). "
            "Source: TCM_Pinout.pdf, openinverter forum #6047 post 2026-05-10.",
            tcm,
        ),
        symbol(
            "BMW_8HP_External_16pin",
            "ZF G8P75HZ OEM external connector (16-pin). "
            "Vehicle harness side; carries T30 / T31 / T15 / 2 PT-CAN buses.",
            ext,
        ),
        ")",
    ]

    out = "\n".join(parts) + "\n"
    (HERE / "oem_tcm.kicad_sym").write_text(out)
    print(f"wrote {HERE / 'oem_tcm.kicad_sym'} "
          f"({len(out)} bytes, {len(tcm)+len(ext)} pins)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
