"""I4 green cards that do not require the blocked I3 staging migration.

Role-member and audit projections are page-bounded for 20K-school operation.
Identity-import 20K remains explicitly BLOCKED_BY_I3; this module must not be
used to claim 20K single-job import Gold before normalized staging exists.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, or_, select

from app.core.context import current_tenant_id
from app.core.exceptions import not_found
from app.core.permissions import require_permission
from app.core.response import paginate, success
from app.db.session import get_sessionmaker
from app.models import Role, User, UserRole
from app.models.audit import SecurityAuditLog
from app.modules.system_admin.routers import system_control_plane_router as _base

_extra = APIRouter()


def _load_role(db, tenant_id: int, role_id: int) -> Role:
    role = db.scalar(select(Role).where(
        Role.id == int(role_id),
        Role.tenant_id == int(tenant_id),
        Role.is_deleted.is_(False),
    ))
    if role is None:
        raise not_found("角色不存在或不属于当前学校")
    return role


@_extra.get("/system/roles/{role_id}/members", summary="角色成员分页（20K 安全）")
def role_members(
    role_id: int,
    page: int = Query(1, ge=1),
    pageSize: int = Query(50, ge=1, le=200),
    user=Depends(require_permission("systemAdmin.role.view")),
):
    _ = user
    tenant_id = int(current_tenant_id() or 0)
    db = get_sessionmaker()()
    try:
        role = _load_role(db, tenant_id, role_id)
        base = select(User.id, User.login_name, User.real_name, User.status).join(
            UserRole, UserRole.user_id == User.id
        ).where(
            UserRole.tenant_id == tenant_id,
            UserRole.role_id == role.id,
            UserRole.status == "ACTIVE",
            UserRole.is_deleted.is_(False),
            User.tenant_id == tenant_id,
            User.is_deleted.is_(False),
        )
        total = int(db.scalar(select(func.count()).select_from(base.subquery())) or 0)
        rows = db.execute(base.order_by(User.id).offset((page - 1) * pageSize).limit(pageSize)).all()
        items = [
            {"id": str(uid), "loginName": login_name, "name": real_name or login_name, "status": status}
            for uid, login_name, real_name, status in rows
        ]
        return success(paginate(items, total, page, pageSize))
    finally:
        db.close()


@_extra.get("/system/roles/{role_id}/audit", summary="角色操作留痕分页")
def role_audit(
    role_id: int,
    page: int = Query(1, ge=1),
    pageSize: int = Query(50, ge=1, le=200),
    user=Depends(require_permission("systemAdmin.audit.view")),
):
    _ = user
    tenant_id = int(current_tenant_id() or 0)
    db = get_sessionmaker()()
    try:
        role = _load_role(db, tenant_id, role_id)
        predicate = or_(
            SecurityAuditLog.resource == f"role:{role.id}",
            SecurityAuditLog.resource_id == str(role.id),
        )
        total = int(db.scalar(select(func.count(SecurityAuditLog.id)).where(
            SecurityAuditLog.tenant_id == tenant_id,
            predicate,
        )) or 0)
        rows = list(db.scalars(select(SecurityAuditLog).where(
            SecurityAuditLog.tenant_id == tenant_id,
            predicate,
        ).order_by(SecurityAuditLog.created_at.desc(), SecurityAuditLog.id.desc()).offset(
            (page - 1) * pageSize
        ).limit(pageSize)).all())
        items = [
            {
                "id": str(row.id),
                "operatorId": str(row.operator_id or ""),
                "operatorName": row.operator_name or "",
                "action": row.action,
                "result": row.result,
                "detail": row.detail_json or {},
                "traceId": row.trace_id,
                "createdAt": row.created_at.isoformat(timespec="seconds") if row.created_at else None,
            }
            for row in rows
        ]
        return success(paginate(items, total, page, pageSize))
    finally:
        db.close()


@_extra.get("/system/roles/{role_id}", summary="学校角色详情（分页能力声明）")
def role_detail(role_id: int, user=Depends(require_permission("systemAdmin.role.view"))):
    payload = _base.get_system_role(role_id, user=user)
    if isinstance(payload, dict) and isinstance(payload.get("data"), dict):
        data = payload["data"]
        preview = list(data.get("members") or [])
        total = int(data.get("memberCount") or 0)
        data["memberPreview"] = preview
        data["memberPreviewCount"] = len(preview)
        data["membersTruncated"] = total > len(preview)
        data["membersEndpoint"] = f"/api/v1/system/roles/{role_id}/members"
        data["auditTrailComplete"] = False
        data["auditEndpoint"] = f"/api/v1/system/roles/{role_id}/audit"
    return payload


def _key(route) -> tuple[str, str]:
    methods = tuple(sorted(getattr(route, "methods", set()) or set()))
    return (",".join(methods), getattr(route, "path", ""))


def _compose() -> APIRouter:
    replacement = {_key(route): route for route in _extra.routes}
    composed = APIRouter()
    routes = []
    for route in _base.router.routes:
        routes.append(replacement.pop(_key(route), route))
    routes.extend(replacement.values())
    composed.routes = routes
    return composed


router = _compose()


def __getattr__(name: str):
    return getattr(_base, name)


def __dir__():
    return sorted(set(globals()) | set(dir(_base)))
