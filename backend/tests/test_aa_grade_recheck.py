"""成绩复查申请端到端（正方 学生端3.12/教师端3.11 对标）：
学生对已发布成绩发起复查 → 教务复审 维持/调整(回写t_acad_grade+刷台账+通知)/不予受理。MySQL-only。
"""
from __future__ import annotations

BASE = "/api/v1/mobile/academic"
ADMIN_BASE = "/api/v1/academic-affairs"
MAIN = 1000000000000000001


def _stu_token(real_name, student_no):
    from app.core.security import create_access_token
    return {"Authorization": "Bearer " + create_access_token({
        "userId": f"u-{student_no}", "realName": real_name, "userType": "STUDENT",
        "studentNo": student_no, "tid": "demo", "tenantId": str(MAIN),
        "activeContextId": "ctx", "currentRoleCode": "STUDENT", "clientType": "MP"})}


def _admin(client):
    data = client.post("/api/v1/auth/mock-login",
                       json={"loginName": "school_admin01", "password": "any"}).json()["data"]
    return {"Authorization": f"Bearer {data['accessToken']}"}


def _seed_student(student_no, real_name):
    from app.db.session import get_sessionmaker
    from app.models import StudentProfile
    db = get_sessionmaker()()
    db.add(StudentProfile(tenant_id=MAIN, student_no=student_no, real_name=real_name,
                          current_stage="ON_CAMPUS", student_status="NORMAL", status="ACTIVE"))
    db.commit(); db.close()


def _seed_grade(student_no, real_name, course, score):
    """建 学生档案 + 学业台账 + 已发布成绩(t_acad_grade)，返回成绩行 id。"""
    from app.db.session import get_sessionmaker
    from app.models import AcademicGrade, AcademicStudent, StudentProfile
    db = get_sessionmaker()()
    p = StudentProfile(tenant_id=MAIN, student_no=student_no, real_name=real_name,
                       current_stage="ON_CAMPUS", student_status="NORMAL", status="ACTIVE")
    db.add(p); db.flush()
    a = AcademicStudent(tenant_id=MAIN, student_id=p.id, student_no=student_no, name=real_name)
    db.add(a); db.flush()
    g = AcademicGrade(tenant_id=MAIN, acad_student_id=a.id, course_name=course, term="2026-1",
                      credit_value=4, score=score, pass_status=("PASSED" if score >= 60 else "FAILED"),
                      source="PUBLISH", record_status="ACTIVE")
    db.add(g); db.flush()
    gid = g.id
    db.commit(); db.close()
    return gid


def test_grade_recheck_full_flow(client, db_mode):
    gid = _seed_grade("RC0001", "复查甲", "高等数学", 58)  # 不及格，复查后调整为及格
    hdr = _stu_token("复查甲", "RC0001")
    # 成绩单暴露 gradeId（学生据此发起复查）
    tr = client.get(f"{BASE}/transcript/my", headers=hdr).json()["data"]
    assert any(str(i["gradeId"]) == str(gid) for i in tr["items"])
    # 理由过短 → 400
    bad = client.post(f"{BASE}/grade-recheck/submit", headers=hdr, json={"acadGradeId": str(gid), "reason": "x"})
    assert bad.status_code == 400, bad.text
    # 正常提交
    ok = client.post(f"{BASE}/grade-recheck/submit", headers=hdr,
                     json={"acadGradeId": str(gid), "reason": "卷面分疑似漏加平时分"})
    assert ok.status_code == 200, ok.text
    my = client.get(f"{BASE}/grade-recheck/my", headers=hdr).json()["data"]["items"]
    assert len(my) == 1 and my[0]["status"] == "SUBMITTED"
    rid = my[0]["recheckId"]
    # 同一成绩重复提交 → 409
    dup = client.post(f"{BASE}/grade-recheck/submit", headers=hdr,
                      json={"acadGradeId": str(gid), "reason": "重复申请应被拦"})
    assert dup.status_code == 409
    # 教务处台账可见
    admin = _admin(client)
    lst = client.get(f"{ADMIN_BASE}/grade-rechecks", headers=admin).json()["data"]
    assert any(x["recheckId"] == rid for x in lst["items"])
    # 复审调整 → 回写成绩单（58→72，不及格转及格）
    rv = client.post(f"{ADMIN_BASE}/grade-rechecks/{rid}/review", headers=admin,
                     json={"action": "ADJUST", "newScore": 72, "note": "重新核分后加平时分"})
    assert rv.status_code == 200 and rv.json()["data"]["status"] == "ADJUSTED"
    tr2 = client.get(f"{BASE}/transcript/my", headers=hdr).json()["data"]
    g2 = [i for i in tr2["items"] if str(i["gradeId"]) == str(gid)][0]
    assert g2["score"] == 72 and g2["passStatus"] == "PASSED"


def test_grade_recheck_uphold_no_change(client, db_mode):
    gid = _seed_grade("RC0010", "复查维持", "英语", 66)
    hdr = _stu_token("复查维持", "RC0010")
    rid = client.post(f"{BASE}/grade-recheck/submit", headers=hdr,
                      json={"acadGradeId": str(gid), "reason": "希望复核一下卷面"}).json()["data"]["recheckId"]
    admin = _admin(client)
    rv = client.post(f"{ADMIN_BASE}/grade-rechecks/{rid}/review", headers=admin,
                     json={"action": "UPHOLD", "note": "复核无误，维持原判"})
    assert rv.status_code == 200 and rv.json()["data"]["status"] == "UPHELD"
    tr = client.get(f"{BASE}/transcript/my", headers=hdr).json()["data"]
    assert [i for i in tr["items"] if str(i["gradeId"]) == str(gid)][0]["score"] == 66  # 未变


def test_grade_recheck_cross_student_forbidden(client, db_mode):
    gid = _seed_grade("RC0020", "复查乙", "语文", 80)
    _seed_student("RC0021", "复查丙")
    r = client.post(f"{BASE}/grade-recheck/submit", headers=_stu_token("复查丙", "RC0021"),
                    json={"acadGradeId": str(gid), "reason": "试图复查别人的成绩"})
    assert r.status_code != 200  # 只能复查本人成绩
