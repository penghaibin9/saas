"""角色权限"谁说了算"的回归锁。

要回答的问题：学校管理员在后台撤掉某角色的某项权限之后，后端是不是**立即**
真的不允许了？还是要等重新登录、等缓存过期、甚至根本没生效？

本项目有两套授权真值并存，本文件把各自的边界钉死：
1. 自定义角色（role_type=CUSTOM）→ 权限来自 t_role_permission，每次请求实时查库；
2. 内置角色（role_type=SYSTEM）→ 由平台基线 ROLE_PERMISSIONS 维护，
   后台**不允许**改（返回明确报错，而不是改了个寂寞）。
"""
from __future__ import annotations

import pytest

TENANT = 1000000000000000001


def _mk_role_and_permission(db, code="systemAdmin.audit.view", role_type="CUSTOM"):
    from sqlalchemy import select
    from app.models import Permission, Role, RolePermission

    role = Role(tenant_id=TENANT, role_code=f"TEST_{role_type}", role_name="测试角色",
                role_type=role_type)
    db.add(role)
    db.flush()

    # Permission Catalog is global authority and may already have reconciled this code.
    # Reuse that canonical fact instead of manufacturing a duplicate unique permission row.
    perm = db.scalars(select(Permission).where(Permission.permission_code == code)).first()
    if perm is None:
        perm = Permission(permission_code=code, permission_name=code,
                          module_code=code.split(".")[0], action=code.split(".")[-1])
        db.add(perm)
        db.flush()

    link = RolePermission(tenant_id=TENANT, role_id=role.id, permission_id=perm.id,
                          status="ACTIVE")
    db.add(link)
    db.commit()
    return role, perm, link


def _user_for(role):
    return {
        "userId": "db-1", "realName": "测试管理员",
        "tenantId": str(TENANT),
        "activeContextId": f"role:{role.id}",
        "currentRoleCode": role.role_code,
        "userType": "SCHOOL_STAFF",
    }


def test_custom_role_revocation_takes_effect_immediately(db_mode):
    """撤权后**同一个会话、不重新登录**就必须立刻被拒。"""
    from app.core.context import set_tenant
    from app.core.permissions import has_permission
    from app.db.session import get_sessionmaker

    set_tenant({"tenantId": str(TENANT)})
    db = get_sessionmaker()()
    try:
        role, _perm, link = _mk_role_and_permission(db)
        user = _user_for(role)
        assert has_permission(user, "systemAdmin.audit.view") is True

        # 管理员在后台撤销这一项
        link.status = "DISABLED"
        link.is_deleted = True
        db.commit()

        assert has_permission(user, "systemAdmin.audit.view") is False, \
            "撤权后必须立即拒绝，不能等重新登录或缓存过期"
    finally:
        db.close()
        set_tenant(None)


def test_custom_role_does_not_inherit_builtin_baseline(db_mode):
    """自定义角色不得回落到内置角色的宽松基线。"""
    from app.core.context import set_tenant
    from app.core.permissions import has_permission
    from app.db.session import get_sessionmaker

    set_tenant({"tenantId": str(TENANT)})
    db = get_sessionmaker()()
    try:
        role, _perm, _link = _mk_role_and_permission(db)
        user = _user_for(role)
        # 只授了 audit.view，别的一律不给
        assert has_permission(user, "systemAdmin.user.manage") is False
    finally:
        db.close()
        set_tenant(None)


def test_builtin_role_permission_edit_is_rejected_not_silently_ignored(client, auth_headers, db_mode):
    """内置角色不允许改权限——必须明确报错，不能返回成功却什么也没发生。"""
    from app.core.context import set_tenant
    from app.db.session import get_sessionmaker

    set_tenant({"tenantId": str(TENANT)})
    db = get_sessionmaker()()
    try:
        role, _perm, _link = _mk_role_and_permission(db, role_type="SYSTEM")
        role_id = role.id
    finally:
        db.close()

    resp = client.put(f"/api/v1/system/roles/{role_id}/permissions",
                      json={"permissionCodes": []}, headers=auth_headers)
    body = resp.json()
    assert body.get("code") != 0, "内置角色改权限必须失败，不能假装成功"
    set_tenant(None)


def test_permission_read_failure_denies_instead_of_falling_back(db_mode, monkeypatch):
    """读授权出异常时必须拒绝，绝不回落到更宽的内置授权。"""
    from app.core import permissions as perms
    from app.core.context import set_tenant

    set_tenant({"tenantId": str(TENANT)})
    try:
        def boom():
            raise RuntimeError("db down")
        monkeypatch.setattr("app.db.session.get_sessionmaker", boom)
        user = {"userId": "db-1", "tenantId": str(TENANT),
                "activeContextId": "role:999999", "currentRoleCode": "SCHOOL_ADMIN",
                "userType": "SCHOOL_STAFF"}
        assert perms.has_permission(user, "systemAdmin.user.manage") is False
    finally:
        set_tenant(None)
