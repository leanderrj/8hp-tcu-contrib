"""End-to-end scenario tests modelled on CarOS tests/scenarios/test_drive_cycle.py.

These compose Plant + ShiftMirror + LIN pump simulator into realistic
driving episodes and assert the resulting CAN-side state matches the
HARA safety requirements.
"""
from __future__ import annotations

from scenarios.orchestrator import DriveSession, Gear, ShiftPhase


# -----------------------------------------------------------------------
# Cold start through first gear engagement
# -----------------------------------------------------------------------

def test_cold_start_to_drive():
    """Power-on -> Park -> Drive transition. Should settle in Forward1."""
    s = DriveSession.fresh()
    s.plant.set_input_rpm(800.0)  # idle motor
    s.request_gear(Gear.Forward1)
    elapsed = s.settle()
    assert elapsed > 0
    assert s.shift.current is Gear.Forward1
    assert s.shift.phase is ShiftPhase.Idle
    # Plant should reflect actual gear ratio
    assert s.plant.state.output_rpm > 0
    assert s.plant.state.last_ratio > 1.0  # forward gear 1 has high ratio


def test_full_upshift_sequence_1_to_8():
    """Walk every forward gear in sequence. Each should settle and
    leave us in the requested gear. The Plant's output RPM should
    monotonically increase as gear ratio decreases."""
    s = DriveSession.fresh()
    s.plant.set_input_rpm(2400.0)
    s.request_gear(Gear.Forward1)
    s.settle()

    output_rpms: list[float] = []
    for g in (Gear.Forward2, Gear.Forward3, Gear.Forward4,
              Gear.Forward5, Gear.Forward6, Gear.Forward7, Gear.Forward8):
        s.request_gear(g)
        s.settle()
        assert s.shift.current is g, \
            f"failed to reach {g.name}; ended at {s.shift.current.name}"
        output_rpms.append(s.plant.state.output_rpm)

    # 1 -> 8 ratio drops from ~4.7 to ~0.67, so output RPM should rise
    assert output_rpms == sorted(output_rpms), \
        f"output RPMs not monotonic across upshift: {output_rpms}"


def test_kickdown_8_to_3_walks_through_intermediate_gears():
    """6→3 kickdown. Mid-shift gear must NEVER skip a step (single-
    element-per-shift safety property)."""
    s = DriveSession.fresh()
    s.plant.set_input_rpm(2400.0)
    s.request_gear(Gear.Forward1)
    s.settle()
    for g in (Gear.Forward2, Gear.Forward3, Gear.Forward4, Gear.Forward5,
              Gear.Forward6, Gear.Forward7, Gear.Forward8):
        s.request_gear(g)
        s.settle()
    assert s.shift.current is Gear.Forward8

    # Kickdown to 3.
    s.request_gear(Gear.Forward3)
    visited: list[Gear] = [s.shift.current]
    while s.shift.current is not Gear.Forward3:
        s.step(1)
        if s.shift.current != visited[-1]:
            visited.append(s.shift.current)
    expected = [Gear.Forward8, Gear.Forward7, Gear.Forward6,
                 Gear.Forward5, Gear.Forward4, Gear.Forward3]
    assert visited == expected, \
        f"kickdown skipped a gear: visited {[g.name for g in visited]}"


# -----------------------------------------------------------------------
# Forward-to-reverse safety (HARA T004 / STR006)
# -----------------------------------------------------------------------

def test_forward_to_reverse_at_rest_walks_via_neutral():
    """STR006: F→R must walk through Neutral. The orchestrator path is
    deterministic; this test enforces the safety claim explicitly."""
    s = DriveSession.fresh()
    s.plant.set_input_rpm(800.0)
    s.request_gear(Gear.Forward1)
    s.settle()

    s.request_gear(Gear.Reverse)
    saw_neutral = False
    while s.shift.current is not Gear.Reverse:
        s.step(1)
        if s.shift.current is Gear.Neutral:
            saw_neutral = True
    assert saw_neutral, \
        "F→R completed without passing through Neutral — STR006 violated"


# -----------------------------------------------------------------------
# Torque-cut handshake
# -----------------------------------------------------------------------

def test_torque_cut_request_asserted_during_overlap():
    """The TCU must hold TorqueCutRequest = 1 from the start of the
    TorqueCut phase through the end of Overlap. This is what the VCU
    relies on to keep torque pulled during the clutch swap."""
    s = DriveSession.fresh()
    s.plant.set_input_rpm(2400.0)
    s.request_gear(Gear.Forward1)
    s.settle()

    s.request_gear(Gear.Forward2)
    saw_request = False
    # Drive at least one tick so the shift state machine leaves Idle, then
    # run until it returns to Idle (shift complete).
    for _ in range(500):
        cmd = s.step(1)
        if cmd["phase"] in (ShiftPhase.TorqueCut, ShiftPhase.Overlap):
            assert cmd["torque_cut_request"], \
                f"phase {cmd['phase'].name} did not assert TorqueCutRequest"
            saw_request = True
        if saw_request and cmd["phase"] is ShiftPhase.Idle:
            break
    assert saw_request, "shift completed without ever requesting torque cut"


def test_torque_cut_timeout_aborts_shift_and_holds_gear():
    """STR013: If VCU never acks, the shift aborts cleanly and we hold
    the original gear (don't get stuck mid-shift, don't drop to N)."""
    s = DriveSession.fresh()
    s.plant.set_input_rpm(2400.0)
    s.request_gear(Gear.Forward1)
    s.settle()

    # Disable the auto-ack so the VCU never acknowledges torque-cut.
    s.auto_ack_torque_cut = False
    s.shift.set_torque_cut_ack(False)
    s.request_gear(Gear.Forward2)

    # Run long enough that the timeout has to fire.
    for _ in range(500):
        s.step(1)

    assert s.shift.fault == "TorqueCutTimeout", \
        f"expected TorqueCutTimeout fault, got {s.shift.fault!r}"
    assert s.shift.current is Gear.Forward1, \
        f"shift didn't hold original gear; ended at {s.shift.current.name}"
    assert s.shift.phase is ShiftPhase.Idle, \
        "shift state machine didn't return to Idle after timeout"


# -----------------------------------------------------------------------
# LIN pump scenarios
# -----------------------------------------------------------------------

def test_pump_reaches_run_during_drive_cycle():
    """The hybrid 8HP aux pump should successfully cold-start and reach
    Run state in the first ~1.1 s of operation. Once running, pump RPM
    contributes to line pressure (which the plant model reflects)."""
    s = DriveSession.fresh()
    s.pump_running = True
    s.plant.set_input_rpm(1500.0)
    s.request_gear(Gear.Forward1)
    s.settle()

    # Step long enough for the pump to run through coldstart + phase 2.
    for _ in range(1500):
        s.step(1)

    assert s.plant.state.pump_status is not None
    assert s.plant.state.pump_status.byte2 == 0x55, \
        f"pump never entered Run; byte2={s.plant.state.pump_status.byte2:#x}"
    assert s.plant.state.line_pressure_bar > s.plant.cfg.base_line_pressure_bar


# -----------------------------------------------------------------------
# Gear-ratio plausibility (HARA T010 / STR011)
# -----------------------------------------------------------------------

def test_input_rpm_ratio_output_consistency_in_every_forward_gear():
    """STR011 (informally): in steady state, output_rpm × gear_ratio
    should equal input_rpm. If the plant model and clutch table
    disagree on ratios this test surfaces it."""
    s = DriveSession.fresh()
    s.plant.set_input_rpm(2400.0)
    s.request_gear(Gear.Forward1)
    s.settle()

    for g in (Gear.Forward2, Gear.Forward3, Gear.Forward4,
              Gear.Forward5, Gear.Forward6, Gear.Forward7, Gear.Forward8):
        s.request_gear(g)
        s.settle()
        ratio = s.plant.state.last_ratio
        assert abs(s.plant.state.output_rpm * ratio - 2400.0) < 1.0, \
            f"in {g.name}: output {s.plant.state.output_rpm} * ratio {ratio} != input"
