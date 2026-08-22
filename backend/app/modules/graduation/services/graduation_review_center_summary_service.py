"""W7.3/W7.6 Review Center summary aggregated inside MySQL.

The queue CTE remains the single projection truth. Summary endpoints must not materialize
an entire school batch in Python just to count statuses or processing time; the database
returns only aggregate rows while preserving the same tenant/data-scope and deadline rules.
W7.4 may additionally bind the aggregate to one stable formal-review reviewer identity.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import bindparam, text

from app.core.timeutil import local_today_bounds_utc, utc_now
from app.modules.graduation.services import graduation_review_center_query_service as q
from app.modules.graduation.services.graduation_review_center_scope_service import reviewer_student_ids
from app.modules.graduation.services.graduation_scope_service import accessible_student_ids
from app.services.db_service import _tid, session


def _deadline_flags(deadlines: dict[str, datetime | None], now: datetime) -> dict[str, int]:
    return {
        f"overdue_{case.lower()}": 1 if deadlines.get(case) and deadlines[case] < now else 0
        for case in q.CASE_TYPES
    }


def _projection_where(reviewer_mentor_id: int | None) -> str:
    if reviewer_mentor_id is None:
        return ""
    return " WHERE case_type='FORMAL_REVIEW' AND reviewer_mentor_id=:reviewer_mentor_id"


def summary(batch_id: int, *, reviewer_mentor_id: int | None = None) -> dict:
    """Return bounded aggregate metrics without hydrating the full projected queue."""
    with session() as db:
        if reviewer_mentor_id is None:
            scope_ids = accessible_student_ids(db, int(_tid()), batch_id=int(batch_id))
        else:
            scope_ids = reviewer_student_ids(
                db,
                batch_id=int(batch_id),
                reviewer_mentor_id=int(reviewer_mentor_id),
            )
        deadlines = q._batch_deadlines(db, int(batch_id))
        now = utc_now()
        # "今日" is a tenant-local calendar concept. DB timestamps are UTC-naive,
        # so query using the canonical tenant-local-day -> UTC-naive bounds.
        today_start, tomorrow_start = local_today_bounds_utc(now)
        params = {
            **q._base_params(int(batch_id), scope_ids),
            **_deadline_flags(deadlines, now),
            "today_start": today_start,
            "tomorrow_start": tomorrow_start,
        }
        if reviewer_mentor_id is not None:
            params["reviewer_mentor_id"] = int(reviewer_mentor_id)
        projection_where = _projection_where(reviewer_mentor_id)

        aggregate_sql = q._CTE + r"""
SELECT
  COUNT(*) AS total,
  SUM(CASE WHEN status_group='WAITING' THEN 1 ELSE 0 END) AS waiting_count,
  SUM(CASE WHEN status_group='IN_REVIEW' THEN 1 ELSE 0 END) AS in_review_count,
  SUM(CASE WHEN status_group='RETURNED' THEN 1 ELSE 0 END) AS returned_count,
  SUM(CASE WHEN status_group='DONE' THEN 1 ELSE 0 END) AS done_count,
  SUM(CASE WHEN status_group='BLOCKED' THEN 1 ELSE 0 END) AS blocked_count,
  SUM(CASE WHEN status_group='DONE' AND reviewed_at>=:today_start AND reviewed_at<:tomorrow_start
           THEN 1 ELSE 0 END) AS done_today,
  SUM(CASE WHEN status_group IN ('WAITING','IN_REVIEW','RETURNED','BLOCKED') AND (
        (case_type='PROPOSAL' AND :overdue_proposal=1)
        OR (case_type='FINAL_DRAFT' AND :overdue_final_draft=1)
        OR (case_type='FINAL' AND :overdue_final=1)
        OR (case_type='FORMAL_REVIEW' AND :overdue_formal_review=1)
      ) THEN 1 ELSE 0 END) AS overdue_count,
  AVG(CASE
        WHEN reviewed_at IS NOT NULL
         AND COALESCE(started_at,assigned_at,submitted_at) IS NOT NULL
         AND reviewed_at>=COALESCE(started_at,assigned_at,submitted_at)
        THEN TIMESTAMPDIFF(SECOND,COALESCE(started_at,assigned_at,submitted_at),reviewed_at)/3600.0
        ELSE NULL
      END) AS avg_hours
FROM projected
""" + projection_where
        aggregate_stmt = text(aggregate_sql).bindparams(bindparam("scope_ids", expanding=True))
        aggregate = dict(db.execute(aggregate_stmt, params).mappings().one())

        by_type_sql = q._CTE + r"""
SELECT case_type,
  COUNT(*) AS total,
  SUM(CASE WHEN status_group='WAITING' THEN 1 ELSE 0 END) AS pending,
  SUM(CASE WHEN status_group='IN_REVIEW' THEN 1 ELSE 0 END) AS in_review,
  SUM(CASE WHEN status_group='RETURNED' THEN 1 ELSE 0 END) AS returned,
  SUM(CASE WHEN status_group='DONE' THEN 1 ELSE 0 END) AS done,
  SUM(CASE WHEN status_group='BLOCKED' THEN 1 ELSE 0 END) AS blocked
FROM projected
""" + projection_where + "\nGROUP BY case_type\n"
        by_type_stmt = text(by_type_sql).bindparams(bindparam("scope_ids", expanding=True))
        raw_by_type = {
            str(row["case_type"]): dict(row)
            for row in db.execute(by_type_stmt, params).mappings().all()
        }

    groups = {
        "WAITING": int(aggregate.get("waiting_count") or 0),
        "IN_REVIEW": int(aggregate.get("in_review_count") or 0),
        "RETURNED": int(aggregate.get("returned_count") or 0),
        "DONE": int(aggregate.get("done_count") or 0),
        "BLOCKED": int(aggregate.get("blocked_count") or 0),
    }
    by_type = []
    for case_type in sorted(q.CASE_TYPES):
        row = raw_by_type.get(case_type, {})
        by_type.append({
            "caseType": case_type,
            "total": int(row.get("total") or 0),
            "pending": int(row.get("pending") or 0),
            "inReview": int(row.get("in_review") or 0),
            "returned": int(row.get("returned") or 0),
            "done": int(row.get("done") or 0),
            "blocked": int(row.get("blocked") or 0),
        })
    avg_hours = aggregate.get("avg_hours")
    return {
        "batchId": str(batch_id),
        "pending": groups["WAITING"] + groups["BLOCKED"],
        "inReview": groups["IN_REVIEW"],
        "returned": groups["RETURNED"],
        "doneToday": int(aggregate.get("done_today") or 0),
        "overdue": int(aggregate.get("overdue_count") or 0),
        "avgHours": round(float(avg_hours), 2) if avg_hours is not None else None,
        "byType": by_type,
        "total": int(aggregate.get("total") or 0),
        "blocked": groups["BLOCKED"],
        "groups": groups,
    }


__all__ = ["summary"]
