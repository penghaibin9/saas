"""
认证与权限边界（当前为 mock）
────────────────────────────────────────────────────────────
- create_access_token / decode_token：演示用 JWT（HS256）。
- get_current_user：从 Authorization: Bearer 解析当前用户 + active_context，写入上下文。
- require_platform_admin：平台运营控制面（跨租户）与学校角色的边界隔离，
  凭 PLATFORM_ADMIN_TOKEN 访问；未配置则默认关闭（对齐冻结契约 §六 平台端例外）。
真实接库后：get_current_user 改为校验签名 + 查 t_user/t_user_active_context；
并叠加 模块授权 × 角色权限 × 数据范围 × 当前身份 四要素校验链（DB 冻结册 §10/§11）。
"""
from __future__ import annotations

import time
from typing import Optional

import jwt
from fastapi import Header

from app.core.config import settings
from app.core.context import set_current_user
from app.core.exceptions import AppException, unauthorized


def create_access_token(payload: dict) -> str:
    now = int(time.time())
    body = {**payload, "iat": now, "exp": now + settings.JWT_EXPIRES_IN}
    return jwt.encode(body, settings.JWT_SECRET, algorithm=settings.JWT_ALG)


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALG])
    except jwt.ExpiredSignatureError:
        raise unauthorized("登录已过期，请重新登录")
    except jwt.PyJWTError:
        raise unauthorized("认证令牌无效")


def _extract_bearer(authorization: Optional[str]) -> Optional[str]:
    if not authorization:
        return None
    return authorization[7:] if authorization.startswith("Bearer ") else authorization


def get_current_user(authorization: Optional[str] = Header(default=None)) -> dict:
    """FastAPI 依赖：要求登录，返回当前用户上下文并写入 contextvar。"""
    token = _extract_bearer(authorization)
    if not token:
        raise unauthorized("未提供认证令牌")
    claims = decode_token(token)
    user = {
        "userId": claims.get("userId"),
        "realName": claims.get("realName"),
        "userType": claims.get("userType"),
        "tenantCode": claims.get("tid"),
        "activeContextId": claims.get("activeContextId"),
        "currentRoleCode": claims.get("currentRoleCode"),
    }
    set_current_user(user)
    return user


def require_platform_admin(authorization: Optional[str] = Header(default=None)) -> str:
    """FastAPI 依赖：平台运营端（跨租户）鉴权，与学校角色严格隔离。"""
    expected = settings.PLATFORM_ADMIN_TOKEN
    if not expected:
        raise AppException("NO_PERMISSION", "平台运营控制台未启用（未配置 PLATFORM_ADMIN_TOKEN）")
    token = _extract_bearer(authorization)
    if not token or token != expected:
        raise unauthorized("平台运营令牌无效")
    return "platform"
