"""首次/管理员重置密码后的服务端强制改密门禁。

安全原则：
- 真实 DB 账号以 ``t_user.must_change_password`` 为实时真值，不相信前端跳转或 JWT 旧 claim；
- 账号/租户/岗位有效性仍由 ``auth_service_db.validate_token_subject`` 先行校验；
- 必须改密时，只允许完成改密、查看最小当前身份信息与登出，任何业务 API fail-closed；
- 缓存只按 ``permissionVersion`` 版本化；密码重置/改密都会提升 user.version，因此不会跨安全版本复用；
- 没有 permissionVersion 的兼容令牌不缓存；安全版本变化后以独立 legacy-block 标记阻断到旧 access token 自然过期。
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


def _force_revalidation_key(raw_tenant_id: str, raw_user_id: str) -> str:
    return f"auth:force-db:{raw_tenant_id}:{raw_user_id}"


def _legacy_block_key(raw_tenant_id: str, raw_user_id: str) -> str:
    return f"auth:block-versionless:{raw_tenant_id}:{raw_user_id}"


def must_change_password_for_subject(user_ctx: dict) -> bool:
    """读取强制改密真值，并以权限版本为边界复用短期缓存。

    ``validate_token_subject`` 在调用本函数之前已经验证真实账号仍然存在且启用，并会在
    user.version / role version 变化时拒绝旧的版本化 access token。管理员重置、自助重置、
    本人改密都会提升 user.version。历史无 permissionVersion token 不能做版本比较，因此在
    force-db 释放前写入独立 legacy-block，至少覆盖一个完整 access-token TTL，避免旧会话复活。
    """
    if not db_enabled():
        return False
    raw_user_id = str((user_ctx or {}).get("userId") or "")
    raw_tenant_id = str((user_ctx or {}).get("tenantId") or "")
    if not raw_user_id.startswith("db-") or not raw_user_id[3:].isdigit() or not raw_tenant_id.isdigit():
        return False

    key = _cache_key(user_ctx)
    force_key = _force_revalidation_key(raw_tenant_id, raw_user_id)
    legacy_block_key = _legacy_block_key(raw_tenant_id, raw_user_id)
    if key:
        cached = cache_get(key)
        if cached == "1":
            return True
        if cached == "0":
            return False
    else:
        # 兼容旧 token 无法通过 permissionVersion 判断密码安全版本。仅在重置/改密安全事件后
        # 阻断它们；平时仍保留历史兼容读取，不把一次发布变成全员强制掉线。
        if cache_get(force_key) == "1" or cache_get(legacy_block_key) == "1":
            return True

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
        # 只有密码安全事件设置了 force-db 时才做这一段，因此正常热路不增加 Redis 操作。
        # 走到这里说明同一请求已先通过 validate_token_subject 的实时版本校验，并读取了本安全
        # 版本的 must_change_password 真值。先留下 legacy-block 覆盖旧无版本 token 的剩余寿命，
        # 再释放 force-db，让新版本 token 恢复 subject cache；写 block 失败则保留 force-db fail-closed。
        if cache_get(force_key) == "1":
            if cache_set(legacy_block_key, "1", settings.JWT_EXPIRES_IN):
                cache_delete(force_key)
    return result
