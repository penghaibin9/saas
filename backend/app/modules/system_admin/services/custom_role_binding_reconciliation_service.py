"""Replay-safe reconciliation for nullable N-1 CustomRoleSource.role_id rows.

This module is deliberately not a runtime fallback. ``role_code`` is used only
inside this one-time repair boundary to prove/create stable Role identity. It
never materializes RolePermission; DRAFT governance source is not runtime
authorization.
"""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import func, select

from app.core.exceptions import AppException
from app.models import Role
from app.models.permission_governance import CustomRoleSource
from app.services import audit_log

AUDIT_ACTION = "CUSTOM_ROLE_BINDING_RECONCILE"


@dataclass(frozen=True)
class ReconcilePlanItem:
    source_id: int
    tenant_id: int
    role_code: str
    action: str
    role_id: int | None = None
    error_code: str | None = None
    error_message: str | None = None

    def as_dict(self) -> dict:
        return {
            "sourceId": str(self.source_id),
            "tenantId": str(self.tenant_id),
            "roleCode": self.role_code,
            "action": self.action,
            "roleId": str(self.role_id) if self.role_id is not None else None,
            "errorCode": self.error_code,
            "errorMessage": self.error_message,
        }


def _validate_source(source: CustomRoleSource) -> tuple[str, str] | None:
    role_code = str(source.role_code or "").strip()
    template_code = str(source.source_template_code or "").strip()
    try:
        template_version = int(source.source_template_version or 0)
    except (TypeError, ValueError):
        template_version = 0
    permission_snapshot = source.permission_codes_json
    if not role_code:
        return "CUSTOM_ROLE_SOURCE_PROVENANCE_INVALID", "role_code 为空"
    if not template_code or template_version <= 0:
        return "CUSTOM_ROLE_SOURCE_PROVENANCE_INVALID", "source template provenance 不完整"
    if not isinstance(permission_snapshot, dict) or not isinstance(permission_snapshot.get("items"), list):
        return "CUSTOM_ROLE_SOURCE_PROVENANCE_INVALID", "permission snapshot 不是规范 items 列表"
    return None


def _plan_unbound_source(db, source: CustomRoleSource, *, lock_roles: bool) -> ReconcilePlanItem:
    invalid = _validate_source(source)
    if invalid:
        return ReconcilePlanItem(
            source_id=int(source.id), tenant_id=int(source.tenant_id), role_code=str(source.role_code or ""),
            action="UNRESOLVED", error_code=invalid[0], error_message=invalid[1],
        )

    role_stmt = select(Role).where(
        Role.tenant_id == int(source.tenant_id),
        Role.role_code == str(source.role_code),
        Role.is_deleted.is_(False),
    ).order_by(Role.id)
    if lock_roles:
        role_stmt = role_stmt.with_for_update()
    candidates = list(db.scalars(role_stmt).all())
    if len(candidates) > 1:
        return ReconcilePlanItem(
            source_id=int(source.id), tenant_id=int(source.tenant_id), role_code=str(source.role_code),
            action="UNRESOLVED", error_code="CUSTOM_ROLE_BINDING_AMBIGUOUS",
            error_message="同租户同 role_code 存在多个 runtime Role，拒绝猜测绑定",
        )
    if len(candidates) == 1:
        role = candidates[0]
        if str(role.role_type or "").upper() != "CUSTOM":
            return ReconcilePlanItem(
                source_id=int(source.id), tenant_id=int(source.tenant_id), role_code=str(source.role_code),
                action="UNRESOLVED", role_id=int(role.id), error_code="CUSTOM_ROLE_BINDING_SYSTEM_COLLISION",
                error_message="同 code 已存在非 CUSTOM Role，必须人工修复",
            )
        if str(role.status or "").upper() != "ACTIVE":
            return ReconcilePlanItem(
                source_id=int(source.id), tenant_id=int(source.tenant_id), role_code=str(source.role_code),
                action="UNRESOLVED", role_id=int(role.id), error_code="CUSTOM_ROLE_BINDING_INACTIVE_ROLE",
                error_message="同 code CUSTOM Role 非 ACTIVE，拒绝自动复用",
            )
        return ReconcilePlanItem(
            source_id=int(source.id), tenant_id=int(source.tenant_id), role_code=str(source.role_code),
            action="BIND_EXISTING", role_id=int(role.id),
        )
    return ReconcilePlanItem(
        source_id=int(source.id), tenant_id=int(source.tenant_id), role_code=str(source.role_code),
        action="CREATE_IDENTITY_ONLY",
    )


def custom_role_binding_inventory(db) -> dict:
    """Pure-read preflight used by the writer-fence/drain and contract gates."""
    null_source_count = int(db.scalar(select(func.count(CustomRoleSource.id)).where(
        CustomRoleSource.role_id.is_(None),
        CustomRoleSource.is_deleted.is_(False),
    )) or 0)
    orphan_source_count = int(db.scalar(select(func.count(CustomRoleSource.id)).where(
        CustomRoleSource.role_id.is_not(None),
        CustomRoleSource.is_deleted.is_(False),
        ~select(Role.id).where(
            Role.id == CustomRoleSource.role_id,
            Role.tenant_id == CustomRoleSource.tenant_id,
            Role.is_deleted.is_(False),
        ).exists(),
    )) or 0)
    max_source_id = int(db.scalar(select(func.max(CustomRoleSource.id)).where(
        CustomRoleSource.is_deleted.is_(False),
    )) or 0)
    return {
        "nullSourceCount": null_source_count,
        "orphanSourceCount": orphan_source_count,
        "maxSourceId": max_source_id,
        "contractReady": null_source_count == 0 and orphan_source_count == 0,
    }


def reconcile_custom_role_bindings(
    db,
    *,
    dry_run: bool = True,
    writer_fence_confirmed: bool = False,
    n_minus_one_writer_count: int | None = None,
    release_sha: str = "",
    reason: str = "P-05 N-1 CustomRoleSource stable binding reconciliation",
) -> dict:
    """Plan or apply stable role_id binding without granting any permission.

    Apply mode deliberately requires deployment-plane evidence that all N-1
    writers have drained. An application flag cannot prove an old process has
    stopped, so callers must supply that evidence explicitly.
    """
    if not dry_run:
        if not writer_fence_confirmed or n_minus_one_writer_count != 0:
            raise AppException(
                "CUSTOM_ROLE_WRITER_FENCE_REQUIRED",
                "必须先冻结旧 CUSTOM Role writer 并确认 N-1 实例数为 0，才能执行绑定修复",
                http_status=409,
                details={"writerFenceConfirmed": bool(writer_fence_confirmed),
                         "nMinusOneWriterCount": n_minus_one_writer_count},
            )
        if not str(release_sha or "").strip():
            raise AppException(
                "RELEASE_SHA_REQUIRED",
                "生产绑定修复必须记录当前 releaseSha",
                http_status=422,
            )

    source_stmt = select(CustomRoleSource).where(
        CustomRoleSource.role_id.is_(None),
        CustomRoleSource.is_deleted.is_(False),
    ).order_by(CustomRoleSource.tenant_id, CustomRoleSource.id)
    if not dry_run:
        source_stmt = source_stmt.with_for_update()
    sources = list(db.scalars(source_stmt).all())
    plans = [_plan_unbound_source(db, source, lock_roles=not dry_run) for source in sources]
    unresolved = [item for item in plans if item.action == "UNRESOLVED"]

    report = {
        "dryRun": bool(dry_run),
        "total": len(plans),
        "updated": 0,
        "skipped": 0,
        "failed": len(unresolved),
        "unresolved": len(unresolved),
        "items": [item.as_dict() for item in plans],
        "writerFence": {
            "confirmed": bool(writer_fence_confirmed),
            "nMinusOneWriterCount": n_minus_one_writer_count,
            "authority": "DEPLOYMENT_PLANE_EVIDENCE",
        },
    }
    if dry_run or not plans:
        report["inventory"] = custom_role_binding_inventory(db)
        return report
    if unresolved:
        raise AppException(
            "CUSTOM_ROLE_BINDING_RECONCILE_UNRESOLVED",
            "存在无法自动证明的 CUSTOM Role 绑定，整批拒绝写入",
            http_status=409,
            details={"failed": len(unresolved), "items": [item.as_dict() for item in unresolved[:50]]},
        )

    source_by_id = {int(source.id): source for source in sources}
    changed_items: list[dict] = []
    for item in plans:
        source = source_by_id[item.source_id]
        role = None
        if item.action == "BIND_EXISTING":
            role = db.scalar(select(Role).where(
                Role.id == int(item.role_id),
                Role.tenant_id == int(item.tenant_id),
                Role.is_deleted.is_(False),
            ).with_for_update())
            if role is None or str(role.role_type or "").upper() != "CUSTOM":
                raise AppException(
                    "CUSTOM_ROLE_BINDING_CHANGED_DURING_RECONCILE",
                    "reconcile 期间 runtime Role 已变化，拒绝提交",
                    http_status=409,
                    details={"sourceId": str(source.id), "roleId": str(item.role_id)},
                )
        elif item.action == "CREATE_IDENTITY_ONLY":
            role = Role(
                tenant_id=int(source.tenant_id),
                role_code=str(source.role_code),
                role_name=str(source.role_code),
                role_type="CUSTOM",
                status="ACTIVE",
                remark=(
                    f"RECONCILED_IDENTITY_ONLY:{source.source_template_code}:"
                    f"v{int(source.source_template_version or 0)}"
                ),
                created_by=source.created_by,
                updated_by=source.updated_by,
            )
            db.add(role)
            db.flush()
        else:  # pragma: no cover - protected by unresolved gate above
            raise AssertionError(f"unexpected reconcile action: {item.action}")

        before = {"roleId": None, "sourceVersion": int(source.version or 0)}
        source.role_id = int(role.id)
        source.version = int(source.version or 0) + 1
        audit_log.record_critical_in_session(
            db,
            AUDIT_ACTION,
            f"custom-role-source:{source.id}",
            detail={
                "tenantId": str(source.tenant_id),
                "sourceId": str(source.id),
                "roleId": str(role.id),
                "roleCode": source.role_code,
                "before": before,
                "after": {"roleId": str(role.id), "sourceVersion": int(source.version or 0)},
                "releaseSha": str(release_sha),
                "reason": str(reason),
                "permissionMaterialized": False,
            },
            tenant_id=int(source.tenant_id),
            resource_id=str(source.id),
        )
        changed_items.append({**item.as_dict(), "roleId": str(role.id)})

    db.flush()
    remaining = int(db.scalar(select(func.count(CustomRoleSource.id)).where(
        CustomRoleSource.role_id.is_(None),
        CustomRoleSource.is_deleted.is_(False),
    )) or 0)
    if remaining:
        raise AppException(
            "CUSTOM_ROLE_BINDING_RECONCILE_INCOMPLETE",
            "绑定修复事务内仍存在未绑定 source，拒绝提交",
            http_status=409,
            details={"remaining": remaining},
        )

    report.update({
        "updated": len(changed_items),
        "failed": 0,
        "unresolved": 0,
        "items": changed_items,
        "inventory": custom_role_binding_inventory(db),
    })
    return report
