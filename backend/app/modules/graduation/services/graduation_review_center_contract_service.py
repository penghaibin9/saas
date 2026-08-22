"""W7.3 Review Center contract facade.

The production query implementation is read-only. Queue ordering/count/pagination and
summary aggregation are performed by the database before bounded DTOs are returned.
W7.4 treats backend allowedActions as the sole action authority: permissions and stable
formal-review ownership are projected here before any client sees a write affordance.
"""
from __future__ import annotations

from app.core.context import get_current_user_ctx
from app.core.exceptions import not_found
from app.core.permissions import has_permission
from app.modules.graduation.services import graduation_identity as gid
from app.modules.graduation.services import graduation_review_center_priority_service as priority
from app.modules.graduation.services import graduation_review_center_query_service as query
from app.modules.graduation.services import graduation_review_center_summary_service as summary_query
from app.modules.graduation.services.graduation_scope_service import has_full_scope
from app.services.db_service import session

PRIORITY_SORT = "PRIORITY"
_CASE_PRIORITY = {"FINAL": 2, "FINAL_DRAFT": 2, "FORMAL_REVIEW": 3, "PROPOSAL": 4}
_STATUS_PRIORITY = {"RETURNED": 0, "WAITING": 5, "IN_REVIEW": 5, "BLOCKED": 5, "DONE": 9}
_SUMMARY_FIELDS = ("pending", "inReview", "returned", "doneToday", "overdue", "avgHours", "byType")


def _actor_state() -> dict:
    user = get_current_user_ctx() or {}
    role = str(user.get("currentRoleCode") or user.get("userType") or "").strip().upper()
    permissions = {
        "proposal_review": has_permission(user, "graduationDesign.proposal.review"),
        "final_review": has_permission(user, "graduationDesign.final.review"),
        "formal_submit": has_permission(user, "graduationDesign.review.submit"),
        "formal_return": has_permission(user, "graduationDesign.review.return"),
    }
    full_scope = has_full_scope()
    reviewer_id = None
    if role == "GD_REVIEWER" or (permissions["formal_submit"] and not full_scope):
        with session() as db:
            mentor = gid.current_user_mentor(db)
            reviewer_id = int(mentor.id) if mentor else None
    return {
        "user": user,
        "role": role,
        "permissions": permissions,
        "fullScope": full_scope,
        "reviewerId": reviewer_id,
    }


def _formal_submit_owned(item: dict, actor: dict) -> bool:
    if actor["fullScope"]:
        return True
    assigned = item.get("reviewerMentorId")
    reviewer_id = actor.get("reviewerId")
    return bool(
        reviewer_id is not None
        and assigned not in (None, "")
        and str(assigned) == str(reviewer_id)
    )


def _allowed_actions(item: dict, actor: dict) -> list[str]:
    case = str(item.get("caseType") or "").upper()
    status = str(item.get("status") or "").upper()
    ready = bool(item.get("reviewReady"))
    permissions = actor["permissions"]

    if case == "PROPOSAL":
        return ["REVIEW"] if status == "PENDING_REVIEW" and ready and permissions["proposal_review"] else []
    if case in {"FINAL", "FINAL_DRAFT"}:
        return ["REVIEW"] if status == "PENDING_REVIEW" and ready and permissions["final_review"] else []
    if case != "FORMAL_REVIEW":
        return []

    if (
        status in {"ASSIGNED", "REVIEWING", "RETURNED"}
        and ready
        and permissions["formal_submit"]
        and _formal_submit_owned(item, actor)
    ):
        return ["SUBMIT"]
    if status == "COMPLETED" and permissions["formal_return"]:
        return ["RETURN"]
    return []


def _project_actor_actions(item: dict, actor: dict) -> dict:
    result = dict(item)
    result["allowedActions"] = _allowed_actions(result, actor)
    return result


def _assert_reviewer_detail_scope(result: dict, actor: dict) -> None:
    if actor["role"] != "GD_REVIEWER":
        return
    case = result.get("case") or {}
    if (
        str(case.get("caseType") or "").upper() != "FORMAL_REVIEW"
        or actor.get("reviewerId") is None
        or str(case.get("reviewerMentorId") or "") != str(actor["reviewerId"])
    ):
        # Do not reveal whether another review/proposal/final exists for a student the
        # reviewer can see through some different assigned task.
        raise not_found("评阅任务不存在或不在当前数据范围内")


def summary(batch_id: int) -> dict:
    actor = _actor_state()
    reviewer_id = actor.get("reviewerId") if actor["role"] == "GD_REVIEWER" else None
    # A reviewer without a stable mentor identity gets an empty projection, never a
    # real-name fallback. -1 deliberately matches no positive reviewer_mentor_id.
    if actor["role"] == "GD_REVIEWER" and reviewer_id is None:
        reviewer_id = -1
    result = summary_query.summary(batch_id, reviewer_mentor_id=reviewer_id)
    for field in _SUMMARY_FIELDS:
        result.setdefault(field, None)
    return result


def list_tasks(*, batch_id: int, page: int, page_size: int, case_type=None,
               status_group=None, keyword=None, reviewer_only: bool = False,
               sort: str | None = PRIORITY_SORT):
    actor = _actor_state()
    if actor["role"] == "GD_REVIEWER":
        # Reviewer role is task-scoped, not merely student-scoped. A missing stable ID
        # must fail closed instead of falling back to reviewer_name.
        if actor.get("reviewerId") is None:
            return [], 0
        reviewer_only = True
    items, total = priority.list_tasks(
        batch_id=batch_id,
        page=page,
        page_size=page_size,
        case_type=case_type,
        status_group=status_group,
        keyword=keyword,
        reviewer_only=reviewer_only,
        sort=sort,
    )
    return [_project_actor_actions(item, actor) for item in items], total


def detail(*, batch_id: int, case_type: str, record_id: int) -> dict:
    actor = _actor_state()
    result = query.detail(batch_id=batch_id, case_type=case_type, record_id=record_id)
    _assert_reviewer_detail_scope(result, actor)
    case = _project_actor_actions(result.get("case") or {}, actor)
    result = dict(result)
    result["case"] = case
    result["allowedActions"] = list(case.get("allowedActions") or [])
    return result
