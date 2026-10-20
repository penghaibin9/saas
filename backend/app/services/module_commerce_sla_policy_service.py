"""Governed tenant commercial SLA policy writer.

The policy remains a PlatformConfig fact; no second SLA authority is introduced.
Tenant-row locking serializes first creation and later updates across workers. Policy
write, optimistic version and critical audit commit in one transaction. Reset disables
the tenant override so the already-supported platform default may become effective.
No default SLA hours are manufactured by this service.
"""
from __future__ import annotations

from copy import deepcopy

from sqlalchemy import select

from app.core.exceptions import AppException, not_found
from app.db.session import db_enabled, get_sessionmaker

_CONFIG_TYPE = "COMMERCIAL_SLA_POLICY"
_CONFIG_KEY = "SUPPORT_TICKET"
_SEVERITIES = ("P0", "P1", "P2", "P3")


def _require_db() -> None:
    if not db_enabled():
        raise AppException("SERVER_ERROR", "商业 SLA 政策需要数据库", http_status=503)


def _expected(value) -> int:
    if isinstance(value, bool):
        raise AppException("VALIDATION_ERROR", "expectedVersion 必须是非负整数", http_status=422)
    try:
        parsed = int(value)
    except (TypeError, ValueError, OverflowError):
        raise AppException("VALIDATION_ERROR", "expectedVersion 必须是非负整数", http_status=422) from None
    if parsed < 0 or str(value).strip() != str(parsed):
        raise AppException("VALIDATION_ERROR", "expectedVersion 必须是非负整数", http_status=422)
    return parsed


def _reason(value) -> str:
    text = str(value or "").strip()
    if not 5 <= len(text) <= 500:
        raise AppException("VALIDATION_ERROR", "SLA 政策变更原因需为5~500字符", http_status=422)
    return text


def _payload(body: dict) -> dict:
    version = str(body.get("policyVersion") or body.get("version") or "").strip()
    if not 3 <= len(version) <= 64:
        raise AppException("VALIDATION_ERROR", "policyVersion 长度必须为3~64字符", http_status=422)
    raw = body.get("targetsHours")
    if not isinstance(raw, dict):
        raise AppException("VALIDATION_ERROR", "targetsHours 必须完整提供 P0/P1/P2/P3", http_status=422)
    targets = {}
    for severity in _SEVERITIES:
        if severity not in raw:
            raise AppException("VALIDATION_ERROR", f"targetsHours.{severity} 必填；系统不会补默认承诺", http_status=422)
        value = raw.get(severity)
        if isinstance(value, bool):
            raise AppException("VALIDATION_ERROR", f"targetsHours.{severity} 必须是正数小时", http_status=422)
        try:
            hours = float(value)
        except (TypeError, ValueError, OverflowError):
            raise AppException("VALIDATION_ERROR", f"targetsHours.{severity} 必须是正数小时", http_status=422) from None
        if not 0 < hours <= 87600:
            raise AppException("VALIDATION_ERROR", f"targetsHours.{severity} 必须在 0~87600 小时之间", http_status=422)
        targets[severity] = int(hours) if hours.is_integer() else round(hours, 2)
    return {"version": version, "targetsHours": targets}


def _row_snapshot(row) -> dict:
    if row is None:
        return {"exists": False, "enabled": False, "rowVersion": 0, "policy": None}
    return {
        "exists": True,
        "enabled": bool(row.enabled and row.status == "ACTIVE" and not row.is_deleted),
        "rowVersion": int(row.version or 0),
        "policy": deepcopy(dict(row.config_json or {})),
    }


def policy_editor(tenant_id: int) -> dict:
    _require_db()
    from app.models import PlatformConfig, Tenant
    from app.services.module_commerce_operations_service import _sla_policy

    tid = int(tenant_id)
    db = get_sessionmaker()()
    try:
        tenant = db.scalars(select(Tenant).where(Tenant.id == tid, Tenant.is_deleted.is_(False))).first()
        if tenant is None:
            raise not_found("学校不存在")
        tenant_row = db.scalars(select(PlatformConfig).where(
            PlatformConfig.tenant_id == tid,
            PlatformConfig.config_type == _CONFIG_TYPE,
            PlatformConfig.config_key == _CONFIG_KEY,
            PlatformConfig.is_deleted.is_(False),
        )).first()
        platform_row = db.scalars(select(PlatformConfig).where(
            PlatformConfig.tenant_id == 0,
            PlatformConfig.config_type == _CONFIG_TYPE,
            PlatformConfig.config_key == _CONFIG_KEY,
            PlatformConfig.is_deleted.is_(False),
        )).first()
        return {
            "tenantId": str(tid), "tenantName": tenant.school_name,
            "tenantOverride": _row_snapshot(tenant_row),
            "platformDefault": _row_snapshot(platform_row),
            "effective": _sla_policy(db, tid),
            "authority": "PLATFORM_CONFIG",
            "defaultHoursInvented": False,
        }
    finally:
        db.close()


def update_tenant_policy(user: dict | None, tenant_id: int, body: dict) -> dict:
    _require_db()
    from app.models import PlatformConfig, Tenant
    from app.services import audit_log

    tid = int(tenant_id); expected = _expected(body.get("expectedVersion")); reason = _reason(body.get("reason")); payload = _payload(body)
    db = get_sessionmaker()()
    try:
        # Parent lock is required even before the first config row exists.
        tenant = db.scalars(select(Tenant).where(
            Tenant.id == tid, Tenant.is_deleted.is_(False),
        ).with_for_update()).first()
        if tenant is None:
            raise not_found("学校不存在")
        row = db.scalars(select(PlatformConfig).where(
            PlatformConfig.tenant_id == tid,
            PlatformConfig.config_type == _CONFIG_TYPE,
            PlatformConfig.config_key == _CONFIG_KEY,
            PlatformConfig.is_deleted.is_(False),
        ).with_for_update()).first()
        current = int(row.version or 0) if row else 0
        if expected != current:
            raise AppException(
                "DATA_CONFLICT", "SLA 政策已被其他操作更新，请刷新后重试", http_status=409,
                details={"expectedVersion": expected, "currentVersion": current},
            )
        before = _row_snapshot(row)
        if row is None:
            row = PlatformConfig(
                tenant_id=tid, config_type=_CONFIG_TYPE, config_key=_CONFIG_KEY,
                config_json=payload, enabled=True, status="ACTIVE",
                remark=reason, version=1,
            )
            db.add(row)
        else:
            row.config_json = payload; row.enabled = True; row.status = "ACTIVE"
            row.remark = reason; row.version = current + 1
        db.flush()
        after = _row_snapshot(row)
        audit_log.record_critical_in_session(
            db, "COMMERCIAL_SLA_POLICY_UPDATE", f"commercial-sla:{tid}",
            detail={
                "tenantId": str(tid), "expectedVersion": expected,
                "currentVersion": after["rowVersion"], "reason": reason,
                "before": before, "after": after,
                "defaultHoursInvented": False,
                "actor": str((user or {}).get("userId") or ""),
            }, tenant_id=tid, resource_id=str(row.id),
        )
        db.commit()
        return policy_editor(tid)
    except Exception:
        db.rollback(); raise
    finally:
        db.close()


def reset_tenant_policy(user: dict | None, tenant_id: int, *, expected_version, reason: str) -> dict:
    _require_db()
    from app.models import PlatformConfig, Tenant
    from app.services import audit_log

    tid = int(tenant_id); expected = _expected(expected_version); reason_text = _reason(reason)
    db = get_sessionmaker()()
    try:
        tenant = db.scalars(select(Tenant).where(
            Tenant.id == tid, Tenant.is_deleted.is_(False),
        ).with_for_update()).first()
        if tenant is None:
            raise not_found("学校不存在")
        row = db.scalars(select(PlatformConfig).where(
            PlatformConfig.tenant_id == tid,
            PlatformConfig.config_type == _CONFIG_TYPE,
            PlatformConfig.config_key == _CONFIG_KEY,
            PlatformConfig.is_deleted.is_(False),
        ).with_for_update()).first()
        current = int(row.version or 0) if row else 0
        if expected != current:
            raise AppException(
                "DATA_CONFLICT", "SLA 政策已被其他操作更新，请刷新后重试", http_status=409,
                details={"expectedVersion": expected, "currentVersion": current},
            )
        if row is None:
            raise AppException("DATA_CONFLICT", "当前没有学校 SLA 覆盖，无需恢复平台默认", http_status=409)
        before = _row_snapshot(row)
        row.enabled = False; row.status = "DISABLED"; row.remark = reason_text; row.version = current + 1
        db.flush(); after = _row_snapshot(row)
        audit_log.record_critical_in_session(
            db, "COMMERCIAL_SLA_POLICY_RESET", f"commercial-sla:{tid}",
            detail={
                "tenantId": str(tid), "expectedVersion": expected,
                "currentVersion": after["rowVersion"], "reason": reason_text,
                "before": before, "after": after, "fallback": "PLATFORM_DEFAULT_OR_UNASSESSED",
                "actor": str((user or {}).get("userId") or ""),
            }, tenant_id=tid, resource_id=str(row.id),
        )
        db.commit()
        return policy_editor(tid)
    except Exception:
        db.rollback(); raise
    finally:
        db.close()
