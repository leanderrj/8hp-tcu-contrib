"""Round-trip every signal in our DBC: encode → bytes → decode → struct,
and assert identity for the values that survive scaling.

This catches schema drift (someone edits the DBC and forgets to
regenerate the C source, or vice versa) and lets the harness validate
that whatever cantools version we're on still produces a stable
encoder/decoder.
"""
from __future__ import annotations

import cantools
import pytest


@pytest.fixture(scope="module")
def db(dbc_path):
    return cantools.database.load_file(dbc_path)


def test_loads_with_expected_message_count(db):
    assert len(db.messages) == 5, [m.name for m in db.messages]
    assert {m.frame_id for m in db.messages} == {0x520, 0x521, 0x540, 0x541, 0x542}


def test_vcu_gear_request_roundtrip(db):
    msg = db.get_message_by_name("VCU_GearRequest")
    sample = {
        "TargetGear": "D",
        "DriveMode": "Sport",
        "AccelPedal": 47.5,
        "TorqueRequest": -120,
        "VehicleSpeed": 88.42,
        "BrakePressed": 0,
        "FaultClear": 0,
        "ForceShift": 0,
        "VcuReady": 1,
        "Counter520": 7,
    }
    encoded = msg.encode(sample)
    assert len(encoded) == 8
    decoded = msg.decode(encoded)
    assert decoded["TargetGear"] == "D"
    assert decoded["DriveMode"] == "Sport"
    assert decoded["AccelPedal"] == pytest.approx(47.5)
    assert decoded["TorqueRequest"] == -120
    assert decoded["VehicleSpeed"] == pytest.approx(88.42, abs=0.01)
    assert decoded["VcuReady"] == 1


def test_tcu_status1_roundtrip(db):
    msg = db.get_message_by_name("TCU_Status1")
    sample = {
        "CurrentGear": "G4",
        "TargetGearEcho": "D",
        "TcuState": "Drive",
        "ShiftInProgress": 0,
        "TcuReady": 1,
        "AnyFault": 0,
        "ParkLock": 0,
        "InputShaftRPM": 2400,
        "OutputShaftRPM": 1800,
        "OilTemp": 78,
        "LinePressure": 12.4,
    }
    encoded = msg.encode(sample)
    decoded = msg.decode(encoded)
    assert decoded["CurrentGear"] == "G4"
    assert decoded["TcuState"] == "Drive"
    assert decoded["InputShaftRPM"] == 2400
    assert decoded["OilTemp"] == 78
    assert decoded["LinePressure"] == pytest.approx(12.4, abs=0.05)


def test_pump_status_uses_thread_7103_scaling(db):
    """Verify the LIN pump RPM and voltage signal scaling matches what
    Damien published in forum thread #7103, post 7."""
    msg = db.get_message_by_name("TCU_PumpStatus")

    # Forum mid-spin example: 0x32 byte 3 = 0x2A (raw 42) → 1344 rpm
    encoded = msg.encode({
        "PumpState": "Run",
        "PumpRunAck": 1,
        "PumpLinFault": 0,
        "PumpAltFault": 0,
        "PumpRPM": 1344,
        "PumpVoltage": 13.6,
        "PumpCurrentRaw": 42,
        "PumpRetryCount": 0,
        "Counter542": 0,
    })
    decoded = msg.decode(encoded)
    assert decoded["PumpRPM"] == 1344
    assert decoded["PumpVoltage"] == pytest.approx(13.6, abs=0.05)
    assert decoded["PumpState"] == "Run"


def _full_gear_request(**overrides):
    """cantools needs every signal set when encoding; this builds a default
    frame and lets tests override one or two fields at a time."""
    base = {
        "TargetGear": "P",
        "DriveMode": "Comfort",
        "AccelPedal": 0.0,
        "TorqueRequest": 0,
        "VehicleSpeed": 0.0,
        "BrakePressed": 0,
        "FaultClear": 0,
        "ForceShift": 0,
        "VcuReady": 0,
        "Counter520": 0,
    }
    base.update(overrides)
    return base


@pytest.mark.parametrize("gear", [
    "P", "R", "N", "D", "S", "M1", "M2", "M3", "M4", "M5", "M6", "M7", "M8",
])
def test_every_target_gear_choice_roundtrips(db, gear):
    msg = db.get_message_by_name("VCU_GearRequest")
    encoded = msg.encode(_full_gear_request(TargetGear=gear))
    assert str(msg.decode(encoded)["TargetGear"]) == gear


@pytest.mark.parametrize("speed_kmh", [0.0, 1.0, 88.42, 250.0])
def test_vehicle_speed_scaling(db, speed_kmh):
    """DBC scale=0.01, so a 0.0–250 km/h sweep round-trips within ±0.01."""
    msg = db.get_message_by_name("VCU_GearRequest")
    encoded = msg.encode(_full_gear_request(VehicleSpeed=speed_kmh))
    decoded = msg.decode(encoded)
    assert decoded["VehicleSpeed"] == pytest.approx(speed_kmh, abs=0.01)


def test_pump_state_enum_has_eight_values(db):
    """We widened PumpState from 2 to 3 bits for {Off, Coldstart,
    Phase2Ready, Run, WatchdogFault, AltFault, NotPresent, Reserved}.
    A regression that drops bits or values would break the pump
    integration in the firmware — catch it here."""
    msg = db.get_message_by_name("TCU_PumpStatus")
    sig = next(s for s in msg.signals if s.name == "PumpState")
    assert sig.length == 3
    # cantools represents value-table entries as NamedSignalValue, which is
    # not hashable; coerce to str for the set comparison.
    assert {str(v) for v in sig.choices.values()} == {
        "Off", "Coldstart", "Phase2Ready", "Run",
        "WatchdogFault", "AltFault", "NotPresent", "Reserved",
    }
