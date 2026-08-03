"""SYS-16 批处理、调度与后台任务授权（真库）。

对应必测 SYS16-T01～T04：
用户委托任务使用范围快照和吊销门禁 / 跨租户jobId返回404 /
重试幂等 / 旧revision按策略拒绝或重算。

不新建统一任务表——直接在既有 t_file_job / t_excel_import_job 等表上
造行验证，去重/状态机权威仍是这些表自己的字段。临时授权来自
system_governance_service（真实 DELEGATIONS 存储 + 实时鉴权），不是新发明的。
"""
from datetime import datetime, timedelta

import pytest

from app.core.context import set_tenant

TENANT_A = 1000000000000000103  # 注意：1000000000000000003 是 app/middleware/context.py
TENANT_B = 1000000000000000104  # 保留的 _DEMO_READONLY_TENANT_ID，测试租户须避开


def _session():
    from app.db.session import get_sessionmaker

    return get_sessionmaker()()


def _ensure_tenant(tid: int, name: str):
    from app.models import Tenant
    from app.services import platform_service as platform

    with _session() as db:
        if db.get(Tenant, tid) is None:
            db.add(Tenant(id=tid, tenant_code=f"demo16-{tid}", school_name=name, status="ACTIVE"))
            db.commit()
    platform.put_config_json(tid, "TENANT_META", "-", {"status": "active", "packageCode": "professional"})


@pytest.fixture()
def tenant_ctx(db_mode):
    _ensure_tenant(TENANT_A, "任务治理测试学校A")
    _ensure_tenant(TENANT_B, "任务治理测试学校B")
    set_tenant({"tenantId": str(TENANT_A)})
    try:
        yield TENANT_A
    finally:
        set_tenant(None)


def _make_role(role_code: str, tenant_id: int) -> int:
    from sqlalchemy import select

    from app.models import Role

    with _session() as db:
        row = db.scalars(select(Role).where(
            Role.tenant_id == tenant_id, Role.role_code == role_code)).first()
        if row is None:
            row = Role(tenant_id=tenant_id, role_code=role_code, role_name=role_code,
                      role_type="SYSTEM", status="ACTIVE")
            db.add(row)
            db.commit()
        return int(row.id)


def _make_user(login_name: str, *, password: str = "Init123456", role_code: str | None = None,
              tenant_id: int = TENANT_A) -> int:
    from app.core.security import hash_password
    from app.models import User, UserRole

    with _session() as db:
        row = User(tenant_id=tenant_id, login_name=login_name, real_name="任务治理测试账号",
                  password_hash=hash_password(password), user_type="TEACHER", status="ACTIVE")
        db.add(row)
        db.flush()
        if role_code:
            role_id = _make_role(role_code, tenant_id)
            db.add(UserRole(tenant_id=tenant_id, user_id=row.id, role_id=role_id, status="ACTIVE"))
        db.commit()
        return int(row.id)


def _login(client, login_name: str, password: str = "Init123456") -> dict:
    result = client.post("/api/v1/auth/login", json={
        "tenantCode": f"demo16-{TENANT_A}", "loginName": login_name,
        "password": password, "clientType": "PC"}).json()
    assert result["code"] == 0, result
    return {"Authorization": f"Bearer {result['data']['accessToken']}"}


def _make_file_job(status: str = "FAILED", tenant_id: int = TENANT_A, dedupe: str = "sys16-fj-1") -> int:
    from app.models.file import FileJob

    with _session() as db:
        row = FileJob(tenant_id=tenant_id, job_type="FILE_SCAN", dedupe_key=dedupe,
                      status=status, attempts=2, locked_by="worker-1")
        db.add(row)
        db.commit()
        return int(row.id)


def _make_excel_job(template_version: str, status: str = "FAILED", tenant_id: int = TENANT_A) -> int:
    from app.models.excel_import_job import ExcelImportJob

    with _session() as db:
        row = ExcelImportJob(tenant_id=tenant_id, module_key="sys16-test", biz_type="TEST",
                             template_version=template_version, status=status)
        db.add(row)
        db.commit()
        return int(row.id)


# ── SYS16-T01：用户委托任务使用范围快照和吊销门禁 ────────────────────────────
def test_t01_delegated_actor_can_act_then_loses_access_after_revoke(tenant_ctx):
    from app.core.exceptions import AppException
    from app.services import job_authorization_service as jauth
    from app.services import system_governance_service as gov

    admin = {"userId": "db-1", "currentRoleCode": "SCHOOL_ADMIN"}
    grantee_id = _make_user("sys16_t01_grantee")  # 无任何角色，天然没有 systemAdmin.job.manage
    grantee = {"userId": f"db-{grantee_id}", "currentRoleCode": ""}

    with pytest.raises(AppException):
        jauth.classify_and_authorize(grantee, "systemAdmin.job.manage")

    # _now() 用本机 datetime.now() 格式化为 "%Y-%m-%d %H:%M:%S"（非 UTC），
    # expiresAt 必须用同基准 + 足够冗余，避免本机时区偏移导致字符串比较误判过期。
    delegation = gov.create_delegation(admin, {
        "granteeUserNo": "sys16_t01_grantee", "roleCode": "SYS_ADMIN",
        "expiresAt": (datetime.now() + timedelta(hours=6)).strftime("%Y-%m-%d %H:%M:%S"),
        "reason": "临时处理批处理任务积压",
    })

    evidence = jauth.classify_and_authorize(grantee, "systemAdmin.job.manage")
    assert evidence["policyType"] == "USER_DELEGATED"
    assert evidence["delegatedSubject"] == delegation["id"]

    gov.revoke_delegation(admin, delegation["id"], "任务已处理完毕，提前回收")

    with pytest.raises(AppException):
        jauth.classify_and_authorize(grantee, "systemAdmin.job.manage")


def test_t01b_own_role_permission_classifies_as_tenant_system_task(tenant_ctx):
    from app.services import job_authorization_service as jauth

    admin = {"userId": "db-1", "currentRoleCode": "SCHOOL_ADMIN"}
    evidence = jauth.classify_and_authorize(admin, "systemAdmin.job.manage")
    assert evidence["policyType"] == "TENANT_SYSTEM_TASK"


def test_t01c_missing_userid_without_service_identity_is_never_auto_authorized(tenant_ctx):
    """回归锁：actor 没有 userId 时绝不能自动放行（曾经的 fail-open bug）。"""
    from app.core.exceptions import AppException
    from app.services import job_authorization_service as jauth

    assert jauth.classify({}, "systemAdmin.job.manage") is None
    with pytest.raises(AppException):
        jauth.classify_and_authorize({}, "systemAdmin.job.manage")

    # 只有显式声明 serviceIdentity 且 servicePermissions 真的覆盖时才算 SERVICE_POLICY
    unclaimed_service_actor = {"serviceIdentity": "cron-worker"}  # 没有 servicePermissions
    assert jauth.classify(unclaimed_service_actor, "systemAdmin.job.manage") is None

    valid_service_actor = {"serviceIdentity": "cron-worker",
                           "servicePermissions": ["systemAdmin.job.manage"]}
    evidence = jauth.classify(valid_service_actor, "systemAdmin.job.manage")
    assert evidence["policyType"] == "SERVICE_POLICY"


# ── SYS16-T02：跨租户jobId返回404 ────────────────────────────────────────────
def test_t02_cross_tenant_job_id_returns_404(tenant_ctx):
    from app.core.exceptions import AppException
    from app.services import job_registry as jr

    other_job_id = _make_file_job(tenant_id=TENANT_B, dedupe="sys16-t02-other")
    with _session() as db:
        with pytest.raises(AppException) as exc:
            jr.get_job(db, f"FILE_JOB:{other_job_id}")
        assert exc.value.http_status == 404


# ── SYS16-T03：重试幂等 ──────────────────────────────────────────────────────
def test_t03_retry_is_idempotent_and_rejects_second_call(tenant_ctx):
    from app.core.exceptions import AppException
    from app.services import job_registry as jr

    admin = {"userId": "db-1", "currentRoleCode": "SCHOOL_ADMIN"}
    job_id = _make_file_job(status="FAILED", dedupe="sys16-t03-dedupe")

    with _session() as db:
        result = jr.retry_job(db, f"FILE_JOB:{job_id}", actor=admin)
        assert result["status"] == "PENDING"

    with _session() as db:
        with pytest.raises(AppException) as exc:
            jr.retry_job(db, f"FILE_JOB:{job_id}", actor=admin)
        assert exc.value.http_status == 409  # 已经是 PENDING，不是 FAILED，拒绝二次重试

    from sqlalchemy import func, select

    from app.models.file import FileJob
    with _session() as db:
        cnt = db.scalar(select(func.count()).select_from(FileJob).where(
            FileJob.tenant_id == TENANT_A, FileJob.dedupe_key == "sys16-t03-dedupe"))
        assert cnt == 1  # 重试只翻转原行状态，不产生第二条任务


# ── SYS16-T04：旧revision按策略拒绝或重算 ────────────────────────────────────
def test_t04_stale_revision_retry_is_rejected(tenant_ctx):
    from app.core.exceptions import AppException
    from app.services import job_registry as jr

    admin = {"userId": "db-1", "currentRoleCode": "SCHOOL_ADMIN"}
    stale_job_id = _make_excel_job(template_version="v0-stale", status="FAILED")

    with _session() as db:
        with pytest.raises(AppException) as exc:
            jr.retry_job(db, f"EXCEL_IMPORT:{stale_job_id}", actor=admin)
        assert exc.value.http_status == 409


def test_t04b_current_revision_retry_succeeds(tenant_ctx):
    from app.services import job_registry as jr

    admin = {"userId": "db-1", "currentRoleCode": "SCHOOL_ADMIN"}
    fresh_job_id = _make_excel_job(template_version="v1", status="FAILED")

    with _session() as db:
        result = jr.retry_job(db, f"EXCEL_IMPORT:{fresh_job_id}", actor=admin)
        assert result["status"] == "UPLOADED"


# ── 只读治理面（overview / list / evidence）────────────────────────────────
def test_overview_and_list_and_evidence(tenant_ctx):
    from app.services import job_registry as jr

    admin = {"userId": "db-1", "currentRoleCode": "SCHOOL_ADMIN"}
    job_id = _make_file_job(status="FAILED", dedupe="sys16-overview-1")

    overview = jr.job_overview()
    assert overview["failed"] >= 1

    with _session() as db:
        items, total = jr.list_jobs(db, kind="FILE_JOB")
        assert total >= 1
        assert any(i["jobId"] == f"FILE_JOB:{job_id}" for i in items)

        evidence = jr.authorization_evidence(db, f"FILE_JOB:{job_id}", actor=admin)
        assert evidence["currentActorAuthorization"]["policyType"] == "TENANT_SYSTEM_TASK"
        assert evidence["initiator"] is not None or evidence["initiator"] is None  # created_by 可能为空，字段必须存在
        assert "idempotency" in evidence


# ── HTTP 端点冒烟 ────────────────────────────────────────────────────────────
def test_http_endpoints(client, tenant_ctx):
    _make_user("sys16_http_admin", role_code="SYS_ADMIN")
    headers = _login(client, "sys16_http_admin")
    job_id = _make_file_job(status="FAILED", dedupe="sys16-http-1")

    r = client.get("/api/v1/system/jobs/overview", headers=headers)
    assert r.json()["code"] == 0, r.json()

    r = client.get("/api/v1/system/job-types", headers=headers)
    assert r.json()["code"] == 0, r.json()

    r = client.get("/api/v1/system/jobs", headers=headers)
    assert r.json()["code"] == 0, r.json()

    r = client.get(f"/api/v1/system/jobs/FILE_JOB:{job_id}/authorization-evidence", headers=headers)
    assert r.json()["code"] == 0, r.json()

    r = client.post(f"/api/v1/system/jobs/FILE_JOB:{job_id}/retry", headers=headers)
    assert r.json()["code"] == 0, r.json()

    r = client.get("/api/v1/system/jobs/FILE_JOB:9999999999/authorization-evidence", headers=headers)
    assert r.json()["code"] != 0
    assert r.status_code == 404
