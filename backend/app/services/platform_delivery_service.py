"""Read-only school-delivery aggregation and frozen platform handoff evidence.

This module deliberately does not create a second business authority.  It reads
commercial, provisioning, first-login and system-implementation truth from
their canonical tables.  Consumer-smoke evidence and the platform handoff are
stored as immutable ``PlatformConfig`` records so the control plane can seal a
delivery without adding a competing READY flag or a new migration.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.core.exceptions import AppException
from app.db.session import get_sessionmaker


CONSUMER_SMOKE_CONFIG = "DELIVERY_CONSUMER_SMOKE"
PLATFORM_ACCEPTANCE_CONFIG = "PLATFORM_DELIVERY_ACCEPTANCE"

REQUIRED_CONSUMER_SURFACES = frozenset({
    "ACADEMIC",
    "STUDENT_AFFAIRS",
    "INTERNSHIP",
    "GRADUATION",
    "TEACHER_MINI",
    "STUDENT_PC",
    "STUDENT_MINI",
    "CROSS_TENANT_DENY",
    "UNENTITLED_DENY",
})
_PASS = "PASS"
_SHA40 = re.compile(r"^[0-9a-f]{40}$", re.IGNORECASE)


def _digest(value: object) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _actor_id(user: dict | None) -> str:
    return str((user or {}).get("userId") or "")


def _latest_by_tenant(rows) -> dict[int, object]:
    result: dict[int, object] = {}
    for row in rows:
        tid = int(row.tenant_id)
        current = result.get(tid)
        if current is None or int(row.id) > int(current.id):
            result[tid] = row
    return result


def _config_maps(rows) -> tuple[dict[int, dict], dict[int, object], dict[int, object]]:
    metas: dict[int, dict] = {}
    consumer: dict[int, object] = {}
    acceptance: dict[int, object] = {}
    for row in rows:
        tid = int(row.tenant_id)
        if row.config_type == "TENANT_META":
            metas[tid] = dict(row.config_json or {})
        elif row.config_type == CONSUMER_SMOKE_CONFIG:
            current = consumer.get(tid)
            if current is None or int(row.id) > int(current.id):
                consumer[tid] = row
        elif row.config_type == PLATFORM_ACCEPTANCE_CONFIG:
            current = acceptance.get(tid)
            if current is None or int(row.id) > int(current.id):
                acceptance[tid] = row
    return metas, consumer, acceptance


def _read_models(tenant_id: int | None = None) -> list[dict]:
    """Build all requested delivery rows with a bounded set of aggregate queries."""
    from app.models import (
        PlatformConfig,
        PlatformOrder,
        StudentProfile,
        SystemImplementationProject,
        Tenant,
        User,
    )
    from app.models.tenant_provisioning import ProvisioningJob, ProvisioningStepRun
    from app.services import platform_defaults as defaults
    from app.services.tenant_effective_state_service import effective_state_from_records

    db = get_sessionmaker()()
    try:
        tenant_query = select(Tenant).where(Tenant.is_deleted.is_(False))
        if tenant_id is not None:
            tenant_query = tenant_query.where(Tenant.id == int(tenant_id))
        tenants = list(db.scalars(tenant_query.order_by(Tenant.id)).all())
        if tenant_id is not None and not tenants:
            raise AppException("DATA_NOT_FOUND", "租户不存在", http_status=404)
        ids = [int(row.id) for row in tenants]
        if not ids:
            return []

        config_rows = list(db.scalars(select(PlatformConfig).where(
            PlatformConfig.tenant_id.in_(ids),
            PlatformConfig.config_type.in_((
                "TENANT_META", CONSUMER_SMOKE_CONFIG, PLATFORM_ACCEPTANCE_CONFIG,
            )),
            PlatformConfig.is_deleted.is_(False),
        )).all())
        metas, smoke_by_tenant, acceptance_by_tenant = _config_maps(config_rows)

        paid_orders = _latest_by_tenant(db.scalars(select(PlatformOrder).where(
            PlatformOrder.tenant_id.in_(ids),
            PlatformOrder.status == "paid",
            PlatformOrder.is_deleted.is_(False),
        )).all())
        jobs = _latest_by_tenant(db.scalars(select(ProvisioningJob).where(
            ProvisioningJob.tenant_id.in_(ids),
            ProvisioningJob.is_deleted.is_(False),
        )).all())
        projects = _latest_by_tenant(db.scalars(select(SystemImplementationProject).where(
            SystemImplementationProject.tenant_id.in_(ids),
            SystemImplementationProject.is_deleted.is_(False),
        )).all())

        admin_rows = list(db.scalars(select(User).where(
            User.tenant_id.in_(ids),
            User.user_type == "SCHOOL_ADMIN",
            User.status == "ACTIVE",
            User.is_deleted.is_(False),
        ).order_by(User.tenant_id, User.id)).all())
        admins_by_tenant: dict[int, list] = {}
        users_by_id = {}
        for row in admin_rows:
            admins_by_tenant.setdefault(int(row.tenant_id), []).append(row)
            users_by_id[int(row.id)] = row

        first_admin_steps = list(db.scalars(select(ProvisioningStepRun).where(
            ProvisioningStepRun.job_id.in_([int(job.id) for job in jobs.values()] or [-1]),
            ProvisioningStepRun.step_code == "FIRST_ADMIN",
            ProvisioningStepRun.is_deleted.is_(False),
        )).all())
        step_by_job = {int(row.job_id): row for row in first_admin_steps}

        user_counts = {int(tid): int(count or 0) for tid, count in db.execute(select(
            User.tenant_id, func.count(User.id),
        ).where(
            User.tenant_id.in_(ids), User.is_deleted.is_(False),
        ).group_by(User.tenant_id)).all()}
        student_counts = {int(tid): int(count or 0) for tid, count in db.execute(select(
            StudentProfile.tenant_id, func.count(StudentProfile.id),
        ).where(
            StudentProfile.tenant_id.in_(ids), StudentProfile.is_deleted.is_(False),
        ).group_by(StudentProfile.tenant_id)).all()}

        known_packages = set(defaults.DEFAULT_PACKAGES)
        known_packages.update(str(row.config_key) for row in db.scalars(select(PlatformConfig).where(
            PlatformConfig.tenant_id == 0,
            PlatformConfig.config_type == "PACKAGE",
            PlatformConfig.is_deleted.is_(False),
        )).all())

        output: list[dict] = []
        for tenant in tenants:
            tid = int(tenant.id)
            meta = metas.get(tid, {})
            effective = effective_state_from_records(
                row_status=tenant.status, meta=meta, strict=False,
            )
            tenant_state = str(effective["effectiveStatus"] or "unresolved").upper()

            job = jobs.get(tid)
            provisioning_state = "NOT_STARTED"
            provisioning_job_id = None
            if job is not None:
                provisioning_job_id = str(job.id)
                provisioning_state = "BOOTSTRAP_READY" if job.status == "SUCCEEDED" else str(job.status)

            first_admin = None
            if job is not None:
                step = step_by_job.get(int(job.id))
                raw_user_id = str(((step.output_summary_json or {}) if step else {}).get("userId") or "")
                if raw_user_id.isdigit():
                    first_admin = users_by_id.get(int(raw_user_id))
            if first_admin is None:
                candidates = admins_by_tenant.get(tid, [])
                first_admin = candidates[0] if candidates else None
            if first_admin is None:
                first_admin_state = "NOT_CREATED"
            elif bool(first_admin.must_change_password):
                first_admin_state = "TEMP_PASSWORD_PENDING"
            else:
                first_admin_state = "PASSWORD_CHANGED"

            paid_order = paid_orders.get(tid)
            paid_package = str(paid_order.package_code or "") if paid_order else ""
            effective_package = str(meta.get("packageCode") or "")
            if paid_order is None:
                commercial_state = "TRIAL_ONLY"
            elif tenant_state == "ACTIVE" and paid_package and paid_package == effective_package:
                commercial_state = "PAID_ACTIVE"
            else:
                commercial_state = "PAID_REPAIR_REQUIRED"
            entitlement_state = (
                "PASS" if commercial_state == "PAID_ACTIVE" and effective_package in known_packages
                else "BLOCKED"
            )

            project = projects.get(tid)
            implementation_state = str(project.status) if project else "NOT_STARTED"
            acceptance_digest = str(project.acceptance_digest or "") if project else ""

            smoke_row = smoke_by_tenant.get(tid)
            smoke = dict(smoke_row.config_json or {}) if smoke_row else {}
            smoke_matches_acceptance = bool(
                smoke.get("status") == _PASS
                and acceptance_digest
                and smoke.get("acceptanceDigest") == acceptance_digest
            )
            consumer_smoke_state = "PASS" if smoke_matches_acceptance else (
                str(smoke.get("status") or "NOT_RUN") if smoke else "NOT_RUN"
            )

            acceptance_row = acceptance_by_tenant.get(tid)
            platform_acceptance = dict(acceptance_row.config_json or {}) if acceptance_row else {}
            acceptance_current = bool(
                platform_acceptance
                and acceptance_digest
                and platform_acceptance.get("acceptanceDigest") == acceptance_digest
                and platform_acceptance.get("consumerEvidenceDigest") == smoke.get("evidenceDigest")
            )
            platform_acceptance_state = "ACCEPTED" if acceptance_current else (
                "STALE" if platform_acceptance else "NOT_ACCEPTED"
            )

            blockers: list[dict] = []
            checks = (
                (tenant_state == "ACTIVE", "TENANT_NOT_ACTIVE", "租户必须处于正式可写状态"),
                (commercial_state == "PAID_ACTIVE", "COMMERCIAL_NOT_ACTIVE", "必须存在已支付且已生效的订单授权"),
                (provisioning_state == "BOOTSTRAP_READY", "PROVISIONING_NOT_READY", "Provisioning SAGA 尚未达到基础开户完成"),
                (first_admin_state == "PASSWORD_CHANGED", "FIRST_ADMIN_NOT_CHANGED", "首位管理员尚未完成真实首登强制改密"),
                (implementation_state == "ACCEPTED" and bool(acceptance_digest), "IMPLEMENTATION_NOT_ACCEPTED", "学校实施尚未 ACCEPTED 并冻结摘要"),
                (entitlement_state == "PASS", "ENTITLEMENT_NOT_READY", "订单与有效套餐授权不一致"),
                (consumer_smoke_state == "PASS", "CONSUMER_SMOKE_NOT_PASS", "控制面 Consumer Smoke 尚未在当前学校验收摘要上通过"),
            )
            for passed, code, message in checks:
                if not passed:
                    blockers.append({"code": code, "message": message})

            base_delivery_state = "READY_FOR_PLATFORM_ACCEPTANCE" if not blockers else "BLOCKED"
            delivery_state = "SCHOOL_DELIVERY_PRODUCTION_READY" if (
                base_delivery_state == "READY_FOR_PLATFORM_ACCEPTANCE" and acceptance_current
            ) else base_delivery_state
            read_model_basis = {
                "tenantId": str(tid),
                "tenantState": tenant_state,
                "commercialState": commercial_state,
                "provisioningState": provisioning_state,
                "firstAdminState": first_admin_state,
                "implementationState": implementation_state,
                "acceptanceDigest": acceptance_digest,
                "entitlementState": entitlement_state,
                "consumerSmokeState": consumer_smoke_state,
                "consumerEvidenceDigest": smoke.get("evidenceDigest") or "",
                "blockerCodes": [item["code"] for item in blockers],
                "platformAcceptanceState": platform_acceptance_state,
            }
            output.append({
                "tenantId": str(tid),
                "tenantCode": tenant.tenant_code,
                "tenantName": tenant.school_name,
                "packageCode": effective_package,
                "tenantState": tenant_state,
                "commercialState": commercial_state,
                "paidOrderNo": str(paid_order.order_no) if paid_order else "",
                "paidPackageCode": paid_package,
                "commercialRepairRequired": commercial_state == "PAID_REPAIR_REQUIRED",
                "provisioningState": provisioning_state,
                "provisioningJobId": provisioning_job_id,
                "firstAdminState": first_admin_state,
                "implementationState": implementation_state,
                "implementationProjectId": str(project.id) if project else "",
                "acceptanceDigest": acceptance_digest,
                "entitlementState": entitlement_state,
                "consumerSmokeState": consumer_smoke_state,
                "consumerSmoke": smoke,
                "platformAcceptanceState": platform_acceptance_state,
                "platformAcceptance": platform_acceptance,
                "accountCounts": {
                    "schoolAdmin": len(admins_by_tenant.get(tid, [])),
                    "users": user_counts.get(tid, 0),
                    "students": student_counts.get(tid, 0),
                },
                "blockers": blockers,
                "deliveryState": delivery_state,
                "readModelDigest": _digest(read_model_basis),
            })
        return output
    finally:
        db.close()


def list_delivery_read_models() -> list[dict]:
    return _read_models()


def get_delivery_read_model(tenant_id: int) -> dict:
    return _read_models(int(tenant_id))[0]


def record_consumer_smoke(user: dict, tenant_id: int, body: dict) -> dict:
    """Freeze exact-head Consumer Smoke evidence; never write business truth."""
    from app.models import PlatformConfig
    from app.services import audit_log

    exact_head = str(body.get("exactHead") or "").strip().lower()
    if not _SHA40.fullmatch(exact_head):
        raise AppException("VALIDATION_ERROR", "exactHead 必须是 40 位 Git SHA", http_status=422)
    from app.modules.platform.services.platform_product_iam_hardening import deployed_commit_sha

    deployed_head = deployed_commit_sha()
    if exact_head != deployed_head:
        raise AppException(
            "DATA_CONFLICT",
            "Consumer Smoke exactHead 与当前服务部署提交不一致",
            http_status=409,
            details={"expectedExactHead": deployed_head, "submittedExactHead": exact_head},
        )
    status = str(body.get("status") or "").strip().upper()
    if status not in {"PASS", "FAILED"}:
        raise AppException("VALIDATION_ERROR", "Consumer Smoke 状态只能是 PASS/FAILED", http_status=422)
    current = get_delivery_read_model(int(tenant_id))
    acceptance_digest = str(body.get("acceptanceDigest") or "").strip()
    if not current["acceptanceDigest"] or acceptance_digest != current["acceptanceDigest"]:
        raise AppException("DATA_CONFLICT", "Consumer Smoke 必须绑定当前学校冻结的 acceptanceDigest", http_status=409)

    normalized_checks = []
    seen: set[str] = set()
    for raw in body.get("checks") or []:
        surface = str(raw.get("surface") or "").strip().upper()
        if not surface or surface in seen:
            raise AppException("VALIDATION_ERROR", "Consumer Smoke surface 缺失或重复", http_status=422)
        seen.add(surface)
        check = {
            "surface": surface,
            "readStatus": str(raw.get("readStatus") or "").strip().upper(),
            "actionStatus": str(raw.get("actionStatus") or "").strip().upper(),
            "scopeStatus": str(raw.get("scopeStatus") or "").strip().upper(),
            "evidenceRef": str(raw.get("evidenceRef") or "").strip()[:500],
        }
        normalized_checks.append(check)
    if status == "PASS":
        missing = sorted(REQUIRED_CONSUMER_SURFACES - seen)
        invalid = [item["surface"] for item in normalized_checks if (
            item["readStatus"] != _PASS or item["actionStatus"] != _PASS
            or item["scopeStatus"] != _PASS or not item["evidenceRef"]
        )]
        if missing or invalid:
            raise AppException(
                "DATA_CONFLICT", "Consumer Smoke 证据不完整，不能记录 PASS", http_status=409,
                details={"missingSurfaces": missing, "invalidSurfaces": invalid},
            )

    evidence_basis = {
        "tenantId": str(tenant_id),
        "status": status,
        "exactHead": exact_head,
        "acceptanceDigest": acceptance_digest,
        "checks": sorted(normalized_checks, key=lambda item: item["surface"]),
        "recordedBy": _actor_id(user),
    }
    evidence_digest = _digest(evidence_basis)
    evidence = {
        **evidence_basis,
        "recordedAt": datetime.utcnow().isoformat(timespec="seconds"),
        "evidenceDigest": evidence_digest,
    }

    db = get_sessionmaker()()
    try:
        existing = db.scalars(select(PlatformConfig).where(
            PlatformConfig.tenant_id == int(tenant_id),
            PlatformConfig.config_type == CONSUMER_SMOKE_CONFIG,
            PlatformConfig.config_key == evidence_digest,
            PlatformConfig.is_deleted.is_(False),
        )).first()
        if existing is None:
            db.add(PlatformConfig(
                tenant_id=int(tenant_id), config_type=CONSUMER_SMOKE_CONFIG,
                config_key=evidence_digest, config_json=evidence, enabled=True,
                status="ACTIVE", remark="exact-head control-plane consumer smoke",
            ))
            audit_log.record_critical_in_session(
                db,
                "PLATFORM_DELIVERY_CONSUMER_SMOKE_RECORDED",
                f"tenant:{tenant_id}",
                detail={"status": status, "exactHead": exact_head, "evidenceDigest": evidence_digest},
                tenant_id=int(tenant_id),
            )
            try:
                db.commit()
            except IntegrityError:
                db.rollback()
                duplicate = db.scalars(select(PlatformConfig).where(
                    PlatformConfig.tenant_id == int(tenant_id),
                    PlatformConfig.config_type == CONSUMER_SMOKE_CONFIG,
                    PlatformConfig.config_key == evidence_digest,
                    PlatformConfig.is_deleted.is_(False),
                )).first()
                if duplicate is None:
                    raise
    finally:
        db.close()
    return get_delivery_read_model(int(tenant_id))


def accept_delivery(user: dict, tenant_id: int, body: dict) -> dict:
    """Freeze platform handoff by reference; never rewrite the school digest."""
    from app.models import PlatformConfig
    from app.services import audit_log

    if str(body.get("confirmText") or "").strip() != "确认交付":
        raise AppException("VALIDATION_ERROR", "请输入“确认交付”", http_status=422)
    comment = str(body.get("comment") or "").strip()
    if len(comment) < 2:
        raise AppException("VALIDATION_ERROR", "请填写平台交付意见", http_status=422)

    current = get_delivery_read_model(int(tenant_id))
    if current["platformAcceptanceState"] == "ACCEPTED":
        return current
    expected = str(body.get("expectedReadModelDigest") or "").strip()
    if expected != current["readModelDigest"]:
        raise AppException(
            "DATA_CONFLICT", "交付状态已变化，请刷新后重试", http_status=409,
            details={"currentReadModelDigest": current["readModelDigest"]},
        )
    if current["deliveryState"] != "READY_FOR_PLATFORM_ACCEPTANCE":
        raise AppException(
            "DATA_CONFLICT", "仍有控制面交付阻断项，不能确认平台交付", http_status=409,
            details={"blockers": current["blockers"]},
        )

    record = {
        "tenantId": str(tenant_id),
        "acceptanceDigest": current["acceptanceDigest"],
        "consumerEvidenceDigest": current["consumerSmoke"].get("evidenceDigest"),
        "commercialState": current["commercialState"],
        "provisioningState": current["provisioningState"],
        "firstAdminState": current["firstAdminState"],
        "implementationState": current["implementationState"],
        "entitlementState": current["entitlementState"],
        "consumerSmokeState": current["consumerSmokeState"],
        "acceptedAt": datetime.utcnow().isoformat(timespec="seconds"),
        "acceptedBy": _actor_id(user),
        "comment": comment,
        "sourceReadModelDigest": current["readModelDigest"],
    }
    record["deliveryAcceptanceDigest"] = _digest(record)
    acceptance_key = _digest({
        "acceptanceDigest": current["acceptanceDigest"],
        "consumerEvidenceDigest": current["consumerSmoke"].get("evidenceDigest"),
    })

    db = get_sessionmaker()()
    try:
        existing = db.scalars(select(PlatformConfig).where(
            PlatformConfig.tenant_id == int(tenant_id),
            PlatformConfig.config_type == PLATFORM_ACCEPTANCE_CONFIG,
            PlatformConfig.config_key == acceptance_key,
            PlatformConfig.is_deleted.is_(False),
        )).first()
        if existing is None:
            db.add(PlatformConfig(
                tenant_id=int(tenant_id), config_type=PLATFORM_ACCEPTANCE_CONFIG,
                config_key=acceptance_key, config_json=record,
                enabled=True, status="ACTIVE", remark="frozen platform delivery acceptance",
            ))
            audit_log.record_critical_in_session(
                db,
                "PLATFORM_DELIVERY_ACCEPTED",
                f"tenant:{tenant_id}",
                detail={
                    "acceptanceDigest": record["acceptanceDigest"],
                    "consumerEvidenceDigest": record["consumerEvidenceDigest"],
                    "deliveryAcceptanceDigest": record["deliveryAcceptanceDigest"],
                },
                tenant_id=int(tenant_id),
            )
            try:
                db.commit()
            except IntegrityError:
                db.rollback()
                duplicate = db.scalars(select(PlatformConfig).where(
                    PlatformConfig.tenant_id == int(tenant_id),
                    PlatformConfig.config_type == PLATFORM_ACCEPTANCE_CONFIG,
                    PlatformConfig.config_key == acceptance_key,
                    PlatformConfig.is_deleted.is_(False),
                )).first()
                if duplicate is None:
                    raise
    finally:
        db.close()
    return get_delivery_read_model(int(tenant_id))
