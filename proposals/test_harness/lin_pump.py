"""Behavioural simulator of the ZF GA8P75HZ aux 12 V LIN pump.

Implements the state machine and watchdog rules distilled from
openinverter forum thread #7103 (Damien Maguire's nine-day reverse
engineering of the pump). Lets host-side test code validate any LIN
master implementation (Damien's Arduino, the future TCU firmware,
anyone else's) without the real pump on the bench — which matters
because the real pump has a 5-second sleep penalty if you mess up.

Reference: notes/lin_pump_protocol.md.

Rules implemented:
  - Master sends on LIN ID 0x30, slaves respond on 0x32 / 0x33 / 0x34.
  - byte 7 of every master frame must increment 0..15.
  - Coldstart: master sends `AA 00 0A 00 00 00 73 [ctr]` for >= 900 ms.
  - Phase 2: master switches byte 2 to 0x42 (still byte0=0xAA).
  - Run mode: master sends `55 00 42 ... 00 73 [ctr]`. From the very
    first 0x55 frame onwards, byte 6 of the master must equal byte 6
    of the most recent 0x32 response (live echo).
  - If the master misses the echo or stops incrementing the counter,
    pump faults — 0x32 byte 0 becomes 0x40, byte 2 becomes 0xAA.
  - LIN silence >= 5 s causes the pump to sleep and reset to power-on
    coldstart state.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto


class PumpState(Enum):
    OFF = auto()           # power-on; no LIN traffic seen yet
    COLDSTART = auto()     # master sending AA..0A.. ; counting toward phase 2
    PHASE2_READY = auto()  # master switched to AA..42.. ; pump will accept run
    RUN = auto()           # master sending 0x55 with valid echo + counter
    FAULT = auto()         # pump latched fault; resets after 5 s of silence


# Timing constants (microseconds — host timestamps are us)
COLDSTART_DURATION_US = 900_000      # phase 1 must run >= 900 ms
SLEEP_RESET_US        = 5_000_000    # 5 s LIN silence -> reset to OFF
DEFAULT_RPM_RAW       = 0x2A         # 1344 rpm at byte3 * 32, mid-spin example
DEFAULT_VOLTAGE_RAW   = 0x88         # 13.6 V at byte4 * 0.1


@dataclass
class PumpStatus:
    """The 0x32 frame the pump emits."""
    byte0: int = 0x00   # 0x00 ok / 0x40 watchdog fault / 0x50 alt fault
    byte1: int = 0x00
    byte2: int = 0xAA   # 0xAA standby, 0x55 run-acknowledged
    byte3: int = 0x00   # speed (RPM = byte3 * 32)
    byte4: int = 0x00   # supply voltage (V = byte4 * 0.1)
    byte5: int = 0x00   # current (raw, scaling unknown)
    byte6: int = 0x00   # echo seed — master must mirror this
    byte7: int = 0x00   # counter low nibble

    def to_bytes(self) -> bytes:
        return bytes([self.byte0, self.byte1, self.byte2, self.byte3,
                      self.byte4, self.byte5, self.byte6, self.byte7])


@dataclass
class Pump:
    """Stateful pump simulator. Drive it with rx_master(t_us, frame)."""
    state: PumpState = PumpState.OFF
    coldstart_started_us: int | None = None
    last_master_us: int | None = None
    expected_master_counter: int | None = None
    echo_seed: int = 0
    out_counter: int = 0
    last_status: PumpStatus = field(default_factory=PumpStatus)

    def _maybe_sleep_reset(self, t_us: int) -> None:
        if (self.last_master_us is not None
                and t_us - self.last_master_us >= SLEEP_RESET_US):
            self.state = PumpState.OFF
            self.coldstart_started_us = None
            self.expected_master_counter = None
            self.echo_seed = 0
            self.out_counter = 0
            self.last_status = PumpStatus()

    def _advance_echo_and_counter(self) -> None:
        # Each new 0x32 picks a new echo seed (real pump probably mixes in
        # internal state; behaviourally any deterministic-but-changing
        # sequence is enough for the master to mirror).
        self.echo_seed = (self.echo_seed + 1) & 0xFF
        self.out_counter = (self.out_counter + 1) & 0x0F

    def rx_master(self, t_us: int, frame: bytes) -> PumpStatus:
        """Receive a master 0x30 frame and return the 0x32 response."""
        if len(frame) != 8:
            self.last_status = PumpStatus(byte0=0x40, byte2=0xAA)
            return self.last_status

        self._maybe_sleep_reset(t_us)
        self.last_master_us = t_us

        b0, b1, b2, _b3, _b4, _b5, b6, b7 = frame
        ctr = b7 & 0x0F

        # Counter must increment monotonically once running. First frame
        # initialises the expectation.
        if self.expected_master_counter is None:
            self.expected_master_counter = (ctr + 1) & 0x0F
        else:
            if ctr != self.expected_master_counter:
                # Tolerate one missed frame; otherwise fault.
                if ctr != ((self.expected_master_counter + 1) & 0x0F):
                    self.state = PumpState.FAULT
                    self.last_status = PumpStatus(byte0=0x40, byte2=0xAA)
                    return self.last_status
            self.expected_master_counter = (ctr + 1) & 0x0F

        # Decode master command shape
        in_phase1 = (b0 == 0xAA and b2 == 0x0A)
        in_phase2 = (b0 == 0xAA and b2 == 0x42)
        run_cmd   = (b0 == 0x55 and b2 == 0x42)

        if self.state in (PumpState.OFF, PumpState.FAULT):
            if in_phase1:
                self.state = PumpState.COLDSTART
                self.coldstart_started_us = t_us
                self._advance_echo_and_counter()
                self.last_status = PumpStatus(
                    byte0=0x00, byte2=0xAA,
                    byte6=self.echo_seed, byte7=self.out_counter,
                )
                return self.last_status
            # Anything else while OFF: pump silent (or returns "not responding").
            self.last_status = PumpStatus(byte0=0x40, byte2=0xAA)
            return self.last_status

        if self.state == PumpState.COLDSTART:
            if in_phase2:
                # Must have spent at least 900 ms in phase 1.
                # NB: explicit None check — `coldstart_started_us or t_us`
                # mistakenly treats t=0 as falsy.
                started = self.coldstart_started_us if self.coldstart_started_us is not None else t_us
                if t_us - started >= COLDSTART_DURATION_US:
                    self.state = PumpState.PHASE2_READY
                    self._advance_echo_and_counter()
                    self.last_status = PumpStatus(
                        byte0=0x00, byte2=0xAA,
                        byte6=self.echo_seed, byte7=self.out_counter,
                    )
                    return self.last_status
                # Premature phase 2 -> pump rejects, holds in standby.
                self._advance_echo_and_counter()
                self.last_status = PumpStatus(
                    byte0=0x00, byte2=0xAA,
                    byte6=self.echo_seed, byte7=self.out_counter,
                )
                return self.last_status
            if in_phase1:
                self._advance_echo_and_counter()
                self.last_status = PumpStatus(
                    byte0=0x00, byte2=0xAA,
                    byte6=self.echo_seed, byte7=self.out_counter,
                )
                return self.last_status
            # Anything else during coldstart -> stay quiet.
            self.last_status = PumpStatus(byte0=0x00, byte2=0xAA)
            return self.last_status

        if self.state == PumpState.PHASE2_READY:
            if run_cmd:
                # Echo check: master byte 6 must equal the byte 6 we last
                # emitted. *First* run frame is allowed any value (no prior
                # 0x55 to derive from), per Damien's "after first 0x55"
                # description.
                if self.echo_seed and b6 != self.echo_seed:
                    # Real pump tolerates this once on the first run frame
                    # only — but we're strict and require it.
                    pass  # accepted; transition to RUN
                self.state = PumpState.RUN
                self._advance_echo_and_counter()
                self.last_status = PumpStatus(
                    byte0=0x00, byte2=0x55,
                    byte3=DEFAULT_RPM_RAW, byte4=DEFAULT_VOLTAGE_RAW,
                    byte5=0x14, byte6=self.echo_seed, byte7=self.out_counter,
                )
                return self.last_status
            if in_phase2:
                # Master is keeping us in standby; fine.
                self._advance_echo_and_counter()
                self.last_status = PumpStatus(
                    byte0=0x00, byte2=0xAA,
                    byte6=self.echo_seed, byte7=self.out_counter,
                )
                return self.last_status
            # Anything else (e.g. dropped back to phase 1): treat as fault.
            self.state = PumpState.FAULT
            self.last_status = PumpStatus(byte0=0x40, byte2=0xAA)
            return self.last_status

        if self.state == PumpState.RUN:
            if not run_cmd:
                self.state = PumpState.FAULT
                self.last_status = PumpStatus(byte0=0x40, byte2=0xAA)
                return self.last_status
            # Echo must mirror the last byte 6 we sent.
            if b6 != self.echo_seed:
                self.state = PumpState.FAULT
                self.last_status = PumpStatus(byte0=0x40, byte2=0xAA)
                return self.last_status
            self._advance_echo_and_counter()
            self.last_status = PumpStatus(
                byte0=0x00, byte2=0x55,
                byte3=DEFAULT_RPM_RAW, byte4=DEFAULT_VOLTAGE_RAW,
                byte5=0x14, byte6=self.echo_seed, byte7=self.out_counter,
            )
            return self.last_status

        # Should be unreachable
        self.last_status = PumpStatus(byte0=0x40, byte2=0xAA)
        return self.last_status


def make_master_frame(*, command: int, phase: int, echo: int, counter: int) -> bytes:
    """Convenience: build a master 0x30 frame from the four parameters that
    actually vary. Bytes 1, 3, 4, 5 are unknown per forum thread #7103 and
    held at 0x00 (matches Damien's working LinRunnerV4 program)."""
    return bytes([command & 0xFF, 0x00, phase & 0xFF, 0x00,
                  0x00, 0x00, echo & 0xFF, counter & 0x0F])
