"""统一权限执行层 app/core/permissions：默认拒绝 + 角色授予 + 超管判定 + 审计端点 permissionCode 门禁。

对应系统管理中心审查修复：P0-3（后端 permissionCode 零执行）、P1-8（/audit/logs 任意教职工可读）、
P1-11（超管/管理员判定散落）。全程 mock 模式（不触 DB）。
"""
from __future__ import annotations

import pytest

from app.core.exceptions import AppException
from app.core.permissions import (PLATFORM_SUPER_ADMIN, enforce_permission,
                                   has_permission, is_super_admin)


def _u(role, user_type="TEACHER"):
    return {"currentRoleCode": role, "userType": user_type, "userId": "u_x", "realName": "测试"}


def test_default_deny_unknown_and_staff():
    # 未登记角色 / 最小权限兜底 STAFF → 一律拒绝（fail-closed）
    assert has_permission(_u("STAFF"), "systemAdmin.audit.view") is False
    assert has_permission(_u("SOME_CUSTOM_ROLE"), "academicAffairs.grade.publish") is False


def test_school_admin_all():
    a = _u("SCHOOL_ADMIN", "ADMIN")
    assert has_permission(a, "academicAffairs.grade.publish") is True
    assert has_permission(a, "systemAdmin.audit.view") is True


def test_super_admin():
    su = _u(PLATFORM_SUPER_ADMIN, PLATFORM_SUPER_ADMIN)
    assert is_super_admin(su) is True
    assert is_super_admin(_u("SCHOOL_ADMIN", "ADMIN")) is False
    assert has_permission(su, "anything.at.all") is True


def test_counselor_scoped_grants():
    c = _u("COUNSELOR")
    assert has_permission(c, "studentAffairs.leave.approve") is True    # 前缀通配命中
    assert has_permission(c, "academicAffairs.grade.publish") is False  # 越界拒绝
    assert has_permission(c, "systemAdmin.audit.view") is False


def test_enforce_raises_and_passes():
    with pytest.raises(AppException):
        enforce_permission(_u("COUNSELOR"), "systemAdmin.audit.view")
    ok = enforce_permission(_u("SCHOOL_ADMIN", "ADMIN"), "systemAdmin.audit.view")
    assert ok["currentRoleCode"] == "SCHOOL_ADMIN"


def _login(client, name):
    return client.post("/api/v1/auth/mock-login",
                       json={"loginName": name, "password": "x"}).json()["data"]["accessToken"]


def test_audit_endpoint_denies_counselor_allows_admin(client):
    # 【P1-8】辅导员无 systemAdmin.audit.view → 403（此前任意教职工可读全部安全审计）
    tk_c = _login(client, "counselor01")
    r = client.get("/api/v1/audit/logs", headers={"Authorization": f"Bearer {tk_c}"})
    assert r.status_code == 403, r.text
    # 学校管理员放行
    tk_a = _login(client, "school_admin01")
    r2 = client.get("/api/v1/audit/logs", headers={"Authorization": f"Bearer {tk_a}"})
    assert r2.status_code == 200 and r2.json()["code"] == 0
