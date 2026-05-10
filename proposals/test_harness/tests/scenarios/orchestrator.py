"""Composable Plant + ShiftLogic + LIN-pump driver for scenario tests.

The C++ shift_logic.cpp is the production implementation. Here we mirror
its semantics in Python so scenarios can run without a build step. The
two are kept aligned by:

  - Sharing the clutch table layout (plant_model.CLUTCH_TABLE
    matches clutch_table.h byte-for-byte; tests in test_plant_model
    enforce this).
  - The phase sequence and timing constants matching ShiftCalibration
    defaults from shift_logic.h.

If the C++ implementation diverges from this Python mirror, a scenario
will fail and the discrepancy gets caught.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass
from enum import Enum, auto
from pathlib import Path

# The harness modules live one level up (proposals/test_harness/).
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from lin_pump import make_master_frame
from plant_model import CLUTCH_TABLE, Plant, PlantInputs


# Mirror of zf8hp::Gear (clutch_table.h)
class Gear(Enum):
    Neutral  = 0
    Forward1 = 1
    Forward2 = 2
    Forward3 = 3
    Forward4 = 4
    Forward5 = 5
    Forward6 = 6
    Forward7 = 7
    Forward8 = 8
    Reverse  = 9


# Mirror of zf8hp::ShiftPhase (shift_logic.h)
class ShiftPhase(Enum):
    Idle = auto()
    PreFill = auto()
    TorqueCut = auto()
    Overlap = auto()
    Complete = auto()
    Limp = auto()


@dataclass
class Calibration:
    pre_fill_ms: int       = 30
    torque_cut_ack_ms: int = 50
    overlap_ms: int        = 120
    torque_restore_ms: int = 30


def _plan_next_step(current: Gear, target: Gear) -> Gear:
    """Mirror of ShiftLogic::PlanNextStep in shift_logic.cpp."""
    if current == target:
        return current
    if current.value in range(1, 9) and target.value in range(1, 9):
        return Gear(target.value if target.value > current.value
                     else current.value - 1) if False \
            else Gear(current.value + (1 if target.value > current.value else -1))
    if current is Gear.Neutral:
        if target is Gear.Reverse:
            return Gear.Reverse
        if target.value in range(1, 9):
            return Gear.Forward1
        return Gear.Neutral
    return Gear.Neutral


class ShiftMirror:
    """Python port of ShiftLogic. Same state machine, same calibration
    defaults, same outputs; used to drive the Plant in scenario tests."""

    def __init__(self, cal: Calibration | None = None):
        self.cal = cal or Calibration()
        self.current = Gear.Neutral
        self.target = Gear.Neutral
        self.next_step = Gear.Neutral
        self.phase = ShiftPhase.Idle
        self.phase_started_ms = 0
        self.torque_cut_ack = False
        self.fault: str | None = None

    def request_gear(self, target: Gear) -> None:
        self.target = target

    def set_torque_cut_ack(self, ack: bool) -> None:
        self.torque_cut_ack = ack

    def _enter(self, p: ShiftPhase, now_ms: int) -> None:
        self.phase = p
        self.phase_started_ms = now_ms
        if p is ShiftPhase.Idle:
            self.torque_cut_ack = False

    def _elapsed(self, now_ms: int) -> int:
        return now_ms - self.phase_started_ms

    def tick(self, now_ms: int) -> dict:
        if self.phase is ShiftPhase.Idle:
            if self.current is not self.target and self.fault is None:
                self.next_step = _plan_next_step(self.current, self.target)
                if self.current is Gear.Neutral or self.next_step is Gear.Neutral:
                    self._enter(ShiftPhase.Overlap, now_ms)
                else:
                    self._enter(ShiftPhase.PreFill, now_ms)
        elif self.phase is ShiftPhase.PreFill:
            if self._elapsed(now_ms) >= self.cal.pre_fill_ms:
                self._enter(ShiftPhase.TorqueCut, now_ms)
        elif self.phase is ShiftPhase.TorqueCut:
            if self.torque_cut_ack:
                self._enter(ShiftPhase.Overlap, now_ms)
            elif self._elapsed(now_ms) >= self.cal.torque_cut_ack_ms:
                self.fault = "TorqueCutTimeout"
                self.target = self.current
                self._enter(ShiftPhase.Idle, now_ms)
        elif self.phase is ShiftPhase.Overlap:
            if self._elapsed(now_ms) >= self.cal.overlap_ms:
                self.current = self.next_step
                self._enter(ShiftPhase.Complete, now_ms)
        elif self.phase is ShiftPhase.Complete:
            if self._elapsed(now_ms) >= self.cal.torque_restore_ms:
                self._enter(ShiftPhase.Idle, now_ms)
        # Limp stays limp.

        ramp = 0
        if self.phase is ShiftPhase.Overlap and self.cal.overlap_ms:
            ramp = min(100, self._elapsed(now_ms) * 100 // self.cal.overlap_ms)
        elif self.phase is ShiftPhase.PreFill and self.cal.pre_fill_ms:
            ramp = self._elapsed(now_ms) * 30 // self.cal.pre_fill_ms

        engaged_set = CLUTCH_TABLE.get(self.current.value, 0)
        target_set  = CLUTCH_TABLE.get(self.next_step.value, 0)
        return {
            "current_gear": self.current,
            "target_gear":  self.target,
            "next_step":    self.next_step,
            "phase":        self.phase,
            "engaged_set":  engaged_set & target_set
                            if self.phase is ShiftPhase.Overlap else engaged_set,
            "ramping_in_set":  target_set & ~engaged_set,
            "ramping_out_set": engaged_set & ~target_set
                                if self.phase is ShiftPhase.Overlap else 0,
            "ramp_progress": ramp,
            "torque_cut_request": self.phase in (
                ShiftPhase.TorqueCut, ShiftPhase.Overlap
            ) and self.current is not Gear.Neutral
              and self.next_step is not Gear.Neutral,
            "shift_active": self.phase not in (ShiftPhase.Idle, ShiftPhase.Limp),
            "fault": self.fault,
        }


@dataclass
class DriveSession:
    """Plant + ShiftMirror + a synthetic VCU that auto-acks the
    torque-cut handshake. The default-everything constructor is
    enough for most scenarios; tests override fields to inject
    fault conditions."""
    plant: Plant
    shift: ShiftMirror
    auto_ack_torque_cut: bool = True
    pump_running: bool = False
    pump_counter: int = 0
    last_pump_status_byte6: int = 0
    now_ms: int = 0

    @classmethod
    def fresh(cls) -> "DriveSession":
        return cls(plant=Plant(), shift=ShiftMirror())

    def _next_pump_frame(self) -> bytes:
        """Build the next 0x30 master frame appropriate to the pump
        state. Mirrors what a working LIN master would do."""
        # Coldstart for the first 1000 ms, then phase 2, then run.
        if self.now_ms < 1000:
            cmd, phase = 0xAA, 0x0A
        elif self.now_ms < 1050:
            cmd, phase = 0xAA, 0x42
        else:
            cmd, phase = 0x55, 0x42

        echo = self.last_pump_status_byte6 if cmd == 0x55 else 0
        f = make_master_frame(command=cmd, phase=phase,
                                echo=echo, counter=self.pump_counter)
        self.pump_counter = (self.pump_counter + 1) & 0x0F
        return f

    def step(self, dt_ms: int = 1) -> dict:
        """Advance the entire stack one tick. Returns the shift
        command for that tick + plant state."""
        self.now_ms += dt_ms
        if self.auto_ack_torque_cut:
            cmd = self.shift.tick(self.now_ms)
            self.shift.set_torque_cut_ack(cmd["torque_cut_request"])
        cmd = self.shift.tick(self.now_ms)

        pump_frame = self._next_pump_frame() if self.pump_running else b""
        plant_inputs = PlantInputs(
            engaged_clutch_set=cmd["engaged_set"]
                                | cmd["ramping_in_set"]
                                | cmd["ramping_out_set"],
            target_clutch_set=CLUTCH_TABLE.get(cmd["next_step"].value, 0),
            ramp_percent=cmd["ramp_progress"],
            pump_master_frame=pump_frame,
            input_torque_nm=200.0,
        )
        plant_state = self.plant.step(dt_ms, plant_inputs)
        if plant_state.pump_status:
            self.last_pump_status_byte6 = plant_state.pump_status.byte6
        return {**cmd, "plant": plant_state}

    def request_gear(self, gear: Gear) -> None:
        self.shift.request_gear(gear)

    def settle(self, max_ms: int = 5000) -> int:
        """Run until the shift state machine returns to Idle in the
        target gear, or `max_ms` elapsed. Returns elapsed ms."""
        start = self.now_ms
        while self.now_ms - start < max_ms:
            cmd = self.step(1)
            if cmd["phase"] is ShiftPhase.Idle and \
               self.shift.current is self.shift.target:
                return self.now_ms - start
        raise AssertionError(
            f"shift did not settle within {max_ms} ms; "
            f"current={self.shift.current.name} target={self.shift.target.name} "
            f"phase={self.shift.phase.name}"
        )
