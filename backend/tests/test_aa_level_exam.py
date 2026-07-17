"""等级考务（/academic-affairs/level-exams*）端点测试。

覆盖：建考→开放→学生报名/取消/复报→缴费确认→截止→成绩录入（合格线自动判定/结论直录+证书号）
→完成（未录全禁止）；重复报名 409；未截止录分 409；学生越权管理 403。

MySQL-only（db_mode 夹具）。
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
    from app.models import College, Major, SchoolClass, StudentProfile
    db = get_sessionmaker()()
    col = College(tenant_id=TID, college_name="软件学院", status="ACTIVE")
    db.add(col); db.flush()
    major = Major(tenant_id=TID, college_id=col.id, major_name="软件技术", status="ACTIVE")
    db.add(major); db.flush()
    klass = SchoolClass(tenant_id=TID, major_id=major.id, class_name="软件2401", grade="2024", status="ACTIVE")
    db.add(klass); db.flush()
    for no, name in (("DJ2401", "级甲"), ("DJ2402", "级乙")):
        db.add(StudentProfile(tenant_id=TID, student_no=no, real_name=name, college_id=col.id,
                              major_id=major.id, class_id=klass.id, grade="2024",
                              student_status="NORMAL", status="ACTIVE"))
    db.commit(); db.close()


def _mk_exam(client, admin, pass_line=425):
    eid = client.post(f"{BASE}/level-exams", headers=admin,
                      json={"examName": "大学英语四级(2025-06)", "category": "CET",
                            "level": "四级", "fee": 30, "passLine": pass_line}).json()["data"]["examId"]
    client.post(f"{BASE}/level-exams/{eid}/transition?action=OPEN", headers=admin)
    return eid


def test_full_chain_scoreline_judgement(client, db_mode):
    """报名→缴费确认→截止→录 430 分（线 425）→PASS+证书号→完成。"""
    _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    eid = _mk_exam(client, admin)
    stu = _stu_token("级甲", "DJ2401")
    assert client.post(f"{BASE}/level-exams/{eid}/register", headers=stu).status_code == 200
    regs = client.get(f"{BASE}/level-exams/{eid}/registrations", headers=admin).json()["data"]["items"]
    rid = regs[0]["regId"]
    assert regs[0]["feeStatus"] == "UNPAID"
    assert client.post(f"{BASE}/level-exam-regs/{rid}/confirm-fee", headers=admin).status_code == 200
    # 未截止不可录分
    assert client.post(f"{BASE}/level-exam-regs/{rid}/result", headers=admin,
                       json={"score": 430}).status_code == 409
    client.post(f"{BASE}/level-exams/{eid}/transition?action=CLOSE", headers=admin)
    r = client.post(f"{BASE}/level-exam-regs/{rid}/result", headers=admin,
                    json={"score": 430, "certNo": "CET4-2025-001"})
    assert r.status_code == 200, r.text
    d = r.json()["data"]
    assert d["result"] == "PASS" and d["certNo"] == "CET4-2025-001", "合格线判定必须自动 PASS"
    assert client.post(f"{BASE}/level-exams/{eid}/transition?action=FINISH", headers=admin).status_code == 200


def test_fail_below_passline_and_finish_gate(client, db_mode):
    _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    eid = _mk_exam(client, admin)
    for no, name in (("DJ2401", "级甲"), ("DJ2402", "级乙")):
        client.post(f"{BASE}/level-exams/{eid}/register", headers=_stu_token(name, no))
    client.post(f"{BASE}/level-exams/{eid}/transition?action=CLOSE", headers=admin)
    regs = client.get(f"{BASE}/level-exams/{eid}/registrations", headers=admin).json()["data"]["items"]
    # 只录一人 → FINISH 409
    r1 = client.post(f"{BASE}/level-exam-regs/{regs[0]['regId']}/result", headers=admin,
                     json={"score": 300}).json()["data"]
    assert r1["result"] == "FAIL" and r1["certNo"] is None
    assert client.post(f"{BASE}/level-exams/{eid}/transition?action=FINISH",
                       headers=admin).status_code == 409, "未录全不得完成"


def test_register_dup_cancel_rereg(client, db_mode):
    _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    eid = _mk_exam(client, admin)
    stu = _stu_token("级甲", "DJ2401")
    assert client.post(f"{BASE}/level-exams/{eid}/register", headers=stu).status_code == 200
    assert client.post(f"{BASE}/level-exams/{eid}/register", headers=stu).status_code == 409
    assert client.post(f"{BASE}/level-exams/{eid}/cancel", headers=stu).status_code == 200
    assert client.post(f"{BASE}/level-exams/{eid}/register", headers=stu).status_code == 200, "取消后可复报"
    my = client.get(f"{BASE}/level-exams/my", headers=stu).json()["data"]["items"]
    assert len(my) == 1 and my[0]["status"] == "REGISTERED", "复报必须复用同一行"


def test_student_forbidden_manage(client, db_mode):
    _seed(db_mode)
    stu = _stu_token("级甲", "DJ2401")
    assert client.post(f"{BASE}/level-exams", headers=stu,
                       json={"examName": "越权考试"}).status_code == 403
