"""Drift detection between the OI 8HP TCU schematic and the rest of the stack.

The CSVs in proposals/hardware/oi_8hp_tcu/ are the authoritative
electrical design. These tests check that:

  1. Every component referenced in nets.csv exists in components.csv.
  2. Every J1 (OEM connector) pin used in the schematic is a real pin
     in the OEM connector model (oem_interface/tcm_pinout.csv).
  3. The nine solenoid output nets connect the MAX22200 chip+channel
     specified in solenoids.h's kSolenoidBinding[] to the TCM pin
     specified in the same binding.
  4. Power rails connect to where they should (3V3 to STM32 VDD, etc.).
  5. The .net file regenerates byte-identically.
"""
from __future__ import annotations

import csv
import re
import subprocess
from collections import defaultdict
from pathlib import Path

import pytest


HW   = Path(__file__).resolve().parents[3] / "proposals" / "hardware"
TCU  = HW / "oi_8hp_tcu"
OEM  = HW / "oem_interface"
NETS = TCU / "nets.csv"
COMPS = TCU / "components.csv"
NETLIST = TCU / "oi_8hp_tcu.net"
GEN  = TCU / "gen_netlist.py"


def _read(path: Path) -> list[dict]:
    with open(path, newline="") as fh:
        return list(csv.DictReader(filter(lambda r: not r.startswith("#"), fh)))


# ----------------------------------------------------------------------
# Structural invariants
# ----------------------------------------------------------------------

def test_every_component_in_nets_is_declared():
    comps = {c["ref"] for c in _read(COMPS) if c.get("ref")}
    rows = _read(NETS)
    used = {r["component"] for r in rows
            if r["component"] and r["component"] != "—"}
    missing = used - comps
    assert not missing, f"nets.csv references undeclared components: {missing}"


def test_every_declared_component_has_at_least_one_net():
    """Catches a component listed in components.csv but never wired up
    to anything — almost always an oversight."""
    comps = [c["ref"] for c in _read(COMPS) if c.get("ref")]
    rows = _read(NETS)
    used = {r["component"] for r in rows if r["component"]}
    unused = [c for c in comps if c not in used]
    assert not unused, f"components.csv has dangling refs: {unused}"


def test_no_duplicate_component_refs():
    refs = [c["ref"] for c in _read(COMPS) if c.get("ref")]
    assert len(refs) == len(set(refs)), \
        f"duplicate component refs: {[r for r in refs if refs.count(r) > 1]}"


# ----------------------------------------------------------------------
# OEM connector consistency
# ----------------------------------------------------------------------

def test_every_j1_pin_used_is_a_real_oem_pin():
    """J1 is the OEM 49-pin Mechatronik connector. Any pin number
    we use must exist in the OEM pinout source-of-truth."""
    oem_pins = {int(r["pin"]) for r in _read(OEM / "tcm_pinout.csv")}
    j1_used = {int(r["pin"]) for r in _read(NETS)
               if r["component"] == "J1" and r["pin"].strip().isdigit()}
    bad = j1_used - oem_pins
    assert not bad, f"nets.csv uses J1 pins not in OEM pinout: {bad}"


def test_every_oem_pin_appears_at_least_once_in_j1_netlist():
    """The 49-pin connector must have all 49 pins accounted for in the
    netlist — even if just as no-connect placeholders. Otherwise the
    PCB editor won't know about half the connector body."""
    oem_pins = {int(r["pin"]) for r in _read(OEM / "tcm_pinout.csv")}
    j1_used = {int(r["pin"]) for r in _read(NETS)
               if r["component"] == "J1" and r["pin"].strip().isdigit()}
    missing = oem_pins - j1_used
    assert not missing, \
        f"J1 pins missing from netlist (use NC_TCM_<n> nets): {sorted(missing)}"


# ----------------------------------------------------------------------
# Firmware solenoid binding consistency (the key drift detector)
# ----------------------------------------------------------------------

# Mirror of kSolenoidBinding from proposals/firmware/solenoid_driver/solenoids.h
EXPECTED_SOLENOID_BINDING = {
    # net_name           (chip_index, channel_index, tcm_pin)
    "SOL_CLUTCH_A":      (0, 0, 41),
    "SOL_CLUTCH_B":      (0, 1, 43),
    "SOL_CLUTCH_C":      (0, 2, 45),
    "SOL_CLUTCH_D":      (0, 3, 42),
    "SOL_CLUTCH_E":      (0, 4, 44),
    "SOL_TCC":           (0, 5, 46),
    "SOL_LINE_PRESSURE": (0, 6, 47),
    "SOL_PARK_HOLD":     (1, 0,  5),
    "SOL_PARK_RELEASE":  (1, 1, 48),
}


def _net_pins(net_name):
    return [r for r in _read(NETS) if r["net"] == net_name]


@pytest.mark.parametrize("net_name,expected", EXPECTED_SOLENOID_BINDING.items())
def test_solenoid_net_connects_correct_max_channel_and_tcm_pin(net_name, expected):
    expected_chip, expected_channel, expected_tcm_pin = expected
    rows = _net_pins(net_name)
    assert rows, f"net {net_name} has no nodes"

    # Find the J1 connection (TCM pin)
    j1_pins = [int(r["pin"]) for r in rows if r["component"] == "J1"]
    assert len(j1_pins) == 1, \
        f"{net_name} should connect to exactly one J1 pin; got {j1_pins}"
    assert j1_pins[0] == expected_tcm_pin, \
        f"{net_name} routes to TCM pin {j1_pins[0]}, " \
        f"firmware says it should be {expected_tcm_pin}"

    # Find the MAX22200 connection
    expected_ref = "U2" if expected_chip == 0 else "U3"
    max_pins = [r["pin"] for r in rows if r["component"] == expected_ref]
    assert len(max_pins) == 1, \
        f"{net_name} should connect to exactly one {expected_ref} pin"
    assert max_pins[0] == f"OUT{expected_channel}", \
        f"{net_name} routes to {expected_ref}.{max_pins[0]}, " \
        f"firmware says channel {expected_channel} (= OUT{expected_channel})"


def test_each_solenoid_has_a_flyback_diode():
    """Every solenoid output should have a flyback diode anchored on
    VBAT_SOL going to the solenoid output net. Catches missing FBs."""
    flyback_present = {r["component"]: True for r in _read(NETS)
                        if r["component"].startswith("D_FB_")}
    fbs = {f"D_FB_{p}" for p in (5, 41, 42, 43, 44, 45, 46, 47, 48)}
    missing = fbs - set(flyback_present)
    assert not missing, f"solenoid outputs missing flyback diodes: {missing}"


# ----------------------------------------------------------------------
# Power tree consistency
# ----------------------------------------------------------------------

def test_3v3_is_supplied_to_stm32_supply_pins():
    """STM32F103C8T6 has VDD/VDDA/VBAT_RTC pins — all need 3V3."""
    rows = [r for r in _read(NETS) if r["net"] == "+3V3" and r["component"] == "U1"]
    pins = {r["pin"] for r in rows}
    expected_supply_pins = {"VDD_1", "VDD_2", "VDD_3", "VDDA", "VBAT"}
    missing = expected_supply_pins - pins
    assert not missing, f"+3V3 missing from STM32 supply pins: {missing}"


def test_gnd_is_supplied_to_stm32_ground_pins():
    rows = [r for r in _read(NETS) if r["net"] == "GND" and r["component"] == "U1"]
    pins = {r["pin"] for r in rows}
    expected = {"VSS_1", "VSS_2", "VSS_3", "VSSA"}
    missing = expected - pins
    assert not missing, f"GND missing from STM32 ground pins: {missing}"


def test_both_max22200_chips_get_vbat_and_5v():
    """MAX22200 needs both VBAT (motor supply) and VDD (5V logic)."""
    for chip_ref in ("U2", "U3"):
        vbat = [r for r in _read(NETS)
                 if r["net"] == "VBAT" and r["component"] == chip_ref]
        v5 = [r for r in _read(NETS)
                if r["net"] == "+5V" and r["component"] == chip_ref]
        assert vbat, f"{chip_ref} missing VBAT supply"
        assert v5,   f"{chip_ref} missing 5V logic supply"


def test_can_lin_supplies_present():
    """TJA1043 + TJA1027 each need 5V on their bus side and 3V3 on the
    logic side."""
    for ref in ("U4", "U5"):
        v5 = [r for r in _read(NETS) if r["net"] == "+5V"  and r["component"] == ref]
        v3 = [r for r in _read(NETS) if r["net"] == "+3V3" and r["component"] == ref]
        assert v5, f"{ref} missing 5V supply"
        assert v3, f"{ref} missing 3V3 IO supply"


# ----------------------------------------------------------------------
# Pin allocation conflict detection (the PB10 trap)
# ----------------------------------------------------------------------

def test_no_stm32_pin_is_double_claimed():
    """Each STM32 pin should appear on exactly one logical net (or its
    supply nets). PB10 is currently dual-claimed for T15_WAKE and
    DEBUG_TX — this test will fail until the conflict is resolved."""
    # A pin like 'PA0' on U1 should appear on exactly one signal net
    # (excluding the power rails).
    power_nets = {"GND", "+3V3", "+5V", "VBAT", "VBAT_SOL", "SENSE_5V"}
    assignments: dict[str, list[str]] = defaultdict(list)
    for r in _read(NETS):
        if r["component"] != "U1":
            continue
        if r["net"] in power_nets:
            continue
        assignments[r["pin"]].append(r["net"])

    conflicts = {pin: nets for pin, nets in assignments.items() if len(set(nets)) > 1}

    # Known conflict to flag explicitly: PB10 is dual-claimed for
    # T15_WAKE and DEBUG_TX. The schematic spec marks it as a known
    # issue that must be resolved before fab. We expect this test to
    # surface it; the assertion message guides the reader.
    if "PB10" in conflicts:
        pytest.fail(
            f"STM32 pin conflict on PB10 (T15_WAKE vs DEBUG_TX) flagged "
            f"in SCHEMATIC.md — must resolve before fab. "
            f"Other conflicts: {[k for k in conflicts if k != 'PB10']}"
        )
    assert not conflicts, f"STM32 pin double-claims: {dict(conflicts)}"


# ----------------------------------------------------------------------
# Generator determinism + format sanity
# ----------------------------------------------------------------------

def test_netlist_regenerates_byte_identical():
    before = NETLIST.read_bytes()
    rc = subprocess.run(["python3", str(GEN)], capture_output=True, cwd=TCU)
    assert rc.returncode == 0, rc.stderr.decode()
    after = NETLIST.read_bytes()
    assert before == after, "gen_netlist.py is non-deterministic"


def test_netlist_starts_with_kicad_legacy_header():
    head = NETLIST.read_text().splitlines()[0]
    assert head.startswith("(export"), \
        f"netlist doesn't look like a KiCad legacy netlist: {head!r}"


def test_netlist_contains_all_components():
    text = NETLIST.read_text()
    for c in _read(COMPS):
        if c.get("ref"):
            assert f'(ref "{c["ref"]}")' in text, \
                f"component {c['ref']} missing from .net"


def test_netlist_contains_all_solenoid_nets():
    text = NETLIST.read_text()
    for net in EXPECTED_SOLENOID_BINDING:
        assert f'(name "{net}")' in text, \
            f"solenoid net {net} missing from .net"
