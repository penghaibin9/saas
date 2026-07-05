"""学生 PC 门户 · 租户配置管理端（/api/v1/admin/tenants/{tenant_id}/student-portal-config）。

权限：
- 平台运营（PLATFORM_OP/PLATFORM_OPERATOR）：可配置任意租户。
- 学校管理员（SCHOOL_ADMIN）：仅可配置本校（path tenant_id 必须 == 当前租户）。
- 普通老师 / 学生：403。
禁止跨租户修改；保存写审计（在 service 内）。
"""
from __future__ import annotations

from fastapi import APIRouter, Body, Depends, Path

from app.core.context import current_tenant_id
from app.core.exceptions import no_permission
from app.core.response import success
from app.core.security import get_current_user
from app.services import student_portal_service as sp

router = APIRouter(prefix="/admin/tenants", tags=["学生门户配置·管理端"])

PLATFORM_ROLES = {"PLATFORM_OP", "PLATFORM_OPERATOR"}
SCHOOL_ADMIN_ROLES = {"SCHOOL_ADMIN"}


def _authorize(tenant_id: int, user: dict) -> None:
    utype = (user.get("userType") or "").strip().upper()
    role = (user.get("currentRoleCode") or "").strip().upper()
    if utype == "STUDENT":
        raise no_permission("学生无权配置学生门户")
    if role in PLATFORM_ROLES:
        return  # 平台运营：任意租户
    if role in SCHOOL_ADMIN_ROLES:
        own = int(current_tenant_id() or 0)
        if own and own == int(tenant_id):
            return  # 学校管理员：仅本校
        raise no_permission("学校管理员只能配置本校租户")
    raise no_permission("无权配置学生门户（需平台运营或学校管理员）")


@router.get("/{tenant_id}/student-portal-config", summary="读取某租户学生门户配置（管理端）")
def get_portal_config(tenant_id: int = Path(...), user=Depends(get_current_user)):
    _authorize(tenant_id, user)
    return success(sp.get_config(int(tenant_id)))


@router.put("/{tenant_id}/student-portal-config", summary="保存某租户学生门户配置（管理端·写审计）")
def put_portal_config(tenant_id: int = Path(...), body: dict = Body(...), user=Depends(get_current_user)):
    _authorize(tenant_id, user)
    return success(sp.update_config(int(tenant_id), body, operator=user), message="保存成功")
