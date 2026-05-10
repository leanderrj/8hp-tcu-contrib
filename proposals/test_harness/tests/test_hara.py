"""Tests for the 8HP TCU HARA.

These guarantee the safety analysis stays self-consistent as hazards
and requirements are added or revised. Run with the rest of the
pytest suite.
"""
from __future__ import annotations

import sys
from pathlib import Path

# proposals/safety/hara.py is the artifact under test
sys.path.insert(
    0,
    str(Path(__file__).resolve().parents[2] / "safety"),
)

import hara
from hara import (
    ASILLevel,
    TCU_HARA,
    TCU_SAFETY_REQUIREMENTS,
    validate,
)


def test_every_hazard_has_unique_id():
    ids = [h.id for h in TCU_HARA]
    assert len(ids) == len(set(ids)), f"duplicate hazard ids: {ids}"


def test_every_hazard_has_safety_goal_and_safe_state():
    for h in TCU_HARA:
        assert h.safety_goal, f"{h.id} missing safety_goal"
        assert h.safe_state, f"{h.id} missing safe_state"


def test_every_hazard_has_at_least_one_mitigation():
    for h in TCU_HARA:
        assert h.mitigations, f"{h.id} has no mitigations listed"


def test_ftti_is_positive():
    for h in TCU_HARA:
        assert h.ftti_ms > 0, f"{h.id} has non-positive FTTI"


def test_asil_levels_are_consistent_with_sec():
    """Each hazard's recorded asil_level must equal the lookup result
    from its (S, E, C). Catches manual edits that fall out of sync."""
    from caros.safety.asil import determine_asil
    for h in TCU_HARA:
        expected = determine_asil(h.severity, h.exposure, h.controllability)
        assert h.asil_level == expected, (
            f"{h.id}: stored ASIL {h.asil_level.name} != "
            f"computed {expected.name} from "
            f"{h.severity.name}/{h.exposure.name}/{h.controllability.name}"
        )


def test_every_high_asil_hazard_has_a_requirement():
    """ASIL >= A must have at least one safety requirement covering it."""
    covered = set()
    for sr in TCU_SAFETY_REQUIREMENTS:
        for ref in sr.hazard_ref.split(","):
            covered.add(ref.strip())
    for h in TCU_HARA:
        if h.asil_level.value >= ASILLevel.A.value:
            assert h.id in covered, (
                f"{h.id} is {h.asil_level.name} but has no safety requirement"
            )


def test_every_requirement_has_at_least_one_test_ref():
    for sr in TCU_SAFETY_REQUIREMENTS:
        assert sr.test_refs, f"{sr.id} has no test references"


def test_every_requirement_references_real_hazard():
    hazard_ids = {h.id for h in TCU_HARA}
    for sr in TCU_SAFETY_REQUIREMENTS:
        for ref in sr.hazard_ref.split(","):
            ref = ref.strip()
            assert ref in hazard_ids, (
                f"{sr.id} references unknown hazard {ref}"
            )


def test_validate_returns_no_errors():
    """Top-level guard: hara.validate() flags any structural issue."""
    findings = validate()
    errors = [f for f in findings if f["level"] == "error"]
    assert errors == [], f"validate() reported errors: {errors}"


def test_park_d_class_is_explicitly_present():
    """Sanity check that the rollaway hazard is rated as ASIL D —
    if someone downgrades it, this test forces a discussion."""
    park_fail = next(h for h in TCU_HARA if h.id == "T002")
    assert park_fail.asil_level == ASILLevel.D, (
        "T002 (Park rollaway) was downgraded — "
        "this is the load-bearing high-integrity hazard."
    )


def test_torque_cut_timeout_is_qm_or_a():
    """Sanity check that the torque-cut handshake hazard hasn't been
    accidentally inflated to a high ASIL — it's a comfort issue, not
    a safety issue at rated torque."""
    h = next(h for h in TCU_HARA if h.id == "T012")
    assert h.asil_level.value <= ASILLevel.A.value, (
        f"T012 inflated to {h.asil_level.name}; reconsider S/E/C"
    )


def test_report_generation_does_not_crash():
    text = hara.generate_report()
    assert "HAZARD ANALYSIS" in text
    assert "ASIL distribution" in text
    assert len(text) > 1000
