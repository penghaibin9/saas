"""13A 学工统计端点（aid/funding/discipline stats）——结构契约 + 违纪计数反映 + 权限。

这些统计仅聚合口径（不含金额/家庭经济明细），供 D 包看板/统计页与工作台指标复用。
"""
from __future__ import annotations

TID = 1000000000000000001
BASE = "/api/v1/student-affairs"


def _hdr(client, login_name):
    data = client.post("/api/v1/auth/mock-login",
                       json={"loginName": login_name, "password": "any"}).json()["data"]
    return {"Authorization": f"Bearer {data['accessToken']}"}


def _seed(db_mode):
    from app.db.session import get_sessionmaker
    from app.models import SchoolClass, StudentProfile
    db = get_sessionmaker()()
    a = SchoolClass(tenant_id=TID, major_id=1, class_name="软件2101", grade="2021", status="ACTIVE")
    db.add(a); db.flush()
    s = StudentProfile(tenant_id=TID, student_no="A001", real_name="甲一", class_id=a.id,
                       current_stage="ORIENTATION", student_status="NORMAL", status="ACTIVE")
    db.add(s); db.flush()
    sid = s.id
    db.commit(); db.close()
    return sid


def test_aid_and_funding_stats_shape(client, db_mode):
    _seed(db_mode)
    hdr = _hdr(client, "school_admin01")
    for path, extra in [("aid", "byLevel"), ("funding", "byType")]:
        r = client.get(f"{BASE}/{path}/stats", headers=hdr)
        assert r.status_code == 200, path
        d = r.json()["data"]
        assert "total" in d and "byStatus" in d and extra in d, path
        assert isinstance(d["byStatus"], list) and isinstance(d[extra], list)


def test_discipline_stats_reflects_case(client, db_mode):
    sid = _seed(db_mode)
    hdr = _hdr(client, "school_admin01")
    reg = client.post(f"{BASE}/discipline/cases", headers=hdr, json={
        "studentId": str(sid), "discType": "WARNING", "reason": "考试违纪，情节较轻，予以处分"})
    assert reg.status_code == 200, reg.text
    r = client.get(f"{BASE}/discipline/stats", headers=hdr)
    assert r.status_code == 200
    d = r.json()["data"]
    assert d["total"] >= 1
    assert any(t["key"] == "WARNING" for t in d["byType"])
    assert "reconcile" in d and "consistent" in d["reconcile"]
