"""standard-20k 沙箱账号凭据治理。

- 20K 学生与 1,280 教职工背景账号需要保持 ACTIVE 身份/角色关系，供真实权限与查询规模验收；
  但不属于可公开登录账号，因此每次建站只写入高熵随机口令的 hash，明文立即丢弃且永不输出。
- admin2 / teacher2 / student2 是明确的体验登录账号，默认必须由部署环境分别注入强口令；
  固定销售演示口令只能显式开启。生产服务器还必须额外确认目标租户为 007，避免误把兼容
  策略扩散到普通客户租户；仓库、构建产物、reset 日志均不得保存固定凭据。
"""
from __future__ import annotations

import os
import secrets

from app.core.security import hash_password

PUBLIC_PASSWORD_ENVS = {
    "admin2": "SANDBOX_ADMIN2_PASSWORD",
    "teacher2": "SANDBOX_TEACHER2_PASSWORD",
    "student2": "SANDBOX_STUDENT2_PASSWORD",
}
_MIN_PUBLIC_PASSWORD_LENGTH = 12
_LEGACY_DEMO_MIN_PASSWORD_LENGTH = 8


def _allow_fixed_local_demo_credentials() -> bool:
    """Allow documented sales-demo credentials only by explicit, tenant-scoped opt-in.

    Production requires a second acknowledgement containing the exact immutable
    sandbox tenant id.  Normal tenants and normal reset runs therefore retain
    the strong, distinct-password policy.
    """
    enabled = str(os.getenv("SANDBOX_ALLOW_FIXED_DEMO_CREDENTIALS") or "").strip() == "1"
    app_env = str(os.getenv("APP_ENV") or "development").strip().lower()
    deployment_mode = str(os.getenv("DEPLOYMENT_MODE") or "local").strip().lower()
    is_server = app_env in {"staging", "production"} or deployment_mode == "production"
    if not enabled:
        return False
    if not is_server:
        return True
    production_ack = str(
        os.getenv("SANDBOX_FIXED_DEMO_CREDENTIALS_PRODUCTION_ACK") or ""
    ).strip()
    return production_ack == "1000000000000000007"


def opaque_background_password_hash() -> str:
    """返回只用于背景身份的不可知高熵 password hash；明文不会离开当前调用栈。"""
    return hash_password(secrets.token_urlsafe(48))


def public_account_password_hashes() -> dict[str, str]:
    """读取体验口令并返回 hash；默认对缺失、弱口令和复用 fail-closed。"""
    fixed_local_demo = _allow_fixed_local_demo_credentials()
    minimum_length = _LEGACY_DEMO_MIN_PASSWORD_LENGTH if fixed_local_demo else _MIN_PUBLIC_PASSWORD_LENGTH
    raw: dict[str, str] = {}
    missing: list[str] = []
    for login, env_name in PUBLIC_PASSWORD_ENVS.items():
        value = str(os.getenv(env_name) or "").strip()
        if not value:
            missing.append(env_name)
            continue
        if len(value) < minimum_length:
            raise RuntimeError(
                f"{env_name} 至少需要 {minimum_length} 个字符，拒绝创建弱口令沙箱账号"
            )
        raw[login] = value
    if missing:
        raise RuntimeError(
            "standard-20k 体验账号缺少环境凭据：" + ", ".join(sorted(missing))
        )
    if not fixed_local_demo and len(set(raw.values())) != len(raw):
        raise RuntimeError("admin2 / teacher2 / student2 必须使用三份不同口令")
    return {login: hash_password(password) for login, password in raw.items()}
