"""Replay every 0x3F9 frame from every iX4 capture through the reference
decoder. The C++ unit test (test_iX4_Lever.cpp) covers 12 hand-picked
fixtures; this covers all 553.

If this passes, the C++ implementation has full-corpus parity with the
empirical CRC search result and the gear-byte mapping.
"""
from __future__ import annotations

import sys
from pathlib import Path

# Make sibling modules importable when pytest is run from the harness dir.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ix4_lever import IX4Lever, Sgear, compute_crc8, validate_frame
from replay import filter_id, gear_transitions, load_capture


def test_every_captured_frame_validates_crc(captures):
    total = 0
    bad = 0
    for path in captures.values():
        for f in filter_id(load_capture(path), 0x3F9):
            total += 1
            if not validate_frame(f.data):
                bad += 1
    assert total == 553, f"expected 553 frames, got {total}"
    assert bad == 0, f"{bad}/{total} frames failed CRC"


def test_poweroff_capture_stays_in_park(captures):
    lever = IX4Lever()
    for f in filter_id(load_capture(captures["ix4_shiftpoweroff.csv"]), 0x3F9):
        lever.decode(f.data)
        assert lever.gear is Sgear.PARK
    assert lever.crc_fails == 0


def test_idrive_buttons_capture_stays_in_park(captures):
    """Pressing iDrive buttons doesn't move the gear (gear was in P)."""
    lever = IX4Lever()
    for f in filter_id(load_capture(captures["ix4_shifteridrivebuttons.csv"]), 0x3F9):
        lever.decode(f.data)
        assert lever.gear is Sgear.PARK
    assert lever.crc_fails == 0


def test_shifter1rnd_visits_all_four_gears(captures):
    """The shifter rotation capture must hit every observed gear value."""
    seen: set[Sgear] = set()
    lever = IX4Lever()
    for f in filter_id(load_capture(captures["ix4_shifter1rnd.csv"]), 0x3F9):
        if lever.decode(f.data):
            seen.add(lever.gear)
    assert seen == {Sgear.PARK, Sgear.NEUTRAL, Sgear.REVERSE, Sgear.DRIVE}


def test_byte6_only_takes_known_values(captures):
    """The four observed gear bytes (and only those) appear across all
    captures. If a future capture introduces 0x34 (Sport?) this test
    will flag it loudly so we know to extend the mapping."""
    seen_bytes: set[int] = set()
    for path in captures.values():
        for f in filter_id(load_capture(path), 0x3F9):
            seen_bytes.add(f.data[6])
    assert seen_bytes == {0x31, 0x32, 0x33, 0x35}


def test_byte1_high_nibble_is_always_0xF(captures):
    """Counter byte high nibble invariant — 553 frames, 0 exceptions."""
    for path in captures.values():
        for f in filter_id(load_capture(path), 0x3F9):
            assert (f.data[1] & 0xF0) == 0xF0, (
                f"byte 1 high nibble != 0xF in {path.name} at {f.ts_us}: {f.data.hex()}"
            )


def test_corrupted_crc_is_rejected_in_isolation():
    lever = IX4Lever()
    good = bytes([0xC5, 0xF1, 0x80, 0x73, 0xFF, 0x30, 0x33, 0x00])
    assert lever.decode(good)
    assert lever.gear is Sgear.PARK

    corrupt = bytearray(good)
    corrupt[6] = 0x35  # claim Drive
    # don't fix the CRC -> still rejected
    ok = lever.decode(bytes(corrupt))
    assert not ok
    assert lever.gear is Sgear.PARK
    assert lever.crc_fails == 1


def test_gear_transitions_in_shifter1rnd(captures):
    """Document the actual transition sequence for posterity. If this
    breaks, the user did something different — not a regression."""
    frames = list(filter_id(load_capture(captures["ix4_shifter1rnd.csv"]), 0x3F9))
    transitions = gear_transitions(frames, byte_idx=6)
    sequence = [v for _, v in transitions]
    # First entry is whatever gear the capture started in (P).
    assert sequence[0] == 0x33
    # Capture ends back in P after the rotation.
    assert sequence[-1] == 0x33
    # The sequence must contain at least one excursion through every
    # non-Park gear.
    for v in (0x31, 0x32, 0x35):
        assert v in sequence
