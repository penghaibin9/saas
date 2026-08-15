"""B-W1 SelectionPreflight: pure-read lifecycle validation shared by commands and UI.

This module never commits, audits, changes capacity, or changes selection/roster state.
W2/W4 extend evidence with ScopeHead/Task identity; W1 only freezes current lifecycle/config truth.
"""
from __future__ import annotations

import json

from app.core.exceptions import AppException
from app.services.db_service import _tid

_EXPECTED = {
    "PUBLISH": "DRAFT",
    "OPEN": "PUBLISHED",
    "CLOSE": "OPEN",
    "LOCK": "CLOSED",
}


def _block(code, message, owner_role="ACADEMIC_ADMIN", how_to_resolve=None, **details):
    row = {
        "code": code,
        "message": message,
        "ownerRole": owner_role,
        "howToResolve": how_to_resolve or message,
    }
    if details:
        row["details"] = details
    return row


def _strict_object(raw, *, code, label, batch_id, blockers):
    if raw in (None, ""):
        return {}
    try:
        value = json.loads(raw) if isinstance(raw, str) else raw
    except (TypeError, ValueError, json.JSONDecodeError):
        blockers.append(_block(
            code,
            f"{label}JSON损坏",
            how_to_resolve=f"修复批次{label}配置后重新预检",
            batchId=str(batch_id),
        ))
        return None
    if not isinstance(value, dict):
        blockers.append(_block(
            code,
            f"{label}格式错误，必须是对象",
            how_to_resolve=f"将批次{label}改为对象结构后重新预检",
            batchId=str(batch_id),
        ))
        return None
    return value


def evaluate_batch(db, batch, action: str) -> dict:
    """Pure read. Return lifecycle blockers and existing roster validation for LOCK."""
    from app.models import AaSelectionCourse

    action = str(action or "").strip().upper()
    if action not in _EXPECTED:
        raise AppException("VALIDATION_ERROR", "preflight action仅支持PUBLISH/OPEN/CLOSE/LOCK")

    blockers = []
    expected = _EXPECTED[action]
    if str(batch.status or "").upper() != expected:
        blockers.append(_block(
            "SELECTION_STATE_MISMATCH",
            f"当前状态{batch.status or 'UNKNOWN'}不可执行{action}",
            how_to_resolve=f"仅{expected}状态可执行{action}",
            expectedStatus=expected,
            actualStatus=str(batch.status or ""),
        ))
    if not getattr(batch, "term_id", None):
        blockers.append(_block(
            "SELECTION_TERM_MISSING",
            "选课批次未绑定正式学期",
            how_to_resolve="返回批次配置并绑定正式termId",
        ))

    _strict_object(
        getattr(batch, "apply_scope_json", None),
        code="SELECTION_SCOPE_CONFIG_INVALID",
        label="适用范围",
        batch_id=batch.id,
        blockers=blockers,
    )
    _strict_object(
        getattr(batch, "rule_json", None),
        code="SELECTION_RULE_CONFIG_INVALID",
        label="选课规则",
        batch_id=batch.id,
        blockers=blockers,
    )

    course_count = None
    if action in {"PUBLISH", "OPEN"}:
        courses = db.query(AaSelectionCourse).filter(
            AaSelectionCourse.tenant_id == _tid(),
            AaSelectionCourse.batch_id == int(batch.id),
            AaSelectionCourse.status == "OPEN",
            AaSelectionCourse.is_deleted.is_(False),
        ).all()
        course_count = len(courses)
        if not courses:
            blockers.append(_block(
                "SELECTION_COURSE_EMPTY",
                "批次未配置有效可选课程",
                how_to_resolve="至少添加一门有效可选课程后重新预检",
            ))
        invalid = [row for row in courses if int(row.capacity or 0) <= 0
                   or int(row.min_capacity or 0) < 0
                   or int(row.min_capacity or 0) > int(row.capacity or 0)]
        if invalid:
            blockers.append(_block(
                "SELECTION_CAPACITY_INVALID",
                f"有{len(invalid)}门课程容量或开班下限配置无效",
                how_to_resolve="修复课程容量/开班下限后重新预检",
                selectionCourseIds=[str(row.id) for row in invalid],
            ))

    roster_validation = None
    if action == "LOCK" and str(batch.status or "").upper() == "CLOSED":
        from .academic_affairs_teaching_roster_service import validate_selection_lock
        roster_validation = validate_selection_lock(db, batch)
        for issue in list(roster_validation.get("issues") or []):
            blockers.append(_block(
                str(issue.get("code") or "SELECTION_ROSTER_INVALID"),
                str(issue.get("message") or "正式名单校验未通过"),
                how_to_resolve="处置该名单问题后重新预检",
                selectionCourseId=str(issue.get("courseId") or ""),
            ))

    return {
        "allowed": not blockers,
        "action": action,
        "batchId": str(batch.id),
        "status": str(batch.status or ""),
        "expectedStatus": expected,
        "courseCount": course_count,
        "blockers": blockers,
        "allowedActions": [action] if not blockers else ["VIEW"],
        "_rosterValidation": roster_validation,
    }


def public_result(result: dict) -> dict:
    return {key: value for key, value in result.items() if not key.startswith("_")}


def require_batch_action(db, batch, action: str) -> dict:
    result = evaluate_batch(db, batch, action)
    if not result["allowed"]:
        first = result["blockers"][0]
        raise AppException(
            "DATA_CONFLICT",
            first["message"],
            details={"preflight": public_result(result)},
            http_status=409,
        )
    return result
