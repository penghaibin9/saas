"""移动学生端·新增自助接口(成绩认定/等级考试报名/专业分流志愿)端到端测试。

验证:学生 token 经 /mobile/academic/* 委托到域 service 真能跑通(不是只 200);
空数据不 500;提交真落库;跨教务处管理端可见。MySQL-only(db_mode 夹具)。
"""
from __future__ import annotations

BASE = "/api/v1/mobile/academic"
ADMIN_BASE = "/api/v1/academic-affairs"
MAIN = 1000000000000000001


def _stu_token(real_name, student_no, *, client_type="STUDENT_MINI", user_type="STUDENT"):
    from app.core.security import create_access_token
    return {"Authorization": "Bearer " + create_access_token({
        "userId": f"u-{student_no}", "realName": real_name, "userType": user_type,
        "studentNo": student_no, "tid": "demo", "tenantId": str(MAIN),
        "activeContextId": "ctx", "currentRoleCode": user_type, "clientType": client_type})}


def _admin(client):
    data = client.post("/api/v1/auth/mock-login",
                       json={"loginName": "school_admin01", "password": "any"}).json()["data"]
    return {"Authorization": f"Bearer {data['accessToken']}"}


def _seed_student(student_no, real_name, grade="2026", major_id=None, class_id=None):
    from app.db.session import get_sessionmaker
    from app.models import StudentProfile
    db = get_sessionmaker()()
    db.add(StudentProfile(tenant_id=MAIN, student_no=student_no, real_name=real_name,
                          grade=grade, major_id=major_id, class_id=class_id,
                          current_stage="ON_CAMPUS", student_status="NORMAL", status="ACTIVE"))
    db.commit(); db.close()


def _seed_target_course(client, admin):
    response = client.post(f"{ADMIN_BASE}/courses", headers=admin, json={
        "courseCode": "RG101", "courseName": "高等数学",
        "category": "MAJOR_CORE", "nature": "REQUIRED", "credit": 4,
        "hoursTotal": 64, "hoursTheory": 48, "hoursPractice": 16,
        "examMode": "EXAM",
    })
    assert response.status_code == 200, response.text
    return response.json()["data"]["courseId"]


# ── 成绩认定 ──

def test_recognition_my_empty_not_500(client, db_mode):
    _seed_student("RG0001", "认定测生")
    r = client.get(f"{BASE}/recognition/my", headers=_stu_token("认定测生", "RG0001")).json()
    assert r["code"] == 0 and r["data"]["items"] == []


def test_recognition_submit_and_visible_to_admin(client, db_mode):
    _seed_student("RG0002", "认定乙")
    hdr = _stu_token("认定乙", "RG0002")
    admin = _admin(client)
    target_course_id = _seed_target_course(client, admin)
    # 低分拦截（即使目标课程合法，低分仍必须被业务规则拒绝）
    bad = client.post(f"{BASE}/recognition/submit", headers=hdr,
                      json={"sourceCourseName": "高数A", "sourceScore": 50,
                            "targetCourseId": str(target_course_id),
                            "targetCourseName": "高等数学"})
    assert bad.status_code == 400, bad.text
    # 正常提交
    ok = client.post(f"{BASE}/recognition/submit", headers=hdr,
                     json={"sourceCourseName": "高数A", "sourceScore": 82, "sourceCredit": 4,
                           "sourceOrigin": "原电子专业",
                           "targetCourseId": str(target_course_id),
                           "targetCourseName": "高等数学", "reason": "转专业替代"})
    assert ok.status_code == 200, ok.text
    my = client.get(f"{BASE}/recognition/my", headers=hdr).json()["data"]["items"]
    assert len(my) == 1 and my[0]["status"] == "SUBMITTED"
    # 教务处管理端可见同一条
    admin_list = client.get(f"{ADMIN_BASE}/grade-recognitions", headers=_admin(client)).json()["data"]
    assert any(x["studentNo"] == "RG0002" for x in admin_list["items"])


def test_recognition_my_is_server_paged_and_mini_scoped(client, db_mode):
    """42 条本人历史按页返回；另一学生和教师小程序令牌均不能读到本人记录。"""
    from app.core.security import create_access_token
    from app.db.session import get_sessionmaker
    from app.models import AaGradeRecognition, StudentProfile

    _seed_student("RGPG001", "认定分页甲")
    _seed_student("RGPG002", "认定分页乙")
    db = get_sessionmaker()()
    try:
        owner = db.query(StudentProfile).filter(
            StudentProfile.tenant_id == MAIN, StudentProfile.student_no == "RGPG001"
        ).one()
        other = db.query(StudentProfile).filter(
            StudentProfile.tenant_id == MAIN, StudentProfile.student_no == "RGPG002"
        ).one()
        for index in range(42):
            db.add(AaGradeRecognition(
                tenant_id=MAIN, student_id=owner.id, student_no=owner.student_no,
                student_name=owner.real_name, source_course_name=f"原课程{index:02d}",
                source_score=80, target_course_name=f"目标课程{index:02d}",
                status="REJECTED", review_reason="请补充学校认可的成绩证明材料",
            ))
        db.add(AaGradeRecognition(
            tenant_id=MAIN, student_id=other.id, student_no=other.student_no,
            student_name=other.real_name, source_course_name="乙同学课程",
            source_score=80, target_course_name="乙同学目标课程", status="REJECTED",
        ))
        db.commit()
    finally:
        db.close()

    owner_headers = _stu_token("认定分页甲", "RGPG001")
    pages = [client.get(f"{BASE}/recognition/my?page={page}&pageSize=20", headers=owner_headers)
             for page in (1, 2, 3)]
    assert all(response.status_code == 200 for response in pages)
    data = [response.json()["data"] for response in pages]
    assert [(item["page"], item["pageSize"], item["total"], item["hasMore"], len(item["items"])) for item in data] == [
        (1, 20, 42, True, 20), (2, 20, 42, True, 20), (3, 20, 42, False, 2),
    ]
    ids = [{row["recognitionId"] for row in item["items"]} for item in data]
    assert ids[0].isdisjoint(ids[1]) and ids[0].isdisjoint(ids[2]) and ids[1].isdisjoint(ids[2])
    other_data = client.get(f"{BASE}/recognition/my?page=1&pageSize=20",
                            headers=_stu_token("认定分页乙", "RGPG002")).json()["data"]
    assert other_data["total"] == 1
    teacher_headers = {"Authorization": "Bearer " + create_access_token({
        "userId": "t-recognition", "realName": "教师", "userType": "TEACHER",
        "tid": "demo", "tenantId": str(MAIN), "activeContextId": "ctx",
        "currentRoleCode": "TEACHER", "clientType": "TEACHER_MINI",
    })}
    assert client.get(f"{BASE}/recognition/my", headers=teacher_headers).status_code == 403


# ── 等级考试报名 ──

def test_level_exam_my_empty_and_register_flow(client, db_mode):
    _seed_student("LV0001", "考级测生")
    admin = _admin(client)
    hdr = _stu_token("考级测生", "LV0001")
    # 空
    r0 = client.get(f"{BASE}/level-exam/my", headers=hdr).json()["data"]
    assert r0["openExams"] == [] and r0["myRegs"] == []
    # 教务处建考试并开放
    eid = client.post(f"{ADMIN_BASE}/level-exams", headers=admin,
                      json={"examName": "四级(移动)", "category": "CET", "level": "四级",
                            "fee": 30, "passLine": 425}).json()["data"]["examId"]
    client.post(f"{ADMIN_BASE}/level-exams/{eid}/transition?action=OPEN", headers=admin)
    # 学生看到并报名
    d = client.get(f"{BASE}/level-exam/my", headers=hdr).json()["data"]
    assert len(d["openExams"]) == 1
    reg = client.post(f"{BASE}/level-exam/{eid}/register", headers=hdr)
    assert reg.status_code == 200, reg.text
    # 同一学生重复点击/重试不能产生第二条正式报名。
    duplicate = client.post(f"{BASE}/level-exam/{eid}/register", headers=hdr)
    assert duplicate.status_code == 409, duplicate.text
    d2 = client.get(f"{BASE}/level-exam/my", headers=hdr).json()["data"]
    assert len(d2["myRegs"]) == 1 and d2["myRegs"][0]["status"] == "REGISTERED"
    # 取消
    assert client.post(f"{BASE}/level-exam/{eid}/cancel", headers=hdr).status_code == 200


def test_level_exam_mobile_reads_are_paged_named_and_student_scoped(client, db_mode):
    """开放考试、本人历史各自分页；历史名称不能因当前页缺席而丢失。"""
    from app.core.security import create_access_token
    from app.db.session import get_sessionmaker
    from app.models import AaLevelExam, AaLevelExamReg, StudentProfile

    _seed_student("LVPG001", "考级分页甲")
    _seed_student("LVPG002", "考级分页乙")
    db = get_sessionmaker()()
    try:
        owner = db.query(StudentProfile).filter(
            StudentProfile.tenant_id == MAIN, StudentProfile.student_no == "LVPG001"
        ).one()
        other = db.query(StudentProfile).filter(
            StudentProfile.tenant_id == MAIN, StudentProfile.student_no == "LVPG002"
        ).one()
        histories = []
        for index in range(42):
            db.add(AaLevelExam(
                tenant_id=MAIN, exam_name=f"移动开放考试{index:02d}", category="SKILL",
                status="OPEN",
            ))
        for index in range(42):
            exam = AaLevelExam(
                tenant_id=MAIN, exam_name=f"移动历史考试{index:02d}", category="CET",
                status="FINISHED",
            )
            db.add(exam)
            histories.append(exam)
        db.flush()
        for exam in histories:
            db.add(AaLevelExamReg(
                tenant_id=MAIN, exam_id=exam.id, student_id=owner.id,
                student_no=owner.student_no, student_name=owner.real_name,
                fee_status="PAID", status="SCORED", result="PASS", score=430,
            ))
        db.add(AaLevelExamReg(
            tenant_id=MAIN, exam_id=histories[0].id, student_id=other.id,
            student_no=other.student_no, student_name=other.real_name,
            fee_status="PAID", status="SCORED", result="PASS", score=430,
        ))
        db.commit()
    finally:
        db.close()

    owner_headers = _stu_token("考级分页甲", "LVPG001")
    pages = [client.get(
        f"{BASE}/level-exam/my?openPage={page}&openPageSize=20&registrationPage={page}&registrationPageSize=20",
        headers=owner_headers,
    ) for page in (1, 2, 3)]
    assert all(response.status_code == 200 for response in pages)
    data = [response.json()["data"] for response in pages]
    assert [(row["openPagination"]["page"], row["openPagination"]["pageSize"], row["openPagination"]["total"], row["openPagination"]["hasMore"], len(row["openExams"])) for row in data] == [
        (1, 20, 42, True, 20), (2, 20, 42, True, 20), (3, 20, 42, False, 2),
    ]
    assert [(row["registrationPagination"]["page"], row["registrationPagination"]["pageSize"], row["registrationPagination"]["total"], row["registrationPagination"]["hasMore"], len(row["myRegs"])) for row in data] == [
        (1, 20, 42, True, 20), (2, 20, 42, True, 20), (3, 20, 42, False, 2),
    ]
    open_ids = [{row["examId"] for row in item["openExams"]} for item in data]
    registration_ids = [{row["regId"] for row in item["myRegs"]} for item in data]
    assert open_ids[0].isdisjoint(open_ids[1]) and open_ids[0].isdisjoint(open_ids[2]) and open_ids[1].isdisjoint(open_ids[2])
    assert registration_ids[0].isdisjoint(registration_ids[1]) and registration_ids[0].isdisjoint(registration_ids[2]) and registration_ids[1].isdisjoint(registration_ids[2])
    assert all(str(row["examName"]).startswith("移动历史考试") for row in data[2]["myRegs"])
    other_data = client.get(f"{BASE}/level-exam/my", headers=_stu_token("考级分页乙", "LVPG002")).json()["data"]
    assert other_data["registrationPagination"]["total"] == 1
    teacher_headers = {"Authorization": "Bearer " + create_access_token({
        "userId": "t-level", "realName": "教师", "userType": "TEACHER",
        "tid": "demo", "tenantId": str(MAIN), "activeContextId": "ctx",
        "currentRoleCode": "TEACHER", "clientType": "TEACHER_MINI",
    })}
    assert client.get(f"{BASE}/level-exam/my", headers=teacher_headers).status_code == 403


# ── 专业分流志愿 ──

def _seed_split(client):
    from app.db.session import get_sessionmaker
    from app.models import College, Major, SchoolClass
    db = get_sessionmaker()()
    col = College(tenant_id=MAIN, college_name="信息学院", status="ACTIVE"); db.add(col); db.flush()
    src = Major(tenant_id=MAIN, college_id=col.id, major_name="电子大类", status="ACTIVE")
    ma = Major(tenant_id=MAIN, college_id=col.id, major_name="软件技术", status="ACTIVE")
    mb = Major(tenant_id=MAIN, college_id=col.id, major_name="网络技术", status="ACTIVE")
    db.add_all([src, ma, mb]); db.flush()
    kls = SchoolClass(tenant_id=MAIN, major_id=src.id, class_name="电信26", grade="2026", status="ACTIVE")
    db.add(kls); db.flush()
    ids = {"src": src.id, "ma": ma.id, "mb": mb.id, "class": kls.id}
    db.commit(); db.close()
    return ids


def test_major_split_view_and_submit(client, db_mode):
    ids = _seed_split(client)
    _seed_student("MS0001", "分流测生", grade="2026", major_id=ids["src"], class_id=ids["class"])
    admin = _admin(client)
    hdr = _stu_token("分流测生", "MS0001")
    # 教务处建分流批次+专业+开放
    bid = client.post(f"{ADMIN_BASE}/major-split/batches", headers=admin,
                      json={"batchName": "2026电子分流", "grade": "2026",
                            "sourceMajorId": str(ids["src"]), "maxChoices": 2}).json()["data"]["batchId"]
    client.post(f"{ADMIN_BASE}/major-split/batches/{bid}/options", headers=admin,
                json={"majorId": str(ids["ma"]), "capacity": 30})
    client.post(f"{ADMIN_BASE}/major-split/batches/{bid}/options", headers=admin,
                json={"majorId": str(ids["mb"]), "capacity": 30})
    client.post(f"{ADMIN_BASE}/major-split/batches/{bid}/open", headers=admin)
    # 学生看到开放批次（含可选专业）
    d = client.get(f"{BASE}/major-split/my", headers=hdr).json()["data"]
    assert len(d["openBatches"]) == 1
    options = client.get(f"{BASE}/major-split/{bid}/options", headers=hdr).json()["data"]
    assert len(options["items"]) == 2
    # 提交志愿
    r = client.post(f"{BASE}/major-split/submit", headers=hdr,
                    json={"batchId": bid, "choices": [str(ids["ma"]), str(ids["mb"])]})
    assert r.status_code == 200, r.text
    # 同一命令的双击/网络重试只回读同一条志愿，不能再写审计。
    repeated = client.post(f"{BASE}/major-split/submit", headers=hdr,
                           json={"batchId": bid, "choices": [str(ids["ma"]), str(ids["mb"])]})
    assert repeated.status_code == 200, repeated.text
    assert repeated.json()["data"]["volunteerId"] == r.json()["data"]["volunteerId"]
    d2 = client.get(f"{BASE}/major-split/my", headers=hdr).json()["data"]
    assert len(d2["myVolunteers"]) == 1
    assert [str(x) for x in d2["myVolunteers"][0]["choices"]] == [str(ids["ma"]), str(ids["mb"])]
    from app.db.session import get_sessionmaker
    from app.models import AffairsAuditTrail
    db = get_sessionmaker()()
    try:
        assert db.query(AffairsAuditTrail).filter(
            AffairsAuditTrail.tenant_id == MAIN,
            AffairsAuditTrail.biz_type == "AA_MAJOR_SPLIT",
            AffairsAuditTrail.biz_id == int(bid),
            AffairsAuditTrail.action == "SPLIT_VOLUNTEER_SUBMIT",
        ).count() == 1
    finally:
        db.close()
    # 旧页面在管理员截止之后再次提交，必须由服务端状态机拒绝。
    assert client.post(f"{ADMIN_BASE}/major-split/batches/{bid}/close", headers=admin).status_code == 200
    stale = client.post(f"{BASE}/major-split/submit", headers=hdr,
                        json={"batchId": bid, "choices": [str(ids["ma"])]})
    assert stale.status_code == 409, stale.text


def test_major_split_mobile_reads_are_paged_snapshotted_and_student_scoped(client, db_mode):
    """开放批次、可选专业、本人历史各自服务端分页，且历史名称不会随专业改名漂移。"""
    import json

    from app.core.security import create_access_token
    from app.db.session import get_sessionmaker
    from app.models import AaMajorSplitBatch, AaMajorSplitOption, AaMajorSplitVolunteer, Major, StudentProfile

    ids = _seed_split(client)
    _seed_student("MSPG001", "分流分页甲", grade="2026", major_id=ids["src"], class_id=ids["class"])
    _seed_student("MSPG002", "分流分页乙", grade="2026", major_id=ids["src"], class_id=ids["class"])
    db = get_sessionmaker()()
    try:
        owner = db.query(StudentProfile).filter(
            StudentProfile.tenant_id == MAIN, StudentProfile.student_no == "MSPG001"
        ).one()
        other = db.query(StudentProfile).filter(
            StudentProfile.tenant_id == MAIN, StudentProfile.student_no == "MSPG002"
        ).one()
        template_major = db.get(Major, ids["ma"])
        target_majors = [template_major]
        for index in range(41):
            target = Major(
                tenant_id=MAIN, college_id=template_major.college_id,
                major_name=f"移动分流可选专业{index:02d}", status="ACTIVE",
            )
            db.add(target)
            target_majors.append(target)
        db.flush()

        rich_open = AaMajorSplitBatch(
            tenant_id=MAIN, batch_name="移动分流开放批次-选项分页", grade="2026",
            source_major_id=ids["src"], max_choices=3, status="OPEN",
        )
        db.add(rich_open)
        db.flush()
        for index, major in enumerate(target_majors):
            db.add(AaMajorSplitOption(
                tenant_id=MAIN, batch_id=rich_open.id, major_id=major.id,
                major_name=f"移动可选专业快照{index:02d}", capacity=30,
            ))
        # 与一个学生有关的开放批次共 42 条，不能由页面一次性加载后再切页。
        for index in range(41):
            batch = AaMajorSplitBatch(
                tenant_id=MAIN, batch_name=f"移动分流开放批次{index:02d}", grade="2026",
                source_major_id=ids["src"], max_choices=1, status="OPEN",
            )
            db.add(batch)
            db.flush()
            db.add(AaMajorSplitOption(
                tenant_id=MAIN, batch_id=batch.id, major_id=template_major.id,
                major_name="软件技术历史快照", capacity=30,
            ))

        historic_batches = []
        for index in range(42):
            batch = AaMajorSplitBatch(
                tenant_id=MAIN, batch_name=f"移动分流历史批次{index:02d}", grade="2026",
                source_major_id=ids["src"], max_choices=1, status="CLOSED",
            )
            db.add(batch)
            db.flush()
            db.add(AaMajorSplitOption(
                tenant_id=MAIN, batch_id=batch.id, major_id=template_major.id,
                major_name=f"历史快照专业{index:02d}", capacity=30,
            ))
            db.add(AaMajorSplitVolunteer(
                tenant_id=MAIN, batch_id=batch.id, student_id=owner.id,
                student_no=owner.student_no, student_name=owner.real_name,
                choices_json=json.dumps([template_major.id]), status="ALLOCATED",
                result_major_id=template_major.id, result_choice_rank=1,
            ))
            historic_batches.append(batch)
        # 乙同学只能读自己的历史志愿。
        db.add(AaMajorSplitVolunteer(
            tenant_id=MAIN, batch_id=historic_batches[0].id, student_id=other.id,
            student_no=other.student_no, student_name=other.real_name,
            choices_json=json.dumps([template_major.id]), status="PENDING",
        ))
        template_major.major_name = "当前专业名称已变更"
        db.commit()
        rich_open_id = str(rich_open.id)
    finally:
        db.close()

    owner_headers = _stu_token("分流分页甲", "MSPG001")
    pages = [client.get(
        f"{BASE}/major-split/my?openPage={page}&openPageSize=20&volunteerPage={page}&volunteerPageSize=20",
        headers=owner_headers,
    ) for page in (1, 2, 3)]
    assert all(response.status_code == 200 for response in pages)
    data = [response.json()["data"] for response in pages]
    assert [(row["openPagination"]["page"], row["openPagination"]["pageSize"], row["openPagination"]["total"], row["openPagination"]["hasMore"], len(row["openBatches"])) for row in data] == [
        (1, 20, 42, True, 20), (2, 20, 42, True, 20), (3, 20, 42, False, 2),
    ]
    assert [(row["volunteerPagination"]["page"], row["volunteerPagination"]["pageSize"], row["volunteerPagination"]["total"], row["volunteerPagination"]["hasMore"], len(row["myVolunteers"])) for row in data] == [
        (1, 20, 42, True, 20), (2, 20, 42, True, 20), (3, 20, 42, False, 2),
    ]
    open_ids = [{row["batchId"] for row in item["openBatches"]} for item in data]
    volunteer_ids = [{row["volunteerId"] for row in item["myVolunteers"]} for item in data]
    assert open_ids[0].isdisjoint(open_ids[1]) and open_ids[0].isdisjoint(open_ids[2]) and open_ids[1].isdisjoint(open_ids[2])
    assert volunteer_ids[0].isdisjoint(volunteer_ids[1]) and volunteer_ids[0].isdisjoint(volunteer_ids[2]) and volunteer_ids[1].isdisjoint(volunteer_ids[2])
    assert all(row["choiceNames"][0].startswith("历史快照专业") for row in data[2]["myVolunteers"])
    assert all(row["resultMajorName"].startswith("历史快照专业") for row in data[2]["myVolunteers"])
    assert all(row["statusLabel"] == "已分配专业，等待学校确认" for row in data[2]["myVolunteers"])

    option_pages = [client.get(
        f"{BASE}/major-split/{rich_open_id}/options?page={page}&pageSize=20&keyword=移动可选专业快照",
        headers=owner_headers,
    ) for page in (1, 2, 3)]
    assert all(response.status_code == 200 for response in option_pages)
    options = [response.json()["data"] for response in option_pages]
    assert [(row["page"], row["pageSize"], row["total"], row["hasMore"], len(row["items"])) for row in options] == [
        (1, 20, 42, True, 20), (2, 20, 42, True, 20), (3, 20, 42, False, 2),
    ]
    option_ids = [{row["optionId"] for row in item["items"]} for item in options]
    assert option_ids[0].isdisjoint(option_ids[1]) and option_ids[0].isdisjoint(option_ids[2]) and option_ids[1].isdisjoint(option_ids[2])

    other = client.get(f"{BASE}/major-split/my", headers=_stu_token("分流分页乙", "MSPG002")).json()["data"]
    assert other["volunteerPagination"]["total"] == 1
    teacher_headers = {"Authorization": "Bearer " + create_access_token({
        "userId": "t-major-split", "realName": "教师", "userType": "TEACHER",
        "tid": "demo", "tenantId": str(MAIN), "activeContextId": "ctx",
        "currentRoleCode": "TEACHER", "clientType": "TEACHER_MINI",
    })}
    old_mobile_headers = _stu_token("分流分页甲", "MSPG001", client_type="MP")
    assert client.get(f"{BASE}/major-split/my", headers=teacher_headers).status_code == 403
    assert client.get(f"{BASE}/major-split/{rich_open_id}/options", headers=teacher_headers).status_code == 403
    assert client.get(f"{BASE}/major-split/my", headers=old_mobile_headers).status_code == 403
