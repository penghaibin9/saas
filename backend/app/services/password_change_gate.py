"""首次/管理员重置密码后的服务端强制改密门禁。

安全原则：
- 真实 DB 账号以 ``t_user.must_change_password`` 为实时真值，不相信前端跳转或 JWT 旧 claim；
- 账号/租户/岗位有效性仍由 ``auth_service_db.validate_token_subject`` 先行校验；
- 必须改密时，只允许完成改密、查看最小当前身份信息与登出，任何业务 API fail-closed；
- 缓存只按 ``permissionVersion`` 版本化；密码重置/改密都会提升 user.version，因此不会跨安全版本复用；
- 没有 permissionVersion 的兼容令牌不缓存，继续逐请求查库；mock/开发账号不接数据库。
"""
from __future__ import annotations

from sqlalchemy import select

from app.core.config import settings
from app.core.redis_client import cache_delete, cache_get, cache_set
from app.db.session import db_enabled, get_sessionmaker

# 这些路径只用于让用户完成安全恢复动作，不包含身份切换、菜单、导出或任何业务写接口。
PASSWORD_CHANGE_ALLOWLIST = frozenset({
    "/api/v1/auth/change-password",
    "/api/v1/auth/logout",
    "/api/v1/auth/me",
    # 冻结兼容入口仅保留 me/logout；authz 不提供改密，因此不能绕过主改密链。
    "/api/v1/authz/me",
    "/api/v1/authz/logout",
})


def is_password_change_allowlisted(path: str | None) -> bool:
    normalized = (path or "").rstrip("/") or "/"
    return normalized in PASSWORD_CHANGE_ALLOWLIST


def _cache_key(user_ctx: dict) -> str | None:
    """只有带权限版本的正式 DB 令牌才允许缓存，避免兼容旧 token 跨密码版本复用。"""
    raw_user_id = str((user_ctx or {}).get("userId") or "")
    raw_tenant_id = str((user_ctx or {}).get("tenantId") or "")
    permission_version = str((user_ctx or {}).get("permissionVersion") or "").strip()
    if (not raw_user_id.startswith("db-") or not raw_user_id[3:].isdigit()
            or not raw_tenant_id.isdigit() or not permission_version):
        return None
    return f"auth:password-change:{raw_tenant_id}:{raw_user_id}:{permission_version}"


def must_change_password_for_subject(user_ctx: dict) -> bool:
    """读取强制改密真值，并以权限版本为边界复用短期缓存。

    ``validate_token_subject`` 在调用本函数之前已经验证真实账号仍然存在且启用，并会在
    user.version / role version 变化时拒绝旧 access token。管理员重置、自助重置、本人改密
    都会提升 user.version，所以缓存不会跨密码安全版本复用；缓存不可用时直接回库，不放行。
    """
    if not db_enabled():
        return False
    raw_user_id = str((user_ctx or {}).get("userId") or "")
    raw_tenant_id = str((user_ctx or {}).get("tenantId") or "")
    if not raw_user_id.startswith("db-") or not raw_user_id[3:].isdigit() or not raw_tenant_id.isdigit():
        return False

    key = _cache_key(user_ctx)
    if key:
        cached = cache_get(key)
        if cached == "1":
            return True
        if cached == "0":
            return False

    from app.models import User

    db = get_sessionmaker()()
    try:
        value = db.scalar(select(User.must_change_password).where(
            User.id == int(raw_user_id[3:]),
            User.tenant_id == int(raw_tenant_id),
            User.status == "ACTIVE",
            User.is_deleted.is_(False),
        ))
        result = bool(value)
    finally:
        db.close()

    if key:
        # 缓存失败只影响性能，不改变刚从数据库读取的授权真值；下一请求会再次回库。
        cache_set(key, "1" if result else "0", settings.AUTH_SUBJECT_CACHE_TTL)
        # 高危密码重置会先写 force-db 标记，迫使旧 access token 绕过 subject cache 查库。
        # 走到这里说明同一请求已先通过 validate_token_subject 的实时版本校验，并且本安全版本
        # 也读取了 must_change_password 真值；此时可清除 force 标记，恢复新合法 token 的缓存热路。
        # 缺 permissionVersion 的兼容令牌没有 key，因此永远不会在这里清标记，继续 fail-closed 回库。
        cache_delete(f"auth:force-db:{raw_tenant_id}:{raw_user_id}")
    return result
