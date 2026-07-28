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
# 2026-07-28：生产库已收敛为单一体验沙箱（demo / demo-school / hnsh 三个演示租户已删除），
# DEFAULT_TENANT_CODE 随之改为 sandbox-school。
# 下方 demo / demo-school / hnsh 条目保留，因为它们是 mock 登录与 pytest 套件的租户夹具
# （测试在独立测试库自建 tenant_id=1000000000000000001 的主租户），与生产库租户无关；
# 删除会让 229 个测试文件的夹具解析不到租户。
# sandbox-school 的 tenantId 必须与库内 t_tenant.id 一致：历史上此处写 1000000000000000007，
# 而真实建站落在 1000000000000000004，会让 mock 登录的沙箱会话看不到任何数据。
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
