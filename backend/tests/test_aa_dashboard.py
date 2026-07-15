"""13B 教务看板（aa-dashboard）· 首页汇总 + 提醒聚合。

发现背景：`test_academic.py::test_credits_and_dashboard_audit` 打的是旧前缀
`/api/v1/academic/dashboard`（app/api/v1/academic.py，遗留模块，对应旧前端
AdminAcademicLayout/AcademicDashboardView 已不在任何路由里，orphaned），并不是
navPlan.js 里真实在用的教务看板（/academic-affairs/dashboard）。真实看板此前只有
一条 403 权限检查（test_aa_term.py），没有验证过真实返回数据，本文件补上。
"""
from __future__ import annotations

TID = 1000000000000000001
BASE = "/api/v1/academic-affairs"


def _hdr(client, login_name):
    data = client.post("/api/v1/auth/mock-login",
                       json={"loginName": login_name, "password": "any"}).json()["data"]
    return {"Authorization": f"Bearer {data['accessToken']}"}


def _seed(db_mode):
    from app.db.session import get_sessionmaker
    from app.models import AaRegistration, AaTerm, SchoolClass, StudentProfile
    db = get_sessionmaker()()
    t = AaTerm(tenant_id=TID, year_code="2026-2027", term_no=1, status="PUBLISHED", is_current=True)
    db.add(t); db.flush()
    c = SchoolClass(tenant_id=TID, major_id=1, class_name="软件2601", grade="2026", status="ACTIVE")
    db.add(c); db.flush()
    s = StudentProfile(tenant_id=TID, student_no="DB001", real_name="看板甲", class_id=c.id,
                       current_stage="ON_CAMPUS", student_status="REGISTERED", status="ACTIVE")
    db.add(s); db.flush()
    db.add(AaRegistration(tenant_id=TID, batch_id=1, student_id=s.id, status="REGISTERED"))
    db.flush()
    db.commit()
    tid = t.id
    db.close()
    return tid


def test_dashboard_summary_reflects_real_data(client, db_mode):
    _seed(db_mode)
    hdr = _hdr(client, "school_admin01")
    r = client.get(f"{BASE}/dashboard", headers=hdr)
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["currentTerm"] is not None
    cards = {c["key"]: c["value"] for c in data["summaryCards"]}
    assert cards["studentTotal"] >= 1
    assert cards["registered"] >= 1
    assert isinstance(data["moduleCards"], list) and len(data["moduleCards"]) > 0


def test_dashboard_reminders_aggregates_six_panels(client, db_mode):
    _seed(db_mode)
    hdr = _hdr(client, "school_admin01")
    r = client.get(f"{BASE}/dashboard/reminders", headers=hdr)
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    for key in ("gradeProgress", "examReminders", "statusChangeReminders",
               "warningReminders", "graduationWarnings", "todos", "generatedAt"):
        assert key in data, f"缺少面板：{key}"


def test_dashboard_student_forbidden_403(client, db_mode):
    from app.core.security import create_access_token
    stu_hdr = {"Authorization": "Bearer " + create_access_token({
        "userId": "u-db001", "realName": "看板甲", "studentNo": "DB001", "userType": "STUDENT",
        "tid": "x", "tenantId": str(TID), "activeContextId": "ctx", "currentRoleCode": "STUDENT",
        "clientType": "MP"})}
    assert client.get(f"{BASE}/dashboard", headers=stu_hdr).status_code == 403
