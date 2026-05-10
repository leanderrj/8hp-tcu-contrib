# Safety analysis — OI 8HP TCU

ISO 26262-3 Hazard Analysis and Risk Assessment for the in-Mechatronik
TCU. Reuses the framework from CarOS (`caros.safety.asil`) so the
hazard schema and ASIL lookup table are the same as Damien's CarOS
project.

## Contents

```
hara.py            12 hazards + 13 derived safety requirements
HARA_REPORT.txt    pre-generated formatted report (regen anytime)
```

## ASIL distribution

| ASIL | Count | Hazards |
|------|-------|---------|
| **D** | 1 | T002 — Park fails to engage (rollaway) |
| **C** | 3 | T001 Park-pawl-at-speed · T003 multi-element lockup · T004 R-while-moving |
| **B** | 3 | T005 stuck-on solenoid · T007 CAN stale · T009 aux pump LIN fault |
| **A** | 3 | T006 open-load solenoid · T010 speed-sensor mismatch · T011 brown-out reset |
| QM | 2 | T008 single-frame corruption · T012 torque-cut timeout |

The single ASIL D classification (T002 rollaway) is the load-bearing
one — it sets the integrity requirement for the Park subsystem and is
the reason `proposals/tcm_max22200_binding/SOLENOID_BINDING.md`
recommends Option A (two MAX22200 chips with the Park subsystem on a
dedicated chip / channel pair) over the cheaper alternatives that
share channels across safety boundaries.

## Run

```bash
# print formatted HARA + summary
python3 proposals/safety/hara.py

# validation: warnings (no test refs) + errors (uncovered hazards)
python3 proposals/safety/hara.py --check

# machine-readable export for downstream tooling
python3 proposals/safety/hara.py --json > hara.json
```

## What this is and isn't

**It is** a formal write-up of safety claims that already exist in our
implementation, mapped through the ISO 26262-3 S/E/C → ASIL lookup
table. Every hazard cites the firmware module(s) that mitigate it and
the test reference(s) that verify the mitigation.

**It is not** a complete ISO 26262 safety case. A real safety case
needs supporting documents:

- ISO 26262-4 system-level safety concept
- ISO 26262-6 software safety requirements with formal traceability
- ISO 26262-9 ASIL decomposition rationale
- ISO 26262-8 supporting processes (configuration, change management)

CarOS has a checklist for these in `caros/safety/iso_compliance.py`;
running the 8HP TCU through that checklist is a follow-up beyond the
scope of this file.

## Per-hazard cross-references

Every entry in `TCU_HARA` lists:

- **Mitigations** — pointers to specific firmware files and the
  decisions inside them (e.g. `shift_logic.cpp PlanNextStep walks
  single-element steps only`, `clutch_table.h static_assert`,
  `MAX22200 OCP fault detection per channel`).
- **Test refs** in `TCU_SAFETY_REQUIREMENTS` — names of the
  `make Test` C++ tests and `pytest` scenario tests that verify the
  requirement.

The `validate()` function flags any hazard with ASIL ≥ A that doesn't
have a derived requirement, and any requirement that doesn't list a
test reference. Currently both pass clean.

## How this connects to CarOS

CarOS is the supervisor (Pi-class, Python, telemetry + UX) and stays
in QM/A territory by deliberately not actuating powertrain. The TCU is
the actuator and lives in A/B/C/D territory. Same ISO framework,
different hazards, different integrity bands. They communicate via CAN
(documented in `proposals/dbc/zf8hp-tcu.dbc`).

`caros/safety/asil.py::CAROS_HARA` lists 10 hazards covering relays,
keyless entry, OBD, sentry mode, power management. Our `TCU_HARA`
lists 12 hazards covering the gearbox actuation. Combining the two
gives an integrated 22-hazard safety story for "openinverter EV
conversion stack supervised by CarOS."
