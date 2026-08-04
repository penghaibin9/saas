"""PLAT-04 租户自动开通、初始化与上线验收（真库）。

对应必测 PLAT04-T01～T04：
任一步失败可续跑 / 重复执行不重复创建角色/管理员 /
补偿失败进入人工队列 / 健康验证失败不READY。

真实动作复用 platform_service.py（Tenant/TenantBrandConfig/TENANT_META/
ensure_builtin_roles/create_school_admin，均已被 test_platform.py 验证过）；
本文件只测"任务编排层"本身的续跑、幂等和补偿语义。
"""
import uuid

import pytest

from app.core.exceptions import AppException


def _key() -> str:
    return f"plat04-test-{uuid.uuid4().hex[:12]}"


def _code() -> str:
    return f"plat04sch{uuid.uuid4().hex[:8]}"


# ── PLAT04-T01：任一步失败可续跑 ─────────────────────────────────────────────
def test_t01_missing_admin_fields_then_resume_after_fix(db_mode):
    from app.services import tenant_provisioning_service as prov

    key, code = _key(), _code()
    admin = {"userId": "db-1", "currentRoleCode": "PLATFORM_SUPER_ADMIN"}

    # 缺 adminLoginName/adminRealName：FIRST_ADMIN 步骤必然失败
    job = prov.start_provisioning_job(admin, {
        "idempotencyKey": key, "tenantCode": code, "tenantName": "PLAT04测试学校T01"})
    assert job["status"] == "FAILED"
    failed_step = next(s for s in job["steps"] if s["status"] == "FAILED")
    assert failed_step["stepCode"] == "FIRST_ADMIN"
    tenant_step = next(s for s in job["steps"] if s["stepCode"] == "TENANT")
    assert tenant_step["status"] == "SUCCEEDED"  # 前面成功的步骤保留，不重跑

    # 用同一个 job 续跑：直接调用 run_provisioning_job 无法补齐输入，
    # 真实做法是重新提交同 idempotencyKey 且带上缺的字段——验证幂等命中同一任务并推进
    resumed = prov.start_provisioning_job(admin, {
        "idempotencyKey": key, "tenantCode": code, "tenantName": "PLAT04测试学校T01",
        "adminLoginName": f"admin-{code}", "adminRealName": "首位管理员"})
    assert resumed["jobId"] == job["jobId"]  # 同一个任务，没有另建一个
    assert resumed["status"] == "SUCCEEDED"
    for step in resumed["steps"]:
        assert step["status"] == "SUCCEEDED"
    # TENANT 步骤没有被重跑第二次（attempt_count 维持第一次的 1）
    tenant_step2 = next(s for s in resumed["steps"] if s["stepCode"] == "TENANT")
    assert tenant_step2["attemptCount"] == 1


def test_t01b_retry_step_only_reruns_failed_step(db_mode):
    from app.services import tenant_provisioning_service as prov

    key, code = _key(), _code()
    admin = {"userId": "db-1", "currentRoleCode": "PLATFORM_SUPER_ADMIN"}
    job = prov.start_provisioning_job(admin, {
        "idempotencyKey": key, "tenantCode": code, "tenantName": "PLAT04测试学校T01B"})
    assert job["status"] == "FAILED"

    with pytest.raises(AppException):
        prov.retry_step(int(job["jobId"]), "TENANT", user=admin)  # TENANT 已 SUCCEEDED，不许重试


# ── PLAT04-T02：重复执行不重复创建角色/管理员 ────────────────────────────────
def test_t02_duplicate_submission_does_not_duplicate_roles_or_admin(db_mode):
    from sqlalchemy import func, select

    from app.db.session import get_sessionmaker
    from app.models import Role, User
    from app.services import tenant_provisioning_service as prov

    key, code = _key(), _code()
    admin = {"userId": "db-1", "currentRoleCode": "PLATFORM_SUPER_ADMIN"}
    body = {"idempotencyKey": key, "tenantCode": code, "tenantName": "PLAT04测试学校T02",
           "adminLoginName": f"admin-{code}", "adminRealName": "首位管理员"}

    first = prov.start_provisioning_job(admin, body)
    assert first["status"] == "SUCCEEDED"
    tenant_id = int(first["tenantId"])

    second = prov.start_provisioning_job(admin, body)  # 完全重复提交同一份请求
    assert second["jobId"] == first["jobId"]
    assert second["status"] == "SUCCEEDED"

    db = get_sessionmaker()()
    try:
        admin_role_count = db.scalar(select(func.count()).select_from(Role).where(
            Role.tenant_id == tenant_id, Role.role_code == "SCHOOL_ADMIN",
            Role.is_deleted.is_(False)))
        assert admin_role_count == 1
        user_count = db.scalar(select(func.count()).select_from(User).where(
            User.tenant_id == tenant_id, User.login_name == f"admin-{code}"))
        assert user_count == 1
    finally:
        db.close()


def test_t02b_first_admin_reveals_password_only_once(db_mode):
    from app.services import tenant_provisioning_service as prov

    key, code = _key(), _code()
    admin = {"userId": "db-1", "currentRoleCode": "PLATFORM_SUPER_ADMIN"}
    body = {"idempotencyKey": key, "tenantCode": code, "tenantName": "PLAT04测试学校T02B",
           "adminLoginName": f"admin-{code}", "adminRealName": "首位管理员"}

    first = prov.start_provisioning_job(admin, body)
    assert "FIRST_ADMIN" in first["revealOnce"]
    assert first["revealOnce"]["FIRST_ADMIN"]["initialPassword"]

    admin_step = next(s for s in first["steps"] if s["stepCode"] == "FIRST_ADMIN")
    assert "initialPassword" not in (admin_step["output"] or {})  # 不落库明文

    second = prov.start_provisioning_job(admin, body)  # 重复提交：不会再次暴露密码
    assert second.get("revealOnce", {}).get("FIRST_ADMIN") is None


# ── PLAT04-T03：补偿失败进入人工队列 ─────────────────────────────────────────
def test_t03_compensation_then_manual_review_queue(db_mode):
    from app.services import tenant_provisioning_service as prov

    key, code = _key(), _code()
    admin = {"userId": "db-1", "currentRoleCode": "PLATFORM_SUPER_ADMIN"}
    job = prov.start_provisioning_job(admin, {
        "idempotencyKey": key, "tenantCode": code, "tenantName": "PLAT04测试学校T03"})
    assert job["status"] == "FAILED"
    job_id = int(job["jobId"])

    compensated = prov.compensate_step(job_id, "FIRST_ADMIN", reason="缺少必填字段，先补偿确认无脏数据",
                                       user=admin)
    step = next(s for s in compensated["steps"] if s["stepCode"] == "FIRST_ADMIN")
    assert step["status"] == "COMPENSATED"

    with pytest.raises(AppException):
        prov.compensate_step(job_id, "FIRST_ADMIN", reason="再次补偿应该被拒绝", user=admin)

    flagged = prov.flag_manual_review(job_id, "FIRST_ADMIN", reason="需要人工确认联系学校要正确信息",
                                      user=admin)
    step2 = next(s for s in flagged["steps"] if s["stepCode"] == "FIRST_ADMIN")
    assert step2["status"] == "NEEDS_MANUAL_REVIEW"

    queue = prov.manual_review_queue()
    assert any(x["jobId"] == str(job_id) and x["stepCode"] == "FIRST_ADMIN" for x in queue)

    overview = prov.governance_overview()
    assert overview["manualReviewCount"] >= 1


def test_t03b_compensate_requires_reason(db_mode):
    from app.services import tenant_provisioning_service as prov

    key, code = _key(), _code()
    admin = {"userId": "db-1", "currentRoleCode": "PLATFORM_SUPER_ADMIN"}
    job = prov.start_provisioning_job(admin, {
        "idempotencyKey": key, "tenantCode": code, "tenantName": "PLAT04测试学校T03B"})
    with pytest.raises(AppException):
        prov.compensate_step(int(job["jobId"]), "FIRST_ADMIN", reason="太短", user=admin)


# ── PLAT04-T04：健康验证失败不READY ──────────────────────────────────────────
def test_t04_health_check_blocks_ready_when_implementation_project_missing(db_mode, monkeypatch):
    from app.services import tenant_provisioning_service as prov

    # 让 IMPLEMENTATION_PROJECT 步骤"看似成功"但不真的建项目，验证 HEALTH_CHECK 会发现并拦下。
    def _fake_impl_project(db, job):
        return {"projectId": None, "reused": False, "fabricated": True}

    monkeypatch.setattr(prov, "_step_implementation_project", _fake_impl_project)

    key, code = _key(), _code()
    admin = {"userId": "db-1", "currentRoleCode": "PLATFORM_SUPER_ADMIN"}
    job = prov.start_provisioning_job(admin, {
        "idempotencyKey": key, "tenantCode": code, "tenantName": "PLAT04测试学校T04",
        "adminLoginName": f"admin-{code}", "adminRealName": "首位管理员"})

    assert job["status"] == "FAILED"  # 不是 SUCCEEDED——健康验证没有被静默放行
    health_step = next(s for s in job["steps"] if s["stepCode"] == "HEALTH_CHECK")
    assert health_step["status"] == "FAILED"
    assert "实施项目缺失" in (health_step["error"] or "")


def test_t04b_full_flow_health_check_passes(db_mode):
    from app.services import tenant_provisioning_service as prov

    key, code = _key(), _code()
    admin = {"userId": "db-1", "currentRoleCode": "PLATFORM_SUPER_ADMIN"}
    job = prov.start_provisioning_job(admin, {
        "idempotencyKey": key, "tenantCode": code, "tenantName": "PLAT04测试学校T04B",
        "adminLoginName": f"admin-{code}", "adminRealName": "首位管理员"})
    assert job["status"] == "SUCCEEDED"
    health_step = next(s for s in job["steps"] if s["stepCode"] == "HEALTH_CHECK")
    assert health_step["status"] == "SUCCEEDED"
    assert health_step["output"]["hasImplementationProject"] is True


def test_cannot_cancel_succeeded_job(db_mode):
    from app.services import tenant_provisioning_service as prov

    key, code = _key(), _code()
    admin = {"userId": "db-1", "currentRoleCode": "PLATFORM_SUPER_ADMIN"}
    job = prov.start_provisioning_job(admin, {
        "idempotencyKey": key, "tenantCode": code, "tenantName": "PLAT04测试学校取消",
        "adminLoginName": f"admin-{code}", "adminRealName": "首位管理员"})
    assert job["status"] == "SUCCEEDED"
    with pytest.raises(AppException):
        prov.cancel_job(int(job["jobId"]), reason="不应该允许取消已成功的任务", user=admin)


# ── 复审补测：意外异常（非AppException）不能让步骤永远卡在RUNNING ──────────
def test_unexpected_exception_leaves_step_failed_and_retryable(db_mode, monkeypatch):
    """_execute_step 抛出非 AppException（如 RuntimeError）之前，这一步会永远停在
    RUNNING——retry_step/compensate_step 都只接受 FAILED，没有恢复路径。"""
    from app.services import tenant_provisioning_service as prov

    key, code = _key(), _code()
    admin = {"userId": "db-1", "currentRoleCode": "PLATFORM_SUPER_ADMIN"}

    original = prov._step_capabilities

    def _boom(db, job):
        raise RuntimeError("模拟意外错误（非业务校验失败）")

    monkeypatch.setattr(prov, "_step_capabilities", _boom)
    job = prov.start_provisioning_job(admin, {
        "idempotencyKey": key, "tenantCode": code, "tenantName": "PLAT04测试学校意外错误",
        "adminLoginName": f"admin-{code}", "adminRealName": "首位管理员"})
    assert job["status"] == "FAILED"
    cap_step = next(s for s in job["steps"] if s["stepCode"] == "CAPABILITIES")
    assert cap_step["status"] == "FAILED"
    assert "意外错误" in (cap_step["error"] or "")

    monkeypatch.setattr(prov, "_step_capabilities", original)
    resumed = prov.retry_step(int(job["jobId"]), "CAPABILITIES", user=admin)
    assert resumed["status"] == "SUCCEEDED"


# ── 复审补测：TENANT 步骤"租户行已存在但 TENANT_META 缺失"要在续跑时补全 ────
def test_step_tenant_backfills_missing_meta_when_tenant_row_preexists(db_mode):
    """模拟"上次执行败在建租户行之后、写 TENANT_META 之前"的窄缝场景：
    租户行已经存在但没有 TENANT_META。旧实现的 reused 分支会直接早退，
    永远不补 TENANT_META；修复后无论新建还是复用都会检查并补齐。"""
    from app.db.session import get_sessionmaker
    from app.models import Tenant
    from app.services import platform_service as psvc
    from app.services import tenant_provisioning_service as prov

    key, code = _key(), _code()
    admin = {"userId": "db-1", "currentRoleCode": "PLATFORM_SUPER_ADMIN"}

    db = get_sessionmaker()()
    try:
        tid = 1000000000000000091
        if db.get(Tenant, tid) is None:
            db.add(Tenant(id=tid, tenant_code=code, school_name="预置租户行", status="ACTIVE"))
            db.commit()
    finally:
        db.close()
    assert psvc.tenant_meta(tid) == {}  # 确认这条窄缝：租户行有了，META 还没有

    job = prov.start_provisioning_job(admin, {
        "idempotencyKey": key, "tenantCode": code, "tenantName": "PLAT04测试学校补META",
        "adminLoginName": f"admin-{code}", "adminRealName": "首位管理员"})
    assert job["status"] == "SUCCEEDED"
    tenant_step = next(s for s in job["steps"] if s["stepCode"] == "TENANT")
    assert tenant_step["output"]["reused"] is True
    meta = psvc.tenant_meta(tid)
    assert meta.get("packageCode")  # 补写成功，不再是空字典


# ── HTTP 端点冒烟 ────────────────────────────────────────────────────────────
def test_http_endpoints(client, db_mode):
    from app.core.security import create_access_token

    token = create_access_token({
        "userId": "u-plat04-owner", "realName": "平台负责人", "userType": "PLATFORM_SUPER_ADMIN",
        "tid": "platform", "tenantId": "1000000000000000000", "tenantName": "平台运营中心",
        "activeContextId": "ctx", "currentRoleCode": "PLATFORM_SUPER_ADMIN", "clientType": "PC"})
    headers = {"Authorization": f"Bearer {token}"}

    key, code = _key(), _code()
    r = client.post("/api/v1/platform/provisioning-jobs", headers=headers, json={
        "idempotencyKey": key, "tenantCode": code, "tenantName": "PLAT04测试学校HTTP",
        "adminLoginName": f"admin-{code}", "adminRealName": "首位管理员"})
    assert r.json()["code"] == 0, r.json()
    job_id = r.json()["data"]["jobId"]

    r = client.get("/api/v1/platform/provisioning-jobs/overview", headers=headers)
    assert r.json()["code"] == 0, r.json()

    r = client.get("/api/v1/platform/provisioning-jobs", headers=headers)
    assert r.json()["code"] == 0, r.json()

    r = client.get(f"/api/v1/platform/provisioning-jobs/{job_id}", headers=headers)
    assert r.json()["code"] == 0, r.json()
