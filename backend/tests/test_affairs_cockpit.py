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
    assert all("route" in x and "status" in x for x in d["domains"])
    assert all(x["status"] == "OK" for x in d["domains"])
    assert all(x.get("total") is not None for x in d["domains"])
    assert "totals" in d and "disciplineReconcileConsistent" in d


def test_cockpit_domain_error_no_fake_zero(client, db_mode, monkeypatch):
    """某域抛错时 status=ERROR、message=统计暂不可用，totals 不为假 0。"""
    import app.services.affairs_aid_service as aid_svc

    def _boom(_user):
        raise RuntimeError("simulated aid stats failure")

    monkeypatch.setattr(aid_svc, "aid_stats", _boom)
    hdr = _hdr(client, "school_admin01")
    r = client.get(f"{BASE}/stats/cockpit", headers=hdr).json()
    assert r["code"] == 0
    aid = next(x for x in r["data"]["domains"] if x["key"] == "aid")
    assert aid["status"] == "ERROR"
    assert aid["total"] is None
    assert aid["message"] == "统计暂不可用"
    assert r["data"]["totals"]["aidApplications"] is None
    # 其他成功域仍可正常返回数字（含 0），但失败域不得被汇总成 0
    assert any(x["status"] == "OK" for x in r["data"]["domains"] if x["key"] != "aid")
