"""Production route replacements for Platform P1 closure work.

Keeps basic tenant-profile edits non-operational and optimistic, and makes customer
success time/state contracts deterministic even when callers bypass the UI.
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Body, Depends
from sqlalchemy import select

from app.core.exceptions import AppException
from app.core.response import success
from app.db.session import get_sessionmaker
from app.models import PlatformConfig, Tenant
from app.models.customer_success import RenewalTask, SupportTicket, TrainingRecord
from app.modules.platform.routers.platform_bundle import require_platform_super_admin

router = APIRouter(prefix="/platform", tags=["平台总控·P1生产闭环"])

_PROFILE_FIELDS = {
    "schoolType": 50,
    "province": 64,
    "city": 64,
    "contactName": 64,
    "contactPhone": 32,
    "contactWechat": 64,
    "remark": 1000,
}


def _tenant_meta_row(db, tenant_id: int, *, lock: bool = False):
    tenant = db.scalars(select(Tenant).where(
        Tenant.id == int(tenant_id), Tenant.is_deleted.is_(False),
    )).first()
    if tenant is None:
        raise AppException("DATA_NOT_FOUND", "租户不存在", http_status=404)
    stmt = select(PlatformConfig).where(
        PlatformConfig.tenant_id == int(tenant_id),
        PlatformConfig.config_type == "TENANT_META",
        PlatformConfig.config_key == "-",
        PlatformConfig.is_deleted.is_(False),
    )
    if lock:
        stmt = stmt.with_for_update()
    row = db.scalars(stmt).first()
    return tenant, row


def _profile_payload(tenant: Tenant, row: PlatformConfig | None) -> dict:
    meta = dict((row.config_json or {}) if row else {})
    return {
        "tenantId": str(tenant.id),
        "tenantCode": tenant.tenant_code,
        "tenantName": tenant.school_name,
        "schoolType": meta.get("schoolType", "VOCATIONAL"),
        "province": meta.get("province", ""),
        "city": meta.get("city", ""),
        "contactName": meta.get("contactName", ""),
        "contactPhone": meta.get("contactPhone", ""),
        "contactWechat": meta.get("contactWechat", ""),
        "remark": meta.get("remark", ""),
        # Environment changes state/destruction semantics and is intentionally read-only here.
        "environment": meta.get("environment", "production"),
        "version": int(row.version or 1) if row else 0,
    }


def _normalize_profile_patch(body: dict) -> tuple[dict, int, str]:
    body = body or {}
    if "expectedVersion" not in body:
        raise AppException("VALIDATION_ERROR", "基础资料保存必须提供 expectedVersion")
    try:
        expected = int(body.get("expectedVersion"))
    except (TypeError, ValueError):
        raise AppException("VALIDATION_ERROR", "expectedVersion 必须是整数") from None
    reason = str(body.get("reason") or "").strip()
    if len(reason) < 5:
        raise AppException("VALIDATION_ERROR", "基础资料变更原因不少于 5 个字")
    extras = set(body) - set(_PROFILE_FIELDS) - {"expectedVersion", "reason"}
    if extras:
        if "environment" in extras:
            raise AppException("VALIDATION_ERROR", "环境属于运行安全属性，不能在基础资料编辑器中修改")
        raise AppException("VALIDATION_ERROR", f"基础资料不支持修改字段：{', '.join(sorted(extras))}")
    patch = {}
    for key, limit in _PROFILE_FIELDS.items():
        if key not in body:
            continue
        value = "" if body.get(key) is None else str(body.get(key)).strip()
        if len(value) > limit:
            raise AppException("VALIDATION_ERROR", f"{key} 最长 {limit} 个字符")
        patch[key] = value
    if "schoolType" in patch and len(patch["schoolType"]) < 2:
        raise AppException("VALIDATION_ERROR", "学校类型不能为空")
    if not patch:
        raise AppException("VALIDATION_ERROR", "没有可保存的基础资料变更")
    return patch, expected, reason


def _save_profile(tenant_id: int, body: dict, user: dict) -> dict:
    patch, expected, reason = _normalize_profile_patch(body)
    db = get_sessionmaker()()
    try:
        tenant, row = _tenant_meta_row(db, tenant_id, lock=True)
        current_version = int(row.version or 1) if row else 0
        if current_version != expected:
            raise AppException(
                "DATA_CONFLICT", "租户基础资料已被其他操作更新，请刷新后重试", http_status=409,
                details={"expectedVersion": expected, "currentVersion": current_version},
            )
        before_meta = dict((row.config_json or {}) if row else {})
        after_meta = {**before_meta, **patch}
        if row is None:
            row = PlatformConfig(
                tenant_id=int(tenant_id), config_type="TENANT_META", config_key="-",
                config_json=after_meta, enabled=True,
            )
            db.add(row)
            db.flush()
        else:
            row.config_json = after_meta
            row.version = current_version + 1
            row.updated_by = None
            db.flush()
        from app.services import audit_log
        audit_log.record_critical_in_session(
            db,
            "PLATFORM_TENANT_PROFILE_UPDATE",
            f"tenant:{tenant_id}",
            detail={
                "changedKeys": sorted(patch),
                "before": {key: before_meta.get(key) for key in patch},
                "after": patch,
                "reason": reason,
                "moduleCode": "platform",
                "environmentImmutable": True,
                "actor": (user or {}).get("userId"),
            },
            tenant_id=int(tenant_id),
            resource_id=str(tenant_id),
        )
        db.commit()
        db.refresh(row)
        result = _profile_payload(tenant, row)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
    try:
        from app.services.auth_service_db import invalidate_tenant_subject_caches
        invalidate_tenant_subject_caches(int(tenant_id))
    except Exception:
        # These fields do not alter authentication/authorization; the DB write remains authoritative.
        pass
    return result


@router.get("/tenants/{tenant_id}/profile", summary="租户基础资料（环境只读）")
def tenant_profile(tenant_id: int, user=Depends(require_platform_super_admin)):
    db = get_sessionmaker()()
    try:
        tenant, row = _tenant_meta_row(db, tenant_id)
        return success(_profile_payload(tenant, row))
    finally:
        db.close()


@router.put("/tenants/{tenant_id}/profile", summary="安全修改租户基础资料")
def tenant_profile_update(
    tenant_id: int, body: dict = Body(...), user=Depends(require_platform_super_admin)
):
    return success(_save_profile(tenant_id, body, user), message="租户基础资料已保存")


@router.put("/tenants/{tenant_id}", summary="租户基础信息修改（兼容入口，执行同一生产约束）")
def tenant_update_compat(
    tenant_id: int, body: dict = Body(...), user=Depends(require_platform_super_admin)
):
    return success(_save_profile(tenant_id, body, user), message="租户基础资料已保存")


def _utc_naive(value, field: str) -> datetime:
    if value in (None, ""):
        raise AppException("VALIDATION_ERROR", f"{field} 不能为空")
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError as exc:
        raise AppException("VALIDATION_ERROR", f"{field} 必须是 ISO8601 时间") from exc
    if parsed.tzinfo is not None:
        return parsed.astimezone(timezone.utc).replace(tzinfo=None, microsecond=0)
    # Backward compatibility: historic naive values are treated as UTC because the
    # customer-health service compares them with datetime.utcnow().
    return parsed.replace(microsecond=0)


def _ensure_tenant(tenant_id: int) -> None:
    from app.services import platform_service as svc
    svc.get_tenant(int(tenant_id))


def _current_row(model, row_id: int):
    db = get_sessionmaker()()
    try:
        row = db.get(model, int(row_id))
        if row is None or row.is_deleted:
            raise AppException("DATA_NOT_FOUND", "记录不存在", http_status=404)
        return str(row.status or "").upper(), int(row.version or 0)
    finally:
        db.close()


@router.post("/support-tickets/{ticket_id}/transition", summary="流转客户工单（状态机）")
def support_ticket_transition(
    ticket_id: int, body: dict = Body(...), user=Depends(require_platform_super_admin)
):
    from app.modules.platform.routers.platform_bundle import _audit, _expected_version
    from app.services import customer_health_service as cs
    target = str((body or {}).get("status") or "").upper()
    current, current_version = _current_row(SupportTicket, ticket_id)
    allowed = {
        "OPEN": {"IN_PROGRESS", "RESOLVED"},
        "IN_PROGRESS": {"RESOLVED"},
        "RESOLVED": {"IN_PROGRESS", "CLOSED"},
        "CLOSED": set(),
    }
    if target not in allowed.get(current, set()):
        raise AppException("STATE_TRANSITION_DENIED", f"工单不能从 {current} 变更为 {target}", http_status=409)
    expected = _expected_version(body or {}, operation="流转工单")
    if expected != current_version:
        raise AppException("VERSION_CONFLICT", "工单已被修改，请刷新后重试", http_status=409)
    out = cs.transition_ticket(
        ticket_id, status=target, resolution_note=(body or {}).get("resolutionNote") or "",
        expected_version=expected,
    )
    _audit("PLATFORM_SUPPORT_TICKET_TRANSITION", str(ticket_id), out, tenant_id=int(out["tenantId"]))
    return success(out, message="工单状态已更新")


@router.post("/trainings", summary="登记客户培训计划（UTC 契约）")
def training_create(body: dict = Body(...), user=Depends(require_platform_super_admin)):
    from app.modules.platform.routers.platform_bundle import _audit
    from app.services import customer_health_service as cs
    tenant_id = int((body or {}).get("tenantId") or 0)
    if tenant_id <= 0:
        raise AppException("VALIDATION_ERROR", "必须指定 tenantId")
    _ensure_tenant(tenant_id)
    scheduled = _utc_naive((body or {}).get("scheduledAt"), "scheduledAt")
    out = cs.create_training(
        tenant_id=tenant_id, topic=(body or {}).get("topic") or "", scheduled_at=scheduled,
        trainer_name=(body or {}).get("trainerName") or "",
    )
    _audit("PLATFORM_TRAINING_CREATE", out["id"], out, tenant_id=tenant_id)
    return success(out, message="培训计划已登记")


@router.post("/trainings/{training_id}/complete", summary="完成客户培训（仅 SCHEDULED 可完成）")
def training_complete(
    training_id: int, body: dict = Body(...), user=Depends(require_platform_super_admin)
):
    from app.modules.platform.routers.platform_bundle import _audit, _expected_version
    from app.services import customer_health_service as cs
    current, current_version = _current_row(TrainingRecord, training_id)
    if current != "SCHEDULED":
        raise AppException("STATE_TRANSITION_DENIED", f"培训处于 {current}，不能重复标记完成", http_status=409)
    expected = _expected_version(body or {}, operation="标记培训完成")
    if expected != current_version:
        raise AppException("VERSION_CONFLICT", "培训记录已被修改，请刷新后重试", http_status=409)
    try:
        attendee_count = int((body or {}).get("attendeeCount") or 0)
    except (TypeError, ValueError):
        raise AppException("VALIDATION_ERROR", "参训人数必须是整数") from None
    if attendee_count < 0:
        raise AppException("VALIDATION_ERROR", "参训人数不能为负数")
    out = cs.complete_training(
        training_id, attendee_count=attendee_count, note=(body or {}).get("note") or "",
        expected_version=expected,
    )
    _audit("PLATFORM_TRAINING_COMPLETE", str(training_id), out, tenant_id=int(out["tenantId"]))
    return success(out, message="培训已标记完成")


@router.post("/renewal-tasks", summary="创建续费跟进（UTC 契约）")
def renewal_create(body: dict = Body(...), user=Depends(require_platform_super_admin)):
    from app.modules.platform.routers.platform_bundle import _audit
    from app.services import customer_health_service as cs
    tenant_id = int((body or {}).get("tenantId") or 0)
    if tenant_id <= 0:
        raise AppException("VALIDATION_ERROR", "必须指定 tenantId")
    _ensure_tenant(tenant_id)
    due_at = _utc_naive((body or {}).get("dueAt"), "dueAt")
    out = cs.create_renewal_task(
        tenant_id=tenant_id, due_at=due_at,
        owner_name=(body or {}).get("ownerName") or "", note=(body or {}).get("note") or "",
    )
    _audit("PLATFORM_RENEWAL_TASK_CREATE", out["id"], out, tenant_id=tenant_id)
    return success(out, message="续费任务已创建")


@router.post("/renewal-tasks/{task_id}/transition", summary="流转续费任务（终态不可逆）")
def renewal_transition(
    task_id: int, body: dict = Body(...), user=Depends(require_platform_super_admin)
):
    from app.modules.platform.routers.platform_bundle import _audit, _expected_version
    from app.services import customer_health_service as cs
    target = str((body or {}).get("status") or "").upper()
    current, current_version = _current_row(RenewalTask, task_id)
    allowed = {
        "PENDING": {"CONTACTED", "COMMITTED", "RENEWED", "CHURNED"},
        "CONTACTED": {"COMMITTED", "RENEWED", "CHURNED"},
        "COMMITTED": {"RENEWED", "CHURNED"},
        "RENEWED": set(),
        "CHURNED": set(),
    }
    if target not in allowed.get(current, set()):
        raise AppException("STATE_TRANSITION_DENIED", f"续费任务不能从 {current} 变更为 {target}", http_status=409)
    expected = _expected_version(body or {}, operation="流转续费任务")
    if expected != current_version:
        raise AppException("VERSION_CONFLICT", "续费任务已被修改，请刷新后重试", http_status=409)
    out = cs.update_renewal_task(
        task_id, status=target, note=(body or {}).get("note") or "", expected_version=expected,
    )
    _audit("PLATFORM_RENEWAL_TASK_TRANSITION", str(task_id), out, tenant_id=int(out["tenantId"]))
    return success(out, message="续费任务状态已更新")
