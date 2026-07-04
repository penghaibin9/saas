"""
租户解析（多租户 SaaS 底座）
────────────────────────────────────────────────────────────
对齐 DB 冻结册：单库 / 单 schema + tenant_id 行级隔离（一期不做每校独立库）。
解析优先级：X-Tenant 头 → ?tenant= → 令牌 tid → 默认租户。
本阶段为 mock：内置一个演示租户，不查库。将来接库时，此处改为查 t_tenant。
"""
from __future__ import annotations

from typing import Optional

from fastapi import Request

from app.core.config import settings
from app.core.context import set_tenant

# mock 租户注册表（将来由 t_tenant 表提供）。key = tenantCode
_MOCK_TENANTS = {
    "demo": {
        "tenantId": "1000000000000000001",
        "tenantCode": "demo",
        "tenantName": "示范职业技术学院",
        "status": "ACTIVE",
    },
    "hnsh": {
        "tenantId": "1000000000000000002",
        "tenantCode": "hnsh",
        "tenantName": "华南商贸职业学院",
        "status": "ACTIVE",
    },
}


def resolve_tenant_code(request: Request) -> str:
    code = (
        request.headers.get("x-tenant")
        or request.query_params.get("tenant")
        or ""
    ).strip()
    if not code:
        code = settings.DEFAULT_TENANT_CODE
    return code


def resolve_tenant(request: Request) -> Optional[dict]:
    """解析当前请求所属租户并写入上下文（single 模式恒为默认租户）。"""
    code = resolve_tenant_code(request)
    tenant = _MOCK_TENANTS.get(code) or _MOCK_TENANTS.get(settings.DEFAULT_TENANT_CODE)
    set_tenant(tenant)
    return tenant


def get_mock_tenant(code: str) -> Optional[dict]:
    return _MOCK_TENANTS.get(code)
