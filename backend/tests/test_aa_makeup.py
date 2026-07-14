"""补考重修缓考免修（/academic-affairs/makeup|retake|exemption/*）端点测试（SM-12 四条线）。

覆盖：补考批次全流程(建→纳入→发布→录入→结束回写t_acad_grade)、重修报名+次数上限422+单节点审批、
免修已获成绩422+三级审批全链路、缓考合流并入补考批次、学生越权管理403。
MySQL-only（db_mode 夹具）。口径核对施工包 §7/§9/§10。
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
    from app.models import AcademicGrade, AcademicStudent, College, Major, StudentProfile
    db = get_sessionmaker()()
    col = College(tenant_id=TID, college_name="软件学院", status="ACTIVE")
    db.add(col); db.flush()
    major = Major(tenant_id=TID, college_id=col.id, major_name="软件技术", status="ACTIVE")
    db.add(major); db.flush()
    s1 = StudentProfile(tenant_id=TID, student_no="MK2401", real_name="补甲", college_id=col.id,
                        major_id=major.id, grade="2024", student_status="NORMAL", status="ACTIVE")
    db.add(s1); db.flush()
    a1 = AcademicStudent(tenant_id=TID, student_id=s1.id, student_no="MK2401", name="补甲",
                         class_name="软件2401", college_name="软件学院")
    db.add(a1); db.flush()
    # 一门挂科（补考候选） + 一门及格（免修 422 用）
    db.add_all([
        AcademicGrade(tenant_id=TID, acad_student_id=a1.id, course_name="高等数学", credit_value=4,
                      score=45, pass_status="FAILED", source="PUBLISH", record_status="ACTIVE"),
        AcademicGrade(tenant_id=TID, acad_student_id=a1.id, course_name="大学英语", credit_value=3,
                      score=88, pass_status="PASSED", source="PUBLISH", record_status="ACTIVE"),
    ])
    db.commit()
    ids = {"student": s1.id, "acad": a1.id}
    db.close()
    return ids


def test_m1_makeup_full_flow(client, db_mode):
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    # 补考候选含挂科生
    pend = client.get(f"{BASE}/makeup/pending", headers=admin).json()
    assert pend["code"] == 0 and any(r["courseName"] == "高等数学" for r in pend["data"]["items"])
    # 建批次→纳入→发布
    bid = client.post(f"{BASE}/makeup/batches", headers=admin, json={"batchName": "2024秋补考"}).json()["data"]["batchId"]
    mk = client.post(f"{BASE}/makeup/batches/{bid}/enroll", headers=admin,
                     json={"acadStudentId": str(ids["acad"]), "courseName": "高等数学", "originScore": 45}).json()
    mid = mk["data"]["makeupId"]
    client.post(f"{BASE}/makeup/batches/{bid}/publish", headers=admin)
    # 录入补考成绩 72 → 接R1审核链：学院审→教务发布回写（CAP60 → 记 60 及格）
    client.post(f"{BASE}/makeup/records/{mid}/score", headers=admin, json={"score": 72})
    # 未学院审直接发布 → 409
    assert client.post(f"{BASE}/makeup/batches/{bid}/finish", headers=admin).status_code == 409
    # 学院审核 SCORING→REVIEWED
    assert client.post(f"{BASE}/makeup/batches/{bid}/college-review", headers=admin).json()["data"]["status"] == "REVIEWED"
    fin = client.post(f"{BASE}/makeup/batches/{bid}/finish", headers=admin).json()
    assert fin["code"] == 0 and fin["data"]["status"] == "FINISHED"
    # 校验回写了 MAKEUP 成绩行（封顶 60 及格）
    from app.db.session import get_sessionmaker
    from app.models import AcademicGrade
    db = get_sessionmaker()()
    g = db.query(AcademicGrade).filter(AcademicGrade.tenant_id == TID, AcademicGrade.source == "MAKEUP",
                                       AcademicGrade.course_name == "高等数学").first()
    assert g is not None and g.score == 60 and g.pass_status == "PASSED"
    db.close()


def test_m2_retake_apply_and_maxcount(client, db_mode):
    _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    stu = _stu_token("补甲", "MK2401")
    # 第1次报名
    r1 = client.post(f"{BASE}/retake/apply", headers=stu, json={"courseName": "高等数学", "termCode": "2024-2"}).json()
    assert r1["code"] == 0 and r1["data"]["status"] == "SUBMITTED"
    aid = r1["data"]["applyId"]
    # 同课程在途重复 → 409
    assert client.post(f"{BASE}/retake/apply", headers=stu,
                       json={"courseName": "高等数学", "termCode": "2024-2"}).status_code == 409
    # 教务处审批通过 → 编入（apply#1 变 ENROLLED，脱离在途）
    assert client.post(f"{BASE}/retake/applies/{aid}/review", headers=admin, json={"action": "APPROVE"}).json()["data"]["status"] == "APPROVED"
    assert client.post(f"{BASE}/retake/applies/{aid}/enroll", headers=admin, json={}).json()["data"]["status"] == "ENROLLED"
    # 第2次报名（不在途，len(done)=1<2 可报），审批编入脱离在途
    aid2 = client.post(f"{BASE}/retake/apply", headers=stu, json={"courseName": "高等数学", "termCode": "2024-3"}).json()["data"]["applyId"]
    client.post(f"{BASE}/retake/applies/{aid2}/review", headers=admin, json={"action": "APPROVE"})
    client.post(f"{BASE}/retake/applies/{aid2}/enroll", headers=admin, json={})
    # 第3次：无在途，但 done=2 已达上限 → 400（本项目校验错误统一 400）
    r3 = client.post(f"{BASE}/retake/apply", headers=stu, json={"courseName": "高等数学", "termCode": "2024-4"})
    assert r3.status_code == 400


def test_m3_exemption_already_passed_422(client, db_mode):
    _seed(db_mode)
    stu = _stu_token("补甲", "MK2401")
    # 大学英语已及格 → 免修申请 400（已获成绩）
    assert client.post(f"{BASE}/exemption/apply", headers=stu,
                       json={"courseName": "大学英语", "termCode": "2024-2"}).status_code == 400


def test_m4_exemption_three_level_approval(client, db_mode):
    _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    stu = _stu_token("补甲", "MK2401")
    e = client.post(f"{BASE}/exemption/apply", headers=stu,
                    json={"courseName": "线性代数", "termCode": "2024-2", "reason": "已获竞赛证书"}).json()
    assert e["code"] == 0 and e["data"]["status"] == "TEACHER_REVIEW"
    eid = e["data"]["exemptionId"]
    # 三级：教师→学院→教务处
    assert client.post(f"{BASE}/exemption/applies/{eid}/review", headers=admin, json={"action": "APPROVE"}).json()["data"]["status"] == "COLLEGE_REVIEW"
    assert client.post(f"{BASE}/exemption/applies/{eid}/review", headers=admin, json={"action": "APPROVE"}).json()["data"]["status"] == "ACADEMIC_REVIEW"
    assert client.post(f"{BASE}/exemption/applies/{eid}/review", headers=admin, json={"action": "APPROVE"}).json()["data"]["status"] == "APPROVED"


def test_m5_deferred_merge_into_makeup(client, db_mode):
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    # 造一条 APPROVED 缓考记录
    from app.db.session import get_sessionmaker
    from app.models import AaDeferredExam
    db = get_sessionmaker()()
    d = AaDeferredExam(tenant_id=TID, student_id=ids["student"], student_no="MK2401", student_name="补甲",
                       exam_course_id=999, course_name="概率论", status="APPROVED")
    db.add(d); db.flush()
    did = d.id
    db.commit(); db.close()
    # 缓考池含该记录
    pool = client.get(f"{BASE}/makeup/deferred-pool", headers=admin).json()
    assert pool["code"] == 0 and any(x["deferId"] == str(did) for x in pool["data"]["items"])
    # 建补考批次并并入
    bid = client.post(f"{BASE}/makeup/batches", headers=admin, json={"batchName": "缓考合流批次"}).json()["data"]["batchId"]
    r = client.post(f"{BASE}/makeup/deferred-pool/{did}/merge", headers=admin, json={"batchId": str(bid)}).json()
    assert r["code"] == 0 and r["data"]["merged"] is True


def test_m7_link_exam_batch(client, db_mode):
    _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    bid = client.post(f"{BASE}/makeup/batches", headers=admin, json={"batchName": "挂考务补考"}).json()["data"]["batchId"]
    # 挂不存在的考务批次 → 404
    assert client.post(f"{BASE}/makeup/batches/{bid}/link-exam", headers=admin, json={"examBatchId": "999999"}).status_code == 404
    # 建真实考务批次并挂
    ebid = client.post(f"{BASE}/exam/batches", headers=admin, json={"batchName": "补考考务批次"}).json()["data"]["batchId"]
    r = client.post(f"{BASE}/makeup/batches/{bid}/link-exam", headers=admin, json={"examBatchId": str(ebid)}).json()
    assert r["code"] == 0 and r["data"]["status"] == "ARRANGED"


def test_m6_student_cannot_manage_403(client, db_mode):
    _seed(db_mode)
    stu = _stu_token("补甲", "MK2401")
    assert client.post(f"{BASE}/makeup/batches", headers=stu, json={"batchName": "越权"}).status_code == 403
    assert client.get(f"{BASE}/retake/applies", headers=stu).status_code == 403
