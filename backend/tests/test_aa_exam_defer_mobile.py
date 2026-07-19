"""教务/学工中心 · 移动端缓考审批（新聚合 affairs_academic_defer_pending，覆盖 COUNSELOR/
ACADEMIC_TEACHER 两个节点身份）。全部经 HTTP client 走真库(db_mode)。PC 端既有
test_aa_exam.py 已覆盖 defer_review 本身节点级范围收敛（e14/e15/e16 三处 403）；本文件
专门覆盖移动端「待我审批」聚合（PC 端 defer_list 本身对非学生模式无范围过滤，返回全校
数据，不能直接复用，此前完全没有测试覆盖这道自建过滤），以及移动端审批全链路。
"""
from __future__ import annotations

MOB = "/api/v1/mobile"
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
    """1 班 1 生 + 教学任务 teacher_key=academic01（供 TEACHER_CONFIRM 节点）+
    counselor01 的 TeacherStudentScope（供 COUNSELOR_REVIEW 节点）。"""
    from app.db.session import get_sessionmaker
    from app.models import (AaCourse, AaTeachingTask, AaTeachingTaskBatch, AaTerm, College, Major,
                            SchoolClass, StudentProfile, TeacherStudentScope)
    db = get_sessionmaker()()
    term = AaTerm(tenant_id=TID, year_code="2030-2031", term_no=1, status="PUBLISHED", is_current=True)
    db.add(term); db.flush()
    col = College(tenant_id=TID, college_name="软件学院", status="ACTIVE")
    db.add(col); db.flush()
    major = Major(tenant_id=TID, college_id=col.id, major_name="软件技术", status="ACTIVE")
    db.add(major); db.flush()
    klass = SchoolClass(tenant_id=TID, major_id=major.id, class_name="软件3001", grade="2030", status="ACTIVE")
    db.add(klass); db.flush()
    co = AaCourse(tenant_id=TID, course_code="MOB_DEFER", course_name="移动缓考测试课", credit=3, status="ENABLED")
    db.add(co); db.flush()
    tb = AaTeachingTaskBatch(tenant_id=TID, term_id=term.id, batch_name="移动缓考测试任务批",
                             college_id=col.id, status="ACTIVE")
    db.add(tb); db.flush()
    tt = AaTeachingTask(tenant_id=TID, batch_id=tb.id, course_id=co.id, course_name="移动缓考测试课",
                        class_id=klass.id, teaching_class_name="软件3001",
                        teacher_key="academic01", teacher_name="赵敏")
    db.add(tt); db.flush()
    s = StudentProfile(tenant_id=TID, student_no="MD3001", real_name="缓考甲", college_id=col.id,
                       major_id=major.id, class_id=klass.id, grade="2030", student_status="NORMAL", status="ACTIVE")
    db.add(s); db.flush()
    db.add(TeacherStudentScope(tenant_id=TID, teacher_key="counselor01", teacher_name="王莉",
                               role_code="COUNSELOR", scope_type="CLASS", ref_value="软件3001",
                               status="ACTIVE"))
    db.commit()
    ids = {"tt": tt.id, "student": s.id, "studentNo": s.student_no}
    db.close()
    return ids


def _batch_with_confirmed_course(client, admin, tt_id):
    bid = client.post(f"{BASE}/exam/batches", headers=admin, json={"batchName": "移动缓考测试批次"}).json()["data"]["batchId"]
    cid = client.post(f"{BASE}/exam/batches/{bid}/courses", headers=admin,
                      json={"teachingTaskId": str(tt_id)}).json()["data"]["examCourseId"]
    client.post(f"{BASE}/exam/courses/{cid}/confirm", headers=admin, json={"action": "CONFIRM"})
    client.put(f"{BASE}/exam/courses/{cid}/schedule", headers=admin,
               json={"examDate": "2031-06-20", "startTime": "09:00", "endTime": "11:00", "durationMinutes": 120})
    client.post(f"{BASE}/exam/batches/{bid}/confirm-courses", headers=admin)
    return bid, cid


def _apply_defer(client, ids, cid):
    stu = _stu_token("缓考甲", ids["studentNo"])
    r = client.post(f"{BASE}/deferred-exams", headers=stu,
                    json={"examCourseId": str(cid), "reasonType": "SICK", "reason": "住院治疗"})
    return r.json()["data"]["deferId"]


def test_defer_pending_counselor_scope_via_mobile(client, db_mode):
    """COUNSELOR_REVIEW 节点「待我审批」聚合：counselor01（已授权该班）可见；
    无授权的其他辅导员看不到（PC defer_list 本身不做此过滤，纯靠移动端新聚合）。"""
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    _, cid = _batch_with_confirmed_course(client, admin, ids["tt"])
    did = _apply_defer(client, ids, cid)

    mine = client.get(f"{MOB}/teacher/academic/defer/pending", headers=_hdr(client, "counselor01")).json()
    assert mine["code"] == 0
    assert any(d["deferId"] == did for d in mine["data"]["list"])


def test_defer_review_counselor_flow_via_mobile(client, db_mode):
    """辅导员移动端通过 → 状态推进 TEACHER_CONFIRM，且推进后不再出现在辅导员自己的待办里。"""
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    _, cid = _batch_with_confirmed_course(client, admin, ids["tt"])
    did = _apply_defer(client, ids, cid)
    hdr = _hdr(client, "counselor01")

    r = client.post(f"{MOB}/teacher/academic/defer/{did}/review", headers=hdr, json={"action": "APPROVE"})
    assert r.status_code == 200 and r.json()["data"]["status"] == "TEACHER_CONFIRM"

    after = client.get(f"{MOB}/teacher/academic/defer/pending", headers=hdr).json()["data"]["list"]
    assert not any(d["deferId"] == did for d in after)


def test_defer_pending_teacher_scope_via_mobile(client, db_mode):
    """TEACHER_CONFIRM 节点「待我审批」聚合：academic01（本人授课）可见；
    无关教师（teacher01）看不到。"""
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    _, cid = _batch_with_confirmed_course(client, admin, ids["tt"])
    did = _apply_defer(client, ids, cid)
    client.post(f"{MOB}/teacher/academic/defer/{did}/review", headers=_hdr(client, "counselor01"),
               json={"action": "APPROVE"})

    mine = client.get(f"{MOB}/teacher/academic/defer/pending", headers=_hdr(client, "academic01")).json()
    assert any(d["deferId"] == did for d in mine["data"]["list"])

    other = client.get(f"{MOB}/teacher/academic/defer/pending", headers=_hdr(client, "teacher01")).json()
    assert not any(d["deferId"] == did for d in other["data"]["list"])


def test_defer_review_teacher_flow_and_return_validation_via_mobile(client, db_mode):
    """任课教师移动端通过 → COLLEGE_REVIEW；退回原因 <5 字 400。"""
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    _, cid = _batch_with_confirmed_course(client, admin, ids["tt"])
    did = _apply_defer(client, ids, cid)
    client.post(f"{MOB}/teacher/academic/defer/{did}/review", headers=_hdr(client, "counselor01"),
               json={"action": "APPROVE"})
    hdr = _hdr(client, "academic01")

    bad = client.post(f"{MOB}/teacher/academic/defer/{did}/review", headers=hdr,
                      json={"action": "RETURN", "reason": "太短"})
    assert bad.status_code == 400

    ok = client.post(f"{MOB}/teacher/academic/defer/{did}/review", headers=hdr, json={"action": "APPROVE"})
    assert ok.status_code == 200 and ok.json()["data"]["status"] == "COLLEGE_REVIEW"


def test_cross_node_review_403_via_mobile(client, db_mode):
    """越权：非本人授课教师在 TEACHER_CONFIRM 节点审批 → 403（复用 PC defer_review 内部
    _check_defer_scope，与 PC 端 e14 同一断言，经 mobile 路径复测）。"""
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    _, cid = _batch_with_confirmed_course(client, admin, ids["tt"])
    did = _apply_defer(client, ids, cid)
    client.post(f"{MOB}/teacher/academic/defer/{did}/review", headers=_hdr(client, "counselor01"),
               json={"action": "APPROVE"})

    r = client.post(f"{MOB}/teacher/academic/defer/{did}/review", headers=_hdr(client, "teacher01"),
                    json={"action": "APPROVE"})
    assert r.status_code == 403
