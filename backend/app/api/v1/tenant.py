"""租户品牌配置（tenantBrandConfig 唯一来源）。"""
from __future__ import annotations

from fastapi import APIRouter

from app.core.response import success
from app.services import mock_tenant_service as tenant_svc

router = APIRouter()


@router.get("/brand", summary="当前租户品牌配置（登录页/顶栏品牌来源）")
def brand():
    return success(tenant_svc.get_brand())
