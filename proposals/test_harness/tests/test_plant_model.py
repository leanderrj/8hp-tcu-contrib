"""Tests for the virtual Mechatronik plant model."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from lin_pump import make_master_frame
from plant_model import (
    CLUTCH_TABLE,
    GEAR_RATIO_BY_GEAR,
    Plant,
    PlantConfig,
    PlantInputs,
    gear_for_clutch_set,
)


def _bits(*letters):
    out = 0
    for l in letters:
        out |= 1 << "ABCDE".index(l)
    return out


def test_clutch_table_matches_clutch_table_h_layout():
    """Every entry in the Python CLUTCH_TABLE must match the
    bit-packing convention from clutch_table.h: bit 0 = A, ..., bit 4 = E."""
    assert CLUTCH_TABLE[1] == _bits("A", "B", "D")
    assert CLUTCH_TABLE[2] == _bits("A", "B", "E")
    assert CLUTCH_TABLE[8] == _bits("B", "C", "D")


def test_each_gear_has_three_engaged_elements():
    for g in range(1, 9):
        assert bin(CLUTCH_TABLE[g]).count("1") == 3
    assert bin(CLUTCH_TABLE[9]).count("1") == 3
    assert CLUTCH_TABLE[0] == 0


def test_adjacent_gears_differ_by_one_element():
    """The single-element-per-shift property — same invariant the C++
    static_assert in clutch_table.h enforces."""
    for g in range(1, 8):
        diff = CLUTCH_TABLE[g] ^ CLUTCH_TABLE[g + 1]
        assert bin(diff).count("1") == 2  # one bit drops, one bit lifts


def test_gear_for_clutch_set_roundtrip():
    for g, mask in CLUTCH_TABLE.items():
        assert gear_for_clutch_set(mask) == g


def test_plant_starts_at_ambient_oil_temp():
    p = Plant()
    assert abs(p.state.oil_temp_c - p.cfg.ambient_oil_c) < 0.001


def test_output_rpm_follows_gear_ratio_in_first_gear():
    p = Plant()
    p.set_input_rpm(2400.0)
    inp = PlantInputs(
        engaged_clutch_set=CLUTCH_TABLE[1],
        target_clutch_set=CLUTCH_TABLE[1],
        ramp_percent=100,
        pump_master_frame=b"",
        input_torque_nm=100.0,
    )
    p.step(10, inp)
    expected = 2400.0 / GEAR_RATIO_BY_GEAR[1]
    assert abs(p.state.output_rpm - expected) < 0.5
    assert p.state.current_gear == 1


def test_output_rpm_blends_during_shift_overlap():
    """Mid-shift, ratio should linearly interpolate between from and to."""
    p = Plant()
    p.set_input_rpm(2400.0)
    inp = PlantInputs(
        engaged_clutch_set=CLUTCH_TABLE[3],
        target_clutch_set=CLUTCH_TABLE[4],
        ramp_percent=50,                     # midway through 3->4
        pump_master_frame=b"",
        input_torque_nm=100.0,
    )
    p.step(10, inp)
    midpoint_ratio = (GEAR_RATIO_BY_GEAR[3] + GEAR_RATIO_BY_GEAR[4]) / 2.0
    assert abs(p.state.last_ratio - midpoint_ratio) < 0.001


def test_neutral_clutch_set_coasts_output_to_zero():
    p = Plant()
    p.set_input_rpm(2400.0)
    p.state.output_rpm = 1500.0  # seed
    inp = PlantInputs(
        engaged_clutch_set=0,
        target_clutch_set=0,
        ramp_percent=100,
        pump_master_frame=b"",
        input_torque_nm=0.0,
    )
    # Step long enough that output coasts all the way to zero.
    for _ in range(500):
        p.step(1, inp)
    assert p.state.output_rpm == 0.0
    assert p.state.current_gear == 0  # Neutral


def test_invalid_clutch_combination_yields_no_gear():
    """A clutch mask that doesn't match any defined gear (e.g.
    mid-overlap with two elements engaged) gets reported as
    current_gear == None and the output coasts."""
    p = Plant()
    p.set_input_rpm(1500.0)
    p.state.output_rpm = 1000.0
    inp = PlantInputs(
        engaged_clutch_set=_bits("A", "B"),  # 2 elements only — no gear matches
        target_clutch_set=_bits("A", "B"),
        ramp_percent=100,
        pump_master_frame=b"",
        input_torque_nm=0.0,
    )
    for _ in range(300):
        p.step(1, inp)
    assert p.state.output_rpm < 1000.0
    assert p.state.current_gear is None


def test_reverse_inverts_output_direction():
    p = Plant()
    p.set_input_rpm(1000.0)
    inp = PlantInputs(
        engaged_clutch_set=CLUTCH_TABLE[9],
        target_clutch_set=CLUTCH_TABLE[9],
        ramp_percent=100,
        pump_master_frame=b"",
        input_torque_nm=50.0,
    )
    p.step(10, inp)
    expected = 1000.0 / GEAR_RATIO_BY_GEAR[9]
    assert expected < 0.0
    assert abs(p.state.output_rpm - expected) < 0.5


def test_pump_running_increases_line_pressure():
    """Drive the pump master frame through cold-start -> phase2 -> run,
    line pressure should rise above the base."""
    p = Plant(PlantConfig(ambient_oil_c=60.0))
    inp = PlantInputs(
        engaged_clutch_set=0,
        target_clutch_set=0,
        ramp_percent=100,
        pump_master_frame=b"",
        input_torque_nm=0.0,
    )

    # Drive 40 phase-1 frames @ 25 ms each (1 second of coldstart).
    counter = 0
    t = 0
    for _ in range(40):
        f = make_master_frame(command=0xAA, phase=0x0A, echo=0, counter=counter)
        inp.pump_master_frame = f
        p.step(25, inp)
        counter = (counter + 1) & 0x0F
        t += 25

    # One phase-2 frame.
    f = make_master_frame(command=0xAA, phase=0x42, echo=0, counter=counter)
    inp.pump_master_frame = f
    state = p.step(25, inp)
    counter = (counter + 1) & 0x0F

    # Run frame, mirroring the echo we just got.
    last_echo = state.pump_status.byte6 if state.pump_status else 0
    f = make_master_frame(command=0x55, phase=0x42, echo=last_echo, counter=counter)
    inp.pump_master_frame = f
    state = p.step(25, inp)

    assert state.pump_status is not None
    assert state.pump_status.byte2 == 0x55  # run acknowledged
    assert state.line_pressure_bar > p.cfg.base_line_pressure_bar


def test_shift_event_warms_oil_slightly():
    """Each clutch-state change adds a small heating term."""
    p = Plant(PlantConfig(ambient_oil_c=60.0,
                            oil_thermal_tau_ms=10_000_000.0,  # disable cooling
                            shift_heating_c_per_event=1.0))
    p.set_input_rpm(2000.0)
    inp = PlantInputs(
        engaged_clutch_set=CLUTCH_TABLE[1],
        target_clutch_set=CLUTCH_TABLE[1],
        ramp_percent=100,
        pump_master_frame=b"",
        input_torque_nm=0.0,
    )
    p.step(10, inp)
    initial = p.state.oil_temp_c

    # Change engaged set — simulates a shift event. Should heat by 1 °C.
    inp.engaged_clutch_set = CLUTCH_TABLE[2]
    p.step(10, inp)
    assert p.state.oil_temp_c > initial + 0.99
