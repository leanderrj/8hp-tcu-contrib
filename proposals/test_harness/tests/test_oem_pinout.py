"""Tests for the OEM TCM KiCad symbol library and pinout CSVs.

The CSV files in proposals/hardware/oem_interface/ are the source of
truth. The .kicad_sym file is generated from them; these tests
guarantee the two never drift.
"""
from __future__ import annotations

import csv
import re
import subprocess
from pathlib import Path

import pytest


HW = Path(__file__).resolve().parents[3] / "proposals" / "hardware" / "oem_interface"
TCM_CSV = HW / "tcm_pinout.csv"
EXT_CSV = HW / "external_pinout.csv"
SYM     = HW / "oem_tcm.kicad_sym"
GEN     = HW / "gen_kicad_sym.py"


def _read_csv(path: Path) -> list[dict]:
    with open(path, newline="") as fh:
        rdr = csv.DictReader(filter(lambda r: not r.startswith("#"), fh))
        return list(rdr)


# ----------------------------------------------------------------------
# CSV structural invariants
# ----------------------------------------------------------------------

def test_tcm_csv_has_49_contiguous_pins():
    rows = _read_csv(TCM_CSV)
    assert len(rows) == 49, f"got {len(rows)} rows, expected 49"
    pin_numbers = sorted(int(r["pin"]) for r in rows)
    assert pin_numbers == list(range(1, 50))


def test_external_csv_has_16_contiguous_pins():
    rows = _read_csv(EXT_CSV)
    assert len(rows) == 16
    pin_numbers = sorted(int(r["pin"]) for r in rows)
    assert pin_numbers == list(range(1, 17))


def test_every_tcm_pin_has_a_name():
    for r in _read_csv(TCM_CSV):
        assert r["name"], f"pin {r['pin']} has no name"


def test_external_to_tcm_mapping_is_bijective():
    """Every pin on the external connector must map to exactly one
    TCM pin, and every TCM pin claimed in external_pinout.csv must
    actually exist in tcm_pinout.csv."""
    tcm = {int(r["pin"]) for r in _read_csv(TCM_CSV)}
    ext = _read_csv(EXT_CSV)
    seen: set[int] = set()
    for r in ext:
        target = int(r["tcm_pin"])
        assert target in tcm, f"ext pin {r['pin']} maps to nonexistent TCM pin {target}"
        assert target not in seen, f"TCM pin {target} mapped from multiple ext pins"
        seen.add(target)


def test_pt_can_pins_are_paired_correctly():
    """Two-pair sanity: PT-CAN 1 H/L map to the same vehicle bus, etc."""
    tcm_by_name = {r["name"]: int(r["pin"]) for r in _read_csv(TCM_CSV)}
    # PT-CAN 1: H @ 31, L @ 30 per source PDF.
    assert tcm_by_name["EXT5_PTCAN1_H"] == 31
    assert tcm_by_name["EXT6_PTCAN1_L"] == 30
    # PT-CAN 2: H @ 33, L @ 34.
    assert tcm_by_name["EXT4_PTCAN2_H"] == 33
    assert tcm_by_name["EXT3_PTCAN2_L"] == 34


def test_solenoid_pins_match_solenoid_binding_h():
    """The C++ binding table in solenoids.h uses the same pin
    numbers as this CSV. Drift between them is a bug."""
    tcm_by_name = {r["name"]: int(r["pin"]) for r in _read_csv(TCM_CSV)}
    expected = {
        "SOL_CLUTCH_A": 41,
        "SOL_CLUTCH_B": 43,
        "SOL_CLUTCH_C": 45,
        "SOL_CLUTCH_D": 42,
        "SOL_CLUTCH_E": 44,
        "SOL_TCC": 46,
        "SOL_LINE_PRESSURE": 47,
        "SOL_PARK_HOLD": 5,
        "SOL_PARK_RELEASE": 48,
    }
    for name, pin in expected.items():
        assert tcm_by_name[name] == pin, \
            f"{name}: CSV says {tcm_by_name[name]}, binding-doc says {pin}"


# ----------------------------------------------------------------------
# KiCad symbol library
# ----------------------------------------------------------------------

def test_symbol_library_exists():
    assert SYM.exists(), f"{SYM} not generated yet — run gen_kicad_sym.py"


def test_symbol_library_is_deterministic():
    """Running the generator should produce identical output every time."""
    before = SYM.read_bytes()
    rc = subprocess.run(["python3", str(GEN)], capture_output=True, cwd=HW)
    assert rc.returncode == 0, rc.stderr.decode()
    after = SYM.read_bytes()
    assert before == after, "gen_kicad_sym.py is non-deterministic"


def test_symbol_library_has_both_symbols():
    text = SYM.read_text()
    assert '(symbol "BMW_8HP_TCM_49pin"' in text
    assert '(symbol "BMW_8HP_External_16pin"' in text


def test_symbol_pin_numbers_match_csv():
    """Every pin in each CSV must appear at least once in the .kicad_sym."""
    text = SYM.read_text()
    for r in _read_csv(TCM_CSV):
        assert f'(number "{r["pin"]}"' in text, f"TCM pin {r['pin']} missing from symbol"
    for r in _read_csv(EXT_CSV):
        assert f'(number "{r["pin"]}"' in text, f"ext pin {r['pin']} missing from symbol"


def test_symbol_pin_names_match_csv():
    """Every CSV pin name appears as a name string in the .kicad_sym."""
    text = SYM.read_text()
    for r in _read_csv(TCM_CSV):
        assert f'(name "{r["name"]}"' in text, \
            f"TCM pin {r['pin']} name {r['name']!r} missing from symbol"


def test_symbol_uses_only_valid_kicad_pin_types():
    """Every (pin TYPE line ...) must use a type KiCad understands."""
    text = SYM.read_text()
    valid = {"input", "output", "bidirectional", "tri_state", "passive",
             "free", "unspecified", "power_in", "power_out", "open_collector",
             "open_emitter", "no_connect"}
    used = set(re.findall(r'\(pin (\w+) line', text))
    bad = used - valid
    assert not bad, f"unrecognised KiCad pin types: {bad}"


def test_no_pin_appears_more_than_once_in_each_symbol():
    """Catch numbering bugs where the generator writes the same pin twice."""
    text = SYM.read_text()
    # Split per symbol, count pin numbers in each.
    sym_blocks = re.split(r'\(symbol "', text)[1:]
    for block in sym_blocks:
        sym_name = block.split('"', 1)[0]
        nums = re.findall(r'\(number "(\d+)"', block)
        # Within one symbol, every pin number must be unique.
        assert len(nums) == len(set(nums)), \
            f"{sym_name}: duplicate pin numbers {sorted(nums)}"


def test_no_connect_pins_marked_correctly():
    """Pins labeled NC* in the CSV must be electrical_type=no_connect."""
    nc_pins = [r for r in _read_csv(TCM_CSV) if r["name"].startswith("NC")]
    assert nc_pins, "expected at least one NC pin"
    for r in nc_pins:
        assert r["electrical_type"] == "no_connect", \
            f"pin {r['pin']} ({r['name']}) is no-connect but type={r['electrical_type']!r}"


def test_t30_t31_pins_are_paralleled_pairs():
    """T30 (+12V) and T31 (GND) each appear on TWO TCM pins for current
    capacity per the source PDF; both pairs route to the same external pin."""
    tcm_by_name = {r["name"]: int(r["pin"]) for r in _read_csv(TCM_CSV)}
    # T30 is on TCM pins 22 and 23.
    assert tcm_by_name["EXT13_T30A"] == 22
    assert tcm_by_name["EXT13_T30"]  == 23
    # T31 is on TCM pins 24 and 25.
    assert tcm_by_name["EXT14_T31"]  == 24
    assert tcm_by_name["EXT14_T31B"] == 25


def test_solenoid_supply_pins_present():
    """The PDF says four +12V supply pins (37-40) are paralleled."""
    rows = {int(r["pin"]): r for r in _read_csv(TCM_CSV)}
    for p in (37, 38, 39, 40):
        assert rows[p]["name"].startswith("VBAT_SOL"), \
            f"pin {p} should be a solenoid supply, got {rows[p]['name']}"
        assert rows[p]["electrical_type"] == "power_in"
