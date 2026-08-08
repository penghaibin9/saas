"""补考重修缓考免修（/academic-affairs/makeup|retake|exemption/*）端点测试（SM-12 四条线）。

覆盖：补考批次全流程(建→按gradeId纳入→发布→录入→结束回写t_acad_grade)、重修报名+次数上限+单节点审批、
免修已获成绩拒绝+三级审批全链路、缓考合流并入补考批次、学生越权管理403。

契约收口（P0-F01/F02/F03）：补考纳入只认 gradeId、重修只认 gradeId、免修只认 courseId；
课程名称、原始分数、学期一律由服务器从正式成绩/课程库推导，客户端不再拥有权威。
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
    """种子必须给全稳定课程身份：当前办理学期 + 课程库版本行 + 带 courseId/版本/修读次数的正式成绩。

    缺任何一项，按 gradeId 纳入补考、按 courseId 免修都会被身份门禁挡下——这是设计意图，
    不是测试环境问题，所以种子照真实数据形态建，不为了让测试变绿而放宽服务端校验。
    """
    from app.db.session import get_sessionmaker
    from app.models import (AaCourse, AaTeachingTask, AaTeachingTaskBatch, AaTerm, AcademicGrade,
                            AcademicStudent, College, Major, SchoolClass, StudentProfile)
    db = get_sessionmaker()()
    term = AaTerm(tenant_id=TID, year_code="2024-2025", term_no=1, status="PUBLISHED", is_current=True)
    db.add(term); db.flush()
    col = College(tenant_id=TID, college_name="软件学院", status="ACTIVE")
    db.add(col); db.flush()
    major = Major(tenant_id=TID, college_id=col.id, major_name="软件技术", status="ACTIVE")
    db.add(major); db.flush()
    klass = SchoolClass(tenant_id=TID, major_id=major.id, class_name="软件2401", grade="2024", status="ACTIVE")
    db.add(klass); db.flush()
    c_math = AaCourse(tenant_id=TID, course_code="MK_MATH", course_name="高等数学", credit=4,
                      version=1, status="ENABLED")
    c_eng = AaCourse(tenant_id=TID, course_code="MK_ENG", course_name="大学英语", credit=3,
                     version=1, status="ENABLED")
    c_lin = AaCourse(tenant_id=TID, course_code="MK_LIN", course_name="线性代数", credit=3,
                     version=1, status="ENABLED")
    db.add_all([c_math, c_eng, c_lin]); db.flush()
    # 重修「编入跟班」必须落到真实教学任务：同学期、同 courseId，否则服务端拒绝
    tb = AaTeachingTaskBatch(tenant_id=TID, term_id=term.id, batch_name="2024秋教学任务",
                             college_id=col.id, status="ACTIVE")
    db.add(tb); db.flush()
    task_math = AaTeachingTask(tenant_id=TID, batch_id=tb.id, course_id=c_math.id, course_name="高等数学",
                               class_id=klass.id, teaching_class_name="软件2401",
                               teacher_key="teacher_a", teacher_name="甲老师")
    db.add(task_math); db.flush()
    s1 = StudentProfile(tenant_id=TID, student_no="MK2401", real_name="补甲", college_id=col.id,
                        major_id=major.id, class_id=klass.id, grade="2024",
                        student_status="NORMAL", status="ACTIVE")
    db.add(s1); db.flush()
    a1 = AcademicStudent(tenant_id=TID, student_id=s1.id, student_no="MK2401", name="补甲",
                         class_name="软件2401", college_name="软件学院")
    db.add(a1); db.flush()
    # 一门挂科（补考/重修候选） + 一门及格（免修拒绝用）
    g_fail = AcademicGrade(tenant_id=TID, acad_student_id=a1.id, course_name="高等数学",
                           course_id=c_math.id, course_code=c_math.course_code, course_version=1,
                           attempt_no=1, credit_value=4, score=45, pass_status="FAILED",
                           source="PUBLISH", record_status="ACTIVE")
    g_pass = AcademicGrade(tenant_id=TID, acad_student_id=a1.id, course_name="大学英语",
                           course_id=c_eng.id, course_code=c_eng.course_code, course_version=1,
                           attempt_no=1, credit_value=3, score=88, pass_status="PASSED",
                           source="PUBLISH", record_status="ACTIVE")
    db.add_all([g_fail, g_pass]); db.commit()
    ids = {"student": s1.id, "acad": a1.id, "failGrade": g_fail.id, "passGrade": g_pass.id,
           "courseMath": c_math.id, "courseEng": c_eng.id, "courseLin": c_lin.id,
           "taskMath": task_math.id}
    db.close()
    return ids


def test_m1_makeup_full_flow(client, db_mode):
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    # 补考候选含挂科生，且带出可直接提交的 gradeId
    pend = client.get(f"{BASE}/makeup/pending", headers=admin).json()
    assert pend["code"] == 0
    row = next(r for r in pend["data"]["items"] if r["courseName"] == "高等数学")
    assert row["gradeId"] == str(ids["failGrade"]) and row["identityReady"] is True
    # 建批次→按 gradeId 纳入→发布
    bid = client.post(f"{BASE}/makeup/batches", headers=admin, json={"batchName": "2024秋补考"}).json()["data"]["batchId"]
    mk = client.post(f"{BASE}/makeup/batches/{bid}/enroll", headers=admin,
                     json={"gradeId": row["gradeId"], "acadStudentId": str(ids["acad"])}).json()
    assert mk["code"] == 0 and mk["data"]["originGradeId"] == str(ids["failGrade"])
    mid = mk["data"]["makeupId"]
    assert client.post(f"{BASE}/makeup/batches/{bid}/publish", headers=admin).json()["code"] == 0
    # 录入补考成绩 72 → 接R1审核链：学院审→教务发布回写（CAP60 → 记 60 及格）
    client.post(f"{BASE}/makeup/records/{mid}/score", headers=admin, json={"score": 72})
    # 未学院审直接发布 → 409
    assert client.post(f"{BASE}/makeup/batches/{bid}/finish", headers=admin).status_code == 409
    # 学院审核 SCORING→REVIEWED
    assert client.post(f"{BASE}/makeup/batches/{bid}/college-review", headers=admin).json()["data"]["status"] == "REVIEWED"
    fin = client.post(f"{BASE}/makeup/batches/{bid}/finish", headers=admin).json()
    assert fin["code"] == 0 and fin["data"]["status"] == "FINISHED"
    # 校验回写了 MAKEUP 成绩行（封顶 60 及格），且原挂科行仍在（追加式，不覆盖历史）
    from app.db.session import get_sessionmaker
    from app.models import AcademicGrade
    db = get_sessionmaker()()
    g = db.query(AcademicGrade).filter(AcademicGrade.tenant_id == TID, AcademicGrade.source == "MAKEUP",
                                       AcademicGrade.course_name == "高等数学").first()
    assert g is not None and g.score == 60 and g.pass_status == "PASSED"
    assert g.course_id == ids["courseMath"] and g.source_biz_id == int(mid)
    origin = db.get(AcademicGrade, ids["failGrade"])
    assert origin is not None and origin.score == 45 and origin.record_status == "ACTIVE"
    db.close()


def test_m1b_makeup_enroll_rejects_legacy_course_name_body(client, db_mode):
    """P0-F01 反向：旧的 courseName/originScore 契约必须被拒，不得再按课程名称猜成绩。"""
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    bid = client.post(f"{BASE}/makeup/batches", headers=admin, json={"batchName": "契约批次"}).json()["data"]["batchId"]
    r = client.post(f"{BASE}/makeup/batches/{bid}/enroll", headers=admin,
                    json={"acadStudentId": str(ids["acad"]), "courseName": "高等数学", "originScore": 45})
    assert r.status_code == 400
    # 拿别人/不存在的 gradeId 纳入 → 409，且不落名单
    bad = client.post(f"{BASE}/makeup/batches/{bid}/enroll", headers=admin,
                      json={"gradeId": "99999999", "acadStudentId": str(ids["acad"])})
    assert bad.status_code == 409
    from app.db.session import get_sessionmaker
    from app.models import AcademicMakeup
    db = get_sessionmaker()()
    assert db.query(AcademicMakeup).filter(AcademicMakeup.tenant_id == TID,
                                           AcademicMakeup.batch_id == int(bid)).count() == 0
    db.close()


def test_m2_retake_apply_and_maxcount(client, db_mode):
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    stu = _stu_token("补甲", "MK2401")
    gid = str(ids["failGrade"])
    # 第1次报名：只传 gradeId，学期/课程由服务器推导
    r1 = client.post(f"{BASE}/retake/apply", headers=stu, json={"gradeId": gid}).json()
    assert r1["code"] == 0 and r1["data"]["status"] == "SUBMITTED"
    assert r1["data"]["courseId"] == str(ids["courseMath"]) and r1["data"]["originGradeId"] == gid
    aid = r1["data"]["applyId"]
    # 同课程在途重复 → 409
    assert client.post(f"{BASE}/retake/apply", headers=stu, json={"gradeId": gid}).status_code == 409
    # 教务处审批通过：APPROVED 仍算在途（还没编入跟班），因此依然不能再报
    assert client.post(f"{BASE}/retake/applies/{aid}/review", headers=admin,
                       json={"action": "APPROVE"}).json()["data"]["status"] == "APPROVED"
    assert client.post(f"{BASE}/retake/apply", headers=stu, json={"gradeId": gid}).status_code == 409
    # 编入真实教学任务后才脱离在途，并生成正式教学班名单版本
    enrolled = client.post(f"{BASE}/retake/applies/{aid}/enroll", headers=admin,
                           json={"teachingTaskRef": str(ids["taskMath"])}).json()
    assert enrolled["code"] == 0 and enrolled["data"]["status"] == "ENROLLED"
    assert enrolled["data"]["rosterVersionId"]
    # 第2次报名（不在途，len(history)=1<2 可报）
    r2 = client.post(f"{BASE}/retake/apply", headers=stu, json={"gradeId": gid}).json()
    assert r2["code"] == 0
    aid2 = r2["data"]["applyId"]
    client.post(f"{BASE}/retake/applies/{aid2}/review", headers=admin, json={"action": "APPROVE"})
    client.post(f"{BASE}/retake/applies/{aid2}/enroll", headers=admin,
                json={"teachingTaskRef": str(ids["taskMath"])})
    # 第3次：无在途，但已达上限2 → 400（本项目校验错误统一 400）
    assert client.post(f"{BASE}/retake/apply", headers=stu, json={"gradeId": gid}).status_code == 400


def test_m2b_retake_rejects_legacy_body_and_foreign_grade(client, db_mode):
    """P0-F02 反向：旧 courseName 契约 400（本项目参数校验失败统一 400）；拿非本人有效挂科成绩 409。"""
    ids = _seed(db_mode)
    stu = _stu_token("补甲", "MK2401")
    assert client.post(f"{BASE}/retake/apply", headers=stu,
                       json={"courseName": "高等数学", "termCode": "2024-2"}).status_code == 400
    # 及格成绩不是挂科结果，不能拿来发起重修
    assert client.post(f"{BASE}/retake/apply", headers=stu,
                       json={"gradeId": str(ids["passGrade"])}).status_code == 409
    from app.db.session import get_sessionmaker
    from app.models import AaRetakeApply
    db = get_sessionmaker()()
    assert db.query(AaRetakeApply).filter(AaRetakeApply.tenant_id == TID).count() == 0
    db.close()


def test_m3_exemption_already_passed_rejected(client, db_mode):
    ids = _seed(db_mode)
    stu = _stu_token("补甲", "MK2401")
    # 大学英语已及格 → 免修申请 400（已获成绩）
    r = client.post(f"{BASE}/exemption/apply", headers=stu, json={"courseId": str(ids["courseEng"])})
    assert r.status_code == 400


def test_m3b_exemption_rejects_legacy_body(client, db_mode):
    """P0-F03 反向：旧 courseName 契约 400（本项目参数校验失败统一 400）；不存在的 courseId 404，均不落申请。"""
    _seed(db_mode)
    stu = _stu_token("补甲", "MK2401")
    assert client.post(f"{BASE}/exemption/apply", headers=stu,
                       json={"courseName": "线性代数", "termCode": "2024-2"}).status_code == 400
    assert client.post(f"{BASE}/exemption/apply", headers=stu,
                       json={"courseId": "99999999"}).status_code == 404
    from app.db.session import get_sessionmaker
    from app.models import AaExemption
    db = get_sessionmaker()()
    assert db.query(AaExemption).filter(AaExemption.tenant_id == TID).count() == 0
    db.close()


def test_m4_exemption_three_level_approval(client, db_mode):
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    stu = _stu_token("补甲", "MK2401")
    e = client.post(f"{BASE}/exemption/apply", headers=stu,
                    json={"courseId": str(ids["courseLin"]), "reason": "已获竞赛证书"}).json()
    assert e["code"] == 0 and e["data"]["status"] == "TEACHER_REVIEW"
    assert e["data"]["courseId"] == str(ids["courseLin"]) and e["data"]["courseName"] == "线性代数"
    eid = e["data"]["exemptionId"]
    # 三级：教师→学院→教务处
    assert client.post(f"{BASE}/exemption/applies/{eid}/review", headers=admin, json={"action": "APPROVE"}).json()["data"]["status"] == "COLLEGE_REVIEW"
    assert client.post(f"{BASE}/exemption/applies/{eid}/review", headers=admin, json={"action": "APPROVE"}).json()["data"]["status"] == "ACADEMIC_REVIEW"
    assert client.post(f"{BASE}/exemption/applies/{eid}/review", headers=admin, json={"action": "APPROVE"}).json()["data"]["status"] == "APPROVED"


def test_m5_deferred_merge_requires_frozen_roster(client, db_mode):
    """缓考并入后续考试必须有原考试课程的冻结名单；凭空造的缓考记录不得混入正式补考批次。"""
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
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
    # 建补考批次并尝试并入：考试课程 999 不存在冻结名单 → 409，不产生补考名单副作用
    bid = client.post(f"{BASE}/makeup/batches", headers=admin, json={"batchName": "缓考合流批次"}).json()["data"]["batchId"]
    r = client.post(f"{BASE}/makeup/deferred-pool/{did}/merge", headers=admin, json={"batchId": str(bid)})
    assert r.status_code == 409
    from app.models import AcademicMakeup
    db = get_sessionmaker()()
    assert db.query(AcademicMakeup).filter(AcademicMakeup.tenant_id == TID,
                                           AcademicMakeup.batch_id == int(bid)).count() == 0
    db.close()


def test_m7_link_exam_batch(client, db_mode):
    _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    from app.db.session import get_sessionmaker
    from app.models import AaTerm
    db = get_sessionmaker()()
    term_id = db.query(AaTerm).filter(AaTerm.tenant_id == TID).first().id
    db.close()
    bid = client.post(f"{BASE}/makeup/batches", headers=admin, json={"batchName": "挂考务补考"}).json()["data"]["batchId"]
    # 挂不存在的考务批次 → 404
    assert client.post(f"{BASE}/makeup/batches/{bid}/link-exam", headers=admin, json={"examBatchId": "999999"}).status_code == 404
    # 建真实考务批次并挂
    ebid = client.post(f"{BASE}/exam/batches", headers=admin,
                       json={"batchName": "补考考务批次", "termId": str(term_id)}).json()["data"]["batchId"]
    r = client.post(f"{BASE}/makeup/batches/{bid}/link-exam", headers=admin, json={"examBatchId": str(ebid)}).json()
    assert r["code"] == 0 and r["data"]["status"] == "ARRANGED"


def test_m6_student_cannot_manage_403(client, db_mode):
    _seed(db_mode)
    stu = _stu_token("补甲", "MK2401")
    assert client.post(f"{BASE}/makeup/batches", headers=stu, json={"batchName": "越权"}).status_code == 403
    assert client.get(f"{BASE}/retake/applies", headers=stu).status_code == 403
