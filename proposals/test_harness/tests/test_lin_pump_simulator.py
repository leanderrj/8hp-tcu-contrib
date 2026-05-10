"""Tests for the LIN pump simulator (lin_pump.py).

These exercise the state machine against synthetic master sequences
that mirror Damien's working LinRunnerV4 program. Validates the rules
distilled in notes/lin_pump_protocol.md without needing the real pump.

Once the TCU firmware exists, its LIN master implementation can drive
this simulator the same way to get end-to-end test coverage of the
control loop without bench hardware.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from lin_pump import (
    COLDSTART_DURATION_US,
    DEFAULT_RPM_RAW,
    DEFAULT_VOLTAGE_RAW,
    Pump,
    PumpState,
    SLEEP_RESET_US,
    make_master_frame,
)


def cold_to_run(pump: Pump, t0_us: int = 0) -> int:
    """Drive `pump` through a complete coldstart -> phase 2 -> run sequence.
    Returns the time (microseconds) of the last frame we sent."""
    t = t0_us
    counter = 0

    # Phase 1: send AA 00 0A ... for slightly more than 900 ms at 25 ms cadence.
    # 40 frames * 25 ms = 1000 ms.
    for _ in range(40):
        f = make_master_frame(command=0xAA, phase=0x0A, echo=0, counter=counter)
        pump.rx_master(t, f)
        t += 25_000
        counter = (counter + 1) & 0x0F

    # Phase 2: send AA 00 42 ... for two frames. Pump returns echo seed.
    f = make_master_frame(command=0xAA, phase=0x42, echo=0, counter=counter)
    resp = pump.rx_master(t, f)
    t += 25_000
    counter = (counter + 1) & 0x0F

    # Run: send 55 00 42 ... mirroring byte 6.
    f = make_master_frame(command=0x55, phase=0x42, echo=resp.byte6, counter=counter)
    pump.rx_master(t, f)
    t += 25_000

    return t


def test_full_run_sequence_reaches_run_state():
    pump = Pump()
    cold_to_run(pump)
    assert pump.state is PumpState.RUN
    assert pump.last_status.byte0 == 0x00
    assert pump.last_status.byte2 == 0x55
    assert pump.last_status.byte3 == DEFAULT_RPM_RAW
    assert pump.last_status.byte4 == DEFAULT_VOLTAGE_RAW


def test_premature_phase2_does_not_reach_ready():
    """Switch to phase 2 before 900 ms has elapsed -> pump stays in COLDSTART."""
    pump = Pump()
    f = make_master_frame(command=0xAA, phase=0x0A, echo=0, counter=0)
    pump.rx_master(0, f)
    assert pump.state is PumpState.COLDSTART

    f = make_master_frame(command=0xAA, phase=0x42, echo=0, counter=1)
    pump.rx_master(100_000, f)  # only 100 ms into coldstart
    assert pump.state is PumpState.COLDSTART


def test_run_command_without_phase2_is_rejected():
    """Skip phase 1 entirely, send 0x55 from cold -> pump stays in OFF/FAULT."""
    pump = Pump()
    f = make_master_frame(command=0x55, phase=0x42, echo=0, counter=0)
    resp = pump.rx_master(0, f)
    assert pump.state in (PumpState.OFF, PumpState.FAULT)
    assert resp.byte0 == 0x40


def test_dropped_echo_byte_causes_fault():
    """The thing that took Damien nine days to figure out."""
    pump = Pump()
    t = cold_to_run(pump)
    assert pump.state is PumpState.RUN

    # Send a run frame but mirror the WRONG echo (0xFF instead of last byte 6).
    f = make_master_frame(command=0x55, phase=0x42, echo=0xFF, counter=15)
    resp = pump.rx_master(t + 25_000, f)
    assert pump.state is PumpState.FAULT
    assert resp.byte0 == 0x40


def test_correct_echo_keeps_pump_in_run():
    """Mirror byte 6 every frame for a long sequence — pump stays in RUN."""
    pump = Pump()
    t = cold_to_run(pump)
    counter = (pump.expected_master_counter or 0)

    # Run for 100 more frames (2.5 s), echo correctly each time.
    for _ in range(100):
        last_echo = pump.last_status.byte6
        f = make_master_frame(command=0x55, phase=0x42, echo=last_echo, counter=counter)
        pump.rx_master(t, f)
        t += 25_000
        counter = (counter + 1) & 0x0F
        assert pump.state is PumpState.RUN, (
            f"pump dropped out of RUN after correct echo at t={t}: {pump.last_status}"
        )


def test_5_second_silence_resets_to_off():
    """Damien noted: ~5 s of LIN silence puts the pump back to power-on state."""
    pump = Pump()
    cold_to_run(pump, t0_us=0)
    assert pump.state is PumpState.RUN

    # Now go silent for 5+ seconds and ping it again.
    silence_t = 2_000_000  # the run sequence ends around t=1 s
    pump._maybe_sleep_reset(silence_t + SLEEP_RESET_US + 1)
    assert pump.state is PumpState.OFF


def test_counter_must_advance():
    """If the master stops incrementing byte 7 low nibble, pump faults."""
    pump = Pump()
    # Coldstart with counter stuck at 0.
    for _ in range(5):
        f = make_master_frame(command=0xAA, phase=0x0A, echo=0, counter=0)
        pump.rx_master(0, f)
    # Pump should have rejected the second-and-onwards frames as counter
    # didn't advance.
    assert pump.state is PumpState.FAULT


def test_recovery_path_after_fault():
    """After a fault, a 5 s silence resets and a fresh coldstart succeeds."""
    pump = Pump()
    cold_to_run(pump)
    # Trigger a fault with a bad echo.
    f = make_master_frame(command=0x55, phase=0x42, echo=0xFF, counter=15)
    pump.rx_master(2_000_000, f)
    assert pump.state is PumpState.FAULT

    # Wait long enough.
    t_after = 2_000_000 + SLEEP_RESET_US + 1
    pump._maybe_sleep_reset(t_after)
    assert pump.state is PumpState.OFF

    # Fresh coldstart from t_after — should reach RUN again.
    cold_to_run(pump, t0_us=t_after)
    assert pump.state is PumpState.RUN


@pytest.mark.parametrize("rpm_raw,expected_rpm", [(0x2A, 1344), (0x40, 2048), (0x80, 4096)])
def test_run_state_reports_rpm_per_forum_scaling(rpm_raw, expected_rpm):
    """Verify the byte3 * 32 = RPM scaling Damien published in #7103 post 7."""
    pump = Pump()
    cold_to_run(pump)
    pump.last_status.byte3 = rpm_raw
    assert pump.last_status.byte3 * 32 == expected_rpm
