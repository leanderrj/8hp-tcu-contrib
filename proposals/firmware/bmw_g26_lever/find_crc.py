#!/usr/bin/env python3
"""Brute-force the CRC8 parameters for BMW G26 CAN ID 0x3F9.

Run from the repo root:
    python3 proposals/firmware/bmw_g26_lever/find_crc.py

Reads SavvyCAN CSV captures from archive/captures/ and finds the unique
(polynomial, init^xorout, byte-range, reflect_in, reflect_out) tuple that
validates 100% of captured 0x3F9 frames.

Result reported as of 2026-05-10:
    range = bytes [1..7], poly = 0x1D, init^xorout = 0x04, no reflection
    Matches: 553 / 553 frames.

This produces the parameters baked into iX4_Lever.{h,cpp}.
"""
from __future__ import annotations
import csv, os, sys

CAP_DIR = os.path.join(os.path.dirname(__file__), '..', '..', '..', 'archive', 'captures')
CAP_DIR = os.path.normpath(CAP_DIR)
TARGET_ID = 0x3F9


def load_id(path: str, want_id: int) -> list[bytes]:
    out = []
    with open(path) as fh:
        r = csv.reader(fh)
        next(r, None)
        for row in r:
            if len(row) < 14:
                continue
            try:
                cid = int(row[1], 16)
                if cid != want_id:
                    continue
                dlc = int(row[5])
                data = bytes(int(row[6 + i], 16) for i in range(min(dlc, 8)))
            except ValueError:
                continue
            out.append(data)
    return out


def crc8(data: bytes, poly: int, init: int = 0,
         refin: bool = False, refout: bool = False, xorout: int = 0) -> int:
    crc = init
    for b in data:
        if refin:
            b = int(f'{b:08b}'[::-1], 2)
        crc ^= b
        for _ in range(8):
            crc = ((crc << 1) ^ poly) & 0xFF if (crc & 0x80) else (crc << 1) & 0xFF
    if refout:
        crc = int(f'{crc:08b}'[::-1], 2)
    return crc ^ xorout


def main() -> int:
    files = ['ix4_shifter1rnd.csv', 'ix4_shifter2rndbuttons.csv',
             'ix4_shifteridrivebuttons.csv', 'ix4_shiftpoweroff.csv']
    frames: list[bytes] = []
    for f in files:
        p = os.path.join(CAP_DIR, f)
        if not os.path.exists(p):
            print(f'capture missing: {p}', file=sys.stderr)
            return 2
        frames += load_id(p, TARGET_ID)
    print(f'loaded {len(frames)} frames of 0x{TARGET_ID:03X}')
    if not frames:
        return 2

    ranges = {
        'b1..7': lambda d: d[1:],
        'b1..6': lambda d: d[1:7],
        'b1..5': lambda d: d[1:6],
        'b1..4': lambda d: d[1:5],
        'b2..7': lambda d: d[2:],
        'idHL+b1..7': lambda d: bytes([0x03, 0xF9]) + d[1:],
        'idLH+b1..7': lambda d: bytes([0xF9, 0x03]) + d[1:],
    }

    hits = []
    for rname, rfn in ranges.items():
        for poly in range(256):
            for refin in (False, True):
                for refout in (False, True):
                    f0 = frames[0]
                    msg = rfn(f0)
                    c0 = crc8(msg, poly, 0, refin, refout, 0)
                    offset = f0[0] ^ c0  # = init ^ xorout
                    ok = True
                    for fr in frames:
                        msg = rfn(fr)
                        c = crc8(msg, poly, 0, refin, refout, 0)
                        if (c ^ offset) != fr[0]:
                            ok = False
                            break
                    if ok:
                        hits.append((rname, poly, offset, refin, refout))

    print(f'\nMatches: {len(hits)}')
    for rname, poly, offset, refin, refout in hits:
        print(f'  range={rname:<14} poly=0x{poly:02X}  init^xorout=0x{offset:02X}  '
              f'refin={refin} refout={refout}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
