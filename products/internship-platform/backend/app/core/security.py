from __future__ import annotations
from datetime import datetime,timedelta,timezone
import secrets
import jwt
from fastapi import Header
from app.config import settings
from app.core.context import set_current_user,set_tenant
from app.core.exceptions import unauthorized

MOBILE_STAFF_USER_TYPES=frozenset({"SCHOOL_ADMIN","COLLEGE_ADMIN","INTERN_MENTOR","TEACHER","COUNSELOR","SECURITY_AUDITOR","LEADER"})

def decode_token(token):
    if not settings.JWT_SECRET: raise unauthorized("服务端未配置登录密钥")
    try:return jwt.decode(token,settings.JWT_SECRET,algorithms=[settings.JWT_ALG])
    except Exception as exc: raise unauthorized("登录状态已失效，请重新登录") from exc

def get_current_user(authorization:str|None=Header(None,alias="Authorization")):
    raw=str(authorization or "").strip()
    if not raw.lower().startswith("bearer "):raise unauthorized()
    user=decode_token(raw.split(None,1)[1])
    tenant=user.get("tenantId") or user.get("tenant_id")
    if not tenant:raise unauthorized("令牌缺少学校上下文")
    set_tenant({"tenantId":str(tenant),"tenantCode":user.get("tenantCode") or ""})
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
