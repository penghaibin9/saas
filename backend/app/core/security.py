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
from fastapi import Depends, Header

from app.core.config import settings
from app.core.context import set_current_user
from app.core.exceptions import AppException, no_permission, unauthorized


def assert_secret_safe() -> None:
    """生产环境禁止默认 JWT 密钥（JWT_SECRET_KEY/JWT_SECRET 必须来自环境变量）。"""
    if settings.APP_ENV in ("prod", "production"):
        weak = {"change-me-in-production", "school-lifecycle-dev-secret-change-me-please-32", ""}
        if settings.jwt_secret in weak or len(settings.jwt_secret) < 32:
            raise RuntimeError("生产环境必须通过环境变量设置 ≥32 位随机 JWT_SECRET_KEY")


def assert_prod_flags_safe() -> None:
    """生产环境基线开关：DEBUG 必须为 false；mock-login 不得显式开启。"""
    if settings.is_prod:
        if settings.DEBUG:
            raise RuntimeError("生产环境必须设置 DEBUG=false")
        v = (settings.MOCK_LOGIN_ENABLED or "").strip().lower()
        if v in ("true", "1", "yes", "on"):
            raise RuntimeError("生产环境禁止显式开启 MOCK_LOGIN_ENABLED（免密演示登录）")


def assert_cors_safe() -> None:
    """生产环境禁止 CORS 通配符（allow_credentials=True 时 * 既不安全也不合规）。
    留空回退通配或显式含 * 均拒绝启动，强制运维显式配置白名单。"""
    if settings.is_prod:
        origins = settings.cors_origin_list
        if not settings.CORS_ORIGINS.strip() or "*" in origins:
            raise RuntimeError("生产环境必须显式配置 CORS_ORIGINS 白名单，禁止使用通配符")


def create_access_token(payload: dict) -> str:
    now = int(time.time())
    import uuid as _uuid
    body = {**payload, "jti": _uuid.uuid4().hex, "iat": now, "exp": now + settings.JWT_EXPIRES_IN}
    return jwt.encode(body, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
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
    from app.core.token_store import jti_blocked
    if jti_blocked(claims.get("jti")):
        from app.core.exceptions import unauthorized as _unauth
        raise _unauth("令牌已登出失效，请重新登录")
    # 租户绑定在 RequestContextMiddleware._bind_token_tenant 完成（async 上下文才能正确传播 contextvar）
    user = {
        "userId": claims.get("userId"),
        "loginName": claims.get("loginName") or claims.get("username"),
        "realName": claims.get("realName"),
        "userType": claims.get("userType"),
        "tenantCode": claims.get("tid"),
        "tenantId": claims.get("tenantId"),
        "activeContextId": claims.get("activeContextId"),
        "currentRoleCode": claims.get("currentRoleCode"),
        "permissionVersion": claims.get("permissionVersion"),
        "studentNo": claims.get("studentNo"),
        "tokenJti": claims.get("jti"),
        "tokenExp": claims.get("exp"),
    }
    # DB 账号逐请求复核角色归属。mock 账号不接库，保持原有演示链路。
    if str(user.get("userId") or "").startswith("db-"):
        from app.services.auth_service_db import validate_token_subject
        validate_token_subject(user)
    set_current_user(user)
    return user


def require_staff(user: dict = Depends(get_current_user)) -> dict:
    """FastAPI 依赖：仅教职工/管理员可访问的 PC 管理端接口。
    学生令牌一律 403，防止学生越权访问全校学生主档/审批/待办/导入导出/审计等 PC 接口。
    学生的合法入口是 /mobile/* 专用端点（严格本人 + 脱敏）。"""
    if (user.get("userType") or "").strip().upper() == "STUDENT":
        raise no_permission("该接口仅教职工可用，请使用移动端个人页")
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


# ── 真实口令（pbkdf2_sha256，标准库实现；生产可平滑替换 bcrypt/argon2）──
import hashlib
import secrets


def hash_password(plain: str, iterations: int = 200000) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", plain.encode(), bytes.fromhex(salt), iterations).hex()
    return f"pbkdf2_sha256${iterations}${salt}${digest}"


def verify_password(plain: str, stored: str) -> bool:
    try:
        algo, iter_s, salt, digest = stored.split("$")
        if algo != "pbkdf2_sha256":
            return False
        calc = hashlib.pbkdf2_hmac("sha256", plain.encode(), bytes.fromhex(salt), int(iter_s)).hex()
        return secrets.compare_digest(calc, digest)
    except Exception:  # noqa: BLE001
        return False
