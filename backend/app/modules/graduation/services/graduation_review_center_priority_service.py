"""W7.3 exact business-priority database pagination.

RETURNED -> overdue -> FINAL/FINAL_DRAFT -> FORMAL_REVIEW -> PROPOSAL -> ordinary active -> DONE.
The database applies this order before LIMIT/OFFSET; Python never reorders a paged subset.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import bindparam, text

from app.modules.graduation.services import graduation_review_center_query_service as q
from app.modules.graduation.services import graduation_review_feedback_service as feedback
from app.modules.graduation.services.graduation_scope_service import accessible_student_ids
from app.services.db_service import _tid, session


def list_tasks(*, batch_id: int, page: int, page_size: int, case_type=None, status_group=None,
               keyword=None, reviewer_only: bool = False, sort: str | None = None):
    sort_key = str(sort or "PRIORITY").upper()
    if sort_key not in q.SORTS:
        from app.core.exceptions import AppException
        raise AppException("VALIDATION_ERROR", "sort 不支持")
    with session() as db:
        scope_ids = accessible_student_ids(db, int(_tid()), batch_id=int(batch_id))
        reviewer_id, reviewer_name = q._current_reviewer(db)
        where, extra = q._filters(case_type, status_group, keyword, reviewer_only, reviewer_id, reviewer_name)
        deadlines = q._batch_deadlines(db, int(batch_id))
        now = datetime.now(timezone.utc)
        params = {**q._base_params(batch_id, scope_ids), **extra}
        for case in q.CASE_TYPES:
            deadline = deadlines.get(case)
            params[f"overdue_{case.lower()}"] = 1 if deadline and deadline < now else 0

        count_stmt = text(q._CTE + "SELECT COUNT(*) FROM projected" + where).bindparams(bindparam("scope_ids", expanding=True))
        total = int(db.execute(count_stmt, params).scalar() or 0)
        if sort_key == "PRIORITY":
            order = """ ORDER BY CASE
              WHEN status_group='RETURNED' THEN 0
              WHEN status_group<>'DONE' AND ((case_type='PROPOSAL' AND :overdue_proposal=1)
                OR (case_type='FINAL_DRAFT' AND :overdue_final_draft=1)
                OR (case_type='FINAL' AND :overdue_final=1)
                OR (case_type='FORMAL_REVIEW' AND :overdue_formal_review=1)) THEN 1
              WHEN status_group='DONE' THEN 9
              WHEN case_type IN ('FINAL','FINAL_DRAFT') THEN 2
              WHEN case_type='FORMAL_REVIEW' THEN 3
              WHEN case_type='PROPOSAL' THEN 4
              ELSE 5 END,
              COALESCE(reviewed_at,submitted_at,assigned_at,created_at) ASC,record_id ASC"""
        elif sort_key == "LATEST":
            order = " ORDER BY COALESCE(reviewed_at,submitted_at,assigned_at,created_at) DESC,record_id DESC"
        elif sort_key == "EARLIEST":
            order = " ORDER BY COALESCE(reviewed_at,submitted_at,assigned_at,created_at) ASC,record_id ASC"
        elif sort_key == "STUDENT_NO":
            order = " ORDER BY student_no ASC,student_name ASC,case_type ASC,record_id ASC"
        else:
            order = " ORDER BY status_group ASC,case_type ASC,record_id ASC"
        page_size = max(1, min(200, int(page_size))); page = max(1, int(page))
        params.update({"limit": page_size, "offset": (page - 1) * page_size})
        page_stmt = text(q._CTE + "SELECT * FROM projected" + where + order + " LIMIT :limit OFFSET :offset").bindparams(bindparam("scope_ids", expanding=True))
        rows = [dict(row) for row in db.execute(page_stmt, params).mappings().all()]
        keys = [("PROPOSAL" if row["case_type"] == "PROPOSAL" else "FORMAL" if row["case_type"] == "FORMAL_REVIEW" else "FINAL", int(row["record_id"])) for row in rows]
        latest = feedback.feedback_for_sources(db, keys)
        items = [q._public(row, deadlines, now, latest.get((keys[idx][0], str(keys[idx][1])))) for idx, row in enumerate(rows)]
        return items, total
