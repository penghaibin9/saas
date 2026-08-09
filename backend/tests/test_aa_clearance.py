"""毕业清考（/academic-affairs/makeup/clearance/*）端点测试。

覆盖重点：
- 自动圈定口径：按正式课程身份 + 冻结有效成绩策略解析后仍 FAILED 才进清考
- 全链路：建批次→扫描圈定→发布→录分→学院审核→教务回写 t_acad_grade(source=CLEARANCE, CAP60)
- 幂等重扫不重复圈入；dryRun 只看不落
- 非清考批次不可扫描(409)；无年级建批次(400)；学生越权(403)

MySQL-only（db_mode 夹具）。
"""
from __future__ import annotations

from datetime import datetime

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


def _ensure_grade_policy(db):
    """正式成绩写入必须有 ACTIVE 策略；测试显式建立当前租户基线策略。"""
    from app.models.academic_affairs_effective_grade import AaEffectiveGradePolicy

    row = db.query(AaEffectiveGradePolicy).filter(
        AaEffectiveGradePolicy.tenant_id == TID,
        AaEffectiveGradePolicy.status == "ACTIVE",
        AaEffectiveGradePolicy.is_deleted.is_(False),
    ).first()
    if row:
        return row
    row = AaEffectiveGradePolicy(
        tenant_id=TID,
        policy_code="CLEARANCE_TEST_POLICY",
        policy_version=1,
        active_scope_key="BASE",
        attempt_strategy="HIGHEST_SCORE",
        makeup_strategy="CAP_AND_OVERRIDE",
        makeup_cap=60,
        retake_strategy="REPLACE_IF_PASSED",
        recognition_priority=75,
        effective_from_term_id=None,
        status="ACTIVE",
    )
    db.add(row)
    db.flush()
    return row


def _ensure_current_term(db):
    from app.models import AaTerm

    term = db.query(AaTerm).filter(
        AaTerm.tenant_id == TID,
        AaTerm.is_current.is_(True),
        AaTerm.is_deleted.is_(False),
    ).first()
    if term:
        return term
    term = AaTerm(
        tenant_id=TID,
        year_code="2026-2027",
        term_no=1,
        term_name="2026-2027第1学期",
        start_date=datetime(2026, 9, 1),
        end_date=datetime(2027, 1, 15),
        status="PUBLISHED",
        is_current=True,
    )
    db.add(term)
    db.flush()
    return term


def _seed(db_mode):
    """应届 2022 级学生：甲=高数按 HIGHEST_SCORE 仍 FAILED；英语重修后 PASSED；
    乙=全部通过；丙=2023 级 FAILED（年级不符）。成绩均带稳定课程身份与策略快照。"""
    from app.db.session import get_sessionmaker
    from app.models import AcademicGrade, AcademicStudent, College, Major, SchoolClass, StudentProfile

    db = get_sessionmaker()()
    term = _ensure_current_term(db)
    policy = _ensure_grade_policy(db)

    col = College(tenant_id=TID, college_name="软件学院", status="ACTIVE")
    db.add(col); db.flush()
    major = Major(tenant_id=TID, college_id=col.id, major_name="软件技术", status="ACTIVE")
    db.add(major); db.flush()
    klass = SchoolClass(tenant_id=TID, major_id=major.id, class_name="软件2201", grade="2022", status="ACTIVE")
    db.add(klass); db.flush()

    def mk_student(no, name, grade):
        p = StudentProfile(tenant_id=TID, student_no=no, real_name=name, college_id=col.id,
                           major_id=major.id, class_id=klass.id, grade=grade,
                           student_status="NORMAL", status="ACTIVE")
        db.add(p); db.flush()
        a = AcademicStudent(tenant_id=TID, student_no=no, name=name, student_id=p.id,
                            class_name="软件2201", record_status="ACTIVE")
        db.add(a); db.flush()
        return p, a

    _p1, a1 = mk_student("QK2201", "清甲", "2022")
    _p2, a2 = mk_student("QK2202", "清乙", "2022")
    _p3, a3 = mk_student("QK2301", "非应届", "2023")

    term_code = f"{term.year_code}-{term.term_no}"

    def grade_row(acad, course_name, course_id, course_code, score, status, attempt_no):
        db.add(AcademicGrade(
            tenant_id=TID,
            acad_student_id=acad.id,
            course_id=course_id,
            course_code=course_code,
            course_version=1,
            attempt_no=attempt_no,
            course_name=course_name,
            term=term_code,
            nature="REQUIRED",
            credit_value=3,
            score=score,
            pass_status=status,
            exam_type="FINAL",
            source="PUBLISH",
            record_status="ACTIVE",
            effective_policy_code=policy.policy_code,
            effective_policy_version=policy.policy_version,
            effective_attempt_strategy=policy.attempt_strategy,
            pass_line_snapshot=60,
        ))

    grade_row(a1, "高等数学", 101, "QK-MATH", 40, "FAILED", 1)
    grade_row(a1, "高等数学", 101, "QK-MATH", 55, "FAILED", 2)   # 最高 55 仍挂 → 圈入
    grade_row(a1, "大学英语", 102, "QK-ENG", 45, "FAILED", 1)
    grade_row(a1, "大学英语", 102, "QK-ENG", 72, "PASSED", 2)   # 重修已过 → 不圈
    grade_row(a2, "高等数学", 101, "QK-MATH", 85, "PASSED", 1)   # 全过 → 不圈
    grade_row(a3, "高等数学", 101, "QK-MATH", 30, "FAILED", 1)   # 2023 级 → 年级不符不圈
    db.commit()
    ids = {"a1": a1.id}
    db.close()
    return ids


def _create_batch(client, admin, grades=("2022",)):
    r = client.post(f"{BASE}/makeup/clearance/batches", headers=admin,
                    json={"batchName": "2022届毕业清考", "targetGrades": list(grades)})
    assert r.status_code == 200, r.text
    return r.json()["data"]["batchId"]


def test_create_requires_grades(client, db_mode):
    admin = _hdr(client, "school_admin01")
    r = client.post(f"{BASE}/makeup/clearance/batches", headers=admin,
                    json={"batchName": "无年级批次", "targetGrades": []})
    assert r.status_code in (400, 422), r.text


def test_scan_scope_and_dedup_rule(client, db_mode):
    """圈定口径：只有正式策略解析后仍 FAILED 的应届课程进名单。"""
    _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    bid = _create_batch(client, admin)
    d = client.post(f"{BASE}/makeup/clearance/batches/{bid}/scan?dryRun=true",
                    headers=admin).json()["data"]
    assert d["dryRun"] is True and d["candidates"] == 1, d
    assert d["identityDebtCount"] == 0, d
    it = d["items"][0]
    assert it["courseName"] == "高等数学" and it["effectiveScore"] == 55 and it["studentNo"] == "QK2201"
    assert it["courseCode"] == "QK-MATH" and it["attemptNo"] == 2 and it["identityReady"] is True
    # 英语（重修已过）、乙（全过）、2023级 均不得出现
    assert all(x["courseName"] != "大学英语" for x in d["items"])
    # dryRun 未落库
    recs = client.get(f"{BASE}/makeup/clearance/batches/{bid}/records", headers=admin).json()["data"]
    assert recs["total"] == 0


def test_scan_idempotent(client, db_mode):
    _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    bid = _create_batch(client, admin)
    d1 = client.post(f"{BASE}/makeup/clearance/batches/{bid}/scan", headers=admin).json()["data"]
    assert d1["added"] == 1 and d1["identityDebtCount"] == 0
    d2 = client.post(f"{BASE}/makeup/clearance/batches/{bid}/scan", headers=admin).json()["data"]
    assert d2["added"] == 0 and d2["skipped"] == 1, "重复扫描不得重复圈入"


def test_full_chain_writes_clearance_grade(client, db_mode):
    """录 88 分 → CAP60 回写 60 PASSED（source=CLEARANCE），且保留正式课程身份。"""
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    bid = _create_batch(client, admin)
    scan = client.post(f"{BASE}/makeup/clearance/batches/{bid}/scan", headers=admin)
    assert scan.status_code == 200, scan.text
    recs = client.get(f"{BASE}/makeup/clearance/batches/{bid}/records", headers=admin).json()["data"]
    mid = recs["items"][0]["makeupId"]
    assert client.post(f"{BASE}/makeup/batches/{bid}/publish", headers=admin).status_code == 200
    assert client.post(f"{BASE}/makeup/records/{mid}/score", headers=admin,
                       json={"score": 88}).status_code == 200
    assert client.post(f"{BASE}/makeup/batches/{bid}/college-review", headers=admin).status_code == 200
    r = client.post(f"{BASE}/makeup/batches/{bid}/finish", headers=admin)
    assert r.status_code == 200, r.text
    from app.db.session import get_sessionmaker
    from app.models import AcademicGrade
    db = get_sessionmaker()()
    g = db.query(AcademicGrade).filter(AcademicGrade.acad_student_id == ids["a1"],
                                       AcademicGrade.source == "CLEARANCE").first()
    db.close()
    assert g is not None, "必须回写 source=CLEARANCE 成绩行"
    assert g.score == 60 and g.pass_status == "PASSED", "清考通过按 CAP60 记 60 分"
    assert g.course_id == 101 and g.course_code == "QK-MATH" and g.attempt_no == 2


def test_scan_rejects_normal_makeup_batch(client, db_mode):
    _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    created = client.post(f"{BASE}/makeup/batches", headers=admin,
                          json={"batchName": "普通补考批次"})
    assert created.status_code == 200, created.text
    bid = created.json()["data"]["batchId"]
    r = client.post(f"{BASE}/makeup/clearance/batches/{bid}/scan", headers=admin)
    assert r.status_code == 409, r.text


def test_kind_filter_in_batch_list(client, db_mode):
    _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    _create_batch(client, admin)
    regular = client.post(f"{BASE}/makeup/batches", headers=admin, json={"batchName": "普通补考"})
    assert regular.status_code == 200, regular.text
    d = client.get(f"{BASE}/makeup/batches?kind=CLEARANCE", headers=admin).json()["data"]
    assert d["total"] == 1 and d["items"][0]["kind"] == "CLEARANCE"


def test_student_forbidden(client, db_mode):
    _seed(db_mode)
    r = client.post(f"{BASE}/makeup/clearance/batches", headers=_stu_token("清甲", "QK2201"),
                    json={"batchName": "越权", "targetGrades": ["2022"]})
    assert r.status_code == 403, r.text
