"""A-W3 internal-only formation dirty-data inventory.

This module is intentionally not routed and never writes.  It provides the evidence
inventory that Academic INT needs before adding shared ProgramCourse/TeachingTask
formation columns or attempting a historical backfill.

Production constraints:
- caller supplies an explicit positive tenant id; no ambient request context is used;
- exactly four tenant-scoped relationship queries collect evidence without N+1;
- roster decisions use the TeachingClass current-roster pointer, not a bag of
  superseded historical roster sources;
- student/member rows and B's live roster resolver are never read;
- course name/nature are never used as formation evidence;
- unresolved/conflicting history stays a migration blocker instead of being guessed.
"""
from __future__ import annotations

from collections import Counter

from sqlalchemy import and_, select

from . import academic_affairs_task_formation_policy as policy

_MAX_SAMPLE_LIMIT = 100
_DEFAULT_SAMPLE_LIMIT = 20


def _positive_tenant_id(value) -> int:
    try:
        tenant_id = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("tenant_id must be a positive integer") from exc
    if tenant_id <= 0:
        raise ValueError("tenant_id must be a positive integer")
    return tenant_id


def _bounded_sample_limit(value) -> int:
    try:
        limit = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("sample_limit must be an integer") from exc
    if limit < 1 or limit > _MAX_SAMPLE_LIMIT:
        raise ValueError(f"sample_limit must be between 1 and {_MAX_SAMPLE_LIMIT}")
    return limit


def _formation_inventory_statements(tenant_id: int):
    """Build the four tenant-scoped read statements used by the inventory."""
    from app.models import (
        AaSelectionCourse,
        AaTeachingClass,
        AaTeachingClassRosterVersion,
        AaTeachingTask,
    )

    tid = _positive_tenant_id(tenant_id)
    tasks = (
        select(AaTeachingTask.id, AaTeachingTask.is_merged, AaTeachingTask.class_id)
        .where(
            AaTeachingTask.tenant_id == tid,
            AaTeachingTask.is_deleted.is_(False),
        )
        .order_by(AaTeachingTask.id.asc())
    )
    teaching_classes = (
        select(AaTeachingClass.teaching_task_id, AaTeachingClass.class_type)
        .where(
            AaTeachingClass.tenant_id == tid,
            AaTeachingClass.is_deleted.is_(False),
        )
        .order_by(AaTeachingClass.teaching_task_id.asc(), AaTeachingClass.id.asc())
    )
    selection_relations = (
        select(AaSelectionCourse.teaching_task_id)
        .where(
            AaSelectionCourse.tenant_id == tid,
            AaSelectionCourse.teaching_task_id.is_not(None),
            AaSelectionCourse.is_deleted.is_(False),
        )
    )
    current_rosters = (
        select(
            AaTeachingClass.teaching_task_id,
            AaTeachingClass.current_roster_version_id,
            AaTeachingClass.roster_status,
            AaTeachingClassRosterVersion.id,
            AaTeachingClassRosterVersion.source_type,
            AaTeachingClassRosterVersion.status,
        )
        .outerjoin(
            AaTeachingClassRosterVersion,
            and_(
                AaTeachingClassRosterVersion.id == AaTeachingClass.current_roster_version_id,
                AaTeachingClassRosterVersion.teaching_class_id == AaTeachingClass.id,
                AaTeachingClassRosterVersion.tenant_id == tid,
                AaTeachingClassRosterVersion.is_deleted.is_(False),
            ),
        )
        .where(
            AaTeachingClass.tenant_id == tid,
            AaTeachingClass.is_deleted.is_(False),
        )
        .order_by(AaTeachingClass.teaching_task_id.asc(), AaTeachingClass.id.asc())
    )
    return tasks, teaching_classes, selection_relations, current_rosters


def _append_sample(samples: dict[str, list[str]], key: str, task_id: int, limit: int) -> None:
    bucket = samples.setdefault(key, [])
    value = str(int(task_id))
    if value not in bucket and len(bucket) < limit:
        bucket.append(value)


def _single_column_value(row):
    """Accept SQLAlchemy Row/tuple and lightweight scalar fixtures without guessing DTOs."""
    try:
        return row[0]
    except (TypeError, KeyError, IndexError):
        return row


def _build_inventory(
    task_rows,
    teaching_class_rows,
    selection_rows,
    current_roster_rows,
    *,
    sample_limit: int = _DEFAULT_SAMPLE_LIMIT,
) -> dict:
    """Classify already-collected relationship facts without additional database I/O."""
    limit = _bounded_sample_limit(sample_limit)
    tasks = [
        (int(task_id), bool(is_merged), int(class_id) if class_id else None)
        for task_id, is_merged, class_id in task_rows
    ]
    task_ids = {task_id for task_id, _is_merged, _class_id in tasks}

    class_type_by_task: dict[int, str | None] = {}
    relationship_counts: Counter[str] = Counter()
    relationship_samples: dict[str, list[str]] = {}
    for task_id, class_type in teaching_class_rows:
        tid = int(task_id)
        if tid not in task_ids:
            relationship_counts["ORPHAN_TEACHING_CLASS_TASK"] += 1
            _append_sample(relationship_samples, "ORPHAN_TEACHING_CLASS_TASK", tid, limit)
            continue
        normalized = str(class_type or "").strip().upper() or None
        if tid in class_type_by_task and class_type_by_task[tid] != normalized:
            relationship_counts["MULTIPLE_TEACHING_CLASS_TYPES"] += 1
            _append_sample(relationship_samples, "MULTIPLE_TEACHING_CLASS_TYPES", tid, limit)
            class_type_by_task[tid] = "__CONFLICT__"
        else:
            class_type_by_task[tid] = normalized

    selection_task_ids: set[int] = set()
    for row in selection_rows:
        raw = _single_column_value(row)
        if raw is None:
            continue
        tid = int(raw)
        if tid not in task_ids:
            relationship_counts["ORPHAN_SELECTION_TASK"] += 1
            _append_sample(relationship_samples, "ORPHAN_SELECTION_TASK", tid, limit)
            continue
        selection_task_ids.add(tid)

    current_roster_source_by_task: dict[int, str] = {}
    for (
        task_id,
        current_roster_version_id,
        roster_status,
        resolved_roster_version_id,
        source_type,
        version_status,
    ) in current_roster_rows:
        tid = int(task_id)
        if tid not in task_ids:
            # The TeachingClass query already reports the canonical orphan once.
            continue
        current_id = int(current_roster_version_id) if current_roster_version_id else None
        resolved_id = int(resolved_roster_version_id) if resolved_roster_version_id else None
        class_roster_status = str(roster_status or "").strip().upper()
        current_version_status = str(version_status or "").strip().upper()
        current_source = str(source_type or "").strip().upper()

        if current_id and not resolved_id:
            relationship_counts["CURRENT_ROSTER_POINTER_DANGLING"] += 1
            _append_sample(relationship_samples, "CURRENT_ROSTER_POINTER_DANGLING", tid, limit)
            continue
        if not current_id and class_roster_status == "LOCKED":
            relationship_counts["ROSTER_LOCKED_WITHOUT_CURRENT_VERSION"] += 1
            _append_sample(relationship_samples, "ROSTER_LOCKED_WITHOUT_CURRENT_VERSION", tid, limit)
            continue
        if resolved_id:
            if class_roster_status != "LOCKED":
                relationship_counts["CURRENT_ROSTER_STATUS_MISMATCH"] += 1
                _append_sample(relationship_samples, "CURRENT_ROSTER_STATUS_MISMATCH", tid, limit)
            if current_version_status != "LOCKED":
                relationship_counts["CURRENT_ROSTER_VERSION_NOT_LOCKED"] += 1
                _append_sample(relationship_samples, "CURRENT_ROSTER_VERSION_NOT_LOCKED", tid, limit)
            if not current_source:
                relationship_counts["CURRENT_ROSTER_SOURCE_MISSING"] += 1
                _append_sample(relationship_samples, "CURRENT_ROSTER_SOURCE_MISSING", tid, limit)
            else:
                current_roster_source_by_task[tid] = current_source

    status_counts: Counter[str] = Counter()
    mode_counts: Counter[str] = Counter()
    source_counts: Counter[str] = Counter()
    blocker_counts: Counter[str] = Counter()
    blocker_samples: dict[str, list[str]] = {}

    for task_id, is_merged, class_id in tasks:
        class_type = class_type_by_task.get(task_id)
        if class_type == "__CONFLICT__":
            evidence = policy.FormationEvidence(
                mode=None,
                status=policy.EVIDENCE_CONFLICT,
                source="MULTIPLE_TEACHING_CLASS_TYPES",
                blockers=("MULTIPLE_TEACHING_CLASS_TYPES",),
            )
        else:
            current_source = current_roster_source_by_task.get(task_id)
            evidence = policy.resolve_legacy_task_formation(
                is_merged=is_merged,
                class_id=class_id,
                selection_exists=task_id in selection_task_ids,
                teaching_class_type=class_type,
                roster_source_types=(current_source,) if current_source else (),
            )
        status_counts[evidence.status] += 1
        source_counts[evidence.source] += 1
        if evidence.mode:
            mode_counts[evidence.mode] += 1
        for blocker in evidence.blockers:
            blocker_counts[blocker] += 1
            _append_sample(blocker_samples, blocker, task_id, limit)

    unresolved = (
        status_counts[policy.EVIDENCE_UNKNOWN]
        + status_counts[policy.EVIDENCE_CONFLICT]
    )
    relationship_total = sum(relationship_counts.values())
    return {
        "totalTasks": len(tasks),
        "evidenceStatusCounts": {
            policy.EVIDENCE_PROVEN: int(status_counts[policy.EVIDENCE_PROVEN]),
            policy.EVIDENCE_UNKNOWN: int(status_counts[policy.EVIDENCE_UNKNOWN]),
            policy.EVIDENCE_CONFLICT: int(status_counts[policy.EVIDENCE_CONFLICT]),
        },
        "formationModeCounts": {
            mode: int(mode_counts[mode]) for mode in sorted(policy.FORMATION_MODES)
        },
        "evidenceSourceCounts": dict(sorted(source_counts.items())),
        "blockerCounts": dict(sorted(blocker_counts.items())),
        "blockerTaskSamples": {key: blocker_samples[key] for key in sorted(blocker_samples)},
        "relationshipBlockerCounts": dict(sorted(relationship_counts.items())),
        "relationshipBlockerTaskSamples": {
            key: relationship_samples[key] for key in sorted(relationship_samples)
        },
        "unresolvedTaskCount": int(unresolved),
        "migrationPreflightSafe": unresolved == 0 and relationship_total == 0,
        # Current legacy Task has no stable sourceProgramCourseId/provenance link. INT must
        # not use a task-mode majority vote to rewrite ProgramCourse plan truth.
        "programCourseFormationBackfill": "REQUIRES_EXPLICIT_PROVENANCE",
    }


def inventory_legacy_task_formation(
    db,
    *,
    tenant_id: int,
    sample_limit: int = _DEFAULT_SAMPLE_LIMIT,
) -> dict:
    """Return a read-only migration preflight report for one explicit tenant."""
    tid = _positive_tenant_id(tenant_id)
    limit = _bounded_sample_limit(sample_limit)
    statements = _formation_inventory_statements(tid)
    task_rows = db.execute(statements[0]).all()
    teaching_class_rows = db.execute(statements[1]).all()
    selection_rows = db.execute(statements[2]).all()
    current_roster_rows = db.execute(statements[3]).all()
    return _build_inventory(
        task_rows,
        teaching_class_rows,
        selection_rows,
        current_roster_rows,
        sample_limit=limit,
    )
