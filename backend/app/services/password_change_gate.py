"""首次/管理员重置密码后的服务端强制改密门禁。

安全原则：
- 真实 DB 账号以 ``t_user.must_change_password`` 为实时真值，不相信前端跳转或 JWT 旧 claim；
- 账号/租户/岗位有效性仍由 ``auth_service_db.validate_token_subject`` 先行校验；
- 必须改密时，只允许完成改密、查看最小当前身份信息与登出，任何业务 API fail-closed；
- mock/开发账号不接数据库，不改变既有开发链路。
"""
from __future__ import annotations

from sqlalchemy import select

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


def must_change_password_for_subject(user_ctx: dict) -> bool:
    """从当前数据库读取强制改密真值。

    ``validate_token_subject`` 在调用本函数之前已经验证真实账号仍然存在且启用；这里仍使用
    tenant + user + active + non-deleted 条件，避免未来调用顺序变化时扩大授权。
    """
    if not db_enabled():
        return False
    raw_user_id = str((user_ctx or {}).get("userId") or "")
    raw_tenant_id = str((user_ctx or {}).get("tenantId") or "")
    if not raw_user_id.startswith("db-") or not raw_user_id[3:].isdigit() or not raw_tenant_id.isdigit():
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
        # fail-closed is handled by validate_token_subject for missing/disabled users. If a future
        # caller bypasses that validator, a missing row must not be interpreted as a privileged state.
        return bool(value)
    finally:
        db.close()
