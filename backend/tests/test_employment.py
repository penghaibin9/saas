"""就业服务域测试：台账/材料/未就业帮扶/跟进/企业岗位 各闭环 + 级联停用 + 看板 + 审计。"""
from __future__ import annotations

from datetime import datetime

MAIN_TID = 1000000000000000001


def _seed(_db_mode):
    from app.db.session import get_sessionmaker
    from app.models import EmpCompany, EmpJob, EmpMaterial, EmpStudent
    db = get_sessionmaker()()
    try:
        s = EmpStudent(tenant_id=MAIN_TID, name="就业甲", student_no="2023999001", class_id="CL01",
                       class_name="软件2301班", destination_type="UNEMPLOYED", verify_status="PENDING_VERIFY",
                       material_status="SUBMITTED", help_level="NORMAL", risk_level="MEDIUM",
                       counselor="李辅导", phone_encrypted="13800008888", unemployed_reason="意向未定")
        db.add(s)
        db.flush()
        m = EmpMaterial(tenant_id=MAIN_TID, emp_student_id=s.id, material_type="OFFER",
                        file_name="录用通知.pdf", submit_time=datetime.utcnow(), status="SUBMITTED")
        c = EmpCompany(tenant_id=MAIN_TID, name="测试企业", credit_code="91330100MA27K1XX0A",
                       industry="IT", nature="民营企业", cooperation_level="深度合作", status="ACTIVE")
        db.add_all([m, c])
        db.flush()
        j = EmpJob(tenant_id=MAIN_TID, company_id=c.id, company_name="测试企业", title="前端开发",
                   headcount=3, status="OPEN", publish_time="2026-03-01")
        db.add(j)
        db.commit()
        return {"student": s.id, "material": m.id, "company": c.id, "job": j.id}
    finally:
        db.close()


def test_students_and_detail(client, auth_headers, db_mode):
    ids = _seed(db_mode)
    lst = client.get("/api/v1/employment/students", headers=auth_headers).json()
    assert lst["code"] == 0 and lst["data"]["total"] == 1
    assert lst["data"]["items"][0]["destinationLabel"] == "待就业"
    det = client.get(f"/api/v1/employment/students/{ids['student']}", headers=auth_headers).json()
    assert det["code"] == 0 and len(det["data"]["materials"]) == 1


def test_void_and_mark_destination(client, auth_headers, db_mode):
    ids = _seed(db_mode)
    bad = client.post(f"/api/v1/employment/students/{ids['student']}/void", headers=auth_headers,
                      json={"reason": "x"}).json()
    assert bad["code"] == 422001
    md = client.post("/api/v1/employment/students/mark-destination", headers=auth_headers,
                     json={"ids": [str(ids["student"])], "destinationType": "SIGNED"}).json()
    assert md["code"] == 0 and md["data"]["count"] == 1


def test_material_closed_loop(client, auth_headers, db_mode):
    ids = _seed(db_mode)
    bad = client.post(f"/api/v1/employment/materials/{ids['material']}/return", headers=auth_headers,
                      json={"reason": "x"}).json()
    assert bad["code"] == 422001
    ok = client.post(f"/api/v1/employment/materials/{ids['material']}/approve", headers=auth_headers,
                     json={}).json()
    assert ok["code"] == 0 and ok["data"]["status"] == "APPROVED"
    # 通过后学生核验状态 VERIFIED
    det = client.get(f"/api/v1/employment/students/{ids['student']}", headers=auth_headers).json()
    assert det["data"]["student"]["verifyStatus"] == "VERIFIED"


def test_unemployed_help(client, auth_headers, db_mode):
    ids = _seed(db_mode)
    un = client.get("/api/v1/employment/unemployed", headers=auth_headers).json()
    assert un["code"] == 0 and un["data"]["total"] == 1
    kh = client.post("/api/v1/employment/unemployed/mark-key-help", headers=auth_headers,
                     json={"ids": [str(ids["student"])]}).json()
    assert kh["code"] == 0
    at = client.post("/api/v1/employment/unemployed/assign-teacher", headers=auth_headers,
                     json={"ids": [str(ids["student"])], "teacher": "王就业"}).json()
    assert at["code"] == 0 and at["data"]["count"] == 1


def test_followup(client, auth_headers, db_mode):
    ids = _seed(db_mode)
    fu = client.post("/api/v1/employment/followups", headers=auth_headers,
                     json={"studentId": str(ids["student"]), "content": "电话沟通推荐岗位", "way": "PHONE"}).json()
    assert fu["code"] == 0
    # 跟进后学生 followUpCount+1
    det = client.get(f"/api/v1/employment/students/{ids['student']}", headers=auth_headers).json()
    assert det["data"]["student"]["followUpCount"] == 1


def test_company_disable_cascades_jobs(client, auth_headers, db_mode):
    ids = _seed(db_mode)
    bad = client.post(f"/api/v1/employment/companies/{ids['company']}/disable", headers=auth_headers,
                      json={"reason": "x"}).json()
    assert bad["code"] == 422001
    ok = client.post(f"/api/v1/employment/companies/{ids['company']}/disable", headers=auth_headers,
                     json={"reason": "薪资与承诺不符停用"}).json()
    assert ok["code"] == 0
    # 级联：关联岗位 CLOSED
    jobs = client.get("/api/v1/employment/jobs", headers=auth_headers).json()
    j = [x for x in jobs["data"]["items"] if x["id"] == str(ids["job"])][0]
    assert j["status"] == "CLOSED"


def test_create_company_job(client, auth_headers, db_mode):
    _seed(db_mode)
    c = client.post("/api/v1/employment/companies", headers=auth_headers,
                    json={"name": "新企业", "creditCode": "91330100MA28K2YY1B"}).json()
    assert c["code"] == 0
    j = client.post("/api/v1/employment/jobs", headers=auth_headers,
                    json={"companyId": c["data"]["id"], "title": "测试岗位", "headcount": 2}).json()
    assert j["code"] == 0


def test_dashboard_and_audit(client, auth_headers, db_mode):
    ids = _seed(db_mode)
    dash = client.get("/api/v1/employment/dashboard", headers=auth_headers).json()
    assert dash["code"] == 0 and any(k["label"] == "毕业生总数" for k in dash["data"]["kpis"])
    client.post(f"/api/v1/employment/materials/{ids['material']}/approve", headers=auth_headers, json={})
    au = client.get("/api/v1/employment/audit-logs?bizType=MATERIAL", headers=auth_headers).json()
    assert au["code"] == 0 and au["data"]["total"] >= 1


def test_requires_login(client):
    assert client.get("/api/v1/employment/dashboard").json()["code"] == 401001
