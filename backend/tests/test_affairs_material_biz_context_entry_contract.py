"""V5-C8 材料登记去手工 bizId/itemCode 合同（真实 DB 模式）。

登记材料缺项此前要求老师理解并手填：
    bizType + bizId（数据库业务记录主键）+ itemCode（工程材料编码）+ itemName
其中 bizId 要从申请详情"复制记录ID"粘过来，itemCode 全靠猜。
这不是正常学校老师该维护的内容：易填错、难培训、难销售。

本合同锁住两个只读入口：
1. biz-context：按 bizType+bizId 解析"这是哪一笔业务、哪个学生"，
   供业务详情页深链预填；授权与范围校验必须和登记材料完全一致，
   越权一律按"不存在"处理，不得成为探测其它业务记录的旁路。
2. item-suggestions：列出本校该业务域**已经真实用过**的材料项。
   刻意不引入"标准材料项目录"——学工域没有这张表，标准材料项属于学校
   自己的业务政策，不能由系统编造。
"""
from __future__ import annotations

TID = 1000000000000000001


# 登录接口有限流（每 IP 每分钟 10 次）。同一登录名在本文件内复用令牌，
# 否则多个用例合并跑时会撞上 RATE_LIMITED，表现为 data=None 的 TypeError。
_TOKENS: dict[str, str] = {}


def _hdr(client, login_name):
    token = _TOKENS.get(login_name)
    if not token:
        body = client.post("/api/v1/auth/mock-login",
                           json={"loginName": login_name, "password": "any"}).json()
        assert body.get("code") == 0, f"登录失败：{body}"
        token = body["data"]["accessToken"]
        _TOKENS[login_name] = token
    return {"Authorization": f"Bearer {token}"}


def _seed(db_mode):
    from datetime import datetime
    from app.db.session import get_sessionmaker
    from app.models import (
        College, DisciplineCase, Major, PsyReferral, SchoolClass, StudentProfile,
    )
    from app.models.affairs_operations import AffairsMaterialRequirement

    db = get_sessionmaker()()

    college = College(tenant_id=TID, college_name="C8材料学院",
                      code="C8-COLLEGE", status="ACTIVE")
    db.add(college)
    db.flush()
    major = Major(tenant_id=TID, college_id=college.id, major_name="C8材料专业",
                  code="C8-MAJOR", status="ACTIVE")
    db.add(major)
    db.flush()
    klass = SchoolClass(tenant_id=TID, major_id=major.id, class_name="机电2402",
                        grade="2024", status="ACTIVE")
    db.add(klass)
    db.flush()
    student = StudentProfile(tenant_id=TID, student_no="202600456", real_name="李四",
                             class_id=klass.id, college_id=college.id, gender="F",
                             current_stage="CAMPUS", student_status="NORMAL", status="ACTIVE")
    db.add(student)
    db.flush()

    case = DisciplineCase(tenant_id=TID, student_id=student.id, disc_type="WARNING",
                          reason="违纪事实", doc_no="学工处分〔2026〕18号",
                          decide_date=datetime(2026, 5, 20), status="REGISTERED")
    referral = PsyReferral(tenant_id=TID, student_id=student.id, level="FOCUS",
                           channel="校内咨询", reason_summary="C8敏感事由不得外泄",
                           note="C8涉密明细不得外泄", status="REFERRED")
    db.add_all([case, referral])
    db.flush()

    # 已用过的材料项：DISC_PROOF 用两次、EXTRA_PROOF 用一次 → 建议按使用次数排序
    for idx, code in enumerate(("DISC_PROOF", "DISC_PROOF", "EXTRA_PROOF")):
        db.add(AffairsMaterialRequirement(
            tenant_id=TID, student_id=student.id, biz_type="DISCIPLINE",
            biz_id=case.id + idx, item_code=code,
            item_name="情况说明" if code == "DISC_PROOF" else "补充证明",
            requirement_reason="C8 合同用例", status="MISSING",
            sensitivity_level="SENSITIVE", material_scope="BUSINESS_SCOPE",
        ))
    db.commit()
    ids = {"student": student.id, "case": case.id, "referral": referral.id}
    db.close()
    return ids


def _biz_context(client, hdr, biz_type, biz_id):
    return client.get("/api/v1/student-affairs/material-center/biz-context",
                      headers=hdr, params={"bizType": biz_type, "bizId": biz_id})


def _suggestions(client, hdr, biz_type):
    return client.get("/api/v1/student-affairs/material-center/item-suggestions",
                      headers=hdr, params={"bizType": biz_type})


def test_biz_context_resolves_student_and_business_without_manual_ids(client, db_mode):
    """核心：给 bizType+bizId，系统自己说清是哪个学生、哪一笔业务。"""
    ids = _seed(db_mode)
    hdr = _hdr(client, "school_admin01")
    response = _biz_context(client, hdr, "DISCIPLINE", ids["case"])
    assert response.status_code == 200, response.text
    data = response.json()["data"]

    assert data["bizType"] == "DISCIPLINE"
    assert data["bizId"] == str(ids["case"])
    assert data["studentId"] == str(ids["student"])
    ctx = data["businessContext"]
    assert ctx["studentName"] == "李四", ctx
    assert ctx["studentNo"] == "202600456", ctx
    assert ctx["className"] == "机电2402", ctx
    assert ctx["bizDisplayTitle"] == "违纪处分", ctx
    assert ctx["bizDisplaySubtitle"] == "学工处分〔2026〕18号", ctx


def test_biz_context_is_not_an_existence_probe(client, db_mode):
    """不存在的记录必须按"不存在"回，不得泄露任何可推断信息。"""
    ids = _seed(db_mode)
    hdr = _hdr(client, "school_admin01")
    missing = _biz_context(client, hdr, "DISCIPLINE", ids["case"] + 999999)
    assert missing.json()["code"] != 0, missing.json()


def test_biz_context_rejects_unsupported_and_invalid_input(client, db_mode):
    """非法业务类型/非法 ID 必须被正式规则挡下，不落到业务表查询。"""
    ids = _seed(db_mode)
    hdr = _hdr(client, "school_admin01")
    assert _biz_context(client, hdr, "NOT_A_BIZ", ids["case"]).json()["code"] != 0
    bad_id = client.get("/api/v1/student-affairs/material-center/biz-context",
                        headers=hdr, params={"bizType": "DISCIPLINE", "bizId": 0})
    assert bad_id.status_code != 200 or bad_id.json()["code"] != 0


def test_biz_context_never_leaks_psychological_detail(client, db_mode):
    """心理转介即使可解析，也只给业务类型，事由与涉密明细一个字都不能带。"""
    ids = _seed(db_mode)
    hdr = _hdr(client, "school_admin01")
    response = _biz_context(client, hdr, "MENTAL", ids["referral"])
    if response.json().get("code") != 0:
        return  # 无心理专项授权时按不存在处理，同样合规
    ctx = response.json()["data"]["businessContext"]
    assert ctx["bizDisplayTitle"] == "心理关注转介", ctx
    assert ctx["bizDisplaySubtitle"] == "", ctx
    blob = str(response.json())
    assert "C8敏感事由不得外泄" not in blob, "转介事由通过 biz-context 泄露"
    assert "C8涉密明细不得外泄" not in blob, "涉密明细通过 biz-context 泄露"


def test_item_suggestions_come_from_real_school_data(client, db_mode):
    """材料项建议必须来自本校真实用过的数据，并按使用次数排序。"""
    _seed(db_mode)
    hdr = _hdr(client, "school_admin01")
    response = _suggestions(client, hdr, "DISCIPLINE")
    assert response.status_code == 200, response.text
    items = response.json()["data"]["items"]
    codes = [x["itemCode"] for x in items]
    assert "DISC_PROOF" in codes and "EXTRA_PROOF" in codes, codes
    by_code = {x["itemCode"]: x for x in items}
    assert by_code["DISC_PROOF"]["usedCount"] == 2, by_code["DISC_PROOF"]
    assert by_code["EXTRA_PROOF"]["usedCount"] == 1, by_code["EXTRA_PROOF"]
    assert codes.index("DISC_PROOF") < codes.index("EXTRA_PROOF"), "应按使用次数降序"
    assert by_code["DISC_PROOF"]["itemName"] == "情况说明"


def test_item_suggestions_do_not_invent_a_catalog(client, db_mode):
    """没用过的业务域必须返回空，绝不能凭空给出一套"标准材料项"。"""
    _seed(db_mode)
    hdr = _hdr(client, "school_admin01")
    response = _suggestions(client, hdr, "DORM_TRANSFER")
    assert response.status_code == 200, response.text
    assert response.json()["data"]["items"] == [], "系统不得编造学校的材料项标准"


def test_item_suggestions_respect_data_scope(client, db_mode):
    """建议也是"候选"，必须过数据范围。

    只按业务权限聚合会把全校用过的材料项和使用次数暴露给只管一个班的辅导员——
    材料项名称本身可能带业务含义，使用次数更是跨范围的聚合信息。
    """
    from app.db.session import get_sessionmaker
    from app.models import (
        AffairsCounselorAssignment, College, Major, Role, SchoolClass,
        StudentProfile, TeacherStudentScope, User, UserRole,
    )
    from app.models.affairs_operations import AffairsMaterialRequirement
    from datetime import datetime, timedelta

    _seed(db_mode)
    db = get_sessionmaker()()
    try:
        counselor = db.query(User).filter_by(tenant_id=TID, login_name="counselor01").first()
        if counselor is None:
            counselor = User(tenant_id=TID, login_name="counselor01", real_name="王莉",
                             password_hash="test-hash", user_type="TEACHER", status="ACTIVE")
            db.add(counselor)
            db.flush()
        role = db.query(Role).filter_by(tenant_id=TID, role_code="COUNSELOR").first()
        if role is None:
            role = Role(tenant_id=TID, role_code="COUNSELOR", role_name="辅导员",
                        role_type="SYSTEM", status="ACTIVE")
            db.add(role)
            db.flush()
        if db.query(UserRole).filter_by(tenant_id=TID, user_id=counselor.id,
                                        role_id=role.id).first() is None:
            db.add(UserRole(tenant_id=TID, user_id=counselor.id, role_id=role.id,
                            status="ACTIVE"))

        college = College(tenant_id=TID, college_name="C8范围学院",
                          code="C8-SCOPE-COLLEGE", status="ACTIVE")
        db.add(college)
        db.flush()
        major = Major(tenant_id=TID, college_id=college.id, major_name="C8范围专业",
                      code="C8-SCOPE-MAJOR", status="ACTIVE")
        db.add(major)
        db.flush()
        mine = SchoolClass(tenant_id=TID, major_id=major.id, class_name="A班", grade="2024",
                           counselor_id=counselor.id, status="ACTIVE")
        theirs = SchoolClass(tenant_id=TID, major_id=major.id, class_name="Z班",
                             grade="2024", status="ACTIVE")
        db.add_all([mine, theirs])
        db.flush()
        db.add_all([
            AffairsCounselorAssignment(
                tenant_id=TID, class_id=mine.id, user_id=counselor.id, duty_type="PRIMARY",
                status="ACTIVE", effective_from=datetime.utcnow() - timedelta(days=1)),
            TeacherStudentScope(
                tenant_id=TID, teacher_key="counselor01", teacher_name="王莉",
                role_code="COUNSELOR", scope_type="CLASS", ref_value="A班", status="ACTIVE"),
        ])

        def add(klass, sno, code, name, biz_id):
            stu = StudentProfile(tenant_id=TID, student_no=sno, real_name=f"学生{sno}",
                                 class_id=klass.id, college_id=college.id, gender="M",
                                 current_stage="CAMPUS", student_status="NORMAL",
                                 status="ACTIVE")
            db.add(stu)
            db.flush()
            db.add(AffairsMaterialRequirement(
                tenant_id=TID, student_id=stu.id, biz_type="DISCIPLINE", biz_id=biz_id,
                item_code=code, item_name=name, requirement_reason="范围合同用例",
                status="MISSING", sensitivity_level="SENSITIVE",
                material_scope="BUSINESS_SCOPE"))

        add(mine, "C8IN001", "IN_SCOPE_PROOF", "范围内材料", 910001)
        add(theirs, "C8OUT001", "OUT_OF_SCOPE_PROOF", "范围外材料", 910002)
        db.commit()
    finally:
        db.close()

    hdr = _hdr(client, "counselor01")
    response = _suggestions(client, hdr, "DISCIPLINE")
    assert response.status_code == 200, response.text
    codes = [x["itemCode"] for x in response.json()["data"]["items"]]
    assert "OUT_OF_SCOPE_PROOF" not in codes, (
        f"越数据范围的材料项被建议出来了：{codes}")


def test_prefilled_ids_still_go_through_the_existing_create_command(client, db_mode):
    """去手填只改入口：最终仍调既有登记命令，写链与校验一个都不能少。"""
    ids = _seed(db_mode)
    hdr = _hdr(client, "school_admin01")
    ctx = _biz_context(client, hdr, "DISCIPLINE", ids["case"]).json()["data"]

    created = client.post("/api/v1/student-affairs/material-requirements", headers=hdr, json={
        "bizType": ctx["bizType"], "bizId": int(ctx["bizId"]),
        "itemCode": "C8_ENTRY_PROOF", "itemName": "由业务详情发起的材料",
        "requirementReason": "从违纪详情直接要求补交材料",
    })
    assert created.json()["code"] == 0, created.json()
    # 正式规则仍然生效：非法材料项编码照样被拒
    bad = client.post("/api/v1/student-affairs/material-requirements", headers=hdr, json={
        "bizType": ctx["bizType"], "bizId": int(ctx["bizId"]),
        "itemCode": "非法编码", "itemName": "应当被拒绝",
    })
    assert bad.json()["code"] != 0, "登记命令的正式校验不得因入口改造而放宽"
