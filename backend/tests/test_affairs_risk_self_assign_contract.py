"""V5-U3 风险「我来处理」合同（真实 DB 模式）。

老师在列表上看到一条待分派风险，想直接接手，此前必须打开分派弹窗、
在责任人选择器里把自己搜出来再选一遍。

本合同要求 self-assign：
- 复用既有 ASSIGN 写链（状态机 / 乐观锁 / _validate_owner / 待办 / 通知 / 审计），
  不新增状态迁移，不放宽任何校验；
- **绝不能用 TAKEOVER 实现**——那是 ESCALATED 之后的上级接管，语义完全不同；
- 列表下发 canClaim，前端据此 fail-closed 显示按钮，
  无处置资格的账号既不显示也认领不了。
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
    from app.db.session import get_sessionmaker
    from app.models import (
        AffairsCounselorAssignment, AffairsRiskRecord, College, Major, Role,
        SchoolClass, StudentProfile, TeacherStudentScope, User, UserRole,
    )

    db = get_sessionmaker()()

    def ensure_user(login, name):
        row = db.query(User).filter_by(tenant_id=TID, login_name=login).first()
        if row is None:
            row = User(tenant_id=TID, login_name=login, real_name=name,
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
        db.flush()

    admin = ensure_user("school_admin01", "张校长")
    bind(admin, ensure_role("SCHOOL_ADMIN", "校级管理员"))
    counselor = ensure_user("counselor01", "王莉")
    bind(counselor, ensure_role("COUNSELOR", "辅导员"))

    college = College(tenant_id=TID, college_name="U3风险学院", code="U3-C", status="ACTIVE")
    db.add(college)
    db.flush()
    major = Major(tenant_id=TID, college_id=college.id, major_name="U3专业",
                  code="U3-M", status="ACTIVE")
    db.add(major)
    db.flush()
    klass = SchoolClass(tenant_id=TID, major_id=major.id, class_name="A班", grade="2024",
                        counselor_id=counselor.id, status="ACTIVE")
    db.add(klass)
    db.flush()
    db.add_all([
        AffairsCounselorAssignment(
            tenant_id=TID, class_id=klass.id, user_id=counselor.id, duty_type="PRIMARY",
            status="ACTIVE", effective_from=datetime.utcnow() - timedelta(days=1)),
        TeacherStudentScope(
            tenant_id=TID, teacher_key="counselor01", teacher_name="王莉",
            role_code="COUNSELOR", scope_type="CLASS", ref_value="A班", status="ACTIVE"),
    ])

    student = StudentProfile(tenant_id=TID, student_no="U3S001", real_name="学生甲",
                             class_id=klass.id, college_id=college.id, gender="M",
                             current_stage="CAMPUS", student_status="NORMAL", status="ACTIVE")
    db.add(student)
    db.flush()

    def risk(status, owner=None):
        row = AffairsRiskRecord(
            tenant_id=TID, student_id=student.id, source="BEHAVIOR", risk_level="HIGH",
            title=f"U3-{status}", detail="自认领用例", status=status,
            owner_id=owner.id if owner else None, version=1)
        db.add(row)
        db.flush()
        return row

    ids = {
        "new": risk("NEW").id,
        "escalated": risk("ESCALATED", owner=counselor).id,
        "closed": risk("CLOSED", owner=admin).id,
    }
    db.commit()
    ids.update({"admin": admin.id, "counselor": counselor.id, "student": student.id})
    db.close()
    return ids


def _rows(client, hdr):
    r = client.get("/api/v1/student-affairs/risk/records", headers=hdr,
                   params={"page": 1, "pageSize": 50})
    assert r.status_code == 200, r.text
    return {str(x["riskId"]): x for x in r.json()["data"]["items"]}


def _claim(client, hdr, risk_id, version=1):
    return client.post(f"/api/v1/student-affairs/risk/records/{risk_id}/assign",
                       headers=hdr, json={"ownerId": "me", "version": version})


def test_list_exposes_can_claim_for_eligible_caller(client, db_mode):
    """有处置资格 + 该行可 ASSIGN 时才下发 canClaim。"""
    ids = _seed(db_mode)
    hdr = _hdr(client, "school_admin01")
    rows = _rows(client, hdr)

    new_row = rows[str(ids["new"])]
    assert new_row["canClaim"] is True, new_row
    assert "ASSIGN" in new_row["allowedActions"]

    closed_row = rows[str(ids["closed"])]
    assert closed_row["canClaim"] is False, "已办结记录不该允许认领"

    esc_row = rows[str(ids["escalated"])]
    assert esc_row["canClaim"] is False, "ESCALATED 不在 ASSIGN 的 from 集合里，不能认领"


def test_claim_goes_through_the_canonical_assign_chain(client, db_mode):
    """认领后必须真的落库成 ASSIGNED，责任人是本人，并留下 ASSIGN 处置痕迹。"""
    ids = _seed(db_mode)
    hdr = _hdr(client, "school_admin01")

    res = _claim(client, hdr, ids["new"])
    body = res.json()
    assert body["code"] == 0, body
    assert body["data"]["status"] == "ASSIGNED", body["data"]
    assert str(body["data"]["ownerId"]) == str(ids["admin"]), body["data"]

    handles = client.get(f"/api/v1/student-affairs/risk/records/{ids['new']}/handles",
                         headers=hdr).json()["data"]["items"]
    assert any(h["action"] == "ASSIGN" for h in handles), handles
    assert not any(h["action"] == "TAKEOVER" for h in handles), (
        "self-assign 绝不能走 TAKEOVER —— 那是升级后的上级接管")


def test_claim_respects_the_state_machine(client, db_mode):
    """状态机不因便利性放宽：已办结记录认领必须被拒。"""
    ids = _seed(db_mode)
    hdr = _hdr(client, "school_admin01")
    res = _claim(client, hdr, ids["closed"])
    assert res.json()["code"] != 0, "CLOSED 不在 ASSIGN 的 from 集合里，必须拒绝"


def test_claim_still_enforces_optimistic_lock(client, db_mode):
    """乐观锁不能被绕过：版本不对必须冲突。"""
    ids = _seed(db_mode)
    hdr = _hdr(client, "school_admin01")
    res = _claim(client, hdr, ids["new"], version=999)
    assert res.json()["code"] != 0, "过期版本必须冲突，不能静默成功"


def test_claim_rejects_accounts_without_handling_authority(client, db_mode):
    """无风险处置资格的账号：既不下发 canClaim，也认领不了。"""
    ids = _seed(db_mode)
    hdr = _hdr(client, "student01")
    listing = client.get("/api/v1/student-affairs/risk/records", headers=hdr,
                         params={"page": 1, "pageSize": 50})
    if listing.status_code == 200 and listing.json().get("code") == 0:
        for row in listing.json()["data"]["items"]:
            assert not row.get("canClaim"), f"无处置资格却下发了 canClaim：{row}"
    res = _claim(client, hdr, ids["new"])
    assert res.json().get("code") != 0, "无处置资格的账号不得认领风险"


def test_list_hides_claim_when_the_active_role_cannot_handle_risks(client, db_mode):
    """多身份账号只能按当前激活角色显示按钮，不能借兼任角色扩大 UI 动作。"""
    ids = _seed(db_mode)
    from app.core.security import create_access_token, decode_token
    from app.db.session import get_sessionmaker
    from app.models import Role, User, UserRole

    db = get_sessionmaker()()
    admin = db.get(User, ids["admin"])
    viewer = db.query(Role).filter_by(tenant_id=TID, role_code="LEADER").first()
    if viewer is None:
        viewer = Role(tenant_id=TID, role_code="LEADER", role_name="校级只读领导",
                      role_type="SYSTEM", status="ACTIVE")
        db.add(viewer)
        db.flush()
    if db.query(UserRole).filter_by(
            tenant_id=TID, user_id=admin.id, role_id=viewer.id).first() is None:
        db.add(UserRole(tenant_id=TID, user_id=admin.id, role_id=viewer.id, status="ACTIVE"))
    db.commit()
    viewer_id, login, name = viewer.id, admin.login_name, admin.real_name
    db.close()

    # 复用正常登录签发的租户/权限版本快照，只切当前激活身份，避免手造 token
    # 漏掉 tenantVersion / permissionVersion 而被会话安全守卫提前拒绝。
    base_hdr = _hdr(client, "school_admin01")
    claims = decode_token(base_hdr["Authorization"].removeprefix("Bearer "))
    claims.update({
        "userId": f"db-{ids['admin']}", "loginName": login, "realName": name,
        "userType": "TEACHER", "activeContextId": f"role:{viewer_id}",
        "currentRoleCode": "LEADER", "clientType": "PC",
    })
    token = create_access_token(claims)
    rows = _rows(client, {"Authorization": f"Bearer {token}"})
    assert rows[str(ids["new"])]["canClaim"] is False, (
        "当前激活角色无风险处置权限时，不得借账号的 SCHOOL_ADMIN 兼任角色显示认领")
