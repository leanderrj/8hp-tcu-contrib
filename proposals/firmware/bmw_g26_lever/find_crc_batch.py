#!/usr/bin/env python3
"""Sweep find_crc.py logic across every BMW E2E-looking CAN ID in
the archive/captures/ corpus and print a CRC parameter table.

Heuristic for "looks like BMW E2E": byte 0 takes >=30 distinct values
(so it's a CRC, not a constant or sequence number) AND byte 1 has only
~16 distinct values with high nibble fixed (the BMW counter pattern).

Reproduces the table in proposals/firmware/bmw_g26_lever/G26_CRC_CATALOG.md.
"""
from __future__ import annotations

import collections
import csv
import os
import sys

CAP_DIR = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "archive", "captures")
)


def load(path: str) -> dict[int, list[bytes]]:
    out: dict[int, list[bytes]] = collections.defaultdict(list)
    with open(path) as f:
        r = csv.reader(f)
        next(r, None)
        for row in r:
            if len(row) < 14:
                continue
            try:
                cid = int(row[1], 16)
                dlc = int(row[5])
                d = bytes(int(row[6 + i], 16) for i in range(min(dlc, 8)))
            except (ValueError, IndexError):
                continue
            out[cid].append(d)
    return out


def crc8(data: bytes, poly: int) -> int:
    crc = 0
    for b in data:
        crc ^= b
        for _ in range(8):
            crc = ((crc << 1) ^ poly) & 0xFF if (crc & 0x80) else (crc << 1) & 0xFF
    return crc


def main() -> int:
    files = [
        "ix4_shifter1rnd.csv",
        "ix4_shifter2rndbuttons.csv",
        "ix4_shifteridrivebuttons.csv",
        "ix4_shiftpoweroff.csv",
    ]

    pool: dict[int, list[bytes]] = collections.defaultdict(list)
    for f in files:
        p = os.path.join(CAP_DIR, f)
        if not os.path.exists(p):
            print(f"capture missing: {p}", file=sys.stderr)
            return 2
        for cid, frames in load(p).items():
            pool[cid] += frames

    candidates = []
    for cid, frames in pool.items():
        if len(frames) < 50:
            continue
        if any(len(d) < 2 for d in frames):
            continue
        b0 = {d[0] for d in frames}
        b1 = {d[1] for d in frames}
        if len(b0) < 30 or len(b1) > 32:
            continue
        high_nibbles = {b >> 4 for b in b1}
        if len(high_nibbles) > 2:
            continue
        candidates.append(cid)
    candidates.sort()

    print(f"{'ID':>6}  {'DLC':>3}  xorout  {'range':>8}  frames    note")
    print("  -----  ---  ------  --------  ------    ----")
    confirmed = 0
    unknown = []
    for cid in candidates:
        frames = pool[cid]
        dlc = len(frames[0])
        f0 = frames[0]

        # First try poly 0x1D, range = bytes [1..dlc-1]
        c0 = crc8(f0[1:], 0x1D)
        offset = f0[0] ^ c0
        if all((crc8(fr[1:], 0x1D) ^ offset) == fr[0] for fr in frames):
            print(f"  0x{cid:03X}  {dlc:>3}    0x{offset:02X}  [1..{dlc-1}]  {len(frames):>6}")
            confirmed += 1
            continue

        # Try other polys / shorter ranges
        found = False
        for end in range(dlc - 1, 1, -1):
            for poly in (0x1D, 0x07, 0x2F, 0x9B):
                c0 = crc8(f0[1:end], poly)
                offset = f0[0] ^ c0
                if all((crc8(fr[1:end], poly) ^ offset) == fr[0] for fr in frames):
                    print(f"  0x{cid:03X}  {dlc:>3}    0x{offset:02X}  [1..{end-1}]  {len(frames):>6}    poly=0x{poly:02X}")
                    confirmed += 1
                    found = True
                    break
            if found:
                break
        if not found:
            unknown.append(cid)
            print(f"  0x{cid:03X}  {dlc:>3}    ----  --------  {len(frames):>6}    no match")

    print(f"\n{confirmed}/{len(candidates)} candidates fit BMW CRC8/0x1D.")
    if unknown:
        print(f"Unmatched: {', '.join(f'0x{c:03X}' for c in unknown)}")
        print("(likely sequence number / multiplexer / AUTOSAR E2E variant)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
