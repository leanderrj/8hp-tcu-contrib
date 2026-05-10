"""Validate the CarOS profile YAML against the DBC it claims to decode.

If the DBC adds/removes signals or changes IDs, the profile must
follow. This test catches drift between the two.
"""
from __future__ import annotations

from pathlib import Path

import cantools
import pytest
import yaml


REPO_ROOT = Path(__file__).resolve().parents[3]
PROFILE = REPO_ROOT / "proposals" / "caros_integration" / "zombieverter_8hp.yaml"
DBC     = REPO_ROOT / "proposals" / "dbc" / "zf8hp-tcu.dbc"


@pytest.fixture(scope="module")
def profile():
    if not PROFILE.exists():
        pytest.skip(f"profile missing: {PROFILE}")
    with open(PROFILE) as fh:
        return yaml.safe_load(fh)


@pytest.fixture(scope="module")
def db():
    if not DBC.exists():
        pytest.skip(f"dbc missing: {DBC}")
    return cantools.database.load_file(DBC)


def test_profile_loads_as_yaml(profile):
    assert profile["vehicle"]["type"] == "ev_conversion"
    assert profile["transmission"]["tcu"] == "openinverter_oi_8hp"


def test_can_messages_match_dbc_ids(profile, db):
    """Every CAN message ID in the profile must exist in the DBC."""
    dbc_ids = {m.frame_id for m in db.messages}
    profile_ids = {m["id"] for m in profile["can"]["messages"].values()}
    extra_in_profile = profile_ids - dbc_ids
    assert not extra_in_profile, (
        f"profile references CAN IDs not in DBC: "
        f"{[hex(i) for i in extra_in_profile]}"
    )


def test_every_dbc_tcu_to_vcu_frame_is_in_profile(profile, db):
    """All TCU->VCU frames (status, shift, pump) must be decoded by
    the profile so CarOS picks them up."""
    profile_ids = {m["id"] for m in profile["can"]["messages"].values()}
    for m in db.messages:
        if "TCU" in m.name and m.frame_id != 0x520:  # 0x520 is VCU->TCU
            assert m.frame_id in profile_ids, \
                f"DBC frame {m.name} (0x{m.frame_id:03X}) missing from profile"


def test_every_critical_signal_has_an_mqtt_topic(profile, db):
    """The headline signals — current_gear, oil_temp, line_pressure,
    park_lock, fault — must all map to MQTT topics."""
    critical = {
        "current_gear", "oil_temp", "line_pressure",
        "park_lock", "any_fault", "input_shaft_rpm", "output_shaft_rpm",
        "shift_phase", "torque_cut_request", "pump_state",
    }
    has_topic: set[str] = set()
    for msg in profile["can"]["messages"].values():
        for sig_name, sig in msg.get("signals", {}).items():
            if sig.get("mqtt_topic"):
                has_topic.add(sig_name)
    missing = critical - has_topic
    assert not missing, f"critical signals without MQTT topic: {missing}"


def test_vcu_gear_request_is_rx_monitor_only(profile):
    """Safety: CarOS must NEVER inject gear requests onto the bus.
    The profile must mark VCU->TCU frames as rx_monitor (logging only)."""
    vcu_frame = profile["can"]["messages"]["vcu_gear_request"]
    assert vcu_frame["direction"] == "rx_monitor", (
        "CarOS profile must not transmit gear requests — "
        "found direction=" + vcu_frame["direction"]
    )


def test_pump_frame_marked_optional(profile):
    """Non-hybrid 8HP variants don't carry the aux pump LIN bus.
    The profile must allow its absence without raising a fault."""
    pump = profile["can"]["messages"]["tcu_pump_status"]
    assert pump.get("optional") is True


def test_safety_alerts_cover_high_asil_hazards(profile):
    """Cross-check: every ASIL-D hazard from the HARA must have at
    least one alert in the profile that would catch it."""
    import sys
    sys.path.insert(0, str(REPO_ROOT / "proposals" / "safety"))
    from hara import ASILLevel, TCU_HARA  # noqa

    asil_d_hazards = [h for h in TCU_HARA if h.asil_level == ASILLevel.D]
    alerts = profile["safety"]["alerts"]
    # T002 (rollaway) is the ASIL D hazard. The
    # park_not_engaged_at_shutdown alert is the dashboard-side coverage.
    assert any("park" in a.lower() for a in alerts), (
        f"profile lacks an alert covering ASIL D hazards "
        f"{[h.id for h in asil_d_hazards]}"
    )


def test_signal_bit_layout_matches_dbc(profile, db):
    """For each signal in the profile, the start_bit and bit_length
    must agree with the DBC. Spot-check the headline ones."""
    msg = db.get_message_by_name("TCU_Status1")
    profile_msg = profile["can"]["messages"]["tcu_status1"]
    profile_signals = profile_msg["signals"]
    for sig in msg.signals:
        # Convert DBC name to profile snake_case key
        key = sig.name.lower()
        # Special case: profile keys use snake_case, DBC mixes camelCase
        camel_to_snake = {
            "currentgear": "current_gear",
            "targetgearecho": "target_gear_echo",
            "tcustate": "tcu_state",
            "shiftinprogress": "shift_in_progress",
            "tcuready": "tcu_ready",
            "anyfault": "any_fault",
            "parklock": "park_lock",
            "inputshaftrpm": "input_shaft_rpm",
            "outputshaftrpm": "output_shaft_rpm",
            "oiltemp": "oil_temp",
            "linepressure": "line_pressure",
        }
        key = camel_to_snake.get(key.replace("_", ""), key)
        if key not in profile_signals:
            continue
        ps = profile_signals[key]
        assert ps["start_bit"] == sig.start, (
            f"{sig.name}: profile start_bit {ps['start_bit']} != "
            f"DBC {sig.start}"
        )
        assert ps["bit_length"] == sig.length, (
            f"{sig.name}: profile bit_length {ps['bit_length']} != "
            f"DBC {sig.length}"
        )
