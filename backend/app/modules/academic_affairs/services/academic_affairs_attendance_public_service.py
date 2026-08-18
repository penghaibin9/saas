"""课堂考勤统一公开 Service。

本模块只保留稳定公开入口与跨适配器共享的小型辅助函数。正式考勤写事务唯一由
``academic_affairs_attendance_teacher_relation_guard`` 持有；关系感知台账/统计唯一由
``academic_affairs_attendance_teacher_relation_read_guard`` 持有。

注意：canonical attendance service 必须延迟加载。services 包初始化时 eager import 会沿
TeachingRoster -> TeachingClass 再回到 TeachingRoster，形成 import-time cycle；facade 本身
不需要在模块导入阶段触碰 canonical runtime。
"""
from __future__ import annotations

import importlib
import json

from sqlalchemy import or_

from app.core.exceptions import AppException

from .academic_affairs_attendance_occurrence_consumer import resolve_formal_occurrence

_ADMIN_ROLES = {"ACADEMIC_ADMIN", "SCHOOL_ADMIN"}
_ADMIN_SPECIAL = "ADMIN_SPECIAL"


def _canonical_service():
    """Load the mature base service only after package initialization has completed."""
    return importlib.import_module(
        ".academic_affairs_attendance_service",
        package=__package__,
    )


def __getattr__(name):
    return getattr(_canonical_service(), name)


# Guard/read adapters deliberately call these local wrappers so tests can still replace
# a single public seam without depending on import order.
def session():
    return _canonical_service().session()


def _tid():
    return _canonical_service()._tid()


def _audit(*args, **kwargs):
    return _canonical_service()._audit(*args, **kwargs)


def _role(user) -> str:
    return _canonical_service()._role(user)


def _teacher_keys(user) -> set[str]:
    return _canonical_service()._teacher_keys(user)


def _primary_teacher_key(user):
    return _canonical_service()._primary_teacher_key(user)


def _row(item) -> dict:
    return _canonical_service()._row(item)


def attendance_task_executable(status) -> bool:
    return _canonical_service().attendance_task_executable(status)


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
    """兼容旧行并优先消费已持久化的 source_type。"""
    persisted = str(result.get("sourceType") or result.get("source_type") or "").strip().upper()
    legacy_special = str(result.get("sessionType") or "").strip().upper() == _ADMIN_SPECIAL
    source_type = persisted or (_ADMIN_SPECIAL if legacy_special else "FORMAL_TEACHING")
    is_special = source_type == _ADMIN_SPECIAL
    result["sourceType"] = source_type
    result["sourceLabel"] = "管理员特殊补录" if is_special else "正式课堂"
    result["sessionTypeLabel"] = (
        "管理员特殊补录" if is_special else str(result.get("sessionType") or "常规")
    )
    return result


def _stats_session_type_condition(model, session_type=None):
    """默认课堂统计排除 ADMIN_SPECIAL；只有显式筛选时才进入特殊补录统计。"""
    requested = str(session_type or "").strip()
    if requested:
        return model.session_type == requested
    return or_(
        model.session_type.is_(None),
        model.session_type != _ADMIN_SPECIAL,
    )


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
