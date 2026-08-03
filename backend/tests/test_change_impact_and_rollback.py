"""PLAT-11 变更、发布、兼容性、灰度与回滚（真库）。

对应必测 PLAT11-T01～T04：
发布前列出服务和租户影响 / 冻结窗口阻断普通变更 /
灰度失败停止扩展并回滚 / 不可逆迁移有替代恢复方案。

影响计算复用 PLAT-08 的 service_catalog_service；冻结窗口复用既有
t_calendar_window（academic_calendar_service.py 已经维护，本文件只读）。
"""
import uuid
from datetime import datetime, timedelta

import pytest

from app.core.exceptions import AppException


def _svc_code() -> str:
    return f"P11{uuid.uuid4().hex[:8]}".upper()


REQUESTER = {"userId": "db-101", "realName": "变更发起人"}
APPROVER = {"userId": "db-102", "realName": "变更审批人"}


# ── PLAT11-T01：发布前列出服务和租户影响 ─────────────────────────────────────
def test_t01_assess_lists_direct_and_indirect_tenants(db_mode):
    from app.services import change_management_service as chg
    from app.services import service_catalog_service as svcat

    svc_a, svc_b = _svc_code(), _svc_code()
    svcat.upsert_service({"serviceCode": svc_a, "serviceName": svc_a, "tier": "P1"})
    svcat.upsert_service({"serviceCode": svc_b, "serviceName": svc_b, "tier": "P1"})
    svcat.add_dependency(svc_b, svc_a)

    t1, t2 = 992001, 992002
    svcat.record_tenant_usage(svc_a, t1)
    svcat.record_tenant_usage(svc_b, t2)

    change = chg.create_change(REQUESTER, {
        "title": "PLAT11-T01变更", "changeType": "CODE", "affectedServiceCodes": [svc_a]})
    assessed = chg.assess(int(change["changeId"]), user=REQUESTER)
    tenant_ids = {t["tenantId"] for t in assessed["affectedTenants"]}
    assert tenant_ids == {str(t1), str(t2)}
    direct = {t["tenantId"] for t in assessed["affectedTenants"] if t["impactType"] == "DIRECT"}
    assert direct == {str(t1)}


def test_t01b_cannot_assess_twice(db_mode):
    from app.services import change_management_service as chg
    from app.services import service_catalog_service as svcat

    svc = _svc_code()
    svcat.upsert_service({"serviceCode": svc, "serviceName": svc, "tier": "P2"})
    change = chg.create_change(REQUESTER, {
        "title": "PLAT11-T01B变更", "changeType": "CODE", "affectedServiceCodes": [svc]})
    chg.assess(int(change["changeId"]), user=REQUESTER)
    with pytest.raises(AppException):
        chg.assess(int(change["changeId"]), user=REQUESTER)


# ── PLAT11-T02：冻结窗口阻断普通变更 ─────────────────────────────────────────
def test_t02_calendar_freeze_window_blocks_schedule(db_mode):
    from app.db.session import get_sessionmaker
    from app.models.academic_calendar import CalendarWindow
    from app.services import change_management_service as chg
    from app.services import service_catalog_service as svcat

    svc = _svc_code()
    svcat.upsert_service({"serviceCode": svc, "serviceName": svc, "tier": "P1"})
    tid = 992010
    svcat.record_tenant_usage(svc, tid)

    now = datetime.utcnow()
    db = get_sessionmaker()()
    try:
        db.add(CalendarWindow(tenant_id=tid, term_id=1, window_type="EXAM", module_code="academicAffairs",
                              start_at=now - timedelta(hours=1), end_at=now + timedelta(hours=1)))
        db.commit()
    finally:
        db.close()

    change = chg.create_change(REQUESTER, {
        "title": "PLAT11-T02变更", "changeType": "CODE", "affectedServiceCodes": [svc]})
    chg.assess(int(change["changeId"]), user=REQUESTER)
    chg.approve(int(change["changeId"]), user=APPROVER, reason="评估通过，同意排期")
    with pytest.raises(AppException) as exc:
        chg.schedule(int(change["changeId"]), user=REQUESTER, scheduled_at=now)
    assert exc.value.http_status == 409
    assert exc.value.details["conflicts"]


def test_t02b_platform_maintenance_window_blocks_schedule(db_mode):
    from app.services import change_management_service as chg
    from app.services import service_catalog_service as svcat

    svc = _svc_code()
    svcat.upsert_service({"serviceCode": svc, "serviceName": svc, "tier": "P1"})
    now = datetime.utcnow()
    chg.upsert_maintenance_window(REQUESTER, {
        "title": "春节代码冻结", "startAt": (now - timedelta(hours=1)).isoformat(),
        "endAt": (now + timedelta(hours=1)).isoformat(), "reason": "假期禁止发布"})

    change = chg.create_change(REQUESTER, {
        "title": "PLAT11-T02B变更", "changeType": "CODE", "affectedServiceCodes": [svc]})
    chg.assess(int(change["changeId"]), user=REQUESTER)
    chg.approve(int(change["changeId"]), user=APPROVER, reason="评估通过，同意排期")
    with pytest.raises(AppException):
        chg.schedule(int(change["changeId"]), user=REQUESTER, scheduled_at=now)


def test_t02d_emergency_change_bypasses_freeze_but_still_needs_separate_approver(db_mode):
    from app.db.session import get_sessionmaker
    from app.models.academic_calendar import CalendarWindow
    from app.services import change_management_service as chg
    from app.services import service_catalog_service as svcat

    svc = _svc_code()
    svcat.upsert_service({"serviceCode": svc, "serviceName": svc, "tier": "P0"})
    tid = 992011
    svcat.record_tenant_usage(svc, tid)
    now = datetime.utcnow()
    db = get_sessionmaker()()
    try:
        db.add(CalendarWindow(tenant_id=tid, term_id=1, window_type="EXAM", module_code="academicAffairs",
                              start_at=now - timedelta(hours=1), end_at=now + timedelta(hours=1)))
        db.commit()
    finally:
        db.close()

    change = chg.create_change(REQUESTER, {
        "title": "紧急安全热修复", "changeType": "HOTFIX", "isEmergency": True,
        "affectedServiceCodes": [svc]})
    cid = int(change["changeId"])
    chg.assess(cid, user=REQUESTER)
    with pytest.raises(AppException):
        chg.approve(cid, user=REQUESTER, reason="尝试自批紧急变更也不允许")  # 紧急变更照样要求发起人≠审批人
    chg.approve(cid, user=APPROVER, reason="紧急安全修复，同意立即排期")
    scheduled = chg.schedule(cid, user=REQUESTER, scheduled_at=now)  # 冻结窗口内也能排期
    assert scheduled["status"] == "SCHEDULED"


def test_t02c_no_conflict_schedule_succeeds(db_mode):
    from app.services import change_management_service as chg
    from app.services import service_catalog_service as svcat

    svc = _svc_code()
    svcat.upsert_service({"serviceCode": svc, "serviceName": svc, "tier": "P2"})
    change = chg.create_change(REQUESTER, {
        "title": "PLAT11-T02C变更", "changeType": "CODE", "affectedServiceCodes": [svc]})
    chg.assess(int(change["changeId"]), user=REQUESTER)
    chg.approve(int(change["changeId"]), user=APPROVER, reason="评估通过，同意排期")
    scheduled = chg.schedule(int(change["changeId"]), user=REQUESTER)
    assert scheduled["status"] == "SCHEDULED"


def test_approver_must_differ_from_requester(db_mode):
    from app.services import change_management_service as chg
    from app.services import service_catalog_service as svcat

    svc = _svc_code()
    svcat.upsert_service({"serviceCode": svc, "serviceName": svc, "tier": "P2"})
    change = chg.create_change(REQUESTER, {
        "title": "自审自批测试", "changeType": "CODE", "affectedServiceCodes": [svc]})
    chg.assess(int(change["changeId"]), user=REQUESTER)
    with pytest.raises(AppException):
        chg.approve(int(change["changeId"]), user=REQUESTER, reason="尝试自己批准自己的变更")


# ── PLAT11-T03：灰度失败停止扩展并回滚 ───────────────────────────────────────
def test_t03_wave_failure_stops_expansion_and_rolls_back(db_mode):
    from app.services import change_management_service as chg
    from app.services import service_catalog_service as svcat

    svc = _svc_code()
    svcat.upsert_service({"serviceCode": svc, "serviceName": svc, "tier": "P2"})
    change = chg.create_change(REQUESTER, {
        "title": "PLAT11-T03变更", "changeType": "CODE", "affectedServiceCodes": [svc]})
    cid = int(change["changeId"])
    chg.assess(cid, user=REQUESTER)
    chg.approve(cid, user=APPROVER, reason="评估通过，同意排期")
    chg.schedule(cid, user=REQUESTER)

    chg.start_wave(cid, wave_no=1, tenant_ids=[992020], user=REQUESTER)
    result = chg.report_wave_result(cid, 1, status="FAILED", error="灰度批次1健康检查失败", user=REQUESTER)
    assert result["changeStatus"] == "ROLLED_BACK"

    with pytest.raises(AppException):
        chg.start_wave(cid, wave_no=2, tenant_ids=[992021], user=REQUESTER)

    detail = chg.get_change(cid)
    assert detail["status"] == "ROLLED_BACK"
    assert len(detail["waves"]) == 1  # 没有第二批


def test_t03b_all_waves_succeed_allows_verify(db_mode):
    from app.services import change_management_service as chg
    from app.services import service_catalog_service as svcat

    svc = _svc_code()
    svcat.upsert_service({"serviceCode": svc, "serviceName": svc, "tier": "P2"})
    change = chg.create_change(REQUESTER, {
        "title": "PLAT11-T03B变更", "changeType": "CODE", "affectedServiceCodes": [svc]})
    cid = int(change["changeId"])
    chg.assess(cid, user=REQUESTER)
    chg.approve(cid, user=APPROVER, reason="评估通过，同意排期")
    chg.schedule(cid, user=REQUESTER)

    chg.start_wave(cid, wave_no=1, tenant_ids=[992030], user=REQUESTER)
    chg.report_wave_result(cid, 1, status="SUCCEEDED", user=REQUESTER)
    chg.start_wave(cid, wave_no=2, tenant_ids=[992031, 992032], user=REQUESTER)
    chg.report_wave_result(cid, 2, status="SUCCEEDED", user=REQUESTER)

    verified = chg.verify(cid, user=REQUESTER)
    assert verified["status"] == "VERIFIED"


def test_verify_rejects_when_a_wave_still_pending(db_mode):
    from app.services import change_management_service as chg
    from app.services import service_catalog_service as svcat

    svc = _svc_code()
    svcat.upsert_service({"serviceCode": svc, "serviceName": svc, "tier": "P2"})
    change = chg.create_change(REQUESTER, {
        "title": "验证前置测试变更", "changeType": "CODE", "affectedServiceCodes": [svc]})
    cid = int(change["changeId"])
    chg.assess(cid, user=REQUESTER)
    chg.approve(cid, user=APPROVER, reason="评估通过，同意排期")
    chg.schedule(cid, user=REQUESTER)
    chg.start_wave(cid, wave_no=1, tenant_ids=[992040], user=REQUESTER)  # 未上报结果，仍是 RUNNING
    with pytest.raises(AppException):
        chg.verify(cid, user=REQUESTER)


# ── PLAT11-T04：不可逆迁移有替代恢复方案 ─────────────────────────────────────
def test_t04_irreversible_migration_requires_rollback_plan(db_mode):
    from app.services import change_management_service as chg
    from app.services import service_catalog_service as svcat

    svc = _svc_code()
    svcat.upsert_service({"serviceCode": svc, "serviceName": svc, "tier": "P1"})
    change = chg.create_change(REQUESTER, {
        "title": "不可逆迁移测试", "changeType": "MIGRATION", "isIrreversible": True,
        "affectedServiceCodes": [svc]})
    cid = int(change["changeId"])
    chg.assess(cid, user=REQUESTER)
    chg.approve(cid, user=APPROVER, reason="评估通过，同意排期")
    with pytest.raises(AppException) as exc:
        chg.schedule(cid, user=REQUESTER)
    assert "替代恢复方案" in exc.value.message


def test_t04b_irreversible_migration_with_rollback_plan_can_schedule(db_mode):
    from app.services import change_management_service as chg
    from app.services import service_catalog_service as svcat

    svc = _svc_code()
    svcat.upsert_service({"serviceCode": svc, "serviceName": svc, "tier": "P1"})
    change = chg.create_change(REQUESTER, {
        "title": "有恢复方案的不可逆迁移", "changeType": "MIGRATION", "isIrreversible": True,
        "rollbackPlan": "无法DOWN迁移；失败时通过恢复变更前备份+重放增量写入日志的方式回退",
        "affectedServiceCodes": [svc]})
    cid = int(change["changeId"])
    chg.assess(cid, user=REQUESTER)
    chg.approve(cid, user=APPROVER, reason="同意排期，已确认恢复方案")
    scheduled = chg.schedule(cid, user=REQUESTER)
    assert scheduled["status"] == "SCHEDULED"


# ── HTTP 端点冒烟 ────────────────────────────────────────────────────────────
def test_http_endpoints(client, db_mode):
    from app.core.security import create_access_token
    from app.services import service_catalog_service as svcat

    svc = _svc_code()
    svcat.upsert_service({"serviceCode": svc, "serviceName": svc, "tier": "P2"})
    token = create_access_token({
        "userId": "u-plat11-owner", "realName": "变更负责人", "userType": "PLATFORM_SUPER_ADMIN",
        "tid": "platform", "tenantId": "1000000000000000000", "tenantName": "平台运营中心",
        "activeContextId": "ctx", "currentRoleCode": "PLATFORM_SUPER_ADMIN", "clientType": "PC"})
    headers = {"Authorization": f"Bearer {token}"}

    r = client.post("/api/v1/platform/changes", headers=headers, json={
        "title": "HTTP冒烟测试变更", "changeType": "CODE", "affectedServiceCodes": [svc]})
    assert r.json()["code"] == 0, r.json()
    change_id = r.json()["data"]["changeId"]

    r = client.get("/api/v1/platform/changes/overview", headers=headers)
    assert r.json()["code"] == 0, r.json()

    r = client.get("/api/v1/platform/changes", headers=headers)
    assert r.json()["code"] == 0, r.json()

    r = client.post(f"/api/v1/platform/changes/{change_id}/assess", headers=headers)
    assert r.json()["code"] == 0, r.json()

    r = client.get(f"/api/v1/platform/changes/{change_id}", headers=headers)
    assert r.json()["code"] == 0, r.json()

    r = client.get("/api/v1/platform/maintenance-windows", headers=headers)
    assert r.json()["code"] == 0, r.json()
