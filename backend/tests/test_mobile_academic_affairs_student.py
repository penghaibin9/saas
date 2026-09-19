"""波5 教务中心·学生自视图新增接口冒烟测试：学分/预警/补考/选课浏览，均需登录+返回200不500。"""
from __future__ import annotations

from datetime import datetime, timedelta

BASE = "/api/v1/mobile/academic"
MAIN = 1000000000000000001


def _stu_token(real_name="学分测生", student_no="CR0001", tenant_id=MAIN, tid="demo", client_type="STUDENT_MINI"):
    from app.core.security import create_access_token
    return {"Authorization": "Bearer " + create_access_token({
        "userId": f"u-{real_name}", "realName": real_name, "userType": "STUDENT",
        "studentNo": student_no, "tid": tid, "tenantId": str(tenant_id),
        "activeContextId": "ctx", "currentRoleCode": "STUDENT", "clientType": client_type})}


def _seed_student(student_no, real_name):
    from app.db.session import get_sessionmaker
    from app.models import StudentProfile
    db = get_sessionmaker()()
    try:
        db.add(StudentProfile(tenant_id=MAIN, student_no=student_no, real_name=real_name,
                              grade="2026", current_stage="ON_CAMPUS",
                              student_status="NORMAL", status="ACTIVE"))
        db.commit()
    finally:
        db.close()


def test_credits_my_no_data_not_500(client, db_mode):
    """无学业数据时接口不能 500；解析不到培养方案时毕业总学分必须是"未知"。

    原断言期望 requiredCredits == 120.0，那是早期「解析不到就给个默认 120」的口径。
    该默认值已被刻意废除：学生没维护专业、或专业没绑培养方案时，学校根本没有依据说
    这个学生该修多少学分，编一个 120 出来会让学生照错目标规划选课，"还差多少学分"
    也会算出一个假数。credit_requirement_payload 的现行契约是未解析即 None。
    """
    _seed_student("CR0001", "学分测生")
    r = client.get(f"{BASE}/credits/my", headers=_stu_token()).json()
    assert r["code"] == 0
    d = r["data"]
    assert d["requiredCredits"] is None, "未解析到培养方案时不得编造默认毕业学分"
    assert d["passedCourses"] == []


def test_warning_my_no_data_not_500(client, db_mode):
    _seed_student("CR0002", "预警测生")
    r = client.get(f"{BASE}/warning/my", headers=_stu_token("预警测生", "CR0002")).json()
    assert r["code"] == 0
    assert r["data"]["items"] == [] and r["data"]["total"] == 0


def test_makeup_my_no_data_not_500(client, db_mode):
    _seed_student("CR0003", "补考测生")
    r = client.get(f"{BASE}/makeup/my", headers=_stu_token("补考测生", "CR0003")).json()
    assert r["code"] == 0
    assert r["data"]["retakes"] == [] and r["data"]["exemptions"] == []


def test_makeup_my_uses_independent_server_pages_and_self_scope(client, db_mode):
    """移动端不能把 21 条历史全量交给前端，也不能用 URL studentId 换人。"""
    _seed_student("CR0021", "补考分页甲")
    _seed_student("CR0022", "补考分页乙")
    from app.db.session import get_sessionmaker
    from app.models import AaExemption, StudentProfile

    db = get_sessionmaker()()
    try:
        first = db.query(StudentProfile).filter(
            StudentProfile.tenant_id == MAIN, StudentProfile.student_no == "CR0021",
        ).one()
        other = db.query(StudentProfile).filter(
            StudentProfile.tenant_id == MAIN, StudentProfile.student_no == "CR0022",
        ).one()
        db.add_all([
            AaExemption(
                tenant_id=MAIN, student_id=first.id, student_no=first.student_no,
                student_name=first.real_name, course_id=10000 + index,
                course_name=f"分页免修{index}", term_code="2026-1",
                status="SUBMITTED", current_node="STUDENT_RESUBMIT",
            )
            for index in range(21)
        ] + [
            AaExemption(
                tenant_id=MAIN, student_id=other.id, student_no=other.student_no,
                student_name=other.real_name, course_id=20001,
                course_name="他人免修", term_code="2026-1",
                status="SUBMITTED", current_node="STUDENT_RESUBMIT",
            )
        ])
        db.commit()
    finally:
        db.close()

    own = _stu_token("补考分页甲", "CR0021")
    first_page = client.get(f"{BASE}/makeup/my", headers=own, params={
        "retakePage": 1, "retakePageSize": 20, "exemptionPage": 1, "exemptionPageSize": 20,
    }).json()["data"]
    assert len(first_page["exemptions"]) == 20
    assert first_page["exemptionPagination"] == {
        "page": 1, "pageSize": 20, "total": 21, "hasMore": True,
    }
    assert all(item["studentId"] != str(other.id) for item in first_page["exemptions"])

    second_page = client.get(f"{BASE}/makeup/my", headers=own, params={
        "retakePage": 1, "retakePageSize": 20, "exemptionPage": 2, "exemptionPageSize": 20,
        "studentId": str(other.id),
    }).json()["data"]
    assert len(second_page["exemptions"]) == 1
    assert second_page["exemptionPagination"] == {
        "page": 2, "pageSize": 20, "total": 21, "hasMore": False,
    }
    assert second_page["exemptions"][0]["studentId"] == str(first_page["exemptions"][0]["studentId"])


def test_makeup_retake_apply_validation(client, db_mode):
    _seed_student("CR0004", "重修测生")
    hdr = _stu_token("重修测生", "CR0004")
    bad = client.post(f"{BASE}/makeup/retake-apply", headers=hdr, json={}).json()
    assert bad["code"] != 0  # courseName 必填校验，未新建服务端崩溃


def test_makeup_mobile_routes_reject_teacher_and_legacy_mobile_client(client, db_mode):
    """补考重修学生接口只接受正式学生小程序/H5，不能用教师或旧泛移动令牌读取、写入。"""
    from app.core.security import create_access_token

    _seed_student("CR0007", "补考权限测生")
    teacher = {"Authorization": "Bearer " + create_access_token({
        "userId": "t-makeup", "realName": "教师", "userType": "TEACHER",
        "tid": "demo", "tenantId": str(MAIN), "activeContextId": "ctx",
        "currentRoleCode": "TEACHER", "clientType": "TEACHER_MINI",
    })}
    old_mobile = _stu_token("补考权限测生", "CR0007", client_type="MP")
    for method, path, payload in (
        ("get", "/makeup/my", None),
        ("get", "/makeup/options", None),
        ("post", "/makeup/retake-apply", {}),
        ("post", "/makeup/exemption-apply", {}),
        ("post", "/makeup/exemption/1/resubmit", {}),
    ):
        request = getattr(client, method)
        kwargs = {"headers": teacher}
        if method != "get":
            kwargs["json"] = payload
        assert request(BASE + path, **kwargs).status_code == 403
    assert client.get(f"{BASE}/makeup/my", headers=old_mobile).status_code == 403
    assert client.get(f"{BASE}/makeup/my", headers=_stu_token("补考权限测生", "CR0007", client_type="STUDENT_PC")).status_code == 200


def test_status_change_resubmit_routes_reject_teacher_and_legacy_mobile_client(client, db_mode):
    """退回重交元数据和写入口同样只能由正式学生移动会话访问。"""
    from app.core.security import create_access_token

    teacher = {"Authorization": "Bearer " + create_access_token({
        "userId": "t-status", "realName": "教师", "userType": "TEACHER",
        "tid": "demo", "tenantId": str(MAIN), "activeContextId": "ctx",
        "currentRoleCode": "TEACHER", "clientType": "TEACHER_MINI",
    })}
    old_mobile = _stu_token("异动权限测生", "CR0008", client_type="MP")
    path = "/api/v1/mobile/academic/status-changes/1/resubmit"
    for headers in (teacher, old_mobile):
        assert client.get(path, headers=headers).status_code == 403
        assert client.post(path, headers=headers, json={}).status_code == 403


def test_transfer_options_are_server_paged_and_tenant_scoped(client, db_mode):
    """异动候选不能整校下发，也不能借 URL 参数切换到他校/他人范围。"""
    from app.db.session import get_sessionmaker
    from app.models import StudentProfile
    from app.models.org import College, Major, SchoolClass

    external_tenant = MAIN + 99
    db = get_sessionmaker()()
    try:
        own_college = College(tenant_id=MAIN, college_name="异动测试学院", status="ACTIVE")
        db.add(own_college); db.flush()
        current_major = Major(tenant_id=MAIN, college_id=own_college.id, major_name="当前专业", status="ACTIVE")
        db.add(current_major); db.flush()
        current_class = SchoolClass(
            tenant_id=MAIN, major_id=current_major.id, class_name="当前班", grade="2026",
            status="ACTIVE", class_status="NORMAL",
        )
        db.add(current_class); db.flush()
        student = StudentProfile(
            tenant_id=MAIN, student_no="CR0030", real_name="异动分页测生", grade="2026",
            current_stage="ON_CAMPUS", student_status="NORMAL", status="ACTIVE",
            college_id=own_college.id, major_id=current_major.id, class_id=current_class.id,
        )
        other = StudentProfile(
            tenant_id=MAIN, student_no="CR0031", real_name="异动另一学生", grade="2026",
            current_stage="ON_CAMPUS", student_status="NORMAL", status="ACTIVE",
            college_id=own_college.id, major_id=current_major.id, class_id=current_class.id,
        )
        db.add_all([student, other])
        for index in range(42):
            target_major = Major(
                tenant_id=MAIN, college_id=own_college.id, major_name=f"转入专业{index:02d}",
                code=f"TR{index:02d}", status="ACTIVE",
            )
            db.add(target_major); db.flush()
            db.add(SchoolClass(
                tenant_id=MAIN, major_id=target_major.id, class_name=f"转入班{index:02d}",
                grade="2026", status="ACTIVE", class_status="NORMAL",
            ))
            db.add(SchoolClass(
                tenant_id=MAIN, major_id=current_major.id, class_name=f"同专业转班{index:02d}",
                grade="2026", status="ACTIVE", class_status="NORMAL",
            ))
        foreign_college = College(tenant_id=external_tenant, college_name="外校学院", status="ACTIVE")
        db.add(foreign_college); db.flush()
        foreign_major = Major(tenant_id=external_tenant, college_id=foreign_college.id, major_name="外校专业", status="ACTIVE")
        db.add(foreign_major); db.flush()
        db.add(SchoolClass(
            tenant_id=external_tenant, major_id=foreign_major.id, class_name="外校班", grade="2026",
            status="ACTIVE", class_status="NORMAL",
        ))
        db.commit()
        current_major_id = current_major.id
        current_class_id = current_class.id
        foreign_major_id = foreign_major.id
    finally:
        db.close()

    own = _stu_token("异动分页测生", "CR0030")
    major_one = client.get(f"{BASE}/transfer-options", headers=own, params={
        "target": "major", "page": 1, "pageSize": 20, "studentId": "not-my-id",
    }).json()
    assert major_one["code"] == 0
    assert major_one["data"]["target"] == "major"
    assert major_one["data"]["page"] == 1 and major_one["data"]["pageSize"] == 20
    assert major_one["data"]["total"] == 42 and major_one["data"]["hasMore"] is True
    assert len(major_one["data"]["items"]) == 20
    assert "majorClasses" not in major_one["data"]
    assert str(current_major_id) not in {item["majorId"] for item in major_one["data"]["items"]}

    major_two = client.get(f"{BASE}/transfer-options", headers=own, params={
        "target": "major", "page": 2, "pageSize": 20,
    }).json()["data"]
    major_three = client.get(f"{BASE}/transfer-options", headers=own, params={
        "target": "major", "page": 3, "pageSize": 20,
    }).json()["data"]
    assert (len(major_two["items"]), len(major_three["items"])) == (20, 2)
    assert major_three["hasMore"] is False

    keyword = client.get(f"{BASE}/transfer-options", headers=own, params={
        "target": "major", "keyword": "转入专业41", "page": 1, "pageSize": 20,
    }).json()["data"]
    assert keyword["total"] == 1
    assert keyword["items"][0]["majorName"] == "转入专业41"

    same_class = client.get(f"{BASE}/transfer-options", headers=own, params={
        "target": "class", "page": 1, "pageSize": 20, "studentId": "other-student",
    }).json()["data"]
    assert same_class["majorId"] == str(current_major_id)
    assert same_class["total"] == 42 and len(same_class["items"]) == 20
    assert str(current_class_id) not in {item["classId"] for item in same_class["items"]}
    assert {item["majorId"] for item in same_class["items"]} == {str(current_major_id)}

    target_major_id = major_one["data"]["items"][0]["majorId"]
    target_class = client.get(f"{BASE}/transfer-options", headers=own, params={
        "target": "class", "majorId": target_major_id, "page": 1, "pageSize": 20,
    }).json()["data"]
    assert target_class["majorId"] == target_major_id
    assert target_class["total"] == 1
    assert {item["majorId"] for item in target_class["items"]} == {target_major_id}

    foreign = client.get(f"{BASE}/transfer-options", headers=own, params={
        "target": "class", "majorId": foreign_major_id, "page": 1, "pageSize": 20,
    })
    assert foreign.status_code == 404
    assert foreign.json()["bizCode"] == "DATA_NOT_FOUND"


def test_transfer_options_reject_teacher_and_legacy_mobile_client(client, db_mode):
    from app.core.security import create_access_token

    _seed_student("CR0032", "异动权限测生")
    teacher = {"Authorization": "Bearer " + create_access_token({
        "userId": "t-transfer", "realName": "教师", "userType": "TEACHER",
        "tid": "demo", "tenantId": str(MAIN), "activeContextId": "ctx",
        "currentRoleCode": "TEACHER", "clientType": "TEACHER_MINI",
    })}
    old_mobile = _stu_token("异动权限测生", "CR0032", client_type="MP")
    path = f"{BASE}/transfer-options?target=major&page=1&pageSize=20"
    assert client.get(path, headers=teacher).status_code == 403
    assert client.get(path, headers=old_mobile).status_code == 403
    assert client.get(path, headers=_stu_token("异动权限测生", "CR0032", client_type="STUDENT_PC")).status_code == 200


def test_registration_mobile_uses_server_pages_and_enforces_self_service_window(client, db_mode):
    """注册读取只返回当前页；过期/未开始窗口须由最终写事务拒绝。"""
    from app.db.session import get_sessionmaker
    from app.models import AaRegistration, AaRegistrationBatch, AaRegistrationDeferral, AffairsAuditTrail, StudentProfile

    now = datetime.utcnow()
    foreign_tenant = MAIN + 77
    db = get_sessionmaker()()
    try:
        student = StudentProfile(
            tenant_id=MAIN, student_no="CR0033", real_name="注册窗口学生", grade="2026",
            current_stage="ORIENTATION", student_status="PENDING_REGISTER", status="ACTIVE",
        )
        defer_student = StudentProfile(
            tenant_id=MAIN, student_no="CR0034", real_name="注册暂缓学生", grade="2026",
            current_stage="ON_CAMPUS", student_status="REGISTERED", status="ACTIVE",
        )
        expired = AaRegistrationBatch(
            tenant_id=MAIN, batch_name="注册窗口已结束", register_type="ENROLL", status="OPEN",
            window_start=now - timedelta(days=3), window_end=now - timedelta(minutes=1),
        )
        future = AaRegistrationBatch(
            tenant_id=MAIN, batch_name="注册窗口未开始", register_type="ENROLL", status="OPEN",
            window_start=now + timedelta(minutes=1), window_end=now + timedelta(days=3),
        )
        valid = AaRegistrationBatch(
            tenant_id=MAIN, batch_name="注册窗口开放", register_type="ENROLL", status="OPEN",
            window_start=now - timedelta(days=1), window_end=now + timedelta(days=1),
        )
        defer_batch = AaRegistrationBatch(
            tenant_id=MAIN, batch_name="注册暂缓窗口开放", register_type="ANNUAL", status="OPEN",
            window_start=now - timedelta(days=1), window_end=now + timedelta(days=1),
        )
        page_batches = [AaRegistrationBatch(
            tenant_id=MAIN, batch_name=f"注册分页批次{index:02d}", register_type="ENROLL", status="OPEN",
            window_start=now - timedelta(days=1), window_end=now + timedelta(days=1),
        ) for index in range(38)]
        foreign = AaRegistrationBatch(
            tenant_id=foreign_tenant, batch_name="外校注册批次", register_type="ENROLL", status="OPEN",
        )
        db.add_all([student, defer_student, expired, future, valid, defer_batch, *page_batches, foreign])
        db.flush()
        # 同一批次的另一名学生已注册，不能因 URL 参数而显示为当前学生的结果。
        db.add(AaRegistration(
            tenant_id=MAIN, batch_id=valid.id, student_id=defer_student.id, status="REGISTERED",
        ))
        db.commit()
        ids = {
            "student": int(student.id), "expired": int(expired.id), "future": int(future.id),
            "valid": int(valid.id), "defer": int(defer_batch.id), "foreign": int(foreign.id),
        }
    finally:
        db.close()

    student_headers = _stu_token("注册窗口学生", "CR0033")
    first = client.get(f"{BASE}/registration/my", headers=student_headers, params={
        "page": 1, "pageSize": 20, "studentId": "not-my-id",
    }).json()
    assert first["code"] == 0
    first_data = first["data"]
    assert first_data["page"] == 1 and first_data["pageSize"] == 20
    assert first_data["total"] == 42 and first_data["hasMore"] is True
    assert len(first_data["batches"]) == 20
    assert first_data["realName"] == "注册窗口学生"

    second = client.get(f"{BASE}/registration/my", headers=student_headers, params={"page": 2, "pageSize": 20}).json()["data"]
    third = client.get(f"{BASE}/registration/my", headers=student_headers, params={"page": 3, "pageSize": 20}).json()["data"]
    assert (len(second["batches"]), len(third["batches"])) == (20, 2)
    assert third["hasMore"] is False

    expired_read = client.get(f"{BASE}/registration/my", headers=student_headers, params={"batchId": ids["expired"]}).json()["data"]
    assert expired_read["total"] == 1
    assert expired_read["batches"][0]["windowStatus"] == "EXPIRED"
    assert expired_read["batches"][0]["canRegister"] is False
    assert "窗口已结束" in expired_read["batches"][0]["blockReason"]
    assert client.post(f"{BASE}/registration/{ids['expired']}/register", headers=student_headers).status_code == 409
    assert client.post(f"{BASE}/registration/{ids['expired']}/defer", headers=student_headers, json={
        "reason": "窗口已经结束不能绕过学校时间限制", "requestedUntil": "2026-12-01",
    }).status_code == 409
    assert client.post(f"{BASE}/registration/{ids['future']}/register", headers=student_headers).status_code == 409

    # 先读取再写的旧页面也不能越过窗口；开放批次则仍由同一正式命令写入学籍与审计。
    registered = client.post(f"{BASE}/registration/{ids['valid']}/register", headers=student_headers)
    assert registered.status_code == 200, registered.text
    assert registered.json()["data"]["studentStatus"] == "REGISTERED"
    valid_read = client.get(f"{BASE}/registration/my", headers=student_headers, params={"batchId": ids["valid"]}).json()["data"]
    assert valid_read["batches"][0]["registrationStatus"] == "REGISTERED"
    assert valid_read["batches"][0]["registrationId"] == registered.json()["data"]["registrationId"]

    defer_headers = _stu_token("注册暂缓学生", "CR0034")
    deferred = client.post(f"{BASE}/registration/{ids['defer']}/defer", headers=defer_headers, json={
        "reason": "因家庭突发情况申请暂缓注册", "requestedUntil": "2026-12-01",
    })
    assert deferred.status_code == 200, deferred.text
    with get_sessionmaker()() as verify:
        registrations = verify.query(AaRegistration).filter(
            AaRegistration.tenant_id == MAIN, AaRegistration.batch_id == ids["valid"],
            AaRegistration.student_id == ids["student"], AaRegistration.is_deleted.is_(False),
        ).all()
        deferrals = verify.query(AaRegistrationDeferral).filter(
            AaRegistrationDeferral.tenant_id == MAIN, AaRegistrationDeferral.batch_id == ids["defer"],
            AaRegistrationDeferral.status == "PENDING", AaRegistrationDeferral.is_deleted.is_(False),
        ).all()
        audits = verify.query(AffairsAuditTrail).filter(
            AffairsAuditTrail.tenant_id == MAIN,
            AffairsAuditTrail.biz_type.in_(("AA_REGISTRATION", "AA_REG_DEFERRAL")),
        ).all()
    assert len(registrations) == 1
    assert len(deferrals) == 1
    assert {audit.action for audit in audits} >= {"REGISTER", "SELF_APPLY"}

    foreign_read = client.get(f"{BASE}/registration/my", headers=student_headers, params={"batchId": ids["foreign"]}).json()["data"]
    assert foreign_read["total"] == 0 and foreign_read["batches"] == []
    assert client.post(f"{BASE}/registration/{ids['foreign']}/register", headers=student_headers).status_code == 404


def test_registration_mobile_routes_reject_teacher_and_legacy_mobile_client(client, db_mode):
    """注册本人读取与两类写入都只能走学生 H5/小程序会话。"""
    from app.core.security import create_access_token

    _seed_student("CR0035", "注册权限学生")
    teacher = {"Authorization": "Bearer " + create_access_token({
        "userId": "t-registration", "realName": "教师", "userType": "TEACHER",
        "tid": "demo", "tenantId": str(MAIN), "activeContextId": "ctx",
        "currentRoleCode": "TEACHER", "clientType": "TEACHER_MINI",
    })}
    old_mobile = _stu_token("注册权限学生", "CR0035", client_type="MP")
    for method, path, body in (
        ("get", "/registration/my", None),
        ("post", "/registration/1/register", {}),
        ("post", "/registration/1/defer", {"reason": "越权测试"}),
    ):
        request = getattr(client, method)
        kwargs = {"headers": teacher}
        if method == "post":
            kwargs["json"] = body
        assert request(BASE + path, **kwargs).status_code == 403
        kwargs["headers"] = old_mobile
        assert request(BASE + path, **kwargs).status_code == 403
    assert client.get(f"{BASE}/registration/my", headers=_stu_token("注册权限学生", "CR0035", client_type="STUDENT_PC")).status_code == 200


def test_student_academic_mobile_routes_use_the_strict_student_client_gate():
    """学生专用教务 URL 不能因某一页漏写 Depends 而被教师/旧泛移动会话调用。"""
    from pathlib import Path

    source = (Path(__file__).resolve().parents[1] / "app" / "api" / "v1" / "mobile.py").read_text(encoding="utf-8")
    student_section = source[source.index('@router.get("/academic/schedule/my"'):source.index('@router.get("/teacher/academic/grade-tasks"')]
    assert "Depends(get_current_user)" not in student_section
    assert student_section.count("Depends(require_mobile_student)") >= 35


def test_student_exam_v2_routes_use_the_strict_student_client_gate(client, db_mode):
    """考试/缓考 v2 是学生小程序页面，不能因独立 router 漏掉已签发端类型校验。"""
    from app.core.security import create_access_token

    _seed_student("CR0036", "考试权限学生")
    teacher = {"Authorization": "Bearer " + create_access_token({
        "userId": "t-exam-v2", "realName": "教师", "userType": "TEACHER",
        "tid": "demo", "tenantId": str(MAIN), "activeContextId": "ctx",
        "currentRoleCode": "TEACHER", "clientType": "TEACHER_MINI",
    })}
    old_mobile = _stu_token("考试权限学生", "CR0036", client_type="MP")
    strict_mini = _stu_token("考试权限学生", "CR0036")
    h5_mobile = _stu_token("考试权限学生", "CR0036", client_type="STUDENT_PC")
    base = "/api/v1/mobile/academic/exam-v2"
    for method, path, body in (
        ("get", "/my", None),
        ("get", "/defer-options", None),
        ("post", "/defer/apply", {}),
    ):
        request = getattr(client, method)
        kwargs = {} if method == "get" else {"json": body}
        assert request(base + path, headers=teacher, **kwargs).status_code == 403
        assert request(base + path, headers=old_mobile, **kwargs).status_code == 403
    assert client.get(f"{base}/my", headers=strict_mini).status_code == 200
    assert client.get(f"{base}/my", headers=h5_mobile).status_code == 200


def test_selection_courses_and_my_selections_no_data_not_500(client, db_mode):
    _seed_student("CR0005", "选课测生")
    hdr = _stu_token("选课测生", "CR0005")
    courses = client.get(f"{BASE}/selection/courses", headers=hdr).json()
    assert courses["code"] == 0 and courses["data"] == []
    mine = client.get(f"{BASE}/selection/my", headers=hdr).json()
    assert mine["code"] == 0 and mine["data"] == []


def test_selection_enroll_requires_selection_course_id(client, db_mode):
    _seed_student("CR0006", "选课测生2")
    hdr = _stu_token("选课测生2", "CR0006")
    bad = client.post(f"{BASE}/selection/enroll", headers=hdr, json={}).json()
    assert bad["code"] != 0


def test_new_academic_endpoints_require_login(client):
    for path in ("/credits/my", "/warning/my", "/makeup/my", "/selection/courses", "/selection/my"):
        assert client.get(BASE + path).json()["code"] == 401001
