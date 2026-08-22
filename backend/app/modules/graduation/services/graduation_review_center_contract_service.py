"""W7.3 Review Center contract completion.

Keeps Proposal / Final / GraduationReview as the only write authorities while
completing the Review Center read-model contract: summary metrics, business
priority sorting, conservative deadline projection and server-side paging.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select

from app.core.exceptions import AppException
from app.models import GraduationBatch
from app.modules.graduation.services import graduation_review_center_service as base
from app.services.db_service import _tid, session

PRIORITY_SORT = "PRIORITY"
SUPPORTED_SORTS = set(base.SORTS) | {PRIORITY_SORT}
_CASE_PRIORITY = {"FINAL": 2, "FORMAL_REVIEW": 3, "PROPOSAL": 4, "FINAL_DRAFT": 5}
_STATUS_PRIORITY = {"RETURNED": 0, "BLOCKED": 1, "WAITING": 5, "IN_REVIEW": 6, "DONE": 9}
_STAGE_HINTS = {
    "PROPOSAL": ("PROPOSAL", "OPENING", "开题"),
    "FINAL_DRAFT": ("DRAFT", "FIRST_DRAFT", "初稿"),
    "FINAL": ("FINAL", "THESIS_FINAL", "定稿"),
    "FORMAL_REVIEW": ("REVIEW", "FORMAL_REVIEW", "评阅"),
}


def _aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _parse_dt(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return _aware(value)
    if not isinstance(value, str) or not value.strip():
        return None
    raw = value.strip().replace("Z", "+00:00")
    try:
        return _aware(datetime.fromisoformat(raw))
    except ValueError:
        return None


def _batch_deadlines(db, batch_id: int) -> tuple[GraduationBatch, dict[str, datetime | None]]:
    batch = db.scalars(select(GraduationBatch).where(
        GraduationBatch.tenant_id == _tid(),
        GraduationBatch.id == int(batch_id),
        GraduationBatch.is_deleted.is_(False),
    )).first()
    if not batch:
        raise AppException("NOT_FOUND", "毕设批次不存在")

    result: dict[str, datetime | None] = {case: None for case in base.CASE_TYPES}
    stages = batch.stage_config if isinstance(batch.stage_config, list) else []
    for item in stages:
        if not isinstance(item, dict):
            continue
        text = " ".join(str(item.get(key) or "") for key in ("code", "name", "stage", "stageCode")).upper()
        end_at = _parse_dt(item.get("endDate") or item.get("end_at") or item.get("deadline"))
        if not end_at:
            continue
        for case, hints in _STAGE_HINTS.items():
            if result[case] is None and any(str(hint).upper() in text for hint in hints):
                result[case] = end_at

    batch_end = _aware(batch.end_date)
    for case in result:
        if result[case] is None:
            result[case] = batch_end
    return batch, result


def _decorate_deadline(row: dict, deadlines: dict[str, datetime | None], now: datetime) -> dict:
    deadline = deadlines.get(str(row.get("caseType") or ""))
    group = str(row.get("statusGroup") or "")
    overdue = bool(deadline and deadline < now and group in {"WAITING", "IN_REVIEW", "RETURNED", "BLOCKED"})
    row["deadlineAt"] = deadline.isoformat() if deadline else None
    row["overdue"] = overdue
    return row


def _processing_hours(row: dict) -> float | None:
    end = _parse_dt(row.get("reviewedAt"))
    if not end:
        return None
    start = _parse_dt(row.get("startedAt") or row.get("assignedAt") or row.get("submittedAt"))
    if not start or end < start:
        return None
    return round((end - start).total_seconds() / 3600.0, 2)


def _priority_key(row: dict):
    group = str(row.get("statusGroup") or "")
    overdue_rank = 0 if row.get("overdue") else 1
    case = str(row.get("caseType") or "")
    sort_at = row.get("_sortAt") or datetime.min
    return (
        _STATUS_PRIORITY.get(group, 8),
        overdue_rank,
        _CASE_PRIORITY.get(case, 8),
        sort_at,
        int(row.get("recordId") or 0),
    )


def _filtered_rows(
    db,
    *,
    batch_id: int,
    case_type: str | None,
    status_group: str | None,
    keyword: str | None,
    reviewer_only: bool,
) -> tuple[list[dict], dict[str, datetime | None]]:
    normalized_case = base._validate_case_type(case_type)
    normalized_group = base._validate_status_group(status_group)
    rows, _ = base._project_bundle(db, int(batch_id), case_type=normalized_case)
    _, deadlines = _batch_deadlines(db, int(batch_id))
    now = datetime.now(timezone.utc)
    rows = [_decorate_deadline(row, deadlines, now) for row in rows]

    if normalized_group:
        rows = [row for row in rows if row.get("statusGroup") == normalized_group]
    needle = str(keyword or "").strip().lower()
    if needle:
        rows = [row for row in rows if needle in " ".join((
            str(row.get("studentName") or ""),
            str(row.get("studentNo") or ""),
            str(row.get("className") or ""),
            str(row.get("majorName") or ""),
            str(row.get("topicTitle") or ""),
        )).lower()]
    if reviewer_only:
        mentor_id, real_name = base._current_reviewer_identity(db)
        rows = [row for row in rows if (
            mentor_id is not None and str(row.get("reviewerMentorId") or "") == str(mentor_id)
        ) or (
            not row.get("reviewerMentorId") and real_name and str(row.get("reviewerName") or "") == real_name
        )]
    return rows, deadlines


def summary(batch_id: int) -> dict:
    with session() as db:
        rows, _ = _filtered_rows(
            db, batch_id=int(batch_id), case_type=None, status_group=None,
            keyword=None, reviewer_only=False,
        )
        now = datetime.now(timezone.utc)
        today = now.date()
        groups = {key: 0 for key in sorted(base.STATUS_GROUPS)}
        by_type: dict[str, dict] = {
            case: {"caseType": case, "total": 0, "pending": 0, "inReview": 0, "returned": 0, "done": 0, "blocked": 0}
            for case in sorted(base.CASE_TYPES)
        }
        durations: list[float] = []
        done_today = 0
        overdue = 0
        for row in rows:
            group = str(row.get("statusGroup") or "BLOCKED")
            groups[group] = groups.get(group, 0) + 1
            slot = by_type[str(row.get("caseType"))]
            slot["total"] += 1
            slot[{"WAITING": "pending", "IN_REVIEW": "inReview", "RETURNED": "returned", "DONE": "done", "BLOCKED": "blocked"}.get(group, "blocked")] += 1
            reviewed_at = _parse_dt(row.get("reviewedAt"))
            if group == "DONE" and reviewed_at and reviewed_at.date() == today:
                done_today += 1
            if row.get("overdue"):
                overdue += 1
            hours = _processing_hours(row)
            if hours is not None:
                durations.append(hours)

        pending = groups.get("WAITING", 0) + groups.get("BLOCKED", 0)
        return {
            "batchId": str(batch_id),
            "pending": pending,
            "inReview": groups.get("IN_REVIEW", 0),
            "returned": groups.get("RETURNED", 0),
            "doneToday": done_today,
            "overdue": overdue,
            "avgHours": round(sum(durations) / len(durations), 2) if durations else None,
            "byType": [by_type[key] for key in sorted(by_type)],
            "total": len(rows),
            "blocked": groups.get("BLOCKED", 0),
            "groups": groups,
        }


def list_tasks(
    *, batch_id: int, page: int, page_size: int,
    case_type: str | None = None, status_group: str | None = None,
    keyword: str | None = None, reviewer_only: bool = False,
    sort: str | None = None,
) -> tuple[list[dict], int]:
    sort_key = str(sort or PRIORITY_SORT).strip().upper()
    if sort_key not in SUPPORTED_SORTS:
        raise AppException("VALIDATION_ERROR", "sort 不支持")
    with session() as db:
        rows, _ = _filtered_rows(
            db, batch_id=int(batch_id), case_type=case_type, status_group=status_group,
            keyword=keyword, reviewer_only=reviewer_only,
        )
        if sort_key == PRIORITY_SORT:
            rows.sort(key=_priority_key)
        elif sort_key == "LATEST":
            rows.sort(key=lambda row: (row.get("_sortAt") or datetime.min, int(row["recordId"])), reverse=True)
        elif sort_key == "EARLIEST":
            rows.sort(key=lambda row: (row.get("_sortAt") or datetime.min, int(row["recordId"])))
        elif sort_key == "STUDENT_NO":
            rows.sort(key=lambda row: (str(row.get("studentNo") or ""), str(row.get("studentName") or ""), row["caseKey"]))
        else:
            rows.sort(key=lambda row: (row.get("statusGroup") or "", row.get("caseType") or "", row["caseKey"]))
        total = len(rows)
        start = (max(1, int(page)) - 1) * int(page_size)
        return [base._public_task(row) for row in rows[start:start + int(page_size)]], total


def detail(*, batch_id: int, case_type: str, record_id: int) -> dict:
    result = base.detail(batch_id=int(batch_id), case_type=case_type, record_id=int(record_id))
    with session() as db:
        _, deadlines = _batch_deadlines(db, int(batch_id))
    case = result.get("case") or {}
    _decorate_deadline(case, deadlines, datetime.now(timezone.utc))
    result["case"] = case
    result["deadlineAt"] = case.get("deadlineAt")
    result["overdue"] = bool(case.get("overdue"))
    return result
