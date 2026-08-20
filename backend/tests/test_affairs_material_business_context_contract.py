"""V5-C7 材料业务可读上下文合同（真实 DB 模式）。

材料四端此前把内部主键当主业务文案：
  管理 PC   困难认定 #123 · 学生 #456
  学生 PC   业务记录 #123
  教师小程序 困难认定 #123 · 学生 #456
老师在手机上靠主键认学生，学生不知道 #123 是哪一笔业务。

本合同要求 additive 增加 businessContext（业务语言），同时：
- bizId / studentId 一律保留，供 API、审计和技术追踪；
- 必须按当前页批量组装，不得逐行查库（N+1）；
- 强敏感业务（MENTAL）只给业务类型，不得借 projection 带出事由/明细。
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
    """造真实业务记录（请假 / 违纪 / 心理转介）再挂材料缺项，
    这样 businessContext 必须真的去业务表取数，而不是拼字符串。"""
    from datetime import datetime
    from app.db.session import get_sessionmaker
    from app.models import (
        College, CsLeave, DisciplineCase, Major, PsyReferral, SchoolClass, StudentProfile,
    )
    from app.models.affairs_operations import AffairsMaterialRequirement

    db = get_sessionmaker()()

    college = College(tenant_id=TID, college_name="C7材料学院",
                      code="C7-COLLEGE", status="ACTIVE")
    db.add(college)
    db.flush()
    major = Major(tenant_id=TID, college_id=college.id, major_name="C7材料专业",
                  code="C7-MAJOR", status="ACTIVE")
    db.add(major)
    db.flush()
    klass = SchoolClass(tenant_id=TID, major_id=major.id, class_name="软件2401",
                        grade="2024", status="ACTIVE")
    db.add(klass)
    db.flush()
    student = StudentProfile(tenant_id=TID, student_no="202600123", real_name="张三",
                             class_id=klass.id, college_id=college.id, gender="M",
                             current_stage="CAMPUS", student_status="NORMAL", status="ACTIVE")
    db.add(student)
    db.flush()

    leave = CsLeave(tenant_id=TID, student_id=student.id, leave_type="SICK",
                    start_time=datetime(2026, 3, 1), end_time=datetime(2026, 3, 5),
                    days=5, reason="就医", status="PENDING_REVIEW",
                    affairs_status="COUNSELOR_REVIEW")
    discipline = DisciplineCase(tenant_id=TID, student_id=student.id, disc_type="WARNING",
                                reason="违纪事实", doc_no="学工处分〔2026〕07号",
                                decide_date=datetime(2026, 4, 10), status="REGISTERED")
    referral = PsyReferral(tenant_id=TID, student_id=student.id, level="FOCUS",
                           channel="校内咨询", reason_summary="敏感事由不得外泄",
                           note="涉密明细不得外泄", status="REFERRED")
    db.add_all([leave, discipline, referral])
    db.flush()

    def add_req(biz_type, biz_id, code, sensitivity="SENSITIVE", scope="BUSINESS_SCOPE"):
        row = AffairsMaterialRequirement(
            tenant_id=TID, student_id=student.id, biz_type=biz_type, biz_id=biz_id,
            item_code=code, item_name=f"材料-{code}", requirement_reason="业务可读合同用例",
            status="MISSING", sensitivity_level=sensitivity, material_scope=scope,
        )
        db.add(row)
        db.flush()
        return row

    reqs = {
        "leave": add_req("LEAVE", leave.id, "LEAVE_PROOF"),
        "discipline": add_req("DISCIPLINE", discipline.id, "DISC_PROOF"),
        "mental": add_req("MENTAL", referral.id, "PSY_PROOF",
                          sensitivity="HIGHLY_SENSITIVE", scope="PSY_STUDENT"),
    }
    db.commit()
    ids = {k: v.id for k, v in reqs.items()}
    # 注意：reqs 的键已占用 leave/discipline/mental，业务记录 id 另起键名，
    # 否则会把 requirement id 覆盖掉。
    ids.update({"student": student.id, "leave_record": leave.id,
                "discipline_case": discipline.id, "referral": referral.id})
    db.close()
    return ids


def _center(client, hdr, **params):
    response = client.get("/api/v1/student-affairs/material-center",
                          headers=hdr, params=params)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["code"] == 0, body
    return body["data"]


def _by_requirement(items):
    return {str(item["requirementId"]): item for item in items}


def test_business_context_speaks_business_language(client, db_mode):
    """核心：老师看到的是学生姓名/学号/班级和业务标题，而不是主键。"""
    ids = _seed(db_mode)
    hdr = _hdr(client, "school_admin01")
    items = _by_requirement(_center(client, hdr, page=1, pageSize=50)["items"])

    leave_item = next(x for x in items.values() if x["bizType"] == "LEAVE")
    assert leave_item["requirementId"] == str(ids["leave"]), leave_item["requirementId"]
    ctx = leave_item.get("businessContext")
    assert ctx, "列表行缺少 businessContext"
    assert ctx["studentName"] == "张三", ctx
    assert ctx["studentNo"] == "202600123", ctx
    assert ctx["className"] == "软件2401", ctx
    assert ctx["bizDisplayTitle"] == "请假申请", ctx


def test_business_context_reads_the_real_business_record(client, db_mode):
    """副标题/周期必须来自业务真表，不是拼出来的常量。"""
    _seed(db_mode)
    hdr = _hdr(client, "school_admin01")
    items = _by_requirement(_center(client, hdr, page=1, pageSize=50)["items"])

    leave_ctx = next(x for x in items.values() if x["bizType"] == "LEAVE")["businessContext"]
    assert leave_ctx["bizPeriod"] == "2026-03-01 ~ 2026-03-05", leave_ctx
    assert leave_ctx["bizDisplaySubtitle"] == "SICK", leave_ctx

    disc_ctx = next(x for x in items.values() if x["bizType"] == "DISCIPLINE")["businessContext"]
    assert disc_ctx["bizDisplayTitle"] == "违纪处分", disc_ctx
    assert disc_ctx["bizDisplaySubtitle"] == "学工处分〔2026〕07号", disc_ctx
    assert disc_ctx["bizPeriod"] == "2026", disc_ctx


def test_internal_ids_are_kept_for_api_and_audit(client, db_mode):
    """可读化是 additive：bizId / studentId 不得被删掉。"""
    _seed(db_mode)
    hdr = _hdr(client, "school_admin01")
    for item in _center(client, hdr, page=1, pageSize=50)["items"]:
        assert item["bizId"], item
        assert item["studentId"], item
        assert item["requirementId"], item


def test_highly_sensitive_biz_leaks_no_detail_through_projection(client, db_mode):
    """强敏感业务只给"这是哪一类业务"，事由/明细一个字都不能进 projection。"""
    _seed(db_mode)
    hdr = _hdr(client, "school_admin01")
    items = _center(client, hdr, page=1, pageSize=50)["items"]
    mental = next((x for x in items if x["bizType"] == "MENTAL"), None)
    if mental is None:
        return  # 当前身份看不到心理材料也是合规的 fail-closed
    ctx = mental["businessContext"]
    assert ctx["bizDisplayTitle"] == "心理关注转介", ctx
    assert ctx["bizDisplaySubtitle"] == "", ctx
    blob = str(ctx)
    assert "敏感事由不得外泄" not in blob, "转介事由通过 businessContext 泄露"
    assert "涉密明细不得外泄" not in blob, "涉密明细通过 businessContext 泄露"


def test_projection_is_batched_not_per_row(client, db_mode):
    """N+1 合同：页大小扩大时，查询次数只能有固定开销，不能随材料行数线性增长。"""
    from sqlalchemy import event
    from app.db.session import get_engine, get_sessionmaker
    from app.models.affairs_operations import AffairsMaterialRequirement

    ids = _seed(db_mode)
    db = get_sessionmaker()()
    try:
        base = db.get(AffairsMaterialRequirement, int(ids["leave"]))
        for i in range(27):
            db.add(AffairsMaterialRequirement(
                tenant_id=TID, student_id=base.student_id, biz_type="LEAVE",
                biz_id=base.biz_id, item_code=f"BULK{i:03d}", item_name=f"批量材料{i:03d}",
                requirement_reason="N+1 合同用例", status="MISSING",
                sensitivity_level="SENSITIVE", material_scope="BUSINESS_SCOPE",
            ))
        db.commit()
    finally:
        db.close()

    hdr = _hdr(client, "school_admin01")
    counter = {"n": 0}

    def _count(*_args, **_kwargs):
        counter["n"] += 1

    engine = get_engine()
    event.listen(engine, "before_cursor_execute", _count)
    try:
        small = _center(client, hdr, page=1, pageSize=5)
        small_selects = counter["n"]
        counter["n"] = 0
        large = _center(client, hdr, page=1, pageSize=50)
        large_selects = counter["n"]
    finally:
        event.remove(engine, "before_cursor_execute", _count)

    assert len(small["items"]) == 5, len(small["items"])
    assert len(large["items"]) >= 30, len(large["items"])
    # 批量 projection 可因较大页多做少量固定查询，但不能按新增的 25+ 行逐条放大。
    assert large_selects <= small_selects + 4, (
        "材料列表从 5 行扩到 30+ 行时 SQL 从 "
        f"{small_selects} 增到 {large_selects}，疑似逐行查询业务记录/学生"
    )
