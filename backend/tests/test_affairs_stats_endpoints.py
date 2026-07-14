"""学工统计端点冒烟（认定/资助/处分统计聚合口径）。

重点：/aid/stats 此前端点已声明但 service 缺 aid_stats 函数（潜在 500），本测试守回归。
三端点均返回 code==0 + 约定聚合字段；不含个体明细/金额明文。
"""
from __future__ import annotations

BASE = "/api/v1/student-affairs"


def _hdr(client, login_name):
    data = client.post("/api/v1/auth/mock-login",
                       json={"loginName": login_name, "password": "any"}).json()["data"]
    return {"Authorization": f"Bearer {data['accessToken']}"}


def test_aid_stats_ok(client, db_mode):
    hdr = _hdr(client, "school_admin01")
    r = client.get(f"{BASE}/aid/stats", headers=hdr).json()
    assert r["code"] == 0
    d = r["data"]
    assert "total" in d and "approved" in d and isinstance(d["byStatus"], list) and isinstance(d["byLevel"], list)


def test_funding_stats_ok(client, db_mode):
    hdr = _hdr(client, "school_admin01")
    r = client.get(f"{BASE}/funding/stats", headers=hdr).json()
    assert r["code"] == 0
    d = r["data"]
    assert "total" in d and isinstance(d["byStatus"], list) and isinstance(d["byType"], list)


def test_discipline_stats_ok(client, db_mode):
    hdr = _hdr(client, "school_admin01")
    r = client.get(f"{BASE}/discipline/stats", headers=hdr).json()
    assert r["code"] == 0
    d = r["data"]
    assert "total" in d and isinstance(d["byStatus"], list) and "reconcile" in d
