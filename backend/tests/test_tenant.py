"""租户品牌：平台主名称必须是「高校学生全生命周期管理平台」，不得再以旧名为产品主名称。"""
from __future__ import annotations


def test_brand_platform_name(client, auth_headers):
    body = client.get("/api/v1/tenant/brand", headers=auth_headers).json()
    assert body["code"] == 0
    d = body["data"]
    assert d["platformDisplayName"] == "高校学生全生命周期管理平台"
    assert d["topbarTitle"] == "高校学生全生命周期管理平台"
    assert "enabledModules" in d and d["schoolName"]
