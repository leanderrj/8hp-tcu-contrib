"""Shared pytest fixtures: capture paths and DBC location."""
from __future__ import annotations

from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parent.parent.parent
CAPTURES = REPO_ROOT / "archive" / "captures"
DBC_PATH = REPO_ROOT / "proposals" / "dbc" / "zf8hp-tcu.dbc"


CAPTURE_FILES = [
    "ix4_shifter1rnd.csv",
    "ix4_shifter2rndbuttons.csv",
    "ix4_shifteridrivebuttons.csv",
    "ix4_shiftpoweroff.csv",
]


@pytest.fixture(scope="session")
def captures() -> dict[str, Path]:
    """Map of capture name → absolute path; fails fast if any are missing."""
    out: dict[str, Path] = {}
    for name in CAPTURE_FILES:
        p = CAPTURES / name
        if not p.exists():
            pytest.skip(f"capture missing: {p}")
        out[name] = p
    return out


@pytest.fixture(scope="session")
def dbc_path() -> Path:
    if not DBC_PATH.exists():
        pytest.skip(f"DBC missing: {DBC_PATH}")
    return DBC_PATH
