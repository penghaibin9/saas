"""RBAC：菜单 / 按钮权限 / 数据范围。"""
from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.response import success
from app.core.security import get_current_user
from app.services import mock_rbac_service as rbac_svc

router = APIRouter()


@router.get("/menus", summary="当前身份可见菜单树")
def menus(user=Depends(get_current_user)):
    return success(rbac_svc.get_menus(user))


@router.get("/permissions", summary="当前身份按钮权限码（permissionActions）")
def permissions(page: str | None = None, user=Depends(get_current_user)):
    return success(rbac_svc.get_permissions(user, page))


@router.get("/data-scope", summary="当前身份数据范围 + 全部 12 种范围目录")
def data_scope(user=Depends(get_current_user)):
    return success(rbac_svc.get_data_scope(user))


@router.get("/roles", summary="平台角色目录（11 类角色，含平台/学校边界说明）")
def roles(user=Depends(get_current_user)):
    return success(rbac_svc.get_role_catalog(user))


@router.get("/current-context", summary="当前身份上下文（currentRole + dataScope + permissionActions）")
def current_context(user=Depends(get_current_user)):
    return success(rbac_svc.get_current_context(user))
