"""
HARA (Hazard Analysis and Risk Assessment) for the openinverter ZF 8HP TCU.

Uses the ISO 26262-3 framework from CarOS (`caros.safety.asil`). Each hazard
documents the operating situation, S/E/C parameters, derived ASIL, safety
goal, safe state, FTTI, and links to the firmware module(s) and test refs
that mitigate it.

This is a *systematic* re-do of the informal safety arguments scattered
across SOLENOID_BINDING.md and the in-code comments. The point is not to
add new safety claims — it is to make the ones we already made auditable
and testable.

Run from this directory:
    python3 hara.py             # print formatted HARA report
    python3 hara.py --check     # validation findings (warnings + errors)
    python3 hara.py --json      # machine-readable export

Tests in proposals/test_harness/tests/test_hara.py exercise the
validation rules and assert each hazard has a derived requirement and at
least one test reference.

Reference: ISO 26262-3:2018 Clauses 6 & 7.
"""
from __future__ import annotations

import sys
from pathlib import Path

# We borrow CarOS's framework rather than reimplementing — keeps a single
# source of truth for ASIL lookup tables and the dataclass schema. CarOS
# lives as a sibling repo at ~/Code/caros; if it's not on the path, adding
# the parent directory makes `caros.safety.asil` importable.
_CAROS = Path(__file__).resolve().parents[3] / "caros"
if _CAROS.exists() and str(_CAROS) not in sys.path:
    sys.path.insert(0, str(_CAROS))

from caros.safety.asil import (  # noqa: E402
    ASILLevel,
    Controllability,
    Exposure,
    HazardousEvent,
    SafetyRequirement,
    Severity,
    determine_asil,
)

# ---------------------------------------------------------------------------
# 8HP TCU hazard catalogue
# ---------------------------------------------------------------------------
#
# Numbering convention: T### so the IDs don't collide with CarOS's H### if
# the catalogues are ever merged. "T" for "Transmission".
#
# The numbers below are conservative — when the available evidence is
# ambiguous (e.g., exposure of a particular software fault), we round
# upward so the resulting ASIL doesn't under-classify the work.

TCU_HARA: list[HazardousEvent] = [
    # =============================================================
    # Park subsystem
    # =============================================================
    HazardousEvent(
        id="T001",
        name="Park pawl drops while driving",
        description=(
            "TCU energises the Park Hold solenoid (TCM pin 5) with the "
            "vehicle moving at speed, causing the parking pawl to attempt "
            "to drop into a rotating output shaft. Mechanical damage to "
            "the gearbox; on engagement, output shaft locks; possible "
            "skid / loss of control."
        ),
        operating_situation="Vehicle in motion above ~5 km/h",
        severity=Severity.S3,
        exposure=Exposure.E2,           # requires multiple software/sensor faults
        controllability=Controllability.C3,  # driver cannot react
        asil_level=determine_asil(Severity.S3, Exposure.E2, Controllability.C3),
        safety_goal=(
            "Park Hold solenoid shall not be energised when vehicle speed "
            "(VCU_VehicleInfo.VehicleSpeed) exceeds 5 km/h, regardless of "
            "VCU_GearRequest.TargetGear."
        ),
        safe_state=(
            "Both Park Hold and Park Release solenoids de-energised; "
            "AnyFault bit set on TCU_Status1; ShiftFaultCode published."
        ),
        ftti_ms=100,                    # ~1 frame at 100 Hz solenoid loop
        mitigations=[
            "park_lock.cpp: VehicleStationaryEnough() gate before Hold pulse",
            "Bind layer: refuse RequestEngaged(true) unless speed sensor agrees",
            "MAX22200 over-current detection on the Park channel",
            "Two-of-two sensor sanity (Pos1 ⊕ Pos2) before reporting engaged",
        ],
    ),
    HazardousEvent(
        id="T002",
        name="Park fails to engage when commanded (rollaway)",
        description=(
            "Driver selects Park, exits the vehicle. The TCU reports Park "
            "engaged on CAN but the pawl is in fact disengaged (sensor "
            "fault, mechanical jam, or commanded but not executed). "
            "Vehicle rolls, possibly into traffic or pedestrians."
        ),
        operating_situation=(
            "Vehicle stationary, driver requests Park before exit"
        ),
        severity=Severity.S3,
        exposure=Exposure.E3,
        controllability=Controllability.C3,
        asil_level=determine_asil(Severity.S3, Exposure.E3, Controllability.C3),
        safety_goal=(
            "TCU shall publish ParkLock=1 only when both park-position "
            "sensors confirm the engaged state."
        ),
        safe_state=(
            "ParkLock=0 published; AnyFault=1; driver alerted via VCU "
            "to engage parking brake."
        ),
        ftti_ms=500,
        mitigations=[
            "park_lock.cpp DecodeSenseState: both sensors must agree on "
            "Engaged before reporting park_lock_engaged=true",
            "EngageTimeout fault if pulse expires without sensor change",
            "VCU pairs ParkLock=1 with parking-brake check before ignition off",
        ],
    ),

    # =============================================================
    # Clutch / shift logic
    # =============================================================
    HazardousEvent(
        id="T003",
        name="Multi-element clutch engagement (driveline lockup)",
        description=(
            "Two clutches on different planetary stages are simultaneously "
            "energised, locking the driveline. At speed, this manifests as "
            "abrupt rear-wheel lock-up: skid, loss of stability, possible "
            "rear-end collision."
        ),
        operating_situation="Vehicle in any forward gear at speed",
        severity=Severity.S3,
        exposure=Exposure.E2,
        controllability=Controllability.C3,
        asil_level=determine_asil(Severity.S3, Exposure.E2, Controllability.C3),
        safety_goal=(
            "Only valid 3-of-5 clutch combinations from the published "
            "ZF 8HP engagement schedule shall be commanded; transitions "
            "shall change exactly one element at a time."
        ),
        safe_state=(
            "All clutches commanded off; ShiftFaultCode = "
            "ClutchTableInconsistent; gearbox reverts to mechanical neutral."
        ),
        ftti_ms=20,                    # one shift-tick
        mitigations=[
            "clutch_table.h static_assert: every adjacent gear pair "
            "differs by exactly one element",
            "shift_logic.cpp PlanNextStep: walks single-element steps only",
            "Solenoids::BuildFramesForChipMask refuses to enable >3 elements",
            "MAX22200 per-channel current monitoring; over-current → fault",
        ],
    ),
    HazardousEvent(
        id="T004",
        name="Reverse engaged while moving forward at speed",
        description=(
            "Driver pushes shifter to R while rolling forward (e.g. "
            "hill-roll mistake). Reverse clutch engages against forward "
            "rotation; gearbox damage; abrupt deceleration; possible "
            "rear-end collision risk."
        ),
        operating_situation="Vehicle rolling forward >5 km/h",
        severity=Severity.S3,
        exposure=Exposure.E2,
        controllability=Controllability.C3,
        asil_level=determine_asil(Severity.S3, Exposure.E2, Controllability.C3),
        safety_goal=(
            "Reverse engagement shall only proceed via Neutral and only "
            "when output-shaft RPM indicates vehicle is stationary or "
            "moving rearward."
        ),
        safe_state="Hold current gear; reject the request; raise fault.",
        ftti_ms=50,
        mitigations=[
            "shift_logic.cpp PlanNextStep: forward → neutral → reverse path",
            "Bind layer: refuse R if output_shaft_rpm > 0 with vehicle",
            "VCU enforces brake-pedal-pressed precondition for R",
        ],
    ),
    HazardousEvent(
        id="T005",
        name="Stuck-on solenoid (one element won't release)",
        description=(
            "After a shift, an outgoing clutch fails to drain (stuck "
            "valve, stuck solenoid, broken return spring). Two clutches "
            "active across stages — same hazard surface as T003 but "
            "introduced post-shift rather than at command."
        ),
        operating_situation="During or shortly after a shift event",
        severity=Severity.S3,
        exposure=Exposure.E2,
        controllability=Controllability.C2,
        asil_level=determine_asil(Severity.S3, Exposure.E2, Controllability.C2),
        safety_goal=(
            "Solenoid-current readback shall confirm de-energisation "
            "within the overlap window; mismatch shall trigger limp."
        ),
        safe_state=(
            "All solenoids commanded off; ShiftLogic enters Limp; "
            "AnyFault and FaultBits[OverCurrent] published."
        ),
        ftti_ms=120,                   # one overlap window
        mitigations=[
            "MAX22200 OCP fault detection per channel",
            "Solenoids::DecodeFaults → TCU_Status2.FaultBits bit 7",
            "shift_logic.cpp Limp state on any clutch fault",
            "FaultStatus polled at end of every Overlap phase",
        ],
    ),
    HazardousEvent(
        id="T006",
        name="Open-load solenoid (commanded clutch fails to engage)",
        description=(
            "Solenoid wiring or coil open-circuited; commanded clutch "
            "draws no current. Resulting clutch combination is invalid; "
            "powerflow is lost or rerouted unpredictably. Vehicle "
            "decelerates abruptly under load."
        ),
        operating_situation="Any shift event or in-gear operation",
        severity=Severity.S2,
        exposure=Exposure.E2,
        controllability=Controllability.C2,
        asil_level=determine_asil(Severity.S2, Exposure.E2, Controllability.C2),
        safety_goal=(
            "MAX22200 open-load detection shall be enabled on every "
            "commanded channel; OLF shall be propagated to CAN within "
            "100 ms."
        ),
        safe_state=(
            "Pre-shift: refuse the shift, hold current gear. "
            "In-gear: limp to nearest valid gear; FaultBits[SolOpen]=1."
        ),
        ftti_ms=100,
        mitigations=[
            "max22200_regs.h CFG_FAULT_DISABLE_OLF kept at 0 (active)",
            "Solenoids::FaultsToTcuStatus2Bits maps OLF → bit 0",
            "shift_logic.cpp: pre-flight current check before TorqueCut",
        ],
    ),

    # =============================================================
    # Communication / supervisor
    # =============================================================
    HazardousEvent(
        id="T007",
        name="VCU CAN frame stale or absent",
        description=(
            "VCU stops publishing VCU_GearRequest (cable break, VCU "
            "reset, brown-out). TCU has no driver-intent input; "
            "ambiguity about whether to hold gear, drop to Neutral, "
            "or fall to Limp."
        ),
        operating_situation="Vehicle in any state; CAN bus disturbance",
        severity=Severity.S2,
        exposure=Exposure.E3,
        controllability=Controllability.C2,
        asil_level=determine_asil(Severity.S2, Exposure.E3, Controllability.C2),
        safety_goal=(
            "On VCU_GearRequest absence > 200 ms, TCU shall hold the "
            "current gear and publish FaultBits[CanStale]=1. TCU shall "
            "NOT auto-enter Neutral or Park, which could disengage "
            "drivetrain at speed."
        ),
        safe_state=(
            "Hold current gear; ShiftActive=0; AnyFault=1; "
            "TcuState=Limp if stale persists > 1 s."
        ),
        ftti_ms=200,
        mitigations=[
            "VCU_GearRequest counter (Counter520) advance check",
            "Per-frame staleness timer; FaultBits[CanStale] at 200 ms",
            "Hold-gear-on-loss policy enforced in bind layer",
        ],
    ),
    HazardousEvent(
        id="T008",
        name="Spurious gear request from corrupted CAN frame",
        description=(
            "Bit error or hostile injection produces a VCU_GearRequest "
            "with TargetGear ≠ current gear. Without integrity checks, "
            "TCU initiates an unintended shift."
        ),
        operating_situation="Vehicle in any state; CAN bus noise/attack",
        severity=Severity.S2,
        exposure=Exposure.E1,
        controllability=Controllability.C2,
        asil_level=determine_asil(Severity.S2, Exposure.E1, Controllability.C2),
        safety_goal=(
            "Gear-change requests shall require N consecutive identical "
            "TargetGear values before action; counter rollback shall "
            "trigger CanStale fault."
        ),
        safe_state="Hold current gear; raise CanStale fault.",
        ftti_ms=50,
        mitigations=[
            "Counter520 monotonicity check (low nibble +1 modulo 16)",
            "Two-frame consensus on TargetGear before initiating shift",
            "Future: per-ID CRC8 (same scheme as F30_Lever / iX4_Lever)",
        ],
    ),

    # =============================================================
    # Aux pump (HZ hybrid 'box only)
    # =============================================================
    HazardousEvent(
        id="T009",
        name="Aux 12 V pump fails while ICE off (hybrid only)",
        description=(
            "On HZ hybrid 'boxes the aux pump maintains line pressure "
            "while the ICE is stopped. Pump LIN failure → line pressure "
            "decays → clutches slip → unintended Neutral or staged "
            "engagement loss while moving."
        ),
        operating_situation="Hybrid 8HP, ICE stopped, vehicle moving",
        severity=Severity.S2,
        exposure=Exposure.E3,
        controllability=Controllability.C2,
        asil_level=determine_asil(Severity.S2, Exposure.E3, Controllability.C2),
        safety_goal=(
            "Pump fault shall trigger Limp before line pressure drops "
            "below the minimum needed to hold the engaged clutch set."
        ),
        safe_state=(
            "VCU informed that ICE restart is required to maintain "
            "powerflow; FaultBits[LinComm]=1; PumpState reflects fault."
        ),
        ftti_ms=500,
        mitigations=[
            "lin_pump.py / firmware LIN master watchdog (byte-6 echo)",
            "PumpRetryCount published on TCU_PumpStatus",
            "TCU_PumpStatus.PumpLinFault propagation to FaultBits",
            "Bind layer: request VCU to start ICE on PumpLinFault",
        ],
    ),

    # =============================================================
    # Sensor / boot
    # =============================================================
    HazardousEvent(
        id="T010",
        name="Speed sensor (input or output) fault",
        description=(
            "Input or output shaft speed sensor reports zero or stuck "
            "value while vehicle is moving. TCU has no slip feedback "
            "during shifts; harsh shifts or wrong gear inferred."
        ),
        operating_situation="Vehicle moving in any forward gear",
        severity=Severity.S2,
        exposure=Exposure.E2,
        controllability=Controllability.C2,
        asil_level=determine_asil(Severity.S2, Exposure.E2, Controllability.C2),
        safety_goal=(
            "Speed sensor plausibility shall be cross-checked against "
            "the gear-ratio prediction (output_rpm × ratio ≈ input_rpm "
            "within ±10 % when no slip). Persistent mismatch shall "
            "fault."
        ),
        safe_state=(
            "Hold gear; refuse new shifts; FaultBits[SpeedSensor]=1; "
            "VCU asked to fall back to torque-limited mode."
        ),
        ftti_ms=200,
        mitigations=[
            "Cross-check input vs output RPM via clutch_table ratio",
            "Cross-check against VCU MotorRPM (where applicable)",
            "FaultBits[SpeedSensor] on persistent mismatch",
        ],
    ),
    HazardousEvent(
        id="T011",
        name="TCU brown-out / unexpected reset while driving",
        description=(
            "Power supply transient resets the STM32. All MAX22200 "
            "outputs go high-Z; clutches drain; gearbox enters "
            "mechanical neutral; brief loss of powerflow at speed."
        ),
        operating_situation="Vehicle moving; 12 V supply transient",
        severity=Severity.S2,
        exposure=Exposure.E2,
        controllability=Controllability.C2,
        asil_level=determine_asil(Severity.S2, Exposure.E2, Controllability.C2),
        safety_goal=(
            "TCU shall re-engage the previously-held gear within 500 ms "
            "of reset, or report FaultBits[Reset] and stay in Limp."
        ),
        safe_state=(
            "Mechanical neutral during reset window (default-safe MAX22200 "
            "high-Z); fast re-engagement once boot completes."
        ),
        ftti_ms=500,
        mitigations=[
            "STM32 brown-out detector configured at 4.4 V",
            "Last-known gear persisted before any state change",
            "MAX22200 default high-Z = mechanical neutral = safe",
            "Boot-time park-position sensor read decides Park vs gear",
        ],
    ),

    # =============================================================
    # Quality / driver-experience hazards (ASIL QM range)
    # =============================================================
    HazardousEvent(
        id="T012",
        name="Torque-cut handshake timeout (harsh shift)",
        description=(
            "VCU never asserts TorqueCutAck during the budget window. "
            "TCU either shifts under torque (clutch wear, lurch) or "
            "aborts. Driver discomfort but no safety hazard at rated "
            "engine torque."
        ),
        operating_situation="Any in-drive upshift or downshift",
        severity=Severity.S1,
        exposure=Exposure.E3,
        controllability=Controllability.C1,
        asil_level=determine_asil(Severity.S1, Exposure.E3, Controllability.C1),
        safety_goal=(
            "On TorqueCutAck timeout, the shift shall abort and the "
            "current gear shall be held."
        ),
        safe_state="Current gear held; ShiftFaultCode = TorqueCutTimeout.",
        ftti_ms=50,
        mitigations=[
            "shift_logic.cpp TorqueCut phase has explicit timeout budget",
            "test_shift_logic.cpp: TestTorqueCutTimeoutAbortsShift",
            "Repeated timeouts → soft-Limp (skip torque-blended shifts)",
        ],
    ),
]


# ---------------------------------------------------------------------------
# Derived safety requirements
# ---------------------------------------------------------------------------

TCU_SAFETY_REQUIREMENTS: list[SafetyRequirement] = [
    # Park ----------------------------------------------------------
    SafetyRequirement(
        id="STR001",
        hazard_ref="T001",
        description=(
            "Park Hold solenoid shall not be energised while reported "
            "vehicle speed exceeds 5 km/h. Speed source: "
            "VCU_VehicleInfo.VehicleSpeed in DBC."
        ),
        asil_level=ASILLevel.D,
        verification_method="testing",
        status="verified",
        test_refs=[
            "T_PARK_ENGAGE_BLOCKED_BY_MOTION",
            "scenarios.test_park_safety::test_park_engage_blocked_at_speed",
        ],
    ),
    SafetyRequirement(
        id="STR002",
        hazard_ref="T002",
        description=(
            "TCU_Status1.ParkLock shall be set to 1 only when "
            "park-position sensors Pos1 ⊕ Pos2 reads as Engaged."
        ),
        asil_level=ASILLevel.C,
        verification_method="testing",
        status="verified",
        test_refs=[
            "T_PARK_SENSOR_BOTH_HIGH_IS_FAULT",
            "T_PARK_SENSOR_BOTH_LOW_IS_FAULT",
        ],
    ),
    SafetyRequirement(
        id="STR003",
        hazard_ref="T001,T002",
        description=(
            "Park Hold and Park Release solenoids shall NEVER be "
            "simultaneously energised."
        ),
        asil_level=ASILLevel.D,
        verification_method="testing",
        status="verified",
        test_refs=[
            "T_PARK_MUTUAL_EXCLUSION_5000_TICKS",
        ],
    ),
    # Clutch / shift -------------------------------------------------
    SafetyRequirement(
        id="STR004",
        hazard_ref="T003",
        description=(
            "Adjacent forward gears in the clutch engagement table "
            "shall differ by exactly one shift element."
        ),
        asil_level=ASILLevel.D,
        verification_method="analysis",
        status="verified",
        test_refs=[
            "T_CLUTCH_TABLE_SINGLE_ELEMENT_PER_SHIFT",
            "static_assert in clutch_table.h",
        ],
    ),
    SafetyRequirement(
        id="STR005",
        hazard_ref="T003",
        description=(
            "Each forward gear shall engage exactly three of the five "
            "shift elements; reverse shall engage exactly three; "
            "neutral shall engage zero."
        ),
        asil_level=ASILLevel.C,
        verification_method="analysis",
        status="verified",
        test_refs=[
            "T_CLUTCH_TABLE_THREE_ELEMENTS_PER_GEAR",
            "static_assert in clutch_table.h",
        ],
    ),
    SafetyRequirement(
        id="STR006",
        hazard_ref="T004",
        description=(
            "Forward-to-reverse and reverse-to-forward gear changes "
            "shall walk through Neutral as an explicit intermediate "
            "step, not engage R clutches directly."
        ),
        asil_level=ASILLevel.C,
        verification_method="testing",
        status="verified",
        test_refs=[
            "T_FORWARD_TO_REVERSE_GOES_VIA_NEUTRAL",
            "scenarios.test_drive_cycle::test_forward_to_reverse_at_rest",
        ],
    ),
    SafetyRequirement(
        id="STR007",
        hazard_ref="T005,T006",
        description=(
            "MAX22200 fault detection (open-load, short-to-supply, "
            "over-current) shall be enabled on every commanded channel "
            "and propagated to TCU_Status2.FaultBits within 100 ms of "
            "fault onset."
        ),
        asil_level=ASILLevel.C,
        verification_method="testing",
        status="verified",
        test_refs=[
            "T_SOLENOID_FAULT_DECODE_PER_CHANNEL",
            "T_SOLENOID_FAULTS_TO_TCU_STATUS2_BITS",
        ],
    ),
    # Communication --------------------------------------------------
    SafetyRequirement(
        id="STR008",
        hazard_ref="T007",
        description=(
            "On VCU_GearRequest absence longer than 200 ms the TCU "
            "shall hold the current gear and set "
            "TCU_Status2.FaultBits[CanStale]=1. The TCU shall NOT "
            "automatically engage Neutral or Park."
        ),
        asil_level=ASILLevel.B,
        verification_method="testing",
        status="reviewed",
        test_refs=[
            "scenarios.test_can_loss::test_vcu_silence_holds_gear",
        ],
    ),
    SafetyRequirement(
        id="STR009",
        hazard_ref="T008",
        description=(
            "VCU_GearRequest counter shall advance by exactly +1 "
            "modulo 16 per frame; rollback or stall shall raise "
            "FaultBits[CanStale]."
        ),
        asil_level=ASILLevel.A,
        verification_method="testing",
        status="reviewed",
        test_refs=[
            "scenarios.test_can_loss::test_counter_rollback_raises_fault",
        ],
    ),
    # Pump -----------------------------------------------------------
    SafetyRequirement(
        id="STR010",
        hazard_ref="T009",
        description=(
            "On any aux pump LIN watchdog or alt-fault, the TCU shall "
            "request the VCU to restart the prime mover (ICE) within "
            "500 ms; on hybrid 'boxes the gear set shall be held until "
            "line pressure recovers."
        ),
        asil_level=ASILLevel.B,
        verification_method="testing",
        status="verified",
        test_refs=[
            "T_DROPPED_ECHO_BYTE_CAUSES_FAULT",
            "T_RECOVERY_PATH_AFTER_FAULT",
        ],
    ),
    # Sensors --------------------------------------------------------
    SafetyRequirement(
        id="STR011",
        hazard_ref="T010",
        description=(
            "Input-shaft and output-shaft RPMs shall be cross-checked "
            "against the engaged-gear ratio every 100 ms; deviations "
            "exceeding 10 % shall set FaultBits[SpeedSensor]."
        ),
        asil_level=ASILLevel.B,
        verification_method="testing",
        status="draft",
        test_refs=[
            "scenarios.test_speed_sensor::test_ratio_mismatch_raises_fault",
        ],
    ),
    # Reset ----------------------------------------------------------
    SafetyRequirement(
        id="STR012",
        hazard_ref="T011",
        description=(
            "On boot, the TCU shall re-engage the gear most recently "
            "persisted to non-volatile storage within 500 ms, provided "
            "park-position sensors and shaft speeds are consistent."
        ),
        asil_level=ASILLevel.B,
        verification_method="testing",
        status="draft",
        test_refs=[
            "scenarios.test_brownout::test_re_engages_last_gear_after_reset",
        ],
    ),
    # Quality (no escalation possible — kept for completeness) ------
    SafetyRequirement(
        id="STR013",
        hazard_ref="T012",
        description=(
            "TorqueCutTimeout shall abort the in-flight shift and "
            "hold the current gear. Three timeouts within 60 s shall "
            "trigger soft-Limp (no torque-blended shifts)."
        ),
        asil_level=ASILLevel.A,
        verification_method="testing",
        status="verified",
        test_refs=[
            "T_TORQUE_CUT_TIMEOUT_ABORTS_SHIFT",
        ],
    ),
]


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

def generate_report() -> str:
    """Same shape as caros.safety.asil.generate_hara_report() but for TCU."""
    from datetime import date as _date
    lines: list[str] = []
    lines.append("=" * 90)
    lines.append("HAZARD ANALYSIS AND RISK ASSESSMENT (HARA) — OI 8HP TCU")
    lines.append(f"Generated: {_date.today().isoformat()}")
    lines.append("Reference: ISO 26262-3:2018 Clause 7")
    lines.append(f"Framework: caros.safety.asil ({_CAROS})")
    lines.append("=" * 90)
    lines.append("")

    for h in TCU_HARA:
        lines.append(f"--- {h.id}: {h.name} ---")
        lines.append(f"  Description     : {h.description}")
        lines.append(f"  Operating sit.  : {h.operating_situation}")
        lines.append(f"  Severity        : {h.severity.name} ({h.severity.value})")
        lines.append(f"  Exposure        : {h.exposure.name} ({h.exposure.value})")
        lines.append(f"  Controllability : {h.controllability.name} ({h.controllability.value})")
        lines.append(f"  ASIL            : {h.asil_level.name}")
        lines.append(f"  Safety goal     : {h.safety_goal}")
        lines.append(f"  Safe state      : {h.safe_state}")
        lines.append(f"  FTTI            : {h.ftti_ms} ms")
        lines.append(f"  Mitigations     :")
        for m in h.mitigations:
            lines.append(f"    - {m}")
        lines.append("")

    lines.append("-" * 90)
    lines.append("SUMMARY")
    lines.append("-" * 90)
    lines.append(f"{'ID':<6} {'Name':<46} {'S':>2} {'E':>2} {'C':>2}  {'ASIL':<6}")
    lines.append("-" * 90)
    for h in TCU_HARA:
        lines.append(
            f"{h.id:<6} {h.name:<46} {h.severity.name:>2} {h.exposure.name:>2} "
            f"{h.controllability.name:>2}  {h.asil_level.name:<6}"
        )
    lines.append("")

    counts: dict[str, int] = {}
    for h in TCU_HARA:
        counts[h.asil_level.name] = counts.get(h.asil_level.name, 0) + 1
    lines.append(f"ASIL distribution: {counts}")
    lines.append("")
    return "\n".join(lines)


def validate() -> list[dict]:
    """Same shape as CarOS validate_safety_requirements() but local."""
    findings: list[dict] = []
    hazard_ids = {h.id for h in TCU_HARA}
    covered: set[str] = set()

    for sr in TCU_SAFETY_REQUIREMENTS:
        if not sr.test_refs:
            findings.append({"level": "warning", "item": sr.id,
                              "message": f"{sr.id} has no test references."})
        for ref in sr.hazard_ref.split(","):
            ref = ref.strip()
            if ref not in hazard_ids:
                findings.append({"level": "error", "item": sr.id,
                                  "message": f"{sr.id} references unknown hazard '{ref}'."})
            else:
                covered.add(ref)

    for hid in hazard_ids:
        if hid not in covered:
            findings.append({"level": "warning", "item": hid,
                              "message": f"Hazard {hid} has no derived requirement."})

    asil_by_id = {h.id: h.asil_level for h in TCU_HARA}
    for hid, asil in asil_by_id.items():
        if asil.value >= ASILLevel.A.value and hid not in covered:
            findings.append({"level": "error", "item": hid,
                              "message": f"Hazard {hid} is {asil.name} but has no requirement."})

    if not findings:
        findings.append({"level": "info", "item": "ALL",
                          "message": "All safety requirements pass validation."})
    return findings


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    if args.check:
        for f in validate():
            print(f"[{f['level']:>7}] {f['item']:<8} {f['message']}")
    elif args.json:
        from dataclasses import asdict
        import json
        out = {
            "hara": [
                {**asdict(h),
                 "severity": h.severity.name,
                 "exposure": h.exposure.name,
                 "controllability": h.controllability.name,
                 "asil_level": h.asil_level.name}
                for h in TCU_HARA
            ],
            "requirements": [
                {**asdict(s), "asil_level": s.asil_level.name}
                for s in TCU_SAFETY_REQUIREMENTS
            ],
        }
        print(json.dumps(out, indent=2))
    else:
        print(generate_report())
