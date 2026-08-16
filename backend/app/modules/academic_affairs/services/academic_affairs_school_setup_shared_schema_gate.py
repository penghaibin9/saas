"""INT evidence gate for the future shared Program schema migration.

This module does not run Alembic or mutate ORM models. It requires three
independent inventories before shared backfill is permitted:
1. Program prev_version series proof;
2. TeachingTask runtime formation integrity;
3. explicit ProgramCourse formation provenance.

TeachingTask evidence is deliberately not accepted as ProgramCourse plan truth.
Nullable expand remains separate from historical backfill, while NOT NULL and
uniqueness tightening always require a later post-backfill evidence gate.
"""
from __future__ import annotations

from collections.abc import Mapping

SERIES_BACKFILL_POLICY = "PROVABLE_PREV_VERSION_ROOT_ONLY"
PROGRAM_COURSE_PROVENANCE_PROVEN = "EXPLICIT_PROVENANCE_PROVEN"


def _mapping(value: object, *, field: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field} must be an inventory report object")
    return value


def _required_bool(report: Mapping[str, object], field: str, *, owner: str) -> bool:
    if field not in report or not isinstance(report[field], bool):
        raise ValueError(f"{owner}.{field} must be boolean")
    return bool(report[field])


def _required_text(report: Mapping[str, object], field: str, *, owner: str) -> str:
    text = str(report.get(field) or "").strip().upper()
    if not text:
        raise ValueError(f"{owner}.{field} is required")
    return text


def _non_negative_count(report: Mapping[str, object], field: str, *, owner: str) -> int:
    try:
        value = int(report.get(field) or 0)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{owner}.{field} must be a non-negative integer") from exc
    if value < 0:
        raise ValueError(f"{owner}.{field} must be a non-negative integer")
    return value


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

    series_safe = _required_bool(
        series, "migrationPreflightSafe", owner="program_series_inventory"
    )
    task_safe = _required_bool(
        task_formation, "migrationPreflightSafe", owner="task_formation_inventory"
    )
    program_course_safe = _required_bool(
        program_course,
        "migrationPreflightSafe",
        owner="program_course_formation_inventory",
    )
    series_policy = _required_text(
        series, "seriesKeyBackfill", owner="program_series_inventory"
    )
    program_course_policy = _required_text(
        program_course,
        "programCourseFormationBackfill",
        owner="program_course_formation_inventory",
    )

    unresolved_programs = _non_negative_count(
        series, "unresolvedProgramCount", owner="program_series_inventory"
    )
    unresolved_tasks = _non_negative_count(
        task_formation, "unresolvedTaskCount", owner="task_formation_inventory"
    )
    unresolved_program_courses = _non_negative_count(
        program_course,
        "unresolvedProgramCourseCount",
        owner="program_course_formation_inventory",
    )

    series_blockers = dict(series.get("blockerCounts") or {})
    task_blockers = dict(task_formation.get("blockerCounts") or {})
    task_relationship_blockers = dict(
        task_formation.get("relationshipBlockerCounts") or {}
    )
    program_course_blockers = dict(program_course.get("blockerCounts") or {})

    series_backfill_allowed = bool(
        series_safe
        and unresolved_programs == 0
        and not series_blockers
        and series_policy == SERIES_BACKFILL_POLICY
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
                "unresolvedProgramCount": unresolved_programs,
                "blockerCounts": series_blockers,
                "seriesKeyBackfill": series_policy,
            },
            "howToResolve": "修复 Program prev_version 根链 blocker；vN-only 历史走 privileged baseline migration policy，不得伪造前代",
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
