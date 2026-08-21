"""Production contracts for the seven P1 closures on existing System Management pages.

This module is mounted as a deterministic route replacement by api.v1.router. It keeps
security-sensitive gates on the server: permission/domain checks, atomic config restore,
formal-role compatibility, and signed organization-impact receipts.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from datetime import datetime

from fastapi import APIRouter, Body, Depends, Query
from sqlalchemy import func, or_, select

from app.core.config import settings
from app.core.context import current_tenant_id
from app.core.exceptions import AppException
from app.core.permissions import has_permission, require_any_permission
from app.core.response import success
from app.db.session import get_sessionmaker
from app.models import College, Major, SchoolClass, StudentProfile
from app.models.config_governance import (
    OVERRIDE_STATUS_ACTIVE,
    OVERRIDE_STATUS_REVOKED,
    SCOPE_TENANT,
    ConfigDefinition,
    ConfigOverride,
)
from app.models.organization_version import StaffAssignment

router = APIRouter(prefix="/system", tags=["系统管理·P1生产闭环"])

_ORG_PREVIEW_TTL_SECONDS = 300


def _actor_id(user: dict | None) -> int | None:
    raw = str((user or {}).get("userId") or (user or {}).get("id") or "").replace("db-", "")
    return int(raw) if raw.isdigit() else None


def _tenant_id() -> int:
    tid = int(current_tenant_id() or 0)
    if not tid:
        raise AppException("TENANT_CONTEXT_REQUIRED", "缺少租户上下文")
    return tid


def _deny(message: str = "当前角色无此操作权限") -> None:
    raise AppException("NO_PERMISSION", message, http_status=403)


def _definition(db, config_key: str) -> ConfigDefinition:
    row = db.scalars(select(ConfigDefinition).where(
        ConfigDefinition.config_key == config_key,
        ConfigDefinition.is_deleted.is_(False),
    )).first()
    if row is None:
        raise AppException("DATA_NOT_FOUND", f"未登记的配置项：{config_key}", http_status=404)
    return row


def _can_config_read(user: dict | None, domain: str) -> bool:
    return (
        has_permission(user, "systemAdmin.config.view")
        or has_permission(user, "systemAdmin.config.manage")
        or (str(domain or "").upper() == "SECURITY" and has_permission(user, "systemAdmin.security.policy.manage"))
    )


def _can_config_write(user: dict | None, domain: str) -> bool:
    return (
        has_permission(user, "systemAdmin.config.manage")
        or (str(domain or "").upper() == "SECURITY" and has_permission(user, "systemAdmin.security.policy.manage"))
    )


def _assert_config_read(user: dict | None, domain: str) -> None:
    if not _can_config_read(user, domain):
        _deny("当前角色无权读取该配置域")


def _assert_config_write(user: dict | None, domain: str) -> None:
    if not _can_config_write(user, domain):
        _deny("当前角色无权修改该配置域")


# ── Parent context: route-specific roles must be able to enter their existing page. ──
@router.get("/context", summary="系统管理上下文（补齐专项治理权限入口）")
def system_context(
    user=Depends(require_any_permission(
        "systemAdmin.dashboard.view", "systemAdmin.user.view", "systemAdmin.role.view",
        "systemAdmin.org.view", "systemAdmin.audit.view", "systemAdmin.config.view",
        "systemAdmin.implementation.view", "systemAdmin.scope.view",
        "systemAdmin.security.policy.manage", "systemAdmin.user.exception.view",
        "systemAdmin.user.bind", "systemAdmin.user.manage", "systemAdmin.role.config",
        "systemAdmin.user.assign", "systemAdmin.org.manage",
    )),
):
    from app.modules.system_admin.routers.system_bundle import get_system_context
    return get_system_context(user=user)


# ── Security configuration: same authority for page read/write/restore. ──
@router.get("/effective-config", summary="配置最终值与完整来源链（专项权限域隔离）")
def effective_config(
    configKey: str | None = None,
    domain: str | None = None,
    orgUnitId: str | None = None,
    termId: str | None = None,
    user=Depends(require_any_permission(
        "systemAdmin.config.view", "systemAdmin.config.manage", "systemAdmin.security.policy.manage"
    )),
):
    from app.services import effective_config_service as svc
    svc.ensure_definitions()
    if configKey:
        db = get_sessionmaker()()
        try:
            definition = _definition(db, str(configKey))
            _assert_config_read(user, definition.domain_code)
        finally:
            db.close()
        return success(svc.resolve(str(configKey), org_unit_id=orgUnitId, term_id=termId))
    requested_domain = str(domain or "").upper()
    if not requested_domain:
        if not (has_permission(user, "systemAdmin.config.view") or has_permission(user, "systemAdmin.config.manage")):
            _deny("专项安全策略权限只能读取 SECURITY 配置域")
    else:
        _assert_config_read(user, requested_domain)
    return success(svc.resolve_all(domain=requested_domain or None))


@router.put("/config-overrides", summary="设置配置覆盖（专项权限不得越域）")
def set_config_override(
    body: dict = Body(...),
    user=Depends(require_any_permission("systemAdmin.config.manage", "systemAdmin.security.policy.manage")),
):
    from app.modules.system_admin.routers.system_bundle import _calendar_dt
    from app.services import effective_config_service as svc
    config_key = str((body or {}).get("configKey") or "").strip()
    if not config_key:
        raise AppException("VALIDATION_ERROR", "缺少 configKey")
    svc.ensure_definitions()
    db = get_sessionmaker()()
    try:
        definition = _definition(db, config_key)
        _assert_config_write(user, definition.domain_code)
    finally:
        db.close()
    return success(
        svc.set_override(
            config_key,
            value=(body or {}).get("value"),
            scope_type=str((body or {}).get("scopeType") or "TENANT"),
            scope_id=str((body or {}).get("scopeId") or ""),
            effective_at=_calendar_dt((body or {}).get("effectiveAt"), "effectiveAt", required=False),
            expires_at=_calendar_dt((body or {}).get("expiresAt"), "expiresAt", required=False),
            reason=str((body or {}).get("reason") or ""),
            expected_version=(body or {}).get("expectedVersion"),
        ),
        message="配置已保存",
    )


@router.get("/config-history/{config_key}", summary="配置变更历史（专项权限不得越域）")
def config_history(
    config_key: str,
    user=Depends(require_any_permission(
        "systemAdmin.config.view", "systemAdmin.config.manage", "systemAdmin.security.policy.manage"
    )),
):
    from app.services import effective_config_service as svc
    svc.ensure_definitions()
    db = get_sessionmaker()()
    try:
        definition = _definition(db, str(config_key))
        _assert_config_read(user, definition.domain_code)
    finally:
        db.close()
    return success(svc.history(str(config_key)))


@router.get("/effective-config-overrides", summary="当前学校层配置覆盖元数据")
def list_effective_config_overrides(
    domain: str = Query(default="SECURITY"),
    user=Depends(require_any_permission(
        "systemAdmin.config.view", "systemAdmin.config.manage", "systemAdmin.security.policy.manage"
    )),
):
    tenant_id = _tenant_id()
    requested_domain = str(domain or "").upper()
    if not requested_domain:
        if not (has_permission(user, "systemAdmin.config.view") or has_permission(user, "systemAdmin.config.manage")):
            _deny("专项安全策略权限只能读取 SECURITY 配置域")
    else:
        _assert_config_read(user, requested_domain)
    now = datetime.utcnow().replace(microsecond=0)
    db = get_sessionmaker()()
    try:
        stmt = (
            select(ConfigOverride, ConfigDefinition)
            .join(ConfigDefinition, ConfigDefinition.config_key == ConfigOverride.config_key)
            .where(
                ConfigOverride.tenant_id == tenant_id,
                ConfigOverride.scope_type == SCOPE_TENANT,
                ConfigOverride.status == OVERRIDE_STATUS_ACTIVE,
                ConfigOverride.is_deleted.is_(False),
                ConfigDefinition.is_deleted.is_(False),
            )
            .order_by(ConfigOverride.config_key, ConfigOverride.effective_at.desc(), ConfigOverride.id.desc())
        )
        if requested_domain:
            stmt = stmt.where(ConfigDefinition.domain_code == requested_domain)
        grouped: dict[str, dict] = {}
        for override, definition in db.execute(stmt).all():
            if override.expires_at is not None and override.expires_at <= now:
                continue
            group = grouped.setdefault(override.config_key, {"definition": definition, "rows": []})
            group["rows"].append(override)
        items = []
        for config_key, group in grouped.items():
            rows = group["rows"]
            definition = group["definition"]
            current = next((row for row in rows if row.effective_at <= now), None)
            display = current or rows[-1]
            chain = [{
                "overrideId": str(row.id),
                "version": int(row.version or 0),
                "effectiveAt": row.effective_at.isoformat() if row.effective_at else None,
                "expiresAt": row.expires_at.isoformat() if row.expires_at else None,
                "value": (row.value_json or {}).get("value"),
                "reason": row.reason or "",
                "scheduled": bool(row.effective_at and row.effective_at > now),
            } for row in rows]
            items.append({
                "overrideId": str(display.id), "version": int(display.version or 0),
                "configKey": config_key, "configName": definition.config_name,
                "domain": definition.domain_code, "scopeType": SCOPE_TENANT, "scopeId": None,
                "value": (display.value_json or {}).get("value"),
                "effectiveAt": display.effective_at.isoformat() if display.effective_at else None,
                "expiresAt": display.expires_at.isoformat() if display.expires_at else None,
                "reason": display.reason or "", "isScheduledOnly": current is None,
                "overrideChain": chain, "overrideCount": len(chain),
                "scheduledCount": sum(1 for row in chain if row["scheduled"]),
            })
        items.sort(key=lambda item: item["configKey"])
        return success({"items": items, "total": len(items)})
    finally:
        db.close()


@router.post("/effective-config-overrides/restore-inheritance", summary="原子恢复学校层配置继承")
def restore_effective_config_inheritance(
    body: dict = Body(...),
    user=Depends(require_any_permission("systemAdmin.config.manage", "systemAdmin.security.policy.manage")),
):
    tenant_id = _tenant_id()
    config_key = str((body or {}).get("configKey") or "").strip()
    reason = str((body or {}).get("reason") or "").strip()
    requested = (body or {}).get("overrides") or []
    if not config_key:
        raise AppException("VALIDATION_ERROR", "缺少 configKey")
    if len(reason) < 5:
        raise AppException("VALIDATION_ERROR", "恢复继承原因不少于 5 个字")
    if not isinstance(requested, list) or not requested:
        raise AppException("VALIDATION_ERROR", "缺少要撤销的学校层覆盖链")
    expected_versions: dict[int, int] = {}
    try:
        for item in requested:
            override_id = int(item["overrideId"])
            expected_versions[override_id] = int(item["expectedVersion"])
    except (KeyError, TypeError, ValueError):
        raise AppException("VALIDATION_ERROR", "overrides 必须包含 overrideId 与 expectedVersion") from None
    if len(expected_versions) != len(requested):
        raise AppException("VALIDATION_ERROR", "覆盖链包含重复 overrideId")

    now = datetime.utcnow().replace(microsecond=0)
    db = get_sessionmaker()()
    try:
        definition = _definition(db, config_key)
        _assert_config_write(user, definition.domain_code)
        rows = list(db.scalars(select(ConfigOverride).where(
            ConfigOverride.tenant_id == tenant_id,
            ConfigOverride.config_key == config_key,
            ConfigOverride.scope_type == SCOPE_TENANT,
            ConfigOverride.status == OVERRIDE_STATUS_ACTIVE,
            ConfigOverride.is_deleted.is_(False),
            or_(ConfigOverride.expires_at.is_(None), ConfigOverride.expires_at > now),
        ).with_for_update()).all())
        actual_ids = {int(row.id) for row in rows}
        requested_ids = set(expected_versions)
        if actual_ids != requested_ids:
            raise AppException(
                "DATA_CONFLICT", "学校层配置覆盖链已发生变化，请刷新后重试", http_status=409,
                details={"expectedIds": sorted(requested_ids), "actualIds": sorted(actual_ids)},
            )
        for row in rows:
            if int(row.version or 0) != expected_versions[int(row.id)]:
                raise AppException(
                    "DATA_CONFLICT", "配置覆盖已被其他人修改，请刷新后重试", http_status=409,
                    details={"overrideId": str(row.id)},
                )
        actor_id = _actor_id(user)
        for row in rows:
            row.status = OVERRIDE_STATUS_REVOKED
            row.reason = reason
            row.updated_by = actor_id
            row.version = int(row.version or 0) + 1
        from app.services import audit_log
        audit_log.record_critical_in_session(
            db, "CONFIG_OVERRIDE_RESTORE_INHERITANCE", f"config:{config_key}",
            detail={
                "configKey": config_key, "domain": definition.domain_code,
                "overrideIds": sorted(str(row.id) for row in rows), "overrideCount": len(rows),
                "reason": reason, "moduleCode": "systemAdmin", "scopeType": SCOPE_TENANT,
                "restoredByInheritance": True,
            },
            tenant_id=tenant_id, resource_id=config_key,
        )
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
    from app.services import effective_config_service as svc
    return success({
        "configKey": config_key,
        "revokedCount": len(expected_versions),
        "effective": svc.resolve(config_key, tenant_id=tenant_id),
    }, message="学校层覆盖已原子撤销并恢复继承")


# ── Stable identity: the exception-view role may inspect, write still needs bind/manage. ──
@router.get("/accounts/{user_id}/effective-identity", summary="账号稳定主体解析")
def effective_identity(
    user_id: int,
    user=Depends(require_any_permission(
        "systemAdmin.user.exception.view", "systemAdmin.user.view", "systemAdmin.user.manage"
    )),
):
    from app.services import account_identity_resolution_service as ident
    return success(ident.effective_identity(user_id))


# ── Formal role assignment: hardened service owns all privilege transitions. ──
@router.post("/role-assignments", summary="正式角色授权（生产权限边界）")
def grant_role_assignment(
    body: dict = Body(...),
    user=Depends(require_any_permission("systemAdmin.user.assign", "systemAdmin.role.config")),
):
    from app.services import role_assignment_p1_guard_service as guard
    raw_user_id = str((body or {}).get("userId") or "").strip()
    if not raw_user_id.isdigit():
        raise AppException("VALIDATION_ERROR", "userId 必须是账号主键")
    return success(guard.grant_assignment(
        int(raw_user_id), str((body or {}).get("roleCode") or ""),
        reason=str((body or {}).get("reason") or ""),
        effective_at=(body or {}).get("effectiveAt"),
        expires_at=(body or {}).get("expiresAt"),
        user=user,
    ), message="角色已授予")


@router.post("/role-assignments/{assignment_id}/revoke", summary="回收正式角色授权（生产权限边界）")
def revoke_role_assignment(
    assignment_id: int, body: dict = Body(...),
    user=Depends(require_any_permission("systemAdmin.user.assign", "systemAdmin.role.config")),
):
    from app.services import role_assignment_p1_guard_service as guard
    return success(guard.revoke_assignment(
        assignment_id, reason=str((body or {}).get("reason") or ""),
        expected_version=(body or {}).get("expectedVersion"), user=user,
    ), message="授权已回收")


@router.post("/role-assignments/{assignment_id}/transfer", summary="转交正式角色授权（生产权限边界）")
def transfer_role_assignment(
    assignment_id: int, body: dict = Body(...),
    user=Depends(require_any_permission("systemAdmin.user.assign", "systemAdmin.role.config")),
):
    from app.services import role_assignment_p1_guard_service as guard
    raw_target = str((body or {}).get("toUserId") or "").strip()
    if not raw_target.isdigit():
        raise AppException("VALIDATION_ERROR", "toUserId 必须是账号主键")
    return success(guard.transfer_assignment(
        assignment_id, to_user_id=int(raw_target), reason=str((body or {}).get("reason") or ""),
        expires_at=(body or {}).get("expiresAt"), expected_version=(body or {}).get("expectedVersion"),
        user=user,
    ), message="工作已转交")


# ── Organization impact receipt: preview is a server-signed, actor-bound write prerequisite. ──
def _org_model(org_type: str):
    code = str(org_type or "").upper()
    models = {"COLLEGE": College, "MAJOR": Major, "CLASS": SchoolClass}
    if code not in models:
        raise AppException("VALIDATION_ERROR", "type 必须是 COLLEGE / MAJOR / CLASS")
    return code, models[code]


def _org_impact_in_db(db, tenant_id: int, org_type: str, node_id: int) -> dict:
    code, model = _org_model(org_type)
    node = db.scalars(select(model).where(
        model.id == int(node_id), model.tenant_id == tenant_id, model.is_deleted.is_(False),
    )).first()
    if node is None:
        raise AppException("DATA_NOT_FOUND", "组织节点不存在", http_status=404)
    major_ids: list[int] = []
    class_ids: list[int] = []
    if code == "COLLEGE":
        major_ids = [int(v) for v in db.scalars(select(Major.id).where(
            Major.tenant_id == tenant_id, Major.college_id == int(node_id),
            Major.is_deleted.is_(False), Major.status == "ACTIVE",
        )).all()]
        if major_ids:
            class_ids = [int(v) for v in db.scalars(select(SchoolClass.id).where(
                SchoolClass.tenant_id == tenant_id, SchoolClass.major_id.in_(major_ids),
                SchoolClass.is_deleted.is_(False), SchoolClass.status == "ACTIVE",
            )).all()]
    elif code == "MAJOR":
        class_ids = [int(v) for v in db.scalars(select(SchoolClass.id).where(
            SchoolClass.tenant_id == tenant_id, SchoolClass.major_id == int(node_id),
            SchoolClass.is_deleted.is_(False), SchoolClass.status == "ACTIVE",
        )).all()]
    else:
        class_ids = [int(node_id)]
    students = 0
    if class_ids:
        students = int(db.scalar(select(func.count()).select_from(StudentProfile).where(
            StudentProfile.tenant_id == tenant_id,
            StudentProfile.class_id.in_(class_ids),
            StudentProfile.is_deleted.is_(False),
        )) or 0)
    assignments = int(db.scalar(select(func.count()).select_from(StaffAssignment).where(
        StaffAssignment.tenant_id == tenant_id,
        StaffAssignment.org_type == code,
        StaffAssignment.org_node_id == int(node_id),
        StaffAssignment.status == "ACTIVE",
        StaffAssignment.is_deleted.is_(False),
    )) or 0)
    return {
        "orgType": code, "orgNodeId": str(node_id),
        "nodeVersion": int(getattr(node, "version", 0) or 0),
        "affectedMajors": len(major_ids), "affectedClasses": len(class_ids) if code != "CLASS" else 0,
        "affectedStudents": students, "affectedAssignments": assignments,
    }


def _preview_secret() -> bytes:
    secret = str(getattr(settings, "JWT_SECRET_KEY", "") or settings.JWT_SECRET or "")
    if len(secret) < 16:
        raise AppException("SERVER_ERROR", "组织影响预演签名密钥未安全配置", http_status=503)
    return secret.encode("utf-8")


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _unb64(value: str) -> bytes:
    raw = str(value or "")
    return base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4))


def _sign_org_preview(payload: dict) -> str:
    encoded = _b64(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8"))
    sig = _b64(hmac.new(_preview_secret(), encoded.encode("ascii"), hashlib.sha256).digest())
    return f"{encoded}.{sig}"


def _verify_org_preview(token: str, *, user: dict, tenant_id: int, org_type: str, node_id: int) -> dict:
    try:
        encoded, supplied = str(token or "").split(".", 1)
        expected = _b64(hmac.new(_preview_secret(), encoded.encode("ascii"), hashlib.sha256).digest())
        if not hmac.compare_digest(expected, supplied):
            raise ValueError("signature")
        payload = json.loads(_unb64(encoded).decode("utf-8"))
    except Exception as exc:
        raise AppException("ORG_IMPACT_PREVIEW_INVALID", "组织影响预演凭证无效，请重新预演", http_status=409) from exc
    actor = str((user or {}).get("userId") or "")
    if (
        int(payload.get("tenantId") or 0) != tenant_id
        or str(payload.get("orgType") or "").upper() != str(org_type or "").upper()
        or int(payload.get("nodeId") or 0) != int(node_id)
        or str(payload.get("actor") or "") != actor
    ):
        raise AppException("ORG_IMPACT_PREVIEW_MISMATCH", "预演凭证与当前学校、节点或操作人不匹配", http_status=409)
    if int(payload.get("exp") or 0) < int(time.time()):
        raise AppException("ORG_IMPACT_PREVIEW_EXPIRED", "组织影响预演已超过 5 分钟，请重新预演", http_status=409)
    return payload


@router.get("/org-nodes/{org_type}/{node_id}/impact", summary="组织高危变更影响预演（签名凭证）")
def org_node_impact(
    org_type: str, node_id: int,
    user=Depends(require_any_permission("systemAdmin.org.view", "systemAdmin.org.manage")),
):
    tenant_id = _tenant_id()
    db = get_sessionmaker()()
    try:
        impact = _org_impact_in_db(db, tenant_id, org_type, node_id)
    finally:
        db.close()
    now = int(time.time())
    signed_payload = {
        "v": 1, "tenantId": tenant_id, "orgType": impact["orgType"], "nodeId": int(node_id),
        "nodeVersion": impact["nodeVersion"], "impact": {k: impact[k] for k in (
            "affectedMajors", "affectedClasses", "affectedStudents", "affectedAssignments"
        )},
        "actor": str((user or {}).get("userId") or ""), "iat": now, "exp": now + _ORG_PREVIEW_TTL_SECONDS,
    }
    return success({
        **impact,
        "previewToken": _sign_org_preview(signed_payload),
        "previewExpiresIn": _ORG_PREVIEW_TTL_SECONDS,
        "canDisable": not any(signed_payload["impact"].values()),
    })


@router.put("/org-nodes/{node_id}/status", summary="组织节点状态变更（停用必须签名预演）")
def set_org_node_status(
    node_id: int, body: dict = Body(...),
    user=Depends(require_any_permission("systemAdmin.org.manage")),
):
    tenant_id = _tenant_id()
    node_type = str((body or {}).get("type") or "").strip().upper()
    action = str((body or {}).get("action") or "").strip().upper()
    reason = str((body or {}).get("reason") or "").strip()
    if action not in {"DISABLE", "ENABLE"}:
        raise AppException("VALIDATION_ERROR", "action 必须是 DISABLE 或 ENABLE")
    if len(reason) < 5:
        raise AppException("VALIDATION_ERROR", "组织状态变更原因不少于 5 个字")
    if "expectedVersion" not in (body or {}):
        raise AppException("VALIDATION_ERROR", "组织状态变更必须提供 expectedVersion")
    expected_version = int((body or {}).get("expectedVersion"))
    code, model = _org_model(node_type)
    preview_payload = None
    if action == "DISABLE":
        preview_payload = _verify_org_preview(
            str((body or {}).get("previewToken") or ""), user=user, tenant_id=tenant_id,
            org_type=code, node_id=node_id,
        )
    db = get_sessionmaker()()
    try:
        row = db.scalars(select(model).where(
            model.id == int(node_id), model.tenant_id == tenant_id, model.is_deleted.is_(False),
        ).with_for_update()).first()
        if row is None:
            raise AppException("DATA_NOT_FOUND", "组织节点不存在", http_status=404)
        current_version = int(getattr(row, "version", 0) or 0)
        if current_version != expected_version:
            raise AppException("DATA_CONFLICT", "组织数据已被他人修改，请重新预演", http_status=409,
                               details={"currentVersion": current_version})
        impact = _org_impact_in_db(db, tenant_id, code, node_id)
        if action == "DISABLE":
            token_impact = preview_payload.get("impact") or {}
            current_impact = {k: impact[k] for k in token_impact}
            if int(preview_payload.get("nodeVersion") or -1) != current_version or token_impact != current_impact:
                raise AppException("DATA_CONFLICT", "组织影响面在预演后发生变化，请重新预演", http_status=409)
            blockers = {k: v for k, v in current_impact.items() if int(v or 0) > 0}
            if blockers:
                raise AppException("ORG_NODE_HAS_ACTIVE_REFERENCES", "存在未处理的下级、学生或在任任职，禁止停用",
                                   http_status=409, details=blockers)
            row.status = "DISABLED"
        else:
            row.status = "ACTIVE"
        row.version = current_version + 1
        from app.services import audit_log
        audit_log.record_critical_in_session(
            db,
            "ORG_NODE_DISABLE" if action == "DISABLE" else "ORG_NODE_ENABLE",
            f"{code}:{node_id}",
            detail={
                "reason": reason, "impact": impact, "expectedVersion": expected_version,
                "previewVerified": action == "DISABLE", "moduleCode": "systemAdmin",
            },
            tenant_id=tenant_id, resource_id=str(node_id),
        )
        db.commit()
        new_version = int(row.version or 0)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
    return success({
        "id": str(node_id), "status": "DISABLED" if action == "DISABLE" else "ACTIVE",
        "version": new_version, "impact": impact,
    }, message="节点已停用" if action == "DISABLE" else "节点已启用")
