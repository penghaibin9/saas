"""真实双租户演示登录改造测试：
demo-school(admin/teacher/student·123456·只读) + sandbox-school(admin2/teacher2/student2·123456·可重置)。
覆盖：真实登录、hash 落库、生产 mock-login 关闭、双租户隔离、学生 stats 403、
教师范围看得见=能处理（沙箱）、demo 只读锁、沙箱重置 dry-run/confirm。"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

DEMO_TID = 1000000000000000003
SBX_TID = 1000000000000000007


def _run_seed_as_school_admin(db, tenant_id: int, tenant_code: str, seeder) -> None:
    """Seed formal file-backed facts under an explicit tenant/admin context.

    Production file binding is intentionally fail-closed when no actor exists. Seed
    fixtures are trusted setup code, so they must install the same explicit context a
    real school-admin request would carry instead of relying on an ambient fallback.
    """
    from app.core.context import set_current_user, set_tenant

    set_tenant({
        "tenantId": str(tenant_id),
        "tenantCode": tenant_code,
        "tenantName": tenant_code,
        "status": "ACTIVE",
    })
    set_current_user({
        "userId": f"pytest-seed-{tenant_id}",
        "realName": "Pytest Seed Admin",
        "userType": "ADMIN",
        "tenantCode": tenant_code,
        "tenantId": str(tenant_id),
        "currentRoleCode": "SCHOOL_ADMIN",
        "loginName": "pytest-seed-admin",
    })
    try:
        seeder(db)
    finally:
        set_current_user(None)
        set_tenant(None)


@pytest.fixture()
def two_tenants(db_mode):
    """在 db_mode 空库上种双租户体系（demo 富数据 + sandbox 最小数据）。"""
    from app.db.session import get_sessionmaker
    from _seed_demo_school import seed_demo_school
    from _seed_two_tenants import seed_demo_tenant, seed_sandbox_school
    db = get_sessionmaker()()
    try:
        _run_seed_as_school_admin(db, DEMO_TID, "demo-school", seed_demo_school)
        _run_seed_as_school_admin(db, DEMO_TID, "demo-school", seed_demo_tenant)
        _run_seed_as_school_admin(db, SBX_TID, "sandbox-school", seed_sandbox_school)
    finally:
        db.close()
    return db_mode


def _login(client, login_name, password="123456"):
    return client.post("/api/v1/auth/login",
                       json={"loginName": login_name, "password": password}).json()


def _h(data):
    return {"Authorization": "Bearer " + data["data"]["accessToken"]}


def _switch_role(client, auth_result: dict, role_code: str) -> dict:
    """走真实 /auth/switch-role，禁止在测试里伪造更高权限 token。"""
    contexts = auth_result["data"].get("contexts") or []
    target = next((item for item in contexts if item.get("roleCode") == role_code), None)
    assert target is not None, f"missing role context {role_code}: {contexts}"
    switched = client.post(
        "/api/v1/auth/switch-role",
        headers=_h(auth_result),
        json={"contextId": target["contextId"], "clientType": "TEACHER_MINI"},
    ).json()
    assert switched["code"] == 0, switched
    assert switched["data"]["currentRole"]["roleCode"] == role_code, switched
    return switched


def _running_internship_batch_id(tenant_id: int) -> str:
    """按生产显式批次合同选择该租户当前 RUNNING 实习批次。"""
    from sqlalchemy import select
    from app.db.session import get_sessionmaker
    from app.models import InternshipBatch

    db = get_sessionmaker()()
    try:
        row = db.scalars(select(InternshipBatch).where(
            InternshipBatch.tenant_id == tenant_id,
            InternshipBatch.status == "RUNNING",
            InternshipBatch.is_deleted.is_(False),
        ).order_by(InternshipBatch.id.desc())).first()
        assert row is not None, f"tenant {tenant_id} missing RUNNING internship batch"
        return str(row.id)
    finally:
        db.close()


def _platform_h():
    from app.core.security import create_access_token
    token = create_access_token({
        "userId": "platform-demo-operator", "realName": "平台运营",
        "userType": "PLATFORM_SUPER_ADMIN", "currentRoleCode": "PLATFORM_SUPER_ADMIN",
        "tenantId": "1000000000000000000", "tenantName": "平台运营中心",
        "activeContextId": "ctx_platform_demo_operator", "clientType": "PC",
    })
    return {"Authorization": "Bearer " + token}


# ═══ 1-6：六个账号真实登录 ═══

def test_all_six_accounts_login(client, two_tenants):
    for login, tid, role in [
        ("admin", DEMO_TID, "SCHOOL_ADMIN"), ("teacher", DEMO_TID, "COUNSELOR"),
        ("student", DEMO_TID, "STUDENT"),
        ("admin2", SBX_TID, "SCHOOL_ADMIN"), ("teacher2", SBX_TID, "COUNSELOR"),
        ("student2", SBX_TID, "STUDENT"),
    ]:
        r = _login(client, login)
        assert r["code"] == 0, (login, r.get("message"))
        assert r["data"]["tenantId"] == str(tid), login
        assert r["data"]["currentRole"]["roleCode"] == role, login
        if login == "teacher2":
            role_codes = {item["roleCode"] for item in (r["data"].get("contexts") or [])}
            assert {"COUNSELOR", "INTERN_MENTOR", "GD_MENTOR"}.issubset(role_codes)
    # 密码错误 → 明确业务错，不是 500
    bad = _login(client, "admin", "wrong-pass")
    assert bad["code"] == 401001


def test_student_token_carries_student_no(client, two_tenants):
    r = _login(client, "student")
    import jwt as _jwt
    from app.core.config import settings
    claims = _jwt.decode(r["data"]["accessToken"], settings.jwt_secret,
                         algorithms=[settings.jwt_algorithm])
    assert claims["tenantId"] == str(DEMO_TID)
    assert claims["studentNo"] == "2026D0006"
    assert claims["userType"] == "STUDENT"
    r2 = _login(client, "student2")
    c2 = _jwt.decode(r2["data"]["accessToken"], settings.jwt_secret,
                     algorithms=[settings.jwt_algorithm])
    assert c2["tenantId"] == str(SBX_TID) and c2["studentNo"] == "2026S0001"


# ═══ 16：123456 不明文落库 ═══

def test_password_hashed_not_plaintext(client, two_tenants):
    from sqlalchemy import select
    from app.db.session import get_sessionmaker
    from app.models import User
    db = get_sessionmaker()()
    try:
        rows = db.scalars(select(User).where(User.login_name.in_(
            ["admin", "teacher", "student", "admin2", "teacher2", "student2"]))).all()
        assert len(rows) == 6
        for u in rows:
            assert u.password_hash.startswith("pbkdf2_sha256$"), u.login_name
            assert "123456" not in u.password_hash, u.login_name
    finally:
        db.close()


# ═══ 7：production 下 mock-login 403 ═══

def test_mock_login_403_in_production(client, two_tenants, monkeypatch):
    from app.core.config import settings
    monkeypatch.setattr(settings, "APP_ENV", "production")
    monkeypatch.setattr(settings, "MOCK_LOGIN_ENABLED", "")
    r = client.post("/api/v1/auth/mock-login",
                    json={"loginName": "student01", "password": "demo"})
    assert r.status_code == 403
    assert "accessToken" not in (r.json().get("data") or {})
    # production 密码登录的验证码/风控存储按设计要求 Redis；本用例只验证 mock-login 关闭。
    # 恢复 test 环境后再验证真实账号链仍正常，避免把“生产无 Redis 应 fail-closed”误判成回归。
    monkeypatch.setattr(settings, "APP_ENV", "test")
    assert _login(client, "student")["code"] == 0


# ═══ 8-10：双租户严格隔离 ═══

def test_tenant_isolation_both_ways(client, two_tenants):
    demo_t = _h(_login(client, "teacher"))
    sbx_t = _h(_login(client, "teacher2"))
    # demo 教师看不到沙箱学生（按学号查 → 404 不泄露存在性）
    r1 = client.get("/api/v1/mobile/teacher/student/2026S0001", headers=demo_t).json()
    assert r1["code"] == 404001
    # 沙箱教师看不到 demo 学生
    r2 = client.get("/api/v1/mobile/teacher/student/2026D0006", headers=sbx_t).json()
    assert r2["code"] == 404001
    # 学生自视图各自只见本租户本人
    s_demo = client.get("/api/v1/mobile/me/overview", headers=_h(_login(client, "student"))).json()
    assert s_demo["data"]["student"]["studentNo"] == "2026D0006"
    s_sbx = client.get("/api/v1/mobile/me/overview", headers=_h(_login(client, "student2"))).json()
    assert s_sbx["data"]["student"]["studentNo"] == "2026S0001"


# ═══ 11：学生访问 stats → 403 ═══

def test_student_stats_403(client, two_tenants):
    for login in ("student", "student2"):
        r = client.get("/api/v1/stats/overview", headers=_h(_login(client, login))).json()
        assert r["code"] == 403001, login


# ═══ 12：教师只能看到自己范围内的学生 ═══

def test_teacher_scope_visibility(client, two_tenants):
    demo_t = _h(_login(client, "teacher"))
    rk = client.get("/api/v1/mobile/teacher/risk-students", headers=demo_t).json()
    assert rk["code"] == 0 and rk["data"]["scopeMode"] == "SCOPED"
    ok = client.get("/api/v1/mobile/teacher/student/2026D0006", headers=demo_t).json()
    assert ok["code"] == 0 and ok["data"]["hasData"] is True
    sbx_t = _h(_login(client, "teacher2"))
    ok2 = client.get("/api/v1/mobile/teacher/student/2026S0001", headers=sbx_t).json()
    assert ok2["code"] == 0


# ═══ 13：看得见 = 能处理（沙箱可写；demo 只读锁 403） ═══

def test_teacher_can_process_visible_items_in_sandbox(client, two_tenants):
    teacher_auth = _login(client, "teacher2")
    counselor_h = _h(teacher_auth)
    it = client.get("/api/v1/mobile/teacher/internship", headers=counselor_h,
                    params={"batchId": _running_internship_batch_id(SBX_TID)}).json()
    reports = it["data"]["weeklyReports"]
    assert len(reports) >= 1
    report = reports[0]
    rid = report["id"]

    # COUNSELOR 只能协同查看；真正批阅必须显式切到实习指导教师岗位。
    intern_auth = _switch_role(client, teacher_auth, "INTERN_MENTOR")
    intern_h = _h(intern_auth)
    ok = client.post(f"/api/v1/mobile/teacher/internship/weekly/{rid}/review",
                     headers=intern_h, json={"action": "APPROVE", "comment": "沙箱批阅通过",
                                             "expectedVersion": report["version"]}).json()
    assert ok["code"] == 0 and ok["data"]["status"] == "APPROVED", ok

    # 同一真实账号再切到毕设导师岗位，验证多岗位互不扩权、各域动作在正确身份下执行。
    gd_auth = _switch_role(client, intern_auth, "GD_MENTOR")
    gd_h = _h(gd_auth)
    gd = client.get("/api/v1/mobile/teacher/graduation", headers=gd_h).json()
    props = gd["data"]["reviewDetail"]
    assert len(props) >= 1
    pid = props[0]["id"]
    ok2 = client.post(f"/api/v1/mobile/teacher/graduation/proposal/{pid}/review",
                      headers=gd_h, json={"action": "APPROVE", "comment": "沙箱开题通过"}).json()
    assert ok2["code"] == 0, ok2


def test_demo_tenant_is_readonly(client, two_tenants):
    """正式演示租户：看得见但写操作被只读锁拦截（403 + 指引去沙箱）。"""
    demo_t = _h(_login(client, "teacher"))
    it = client.get("/api/v1/mobile/teacher/internship", headers=demo_t,
                    params={"batchId": _running_internship_batch_id(DEMO_TID)}).json()
    assert it["code"] == 0
    reports = it["data"]["weeklyReports"]
    assert len(reports) >= 1  # 看得见
    r = client.post(f"/api/v1/mobile/teacher/internship/weekly/{reports[0]['id']}/review",
                    headers=demo_t, json={"action": "APPROVE", "comment": "演示批阅",
                                          "expectedVersion": reports[0]["version"]})
    assert r.status_code == 403
    assert "沙箱" in r.json()["message"]
    # 学生写操作同样只读
    stu = _h(_login(client, "student"))
    r2 = client.post("/api/v1/mobile/campus-service/apply", headers=stu,
                     json={"serviceKey": "证明开具", "reason": "演示环境提交应被只读锁拦截"})
    assert r2.status_code == 403
    # 沙箱学生正常提交（对照组）
    stu2 = _h(_login(client, "student2"))
    r3 = client.post("/api/v1/mobile/campus-service/apply", headers=stu2,
                     json={"serviceKey": "证明开具", "reason": "沙箱提交应成功入库"}).json()
    assert r3["code"] == 0


# ═══ 14-15：沙箱重置 dry-run 不落库 / confirm 只影响沙箱 ═══

def _count_students(db, tid):
    from sqlalchemy import func, select
    from app.models import StudentProfile
    return db.scalar(select(func.count()).select_from(StudentProfile).where(
        StudentProfile.tenant_id == tid)) or 0


def test_sandbox_reset_dry_run_no_change(client, two_tenants):
    from app.db.session import get_sessionmaker
    from app.services.sandbox_service import reset_sandbox
    db = get_sessionmaker()()
    try:
        before = _count_students(db, SBX_TID)
        report = reset_sandbox(db, dry_run=True)
        assert report["dryRun"] is True and report["wouldRemove"]
        assert _count_students(db, SBX_TID) == before  # 未落库
    finally:
        db.close()


def test_sandbox_reset_confirm_only_affects_sandbox(client, two_tenants):
    from app.db.session import get_sessionmaker
    from app.services.sandbox_service import reset_sandbox
    db = get_sessionmaker()()
    try:
        demo_before = _count_students(db, DEMO_TID)
        # 沙箱先产生一条脏数据（学生提交申请）
        stu2 = _h(_login(client, "student2"))
        client.post("/api/v1/mobile/campus-service/apply", headers=stu2,
                    json={"serviceKey": "证明开具", "reason": "重置前的脏数据一条"})
        report = reset_sandbox(db, dry_run=False)
        assert report["removed"] and report["reseeded"]
        assert _count_students(db, SBX_TID) == 100    # 重建后回到完整演示学校基线
        assert _count_students(db, DEMO_TID) == demo_before  # demo 不受影响
        # 重置后账号仍可登录
        assert _login(client, "student2")["code"] == 0
    finally:
        db.close()


def test_sandbox_baseline_is_protected_but_new_rows_are_deletable(client, two_tenants):
    """预制行不可删；现场新增行未进入基线索引，仍可正常软删。"""
    from sqlalchemy import func, select
    from app.core.exceptions import AppException
    from app.db.session import get_sessionmaker
    from app.models import SandboxBaseline, StudentProfile

    db = get_sessionmaker()()
    try:
        protected_count = db.scalar(select(func.count()).select_from(SandboxBaseline).where(
            SandboxBaseline.tenant_id == SBX_TID)) or 0
        assert protected_count > 100

        baseline_student = db.scalars(select(StudentProfile).where(
            StudentProfile.tenant_id == SBX_TID,
            StudentProfile.is_deleted.is_(False)).order_by(StudentProfile.id)).first()
        baseline_student.is_deleted = True
        with pytest.raises(AppException, match="演示基线"):
            db.commit()
        db.rollback()

        live = StudentProfile(tenant_id=SBX_TID, student_no="LIVE-DEMO-0001",
                              real_name="现场新增学生", status="ENROLLED")
        db.add(live)
        db.commit()
        live.is_deleted = True
        db.commit()
        assert live.is_deleted is True
    finally:
        db.close()


def test_platform_can_restore_only_the_fixed_sandbox(client, two_tenants):
    denied = client.post(f"/api/v1/platform/tenants/{DEMO_TID}/reset-sandbox-data",
                         headers=_platform_h()).json()
    assert denied["code"] == 403001
    restored = client.post(f"/api/v1/platform/tenants/{SBX_TID}/reset-sandbox-data",
                           headers=_platform_h()).json()
    assert restored["code"] == 0
    assert restored["data"]["reseeded"]["students"] == 100