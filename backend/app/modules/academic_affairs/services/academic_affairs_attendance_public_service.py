"""课堂考勤统一公开 Service。

正式考勤写事务唯一由 ``academic_affairs_attendance_teacher_relation_guard`` 持有；
关系感知台账/统计唯一由 ``academic_affairs_attendance_teacher_relation_read_guard`` 持有。
本模块只保留稳定公开入口与两类最终 Owner 共享的无状态/小型辅助函数。

历史 ``academic_affairs_attendance_service`` 已降为兼容导出，不再保存第二套考勤事务。
因此 PC、移动端、旧 import path 与直接 Service 调用都进入同一 Authority。
"""
from __future__ import annotations

import json
from datetime import datetime

from sqlalchemy import and_, or_

from app.core.affairs_security import _derive_keys
from app.core.context import get_current_user_ctx
from app.core.exceptions import AppException
from app.services.db_service import _iso, _tid, session

from .academic_affairs_attendance_occurrence_consumer import resolve_formal_occurrence

_STATUS_OK = ("PRESENT", "LATE", "ABSENT", "LEAVE")
_ADMIN_ROLES = {"ACADEMIC_ADMIN", "SCHOOL_ADMIN"}
_ADMIN_SPECIAL = "ADMIN_SPECIAL"
ATTENDANCE_TASK_STATUSES = frozenset({"TEACHER_CONFIRMED", "COLLEGE_REVIEW", "APPROVED", "READY"})
_ATTENDANCE_TASK_STATUSES = ATTENDANCE_TASK_STATUSES


def attendance_task_executable(status) -> bool:
    """Single executable-state contract shared by attendance read and write paths."""
    return str(status or "").strip().upper() in ATTENDANCE_TASK_STATUSES


def _op():
    user = get_current_user_ctx() or {}
    return (user.get("realName") or "系统"), str(user.get("userId") or "")


def _audit(db, biz_id, action, detail=""):
    from app.models import AffairsAuditTrail

    name, uid = _op()
    db.add(AffairsAuditTrail(
        tenant_id=_tid(),
        biz_type="AA_ATTENDANCE",
        biz_id=int(biz_id) if biz_id else None,
        action=action,
        operator=name or uid,
        detail=(detail or "")[:990],
        occurred_at=datetime.utcnow(),
    ))


def _role(user) -> str:
    return str((user or {}).get("currentRoleCode") or "").upper()


def _teacher_keys(user) -> set[str]:
    """工号族标识；不包含 realName，避免同名教师互相命中。"""
    return set(_derive_keys(user or {}))


def _primary_teacher_key(user) -> str | None:
    """稳定、确定性的当前教师键，仅供管理员特殊补录/历史兼容兜底。"""
    user = user or {}
    login = str(user.get("loginName") or "").strip()
    if login:
        return login
    context_id = str(user.get("activeContextId") or "").strip()
    if context_id.startswith("ctx_") and len(context_id) > 4:
        return context_id[4:]
    uid = str(user.get("userId") or "").strip()
    if uid.startswith("u_") and len(uid) > 2:
        return uid[2:]
    return uid or None


def _check_owner(attendance_session, user):
    """历史兼容 helper；正式执行路径使用 relation-aware guard。"""
    if _role(user) in _ADMIN_ROLES:
        return
    if not attendance_session.teacher_key:
        raise AppException(
            "NO_DATA_SCOPE",
            "该历史考勤场次缺少稳定教师工号，归属待教务处修复",
            http_status=403,
        )
    keys = _teacher_keys(user)
    if not keys or attendance_session.teacher_key not in keys:
        raise AppException("NO_DATA_SCOPE", "该考勤场次不在您的授课范围内", http_status=403)


def _row(item) -> dict:
    return {
        "sessionId": str(item.id),
        "classId": str(item.class_id or ""),
        "courseName": item.course_name or "",
        "termCode": item.term_code or "",
        "sessionDate": item.session_date,
        "slotNo": item.slot_no,
        "sessionType": item.session_type or "常规",
        # INT owns persisted source_type when present; C standalone remains compatible
        # with the pre-INT model where this column is not yet available.
        "sourceType": getattr(item, "source_type", None),
        "totalCount": item.total_count,
        "presentCount": item.present_count,
        "absentCount": item.absent_count,
        "status": item.status,
        "createdAt": _iso(item.created_at),
    }


def _special_evidence_text(value) -> str:
    """把特殊补录证据压成可审计文本。"""
    if value in (None, "", [], {}):
        return ""
    if isinstance(value, (dict, list, tuple)):
        text = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    else:
        text = str(value).strip()
    return text[:300]


def _admin_special_contract(role: str, body: dict, *, task_id) -> tuple[bool, str, str]:
    """隔离管理员特殊考勤旁路并冻结最小审计合同。"""
    requested_type = str(body.get("sessionType") or "").strip().upper()
    is_special = requested_type == _ADMIN_SPECIAL

    if is_special and role not in _ADMIN_ROLES:
        raise AppException(
            "NO_PERMISSION",
            "普通教师不能创建管理员特殊考勤场次",
            http_status=403,
        )
    if role in _ADMIN_ROLES and not task_id and not is_special:
        raise AppException(
            "VALIDATION_ERROR",
            "管理员脱离教学任务补录考勤必须显式选择 ADMIN_SPECIAL",
        )
    if not is_special:
        return False, "", ""

    reason = str(body.get("specialReason") or body.get("reason") or "").strip()
    if len(reason) < 5:
        raise AppException("VALIDATION_ERROR", "管理员特殊考勤原因必填且不少于5字")
    evidence = _special_evidence_text(body.get("specialEvidence", body.get("evidence")))
    if not evidence:
        raise AppException("VALIDATION_ERROR", "管理员特殊考勤必须提供可审计 evidence")
    return True, reason[:300], evidence


def _with_source_type(result: dict) -> dict:
    """Persisted source Authority wins; historical rows fall back to session_type."""
    stored_source = str(result.get("sourceType") or result.get("source_type") or "").strip().upper()
    if stored_source in {"FORMAL_TEACHING", _ADMIN_SPECIAL}:
        effective_source = stored_source
    elif stored_source:
        # A non-empty invalid source is governance debt; never silently reinterpret it as formal.
        effective_source = "UNKNOWN"
    else:
        effective_source = (
            _ADMIN_SPECIAL
            if str(result.get("sessionType") or "").strip().upper() == _ADMIN_SPECIAL
            else "FORMAL_TEACHING"
        )

    is_special = effective_source == _ADMIN_SPECIAL
    result["sourceType"] = effective_source
    result["sourceLabel"] = (
        "管理员特殊补录"
        if is_special
        else ("正式课堂" if effective_source == "FORMAL_TEACHING" else "来源待治理")
    )
    result["sessionTypeLabel"] = (
        "管理员特殊补录" if is_special else str(result.get("sessionType") or "常规")
    )
    return result


def _stats_session_type_condition(model, session_type=None):
    """INT source_type 优先；C standalone 无该列时保持 legacy session_type 口径。"""
    requested = str(session_type or "").strip()
    source_type = getattr(model, "source_type", None)

    if source_type is None:
        if requested:
            return model.session_type == requested
        return or_(
            model.session_type.is_(None),
            model.session_type != _ADMIN_SPECIAL,
        )

    if requested:
        if requested.upper() == _ADMIN_SPECIAL:
            return or_(
                source_type == _ADMIN_SPECIAL,
                and_(source_type.is_(None), model.session_type == _ADMIN_SPECIAL),
            )
        return and_(
            or_(source_type == "FORMAL_TEACHING", source_type.is_(None)),
            model.session_type == requested,
        )
    return or_(
        source_type == "FORMAL_TEACHING",
        and_(
            source_type.is_(None),
            or_(model.session_type.is_(None), model.session_type != _ADMIN_SPECIAL),
        ),
    )


def resolve_versioned_roster(*args, **kwargs):
    """Stable injectable seam for the authoritative versioned TeachingRoster resolver."""
    from .academic_affairs_roster_consumer_service import resolve_versioned_roster as resolver

    return resolver(*args, **kwargs)


def freeze_consumer_snapshot(*args, **kwargs):
    """Stable injectable seam for the immutable RosterConsumerSnapshot writer."""
    from .academic_affairs_roster_consumer_service import freeze_consumer_snapshot as freezer

    return freezer(*args, **kwargs)


def create_session(user, body) -> dict:
    """稳定公开入口：唯一委托 relation-aware 写事务。"""
    from . import academic_affairs_attendance_teacher_relation_guard as relation_guard

    return relation_guard.create_session(user, body)


def get_session(session_id, user) -> dict:
    """稳定公开入口：详情读取与执行权限共用 relation-aware Authority。"""
    from . import academic_affairs_attendance_teacher_relation_guard as relation_guard

    return relation_guard.get_session(session_id, user)


def mark_attendance(session_id, user, body) -> dict:
    """稳定公开入口：逐生点名只走 relation-aware command。"""
    from . import academic_affairs_attendance_teacher_relation_guard as relation_guard

    return relation_guard.mark_attendance(session_id, user, body)


def submit_session(session_id, user) -> dict:
    """稳定公开入口：提交只走 relation-aware command。"""
    from . import academic_affairs_attendance_teacher_relation_guard as relation_guard

    return relation_guard.submit_session(session_id, user)


def list_sessions(user, page=1, page_size=20, class_id=None, term_code=None, session_type=None):
    """稳定公开入口：台账分页只走 relation-aware read Authority。"""
    from . import academic_affairs_attendance_teacher_relation_read_guard as read_guard

    return read_guard.list_sessions(user, page, page_size, class_id, term_code, session_type)


def attendance_stats(user, class_id=None, term_code=None, session_type=None):
    """稳定公开入口：统计只走 relation-aware read Authority。"""
    from . import academic_affairs_attendance_teacher_relation_read_guard as read_guard

    return read_guard.attendance_stats(user, class_id, term_code, session_type)
