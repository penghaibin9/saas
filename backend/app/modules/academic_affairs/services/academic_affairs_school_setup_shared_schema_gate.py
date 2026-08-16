"""INT evidence gate for the future shared Program schema migration.

This module does not run Alembic or mutate ORM models. It converts the already
frozen Program-series and formation inventories into explicit expand/backfill/
tighten decisions so a migration cannot treat "DDL succeeded" as proof that
legacy data was safe to rewrite.

Key distinction:
- nullable expand can be prepared after both inventories are present;
- Program.series_key historical backfill is allowed only for fully proven
  prev_version root chains;
- AaProgramCourse.formation_mode is NOT authorized by TeachingTask formation
  evidence alone. The W3 inventory explicitly says REQUIRES_EXPLICIT_PROVENANCE;
- NOT NULL/tighten is always a separate post-backfill gate and is never approved
  by these pre-migration reports.
"""
from __future__ import annotations

from collections.abc import Mapping

SERIES_BACKFILL_POLICY = "PROVABLE_PREV_VERSION_ROOT_ONLY"
FORMATION_PROVENANCE_REQUIRED = "REQUIRES_EXPLICIT_PROVENANCE"


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


def evaluate_shared_program_schema_gate(
    *,
    program_series_inventory: Mapping[str, object],
    formation_inventory: Mapping[str, object],
) -> dict:
    """Return fail-closed migration phase permissions from inventory evidence."""
    series = _mapping(program_series_inventory, field="program_series_inventory")
    formation = _mapping(formation_inventory, field="formation_inventory")

    series_safe = _required_bool(
        series, "migrationPreflightSafe", owner="program_series_inventory"
    )
    formation_task_safe = _required_bool(
        formation, "migrationPreflightSafe", owner="formation_inventory"
    )
    series_policy = _required_text(
        series, "seriesKeyBackfill", owner="program_series_inventory"
    )
    program_course_backfill = _required_text(
        formation, "programCourseFormationBackfill", owner="formation_inventory"
    )

    unresolved_programs = int(series.get("unresolvedProgramCount") or 0)
    unresolved_tasks = int(formation.get("unresolvedTaskCount") or 0)
    if unresolved_programs < 0 or unresolved_tasks < 0:
        raise ValueError("inventory unresolved counts cannot be negative")

    series_blockers = dict(series.get("blockerCounts") or {})
    formation_blockers = dict(formation.get("blockerCounts") or {})
    relationship_blockers = dict(formation.get("relationshipBlockerCounts") or {})

    series_backfill_allowed = bool(
        series_safe
        and unresolved_programs == 0
        and not series_blockers
        and series_policy == SERIES_BACKFILL_POLICY
    )

    # TeachingTask formation can be entirely proven while ProgramCourse still has
    # no explicit provenance edge to those tasks. Never convert task majority or
    # class labels into ProgramCourse plan truth.
    formation_task_evidence_clean = bool(
        formation_task_safe
        and unresolved_tasks == 0
        and not formation_blockers
        and not relationship_blockers
    )
    formation_backfill_allowed = bool(
        formation_task_evidence_clean
        and program_course_backfill != FORMATION_PROVENANCE_REQUIRED
        and program_course_backfill == "EXPLICIT_PROVENANCE_PROVEN"
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
    if not formation_backfill_allowed:
        blockers.append({
            "code": "PROGRAM_COURSE_FORMATION_BACKFILL_NOT_PROVEN",
            "evidence": {
                "taskFormationInventorySafe": formation_task_evidence_clean,
                "unresolvedTaskCount": unresolved_tasks,
                "blockerCounts": formation_blockers,
                "relationshipBlockerCounts": relationship_blockers,
                "programCourseFormationBackfill": program_course_backfill,
            },
            "howToResolve": "补充 ProgramCourse→历史编班来源的显式 provenance inventory；禁止用课程名称/性质、TeachingTask 多数票或 ADMIN_FIXED 默认值回填",
        })

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
        "programCourseFormationBackfillAllowed": formation_backfill_allowed,
        "sharedBackfillAllowed": series_backfill_allowed and formation_backfill_allowed,
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
