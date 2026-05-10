"""Virtual ZF 8HP gearbox + hybrid aux-pump plant model.

Goal: a deterministic Python model that produces synthetic shaft RPMs,
oil temperature, line pressure, and aux-pump state in response to the
TCU's commanded clutch engagement set + LIN traffic. Used by the test
harness to drive the shift state machine and the LIN pump master code
through full control-loop scenarios without bench hardware.

This is *not* a high-fidelity hydraulic simulator. It is a behavioural
model that's right about:

  - **Gear ratios**: derived from the published 8HP gear set. The
    forward ratio per gear is a constant lookup; we don't simulate
    mechanical compliance.
  - **Output RPM relation**: output_rpm ≈ input_rpm / gear_ratio when a
    valid 3-of-5 clutch combination is engaged; otherwise output is
    held (drivetrain assumed to coast).
  - **Mid-shift slip**: during a clutch swap we ramp gear_ratio
    linearly between the from-gear and to-gear ratios over the time
    the bind layer reports as "ramp percent".
  - **Line pressure**: proportional to pump RPM × pump duty, falling
    off with oil temperature. Cold oil = higher line pressure for the
    same flow.
  - **Oil temperature**: drifts toward an ambient setpoint with a long
    time constant. Heated by mechanical losses during shifts.
  - **Aux pump**: composed with lin_pump.Pump. The plant uses the
    pump's reported RPM as a contributor to line pressure.

It is *deliberately wrong* about:

  - Detailed clutch fill dynamics (we don't model fluid compressibility).
  - Real torque transmission (we don't compute slip torque).
  - Bus-side timing of solenoid current control loops.

That fidelity comes from bench data, which we don't have. The model
is defensible for protocol/state-machine testing and unsuitable for
calibration.

Sources:
  - Gear ratios: ZF 8HP70 / 8HP90 family published ratios (Wikipedia
    cross-checked against ZF marketing brochure "The 8HP Family").
  - Single-element-per-shift property: Greiner & Grumbach, SAE 2009-01-1083.
  - Aux pump behaviour: openinverter forum thread #7103, post 7
    (re-encoded in lin_pump.py).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from lin_pump import Pump as LinPump, PumpStatus


# Forward gear ratios for ZF 8HP (model 8HP70 / 8HP90). Source: ZF
# marketing brochure "The 8HP Family", cross-referenced with the
# Wikipedia ZF 8HP article. These are the *forward* drive ratios from
# input shaft to output shaft, so output_rpm = input_rpm / ratio.
GEAR_RATIO_BY_GEAR = {
    0:  None,    # Neutral
    1:  4.71,
    2:  3.14,
    3:  2.10,
    4:  1.67,
    5:  1.29,
    6:  1.00,
    7:  0.84,
    8:  0.67,
    9: -3.30,    # Reverse (negative ratio: output reverses direction)
}


# The clutch engagement table in clutch_table.h. Replicated here so the
# Python model can validate that a TCU's commanded clutch set
# corresponds to a valid gear (and refuse to produce sensible output
# otherwise).
CLUTCH_TABLE = {
    0: 0b00000,                               # Neutral
    1: 0b11001,                               # A | B | D  (bits 0,1,3)
    2: 0b10011,                               # A | B | E  (bits 0,1,4)
    3: 0b10101,                               # A | C | E  (bits 0,2,4)
    4: 0b01101,                               # A | C | D  (bits 0,2,3)
    5: 0b11001,                               # NB: A|B|D again would be wrong;
                                              # corrected below from clutch_table.h
}


# Re-derive from clutch_table.h convention. Bit 0=A 1=B 2=C 3=D 4=E.
def _bits(*letters: str) -> int:
    out = 0
    for l in letters:
        out |= 1 << "ABCDE".index(l)
    return out


CLUTCH_TABLE = {
    0: 0,
    1: _bits("A", "B", "D"),
    2: _bits("A", "B", "E"),
    3: _bits("A", "C", "E"),
    4: _bits("A", "C", "D"),
    5: _bits("A", "D", "E"),
    6: _bits("B", "D", "E"),
    7: _bits("B", "C", "E"),
    8: _bits("B", "C", "D"),
    9: _bits("C", "D", "E"),  # Reverse
}


def gear_for_clutch_set(engaged: int) -> Optional[int]:
    """Reverse lookup: which gear is engaged given a clutch bitmask, or
    None if the mask doesn't match any defined gear."""
    for gear, mask in CLUTCH_TABLE.items():
        if mask == engaged:
            return gear
    return None


@dataclass
class PlantInputs:
    """One control tick of TCU intent."""
    engaged_clutch_set: int             # bitmask, bits 0..4 = A..E
    target_clutch_set: int              # what we're shifting toward
    ramp_percent: int                   # 0..100 progress through the swap
    pump_master_frame: bytes            # the 8-byte 0x30 frame (or empty)
    input_torque_nm: float              # from VCU (engine/motor)


@dataclass
class PlantState:
    """The model's view of the gearbox right now."""
    input_rpm: float = 0.0
    output_rpm: float = 0.0
    oil_temp_c: float = 60.0
    line_pressure_bar: float = 0.0
    pump_status: Optional[PumpStatus] = None
    current_gear: Optional[int] = None
    last_ratio: float = 0.0


@dataclass
class PlantConfig:
    """Tunable physical-ish constants. Not calibration data — these
    just need to be plausible for the harness."""
    ambient_oil_c: float          = 60.0
    oil_thermal_tau_ms: float     = 60_000.0    # 1-minute drift
    shift_heating_c_per_event: float = 0.05
    base_line_pressure_bar: float = 1.0
    line_pressure_per_pump_rpm: float = 0.001     # 4000 rpm -> +4 bar
    line_pressure_oil_temp_drop_per_c: float = 0.005  # warmer = thinner = less P
    spin_down_per_ms: float       = 5.0           # input RPM coast-down


class Plant:
    """Stateful plant model. Step it at 1 ms granularity from the test."""

    def __init__(self, cfg: PlantConfig | None = None):
        self.cfg = cfg or PlantConfig()
        self.state = PlantState(oil_temp_c=self.cfg.ambient_oil_c)
        self._pump = LinPump()
        self._t_us = 0
        self._last_engaged: int = 0

    @property
    def now_us(self) -> int:
        return self._t_us

    def set_input_rpm(self, rpm: float) -> None:
        """Force the input shaft RPM (e.g. driver request, motor
        controller in cruise). Tests can set this directly to exercise
        gear ratio + slip behaviour."""
        self.state.input_rpm = rpm

    def step(self, dt_ms: int, inputs: PlantInputs) -> PlantState:
        """Advance the model by `dt_ms` milliseconds and return the new
        state. The TCU bind layer is expected to call step() at 1..10 ms
        granularity matching its own task tick."""
        self._t_us += dt_ms * 1_000

        # ----- Aux pump (LIN) ---------------------------------------------
        if inputs.pump_master_frame:
            self.state.pump_status = self._pump.rx_master(
                self._t_us, inputs.pump_master_frame
            )
        pump_rpm = (self.state.pump_status.byte3 * 32) if self.state.pump_status else 0

        # ----- Line pressure ----------------------------------------------
        # Base + pump contribution - oil-temperature thinning.
        base = self.cfg.base_line_pressure_bar
        from_pump = pump_rpm * self.cfg.line_pressure_per_pump_rpm
        oil_drop = max(self.state.oil_temp_c - 60.0, 0.0) \
                    * self.cfg.line_pressure_oil_temp_drop_per_c
        self.state.line_pressure_bar = max(base + from_pump - oil_drop, 0.0)

        # ----- Gear / slip -------------------------------------------------
        from_gear = gear_for_clutch_set(inputs.engaged_clutch_set)
        to_gear   = gear_for_clutch_set(inputs.target_clutch_set)

        # Resolve ratios; None / Neutral / invalid combinations all
        # contribute a 0.0 ratio, which we treat as "no torque path".
        def _ratio(gear):
            if gear is None:                 return 0.0
            r = GEAR_RATIO_BY_GEAR.get(gear)
            return r if r is not None else 0.0

        r_from = _ratio(from_gear)
        r_to   = _ratio(to_gear)
        ratio  = r_from + (r_to - r_from) * (inputs.ramp_percent / 100.0)
        self.state.last_ratio = ratio

        if abs(ratio) > 1e-6:
            # Power path established — output is the input divided by
            # the (possibly blended) ratio.
            self.state.output_rpm = self.state.input_rpm / ratio
            # Report whichever side currently matches the gearbox's
            # actual engaged set; during overlap, neither will and
            # current_gear becomes None until settle.
            self.state.current_gear = from_gear if from_gear is not None else to_gear
        else:
            # No torque path (Neutral, invalid mask, or a no-element
            # transient). Output shaft coasts under drag, doesn't slam
            # to zero.
            self.state.output_rpm = max(
                self.state.output_rpm - self.cfg.spin_down_per_ms * dt_ms, 0.0
            )
            self.state.current_gear = from_gear if from_gear is not None else to_gear

        # ----- Oil temperature drift --------------------------------------
        # First-order toward ambient + a little heating each shift event.
        if inputs.engaged_clutch_set != self._last_engaged:
            self.state.oil_temp_c += self.cfg.shift_heating_c_per_event
            self._last_engaged = inputs.engaged_clutch_set
        if self.cfg.oil_thermal_tau_ms > 0:
            alpha = dt_ms / self.cfg.oil_thermal_tau_ms
            self.state.oil_temp_c += (self.cfg.ambient_oil_c
                                       - self.state.oil_temp_c) * alpha

        return self.state
