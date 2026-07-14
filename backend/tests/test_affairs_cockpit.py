"""13A-D 学工统计驾驶舱冒烟（各域聚合，仅聚合口径）。"""
from __future__ import annotations

BASE = "/api/v1/student-affairs"


def _hdr(client, login_name):
    data = client.post("/api/v1/auth/mock-login",
                       json={"loginName": login_name, "password": "any"}).json()["data"]
    return {"Authorization": f"Bearer {data['accessToken']}"}


def test_cockpit_ok(client, db_mode):
    hdr = _hdr(client, "school_admin01")
    r = client.get(f"{BASE}/stats/cockpit", headers=hdr).json()
    assert r["code"] == 0
    d = r["data"]
    assert isinstance(d["domains"], list) and len(d["domains"]) >= 4
    keys = {x["key"] for x in d["domains"]}
    assert {"aid", "funding", "discipline", "activity"} <= keys
    assert all("route" in x and "total" in x and "highlight" in x for x in d["domains"])
    assert "totals" in d and "disciplineReconcileConsistent" in d
