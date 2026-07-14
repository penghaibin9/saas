"""教学质量（/academic-affairs/quality/*）端点测试（零新表，聚合既有表）。

覆盖：质量看板指标(挂科率/预警/发布率等)、报告导出 xlsx(用途必填400 + 合法导出 PK 字节)、
导出历史、学生越权403。MySQL-only（db_mode 夹具）。口径核对施工包 §8/§9。
"""
from __future__ import annotations

BASE = "/api/v1/academic-affairs"
TID = 1000000000000000001


def _hdr(client, login_name):
    data = client.post("/api/v1/auth/mock-login",
                       json={"loginName": login_name, "password": "any"}).json()["data"]
    return {"Authorization": f"Bearer {data['accessToken']}"}


def _stu_token(real_name, student_no):
    from app.core.security import create_access_token
    return {"Authorization": "Bearer " + create_access_token({
        "userId": f"u-{student_no}", "realName": real_name, "studentNo": student_no,
        "userType": "STUDENT", "tid": "x", "tenantId": str(TID), "activeContextId": "ctx",
        "currentRoleCode": "STUDENT", "clientType": "MP"})}


def _seed(db_mode):
    from app.db.session import get_sessionmaker
    from app.models import AcademicGrade, AcademicStudent, AcademicWarning, College, StudentProfile
    db = get_sessionmaker()()
    col = College(tenant_id=TID, college_name="软件学院", status="ACTIVE")
    db.add(col); db.flush()
    s1 = StudentProfile(tenant_id=TID, student_no="QL2401", real_name="质甲", college_id=col.id,
                        student_status="NORMAL", status="ACTIVE")
    db.add(s1); db.flush()
    a1 = AcademicStudent(tenant_id=TID, student_id=s1.id, student_no="QL2401", name="质甲",
                         class_name="软件2401", college_name="软件学院")
    db.add(a1); db.flush()
    db.add_all([
        AcademicGrade(tenant_id=TID, acad_student_id=a1.id, course_name="高数", credit_value=4,
                      score=45, pass_status="FAILED", source="PUBLISH", record_status="ACTIVE"),
        AcademicGrade(tenant_id=TID, acad_student_id=a1.id, course_name="英语", credit_value=3,
                      score=80, pass_status="PASSED", source="PUBLISH", record_status="ACTIVE"),
        AcademicWarning(tenant_id=TID, acad_student_id=a1.id, warn_type="MULTI_FAIL", level="HIGH",
                        status="PENDING_HANDLE", record_status="ACTIVE"),
    ])
    db.commit()
    db.close()
    return {}


def test_q1_dashboard(client, db_mode):
    _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    r = client.get(f"{BASE}/quality/dashboard", headers=admin).json()
    assert r["code"] == 0
    keys = {i["key"] for i in r["data"]["indicators"]}
    assert "failRate" in keys and "warningCount" in keys and "gradPassRate" in keys
    fail = next(i for i in r["data"]["indicators"] if i["key"] == "failRate")
    assert fail["value"] == 50.0  # 1 挂科 / 2 总成绩
    warn = next(i for i in r["data"]["indicators"] if i["key"] == "warningCount")
    assert warn["value"] == 1


def test_q2_report_export(client, db_mode):
    _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    # 用途过短 400
    assert client.post(f"{BASE}/quality/reports/export", headers=admin, json={"purpose": "x"}).status_code == 400
    # 合法导出 → xlsx (PK 魔数)
    r = client.post(f"{BASE}/quality/reports/export", headers=admin, json={"purpose": "期末教学质量汇报"})
    assert r.status_code == 200 and r.content[:2] == b"PK"
    # 导出历史含该次
    hist = client.get(f"{BASE}/quality/reports", headers=admin).json()
    assert hist["data"]["total"] >= 1


def test_q3_student_forbidden(client, db_mode):
    _seed(db_mode)
    stu = _stu_token("质甲", "QL2401")
    assert client.get(f"{BASE}/quality/dashboard", headers=stu).status_code == 403
    assert client.post(f"{BASE}/quality/reports/export", headers=stu, json={"purpose": "越权导出测试"}).status_code == 403
