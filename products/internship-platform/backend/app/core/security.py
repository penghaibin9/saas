from __future__ import annotations
from datetime import datetime,timedelta,timezone
import secrets
import jwt
from fastapi import Header, Request
from app.config import settings
from app.core.context import set_current_user,set_tenant
from app.core.exceptions import no_permission, unauthorized

MOBILE_STAFF_USER_TYPES=frozenset({"SCHOOL_ADMIN","COLLEGE_ADMIN","INTERN_MENTOR","TEACHER","COUNSELOR","SECURITY_AUDITOR","LEADER"})

def decode_token(token):
    if not settings.JWT_SECRET: raise unauthorized("服务端未配置登录密钥")
    try:return jwt.decode(token,settings.JWT_SECRET,algorithms=[settings.JWT_ALG])
    except Exception as exc: raise unauthorized("登录状态已失效，请重新登录") from exc

_PASSWORD_RECOVERY_ALLOWLIST = frozenset({
    "/api/v1/auth/me",
    "/api/v1/auth/change-password",
})


def _validate_db_subject(user: dict, request_path: str = "") -> dict:
    """G11/IAM: every real DB token is checked against the current credential epoch.

    This deliberately uses DB truth on each Standalone request. The product has a much
    smaller subject volume than the platform control plane, and fail-closed correctness is
    more important here than introducing another Redis authorization cache.
    """
    raw_user_id = str((user or {}).get("userId") or "")
    raw_tenant_id = str((user or {}).get("tenantId") or (user or {}).get("tenant_id") or "")
    if not raw_user_id.startswith("db-"):
        return user
    if not raw_user_id[3:].isdigit() or not raw_tenant_id.isdigit():
        raise unauthorized("真实账号令牌无效，请重新登录")
    from sqlalchemy import select
    from app.db.session import db_enabled, get_sessionmaker
    if not db_enabled():
        raise unauthorized("真实账号校验需要数据库")
    from app.models import User
    db=get_sessionmaker()()
    try:
        account=db.scalar(select(User).where(
            User.id==int(raw_user_id[3:]),
            User.tenant_id==int(raw_tenant_id),
            User.is_deleted.is_(False),
            User.status=="ACTIVE",
        ))
        if not account:
            raise unauthorized("账号已停用或令牌已失效，请重新登录")
        token_version=user.get("credentialVersion")
        current_version=int(account.credential_version or 0)
        valid=(current_version==0) if token_version is None else (
            type(token_version) is int and token_version==current_version
        )
        if not valid:
            raise unauthorized("认证凭据已更新，请重新登录")
        user["mustChangePassword"]=bool(account.must_change_password)
        if account.must_change_password and (request_path.rstrip("/") or "/") not in _PASSWORD_RECOVERY_ALLOWLIST:
            from app.core.exceptions import AppException
            raise AppException(
                "PASSWORD_CHANGE_REQUIRED",
                "首次登录或密码被管理员重置后必须先修改临时密码",
                details={"action":"CHANGE_PASSWORD","path":"/api/v1/auth/change-password"},
                http_status=403,
            )
        return user
    finally:
        db.close()


def get_current_user(request:Request,authorization:str|None=Header(None,alias="Authorization")):
    raw=str(authorization or "").strip()
    if not raw.lower().startswith("bearer "):raise unauthorized()
    user=decode_token(raw.split(None,1)[1])
    tenant=user.get("tenantId") or user.get("tenant_id")
    if not tenant:raise unauthorized("令牌缺少学校上下文")
    set_tenant({"tenantId":str(tenant),"tenantCode":user.get("tenantCode") or ""})
    user=_validate_db_subject(user,request.url.path)
    set_current_user(user)
    return user

def create_access_token(payload: dict, *, expires_in: int | None = None) -> str:
    import time
    ttl = settings.JWT_EXPIRES_IN if expires_in is None else max(60, int(expires_in))
    now = int(time.time())
    body = {**dict(payload or {}), "jti": secrets.token_hex(16), "iat": now, "exp": now + ttl}
    if not settings.JWT_SECRET:
        raise unauthorized("服务端未配置登录密钥")
    return jwt.encode(body, settings.JWT_SECRET, algorithm=settings.JWT_ALG)

def hash_password(plain: str, iterations: int = 200000) -> str:
    import hashlib
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", str(plain or "").encode(), bytes.fromhex(salt), int(iterations)).hex()
    return "pbkdf2_sha256${}${}${}".format(int(iterations), salt, digest)

def verify_password(plain: str, stored: str) -> bool:
    import hashlib
    try:
        algo, iter_s, salt, digest = str(stored or "").split("$")
        if algo != "pbkdf2_sha256":
            return False
        calc = hashlib.pbkdf2_hmac("sha256", str(plain or "").encode(), bytes.fromhex(salt), int(iter_s)).hex()
        return secrets.compare_digest(calc, digest)
    except Exception:
        return False


def require_mobile_student(user=__import__("fastapi").Depends(get_current_user)):
    if str((user or {}).get("userType") or "").upper() != "STUDENT":
        raise no_permission("该接口仅学生移动端可用")
    return user
