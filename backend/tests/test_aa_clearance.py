"""毕业清考（/academic-affairs/makeup/clearance/*）端点测试。

覆盖重点：
- 自动圈定口径：同课程按有效成绩去重后仍 FAILED 才进清考（补考/重修已通过的不再圈入）
- 全链路：建批次→扫描圈定→发布→录分→学院审核→教务回写 t_acad_grade(source=CLEARANCE, CAP60)
- 幂等重扫不重复圈入；dryRun 只看不落
- 非清考批次不可扫描(409)；无年级建批次(400)；学生越权(403)

当前生产合同要求清考批次绑定正式可写学期，候选成绩必须冻结稳定 courseId/courseCode/courseVersion/attemptNo；
本测试按该合同种真实最小事实，不恢复按课程名猜测的旧入口。
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
    """应届 2022 级学生 + 当前学期 + 稳定课程身份；仅高数有效成绩仍失败者进入清考。"""
    from app.db.session import get_sessionmaker
    from app.models import (AaCourse, AaTerm, AcademicGrade, AcademicStudent,
                            College, Major, SchoolClass, StudentProfile)
    from tests.support_grade_review_identity import seed_grade_review_identity

    db = get_sessionmaker()()
    term = AaTerm(
        tenant_id=TID, year_code="2026-2027", term_no=1,
        term_name="2026-2027第1学期", teaching_weeks=18,
        status="PUBLISHED", is_current=True,
    )
    db.add(term); db.flush()
    col = College(tenant_id=TID, college_name="软件学院", status="ACTIVE")
    db.add(col); db.flush()
    major = Major(tenant_id=TID, college_id=col.id, major_name="软件技术", status="ACTIVE")
    db.add(major); db.flush()
    klass = SchoolClass(tenant_id=TID, major_id=major.id, class_name="软件2201", grade="2022", status="ACTIVE")
    db.add(klass); db.flush()
    seed_grade_review_identity(db, college_ids=[col.id])

    math = AaCourse(
        tenant_id=TID, course_code="QK-MATH", course_name="高等数学",
        credit=4, status="ENABLED",
    )
    english = AaCourse(
        tenant_id=TID, course_code="QK-ENG", course_name="大学英语",
        credit=3, status="ENABLED",
    )
    db.add_all([math, english]); db.flush()

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

    def grade_row(acad, course, score, status, attempt_no):
        db.add(AcademicGrade(
            tenant_id=TID,
            acad_student_id=acad.id,
            course_id=course.id,
            course_code=course.course_code,
            course_version=1,
            attempt_no=attempt_no,
            course_name=course.course_name,
            credit_value=float(course.credit or 0),
            term="2026-2027-1",
            score=score,
            pass_status=status,
            source="PUBLISH",
            record_status="ACTIVE",
        ))

    grade_row(a1, math, 40, "FAILED", 1)
    grade_row(a1, math, 55, "FAILED", 2)
    grade_row(a1, english, 45, "FAILED", 1)
    grade_row(a1, english, 72, "PASSED", 2)
    grade_row(a2, math, 85, "PASSED", 1)
    grade_row(a3, math, 30, "FAILED", 1)
    db.commit()
    ids = {"a1": a1.id, "term": term.id, "math": math.id, "english": english.id}
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
    _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    bid = _create_batch(client, admin)
    d = client.post(f"{BASE}/makeup/clearance/batches/{bid}/scan?dryRun=true",
                    headers=admin).json()["data"]
    assert d["dryRun"] is True and d["candidates"] == 1, d
    it = d["items"][0]
    assert it["courseName"] == "高等数学" and it["effectiveScore"] == 55 and it["studentNo"] == "QK2201"
    assert it["identityReady"] is True
    assert all(x["courseName"] != "大学英语" for x in d["items"])
    recs = client.get(f"{BASE}/makeup/clearance/batches/{bid}/records", headers=admin).json()["data"]
    assert recs["total"] == 0


def test_scan_idempotent(client, db_mode):
    _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    bid = _create_batch(client, admin)
    d1 = client.post(f"{BASE}/makeup/clearance/batches/{bid}/scan", headers=admin).json()["data"]
    assert d1["added"] == 1
    d2 = client.post(f"{BASE}/makeup/clearance/batches/{bid}/scan", headers=admin).json()["data"]
    assert d2["added"] == 0 and d2["skipped"] == 1, "重复扫描不得重复圈入"


def test_full_chain_writes_clearance_grade(client, db_mode):
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
    assert g is not None, "必须回写 source=CLEARANCE 成绩行"
    assert g.score == 60 and g.pass_status == "PASSED", "清考通过按 CAP60 记 60 分"
    assert g.course_id == ids["math"] and g.course_code == "QK-MATH"
    db.close()


def test_scan_rejects_normal_makeup_batch(client, db_mode):
    _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    resp = client.post(f"{BASE}/makeup/batches", headers=admin,
                       json={"batchName": "普通补考批次"})
    assert resp.status_code == 200, resp.text
    bid = resp.json()["data"]["batchId"]
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
