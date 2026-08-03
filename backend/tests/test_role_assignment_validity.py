"""SYS-07 角色成员、自动业务身份与有效期（真库）。

对应必测 SYS07-T01～T03：
到期无需重新登录即失效 / 任务转交后旧身份失效 / 当前激活角色隔离不默认并集。
"""
from datetime import datetime, timedelta

import pytest

from app.core.exceptions import AppException
from app.services import business_identity_service as bis
from app.services import role_assignment_service as ras

MAIN_TENANT_ID = 1000000000000000001


def _session():
    from app.db.session import get_sessionmaker

    return get_sessionmaker()()


def _ensure_tenant(tenant_id: int = MAIN_TENANT_ID) -> None:
    from app.models import Tenant

    with _session() as db:
        if db.get(Tenant, int(tenant_id)) is None:
            db.add(Tenant(id=int(tenant_id), tenant_code="demo",
                          school_name="角色测试学校", status="ACTIVE"))
            db.commit()


def _make_user(login_name: str, *, real_name: str = "角色测试用户",
               user_type: str = "TEACHER", tenant_id: int = MAIN_TENANT_ID) -> int:
    from app.core.security import hash_password
    from app.models import User

    _ensure_tenant(tenant_id)
    with _session() as db:
        row = User(tenant_id=tenant_id, login_name=login_name, real_name=real_name,
                   password_hash=hash_password("Init123456"), user_type=user_type,
                   status="ACTIVE")
        db.add(row)
        db.commit()
        return int(row.id)


def _make_role(role_code: str, tenant_id: int = MAIN_TENANT_ID) -> int:
    from sqlalchemy import select

    from app.models import Role

    _ensure_tenant(tenant_id)
    with _session() as db:
        row = db.scalars(select(Role).where(
            Role.tenant_id == tenant_id, Role.role_code == role_code)).first()
        if row is None:
            row = Role(tenant_id=tenant_id, role_code=role_code, role_name=role_code,
                       role_type="SYSTEM", status="ACTIVE")
            db.add(row)
            db.commit()
        return int(row.id)


def _user_role_status(user_id: int, role_code: str) -> str:
    from sqlalchemy import select

    from app.models import Role, UserRole

    with _session() as db:
        row = db.execute(select(UserRole.status).join(
            Role, Role.id == UserRole.role_id).where(
            UserRole.tenant_id == MAIN_TENANT_ID, UserRole.user_id == int(user_id),
            Role.role_code == role_code)).first()
        return str(row[0]) if row else ""


def _login_roles(user_id: int) -> list[str]:
    """走真实鉴权取角色上下文——只有它说了算，不看治理表自说自话。"""
    from app.models import User
    from app.services import auth_service_db as auth

    with _session() as db:
        account = db.get(User, int(user_id))
        return [c["roleCode"] for c in auth._role_contexts(db, account)]


# ── SYS07-T01：到期立即失效，且不需要重新登录 ────────────────────────────────
def test_t01_expired_assignment_dies_without_relogin(db_mode):
    _make_role("COUNSELOR")
    user_id = _make_user("ras_expire_01")
    soon = (datetime.now().replace(microsecond=0) + timedelta(seconds=1))

    granted = ras.grant_assignment(user_id, "COUNSELOR", reason="学期内临时代管班级",
                                   expires_at=soon.strftime("%Y-%m-%d %H:%M:%S"),
                                   tenant_id=MAIN_TENANT_ID)
    assert granted["status"] == "ACTIVE"
    assert _user_role_status(user_id, "COUNSELOR") == "ACTIVE"
    assert "COUNSELOR" in _login_roles(user_id)

    # 把到期时间推到过去（等价于时间流逝），再走"读取时双保险"
    from app.models.role_assignment import RoleAssignmentValidity

    with _session() as db:
        row = db.get(RoleAssignmentValidity, int(granted["assignmentId"]))
        row.expires_at = datetime.now().replace(microsecond=0) - timedelta(minutes=1)
        db.commit()

    assert ras.effective_assignments(user_id, tenant_id=MAIN_TENANT_ID) == []
    # 关键：真实鉴权链路上的 t_user_role 也必须被翻掉，否则"到期"只是治理表的自我安慰
    assert _user_role_status(user_id, "COUNSELOR") == "EXPIRED"
    assert "COUNSELOR" not in _login_roles(user_id)


def test_t01b_sweep_is_the_other_half_of_the_safety_net(db_mode):
    _make_role("COUNSELOR")
    user_id = _make_user("ras_expire_02")
    granted = ras.grant_assignment(user_id, "COUNSELOR", reason="定时任务回收验证",
                                   expires_at=(datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S"),
                                   tenant_id=MAIN_TENANT_ID)
    from app.models.role_assignment import RoleAssignmentValidity

    with _session() as db:
        db.get(RoleAssignmentValidity, int(granted["assignmentId"])).expires_at = \
            datetime.now().replace(microsecond=0) - timedelta(minutes=1)
        db.commit()

    result = ras.sweep_expired(tenant_id=MAIN_TENANT_ID)
    assert result["count"] == 1
    assert str(user_id) in result["expiredUsers"]
    assert _user_role_status(user_id, "COUNSELOR") == "EXPIRED"
    # 幂等：再扫一次不会重复计数
    assert ras.sweep_expired(tenant_id=MAIN_TENANT_ID)["count"] == 0


def test_t01c_long_term_assignment_is_not_touched(db_mode):
    _make_role("ACADEMIC_ADMIN")
    user_id = _make_user("ras_longterm_01")
    ras.grant_assignment(user_id, "ACADEMIC_ADMIN", reason="长期岗位授权",
                         tenant_id=MAIN_TENANT_ID)
    ras.sweep_expired(tenant_id=MAIN_TENANT_ID)
    assert _user_role_status(user_id, "ACADEMIC_ADMIN") == "ACTIVE"
    assert len(ras.effective_assignments(user_id, tenant_id=MAIN_TENANT_ID)) == 1


# ── SYS07-T02：转交后旧身份立即失效 ─────────────────────────────────────────
def test_t02_transfer_kills_the_old_holder(db_mode):
    _make_role("COUNSELOR")
    old_id = _make_user("ras_transfer_old")
    new_id = _make_user("ras_transfer_new")
    granted = ras.grant_assignment(old_id, "COUNSELOR", reason="原辅导员岗位授权",
                                   tenant_id=MAIN_TENANT_ID)

    moved = ras.transfer_assignment(int(granted["assignmentId"]), to_user_id=new_id,
                                    reason="辅导员离岗，工作转交", tenant_id=MAIN_TENANT_ID)

    assert _user_role_status(old_id, "COUNSELOR") == "REVOKED"
    assert "COUNSELOR" not in _login_roles(old_id)
    assert ras.effective_assignments(old_id, tenant_id=MAIN_TENANT_ID) == []

    assert moved["userId"] == str(new_id)
    assert moved["sourceType"] == "TRANSFER"
    assert _user_role_status(new_id, "COUNSELOR") == "ACTIVE"
    assert "COUNSELOR" in _login_roles(new_id)

    old = ras.get_assignment(int(granted["assignmentId"]), tenant_id=MAIN_TENANT_ID)
    assert old["transferredToUserId"] == str(new_id), "转交去向必须可追溯"


def test_t02b_business_identity_follows_the_business_table(db_mode):
    """业务身份不是固定角色：业务关系一改，身份当场变。"""
    from app.models.internship import InternshipRecord

    old_id = _make_user("ras_advisor_old")
    new_id = _make_user("ras_advisor_new")
    with _session() as db:
        rec = InternshipRecord(tenant_id=MAIN_TENANT_ID, student_id=1,
                               advisor_user_id=old_id, advisor_name="旧指导教师",
                               status="ONGOING")
        db.add(rec)
        db.commit()
        record_id = int(rec.id)

    before = bis.list_business_identities(tenant_id=MAIN_TENANT_ID,
                                          identity_type=bis.IDENTITY_INTERNSHIP_ADVISOR)
    assert {r["userId"] for r in before["list"]} == {str(old_id)}

    with _session() as db:
        db.get(InternshipRecord, record_id).advisor_user_id = new_id
        db.commit()

    after = bis.list_business_identities(tenant_id=MAIN_TENANT_ID,
                                         identity_type=bis.IDENTITY_INTERNSHIP_ADVISOR)
    assert {r["userId"] for r in after["list"]} == {str(new_id)}, "旧指导教师的身份必须当场消失"


def test_t02c_manual_identity_never_grants_directly(db_mode):
    user_id = _make_user("ras_emergency_01")
    out = bis.request_manual_identity(identity_type=bis.IDENTITY_GD_MENTOR,
                                      user_id=user_id, reason="导师住院，临时应急处理",
                                      tenant_id=MAIN_TENANT_ID)
    assert out["granted"] is False
    assert out["status"] == "PENDING_SECURITY_CHANGE"
    assert out["changeSetId"]
    # 申请不产生任何身份
    rows = bis.list_business_identities(tenant_id=MAIN_TENANT_ID, user_id=user_id)
    assert rows["total"] == 0

    with pytest.raises(AppException):
        bis.request_manual_identity(identity_type="NOT_A_TYPE", user_id=user_id,
                                    reason="不存在的身份类型", tenant_id=MAIN_TENANT_ID)


# ── SYS07-T03：当前激活角色隔离，不默认并集 ────────────────────────────────
def test_t03_active_role_is_isolated_not_unioned(db_mode):
    from app.core.permissions import has_permission

    _make_role("COUNSELOR")
    _make_role("ACADEMIC_ADMIN")
    user_id = _make_user("ras_multi_role")
    ras.grant_assignment(user_id, "COUNSELOR", reason="同时带班的教务人员",
                         tenant_id=MAIN_TENANT_ID)
    ras.grant_assignment(user_id, "ACADEMIC_ADMIN", reason="同时担任教务管理员",
                         tenant_id=MAIN_TENANT_ID)
    assert set(_login_roles(user_id)) >= {"COUNSELOR", "ACADEMIC_ADMIN"}

    as_counselor = {"userId": f"db-{user_id}", "tenantId": str(MAIN_TENANT_ID),
                    "currentRoleCode": "COUNSELOR", "userType": "TEACHER"}
    as_academic = {**as_counselor, "currentRoleCode": "ACADEMIC_ADMIN"}

    # 找一个只有教务管理员才有、辅导员没有的权限，验证不并集
    academic_only = None
    from app.core.permissions import ROLE_PERMISSIONS

    for code in sorted(ROLE_PERMISSIONS.get("ACADEMIC_ADMIN", set())):
        if code.endswith("*") or code in ROLE_PERMISSIONS.get("COUNSELOR", set()):
            continue
        if has_permission(as_academic, code) and not has_permission(as_counselor, code):
            academic_only = code
            break
    assert academic_only, "找不到可用于验证的教务专属权限码"
    assert has_permission(as_counselor, academic_only) is False, "多角色不得默认并集"


# ── 首屏结论分类 ─────────────────────────────────────────────────────────────
def test_summary_buckets(db_mode):
    _make_role("COUNSELOR")
    _make_role("SCHOOL_ADMIN")
    soon_user = _make_user("ras_bucket_soon")
    long_user = _make_user("ras_bucket_long")
    admin_a = _make_user("ras_bucket_admin_a")
    admin_b = _make_user("ras_bucket_admin_b")

    ras.grant_assignment(soon_user, "COUNSELOR", reason="即将到期的授权",
                         expires_at=(datetime.now() + timedelta(days=3)).strftime("%Y-%m-%d %H:%M:%S"),
                         tenant_id=MAIN_TENANT_ID)
    ras.grant_assignment(long_user, "COUNSELOR", reason="长期未复核授权",
                         tenant_id=MAIN_TENANT_ID)
    ras.grant_assignment(admin_a, "SCHOOL_ADMIN", reason="学校管理员甲",
                         tenant_id=MAIN_TENANT_ID)
    ras.grant_assignment(admin_b, "SCHOOL_ADMIN", reason="学校管理员乙",
                         tenant_id=MAIN_TENANT_ID)

    listed = ras.list_assignments(tenant_id=MAIN_TENANT_ID)
    summary = listed["summary"]
    assert summary[ras.BUCKET_EXPIRING_SOON] >= 1
    assert summary[ras.BUCKET_UNREVIEWED] >= 1
    assert summary[ras.BUCKET_HIGH_PRIV_MULTI] >= 1

    filtered = ras.list_assignments(tenant_id=MAIN_TENANT_ID,
                                    bucket=ras.BUCKET_EXPIRING_SOON)
    assert filtered["total"] >= 1
    assert all(row["expiresAt"] for row in filtered["list"])


def test_legacy_assignment_without_validity_is_flagged_unknown_source(db_mode):
    """历史直接写 t_user_role 的授权没有有效期行，必须被标成来源不明，不能装看不见。"""
    from app.models import UserRole

    role_id = _make_role("COUNSELOR")
    user_id = _make_user("ras_legacy_01")
    with _session() as db:
        db.add(UserRole(tenant_id=MAIN_TENANT_ID, user_id=user_id, role_id=role_id,
                        status="ACTIVE"))
        db.commit()

    listed = ras.list_assignments(tenant_id=MAIN_TENANT_ID)
    assert listed["summary"][ras.BUCKET_UNKNOWN_SOURCE] >= 1
    legacy = [r for r in listed["list"] if r["userId"] == str(user_id)]
    assert legacy and legacy[0]["sourceType"] == "UNKNOWN"


def test_review_clears_unreviewed_bucket(db_mode):
    _make_role("COUNSELOR")
    user_id = _make_user("ras_review_01")
    granted = ras.grant_assignment(user_id, "COUNSELOR", reason="长期授权待复核",
                                   tenant_id=MAIN_TENANT_ID)
    before = ras.list_assignments(tenant_id=MAIN_TENANT_ID)["summary"][ras.BUCKET_UNREVIEWED]
    ras.review_assignment(int(granted["assignmentId"]), term="2026-2027-1",
                          reason="岗位仍在，继续保留", tenant_id=MAIN_TENANT_ID)
    after = ras.list_assignments(tenant_id=MAIN_TENANT_ID)["summary"][ras.BUCKET_UNREVIEWED]
    assert after == before - 1


def test_revoke_version_conflict(db_mode):
    _make_role("COUNSELOR")
    user_id = _make_user("ras_version_01")
    granted = ras.grant_assignment(user_id, "COUNSELOR", reason="版本冲突验证",
                                   tenant_id=MAIN_TENANT_ID)
    stale = int(granted["version"])
    ras.review_assignment(int(granted["assignmentId"]), term="2026-2027-1",
                          reason="先复核一次抬高版本", tenant_id=MAIN_TENANT_ID)
    with pytest.raises(AppException) as caught:
        ras.revoke_assignment(int(granted["assignmentId"]), reason="拿旧版本回收",
                              expected_version=stale, tenant_id=MAIN_TENANT_ID)
    assert caught.value.code == "DATA_CONFLICT"
    assert caught.value.http_status == 409


def test_grant_validates_input(db_mode):
    _make_role("COUNSELOR")
    user_id = _make_user("ras_validate_01")
    with pytest.raises(AppException):
        ras.grant_assignment(user_id, "COUNSELOR", reason="短", tenant_id=MAIN_TENANT_ID)
    with pytest.raises(AppException):
        ras.grant_assignment(user_id, "NOT_A_ROLE", reason="角色不存在的授权",
                             tenant_id=MAIN_TENANT_ID)
    with pytest.raises(AppException) as caught:
        ras.grant_assignment(user_id, "COUNSELOR", reason="到期早于生效",
                             effective_at="2026-09-01", expires_at="2026-08-01",
                             tenant_id=MAIN_TENANT_ID)
    assert "晚于" in caught.value.message


# ── 接口层 ───────────────────────────────────────────────────────────────────
def test_http_endpoints(client, auth_headers, db_mode):
    _make_role("COUNSELOR")
    user_id = _make_user("ras_http_01")

    granted = client.post("/api/v1/system/role-assignments", headers=auth_headers,
                          json={"userId": str(user_id), "roleCode": "COUNSELOR",
                                "reason": "接口层授予验证",
                                "expiresAt": (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")}).json()
    assert granted["code"] == 0
    assignment_id = granted["data"]["assignmentId"]

    listed = client.get("/api/v1/system/role-assignments", headers=auth_headers).json()
    assert listed["code"] == 0 and listed["data"]["total"] >= 1
    assert "summary" in listed["data"]

    identities = client.get("/api/v1/system/business-identities", headers=auth_headers).json()
    assert identities["code"] == 0
    assert len(identities["data"]["types"]) == 6

    swept = client.post("/api/v1/system/role-assignments/sweep-expired",
                        headers=auth_headers).json()
    assert swept["code"] == 0

    revoked = client.post(f"/api/v1/system/role-assignments/{assignment_id}/revoke",
                          headers=auth_headers,
                          json={"reason": "接口层回收验证"}).json()
    assert revoked["code"] == 0 and revoked["data"]["status"] == "REVOKED"
    assert _user_role_status(user_id, "COUNSELOR") == "REVOKED"
