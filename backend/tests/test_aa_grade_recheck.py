"""成绩复查申请端到端（正方 学生端3.12/教师端3.11 对标）。

学生对已发布正式成绩发起复查 → 教务复审维持/调整。ADJUST 必须消费真实学期、发布任务、
稳定课程身份和冻结有效成绩策略；旧的裸 AcademicGrade fixture 已不能代表可安全更正的正式成绩。
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
    """种一条真正可复查的正式成绩：学期/任务/课程身份/有效成绩策略快照齐全。"""
    from app.db.session import get_sessionmaker
    from app.models import (AaCourse, AaEffectiveGradePolicy, AaGradeTask, AaTerm,
                            AcademicGrade, AcademicStudent, StudentProfile)

    db = get_sessionmaker()()
    term = AaTerm(
        tenant_id=MAIN, year_code="2026-2027", term_no=1,
        term_name="2026-2027第1学期", status="PUBLISHED", is_current=True,
    )
    db.add(term); db.flush()
    policy = AaEffectiveGradePolicy(
        tenant_id=MAIN, policy_code="RC_POLICY", policy_version=1,
        attempt_strategy="LATEST_ATTEMPT", effective_from_term_id=term.id,
        active_scope_key=str(term.id), status="ACTIVE",
    )
    db.add(policy); db.flush()
    course_row = AaCourse(
        tenant_id=MAIN, course_code=f"RC-{student_no}", course_name=course,
        credit=4, status="ENABLED",
    )
    db.add(course_row); db.flush()
    profile = StudentProfile(
        tenant_id=MAIN, student_no=student_no, real_name=real_name,
        current_stage="ON_CAMPUS", student_status="NORMAL", status="ACTIVE",
    )
    db.add(profile); db.flush()
    acad = AcademicStudent(
        tenant_id=MAIN, student_id=profile.id, student_no=student_no, name=real_name,
    )
    db.add(acad); db.flush()
    task = AaGradeTask(
        tenant_id=MAIN, term_id=term.id, term_code="2026-2027-1",
        course_id=course_row.id, course_name=course, credit=4,
        usual_ratio=30, final_ratio=70, pass_line=60, status="PUBLISHED",
    )
    db.add(task); db.flush()
    grade = AcademicGrade(
        tenant_id=MAIN,
        acad_student_id=acad.id,
        course_id=course_row.id,
        course_code=course_row.course_code,
        course_version=int(course_row.version or 1),
        attempt_no=1,
        course_name=course,
        term="2026-2027-1",
        grade_task_id=task.id,
        pass_line_snapshot=60,
        effective_policy_code="RC_POLICY",
        effective_policy_version=1,
        effective_attempt_strategy="LATEST_ATTEMPT",
        credit_value=4,
        score=score,
        pass_status=("PASSED" if score >= 60 else "FAILED"),
        source="PUBLISH",
        record_status="ACTIVE",
    )
    db.add(grade); db.flush()
    gid = int(grade.id)
    db.commit(); db.close()
    return gid


def test_grade_recheck_full_flow(client, db_mode):
    gid = _seed_grade("RC0001", "复查甲", "高等数学", 58)
    hdr = _stu_token("复查甲", "RC0001")
    tr = client.get(f"{BASE}/transcript/my", headers=hdr).json()["data"]
    assert any(str(i["gradeId"]) == str(gid) for i in tr["items"])

    bad = client.post(f"{BASE}/grade-recheck/submit", headers=hdr,
                      json={"acadGradeId": str(gid), "reason": "x"})
    assert bad.status_code == 400, bad.text
    ok = client.post(f"{BASE}/grade-recheck/submit", headers=hdr,
                     json={"acadGradeId": str(gid), "reason": "卷面分疑似漏加平时分"})
    assert ok.status_code == 200, ok.text
    my = client.get(f"{BASE}/grade-recheck/my", headers=hdr).json()["data"]["items"]
    assert len(my) == 1 and my[0]["status"] == "SUBMITTED"
    rid = my[0]["recheckId"]

    dup = client.post(f"{BASE}/grade-recheck/submit", headers=hdr,
                      json={"acadGradeId": str(gid), "reason": "重复申请应被拦"})
    assert dup.status_code == 409

    admin = _admin(client)
    lst = client.get(f"{ADMIN_BASE}/grade-rechecks", headers=admin).json()["data"]
    assert any(x["recheckId"] == rid for x in lst["items"])
    rv = client.post(f"{ADMIN_BASE}/grade-rechecks/{rid}/review", headers=admin,
                     json={"action": "ADJUST", "newScore": 72, "note": "重新核分后加平时分"})
    assert rv.status_code == 200 and rv.json()["data"]["status"] == "ADJUSTED", rv.text

    # ADJUST 是 append-only：旧成绩退位，成绩单应展示新的 RECHECK 版本而不是沿用旧 gradeId。
    tr2 = client.get(f"{BASE}/transcript/my", headers=hdr).json()["data"]
    current = [i for i in tr2["items"] if i["courseName"] == "高等数学"]
    assert len(current) == 1
    assert current[0]["score"] == 72 and current[0]["passStatus"] == "PASSED"
    assert current[0]["source"] == "RECHECK" and str(current[0]["gradeId"]) != str(gid)


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
    assert [i for i in tr["items"] if str(i["gradeId"]) == str(gid)][0]["score"] == 66


def test_grade_recheck_cross_student_forbidden(client, db_mode):
    gid = _seed_grade("RC0020", "复查乙", "语文", 80)
    _seed_student("RC0021", "复查丙")
    r = client.post(f"{BASE}/grade-recheck/submit", headers=_stu_token("复查丙", "RC0021"),
                    json={"acadGradeId": str(gid), "reason": "试图复查别人的成绩"})
    assert r.status_code != 200
