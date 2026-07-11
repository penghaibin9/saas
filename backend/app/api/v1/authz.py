"""
/api/v1/authz —— 权限与身份底座（对齐 docs/api/01-认证租户与当前上下文API.md）
1.1 登录 · 1.2 登出 · 1.3 刷新 · 1.4 当前用户 · 1.5 租户品牌 · 1.6 身份列表
1.7 当前身份 · 1.8 切换身份 · 1.9 数据范围 · 1.10 菜单 · 1.11 按钮 · 1.12 模块授权 · 1.13 权限校验
当前全部为 mock 实现；契约字段与真实版一致，接库时仅替换 services 层。
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field

from app.core.config import settings
from app.core.context import get_tenant
from app.core.exceptions import AppException, unauthorized
from app.core.response import success
from app.core.security import create_access_token, decode_token, get_current_user
from app.core.tenant_context import get_mock_tenant
from app.services import audit_log
from app.services.mock_data import (
    ACTIVE_CONTEXT, DATA_SCOPE_META, MOCK_BRAND, MOCK_BUTTONS, MOCK_MENUS,
    MOCK_MODULES, get_active_context, get_context, get_user_by_id, get_user_by_login,
)

router = APIRouter(prefix="/authz", tags=["01·认证与身份底座"])


# ────────────────── 请求体 ──────────────────
class LoginBody(BaseModel):
    tenantCode: str = Field(default="demo", description="学校编码（定位租户）")
    loginName: str = Field(min_length=1, description="登录名，mock 可用：student01 / teacher01 / admin01")
    password: str = Field(min_length=1, description="mock 阶段任意非空密码")
    clientType: str = Field(default="PC", description="PC | STUDENT_MINI | TEACHER_MINI")


class RefreshBody(BaseModel):
    refreshToken: str


class ActivateBody(BaseModel):
    clientType: str = "PC"
    deviceId: Optional[str] = None


class CheckBody(BaseModel):
    permissionCode: str
    resourceId: Optional[str] = None


def _issue_tokens(user: dict, tenant_code: str, ctx: dict) -> dict:
    claims = {
        "userId": user["userId"], "realName": user["realName"],
        "userType": user["userType"], "tid": tenant_code,
        "activeContextId": ctx["contextId"], "currentRoleCode": ctx["contextType"],
    }
    return {
        "accessToken": create_access_token(claims),
        "refreshToken": create_access_token({**claims, "typ": "refresh"}),
        "expiresIn": settings.JWT_EXPIRES_IN,
    }


# ────────────────── 1.1 登录（mock）──────────────────
@router.post("/login", summary="1.1 登录（mock：任意非空密码）")
def login(body: LoginBody):
    # 【安全修复 P0-1】mock 免密登录（任意非空密码即签发正式令牌）必须受生产门禁保护，
    # 否则等同免密管理员后门。与 /auth/mock-login 口径一致：生产（或显式关闭）一律 403，绝不签发令牌。
    if not settings.mock_login_enabled:
        audit_log.record("LOGIN_DENIED", f"user:{body.loginName}",
                         {"reason": "演示登录已关闭（生产禁用免密登录）"}, result="DENIED")
        raise AppException("NO_PERMISSION", "演示登录已关闭，请使用账号密码登录（/api/v1/auth/login）")
    user = get_user_by_login(body.loginName)
    if not user:
        audit_log.record("LOGIN", f"user:{body.loginName}", {"reason": "用户不存在"}, result="FAIL")
        raise AppException("UNAUTHORIZED", "用户名或密码错误（mock 账号：student01 / teacher01 / admin01）")
    tenant_code = body.tenantCode if get_mock_tenant(body.tenantCode) else settings.DEFAULT_TENANT_CODE
    ctx = get_active_context(user)
    ACTIVE_CONTEXT[user["userId"]] = ctx["contextId"]
    tokens = _issue_tokens(user, tenant_code, ctx)
    audit_log.record("LOGIN", f"user:{user['userId']}", {"clientType": body.clientType})
    return success({
        **tokens,
        "user": {
            "userId": user["userId"], "realName": user["realName"],
            "userType": user["userType"], "mustChangePassword": user["mustChangePassword"],
        },
        "contexts": user["contexts"],
        "activeContextId": ctx["contextId"],
    })


# ────────────────── 1.2 登出 ──────────────────
@router.post("/logout", summary="1.2 登出")
def logout(user=Depends(get_current_user)):
    audit_log.record("LOGOUT", f"user:{user['userId']}")
    return success({}, message="已登出")


# ────────────────── 1.3 刷新 Token ──────────────────
@router.post("/token/refresh", summary="1.3 刷新 Token")
def refresh_token(body: RefreshBody):
    claims = decode_token(body.refreshToken)
    if claims.get("typ") != "refresh":
        raise unauthorized("不是合法的 refreshToken")
    mock_user = get_user_by_id(claims.get("userId", ""))
    if not mock_user:
        raise unauthorized("用户不存在")
    ctx = get_active_context(mock_user)
    return success(_issue_tokens(mock_user, claims.get("tid", settings.DEFAULT_TENANT_CODE), ctx))


# ────────────────── 1.4 当前用户 ──────────────────
@router.get("/me", summary="1.4 当前用户")
def me(user=Depends(get_current_user)):
    mock_user = get_user_by_id(user["userId"])
    if not mock_user:
        raise unauthorized("用户不存在")
    ctx = get_active_context(mock_user)
    return success({
        "userId": mock_user["userId"], "realName": mock_user["realName"],
        "userType": mock_user["userType"], "avatarFileId": mock_user["avatarFileId"],
        "phoneMasked": mock_user["phoneMasked"],  # 契约 §九：敏感字段默认脱敏
        "activeContextId": ctx["contextId"],
    })


# ────────────────── 1.5 当前租户品牌（可公开，登录页需要）──────────────────
@router.get("/tenant/brand", summary="1.5 当前租户品牌 tenantBrandConfig")
def tenant_brand(request: Request):
    tenant = get_tenant()
    code = (request.query_params.get("tenant") or "").strip() or None
    if code is None and tenant:
        code = tenant["tenantCode"]
    brand = MOCK_BRAND.get(code or settings.DEFAULT_TENANT_CODE)
    if not brand:
        raise AppException("TENANT_NOT_FOUND", "租户不存在或已停用")
    return success(brand)


# ────────────────── 1.6 我的身份列表 ──────────────────
@router.get("/contexts", summary="1.6 我的身份列表")
def my_contexts(user=Depends(get_current_user)):
    mock_user = get_user_by_id(user["userId"])
    return success({"items": mock_user["contexts"]})


# ────────────────── 1.7 当前身份 ──────────────────
@router.get("/contexts/active", summary="1.7 当前身份")
def active_context(user=Depends(get_current_user)):
    mock_user = get_user_by_id(user["userId"])
    ctx = get_active_context(mock_user)
    return success({
        "contextId": ctx["contextId"], "contextType": ctx["contextType"],
        "contextName": ctx["contextName"], "dataScope": ctx["dataScope"],
        "moduleScope": [m["moduleCode"] for m in MOCK_MODULES if m["status"] not in ("SUSPENDED",)],
    })


# ────────────────── 1.8 切换身份（角色切换）──────────────────
@router.post("/contexts/{context_id}/activate", summary="1.8 切换身份")
def activate_context(context_id: str, body: ActivateBody, user=Depends(get_current_user)):
    mock_user = get_user_by_id(user["userId"])
    ctx = get_context(mock_user, context_id)
    if not ctx:
        raise AppException("ROLE_NOT_FOUND", "身份不存在、已禁用或不属于当前用户")
    ACTIVE_CONTEXT[mock_user["userId"]] = context_id
    audit_log.record("CONTEXT_SWITCH", f"context:{context_id}",
                     {"contextType": ctx["contextType"], "clientType": body.clientType})
    return success({
        "activeContextId": context_id,
        "contextType": ctx["contextType"],
        "dataScope": ctx["dataScope"],
        "menusChanged": True,  # 前端须重新拉 1.9 / 1.10 / 1.11
    })


# ────────────────── 1.9 我的数据范围 ──────────────────
@router.get("/me/data-scope", summary="1.9 我的数据范围")
def my_data_scope(user=Depends(get_current_user)):
    mock_user = get_user_by_id(user["userId"])
    ctx = get_active_context(mock_user)
    meta = DATA_SCOPE_META.get(ctx["dataScope"], {"scopeLabel": ctx["dataScope"], "studentCount": None})
    return success({"scopeType": ctx["dataScope"], **meta})


# ────────────────── 1.10 我的菜单 ──────────────────
@router.get("/me/menus", summary="1.10 我的菜单（按当前身份）")
def my_menus(user=Depends(get_current_user)):
    mock_user = get_user_by_id(user["userId"])
    ctx = get_active_context(mock_user)
    menus = MOCK_MENUS.get(ctx["contextType"], [])
    # 到期只读模块打标（不隐藏，契约 1.10 备注）
    readonly_modules = {m["moduleCode"] for m in MOCK_MODULES if m["status"] == "EXPIRED_READONLY"}

    def mark(items: list[dict]) -> list[dict]:
        return [{**m, "readonly": m["moduleCode"] in readonly_modules or m["readonly"],
                 "children": mark(m["children"])} for m in items]

    return success({"items": mark(menus)})


# ────────────────── 1.11 我的按钮权限 ──────────────────
@router.get("/me/buttons", summary="1.11 我的按钮权限")
def my_buttons(page: str = Query(default="studentList", description="页面标识，如 studentList / approvals"),
               user=Depends(get_current_user)):
    mock_user = get_user_by_id(user["userId"])
    ctx = get_active_context(mock_user)
    return success({"buttons": MOCK_BUTTONS.get(page, {}).get(ctx["contextType"], [])})


# ────────────────── 1.12 我的模块授权 ──────────────────
@router.get("/modules", summary="1.12 我的模块授权")
def my_modules(user=Depends(get_current_user)):
    return success({"items": MOCK_MODULES})


# ────────────────── 1.13 权限校验（内部）──────────────────
@router.post("/check", summary="1.13 权限校验")
def check_permission(body: CheckBody, user=Depends(get_current_user)):
    mock_user = get_user_by_id(user["userId"])
    ctx = get_active_context(mock_user)
    allowed_prefix = {"STUDENT": ("student.self", "todo", "message"),
                      "SCHOOL_ADMIN": ("",)}  # 管理员放开（mock）
    prefixes = allowed_prefix.get(ctx["contextType"], ("student", "approval", "todo", "message"))
    allowed = any(body.permissionCode.startswith(p) for p in prefixes)
    return success({"allowed": allowed})
