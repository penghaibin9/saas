"""M3-M5 module-commerce portfolio, reversible stop and governed export acceptance.

This service deliberately stops before physical purge. It never freezes a whole
tenant, revokes tenant-wide sessions, deletes business rows or deletes file bytes.
"""
from __future__ import annotations

from datetime import datetime, timedelta
import hashlib
import json

from sqlalchemy import func, select

from app.core.exceptions import AppException
from app.db.session import db_enabled, get_sessionmaker

CANONICAL_MODULES = ("internship", "graduationDesign", "studentAffairs", "academicAffairs")
ACTIVE_JOB_STATES = {
    "REQUESTED", "PRECHECK", "FREEZING", "FROZEN", "EXPORTING",
    "WAIT_EXPORT_ACCEPT", "RETENTION", "BLOCKED", "FAILED",
}
IRREVERSIBLE_JOB_STATES = {"PURGE_READY", "PURGING", "VERIFYING", "SUCCEEDED"}
MODULE_ALIASES = {
    "internship": "internship", "INTERNSHIP": "internship",
    "graduation": "graduationDesign", "GRADUATION": "graduationDesign",
    "graduationDesign": "graduationDesign", "GRADUATION_DESIGN": "graduationDesign",
    "studentAffairs": "studentAffairs", "STUDENT_AFFAIRS": "studentAffairs", "AFFAIRS": "studentAffairs",
    "academicAffairs": "academicAffairs", "ACADEMIC_AFFAIRS": "academicAffairs", "ACADEMIC": "academicAffairs",
}
DELIVERY_ACCEPTANCE_CONFIG = "MODULE_DELIVERY_ACCEPTANCE"


def canonical_module(value: str) -> str:
    raw = str(value or "").strip()
    module = MODULE_ALIASES.get(raw) or MODULE_ALIASES.get(raw.upper())
    if module not in CANONICAL_MODULES:
        raise AppException("VALIDATION_ERROR", f"未知商业模块：{value}", http_status=422)
    return module


def _actor_id(user: dict | None) -> int | None:
    raw = str((user or {}).get("userId") or "").removeprefix("db-")
    return int(raw) if raw.isdigit() else None


def _require_db() -> None:
    if not db_enabled():
        raise AppException("SERVER_ERROR", "模块商业生命周期需要数据库")


def _sha(value) -> str:
    text = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _current_source(row, now: datetime) -> bool:
    return bool(row.status in {"ACTIVE", "SCHEDULED"} and row.starts_at <= now and row.ends_at > now)


def _preserving_source(row, now: datetime) -> bool:
    return bool(row.status in {"ACTIVE", "SCHEDULED"} and row.ends_at > now)


def _module_state(db, tenant_id: int, module_key: str, *, lock: bool = False):
    from app.models import TenantModuleState
    q = select(TenantModuleState).where(
        TenantModuleState.tenant_id == int(tenant_id), TenantModuleState.module_key == module_key,
        TenantModuleState.is_deleted.is_(False),
    )
    if lock: q = q.with_for_update()
    return db.scalars(q).first()


def _sources(db, tenant_id: int, module_key: str, *, lock: bool = False):
    from app.models import TenantModuleSubscriptionSource
    q = select(TenantModuleSubscriptionSource).where(
        TenantModuleSubscriptionSource.tenant_id == int(tenant_id),
        TenantModuleSubscriptionSource.module_key == module_key,
        TenantModuleSubscriptionSource.is_deleted.is_(False),
    ).order_by(TenantModuleSubscriptionSource.starts_at, TenantModuleSubscriptionSource.id)
    if lock: q = q.with_for_update()
    return list(db.scalars(q).all())


def _active_cancel_plan(db, tenant_id: int, source_id: int, *, lock: bool = False):
    from app.models import TenantModuleCancellationPlan
    q = select(TenantModuleCancellationPlan).where(
        TenantModuleCancellationPlan.tenant_id == int(tenant_id),
        TenantModuleCancellationPlan.source_id == int(source_id),
        TenantModuleCancellationPlan.is_deleted.is_(False),
    )
    if lock: q = q.with_for_update()
    return db.scalars(q).first()


def _active_module_job(db, tenant_id: int, module_key: str, *, lock: bool = False):
    from app.models import TenantModuleOffboardingJob
    q = select(TenantModuleOffboardingJob).where(
        TenantModuleOffboardingJob.tenant_id == int(tenant_id),
        TenantModuleOffboardingJob.module_key == module_key,
        TenantModuleOffboardingJob.state.in_(tuple(ACTIVE_JOB_STATES)),
        TenantModuleOffboardingJob.is_deleted.is_(False),
    ).order_by(TenantModuleOffboardingJob.id.desc())
    if lock: q = q.with_for_update()
    return db.scalars(q).first()


def _tenant_offboarding_job(db, tenant_id: int):
    from app.models.tenant_offboarding import TenantOffboardingJob
    from app.services.tenant_offboarding_service import ACTIVE_STATES
    return db.scalars(select(TenantOffboardingJob).where(
        TenantOffboardingJob.tenant_id == int(tenant_id),
        TenantOffboardingJob.state.in_(tuple(ACTIVE_STATES)),
        TenantOffboardingJob.is_deleted.is_(False),
    ).order_by(TenantOffboardingJob.id.desc())).first()


def _set_step(db, job, code: str, status: str, *, result: dict | None = None, error: str | None = None) -> None:
    from app.models import TenantModuleOffboardingStep
    row = db.scalars(select(TenantModuleOffboardingStep).where(
        TenantModuleOffboardingStep.job_id == int(job.id),
        TenantModuleOffboardingStep.step_code == code,
        TenantModuleOffboardingStep.is_deleted.is_(False),
    ).with_for_update()).first()
    now = datetime.utcnow()
    if row is None:
        row = TenantModuleOffboardingStep(tenant_id=int(job.tenant_id), job_id=int(job.id), step_code=code, status=status, attempts=0)
        db.add(row)
    row.status = status
    row.attempts = int(row.attempts or 0) + (1 if status == "RUNNING" else 0)
    if result is not None: row.result_json = dict(result)
    row.last_error = error
    if status == "RUNNING": row.started_at = now
    if status in {"SUCCEEDED", "FAILED", "BLOCKED", "CANCELLED"}: row.finished_at = now


def _source_digest(rows) -> str:
    return _sha([{
        "id": int(row.id), "version": int(row.version or 0), "moduleGeneration": int(row.module_generation),
        "sourceType": row.source_type, "sourceRef": row.source_ref,
        "startsAt": row.starts_at.isoformat(timespec="seconds"), "endsAt": row.ends_at.isoformat(timespec="seconds"),
        "status": row.status, "features": dict(row.feature_snapshot_json or {}), "quotas": dict(row.quota_snapshot_json or {}),
    } for row in rows])


def _module_logical_file_bytes(db, tenant_id: int, module_key: str) -> int:
    from app.models.file import FileBinding, FileObject
    aliases = {
        "internship": {"internship", "INTERNSHIP"},
        "graduationDesign": {"graduation", "graduationDesign", "GRADUATION"},
        "studentAffairs": {"studentAffairs", "STUDENT_AFFAIRS", "AFFAIRS"},
        "academicAffairs": {"academicAffairs", "ACADEMIC_AFFAIRS", "ACADEMIC"},
    }[module_key]
    ids = set(db.scalars(select(FileBinding.file_id).where(
        FileBinding.tenant_id == int(tenant_id), FileBinding.module_code.in_(tuple(aliases)),
        FileBinding.status == "ACTIVE", FileBinding.is_deleted.is_(False),
    )).all())
    if not ids: return 0
    return int(db.scalar(select(func.coalesce(func.sum(FileObject.size_bytes), 0)).where(
        FileObject.tenant_id == int(tenant_id), FileObject.id.in_(ids), FileObject.is_deleted.is_(False),
    )) or 0)


def _held_reservation_bytes(db, tenant_id: int, module_key: str, now: datetime) -> int:
    from app.models.file_quota import FileStorageQuotaReservation
    aliases = {
        "internship": {"internship", "INTERNSHIP"},
        "graduationDesign": {"graduation", "graduationDesign", "GRADUATION"},
        "studentAffairs": {"studentAffairs", "STUDENT_AFFAIRS", "AFFAIRS"},
        "academicAffairs": {"academicAffairs", "ACADEMIC_AFFAIRS", "ACADEMIC"},
    }[module_key]
    return int(db.scalar(select(func.coalesce(func.sum(FileStorageQuotaReservation.reserved_bytes), 0)).where(
        FileStorageQuotaReservation.tenant_id == int(tenant_id), FileStorageQuotaReservation.module_code.in_(tuple(aliases)),
        FileStorageQuotaReservation.status == "HELD", FileStorageQuotaReservation.expires_at > now,
        FileStorageQuotaReservation.is_deleted.is_(False),
    )) or 0)


def _latest_delivery_acceptance(db, tenant_id: int, module_key: str, generation: int) -> dict | None:
    from app.models import PlatformConfig
    rows = list(db.scalars(select(PlatformConfig).where(
        PlatformConfig.tenant_id == int(tenant_id), PlatformConfig.config_type == DELIVERY_ACCEPTANCE_CONFIG,
        PlatformConfig.is_deleted.is_(False),
    ).order_by(PlatformConfig.id.desc())).all())
    for row in rows:
        data = dict(row.config_json or {})
        if data.get("moduleKey") == module_key and int(data.get("moduleGeneration") or 0) == int(generation): return data
    return None


def tenant_module_portfolio(tenant_id: int) -> dict:
    _require_db()
    from app.models import Tenant
    from app.models.file import FileObject
    from app.services import module_subscription_service as subscriptions
    from app.services import system_governance_service as gov
    now = datetime.utcnow(); db = get_sessionmaker()()
    try:
        tenant = db.get(Tenant, int(tenant_id))
        if tenant is None or tenant.is_deleted: raise AppException("DATA_NOT_FOUND", "租户不存在", http_status=404)
        school_gate = gov.get_module_features(int(tenant_id)) or {}
        physical_file_bytes = int(db.scalar(select(func.coalesce(func.sum(FileObject.size_bytes), 0)).where(
            FileObject.tenant_id == int(tenant_id), FileObject.is_deleted.is_(False),
        )) or 0)
        output = []
        for module in CANONICAL_MODULES:
            state = _module_state(db, tenant_id, module); rows = _sources(db, tenant_id, module)
            current = [row for row in rows if _current_source(row, now)]
            preserving = [row for row in rows if _preserving_source(row, now)]; plans = {}
            for row in rows:
                plan = _active_cancel_plan(db, tenant_id, int(row.id))
                if plan is not None and plan.status == "SCHEDULED": plans[int(row.id)] = plan
            quotas = subscriptions._quota_projection(current); generation = int(state.generation) if state else 0
            gate = school_gate.get(module) or school_gate.get("graduation" if module == "graduationDesign" else module) or {}
            job = _active_module_job(db, tenant_id, module)
            output.append({
                "moduleKey": module, "generation": generation,
                "lifecycleVersion": int(state.lifecycle_version) if state else 0,
                "dataState": str(state.data_state) if state else "NONE", "entitled": bool(current),
                "schoolEnabled": bool(gate.get("enabled", True)) if current else False,
                "currentSourceCount": len(current), "preservingSourceCount": len(preserving),
                "sourceDigest": _source_digest(current), "quotas": quotas,
                "logicalFileBytes": _module_logical_file_bytes(db, tenant_id, module),
                "heldReservationBytes": _held_reservation_bytes(db, tenant_id, module, now),
                "deliveryAcceptance": _latest_delivery_acceptance(db, tenant_id, module, generation),
                "offboardingJobId": str(job.id) if job is not None else None,
                "sources": [{
                    "sourceId": str(row.id), "sourceType": row.source_type, "sourceRef": row.source_ref,
                    "status": "CANCEL_SCHEDULED" if int(row.id) in plans else row.status,
                    "startsAt": row.starts_at.isoformat(timespec="seconds"), "endsAt": row.ends_at.isoformat(timespec="seconds"),
                    "version": int(row.version or 0),
                    "cancelPlanVersion": int(plans[int(row.id)].version or 0) if int(row.id) in plans else None,
                } for row in rows],
            })
        return {"tenantId": str(tenant.id), "tenantCode": tenant.tenant_code, "tenantName": tenant.school_name,
                "physicalTenantFileBytes": physical_file_bytes, "modules": output, "physicalBytesMayBeShared": True}
    finally: db.close()


def accept_module_delivery(user: dict, tenant_id: int, module_key: str, *, acceptance_ref: str, reason: str, expected_generation: int) -> dict:
    _require_db(); from app.models import PlatformConfig; from app.services import audit_log
    module = canonical_module(module_key); ref = str(acceptance_ref or "").strip(); reason_text = str(reason or "").strip()
    if len(ref) < 6 or len(reason_text) < 5: raise AppException("VALIDATION_ERROR", "验收编号至少6字符，验收说明至少5字符", http_status=422)
    db = get_sessionmaker()()
    try:
        state = _module_state(db, tenant_id, module, lock=True)
        if state is None or int(state.generation) != int(expected_generation): raise AppException("DATA_CONFLICT", "模块代次已变化，请刷新后验收", http_status=409)
        if str(state.data_state).upper() != "AVAILABLE": raise AppException("DATA_CONFLICT", "模块当前不处于可交付状态", http_status=409)
        now = datetime.utcnow(); current = [row for row in _sources(db, tenant_id, module, lock=True) if _current_source(row, now)]
        if not current: raise AppException("DATA_CONFLICT", "没有有效已付模块来源，禁止形成交付验收", http_status=409)
        digest = _source_digest(current); key = f"{module}:{int(state.generation)}:{digest[:32]}"
        existing = db.scalars(select(PlatformConfig).where(
            PlatformConfig.tenant_id == int(tenant_id), PlatformConfig.config_type == DELIVERY_ACCEPTANCE_CONFIG,
            PlatformConfig.config_key == key, PlatformConfig.is_deleted.is_(False),
        ).with_for_update()).first()
        payload = {"moduleKey": module, "moduleGeneration": int(state.generation), "lifecycleVersion": int(state.lifecycle_version),
                   "sourceDigest": digest, "acceptanceRef": ref, "reason": reason_text,
                   "acceptedBy": str((user or {}).get("userId") or ""), "acceptedAt": now.isoformat(timespec="seconds")}
        if existing is not None:
            old = dict(existing.config_json or {})
            if old.get("acceptanceRef") == ref and old.get("sourceDigest") == digest: return {**old, "replayed": True}
            raise AppException("DATA_CONFLICT", "当前合同来源已存在不同验收记录", http_status=409)
        row = PlatformConfig(tenant_id=int(tenant_id), config_type=DELIVERY_ACCEPTANCE_CONFIG, config_key=key,
            config_json=payload, enabled=True, status="ACTIVE", remark=reason_text, created_by=_actor_id(user), updated_by=_actor_id(user))
        db.add(row); db.flush(); audit_log.record_critical_in_session(db, "COMMERCIAL_MODULE_DELIVERY_ACCEPT",
            f"module:{tenant_id}:{module}:{state.generation}", detail=payload, tenant_id=int(tenant_id), resource_id=str(row.id))
        db.commit(); return {**payload, "replayed": False}
    except Exception: db.rollback(); raise
    finally: db.close()


def schedule_source_cancellation(user: dict, tenant_id: int, source_id: int, *, expected_version: int, reason: str) -> dict:
    _require_db(); from app.models import TenantModuleCancellationPlan, TenantModuleSubscriptionSource; from app.services import audit_log
    reason_text = str(reason or "").strip()
    if len(reason_text) < 5: raise AppException("VALIDATION_ERROR", "计划退订原因至少5个字符", http_status=422)
    db = get_sessionmaker()()
    try:
        source = db.scalars(select(TenantModuleSubscriptionSource).where(
            TenantModuleSubscriptionSource.id == int(source_id), TenantModuleSubscriptionSource.tenant_id == int(tenant_id),
            TenantModuleSubscriptionSource.is_deleted.is_(False),).with_for_update()).first()
        if source is None: raise AppException("DATA_NOT_FOUND", "模块订阅来源不存在", http_status=404)
        if int(source.version or 0) != int(expected_version): raise AppException("DATA_CONFLICT", "订阅来源已变化，请刷新后重试", http_status=409)
        if source.status not in {"ACTIVE", "SCHEDULED"} or source.ends_at <= datetime.utcnow(): raise AppException("DATA_CONFLICT", "该来源已终止或已到期，不能计划退订", http_status=409)
        plan = _active_cancel_plan(db, tenant_id, source_id, lock=True)
        if plan is not None and plan.status == "SCHEDULED": return {"sourceId": str(source.id), "planId": str(plan.id), "status": "CANCEL_SCHEDULED", "effectiveAt": plan.effective_at.isoformat(timespec="seconds"), "version": int(plan.version or 0), "replayed": True}
        if plan is None:
            plan = TenantModuleCancellationPlan(tenant_id=int(tenant_id), source_id=int(source.id), module_key=source.module_key,
                module_generation=int(source.module_generation), status="SCHEDULED", effective_at=source.ends_at,
                reason=reason_text, requested_by=_actor_id(user), requested_at=datetime.utcnow()); db.add(plan)
        else:
            plan.status = "SCHEDULED"; plan.effective_at = source.ends_at; plan.reason = reason_text; plan.requested_by = _actor_id(user)
            plan.requested_at = datetime.utcnow(); plan.cancelled_at = None; plan.version = int(plan.version or 0) + 1
        db.flush(); audit_log.record_critical_in_session(db, "COMMERCIAL_MODULE_SOURCE_CANCEL_SCHEDULE", f"module-source:{source.id}",
            detail={"tenantId": str(tenant_id), "moduleKey": source.module_key, "effectiveAt": source.ends_at.isoformat(timespec="seconds"), "reason": reason_text},
            tenant_id=int(tenant_id), resource_id=str(plan.id)); db.commit()
        return {"sourceId": str(source.id), "planId": str(plan.id), "status": "CANCEL_SCHEDULED", "effectiveAt": plan.effective_at.isoformat(timespec="seconds"), "version": int(plan.version or 0), "replayed": False}
    except Exception: db.rollback(); raise
    finally: db.close()


def resume_source_renewal(user: dict, tenant_id: int, source_id: int, *, expected_plan_version: int, reason: str) -> dict:
    _require_db(); from app.services import audit_log; reason_text = str(reason or "").strip()
    if len(reason_text) < 5: raise AppException("VALIDATION_ERROR", "恢复续费原因至少5个字符", http_status=422)
    db = get_sessionmaker()()
    try:
        plan = _active_cancel_plan(db, tenant_id, source_id, lock=True)
        if plan is None: raise AppException("DATA_NOT_FOUND", "计划退订记录不存在", http_status=404)
        if int(plan.version or 0) != int(expected_plan_version): raise AppException("DATA_CONFLICT", "计划退订记录已变化，请刷新后重试", http_status=409)
        if plan.status == "CANCELLED": return {"sourceId": str(source_id), "status": "ACTIVE", "version": int(plan.version or 0), "replayed": True}
        if plan.status != "SCHEDULED" or plan.effective_at <= datetime.utcnow(): raise AppException("DATA_CONFLICT", "计划已生效或状态不可恢复", http_status=409)
        plan.status = "CANCELLED"; plan.cancelled_at = datetime.utcnow(); plan.version = int(plan.version or 0) + 1
        audit_log.record_critical_in_session(db, "COMMERCIAL_MODULE_SOURCE_CANCEL_UNDO", f"module-source:{source_id}",
            detail={"tenantId": str(tenant_id), "moduleKey": plan.module_key, "reason": reason_text}, tenant_id=int(tenant_id), resource_id=str(plan.id)); db.commit()
        return {"sourceId": str(source_id), "status": "ACTIVE", "version": int(plan.version), "replayed": False}
    except Exception: db.rollback(); raise
    finally: db.close()


def preview_module_offboarding(tenant_id: int, module_key: str) -> dict:
    _require_db(); module = canonical_module(module_key); now = datetime.utcnow(); db = get_sessionmaker()()
    try:
        state = _module_state(db, tenant_id, module)
        if state is None: raise AppException("DATA_NOT_FOUND", "模块实例不存在", http_status=404)
        preserving = [row for row in _sources(db, tenant_id, module) if _preserving_source(row, now)]
        tenant_job = _tenant_offboarding_job(db, tenant_id); module_job = _active_module_job(db, tenant_id, module); blockers = []
        if preserving: blockers.append({"code": "ACTIVE_SUBSCRIPTION_SOURCE", "message": "仍有当前或未来有效的订阅来源；先等待服务期结束或按合同终止来源", "sourceIds": [str(row.id) for row in preserving]})
        if tenant_job is not None: blockers.append({"code": "TENANT_OFFBOARDING_ACTIVE", "message": "整校退出任务正在进行，禁止同时发起模块退出", "jobId": str(tenant_job.id)})
        if module_job is not None: blockers.append({"code": "MODULE_OFFBOARDING_ACTIVE", "message": "该模块已有未结束退出任务", "jobId": str(module_job.id)})
        basis = {"tenantId": str(tenant_id), "moduleKey": module, "moduleGeneration": int(state.generation),
                 "lifecycleVersion": int(state.lifecycle_version), "dataState": str(state.data_state), "preservingSourceIds": [int(row.id) for row in preserving]}
        return {**basis, "scopeHash": _sha(basis), "blockers": blockers, "canRequest": not blockers and str(state.data_state).upper() == "AVAILABLE",
                "irreversibleExecutionAvailable": False, "nextStage": "M5_EXPORT_AND_ACCEPTANCE"}
    finally: db.close()


def request_module_offboarding(user: dict, tenant_id: int, module_key: str, *, expected_lifecycle_version: int, reason: str, retention_days: int, retention_policy_version: str) -> dict:
    _require_db(); from app.models import TenantModuleOffboardingJob; from app.services import audit_log; from app.services.auth_service_db import invalidate_tenant_subject_caches
    module = canonical_module(module_key); reason_text = str(reason or "").strip(); policy = str(retention_policy_version or "").strip()
    if len(reason_text) < 10 or not policy or not 1 <= int(retention_days) <= 3650: raise AppException("VALIDATION_ERROR", "退订原因至少10字符，且必须提供1-3650天的明确保留政策", http_status=422)
    db = get_sessionmaker()()
    try:
        state = _module_state(db, tenant_id, module, lock=True)
        if state is None: raise AppException("DATA_NOT_FOUND", "模块实例不存在", http_status=404)
        current_version = int(state.lifecycle_version or 0)
        if current_version != int(expected_lifecycle_version): raise AppException("DATA_CONFLICT", "模块生命周期已变化，请刷新后重试", http_status=409)
        if str(state.data_state).upper() in {"PURGING", "PURGED"}: raise AppException("DATA_CONFLICT", "模块已进入不可逆阶段，不能重新发起", http_status=409)
        now = datetime.utcnow(); preserving = [row for row in _sources(db, tenant_id, module, lock=True) if _preserving_source(row, now)]
        if preserving: raise AppException("DATA_CONFLICT", "仍有有效订阅来源，禁止冻结整个模块实例", http_status=409, details={"sourceIds": [str(row.id) for row in preserving]})
        tenant_job = _tenant_offboarding_job(db, tenant_id)
        if tenant_job is not None: raise AppException("DATA_CONFLICT", "整校退出任务正在进行，禁止模块退出", http_status=409, details={"jobId": str(tenant_job.id)})
        existing = _active_module_job(db, tenant_id, module, lock=True)
        if existing is not None: raise AppException("DATA_CONFLICT", "该模块已有未结束退出任务", http_status=409, details={"jobId": str(existing.id), "state": existing.state})
        basis = {"tenantId": str(tenant_id), "moduleKey": module, "moduleGeneration": int(state.generation), "lifecycleVersion": current_version, "preservingSourceIds": []}; scope_hash = _sha(basis)
        job = TenantModuleOffboardingJob(tenant_id=int(tenant_id), module_key=module, module_generation=int(state.generation), state="FROZEN",
            expected_lifecycle_version=current_version, reason=reason_text, requested_by=_actor_id(user), requested_at=now,
            retention_days=int(retention_days), retention_policy_version=policy, scope_hash=scope_hash, last_completed_step="FREEZE",
            result_json={"requestScope": basis, "physicalPurgeAuthorized": False})
        db.add(job); db.flush(); _set_step(db, job, "PRECHECK", "SUCCEEDED", result={"scopeHash": scope_hash})
        state.data_state = "FROZEN"; state.frozen_at = now; state.lifecycle_version = current_version + 1
        _set_step(db, job, "FREEZE", "SUCCEEDED", result={"moduleGeneration": int(state.generation), "lifecycleVersion": int(state.lifecycle_version), "tenantWideFreeze": False})
        audit_log.record_critical_in_session(db, "COMMERCIAL_MODULE_OFFBOARD_FREEZE", f"module-offboard:{job.id}",
            detail={"tenantId": str(tenant_id), "moduleKey": module, "moduleGeneration": int(state.generation), "scopeHash": scope_hash, "reason": reason_text, "physicalPurgeAuthorized": False},
            tenant_id=int(tenant_id), resource_id=str(job.id)); db.commit(); created_job_id = int(job.id)
    except Exception: db.rollback(); raise
    finally: db.close()
    invalidate_tenant_subject_caches(int(tenant_id)); return get_module_offboarding_job(created_job_id)


def get_module_offboarding_job(job_id: int) -> dict:
    from app.models import TenantModuleOffboardingJob, TenantModuleOffboardingStep
    db = get_sessionmaker()()
    try:
        job = db.scalars(select(TenantModuleOffboardingJob).where(TenantModuleOffboardingJob.id == int(job_id), TenantModuleOffboardingJob.is_deleted.is_(False))).first()
        if job is None: raise AppException("DATA_NOT_FOUND", "模块退出任务不存在", http_status=404)
        steps = list(db.scalars(select(TenantModuleOffboardingStep).where(TenantModuleOffboardingStep.job_id == int(job.id), TenantModuleOffboardingStep.is_deleted.is_(False)).order_by(TenantModuleOffboardingStep.id)).all())
        return {"jobId": str(job.id), "tenantId": str(job.tenant_id), "moduleKey": job.module_key, "moduleGeneration": int(job.module_generation),
            "state": job.state, "version": int(job.version or 0), "scopeHash": job.scope_hash, "retentionDays": int(job.retention_days),
            "retentionPolicyVersion": job.retention_policy_version, "retentionUntil": job.retention_until.isoformat(timespec="seconds") if job.retention_until else None,
            "exportJobId": str(job.export_job_id) if job.export_job_id else None, "manifestId": str(job.manifest_id) if job.manifest_id else None,
            "exportFileId": str(job.export_file_id) if job.export_file_id else None, "acceptanceRef": job.acceptance_ref,
            "acceptedAt": job.accepted_at.isoformat(timespec="seconds") if job.accepted_at else None,
            "irreversibleStartedAt": job.irreversible_started_at.isoformat(timespec="seconds") if job.irreversible_started_at else None,
            "physicalPurgeAuthorized": False,
            "steps": [{"stepCode": row.step_code, "status": row.status, "attempts": int(row.attempts or 0), "result": dict(row.result_json or {})} for row in steps]}
    finally: db.close()


def cancel_module_offboarding(user: dict, job_id: int, *, expected_version: int, reason: str) -> dict:
    _require_db(); from app.models import TenantModuleOffboardingJob; from app.services import audit_log; from app.services.auth_service_db import invalidate_tenant_subject_caches
    reason_text = str(reason or "").strip()
    if len(reason_text) < 5: raise AppException("VALIDATION_ERROR", "取消退出原因至少5个字符", http_status=422)
    db = get_sessionmaker()()
    try:
        job = db.scalars(select(TenantModuleOffboardingJob).where(TenantModuleOffboardingJob.id == int(job_id), TenantModuleOffboardingJob.is_deleted.is_(False)).with_for_update()).first()
        if job is None: raise AppException("DATA_NOT_FOUND", "模块退出任务不存在", http_status=404)
        if int(job.version or 0) != int(expected_version): raise AppException("DATA_CONFLICT", "退出任务已变化，请刷新后重试", http_status=409)
        if job.irreversible_started_at is not None or job.state in IRREVERSIBLE_JOB_STATES: raise AppException("DATA_CONFLICT", "不可逆阶段开始后不能取消，只能续跑原任务", http_status=409)
        if job.state == "CANCELLED": return {**get_module_offboarding_job(job.id), "replayed": True}
        state = _module_state(db, int(job.tenant_id), job.module_key, lock=True)
        if state is None or int(state.generation) != int(job.module_generation): raise AppException("DATA_CONFLICT", "模块代次已变化，不能恢复旧实例", http_status=409)
        state.data_state = "AVAILABLE"; state.frozen_at = None; state.lifecycle_version = int(state.lifecycle_version or 0) + 1
        job.state = "CANCELLED"; job.last_completed_step = "CANCELLED"; job.version = int(job.version or 0) + 1
        _set_step(db, job, "CANCEL", "SUCCEEDED", result={"restoredDataState": "AVAILABLE", "entitlementRestored": False})
        audit_log.record_critical_in_session(db, "COMMERCIAL_MODULE_OFFBOARD_CANCEL", f"module-offboard:{job.id}",
            detail={"tenantId": str(job.tenant_id), "moduleKey": job.module_key, "moduleGeneration": int(job.module_generation), "reason": reason_text, "entitlementRestored": False},
            tenant_id=int(job.tenant_id), resource_id=str(job.id)); db.commit(); tenant_id = int(job.tenant_id)
    except Exception: db.rollback(); raise
    finally: db.close()
    invalidate_tenant_subject_caches(tenant_id); return get_module_offboarding_job(int(job_id))


def _validate_export_contract(db, job, *, export_job_id: int, manifest_id: int, scope_hash: str):
    from app.models.data_exchange import ExportJob
    from app.models.file import ArchiveManifest, FileObject
    from app.services.file_content_security import is_downloadable_status
    from app.services.file_scan_constants import READY_SCAN_STATES
    if str(scope_hash or "") != str(job.scope_hash): raise AppException("DATA_CONFLICT", "导出范围指纹与退出计划不一致", http_status=409)
    export = db.scalars(select(ExportJob).where(ExportJob.id == int(export_job_id), ExportJob.tenant_id == int(job.tenant_id), ExportJob.is_deleted.is_(False)).with_for_update()).first()
    if export is None: raise AppException("DATA_NOT_FOUND", "导出任务不存在", http_status=404)
    if export.status != "SUCCEEDED" or export.revoked_at is not None: raise AppException("DATA_CONFLICT", "导出任务尚未成功或已撤销", http_status=409)
    if export.expires_at is not None and export.expires_at <= datetime.utcnow(): raise AppException("DATA_CONFLICT", "导出文件已过期", http_status=409)
    if canonical_module(export.module_code) != job.module_key: raise AppException("DATA_CONFLICT", "导出任务不属于目标模块", http_status=409)
    filters = dict(export.filter_snapshot_json or {}); result = dict(export.result_json or {})
    if int(filters.get("moduleGeneration") or 0) != int(job.module_generation): raise AppException("DATA_CONFLICT", "导出任务模块代次不一致", http_status=409)
    if str(filters.get("scopeHash") or "") != job.scope_hash: raise AppException("DATA_CONFLICT", "导出任务没有绑定当前退出范围", http_status=409)
    if export.file_object_id is None: raise AppException("DATA_CONFLICT", "导出任务没有真实文件对象", http_status=409)
    file_row = db.scalars(select(FileObject).where(FileObject.id == int(export.file_object_id), FileObject.tenant_id == int(job.tenant_id), FileObject.is_deleted.is_(False))).first()
    if file_row is None or not is_downloadable_status(file_row.status): raise AppException("DATA_CONFLICT", "导出文件不存在或不可下载", http_status=409)
    if str(file_row.scan_status or "NOT_REQUIRED").upper() not in READY_SCAN_STATES: raise AppException("DATA_CONFLICT", "导出文件安全扫描尚未完成", http_status=409)
    if not file_row.sha256 or str(result.get("fileSha256") or "") != str(file_row.sha256): raise AppException("DATA_CONFLICT", "导出文件SHA256与任务回执不一致", http_status=409)
    if int(result.get("fileSizeBytes") or -1) != int(file_row.size_bytes or 0): raise AppException("DATA_CONFLICT", "导出文件字节数与任务回执不一致", http_status=409)
    manifest = db.scalars(select(ArchiveManifest).where(ArchiveManifest.id == int(manifest_id), ArchiveManifest.tenant_id == int(job.tenant_id), ArchiveManifest.is_deleted.is_(False)).with_for_update()).first()
    if manifest is None: raise AppException("DATA_NOT_FOUND", "归档Manifest不存在", http_status=404)
    if canonical_module(manifest.module_code) != job.module_key: raise AppException("DATA_CONFLICT", "Manifest不属于目标模块", http_status=409)
    if manifest.status not in {"FROZEN", "PACKAGED"}: raise AppException("DATA_CONFLICT", "Manifest尚未冻结或打包", http_status=409)
    if int(manifest.package_file_id or 0) != int(file_row.id): raise AppException("DATA_CONFLICT", "Manifest与导出文件不是同一交付包", http_status=409)
    if not manifest.manifest_sha256 or str(result.get("manifestSha256") or "") != str(manifest.manifest_sha256): raise AppException("DATA_CONFLICT", "Manifest摘要与导出回执不一致", http_status=409)
    if str(result.get("scopeHash") or "") != job.scope_hash: raise AppException("DATA_CONFLICT", "导出结果范围指纹不一致", http_status=409)
    if int(result.get("moduleGeneration") or 0) != int(job.module_generation): raise AppException("DATA_CONFLICT", "导出结果模块代次不一致", http_status=409)
    object_count = result.get("objectCount"); attachment_count = result.get("attachmentCount")
    if type(object_count) is not int or object_count < 0 or int(export.row_count or 0) != object_count: raise AppException("DATA_CONFLICT", "导出对象数与任务行数不一致", http_status=409)
    if type(attachment_count) is not int or attachment_count < 0: raise AppException("DATA_CONFLICT", "导出附件数量缺失或无效", http_status=409)
    return export, manifest, file_row, result


def bind_module_export(user: dict, job_id: int, *, export_job_id: int, manifest_id: int, scope_hash: str, expected_version: int) -> dict:
    _require_db(); from app.models import TenantModuleOffboardingJob; from app.services import audit_log; db = get_sessionmaker()()
    try:
        job = db.scalars(select(TenantModuleOffboardingJob).where(TenantModuleOffboardingJob.id == int(job_id), TenantModuleOffboardingJob.is_deleted.is_(False)).with_for_update()).first()
        if job is None: raise AppException("DATA_NOT_FOUND", "模块退出任务不存在", http_status=404)
        if int(job.version or 0) != int(expected_version): raise AppException("DATA_CONFLICT", "退出任务已变化，请刷新后重试", http_status=409)
        if job.state not in {"FROZEN", "EXPORTING", "WAIT_EXPORT_ACCEPT"}: raise AppException("DATA_CONFLICT", f"当前状态 {job.state} 不能绑定最终导出", http_status=409)
        export, manifest, file_row, result = _validate_export_contract(db, job, export_job_id=export_job_id, manifest_id=manifest_id, scope_hash=scope_hash)
        job.export_job_id = int(export.id); job.manifest_id = int(manifest.id); job.export_file_id = int(file_row.id); job.state = "WAIT_EXPORT_ACCEPT"; job.last_completed_step = "EXPORT"; job.version = int(job.version or 0) + 1
        job.result_json = {**dict(job.result_json or {}), "exportEvidence": {"exportJobId": str(export.id), "manifestId": str(manifest.id), "fileId": str(file_row.id), "fileSha256": file_row.sha256, "fileSizeBytes": int(file_row.size_bytes or 0), "objectCount": int(result["objectCount"]), "attachmentCount": int(result["attachmentCount"])}}
        _set_step(db, job, "EXPORT", "SUCCEEDED", result=dict(job.result_json["exportEvidence"])); audit_log.record_critical_in_session(db, "COMMERCIAL_MODULE_EXPORT_BIND", f"module-offboard:{job.id}",
            detail={"tenantId": str(job.tenant_id), "moduleKey": job.module_key, "moduleGeneration": int(job.module_generation), "scopeHash": job.scope_hash, "exportJobId": str(export.id), "manifestId": str(manifest.id)}, tenant_id=int(job.tenant_id), resource_id=str(job.id)); db.commit(); return get_module_offboarding_job(int(job.id))
    except Exception: db.rollback(); raise
    finally: db.close()


def accept_module_export(user: dict, job_id: int, *, acceptance_ref: str, expected_version: int) -> dict:
    _require_db(); from app.models import TenantModuleOffboardingJob; from app.services import audit_log; from app.services.auth_service_db import invalidate_tenant_subject_caches
    ref = str(acceptance_ref or "").strip()
    if len(ref) < 6: raise AppException("VALIDATION_ERROR", "校方接收凭据至少6个字符", http_status=422)
    db = get_sessionmaker()()
    try:
        job = db.scalars(select(TenantModuleOffboardingJob).where(TenantModuleOffboardingJob.id == int(job_id), TenantModuleOffboardingJob.is_deleted.is_(False)).with_for_update()).first()
        if job is None: raise AppException("DATA_NOT_FOUND", "模块退出任务不存在", http_status=404)
        if int(job.version or 0) != int(expected_version): raise AppException("DATA_CONFLICT", "退出任务已变化，请刷新后重试", http_status=409)
        if job.state != "WAIT_EXPORT_ACCEPT" or not job.export_job_id or not job.manifest_id: raise AppException("DATA_CONFLICT", "最终导出尚未完成服务端核验", http_status=409)
        _validate_export_contract(db, job, export_job_id=int(job.export_job_id), manifest_id=int(job.manifest_id), scope_hash=job.scope_hash)
        state = _module_state(db, int(job.tenant_id), job.module_key, lock=True)
        if state is None or int(state.generation) != int(job.module_generation): raise AppException("DATA_CONFLICT", "模块代次已变化，禁止接收旧交付包", http_status=409)
        now = datetime.utcnow(); job.acceptance_ref = ref; job.accepted_by = _actor_id(user); job.accepted_at = now; job.retention_until = now + timedelta(days=int(job.retention_days)); job.state = "RETENTION"; job.last_completed_step = "RETENTION"; job.version = int(job.version or 0) + 1
        state.data_state = "RETAINED"; state.lifecycle_version = int(state.lifecycle_version or 0) + 1
        _set_step(db, job, "EXPORT_ACCEPT", "SUCCEEDED", result={"acceptanceRef": ref, "acceptedAt": now.isoformat(timespec="seconds")})
        _set_step(db, job, "RETENTION", "SUCCEEDED", result={"retentionPolicyVersion": job.retention_policy_version, "retentionUntil": job.retention_until.isoformat(timespec="seconds"), "startsFrom": "EXPORT_ACCEPTANCE", "physicalPurgeAuthorized": False})
        audit_log.record_critical_in_session(db, "COMMERCIAL_MODULE_EXPORT_ACCEPT", f"module-offboard:{job.id}",
            detail={"tenantId": str(job.tenant_id), "moduleKey": job.module_key, "moduleGeneration": int(job.module_generation), "scopeHash": job.scope_hash, "acceptanceRef": ref, "retentionUntil": job.retention_until.isoformat(timespec="seconds"), "physicalPurgeAuthorized": False}, tenant_id=int(job.tenant_id), resource_id=str(job.id)); db.commit(); tenant_id = int(job.tenant_id)
    except Exception: db.rollback(); raise
    finally: db.close()
    invalidate_tenant_subject_caches(tenant_id); return get_module_offboarding_job(int(job_id))
