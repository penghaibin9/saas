"""INT evidence gate for the future shared Program schema migration.

This module does not run Alembic or mutate ORM models. It requires three
independent inventories before shared backfill is permitted:
1. canonical Program prev_version series proof with an explicit Program->series
   ``proposedBackfill`` mapping;
2. TeachingTask runtime formation integrity;
3. explicit ProgramCourse formation provenance.

TeachingTask evidence is deliberately not accepted as ProgramCourse plan truth.
Nullable expand remains separate from historical backfill, while NOT NULL and
uniqueness tightening always require a later post-backfill evidence gate.
"""
from __future__ import annotations

from collections.abc import Mapping

PROGRAM_COURSE_PROVENANCE_PROVEN = "EXPLICIT_PROVENANCE_PROVEN"


def _mapping(value: object, *, field: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field} must be an inventory report object")
    return value


def _required_bool(report: Mapping[str, object], field: str, *, owner: str) -> bool:
    if field not in report or not isinstance(report[field], bool):
        raise ValueError(f"{owner}.{field} must be boolean")
    return bool(report[field])


def _required_list(report: Mapping[str, object], field: str, *, owner: str) -> list:
    value = report.get(field)
    if not isinstance(value, list):
        raise ValueError(f"{owner}.{field} must be a list")
    return list(value)


def _required_text(report: Mapping[str, object], field: str, *, owner: str) -> str:
    text = str(report.get(field) or "").strip().upper()
    if not text:
        raise ValueError(f"{owner}.{field} is required")
    return text


def _non_negative_count(report: Mapping[str, object], field: str, *, owner: str) -> int:
    if field not in report:
        raise ValueError(f"{owner}.{field} is required")
    try:
        value = int(report[field])
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{owner}.{field} must be a non-negative integer") from exc
    if value < 0:
        raise ValueError(f"{owner}.{field} must be a non-negative integer")
    return value


def _canonical_series_evidence(series: Mapping[str, object]) -> tuple[bool, int, list[dict], list[dict]]:
    safe = _required_bool(series, "migrationPreflightSafe", owner="program_series_inventory")
    total_rows = _non_negative_count(series, "totalRows", owner="program_series_inventory")
    blockers = [dict(item) for item in _required_list(
        series, "blockers", owner="program_series_inventory"
    )]
    proposed = [dict(item) for item in _required_list(
        series, "proposedBackfill", owner="program_series_inventory"
    )]

    if safe and blockers:
        raise ValueError("program_series_inventory safe report cannot contain blockers")
    if not safe and proposed:
        raise ValueError("program_series_inventory dirty report must not contain partial proposedBackfill")

    seen_program_ids: set[int] = set()
    seen_identity: set[tuple[int, str, int]] = set()
    for item in proposed:
        try:
            program_id = int(item.get("programId"))
            tenant_id = int(item.get("tenantId"))
            version = int(item.get("version"))
        except (TypeError, ValueError) as exc:
            raise ValueError("program_series_inventory proposedBackfill has invalid identifiers") from exc
        series_key = str(item.get("seriesKey") or "").strip()
        if program_id <= 0 or tenant_id <= 0 or version <= 0 or not series_key:
            raise ValueError("program_series_inventory proposedBackfill has invalid identifiers")
        if program_id in seen_program_ids:
            raise ValueError("program_series_inventory proposedBackfill duplicates programId")
        identity = (tenant_id, series_key, version)
        if identity in seen_identity:
            raise ValueError("program_series_inventory proposedBackfill collides on tenant+seriesKey+version")
        seen_program_ids.add(program_id)
        seen_identity.add(identity)

    if safe and len(proposed) != total_rows:
        raise ValueError(
            "program_series_inventory safe report must provide proposedBackfill for every Program row"
        )
    return safe, total_rows, blockers, proposed


def evaluate_shared_program_schema_gate(
    *,
    program_series_inventory: Mapping[str, object],
    task_formation_inventory: Mapping[str, object],
    program_course_formation_inventory: Mapping[str, object],
) -> dict:
    """Return fail-closed migration phase permissions from independent evidence."""
    series = _mapping(program_series_inventory, field="program_series_inventory")
    task_formation = _mapping(task_formation_inventory, field="task_formation_inventory")
    program_course = _mapping(
        program_course_formation_inventory,
        field="program_course_formation_inventory",
    )

    series_safe, total_programs, series_blockers, proposed_backfill = _canonical_series_evidence(series)
    task_safe = _required_bool(
        task_formation, "migrationPreflightSafe", owner="task_formation_inventory"
    )
    program_course_safe = _required_bool(
        program_course,
        "migrationPreflightSafe",
        owner="program_course_formation_inventory",
    )
    program_course_policy = _required_text(
        program_course,
        "programCourseFormationBackfill",
        owner="program_course_formation_inventory",
    )

    unresolved_tasks = _non_negative_count(
        task_formation, "unresolvedTaskCount", owner="task_formation_inventory"
    )
    unresolved_program_courses = _non_negative_count(
        program_course,
        "unresolvedProgramCourseCount",
        owner="program_course_formation_inventory",
    )

    task_blockers = dict(task_formation.get("blockerCounts") or {})
    task_relationship_blockers = dict(
        task_formation.get("relationshipBlockerCounts") or {}
    )
    program_course_blockers = dict(program_course.get("blockerCounts") or {})

    series_backfill_allowed = bool(
        series_safe
        and not series_blockers
        and len(proposed_backfill) == total_programs
    )
    task_formation_evidence_clean = bool(
        task_safe
        and unresolved_tasks == 0
        and not task_blockers
        and not task_relationship_blockers
    )
    program_course_backfill_allowed = bool(
        program_course_safe
        and unresolved_program_courses == 0
        and not program_course_blockers
        and program_course_policy == PROGRAM_COURSE_PROVENANCE_PROVEN
    )

    blockers: list[dict] = []
    if not series_backfill_allowed:
        blockers.append({
            "code": "PROGRAM_SERIES_BACKFILL_NOT_PROVEN",
            "evidence": {
                "migrationPreflightSafe": series_safe,
                "totalPrograms": total_programs,
                "blockerCount": len(series_blockers),
                "blockerCodes": sorted({str(item.get("code") or "") for item in series_blockers}),
                "proposedBackfillCount": len(proposed_backfill),
            },
            "howToResolve": "修复 canonical Program prev_version blocker；vN-only 历史走 privileged baseline migration policy，不得伪造前代或由 migration 重算 series",
        })
    if not task_formation_evidence_clean:
        blockers.append({
            "code": "TASK_FORMATION_EVIDENCE_NOT_CLEAN",
            "evidence": {
                "migrationPreflightSafe": task_safe,
                "unresolvedTaskCount": unresolved_tasks,
                "blockerCounts": task_blockers,
                "relationshipBlockerCounts": task_relationship_blockers,
            },
            "howToResolve": "先修复当前 TeachingTask/TeachingClass/roster 关系 blocker；禁止把冲突运行态带入共享 formation 迁移",
        })
    if not program_course_backfill_allowed:
        blockers.append({
            "code": "PROGRAM_COURSE_FORMATION_BACKFILL_NOT_PROVEN",
            "evidence": {
                "migrationPreflightSafe": program_course_safe,
                "unresolvedProgramCourseCount": unresolved_program_courses,
                "blockerCounts": program_course_blockers,
                "programCourseFormationBackfill": program_course_policy,
            },
            "howToResolve": "为每条历史 ProgramCourse 提供显式 formation provenance；禁止用课程名称/性质、TeachingTask 多数票或 ADMIN_FIXED 默认值回填",
        })

    shared_backfill_allowed = bool(
        series_backfill_allowed
        and task_formation_evidence_clean
        and program_course_backfill_allowed
    )
    return {
        "inventoryEvidenceComplete": True,
        "nullableExpandAllowed": True,
        "expandColumns": [
            {
                "table": "t_aa_program",
                "column": "series_key",
                "nullable": True,
                "historicalDefault": None,
            },
            {
                "table": "t_aa_program_course",
                "column": "formation_mode",
                "nullable": True,
                "historicalDefault": None,
            },
        ],
        "programSeriesBackfillAllowed": series_backfill_allowed,
        "programSeriesBackfillProposal": proposed_backfill if series_backfill_allowed else [],
        "taskFormationEvidenceClean": task_formation_evidence_clean,
        "programCourseFormationBackfillAllowed": program_course_backfill_allowed,
        "sharedBackfillAllowed": shared_backfill_allowed,
        "notNullTightenAllowed": False,
        "uniqueSeriesConstraintTightenAllowed": False,
        "postBackfillEvidenceRequired": [
            "ZERO_NULL_SERIES_KEY",
            "ZERO_NULL_FORMATION_MODE",
            "ZERO_SERIES_VERSION_COLLISION",
            "ZERO_FORMATION_PROVENANCE_MISMATCH",
            "N_MINUS_1_WRITERS_RETIRED",
        ],
        "blockers": blockers,
    }
