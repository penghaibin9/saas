"""移动端聚合测试：学生只见本人、学生隔离、租户隔离、教师本校、403/401、脱敏、空态不500。"""
from __future__ import annotations

MAIN = 1000000000000000001
DEMO = 1000000000000000003


def _stu_token(real_name, tenant_id=MAIN, tid="demo"):
    from app.core.security import create_access_token
    return {"Authorization": "Bearer " + create_access_token({
        "userId": f"u-{real_name}", "realName": real_name, "userType": "STUDENT",
        "tid": tid, "tenantId": str(tenant_id), "activeContextId": "ctx",
        "currentRoleCode": "STUDENT", "clientType": "MP"})}


def _teacher_token(tenant_id=MAIN, tid="demo"):
    from app.core.security import create_access_token
    return {"Authorization": "Bearer " + create_access_token({
        "userId": "u-teacher", "realName": "王辅导", "userType": "TEACHER",
        "tid": tid, "tenantId": str(tenant_id), "activeContextId": "ctx",
        "currentRoleCode": "COUNSELOR", "clientType": "MP"})}


def _seed_two_students(_db_mode):
    from app.db.session import get_sessionmaker
    from app.models import AcademicGrade, AcademicStudent, StudentProfile
    db = get_sessionmaker()()
    try:
        for nm, no in [("学生甲", "MB0001"), ("学生乙", "MB0002")]:
            db.add(StudentProfile(tenant_id=MAIN, student_no=no, real_name=nm, grade="2023",
                                  current_stage="ON_CAMPUS", student_status="NORMAL", status="ACTIVE"))
        db.flush()
        # 甲的学业记录
        a = AcademicStudent(tenant_id=MAIN, name="学生甲", student_no="MB0001", class_name="软件2301班",
                            gpa=3.5, avg_score=88, obtained_credits=70, required_credits=120,
                            academic_status="NORMAL", warning_level="NONE")
        db.add(a)
        db.flush()
        db.add(AcademicGrade(tenant_id=MAIN, acad_student_id=a.id, course_name="甲的课程", term="2025-2026-2",
                             nature="REQUIRED", credit_value=4, score=90, pass_status="PASSED", exam_type="FINAL"))
        # 乙的学业记录（不同）
        b = AcademicStudent(tenant_id=MAIN, name="学生乙", student_no="MB0002", class_name="软件2301班",
                            gpa=2.0, avg_score=60, obtained_credits=40, required_credits=120,
                            academic_status="WARNING", warning_level="HIGH")
        db.add(b)
        db.commit()
    finally:
        db.close()


def test_student_sees_only_self(client, db_mode):
    _seed_two_students(db_mode)
    a = client.get("/api/v1/mobile/academic/my", headers=_stu_token("学生甲")).json()
    assert a["code"] == 0 and a["data"]["hasData"] is True
    assert a["data"]["summary"]["gpa"] == 3.5
    assert a["data"]["grades"][0]["course"] == "甲的课程"
    # 甲看不到乙的 GPA
    b = client.get("/api/v1/mobile/academic/my", headers=_stu_token("学生乙")).json()
    assert b["data"]["summary"]["gpa"] == 2.0 and b["data"]["summary"]["academicStatus"] == "WARNING"
    # 两者数据不串
    assert a["data"]["summary"]["gpa"] != b["data"]["summary"]["gpa"]


def test_unknown_student_empty_not_500(client, db_mode):
    _seed_two_students(db_mode)
    r = client.get("/api/v1/mobile/academic/my", headers=_stu_token("查无此人")).json()
    assert r["code"] == 0 and r["data"]["hasData"] is False  # 空态而非 500


def test_overview_and_six_my_no_500(client, db_mode):
    _seed_two_students(db_mode)
    ov = client.get("/api/v1/mobile/me/overview", headers=_stu_token("学生甲")).json()
    assert ov["code"] == 0 and ov["data"]["student"]["name"] == "学生甲"
    for d in ("orientation", "campus-service", "academic", "internship", "graduation", "employment"):
        r = client.get(f"/api/v1/mobile/{d}/my", headers=_stu_token("学生甲")).json()
        assert r["code"] == 0, (d, r)  # 有的域甲无记录 → hasData False，但不 500


def test_teacher_cannot_access_student_self(client, db_mode):
    _seed_two_students(db_mode)
    r = client.get("/api/v1/mobile/academic/my", headers=_teacher_token()).json()
    assert r["code"] == 403001 and r["bizCode"] == "NO_PERMISSION"


def test_student_cannot_access_teacher(client, db_mode):
    r = client.get("/api/v1/mobile/teacher/overview", headers=_stu_token("学生甲")).json()
    assert r["code"] == 403001


def test_teacher_overview_ok(client, db_mode):
    _seed_two_students(db_mode)
    r = client.get("/api/v1/mobile/teacher/overview", headers=_teacher_token()).json()
    assert r["code"] == 0 and "metrics" in r["data"] and "pendingTotal" in r["data"]


def test_tenant_isolation(client, db_mode):
    _seed_two_students(db_mode)
    # demo-school 租户的学生 token（realName 学生甲 但 tenant=demo）→ 看不到 main 的学生甲数据
    r = client.get("/api/v1/mobile/academic/my",
                   headers=_stu_token("学生甲", tenant_id=DEMO, tid="demo-school")).json()
    assert r["code"] == 0 and r["data"]["hasData"] is False  # 跨租户查不到


def test_requires_login(client):
    assert client.get("/api/v1/mobile/me/overview").json()["code"] == 401001
    assert client.get("/api/v1/mobile/teacher/overview").json()["code"] == 401001


# ══════════ P9.2 新增：档案脱敏 / 消息本人 / 申请本人 / 写操作 / 教师范围 ══════════

def _seed_rich(_db_mode):
    """张三（含手机/在校服务/请假/实习记录）+ 李四（另一名学生，用于隔离）+ 一条学业预警。"""
    from app.db.session import get_sessionmaker
    from app.models import (AcademicStudent, AcademicWarning, CsLeave, CsServiceStudent,
                            InternshipRecord, StudentContact, StudentProfile)
    db = get_sessionmaker()()
    try:
        p3 = StudentProfile(tenant_id=MAIN, student_no="RICH01", real_name="张三", grade="2023",
                            current_stage="INTERNSHIP", student_status="NORMAL", status="ACTIVE",
                            id_card_encrypted="430123200501011234")
        p4 = StudentProfile(tenant_id=MAIN, student_no="RICH02", real_name="李四", grade="2023",
                            current_stage="ON_CAMPUS", student_status="NORMAL", status="ACTIVE")
        db.add_all([p3, p4])
        db.flush()
        db.add(StudentContact(tenant_id=MAIN, student_id=p3.id, contact_type="PHONE",
                              contact_value_encrypted="13800001111", is_primary=True))
        cs3 = CsServiceStudent(tenant_id=MAIN, student_no="RICH01", student_id=p3.id, name="张三",
                               risk_level="HIGH", record_status="ACTIVE")
        db.add(cs3)
        db.flush()
        db.add(CsLeave(tenant_id=MAIN, cs_student_id=cs3.id, leave_type="PERSONAL",
                       reason="家中有事", status="PENDING_REVIEW"))
        db.add(InternshipRecord(tenant_id=MAIN, student_id=p3.id, enterprise_name="示范科技",
                                position_name="开发实习生", status="ONBOARD", risk_level="MEDIUM"))
        a3 = AcademicStudent(tenant_id=MAIN, name="张三", student_no="RICH01", class_name="软件2301班",
                             gpa=2.1, avg_score=61, obtained_credits=40, required_credits=120,
                             academic_status="WARNING", warning_level="HIGH")
        db.add(a3)
        db.flush()
        db.add(AcademicWarning(tenant_id=MAIN, acad_student_id=a3.id, warn_type="GPA",
                               level="HIGH", reason="GPA 偏低", status="PENDING_HANDLE",
                               record_status="ACTIVE"))
        db.commit()
        return p3.id
    finally:
        db.close()


def test_profile_masked(client, db_mode):
    _seed_rich(db_mode)
    r = client.get("/api/v1/mobile/me/profile", headers=_stu_token("张三")).json()
    assert r["code"] == 0 and r["data"]["hasData"] is True
    d = r["data"]
    assert d["name"] == "张三" and d["studentNo"] == "RICH01"
    assert "****" in d["phoneMasked"] and "13800001111" not in d["phoneMasked"]
    assert "*" in d["idCardMasked"] and "430123200501011234" not in d["idCardMasked"]
    assert "address" not in d  # 住址不返回


def test_messages_self_only(client, db_mode):
    _seed_rich(db_mode)
    r = client.get("/api/v1/mobile/me/messages", headers=_stu_token("张三")).json()
    assert r["code"] == 0
    prog = r["data"]["groups"]["progress"]
    assert any("请假" in m["title"] for m in prog)  # 本人请假进度
    # 李四没有请假记录 → progress 为空
    r2 = client.get("/api/v1/mobile/me/messages", headers=_stu_token("李四")).json()
    assert r2["code"] == 0 and r2["data"]["groups"]["progress"] == []


def test_applications_self_only(client, db_mode):
    _seed_rich(db_mode)
    r = client.get("/api/v1/mobile/me/applications", headers=_stu_token("张三")).json()
    assert r["code"] == 0 and len(r["data"]["applications"]) >= 1
    assert any(a["sourceType"] == "LEAVE" for a in r["data"]["applications"])
    # 李四看不到张三的申请
    r2 = client.get("/api/v1/mobile/me/applications", headers=_stu_token("李四")).json()
    assert r2["code"] == 0 and r2["data"]["applications"] == []


def test_service_apply_success_and_422(client, db_mode):
    _seed_rich(db_mode)
    ok = client.post("/api/v1/mobile/campus-service/apply",
                     headers=_stu_token("张三"),
                     json={"serviceKey": "证明开具", "reason": "办理助学贷款需要在校证明"}).json()
    assert ok["code"] == 0 and ok["data"]["id"]
    bad = client.post("/api/v1/mobile/campus-service/apply",
                      headers=_stu_token("张三"),
                      json={"serviceKey": "证明开具", "reason": "太短"}).json()
    assert bad["code"] == 422001  # 事由 < 5 字


def test_weekly_submit_success_and_409(client, db_mode):
    _seed_rich(db_mode)
    body = {"weekNo": 3, "workContent": "本周完成登录模块开发与联调，累计提交代码若干。",
           "harvestContent": "熟悉了登录鉴权与联调流程，收获较大。"}
    ok = client.post("/api/v1/mobile/internship/weekly", headers=_stu_token("张三"), json=body).json()
    assert ok["code"] == 0 and ok["data"]["id"]
    dup = client.post("/api/v1/mobile/internship/weekly", headers=_stu_token("张三"), json=body).json()
    assert dup["code"] == 409001  # 同周重复提交


def test_weekly_no_internship_not_500(client, db_mode):
    _seed_rich(db_mode)
    # 李四没有实习记录 → 404 业务错，非 500
    r = client.post("/api/v1/mobile/internship/weekly", headers=_stu_token("李四"),
                    json={"weekNo": 1, "workContent": "十个字以上的本周工作内容测试文本。",
                         "harvestContent": "十个字以上的本周收获内容测试文本。"}).json()
    assert r["code"] == 404001


def test_teacher_todos_403_and_200(client, db_mode):
    _seed_rich(db_mode)
    assert client.get("/api/v1/mobile/teacher/todos",
                      headers=_stu_token("张三")).json()["code"] == 403001
    r = client.get("/api/v1/mobile/teacher/todos", headers=_teacher_token()).json()
    assert r["code"] == 0 and "pendingCount" in r["data"] and "list" in r["data"]


def test_teacher_risk_students_tenant_isolation(client, db_mode):
    _seed_rich(db_mode)
    main = client.get("/api/v1/mobile/teacher/risk-students", headers=_teacher_token()).json()
    assert main["code"] == 0 and main["data"]["total"] >= 1  # 主租户有风险学生
    demo = client.get("/api/v1/mobile/teacher/risk-students",
                      headers=_teacher_token(tenant_id=DEMO, tid="demo-school")).json()
    assert demo["code"] == 0 and demo["data"]["total"] == 0  # demo 租户看不到主租户风险学生


def test_teacher_student_detail_200_and_404(client, db_mode):
    sid = _seed_rich(db_mode)
    ok = client.get(f"/api/v1/mobile/teacher/student/{sid}", headers=_teacher_token()).json()
    assert ok["code"] == 0 and ok["data"]["hasData"] is True
    # 不返回身份证/手机明文
    import json as _json
    blob = _json.dumps(ok["data"], ensure_ascii=False)
    assert "13800001111" not in blob and "430123200501011234" not in blob
    nf = client.get("/api/v1/mobile/teacher/student/999999", headers=_teacher_token()).json()
    assert nf["code"] == 404001


def test_teacher_student_detail_cross_tenant_not_found(client, db_mode):
    sid = _seed_rich(db_mode)
    # demo 租户教师查主租户学生 id → 查不到（404），不跨租户泄露
    r = client.get(f"/api/v1/mobile/teacher/student/{sid}",
                   headers=_teacher_token(tenant_id=DEMO, tid="demo-school")).json()
    assert r["code"] == 404001


def test_teacher_domain_pages_structure(client, db_mode):
    _seed_rich(db_mode)
    it = client.get("/api/v1/mobile/teacher/internship", headers=_teacher_token()).json()
    assert it["code"] == 0 and "weeklyReports" in it["data"] and "abnormalCheckins" in it["data"]
    gd = client.get("/api/v1/mobile/teacher/graduation", headers=_teacher_token()).json()
    assert gd["code"] == 0 and "students" in gd["data"] and "reviewDetail" in gd["data"]
    em = client.get("/api/v1/mobile/teacher/employment", headers=_teacher_token()).json()
    assert em["code"] == 0 and "students" in em["data"] and "jobPool" in em["data"]
    msg = client.get("/api/v1/mobile/teacher/messages", headers=_teacher_token()).json()
    assert msg["code"] == 0 and "groups" in msg["data"]
    ap = client.get("/api/v1/mobile/teacher/approvals", headers=_teacher_token()).json()
    assert ap["code"] == 0 and "approvals" in ap["data"]


def test_new_endpoints_require_login(client):
    for path in ("/api/v1/mobile/me/profile", "/api/v1/mobile/me/applications",
                 "/api/v1/mobile/teacher/risk-students", "/api/v1/mobile/teacher/messages"):
        assert client.get(path).json()["code"] == 401001


# ── 波8 补测：教师·我的班级 / 我的学生（counselor_id/head_teacher_id 数值ID范围收敛）──

def _teacher_token_numeric(uid, tenant_id=MAIN, tid="demo", role="COUNSELOR"):
    from app.core.security import create_access_token
    return {"Authorization": "Bearer " + create_access_token({
        "userId": str(uid), "realName": "范老师", "userType": "TEACHER",
        "tid": tid, "tenantId": str(tenant_id), "activeContextId": "ctx",
        "currentRoleCode": role, "clientType": "MP"})}


def _seed_class_with_counselor(counselor_id, n_students=2, tenant_id=MAIN):
    from app.db.session import get_sessionmaker
    from app.models import SchoolClass, StudentProfile
    db = get_sessionmaker()()
    try:
        c = SchoolClass(tenant_id=tenant_id, major_id=1, class_name="移动测2601",
                        grade="2026", counselor_id=counselor_id, status="ACTIVE")
        db.add(c); db.flush()
        cid = c.id
        for i in range(n_students):
            db.add(StudentProfile(tenant_id=tenant_id, student_no=f"MC{i:04d}",
                                  real_name=f"移测生{i}", class_id=cid,
                                  current_stage="ON_CAMPUS", student_status="NORMAL", status="ACTIVE"))
        db.commit()
        return cid
    finally:
        db.close()


def test_teacher_my_classes_and_students(client, db_mode):
    cid = _seed_class_with_counselor(555001, n_students=3)
    hdr = _teacher_token_numeric(555001)
    classes = client.get("/api/v1/mobile/teacher/my-classes", headers=hdr).json()
    assert classes["code"] == 0
    items = classes["data"]["items"]
    assert len(items) == 1 and items[0]["classId"] == str(cid) and items[0]["studentCount"] == 3

    students = client.get("/api/v1/mobile/teacher/my-students", headers=hdr).json()["data"]
    assert students["total"] == 3
    names = {s["name"] for s in students["items"]}
    assert names == {"移测生0", "移测生1", "移测生2"}

    by_class = client.get(f"/api/v1/mobile/teacher/my-students?classId={cid}",
                          headers=hdr).json()["data"]
    assert by_class["total"] == 3


def test_teacher_my_classes_no_scope_empty_not_500(client, db_mode):
    """未担任任何班级辅导员/班主任的教师账号：空态，不 500，不误报他人班级。"""
    _seed_class_with_counselor(555002, n_students=1)
    hdr = _teacher_token_numeric(555099)  # 与已建班级的 counselor_id 不同
    classes = client.get("/api/v1/mobile/teacher/my-classes", headers=hdr).json()
    assert classes["code"] == 0 and classes["data"]["items"] == []
    students = client.get("/api/v1/mobile/teacher/my-students", headers=hdr).json()["data"]
    assert students["items"] == [] and students["total"] == 0


def test_teacher_my_classes_cross_tenant_isolation(client, db_mode):
    """同一 counselor_id 数字在另一租户建的班级不应串到本租户查询结果。"""
    _seed_class_with_counselor(555003, n_students=2, tenant_id=MAIN)
    _seed_class_with_counselor(555003, n_students=5, tenant_id=DEMO)
    hdr = _teacher_token_numeric(555003, tenant_id=MAIN, tid="demo")
    students = client.get("/api/v1/mobile/teacher/my-students", headers=hdr).json()["data"]
    assert students["total"] == 2  # 只看本租户 2 人，不是跨租户合计的 7 人
