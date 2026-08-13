"""V5-C1 待审请假搜索真实性合同（真实 DB 模式）。

锁住的缺陷：管理 PC 请假初审工作台只请求 page=1&pageSize=100，再在前端按姓名/学号
本地过滤；后端 /leave/pending 本身没有 keyword。待审量 >100 时老师会"搜不到真实存在
的学生"——这是结果不真实，不是体验问题。

本文件要求搜索在服务端完成，且必须落在 tenant/数据范围/审批节点条件之后、
COUNT/OFFSET/LIMIT 之前，因此：
- 目标学生排在第 100 条以后仍必须能被搜到；
- total 是过滤后的真实 SQL count，不是当前页命中数；
- 跨租户同名、越数据范围同名一律搜不到（关键词不得成为绕过范围的口子）。
"""
from __future__ import annotations

TID = 1000000000000000001
OTHER_TID = 1000000000000000002

# 目标学生放在最早创建的一条请假上；列表按 CsLeave.id 倒序，
# 因此它会被 130 条后建的请假挤到第 100 条之后。
TARGET_NAME = "钱七七"
TARGET_SNO = "TGTSNO0001"
FILLER_COUNT = 130


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
    """A班=辅导员范围内；C班=同租户但越范围；OTHER_TID=跨租户。三处都放同名同学号学生。"""
    from datetime import datetime, timedelta
    from app.db.session import get_sessionmaker
    from app.models import (
        AffairsCounselorAssignment, College, CsLeave, Major, Role, SchoolClass,
        StudentProfile, TeacherStudentScope, User, UserRole,
    )
    db = get_sessionmaker()()

    def ensure_user(tenant_id, login_name, real_name):
        row = db.query(User).filter_by(tenant_id=tenant_id, login_name=login_name).first()
        if row is None:
            row = User(tenant_id=tenant_id, login_name=login_name, real_name=real_name,
                       password_hash="test-hash", user_type="TEACHER", status="ACTIVE")
            db.add(row)
            db.flush()
        else:
            row.status, row.is_deleted = "ACTIVE", False
        return row

    def ensure_role(tenant_id, role_code, role_name):
        row = db.query(Role).filter_by(tenant_id=tenant_id, role_code=role_code).first()
        if row is None:
            row = Role(tenant_id=tenant_id, role_code=role_code, role_name=role_name,
                       role_type="SYSTEM", status="ACTIVE")
            db.add(row)
            db.flush()
        else:
            row.status, row.is_deleted = "ACTIVE", False
        return row

    def bind(tenant_id, user, role):
        row = db.query(UserRole).filter_by(
            tenant_id=tenant_id, user_id=user.id, role_id=role.id).first()
        if row is None:
            db.add(UserRole(tenant_id=tenant_id, user_id=user.id,
                            role_id=role.id, status="ACTIVE"))
        else:
            row.status, row.is_deleted = "ACTIVE", False

    counselor = ensure_user(TID, "counselor01", "王莉")
    bind(TID, counselor, ensure_role(TID, "COUNSELOR", "辅导员"))

    college = College(tenant_id=TID, college_name="C1搜索学院",
                      code="C1-COLLEGE", status="ACTIVE")
    db.add(college)
    db.flush()
    major = Major(tenant_id=TID, college_id=college.id, major_name="C1搜索专业",
                  code="C1-MAJOR", status="ACTIVE")
    db.add(major)
    db.flush()
    in_scope = SchoolClass(tenant_id=TID, major_id=major.id, class_name="A班",
                           grade="2024", counselor_id=counselor.id, status="ACTIVE")
    out_scope = SchoolClass(tenant_id=TID, major_id=major.id, class_name="C班",
                            grade="2024", status="ACTIVE")
    db.add_all([in_scope, out_scope])
    db.flush()

    effective = datetime.utcnow() - timedelta(days=1)
    # 辅导员只被授予 A班：C班 属于同租户但越数据范围。
    db.add_all([
        AffairsCounselorAssignment(tenant_id=TID, class_id=in_scope.id,
                                   user_id=counselor.id, duty_type="PRIMARY",
                                   status="ACTIVE", effective_from=effective),
        TeacherStudentScope(tenant_id=TID, teacher_key="counselor01", teacher_name="王莉",
                            role_code="COUNSELOR", scope_type="CLASS",
                            ref_value="A班", status="ACTIVE"),
    ])

    def add_student(tenant_id, class_id, college_id, sno, name):
        row = StudentProfile(tenant_id=tenant_id, student_no=sno, real_name=name,
                             class_id=class_id, college_id=college_id, gender="M",
                             current_stage="CAMPUS", student_status="NORMAL",
                             status="ACTIVE")
        db.add(row)
        db.flush()
        return row

    def add_pending_leave(tenant_id, student):
        row = CsLeave(tenant_id=tenant_id, student_id=student.id, leave_type="PERSONAL",
                      start_time=datetime(2026, 3, 1), end_time=datetime(2026, 3, 2),
                      days=1, reason="回家处理家庭事务",
                      status="PENDING_REVIEW", affairs_status="COUNSELOR_REVIEW")
        db.add(row)
        db.flush()
        return row

    # ① 目标学生的请假最先建 → id 最小 → 倒序排最后。
    target = add_student(TID, in_scope.id, college.id, TARGET_SNO, TARGET_NAME)
    target_leave = add_pending_leave(TID, target)

    # ② 130 条填充请假，把目标挤出第一页。
    for i in range(FILLER_COUNT):
        filler = add_student(TID, in_scope.id, college.id, f"FILL{i:04d}", f"填充{i:04d}")
        add_pending_leave(TID, filler)

    # ③ 同租户越数据范围的同名同学号学生（C班，辅导员无授权）。
    out_student = add_student(TID, out_scope.id, college.id, TARGET_SNO + "X", TARGET_NAME)
    add_pending_leave(TID, out_student)

    # ④ 跨租户同名同学号学生。
    other_college = College(tenant_id=OTHER_TID, college_name="他校学院",
                            code="C1-OTHER-COLLEGE", status="ACTIVE")
    db.add(other_college)
    db.flush()
    other_major = Major(tenant_id=OTHER_TID, college_id=other_college.id,
                        major_name="他校专业", code="C1-OTHER-MAJOR", status="ACTIVE")
    db.add(other_major)
    db.flush()
    other_class = SchoolClass(tenant_id=OTHER_TID, major_id=other_major.id,
                              class_name="他校A班", grade="2024", status="ACTIVE")
    db.add(other_class)
    db.flush()
    other_student = add_student(OTHER_TID, other_class.id, other_college.id,
                                TARGET_SNO, TARGET_NAME)
    add_pending_leave(OTHER_TID, other_student)

    db.commit()
    ids = {"target_student": target.id, "target_leave": target_leave.id,
           "out_student": out_student.id, "other_student": other_student.id,
           "in_class": in_scope.id, "out_class": out_scope.id}
    db.close()
    return ids


def _pending(client, hdr, **params):
    response = client.get("/api/v1/student-affairs/leave/pending",
                          headers=hdr, params=params)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["code"] == 0, body
    data = body["data"]
    # 后端分页契约字段为 items；前端 callList 再归一化成 list。测试按后端真值断言。
    data["list"] = data["items"]
    return data


def test_target_beyond_first_page_is_unreachable_without_search(client, db_mode):
    """前置事实：不搜索时目标学生确实落在第 100 条之后（否则本合同就测不到东西）。"""
    ids = _seed(db_mode)
    hdr = _hdr(client, "counselor01")
    page1 = _pending(client, hdr, page=1, pageSize=100)
    assert page1["total"] >= FILLER_COUNT + 1
    names = [row["studentName"] for row in page1["list"]]
    assert TARGET_NAME not in names, "目标学生本应被挤出第一页，测试数据构造失效"


def test_pending_search_finds_student_beyond_page_one(client, db_mode):
    """核心：按姓名/学号搜索必须命中第 100 条以后的真实记录，且 total 为过滤后真值。"""
    ids = _seed(db_mode)
    hdr = _hdr(client, "counselor01")

    by_name = _pending(client, hdr, page=1, pageSize=20, keyword=TARGET_NAME)
    assert by_name["total"] == 1, by_name
    assert [row["studentName"] for row in by_name["list"]] == [TARGET_NAME]
    assert str(by_name["list"][0]["id"]) == str(ids["target_leave"])

    by_sno = _pending(client, hdr, page=1, pageSize=20, keyword=TARGET_SNO)
    assert by_sno["total"] == 1, by_sno
    assert str(by_sno["list"][0]["id"]) == str(ids["target_leave"])


def test_pending_search_never_crosses_tenant_or_data_scope(client, db_mode):
    """关键词不得成为绕过租户/数据范围的口子：同名的越范围与跨租户记录一律搜不到。"""
    ids = _seed(db_mode)
    hdr = _hdr(client, "counselor01")

    hit = _pending(client, hdr, page=1, pageSize=50, keyword=TARGET_NAME)
    student_ids = {str(row["studentId"]) for row in hit["list"]}
    assert str(ids["out_student"]) not in student_ids, "越数据范围的同名学生被搜出来了"
    assert str(ids["other_student"]) not in student_ids, "跨租户的同名学生被搜出来了"
    assert hit["total"] == 1, f"total 必须只统计授权范围内的命中：{hit['total']}"


def test_pending_search_total_matches_paging_without_gap_or_dup(client, db_mode):
    """搜索结果分页必须无重复、无遗漏，且 total 与逐页累计一致。"""
    ids = _seed(db_mode)
    hdr = _hdr(client, "counselor01")

    # "填充" 前缀命中全部 130 条，用来验证搜索条件下的真分页。
    first = _pending(client, hdr, page=1, pageSize=50, keyword="填充")
    assert first["total"] == FILLER_COUNT, first["total"]

    seen, page = [], 1
    while True:
        data = _pending(client, hdr, page=page, pageSize=50, keyword="填充")
        seen.extend(str(row["id"]) for row in data["list"])
        if len(data["list"]) < 50 or len(seen) >= data["total"]:
            break
        page += 1
    assert len(seen) == FILLER_COUNT, f"逐页累计 {len(seen)} != total {FILLER_COUNT}"
    assert len(set(seen)) == FILLER_COUNT, "分页出现重复记录"


def test_pending_without_keyword_restores_full_queue(client, db_mode):
    """清空关键词必须恢复完整待审队列（搜索是可选条件，不能污染默认口径）。"""
    ids = _seed(db_mode)
    hdr = _hdr(client, "counselor01")

    full = _pending(client, hdr, page=1, pageSize=20)
    filtered = _pending(client, hdr, page=1, pageSize=20, keyword=TARGET_NAME)
    blank = _pending(client, hdr, page=1, pageSize=20, keyword="   ")

    assert filtered["total"] == 1
    assert full["total"] == FILLER_COUNT + 1, full["total"]
    assert blank["total"] == full["total"], "纯空白关键词应视为未搜索"


def test_pending_search_miss_returns_empty_not_fallback(client, db_mode):
    """搜不到必须是空结果，绝不能回落成"返回全部"。"""
    ids = _seed(db_mode)
    hdr = _hdr(client, "counselor01")
    miss = _pending(client, hdr, page=1, pageSize=20, keyword="不存在的学生ZZZ")
    assert miss["total"] == 0, miss
    assert miss["list"] == []
