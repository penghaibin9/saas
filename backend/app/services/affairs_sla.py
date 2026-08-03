"""学工时效 SLA 单一配置源。"""
from __future__ import annotations

import json
from datetime import datetime, timedelta
from math import isfinite

from app.core.config import settings

RISK_SLA_DEFAULTS = {
    "CRITICAL": {"assignHours": 1, "processHours": 24, "followHours": 24},
    "HIGH": {"assignHours": 2, "processHours": 48, "followHours": 48},
    "MEDIUM": {"assignHours": 4, "processHours": 72, "followHours": 72},
    "LOW": {"assignHours": 8, "processHours": 120, "followHours": 120},
}
LEAVE_SLA_DEFAULTS = {
    "approvalHours": 24,
    "nearDueHours": 12,
    "cancelHours": 24,
    "extensionApprovalHours": 24,
}

_OPEN_HANDLE_STATUSES = frozenset({"PROCESSING", "FOLLOWING"})


def _positive_number(value, fallback):
    try:
        value = float(value)
    except (TypeError, ValueError):
        return fallback
    return value if isfinite(value) and value > 0 else fallback


def _json_object(value) -> dict:
    try:
        parsed = json.loads(value or "{}")
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _tenant_json(key: str, fallback_text: str = "") -> dict:
    """读取当前租户生效 JSON；配置缺失/表未迁移时安全回落环境默认。"""
    try:
        from sqlalchemy import select
        from app.db.session import db_enabled, get_sessionmaker
        from app.models import SysConfig
        from app.services.db_service import _tid
        if not db_enabled():
            return _json_object(fallback_text)
        db = get_sessionmaker()()
        try:
            row = db.scalars(select(SysConfig).where(
                SysConfig.tenant_id == _tid(),
                SysConfig.config_key == key,
                SysConfig.is_deleted.is_(False),
            )).first()
            return _json_object(row.value_text if row and row.value_text else fallback_text)
        finally:
            db.close()
    except Exception:
        return _json_object(fallback_text)


def _risk_unknown_fallback() -> dict:
    process = _positive_number(
        getattr(settings, "AFFAIRS_RISK_ASSIGNED_PROCESS_HOURS", 72), 72)
    return {
        "assignHours": _positive_number(
            getattr(settings, "AFFAIRS_RISK_NEW_ASSIGN_HOURS", 4), 4),
        "processHours": process,
        "followHours": process,
    }


def get_risk_sla(level: str | None) -> dict:
    """返回等级当前生效 SLA；未知等级沿用旧全局默认作为兼容回退。"""
    code = str(level or "").upper()
    defaults = RISK_SLA_DEFAULTS.get(code, _risk_unknown_fallback())
    configured = _tenant_json(
        "AFFAIRS_RISK_SLA_JSON", getattr(settings, "AFFAIRS_RISK_SLA_JSON", "")
    ).get(code, {})
    configured = configured if isinstance(configured, dict) else {}
    process = _positive_number(configured.get("processHours"), defaults["processHours"])
    return {
        "assignHours": _positive_number(configured.get("assignHours"), defaults["assignHours"]),
        "processHours": process,
        "followHours": _positive_number(
            configured.get("followHours"), defaults.get("followHours", process)),
    }


def get_leave_sla() -> dict:
    configured = _tenant_json(
        "AFFAIRS_LEAVE_SLA_JSON", getattr(settings, "AFFAIRS_LEAVE_SLA_JSON", "")
    )
    return {
        key: _positive_number(configured.get(key), value)
        for key, value in LEAVE_SLA_DEFAULTS.items()
    }


def risk_due_at(record) -> datetime | None:
    """按当前风险状态返回当前阶段截止时间。

    NEW → 分派时限；ASSIGNED → 首次处置时限；
    PROCESSING/FOLLOWING → 自最近更新起的跟进/办结时限（卡住无更新则超时升级）。
    """
    sla = get_risk_sla(getattr(record, "risk_level", None))
    status = getattr(record, "status", None)
    if status == "NEW" and getattr(record, "created_at", None):
        return record.created_at + timedelta(hours=sla["assignHours"])
    if status == "ASSIGNED" and getattr(record, "assigned_at", None):
        return record.assigned_at + timedelta(hours=sla["processHours"])
    if status in _OPEN_HANDLE_STATUSES:
        start = getattr(record, "updated_at", None) or getattr(record, "assigned_at", None)
        if start:
            return start + timedelta(hours=sla["followHours"])
    return None


def risk_is_overdue(record, now: datetime | None = None) -> bool:
    """与扫描、详情和统计共用的风险超时判定。"""
    if getattr(record, "status", None) == "ESCALATED":
        return True
    due_at = risk_due_at(record)
    return bool(due_at and due_at <= (now or datetime.utcnow()))


def leave_approval_deadline(created_at: datetime | None) -> datetime | None:
    return created_at + timedelta(hours=get_leave_sla()["approvalHours"]) if created_at else None


def leave_is_pending_approval_overdue(record, now: datetime | None = None) -> bool:
    return bool(
        getattr(record, "affairs_status", None)
        in {"COUNSELOR_REVIEW", "COLLEGE_REVIEW", "STUDENT_AFFAIRS_REVIEW"}
        and (deadline := leave_approval_deadline(getattr(record, "created_at", None)))
        and deadline <= (now or datetime.utcnow())
    )
