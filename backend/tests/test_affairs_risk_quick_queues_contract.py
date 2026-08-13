"""V5-U2 风险快捷队列合同（真实 DB 模式）。

风险后端本来就在算 highCritical / open / unassigned / overdue 四个指标，
但 list_risks 只支持 source/status/riskLevel/studentId 过滤。老师看到
"超时 8 条"却没法一键只看这 8 条，只能手工组合筛选。

本合同要求快捷队列是 server-backed：
- priority / overdueOnly / unassignedOnly / ownerId 全部作为 SQL 条件参与
  COUNT 与分页（前端拿当前页再筛，在超过一页时会漏掉真实存在的记录）；
- **点卡片进去，列表 total 必须等于点之前卡片上的数字**——
  快捷队列和指标卡必须共用同一份判定，不能一个用 SQL 谓词、一个用别的口径；
- 数据范围永远先生效，快捷队列不得成为看到范围外记录的口子。
"""
from __future__ import annotations

from datetime import datetime, timedelta

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
    """构造覆盖四个快捷队列的风险记录，外加一条越数据范围的高危记录。"""
    from app.db.session import get_sessionmaker
    from app.models import (
        AffairsCounselorAssignment, AffairsRiskRecord, College, Major, Role,
        SchoolClass, StudentProfile, TeacherStudentScope, User, UserRole,
    )

    db = get_sessionmaker()()

    def ensure_user(login_name, real_name):
        row = db.query(User).filter_by(tenant_id=TID, login_name=login_name).first()
        if row is None:
            row = User(tenant_id=TID, login_name=login_name, real_name=real_name,
                       password_hash="test-hash", user_type="TEACHER", status="ACTIVE")
            db.add(row)
            db.flush()
        else:
            row.status, row.is_deleted = "ACTIVE", False
        return row

    def ensure_role(code, name):
        row = db.query(Role).filter_by(tenant_id=TID, role_code=code).first()
        if row is None:
            row = Role(tenant_id=TID, role_code=code, role_name=name,
                       role_type="SYSTEM", status="ACTIVE")
            db.add(row)
            db.flush()
        else:
            row.status, row.is_deleted = "ACTIVE", False
        return row

    def bind(u, r):
        if db.query(UserRole).filter_by(tenant_id=TID, user_id=u.id, role_id=r.id).first() is None:
            db.add(UserRole(tenant_id=TID, user_id=u.id, role_id=r.id, status="ACTIVE"))

    # mock-login 只认固定演示账号；用 school_admin01（TENANT_ALL）避免
    # 数据范围成为干扰变量，范围本身由下面的 counselor01 用例单独验。
    admin = ensure_user("school_admin01", "学工处")
    bind(admin, ensure_role("STUDENT_AFFAIRS_ADMIN", "学工处管理员"))
    counselor = ensure_user("counselor01", "王莉")
    bind(counselor, ensure_role("COUNSELOR", "辅导员"))
    other = ensure_user("u2_other_owner", "别的责任人")
    bind(other, ensure_role("STUDENT_AFFAIRS_ADMIN", "学工处管理员"))

    college = College(tenant_id=TID, college_name="U2风险学院",
                      code="U2-COLLEGE", status="ACTIVE")
    db.add(college)
    db.flush()
    major = Major(tenant_id=TID, college_id=college.id, major_name="U2风险专业",
                  code="U2-MAJOR", status="ACTIVE")
    db.add(major)
    db.flush()
    in_scope = SchoolClass(tenant_id=TID, major_id=major.id, class_name="A班", grade="2024",
                           counselor_id=counselor.id, status="ACTIVE")
    out_scope = SchoolClass(tenant_id=TID, major_id=major.id, class_name="Z班",
                            grade="2024", status="ACTIVE")
    db.add_all([in_scope, out_scope])
    db.flush()
    db.add_all([
        AffairsCounselorAssignment(
            tenant_id=TID, class_id=in_scope.id, user_id=counselor.id, duty_type="PRIMARY",
            status="ACTIVE", effective_from=datetime.utcnow() - timedelta(days=1)),
        TeacherStudentScope(
            tenant_id=TID, teacher_key="counselor01", teacher_name="王莉",
            role_code="COUNSELOR", scope_type="CLASS", ref_value="A班", status="ACTIVE"),
    ])

    def student(klass, sno):
        row = StudentProfile(tenant_id=TID, student_no=sno, real_name=f"学生{sno}",
                             class_id=klass.id, college_id=college.id, gender="M",
                             current_stage="CAMPUS", student_status="NORMAL", status="ACTIVE")
        db.add(row)
        db.flush()
        return row

    def risk(stu, *, level, status, owner=None, created=None, assigned=None):
        row = AffairsRiskRecord(
            tenant_id=TID, student_id=stu.id, source="BEHAVIOR", risk_level=level,
            title=f"U2-{level}-{status}", detail="快捷队列用例", status=status,
            owner_id=owner.id if owner else None, version=1,
        )
        db.add(row)
        db.flush()
        # created_at / assigned_at 由超时判定使用，需显式落到过去。
        if created is not None:
            row.created_at = created
        if assigned is not None:
            row.assigned_at = assigned
        db.flush()
        return row

    s1, s2, s3, s4, s5 = (student(in_scope, f"U2A{i}") for i in range(1, 6))
    s_out = student(out_scope, "U2Z1")

    now = datetime.utcnow()
    ids = {
        # 高危待分派且已超时（NEW 超过 assignHours）
        "high_unassigned_overdue": risk(s1, level="CRITICAL", status="NEW",
                                        created=now - timedelta(days=30)).id,
        # 高危、已分派给本人、未超时
        "high_mine": risk(s2, level="HIGH", status="ASSIGNED", owner=admin,
                          created=now, assigned=now).id,
        # 低危、分派给别人、未超时
        "low_other": risk(s3, level="LOW", status="ASSIGNED", owner=other,
                          created=now, assigned=now).id,
        # 中危、待分派、未超时
        "mid_unassigned": risk(s4, level="MEDIUM", status="NEW", created=now).id,
        # 已办结（不该出现在"未闭环"类队列里）
        "closed": risk(s5, level="HIGH", status="CLOSED", owner=admin,
                       created=now, assigned=now).id,
        # 越数据范围的高危超时记录：辅导员一律看不到
        "out_of_scope": risk(s_out, level="CRITICAL", status="NEW",
                             created=now - timedelta(days=30)).id,
    }
    db.commit()
    ids.update({"admin": admin.id, "other": other.id})
    db.close()
    return ids


def _list(client, hdr, **params):
    response = client.get("/api/v1/student-affairs/risk/records", headers=hdr, params=params)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["code"] == 0, body
    return body["data"]


def test_quick_queue_total_equals_the_metric_card_number(client, db_mode):
    """核心：点卡片进去，列表 total 必须等于点之前卡片上的数字。

    这是快捷队列最容易出的错——卡片一套口径、过滤另一套，
    老师看到"超时 8 条"点进去只有 5 条。
    """
    _seed(db_mode)
    hdr = _hdr(client, "school_admin01")
    base = _list(client, hdr, page=1, pageSize=50)
    stats = base["stats"]

    overdue = _list(client, hdr, page=1, pageSize=50, overdueOnly=True)
    assert overdue["total"] == stats["overdue"], (
        f"超时卡片 {stats['overdue']} != 超时队列 total {overdue['total']}")

    unassigned = _list(client, hdr, page=1, pageSize=50, unassignedOnly=True)
    assert unassigned["total"] == stats["unassigned"], (
        f"待分派卡片 {stats['unassigned']} != 队列 total {unassigned['total']}")

    high = _list(client, hdr, page=1, pageSize=50, priority="HIGH_CRITICAL")
    assert high["total"] == stats["highCritical"], (
        f"高危卡片 {stats['highCritical']} != 队列 total {high['total']}")


def test_quick_queues_return_the_right_records(client, db_mode):
    """逐条核对每个队列真正命中的记录。"""
    ids = _seed(db_mode)
    hdr = _hdr(client, "school_admin01")

    high = {str(x["riskId"]) for x in
            _list(client, hdr, page=1, pageSize=50, priority="HIGH_CRITICAL")["items"]}
    assert str(ids["high_unassigned_overdue"]) in high
    assert str(ids["high_mine"]) in high
    assert str(ids["low_other"]) not in high, "低危不该进高危队列"

    unassigned = {str(x["riskId"]) for x in
                  _list(client, hdr, page=1, pageSize=50, unassignedOnly=True)["items"]}
    assert str(ids["mid_unassigned"]) in unassigned
    assert str(ids["high_mine"]) not in unassigned, "已分派记录不该进待分派队列"

    overdue = {str(x["riskId"]) for x in
               _list(client, hdr, page=1, pageSize=50, overdueOnly=True)["items"]}
    assert str(ids["high_unassigned_overdue"]) in overdue
    assert str(ids["high_mine"]) not in overdue, "刚分派的记录不该算超时"


def test_owner_queue_only_returns_my_records(client, db_mode):
    """「我负责的」必须真的只返回我负责的。"""
    ids = _seed(db_mode)
    hdr = _hdr(client, "school_admin01")
    mine = _list(client, hdr, page=1, pageSize=50, ownerId=str(ids["admin"]))
    got = {str(x["riskId"]) for x in mine["items"]}
    assert str(ids["high_mine"]) in got
    assert str(ids["low_other"]) not in got, "别人负责的记录进了「我负责的」"
    for item in mine["items"]:
        assert str(item["ownerId"]) == str(ids["admin"]), item


def test_quick_queues_compose_with_existing_filters(client, db_mode):
    """快捷队列要能和既有筛选叠加，不能互相覆盖。"""
    ids = _seed(db_mode)
    hdr = _hdr(client, "school_admin01")
    both = _list(client, hdr, page=1, pageSize=50,
                 priority="HIGH_CRITICAL", unassignedOnly=True)
    got = {str(x["riskId"]) for x in both["items"]}
    # 学工处是 TENANT_ALL，Z 班那条 CRITICAL/NEW 对它并不越范围，因此也应命中；
    # 它只在下面 counselor01 的范围用例里必须消失。
    assert got == {str(ids["high_unassigned_overdue"]), str(ids["out_of_scope"])}, got
    assert both["total"] == 2, both["total"]
    # 叠加确实收窄了：单条件时命中更多
    only_high = _list(client, hdr, page=1, pageSize=50, priority="HIGH_CRITICAL")
    assert only_high["total"] > both["total"], (only_high["total"], both["total"])


def test_quick_queues_never_escape_data_scope(client, db_mode):
    """数据范围永远先生效：快捷队列不得成为看到范围外记录的口子。"""
    ids = _seed(db_mode)
    hdr = _hdr(client, "counselor01")
    for params in (
        {"priority": "HIGH_CRITICAL"},
        {"overdueOnly": True},
        {"unassignedOnly": True},
    ):
        data = _list(client, hdr, page=1, pageSize=50, **params)
        got = {str(x["riskId"]) for x in data["items"]}
        assert str(ids["out_of_scope"]) not in got, f"{params} 泄露了越范围记录"


def test_unknown_owner_returns_empty_not_everything(client, db_mode):
    """解析不出的责任人必须返回空，绝不能静默退化成不过滤。"""
    _seed(db_mode)
    hdr = _hdr(client, "school_admin01")
    data = _list(client, hdr, page=1, pageSize=50, ownerId="not-a-user-id")
    assert data["total"] == 0, data["total"]
    assert data["items"] == []


def test_quick_queue_paging_is_server_side(client, db_mode):
    """队列分页必须在服务端：逐页累计等于 total，且无重复。"""
    _seed(db_mode)
    hdr = _hdr(client, "school_admin01")
    first = _list(client, hdr, page=1, pageSize=2, priority="HIGH_CRITICAL")
    total = first["total"]
    seen, page = [], 1
    while True:
        data = _list(client, hdr, page=page, pageSize=2, priority="HIGH_CRITICAL")
        assert data["total"] == total, "翻页不应改变 total"
        seen.extend(str(x["riskId"]) for x in data["items"])
        if not data["items"] or len(seen) >= total:
            break
        page += 1
    assert len(seen) == total and len(set(seen)) == total, (len(seen), total)
