"""Python reference implementation of iX4_Lever.

Mirrors the C++ version at proposals/firmware/bmw_g26_lever/iX4_Lever.cpp
exactly (CRC, counter check, gear mapping). Keeping the two in sync is the
test — if a frame decodes differently here than in the C++, one of them
is wrong.

Used by tests/test_ix4_lever_full_capture.py to replay every captured
0x3F9 frame and assert behaviour.
"""
from __future__ import annotations

from enum import Enum

CAN_ID = 0x3F9
CRC_POLY = 0x1D
CRC_XOROUT = 0x04


class Sgear(Enum):
    PARK = "PARK"
    REVERSE = "REVERSE"
    NEUTRAL = "NEUTRAL"
    DRIVE = "DRIVE"


def _crc_table(poly: int) -> list[int]:
    t = [0] * 256
    for d in range(256):
        r = d
        for _ in range(8):
            r = ((r << 1) ^ poly) & 0xFF if (r & 0x80) else (r << 1) & 0xFF
        t[d] = r
    return t


_TABLE = _crc_table(CRC_POLY)


def compute_crc8(frame: bytes) -> int:
    """CRC8 over bytes [1..7] with poly 0x1D, init 0x00, xorout 0x04."""
    if len(frame) < 8:
        raise ValueError("need 8 bytes")
    rem = 0
    for i in range(1, 8):
        rem = _TABLE[frame[i] ^ rem]
    return rem ^ CRC_XOROUT


def validate_frame(frame: bytes) -> bool:
    return compute_crc8(frame) == frame[0]


def decode_gear_byte(b6: int) -> Sgear | None:
    """Return Sgear or None if `b6` isn't a recognised gear value.

    Mapping per CRC_NOTES.md:
       0x33 = PARK    (confirmed)
       0x31 = NEUTRAL (transient center position)
       0x32 = REVERSE (hypothesis pending forum confirmation)
       0x35 = DRIVE   (hypothesis pending forum confirmation)
       0x34 = unobserved (probably Sport)
    """
    return {
        0x33: Sgear.PARK,
        0x31: Sgear.NEUTRAL,
        0x32: Sgear.REVERSE,
        0x35: Sgear.DRIVE,
    }.get(b6)


class IX4Lever:
    """Stateful decoder. Holds last-known-good gear across bad frames."""

    def __init__(self) -> None:
        self.gear: Sgear = Sgear.PARK
        self.crc_fails = 0
        self.counter_fails = 0
        self.prev_counter: int | None = None

    def decode(self, frame: bytes) -> bool:
        if len(frame) < 8:
            return False

        if not validate_frame(frame):
            self.crc_fails += 1
            return False

        # Counter check: high nibble of byte 1 must be 0xF in every observed
        # capture. Low nibble cycles 0..14.
        if (frame[1] & 0xF0) != 0xF0:
            self.counter_fails += 1
            return False
        ctr = frame[1] & 0x0F
        if self.prev_counter is not None:
            expected = (self.prev_counter + 1) & 0x0F
            # Allow one missed frame.
            if ctr != expected and ctr != ((expected + 1) & 0x0F):
                self.counter_fails += 1
        self.prev_counter = ctr

        new_gear = decode_gear_byte(frame[6])
        if new_gear is not None:
            self.gear = new_gear
        return True
