"""成绩认定/课程替代（/academic-affairs/grade-recognitions*）端点测试。

覆盖：学生自助提交→教务审核通过→写 t_acad_grade(source=RECOGNIZED)+台账刷新（学分绩点即时生效）；
原成绩<60 拦截；同目标课程在途重复 409；目标课程已通过 409；驳回原因≥5字；学生越权审核 403。

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
    from app.models import AcademicGrade, AcademicStudent, College, Major, SchoolClass, StudentProfile
    db = get_sessionmaker()()
    col = College(tenant_id=TID, college_name="软件学院", status="ACTIVE")
    db.add(col); db.flush()
    major = Major(tenant_id=TID, college_id=col.id, major_name="软件技术", status="ACTIVE")
    db.add(major); db.flush()
    klass = SchoolClass(tenant_id=TID, major_id=major.id, class_name="软件2401", grade="2024", status="ACTIVE")
    db.add(klass); db.flush()
    p = StudentProfile(tenant_id=TID, student_no="RN2401", real_name="认甲", college_id=col.id,
                       major_id=major.id, class_id=klass.id, grade="2024",
                       student_status="NORMAL", status="ACTIVE")
    db.add(p); db.flush()
    a = AcademicStudent(tenant_id=TID, student_no="RN2401", name="认甲", student_id=p.id,
                        class_name="软件2401", record_status="ACTIVE")
    db.add(a); db.flush()
    # 已通过课程（用于"目标已通过 409"用例）
    db.add(AcademicGrade(tenant_id=TID, acad_student_id=a.id, course_name="大学英语",
                         score=80, credit_value=3, pass_status="PASSED", record_status="ACTIVE"))
    db.commit()
    ids = {"profile": p.id, "acad": a.id}
    db.close()
    return ids


_BODY = {"sourceCourseName": "高等数学A", "sourceScore": 82, "sourceCredit": 4,
         "sourceOrigin": "原电子信息专业", "targetCourseName": "高等数学", "reason": "转专业课程替代"}


def test_full_chain_recognized_grade_and_aggregates(client, db_mode):
    ids = _seed(db_mode)
    stu = _stu_token("认甲", "RN2401")
    admin = _hdr(client, "school_admin01")
    r = client.post(f"{BASE}/grade-recognitions/student/submit", headers=stu, json=_BODY)
    assert r.status_code == 200, r.text
    rid = r.json()["data"]["recognitionId"]
    rr = client.post(f"{BASE}/grade-recognitions/{rid}/review", headers=admin,
                     json={"action": "APPROVE"})
    assert rr.status_code == 200, rr.text
    from app.db.session import get_sessionmaker
    from app.models import AcademicGrade, AcademicStudent
    db = get_sessionmaker()()
    g = db.query(AcademicGrade).filter(AcademicGrade.acad_student_id == ids["acad"],
                                       AcademicGrade.source == "RECOGNIZED").first()
    a = db.get(AcademicStudent, ids["acad"])
    db.close()
    assert g is not None and g.course_name == "高等数学" and g.score == 82 and g.pass_status == "PASSED"
    # 台账即时刷新：认定4学分 + 原有英语3学分 = 7；学分加权绩点 (3.2*4 + 3.0*3)/7
    assert float(a.obtained_credits) == 7.0, a.obtained_credits
    assert abs(float(a.gpa) - round((3.2 * 4 + 3.0 * 3) / 7, 2)) < 0.01, a.gpa


def test_fail_score_rejected(client, db_mode):
    _seed(db_mode)
    stu = _stu_token("认甲", "RN2401")
    body = dict(_BODY, sourceScore=55)
    r = client.post(f"{BASE}/grade-recognitions/student/submit", headers=stu, json=body)
    assert r.status_code == 400, r.text


def test_duplicate_pending_409(client, db_mode):
    _seed(db_mode)
    stu = _stu_token("认甲", "RN2401")
    assert client.post(f"{BASE}/grade-recognitions/student/submit", headers=stu, json=_BODY).status_code == 200
    r = client.post(f"{BASE}/grade-recognitions/student/submit", headers=stu, json=_BODY)
    assert r.status_code == 409, r.text


def test_target_already_passed_409(client, db_mode):
    _seed(db_mode)
    stu = _stu_token("认甲", "RN2401")
    body = dict(_BODY, targetCourseName="大学英语")
    r = client.post(f"{BASE}/grade-recognitions/student/submit", headers=stu, json=body)
    assert r.status_code == 409, r.text


def test_reject_requires_reason_and_student_forbidden(client, db_mode):
    _seed(db_mode)
    stu = _stu_token("认甲", "RN2401")
    admin = _hdr(client, "school_admin01")
    rid = client.post(f"{BASE}/grade-recognitions/student/submit", headers=stu,
                      json=_BODY).json()["data"]["recognitionId"]
    assert client.post(f"{BASE}/grade-recognitions/{rid}/review", headers=admin,
                       json={"action": "REJECT", "reason": "短"}).status_code == 400
    assert client.post(f"{BASE}/grade-recognitions/{rid}/review", headers=stu,
                       json={"action": "APPROVE"}).status_code == 403
    assert client.post(f"{BASE}/grade-recognitions/{rid}/review", headers=admin,
                       json={"action": "REJECT", "reason": "原课程大纲学时不足，不予认定"}).status_code == 200


def test_target_course_picker_and_attachment(client, db_mode):
    """课程库选择器(targetCourseId→快照名) + 佐证附件(校验 FileObject);无效附件拦截。"""
    _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    from app.db.session import get_sessionmaker
    from app.models import AaCourse, FileObject
    db = get_sessionmaker()()
    c = AaCourse(tenant_id=TID, course_code="TGT001", course_name="高等数学", credit=4, status="ENABLED")
    db.add(c); db.flush()
    f = FileObject(tenant_id=TID, file_key="k/1.pdf", file_name="成绩证明.pdf", biz_type="ATTACHMENT", status="STORED")
    db.add(f); db.flush()
    cid, fid = c.id, f.id
    db.commit(); db.close()
    # 无效附件 → 拦截
    bad = client.post(f"{BASE}/grade-recognitions", headers=admin,
                      json={"studentNo": "RN2401", "sourceCourseName": "高数A", "sourceScore": 82,
                            "targetCourseId": str(cid), "attachmentFileIds": ["999999"]})
    assert bad.status_code == 400, bad.text
    # 有效:选择器取快照名 + 真附件
    ok = client.post(f"{BASE}/grade-recognitions", headers=admin,
                     json={"studentNo": "RN2401", "sourceCourseName": "高数A", "sourceScore": 82,
                           "sourceCredit": 4, "targetCourseId": str(cid), "attachmentFileIds": [str(fid)]})
    assert ok.status_code == 200, ok.text
    d = ok.json()["data"]
    assert d["targetCourseName"] == "高等数学"
    assert d["targetCourseId"] == str(cid)
    assert d["attachmentFileIds"] == [str(fid)]


def test_freetext_target_backward_compatible(client, db_mode):
    """向后兼容:仅传 targetCourseName(无 targetCourseId)仍可提交（学生端/旧路径）。"""
    _seed(db_mode)
    stu = _stu_token("认甲", "RN2401")
    r = client.post(f"{BASE}/grade-recognitions/student/submit", headers=stu, json=_BODY)
    assert r.status_code == 200, r.text
    assert r.json()["data"]["targetCourseName"] == "高等数学"
    assert r.json()["data"]["targetCourseId"] is None
