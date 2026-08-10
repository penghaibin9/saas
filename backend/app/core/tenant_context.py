"""
租户解析（多租户 SaaS 底座）
────────────────────────────────────────────────────────────
对齐 DB 冻结册：单库 / 单 schema + tenant_id 行级隔离（一期不做每校独立库）。
解析优先级：X-Tenant 头 → ?tenant= → 默认租户；令牌 tid 由 middleware 在其后重绑。

事实源收口（P0）：
- DB 模式下唯一事实源是 t_tenant（含真实 status），不再由本模块凭空声明 ACTIVE；
- 显式传了租户但查不到 → **fail closed**，不再静默回落默认租户。
  旧行为会让"随便写一个不存在的 tenantCode"的请求落到默认学校的数据上。
- 下方 _MOCK_TENANTS 降级为**仅供 mock 登录与 pytest 夹具**使用的测试夹具，
  DB 模式下不参与生产解析（除非该 code 在库里也真实存在）。
"""
from __future__ import annotations

import threading
import time
from typing import Optional

from fastapi import Request

from app.core.config import settings
from app.core.context import set_tenant

# ── 测试/Mock 夹具（非生产事实源）──────────────────────────────
# 2026-07-28：生产库已收敛为单一体验沙箱（demo / demo-school / hnsh 三个演示租户已删除），
# DEFAULT_TENANT_CODE 随之改为 sandbox-school。
# demo / demo-school / hnsh 条目保留，因为它们是 mock 登录与 pytest 套件的租户夹具
# （测试在独立测试库自建 tenant_id=1000000000000000001 的主租户），与生产库租户无关；
# 删除会让大量测试文件的夹具解析不到租户。
_MOCK_TENANTS = {
    "sandbox-school": {
        "tenantId": "1000000000000000004",
        "tenantCode": "sandbox-school",
        "tenantName": "体验沙箱学校",
        "status": "ACTIVE",
    },
    "demo": {
        "tenantId": "1000000000000000001",
        "tenantCode": "demo",
        "tenantName": "示范职业技术学院",
        "status": "ACTIVE",
    },
    "demo-school": {
        "tenantId": "1000000000000000003",
        "tenantCode": "demo-school",
        "tenantName": "演示职业技术学校",
        "status": "ACTIVE",
    },
    "hnsh": {
        "tenantId": "1000000000000000002",
        "tenantCode": "hnsh",
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
    """从 t_tenant 读取真实租户（含真实 status）。查不到返回 None。"""
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
    except Exception:  # noqa: BLE001 — 库不可用时不缓存，交给下面按模式判定
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
    """按 code 解析租户。DB 模式以 t_tenant 为准，查不到才看测试夹具。"""
    code = (code or "").strip()
    if not code:
        return None
    try:
        from app.db.session import db_enabled
        if db_enabled():
            found = _lookup_db_tenant(code)
            if found is not None:
                return found
            # 库里没有该租户：只有非生产环境才允许用 mock 夹具兜底（pytest / 本地联调）。
            if settings.is_prod:
                return None
    except Exception:  # noqa: BLE001
        pass
    return _MOCK_TENANTS.get(code)


def resolve_tenant(request: Request) -> Optional[dict]:
    """解析当前请求所属租户并写入上下文。

    显式传入且解析不到 → 返回 None（fail closed），由 middleware 拒绝请求；
    绝不再回落到默认租户去服务另一所学校的数据。
    """
    code = resolve_tenant_code(request)
    tenant = lookup_tenant(code)
    if tenant is None and not tenant_code_was_explicit(request):
        # 没传租户：默认租户本身解析不到属于部署配置问题，保留原有夹具兜底路径。
        tenant = _MOCK_TENANTS.get(settings.DEFAULT_TENANT_CODE)
    set_tenant(tenant)
    return tenant


def get_mock_tenant(code: str) -> Optional[dict]:
    """mock 登录 / pytest 夹具专用。生产解析请用 lookup_tenant。"""
    return _MOCK_TENANTS.get(code)
