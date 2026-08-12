"""
租户解析（多租户 SaaS 底座）
────────────────────────────────────────────────────────────
对齐 DB 冻结册：单库 / 单 schema + tenant_id 行级隔离（一期不做每校独立库）。
解析优先级：X-Tenant 头 → ?tenant= → 默认租户；令牌 tid 由 middleware 在其后重绑。

生产事实源规则（P0）：
- DB 模式下唯一事实源是 t_tenant（含真实 status）；
- 显式传了租户但查不到 → fail closed；
- production 下默认租户查不到、数据库解析异常、DB 模式判断异常 → 一律 fail closed，
  绝不回落 mock tenant；
- _MOCK_TENANTS 仅供 mock 登录、pytest 与本地联调使用。
"""
from __future__ import annotations

import threading
import time
from typing import Optional

from fastapi import Request

from app.core.config import settings
from app.core.context import set_tenant
from app.core.tenant_identity import (
    DEMO_SCHOOL,
    LEGACY_HNSH,
    PRIMARY_DEMO,
    SANDBOX_SCHOOL,
)

# ── 测试/Mock 夹具（非生产事实源）──────────────────────────────
# well-known tenant id 统一来自 app.core.tenant_identity，禁止在本模块重复写 Snowflake 常量。
_MOCK_TENANTS = {
    SANDBOX_SCHOOL.tenant_code: {
        "tenantId": str(SANDBOX_SCHOOL.tenant_id),
        "tenantCode": SANDBOX_SCHOOL.tenant_code,
        "tenantName": "体验沙箱学校",
        "status": "ACTIVE",
    },
    PRIMARY_DEMO.tenant_code: {
        "tenantId": str(PRIMARY_DEMO.tenant_id),
        "tenantCode": PRIMARY_DEMO.tenant_code,
        "tenantName": "示范职业技术学院",
        "status": "ACTIVE",
    },
    DEMO_SCHOOL.tenant_code: {
        "tenantId": str(DEMO_SCHOOL.tenant_id),
        "tenantCode": DEMO_SCHOOL.tenant_code,
        "tenantName": "演示职业技术学校",
        "status": "ACTIVE",
    },
    LEGACY_HNSH.tenant_code: {
        "tenantId": str(LEGACY_HNSH.tenant_id),
        "tenantCode": LEGACY_HNSH.tenant_code,
        "tenantName": "华南商贸职业学院",
        "status": "ACTIVE",
    },
}

# t_tenant 查询缓存：每请求查库代价太高，但缓存必须短，
# 否则"刚停用的学校"还能继续按 ACTIVE 服务若干分钟。
_CACHE_TTL_SECONDS = 30
_cache: dict[str, tuple[float, Optional[dict]]] = {}
_cache_lock = threading.Lock()


def invalidate_tenant_cache(code: str | None = None) -> None:
    """租户状态/套餐变更后调用，避免缓存把停用学校继续放行。"""
    with _cache_lock:
        if code is None:
            _cache.clear()
        else:
            _cache.pop(code, None)


def _lookup_db_tenant(code: str) -> Optional[dict]:
    """从 t_tenant 读取真实租户（含真实 status）。查不到/库不可用返回 None。"""
    now = time.monotonic()
    with _cache_lock:
        hit = _cache.get(code)
        if hit and now - hit[0] < _CACHE_TTL_SECONDS:
            return hit[1]
    result: Optional[dict] = None
    try:
        from sqlalchemy import select

        from app.db.session import get_sessionmaker
        from app.models import Tenant

        db = get_sessionmaker()()
        try:
            row = db.scalar(select(Tenant).where(Tenant.tenant_code == code))
            if row is not None:
                result = {
                    "tenantId": str(row.id),
                    "tenantCode": row.tenant_code,
                    "tenantName": row.short_name or row.school_name or "",
                    "status": (row.status or "").upper(),
                }
        finally:
            db.close()
    except Exception:  # noqa: BLE001 — 调用方按环境决定是否允许 mock 兜底
        return None
    with _cache_lock:
        _cache[code] = (now, result)
    return result


def resolve_tenant_code(request: Request) -> str:
    code = (
        request.headers.get("x-tenant")
        or request.query_params.get("tenant")
        or ""
    ).strip()
    if not code:
        code = settings.DEFAULT_TENANT_CODE
    return code


def tenant_code_was_explicit(request: Request) -> bool:
    """请求是否显式指定了租户（用于区分"没传"和"传了个不存在的"）。"""
    return bool((request.headers.get("x-tenant")
                 or request.query_params.get("tenant") or "").strip())


def lookup_tenant(code: str) -> Optional[dict]:
    """按 code 解析租户。production 永远只认数据库，不允许 mock 身份参与生产解析。"""
    code = (code or "").strip()
    if not code:
        return None
    try:
        from app.db.session import db_enabled

        enabled = db_enabled()
        if enabled:
            found = _lookup_db_tenant(code)
            if found is not None:
                return found
            if settings.is_prod:
                return None
        elif settings.is_prod:
            return None
    except Exception:  # noqa: BLE001
        if settings.is_prod:
            return None
    return _MOCK_TENANTS.get(code)


def resolve_tenant(request: Request) -> Optional[dict]:
    """解析当前请求所属租户并写入上下文。

    production 下无论租户来自显式参数还是 DEFAULT_TENANT_CODE，只要数据库不能给出真实租户，
    都返回 None 交给 middleware fail closed。非生产环境仍保留默认 mock 夹具便于 pytest/本地联调。
    """
    code = resolve_tenant_code(request)
    tenant = lookup_tenant(code)
    if tenant is None and not settings.is_prod and not tenant_code_was_explicit(request):
        tenant = _MOCK_TENANTS.get(settings.DEFAULT_TENANT_CODE)
    set_tenant(tenant)
    return tenant


def get_mock_tenant(code: str) -> Optional[dict]:
    """mock 登录 / pytest 夹具专用。生产解析请用 lookup_tenant。"""
    return _MOCK_TENANTS.get(code)
