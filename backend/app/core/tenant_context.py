"""
租户解析（多租户 SaaS 底座）
────────────────────────────────────────────────────────────
对齐 DB 冻结册：单库 / 单 schema + tenant_id 行级隔离（一期不做每校独立库）。
解析优先级：X-Tenant 头 → ?tenant= → Bearer token tid → tenant-neutral auth/platform → 默认租户。

生产事实源规则（P0）：
- DB 模式下唯一事实源是 t_tenant（含真实 status）；
- 显式传了租户但查不到 → fail closed；
- 已登录业务请求优先按 token tid 查真实租户，不依赖某个默认沙箱存在；
- auth/platform 等租户中立入口允许在没有 tenant 事实时进入自身认证/控制面逻辑；
- production 下其它请求的默认租户查不到、数据库解析异常、DB 模式判断异常 → fail closed；
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

# 这些入口会在自己的业务层解析 tenant（登录 body、refresh subject、平台控制面），
# 因而 middleware 不应先拿一个 DEFAULT_TENANT_CODE 强行决定它们属于哪所学校。
# 注意必须做“命名空间边界”匹配，不能用 startswith('/api/v1/auth')，否则 /authz 会被误放行。
_TENANT_NEUTRAL_NAMESPACES = (
    "/api/v1/auth",
    "/api/v1/platform",
)
_TENANT_NEUTRAL_EXACT_PATHS = frozenset({
    "/health",
    "/health/ready",
    "/docs",
    "/openapi.json",
    "/redoc",
})
_TENANT_NEUTRAL = {
    "tenantId": "",
    "tenantCode": "",
    "tenantName": "",
    "status": "TENANT_NEUTRAL",
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


def _explicit_tenant_code(request: Request) -> str:
    return (
        request.headers.get("x-tenant")
        or request.query_params.get("tenant")
        or ""
    ).strip()


def _token_tenant_code(request: Request) -> str:
    auth = (request.headers.get("authorization") or "").strip()
    if not auth.lower().startswith("bearer "):
        return ""
    try:
        from app.core.security import decode_token

        claims = decode_token(auth[7:].strip())
        return str(claims.get("tid") or "").strip()
    except Exception:
        return ""


def _path_in_namespace(path: str, namespace: str) -> bool:
    return path == namespace or path.startswith(namespace + "/")


def _is_tenant_neutral_path(request: Request) -> bool:
    path = str(request.url.path or "").rstrip("/") or "/"
    if path in _TENANT_NEUTRAL_EXACT_PATHS:
        return True
    return any(_path_in_namespace(path, namespace) for namespace in _TENANT_NEUTRAL_NAMESPACES)


def resolve_tenant_code(request: Request) -> str:
    explicit = _explicit_tenant_code(request)
    if explicit:
        return explicit
    token_code = _token_tenant_code(request)
    if token_code:
        return token_code
    if _is_tenant_neutral_path(request):
        return ""
    return settings.DEFAULT_TENANT_CODE


def tenant_code_was_explicit(request: Request) -> bool:
    """请求是否显式指定了租户（用于区分"没传"和"传了个不存在的"）。"""
    return bool(_explicit_tenant_code(request))


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

    显式 tenant / token tid 必须解析到真实 DB 租户；production 业务请求否则 fail closed。
    只有 auth/platform 等租户中立路径在既无显式 tenant、也无 token tid 时使用空的中立上下文。
    非生产环境仍保留默认 mock 夹具便于 pytest/本地联调。
    """
    code = resolve_tenant_code(request)
    if not code and _is_tenant_neutral_path(request) and not tenant_code_was_explicit(request):
        tenant = dict(_TENANT_NEUTRAL)
        set_tenant(tenant)
        return tenant

    tenant = lookup_tenant(code)
    if tenant is None and not settings.is_prod and not tenant_code_was_explicit(request):
        tenant = _MOCK_TENANTS.get(settings.DEFAULT_TENANT_CODE)
    set_tenant(tenant)
    return tenant


def get_mock_tenant(code: str) -> Optional[dict]:
    """mock 登录 / pytest 夹具专用。生产解析请用 lookup_tenant。"""
    return _MOCK_TENANTS.get(code)
