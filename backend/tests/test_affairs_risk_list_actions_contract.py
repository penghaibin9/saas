"""V5-C5 风险列表行级动作合同（真实 DB 模式）。

锁住的缺陷：风险详情 get_risk 会按 RISK_TRANSITIONS + 权限 + 责任关系下发
allowedActions，但列表投影 _row() 没有这个字段；管理 PC 列表只按全局权限
（canBtn('studentAffairs.risk.assign' / '.handle')）显示"分派/处置"。

于是出现：按钮看得到 → 点进去填写 → 提交 → 服务器说当前状态不允许/你不是责任人。
后端仍 fail-closed 没有越权，但 UI 合同是错位的。

本合同要求：
- 列表每行下发 allowedActions；
- 与详情 allowedActions 完全一致（同一状态机推导，不得各算一套）；
- 列表声明可做的动作，写服务必须真的接受；列表没声明的，写服务必须拒绝。
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
    """覆盖状态机的关键状态：NEW / ASSIGNED(本人) / ASSIGNED(他人) /
    PROCESSING(他人) / ESCALATED / CLOSED。"""
    from app.db.session import get_sessionmaker
    from app.models import (
        AffairsRiskRecord, College, Major, Role, SchoolClass, StudentProfile, User, UserRole,
    )

    db = get_sessionmaker()()

    college = College(tenant_id=TID, college_name="C5风险学院",
                      code="C5-COLLEGE", status="ACTIVE")
    db.add(college)
    db.flush()
    major = Major(tenant_id=TID, college_id=college.id, major_name="C5风险专业",
                  code="C5-MAJOR", status="ACTIVE")
    db.add(major)
    db.flush()
    klass = SchoolClass(tenant_id=TID, major_id=major.id, class_name="C5班",
                        grade="2024", status="ACTIVE")
    db.add(klass)
    db.flush()
    student = StudentProfile(tenant_id=TID, student_no="C5STU0001", real_name="风险测试学生",
                             class_id=klass.id, college_id=college.id, gender="M",
                             current_stage="CAMPUS", student_status="NORMAL", status="ACTIVE")
    db.add(student)
    db.flush()

    # 责任人必须真的持有风险处置角色且数据范围覆盖该学生：
    # assign 写链的 _validate_owner 会校验这三点，光建账号会被正确拒绝。
    other = User(tenant_id=TID, login_name="c5_other_owner", real_name="别的责任人",
                 password_hash="test-hash", user_type="TEACHER", status="ACTIVE")
    db.add(other)
    db.flush()
    owner_role = db.query(Role).filter_by(
        tenant_id=TID, role_code="STUDENT_AFFAIRS_ADMIN").first()
    if owner_role is None:
        owner_role = Role(tenant_id=TID, role_code="STUDENT_AFFAIRS_ADMIN",
                          role_name="学工处管理员", role_type="SYSTEM", status="ACTIVE")
        db.add(owner_role)
        db.flush()
    db.add(UserRole(tenant_id=TID, user_id=other.id, role_id=owner_role.id, status="ACTIVE"))
    db.flush()

    def add_risk(status, owner_id=None, title=""):
        row = AffairsRiskRecord(
            tenant_id=TID, student_id=student.id, source="BEHAVIOR",
            risk_level="HIGH", title=title or f"风险-{status}",
            detail="行为异常需跟进", status=status, owner_id=owner_id, version=1,
        )
        db.add(row)
        db.flush()
        return row

    risks = {
        "new": add_risk("NEW"),
        "assigned_other": add_risk("ASSIGNED", owner_id=other.id),
        "processing_other": add_risk("PROCESSING", owner_id=other.id),
        "escalated": add_risk("ESCALATED", owner_id=other.id),
        "closed": add_risk("CLOSED", owner_id=other.id),
    }
    db.commit()
    ids = {key: row.id for key, row in risks.items()}
    ids["other_owner"] = other.id
    ids["student"] = student.id
    db.close()
    return ids


def _list(client, hdr, **params):
    response = client.get("/api/v1/student-affairs/risk/records", headers=hdr, params=params)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["code"] == 0, body
    return body["data"]


def _detail(client, hdr, risk_id):
    response = client.get(f"/api/v1/student-affairs/risk/records/{risk_id}", headers=hdr)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["code"] == 0, body
    return body["data"]


def _rows_by_id(client, hdr):
    data = _list(client, hdr, page=1, pageSize=50)
    return {str(row["riskId"]): row for row in data["items"]}


def test_risk_list_rows_expose_allowed_actions(client, db_mode):
    """C5 核心：列表投影必须带 allowedActions，否则前端只能靠全局权限猜。"""
    _seed(db_mode)
    hdr = _hdr(client, "school_admin01")
    rows = _rows_by_id(client, hdr)
    assert rows, "列表不应为空"
    for risk_id, row in rows.items():
        assert "allowedActions" in row, f"风险 {risk_id} 的列表行缺少 allowedActions"
        assert isinstance(row["allowedActions"], list)


def test_list_actions_match_detail_actions_exactly(client, db_mode):
    """列表与详情必须来自同一状态机推导，不允许两套结果。"""
    ids = _seed(db_mode)
    hdr = _hdr(client, "school_admin01")
    rows = _rows_by_id(client, hdr)

    for key in ("new", "assigned_other", "processing_other", "escalated", "closed"):
        risk_id = str(ids[key])
        assert risk_id in rows, f"{key} 未出现在列表中"
        detail = _detail(client, hdr, risk_id)
        assert sorted(rows[risk_id]["allowedActions"]) == sorted(detail["allowedActions"]), (
            f"{key}: 列表 {rows[risk_id]['allowedActions']} != 详情 {detail['allowedActions']}"
        )


def test_state_machine_semantics_hold_on_the_list(client, db_mode):
    """按状态机语义逐条核对，尤其 TAKEOVER 只属于 ESCALATED，不是普通 self-assign。"""
    ids = _seed(db_mode)
    hdr = _hdr(client, "school_admin01")
    rows = _rows_by_id(client, hdr)

    new_actions = rows[str(ids["new"])]["allowedActions"]
    assert "ASSIGN" in new_actions, new_actions
    assert "TAKEOVER" not in new_actions, "NEW 不得出现 TAKEOVER（那是升级后上级接管）"
    assert "CLOSE" not in new_actions, "NEW 不得直接办结"

    escalated_actions = rows[str(ids["escalated"])]["allowedActions"]
    assert "TAKEOVER" in escalated_actions, escalated_actions
    assert "ASSIGN" not in escalated_actions, "ESCALATED 不在 ASSIGN 的 from 集合里"

    closed_actions = rows[str(ids["closed"])]["allowedActions"]
    assert "PROCESS" not in closed_actions, "CLOSED 不得出现处置动作"
    assert "ASSIGN" not in closed_actions
    assert set(closed_actions) <= {"REOPEN"}, closed_actions


def test_list_actions_are_not_wider_than_the_write_service(client, db_mode):
    """列表没声明的动作，写服务必须拒绝；列表声明了的，写服务必须接受。

    这是 C5 的真正目的：UI 合同与 canonical 写链一致，不靠"点了才知道"。
    """
    ids = _seed(db_mode)
    hdr = _hdr(client, "school_admin01")
    rows = _rows_by_id(client, hdr)

    closed_id = str(ids["closed"])
    assert "PROCESS" not in rows[closed_id]["allowedActions"]
    denied = client.post(f"/api/v1/student-affairs/risk/records/{closed_id}/process",
                         headers=hdr, json={"content": "尝试对已办结记录处置", "version": 1})
    assert denied.json()["code"] != 0, "已办结记录不应允许处置，写服务与列表口径不一致"

    new_id = str(ids["new"])
    assert "ASSIGN" in rows[new_id]["allowedActions"]
    accepted = client.post(f"/api/v1/student-affairs/risk/records/{new_id}/assign", headers=hdr,
                           json={"ownerId": str(ids["other_owner"]), "version": 1})
    assert accepted.json()["code"] == 0, (
        f"列表声明可 ASSIGN，写服务却拒绝：{accepted.json()}")


def test_actions_are_empty_without_risk_permissions(client, db_mode):
    """无风险权限的身份：列表要么看不到记录，要么 allowedActions 为空（fail-closed）。"""
    _seed(db_mode)
    hdr = _hdr(client, "student01")
    response = client.get("/api/v1/student-affairs/risk/records", headers=hdr,
                          params={"page": 1, "pageSize": 50})
    if response.status_code != 200 or response.json().get("code") != 0:
        return  # 直接 403/业务失败也是可接受的 fail-closed
    for row in response.json()["data"]["items"]:
        assert not row.get("allowedActions"), (
            f"无处置权限的身份不应拿到可执行动作：{row.get('allowedActions')}")
