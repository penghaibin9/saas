"""SaaS 内置角色与用户角色关系的幂等落库服务；调用方负责事务提交。"""
from __future__ import annotations

from sqlalchemy import select

from app.core.exceptions import AppException
from app.services.saas_role_templates import (BUILTIN_ROLE_TEMPLATES,
                                               ROLE_TEMPLATE_BY_CODE,
                                               ROLE_TEMPLATE_VERSION)


def ensure_builtin_roles(db, tenant_id: int) -> dict:
    from app.models import Role
    codes = tuple(ROLE_TEMPLATE_BY_CODE)
    existing = db.scalars(select(Role).where(
        Role.tenant_id == tenant_id, Role.role_code.in_(codes))).all()
    by_code = {r.role_code: r for r in existing}
    report = {"created": 0, "restored": 0, "unchanged": 0,
              "templateVersion": ROLE_TEMPLATE_VERSION}
    for template in BUILTIN_ROLE_TEMPLATES:
        code = template["roleCode"]
        role = by_code.get(code)
        marker = f"SAAS_BUILTIN:{ROLE_TEMPLATE_VERSION};scope={template['defaultScope']}"
        if role is None:
            db.add(Role(tenant_id=tenant_id, role_code=code,
                        role_name=template["roleName"], role_type="SYSTEM",
                        status="ACTIVE", remark=marker))
            report["created"] += 1
            continue
        if (role.role_type or "SYSTEM").upper() == "CUSTOM":
            raise AppException("DATA_CONFLICT", f"自定义角色占用了系统编码：{code}")
        if role.is_deleted or role.status not in ("ACTIVE", "ENABLED"):
            role.is_deleted = False
            role.status = "ACTIVE"
            role.version = int(role.version or 0) + 1
            report["restored"] += 1
        else:
            report["unchanged"] += 1
        role.role_type = "SYSTEM"
        role.role_name = template["roleName"]
        role.remark = marker
    db.flush()
    return report


def ensure_user_roles(db, tenant_id: int, user_id: int, role_codes: list[str]) -> dict:
    from app.models import Role, UserRole
    unknown = [code for code in role_codes if code not in ROLE_TEMPLATE_BY_CODE]
    if unknown:
        raise AppException("VALIDATION_ERROR", f"不支持的预设角色：{','.join(unknown)}")
    roles = db.scalars(select(Role).where(
        Role.tenant_id == tenant_id, Role.role_code.in_(tuple(role_codes)),
        Role.is_deleted.is_(False), Role.status.in_(("ACTIVE", "ENABLED")))).all()
    by_code = {r.role_code: r for r in roles}
    missing = [code for code in role_codes if code not in by_code]
    if missing:
        raise AppException("DATA_CONFLICT", f"租户角色模板未初始化：{','.join(missing)}")
    role_ids = tuple(r.id for r in roles)
    links = db.scalars(select(UserRole).where(
        UserRole.tenant_id == tenant_id, UserRole.user_id == user_id,
        UserRole.role_id.in_(role_ids))).all()
    by_role_id = {link.role_id: link for link in links}
    report = {"created": 0, "restored": 0, "unchanged": 0}
    for code in role_codes:
        role = by_code[code]
        link = by_role_id.get(role.id)
        if link is None:
            db.add(UserRole(tenant_id=tenant_id, user_id=user_id,
                            role_id=role.id, status="ACTIVE"))
            report["created"] += 1
        elif link.is_deleted or link.status != "ACTIVE":
            link.is_deleted = False
            link.status = "ACTIVE"
            link.version = int(link.version or 0) + 1
            report["restored"] += 1
        else:
            report["unchanged"] += 1
    db.flush()
    return report
