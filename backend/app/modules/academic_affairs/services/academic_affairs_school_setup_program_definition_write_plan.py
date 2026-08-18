"""INT pure write-plan contract for ordinary Program DEFINITION confirmation.

This is not a writer. It freezes what a future shared-schema writer may persist
after the complete Program preflight is green. In particular it must NOT call the
interactive ``create_new_version`` flow, because that flow clones predecessor
children while import CREATE must persist the already-reconciled source snapshot.

Hard boundaries:
- CREATE always plans a DRAFT Program version;
- vN inherits only the proven series/prev relationship, never predecessor child
  definitions;
- REUSE plans zero writes;
- BINDING rows plan zero writes in DEFINITION phase;
- Major.education_years and Course facts are assertions/authorities, not import
  write targets;
- execution remains blocked until shared ``AaProgram.series_key`` and
  ``AaProgramCourse.formation_mode`` schema are present.
"""
from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping
from decimal import Decimal

from .academic_affairs_school_setup_import_contract import (
    PROGRAM_GROUP_BINDING,
    PROGRAM_GROUP_COURSE,
    PROGRAM_GROUP_CREDIT_REQUIREMENT,
    PROGRAM_GROUP_GRADUATION,
    PROGRAM_GROUP_MAIN,
    PROGRAM_GROUP_PRACTICE,
    RECONCILIATION_CREATE,
    RECONCILIATION_REUSE,
)
from .academic_affairs_school_setup_program_binding_policy import PHASE_DEFINITION
from .academic_affairs_school_setup_program_snapshot_response_guard import (
    guard_course_snapshots,
)

SCHEMA_PREREQUISITES = (
    "AaProgram.series_key",
    "AaProgramCourse.formation_mode",
)


def _decimal(value: object) -> Decimal:
    return value if isinstance(value, Decimal) else Decimal(str(value))


def _course_index(
    course_snapshots: Iterable[Mapping[str, object]],
    requested_keys: Iterable[str],
) -> dict[str, dict]:
    rows = guard_course_snapshots(course_snapshots, requested_keys)
    result: dict[str, dict] = {}
    for row in rows:
        code = str(row.get("courseCode") or "").strip().upper()
        version = int(row.get("version") or 0)
        key = f"{code}@v{version}"
        if key in result:
            raise ValueError(f"duplicate Course write-plan snapshot: {key}")
        course_id = int(row.get("courseId") or 0)
        course_name = str(row.get("courseName") or "").strip()
        if course_id <= 0 or not course_name:
            raise ValueError(f"Course write-plan snapshot missing courseId/courseName: {key}")
        result[key] = dict(row, courseId=course_id, courseName=course_name)
    return result


def _require_definition_result(preflight_result: Mapping[str, object]) -> list[dict]:
    if not bool(preflight_result.get("programPreflightSafe")):
        raise ValueError("Program definition write plan requires a green full preflight")
    if str(preflight_result.get("stage") or "").strip().upper() != "READY":
        raise ValueError("Program definition write plan requires READY stage")
    phase = str((preflight_result.get("binding") or {}).get("phase") or "").strip().upper()
    if phase != PHASE_DEFINITION:
        raise ValueError("Program definition write plan is DEFINITION-phase only")
    actions = [dict(item) for item in (preflight_result.get("actions") or ())]
    seen: set[str] = set()
    for action in actions:
        program_key = str(action.get("programKey") or "").strip()
        if not program_key or program_key in seen:
            raise ValueError("Program definition preflight actions must have unique programKey")
        seen.add(program_key)
        decision = str(action.get("action") or "").strip().upper()
        if decision not in {RECONCILIATION_CREATE, RECONCILIATION_REUSE}:
            raise ValueError(f"unsafe Program definition action in green preflight: {decision}")
    return actions


def build_program_definition_write_plan(
    normalized_rows: Iterable[Mapping[str, object]],
    preflight_result: Mapping[str, object],
    *,
    course_snapshots: Iterable[Mapping[str, object]],
) -> dict:
    """Build an immutable-intent plan; caller still owns transaction and writes."""
    rows = [dict(row) for row in normalized_rows]
    actions = _require_definition_result(preflight_result)

    rows_by_program: dict[str, list[dict]] = defaultdict(list)
    requested_course_keys: set[str] = set()
    for row in rows:
        program_key = str(row.get("programKey") or "").strip()
        if not program_key:
            raise ValueError("normalized Program row missing programKey")
        rows_by_program[program_key].append(row)
        if str(row.get("logicalGroup") or "").strip().upper() == PROGRAM_GROUP_COURSE:
            course_key = str((row.get("payload") or {}).get("courseKey") or "").strip()
            if not course_key:
                raise ValueError("normalized ProgramCourse row missing courseKey")
            requested_course_keys.add(course_key)

    courses = _course_index(course_snapshots, requested_course_keys)
    plans: list[dict] = []
    for action in sorted(actions, key=lambda item: str(item.get("programKey") or "")):
        program_key = str(action["programKey"])
        decision = str(action["action"]).upper()
        if decision == RECONCILIATION_REUSE:
            program_id = str(action.get("programId") or "").strip()
            if not program_id or not bool(action.get("definitionReconciled")):
                raise ValueError(f"REUSE write plan requires reconciled programId: {program_key}")
            plans.append({
                "programKey": program_key,
                "action": RECONCILIATION_REUSE,
                "programId": program_id,
                "writeCount": 0,
                "writes": {},
            })
            continue

        if str(action.get("createStatus") or "").strip().upper() != "DRAFT":
            raise ValueError(f"CREATE write plan must remain DRAFT: {program_key}")
        program_rows = rows_by_program.get(program_key, [])
        mains = [row for row in program_rows if str(row.get("logicalGroup") or "").upper() == PROGRAM_GROUP_MAIN]
        if len(mains) != 1:
            raise ValueError(f"CREATE write plan requires exactly one MAIN row: {program_key}")
        main = dict(mains[0].get("payload") or {})

        credit_requirements = sorted(
            [
                dict(row.get("payload") or {})
                for row in program_rows
                if str(row.get("logicalGroup") or "").upper() == PROGRAM_GROUP_CREDIT_REQUIREMENT
            ],
            key=lambda item: str(item.get("module") or ""),
        )
        requirement_json = {
            "creditStructure": [
                {
                    "module": str(item.get("module") or "").strip(),
                    "creditTarget": _decimal(item.get("creditTarget") or 0),
                }
                for item in credit_requirements
            ]
        }

        course_writes = []
        for row in sorted(
            [row for row in program_rows if str(row.get("logicalGroup") or "").upper() == PROGRAM_GROUP_COURSE],
            key=lambda item: (int((item.get("payload") or {}).get("openTermNo") or 0), str((item.get("payload") or {}).get("courseKey") or "")),
        ):
            payload = dict(row.get("payload") or {})
            course_key = str(payload.get("courseKey") or "")
            catalog = courses.get(course_key)
            if catalog is None:
                raise ValueError(f"Course write-plan snapshot missing: {course_key}")
            catalog_credit = _decimal(catalog.get("credit") or 0)
            explicit_credit = payload.get("creditSnapshot")
            if explicit_credit is not None and _decimal(explicit_credit) != catalog_credit:
                raise ValueError(f"Course credit changed after preflight: {course_key}")
            course_writes.append({
                "courseId": int(catalog["courseId"]),
                "courseKey": course_key,
                "courseName": str(catalog["courseName"]),
                "openTermNo": int(payload.get("openTermNo") or 0),
                "module": str(payload.get("module") or "").strip(),
                "formationMode": str(payload.get("formationMode") or "").strip().upper(),
                "creditSnapshot": catalog_credit,
            })

        practice_writes = [
            dict(row.get("payload") or {})
            for row in sorted(
                [row for row in program_rows if str(row.get("logicalGroup") or "").upper() == PROGRAM_GROUP_PRACTICE],
                key=lambda item: (int((item.get("payload") or {}).get("sortOrder") or 0), str((item.get("payload") or {}).get("segmentName") or "")),
            )
        ]
        graduation_writes = [
            dict(row.get("payload") or {})
            for row in sorted(
                [row for row in program_rows if str(row.get("logicalGroup") or "").upper() == PROGRAM_GROUP_GRADUATION],
                key=lambda item: (int((item.get("payload") or {}).get("sortOrder") or 0), str((item.get("payload") or {}).get("category") or ""), str((item.get("payload") or {}).get("content") or "")),
            )
        ]

        program_write = {
            "seriesKey": str(main.get("programSeriesKey") or "").strip().upper(),
            "version": int(main.get("programVersion") or 0),
            "programName": str(main.get("programName") or "").strip(),
            "majorId": int(main.get("majorId") or 0),
            "gradeYear": str(main.get("gradeYear") or "").strip(),
            "totalCredits": _decimal(main.get("totalCredits") or 0),
            "requirementJson": requirement_json,
            "prevProgramId": str(action.get("predecessorProgramId") or ""),
            "status": "DRAFT",
        }
        if not program_write["seriesKey"] or program_write["version"] <= 0:
            raise ValueError(f"CREATE write plan missing series/version: {program_key}")

        writes = {
            "program": program_write,
            "courses": course_writes,
            "practices": practice_writes,
            "graduationRequirements": graduation_writes,
            "bindings": [],
        }
        plans.append({
            "programKey": program_key,
            "action": RECONCILIATION_CREATE,
            "programId": "",
            "writeCount": 1 + len(course_writes) + len(practice_writes) + len(graduation_writes),
            "writes": writes,
        })

    return {
        "phase": PHASE_DEFINITION,
        "executable": False,
        "schemaPrerequisites": list(SCHEMA_PREREQUISITES),
        "programPlans": plans,
    }
