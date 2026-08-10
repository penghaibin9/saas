"""
认证与权限边界

- create_access_token / decode_token：JWT（HS256）；生产必须强密钥。
- get_current_user：从 Authorization: Bearer 解析当前用户 + active_context。
- 平台运营端（跨租户）鉴权见 api/v1/platform.py 的 require_platform_super_admin。
- DB 账号（userId 以 db- 开头）逐请求复核；演示账号仅在非 production 且 mock-login 开启时可用。
"""
from __future__ import annotations

import time
from typing import Optional

import jwt
from fastapi import Depends, Header, Request

from app.core.config import settings
from app.core.context import set_current_user
from app.core.exceptions import AppException, no_permission, unauthorized


def assert_secret_safe() -> None:
    """生产环境禁止默认 JWT 密钥（JWT_SECRET / JWT_SECRET_KEY 必须够长且非默认）。"""
    if settings.is_prod:
        weak = {"change-me-in-production", "school-lifecycle-dev-secret-change-me-please-32", ""}
        if settings.jwt_secret in weak or len(settings.jwt_secret) < 32:
            raise RuntimeError("生产环境必须通过环境变量设置 ≥32 位随机 JWT_SECRET（或兼容名 JWT_SECRET_KEY）")
    from app.core.field_crypto import assert_field_encryption_safe
    assert_field_encryption_safe()


def assert_prod_flags_safe() -> None:
    """生产 / DEPLOYMENT_MODE=production 基线开关。"""
    if not settings.is_prod:
        return
    if settings.DEBUG:
        raise RuntimeError("生产环境必须设置 DEBUG=false")
    v = (settings.MOCK_LOGIN_ENABLED or "").strip().lower()
    if v in ("true", "1", "yes", "on"):
        raise RuntimeError("生产环境禁止显式开启 MOCK_LOGIN_ENABLED（免密演示登录）")
    if not settings.DB_ENABLED:
        raise RuntimeError("生产环境必须设置 DB_ENABLED=true")
    url = (settings.DATABASE_URL or "").strip()
    if not url:
        if not (settings.DB_HOST and settings.DB_NAME and settings.DB_USER):
            raise RuntimeError("生产环境必须配置 DATABASE_URL 或完整的 DB_HOST/DB_NAME/DB_USER")
        if settings.db_dialect != "mysql":
            raise RuntimeError("生产环境仅允许 MySQL（请配置 mysql DATABASE_URL 或 DB_DRIVER=mysql）")
    elif settings.db_dialect != "mysql":
        raise RuntimeError("生产环境仅允许 MySQL DATABASE_URL")
    if not (settings.INTERNAL_OPS_TOKEN or "").strip():
        raise RuntimeError("生产环境必须设置 INTERNAL_OPS_TOKEN（保护 /health/ready 与 /internal/metrics）")


def assert_cors_safe() -> None:
    """生产环境禁止 CORS 通配符。"""
    if settings.is_prod:
        origins = settings.cors_origin_list
        if not settings.CORS_ORIGINS.strip() or "*" in origins:
            raise RuntimeError("生产环境必须显式配置 CORS_ORIGINS 白名单，禁止使用通配符")


def assert_scale_safe() -> None:
    """多实例部署必须配 Redis。"""
    if settings.is_prod and settings.MULTI_INSTANCE and not settings.REDIS_URL.strip():
        raise RuntimeError(
            "多实例部署（MULTI_INSTANCE=true）必须配置 REDIS_URL：否则限流/登录锁定/"
            "令牌黑名单在各进程间不共享，无法生效。请配置 Redis，或单进程部署时置 MULTI_INSTANCE=false")


def assert_scheduler_safe() -> None:
    """多 worker / 多实例禁止在 Web 进程内嵌定时任务。"""
    mode = (settings.SCHEDULER_MODE or "web").strip().lower()
    multi = bool(settings.MULTI_INSTANCE) or int(settings.WEB_CONCURRENCY or 1) > 1
    if mode == "web" and multi:
        raise RuntimeError(
            "MULTI_INSTANCE=true 或 WEB_CONCURRENCY>1 时禁止 SCHEDULER_MODE=web；"
            "请改用独立 scheduler 进程（SCHEDULER_MODE=external）")
    if settings.is_prod and mode == "web" and multi:
        raise RuntimeError("生产多实例禁止 Web 内嵌定时任务")


def create_access_token(payload: dict, *, expires_in: int | None = None) -> str:
    now = int(time.time())
    import uuid as _uuid
    ttl = settings.JWT_EXPIRES_IN if expires_in is None else max(60, int(expires_in))
    body = {**payload, "jti": _uuid.uuid4().hex, "iat": now, "exp": now + ttl}
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


def _optional_positive_int_claim(claims: dict, key: str) -> int | None:
    """解析正式对象 ID claim；存在但非法时拒绝整个令牌，禁止静默退回学号匹配。"""
    raw = claims.get(key)
    if raw in (None, ""):
        return None
    try:
        value = int(raw)
    except (TypeError, ValueError):
        raise unauthorized("认证令牌中的学生身份无效")
    if value <= 0:
        raise unauthorized("认证令牌中的学生身份无效")
    return value


def get_current_user(request: Request, authorization: Optional[str] = Header(default=None)) -> dict:
    """FastAPI 依赖：要求登录，逐请求复核真实账号并执行首次改密强门禁。"""
    token = _extract_bearer(authorization)
    if not token:
        raise unauthorized("未提供认证令牌")
    claims = decode_token(token)
    from app.core.token_store import jti_blocked
    if jti_blocked(claims.get("jti")):
        from app.core.exceptions import unauthorized as _unauth
        raise _unauth("令牌已登出失效，请重新登录")
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
        "studentId": _optional_positive_int_claim(claims, "studentId"),
        "studentNo": claims.get("studentNo"),
        "collegeId": claims.get("collegeId"),
        "collegeIds": claims.get("collegeIds"),
        "majorId": claims.get("majorId"),
        "majorIds": claims.get("majorIds"),
        "guardianPhoneHash": claims.get("guardianPhoneHash"),
        "tokenJti": claims.get("jti"),
        "tokenExp": claims.get("exp"),
    }
    if str(user.get("userId") or "").startswith("db-"):
        from app.services.auth_service_db import validate_token_subject
        validate_token_subject(user)
        # 强制改密必须使用数据库实时真值，而不是只信登录响应/JWT。这样管理员重置密码后，
        # 已存在的 access token 也不能继续操作业务；仅保留改密、me、logout 最小恢复链。
        from app.services.password_change_gate import (
            is_password_change_allowlisted,
            must_change_password_for_subject,
        )
        if must_change_password_for_subject(user) and not is_password_change_allowlisted(request.url.path):
            raise AppException(
                "PASSWORD_CHANGE_REQUIRED",
                "首次登录或密码被管理员重置后必须先修改初始密码",
                details={"action": "CHANGE_PASSWORD", "path": "/api/v1/auth/change-password"},
                http_status=403,
            )
    tenant_id = str(user.get("tenantId") or "")
    user_id = str(user.get("userId") or "")
    if tenant_id and user_id:
        from app.core.token_store import rate_limit
        if not rate_limit(f"api:tenant:{tenant_id}", settings.TENANT_API_RATE_LIMIT_PER_SECOND, 1):
            raise AppException("RATE_LIMITED", "当前学校请求过于集中，请稍后重试")
        if not rate_limit(f"api:user:{tenant_id}:{user_id}", settings.USER_API_RATE_LIMIT_PER_SECOND, 1):
            raise AppException("RATE_LIMITED", "请求过于频繁，请稍后重试")
    set_current_user(user)
    return user


STAFF_USER_TYPES = frozenset({
    "TEACHER", "ADMIN", "STAFF", "SCHOOL_ADMIN", "PLATFORM_SUPER_ADMIN",
})

MOBILE_STAFF_USER_TYPES = frozenset({"TEACHER", "ADMIN", "STAFF", "SCHOOL_ADMIN"})


def require_staff(user: dict = Depends(get_current_user)) -> dict:
    """FastAPI 依赖：仅教职工/管理员可访问的 PC 管理端接口。"""
    if (user.get("userType") or "").strip().upper() not in STAFF_USER_TYPES:
        raise no_permission("该接口仅教职工可用，请使用个人/家长门户")
    return user


def require_mobile_staff(user: dict = Depends(get_current_user)) -> dict:
    """FastAPI 依赖：学校移动教师端严格教职工白名单，空值/未知类型一律拒绝。"""
    if not user.get("userId") or (user.get("userType") or "").strip().upper() not in MOBILE_STAFF_USER_TYPES:
        raise no_permission("该接口仅学校教职工移动端可用")
    return user


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
