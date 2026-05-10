"""SavvyCAN CSV capture loader.

Lets test code iterate frames from any of the captures in
`archive/captures/` without each test reinventing the parser.

Format produced by SavvyCAN (and matched by the captures Damien posted
to forum thread #7028):

    Time Stamp,ID,Extended,Dir,Bus,LEN,D1,D2,D3,D4,D5,D6,D7,D8
    185818721,00000000,false,Rx,0,8,00,04,00,00,00,00,00,00,
    ...

Time stamps are integer microseconds.
"""
from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator


@dataclass(frozen=True)
class Frame:
    ts_us: int          # microseconds since capture start
    can_id: int         # 11- or 29-bit identifier
    extended: bool
    direction: str      # "Rx" / "Tx"
    bus: int
    data: bytes         # length == dlc

    @property
    def dlc(self) -> int:
        return len(self.data)


def load_capture(path: str | Path) -> list[Frame]:
    """Read a SavvyCAN CSV in full and return every frame as a Frame."""
    out: list[Frame] = []
    with open(path, newline="") as fh:
        r = csv.reader(fh)
        next(r, None)  # header
        for row in r:
            if len(row) < 14:
                continue
            try:
                ts = int(row[0])
                can_id = int(row[1], 16)
                extended = row[2].strip().lower() == "true"
                direction = row[3]
                bus = int(row[4])
                dlc = int(row[5])
                data = bytes(int(row[6 + i], 16) for i in range(min(dlc, 8)))
            except (ValueError, IndexError):
                continue
            out.append(Frame(ts, can_id, extended, direction, bus, data))
    return out


def filter_id(frames: Iterable[Frame], can_id: int) -> Iterator[Frame]:
    """Yield only frames matching `can_id`."""
    for f in frames:
        if f.can_id == can_id:
            yield f


def gear_transitions(frames: Iterable[Frame], byte_idx: int) -> list[tuple[int, int]]:
    """Compress the same-byte runs into (timestamp, value) transition events.

    Useful for asserting that a capture passes through expected gear
    states in order, without caring how many heartbeat frames were
    emitted at each state.
    """
    out: list[tuple[int, int]] = []
    last = None
    for f in frames:
        if len(f.data) <= byte_idx:
            continue
        v = f.data[byte_idx]
        if v != last:
            out.append((f.ts_us, v))
            last = v
    return out
