"""W7.3 Review Center contract facade.

The production query implementation is read-only. Queue ordering/count/pagination and
summary aggregation are performed by the database before bounded DTOs are returned.
"""
from __future__ import annotations

from app.modules.graduation.services import graduation_review_center_priority_service as priority
from app.modules.graduation.services import graduation_review_center_query_service as query
from app.modules.graduation.services import graduation_review_center_summary_service as summary_query

PRIORITY_SORT = "PRIORITY"
_CASE_PRIORITY = {"FINAL": 2, "FINAL_DRAFT": 2, "FORMAL_REVIEW": 3, "PROPOSAL": 4}
_STATUS_PRIORITY = {"RETURNED": 0, "WAITING": 5, "IN_REVIEW": 5, "BLOCKED": 5, "DONE": 9}
_SUMMARY_FIELDS = ("pending", "inReview", "returned", "doneToday", "overdue", "avgHours", "byType")


def summary(batch_id: int) -> dict:
    result = summary_query.summary(batch_id)
    for field in _SUMMARY_FIELDS:
        result.setdefault(field, None)
    return result


def list_tasks(*, batch_id: int, page: int, page_size: int, case_type=None,
               status_group=None, keyword=None, reviewer_only: bool = False,
               sort: str | None = PRIORITY_SORT):
    return priority.list_tasks(batch_id=batch_id, page=page, page_size=page_size,
                               case_type=case_type, status_group=status_group,
                               keyword=keyword, reviewer_only=reviewer_only, sort=sort)


def detail(*, batch_id: int, case_type: str, record_id: int) -> dict:
    return query.detail(batch_id=batch_id, case_type=case_type, record_id=record_id)
