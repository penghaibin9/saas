"""PLAT-09 事件、状态页与统一学校通知（真库）。

对应必测 PLAT09-T01～T03：
一次发布只给受影响租户 / 通知失败重试不重复 / RESOLVED后可转Problem。

受众计算复用 PLAT-08 的 service_catalog_service（同一份依赖图和影响面判定）。
"""
import uuid

import pytest

from app.core.exceptions import AppException


def _svc_code() -> str:
    return f"P09{uuid.uuid4().hex[:8]}".upper()


def _make_tenant_with_admin(tenant_id: int, login_suffix: str) -> int:
    from app.core.security import hash_password
    from app.db.session import get_sessionmaker
    from app.models import Tenant, User

    db = get_sessionmaker()()
    try:
        if db.get(Tenant, tenant_id) is None:
            db.add(Tenant(id=tenant_id, tenant_code=f"p09-{tenant_id}",
                          school_name=f"事件通知测试校{tenant_id}", status="ACTIVE"))
        admin = User(tenant_id=tenant_id, login_name=f"p09admin-{login_suffix}",
                    real_name="校管理员", password_hash=hash_password("Init123456"),
                    user_type="SCHOOL_ADMIN", status="ACTIVE")
        db.add(admin)
        db.commit()
        return admin.id
    finally:
        db.close()


def _owner_headers() -> dict:
    from app.core.security import create_access_token
    token = create_access_token({
        "userId": "u-plat09-owner", "realName": "事件指挥", "userType": "PLATFORM_SUPER_ADMIN",
        "tid": "platform", "tenantId": "1000000000000000000", "tenantName": "平台运营中心",
        "activeContextId": "ctx", "currentRoleCode": "PLATFORM_SUPER_ADMIN", "clientType": "PC"})
    return {"Authorization": f"Bearer {token}"}


# ── PLAT09-T01：一次发布只给受影响租户 ───────────────────────────────────────
def test_t01_publish_only_notifies_affected_tenants(db_mode):
    from app.services import incident_service as inc
    from app.services import service_catalog_service as svcat

    svc_a, svc_b, svc_unrelated = _svc_code(), _svc_code(), _svc_code()
    for code in (svc_a, svc_b, svc_unrelated):
        svcat.upsert_service({"serviceCode": code, "serviceName": code, "tier": "P1"})
    svcat.add_dependency(svc_b, svc_a)  # B 依赖 A：A 故障会间接影响 B 的租户

    t1, t2, t3 = 991001, 991002, 991003
    admin1 = _make_tenant_with_admin(t1, "t01-1")
    admin2 = _make_tenant_with_admin(t2, "t01-2")
    admin3 = _make_tenant_with_admin(t3, "t01-3")
    svcat.record_tenant_usage(svc_a, t1)          # T1 直接用 A
    svcat.record_tenant_usage(svc_b, t2)          # T2 只用 B（间接受 A 影响）
    svcat.record_tenant_usage(svc_unrelated, t3)  # T3 用完全无关的服务

    admin = {"userId": "db-1", "realName": "事件指挥"}
    incident = inc.create_incident(admin, {
        "title": "PLAT09-T01测试事件", "severity": "P1", "affectedServiceCodes": [svc_a]})
    tenant_ids = {t["tenantId"] for t in incident["affectedTenants"]}
    assert tenant_ids == {str(t1), str(t2)}
    assert str(t3) not in tenant_ids

    update = inc.add_update(int(incident["incidentId"]), {"externalMessage": "正在排查中"}, user=admin)
    published = inc.publish_update(int(incident["incidentId"]), int(update["updateId"]), user=admin)
    assert published["notificationResult"][str(t1)]["status"] == "SUCCEEDED"
    assert published["notificationResult"][str(t2)]["status"] == "SUCCEEDED"
    assert str(t3) not in published["notificationResult"]

    from sqlalchemy import select
    from app.db.session import get_sessionmaker
    from app.models.message import UnifiedMessage
    db = get_sessionmaker()()
    try:
        t1_msgs = db.scalars(select(UnifiedMessage).where(
            UnifiedMessage.tenant_id == t1, UnifiedMessage.receiver_user_id == admin1)).all()
        assert len(t1_msgs) == 1
        t3_msgs = db.scalars(select(UnifiedMessage).where(UnifiedMessage.tenant_id == t3)).all()
        assert len(t3_msgs) == 0  # T3 没收到任何本次事件的消息
    finally:
        db.close()
    assert admin2 and admin3  # 变量确实用于建号，避免未使用告警


# ── PLAT09-T02：通知失败重试不重复 ───────────────────────────────────────────
def test_t02_republish_does_not_duplicate_delivered_messages(db_mode):
    from sqlalchemy import func, select

    from app.db.session import get_sessionmaker
    from app.models.message import UnifiedMessage
    from app.services import incident_service as inc
    from app.services import service_catalog_service as svcat

    svc = _svc_code()
    svcat.upsert_service({"serviceCode": svc, "serviceName": svc, "tier": "P0"})
    tid = 991010
    admin_id = _make_tenant_with_admin(tid, "t02")
    svcat.record_tenant_usage(svc, tid)

    admin = {"userId": "db-1", "realName": "事件指挥"}
    incident = inc.create_incident(admin, {
        "title": "PLAT09-T02测试事件", "severity": "P0", "affectedServiceCodes": [svc]})
    update = inc.add_update(int(incident["incidentId"]), {"externalMessage": "首次发布"}, user=admin)

    first = inc.publish_update(int(incident["incidentId"]), int(update["updateId"]), user=admin)
    assert first["notificationResult"][str(tid)]["status"] == "SUCCEEDED"

    second = inc.publish_update(int(incident["incidentId"]), int(update["updateId"]), user=admin)
    assert second["notificationResult"][str(tid)]["status"] == "SUCCEEDED"

    db = get_sessionmaker()()
    try:
        cnt = db.scalar(select(func.count()).select_from(UnifiedMessage).where(
            UnifiedMessage.tenant_id == tid, UnifiedMessage.receiver_user_id == admin_id))
        assert cnt == 1  # 重复发布只产生一条站内消息
    finally:
        db.close()


def test_t02b_retry_only_resends_to_previously_failed_tenants(db_mode, monkeypatch):
    from app.services import incident_service as inc
    from app.services import service_catalog_service as svcat

    svc = _svc_code()
    svcat.upsert_service({"serviceCode": svc, "serviceName": svc, "tier": "P0"})
    tid_ok, tid_no_admin = 991020, 991021
    _make_tenant_with_admin(tid_ok, "t02b")
    from app.db.session import get_sessionmaker
    from app.models import Tenant
    db = get_sessionmaker()()
    try:
        if db.get(Tenant, tid_no_admin) is None:
            db.add(Tenant(id=tid_no_admin, tenant_code=f"p09-{tid_no_admin}",
                          school_name="无管理员测试校", status="ACTIVE"))
            db.commit()
    finally:
        db.close()
    svcat.record_tenant_usage(svc, tid_ok)
    svcat.record_tenant_usage(svc, tid_no_admin)  # 这个租户没有 SCHOOL_ADMIN，第一次必然失败

    admin = {"userId": "db-1", "realName": "事件指挥"}
    incident = inc.create_incident(admin, {
        "title": "PLAT09-T02B测试事件", "severity": "P1", "affectedServiceCodes": [svc]})
    update = inc.add_update(int(incident["incidentId"]), {"externalMessage": "发布"}, user=admin)
    first = inc.publish_update(int(incident["incidentId"]), int(update["updateId"]), user=admin)
    assert first["notificationResult"][str(tid_ok)]["status"] == "SUCCEEDED"
    assert first["notificationResult"][str(tid_no_admin)]["status"] == "FAILED"

    # 补建管理员后重试：只有之前失败的租户会被重新处理，成功的不受影响
    _make_tenant_with_admin(tid_no_admin, "t02b-late")
    retried = inc.publish_update(int(incident["incidentId"]), int(update["updateId"]), user=admin)
    assert retried["notificationResult"][str(tid_no_admin)]["status"] == "SUCCEEDED"
    assert retried["notificationResult"][str(tid_ok)]["status"] == "SUCCEEDED"


# ── PLAT09-T03：RESOLVED后可转Problem ────────────────────────────────────────
def test_t03_only_resolved_incident_can_request_problem_conversion(db_mode):
    from app.services import incident_service as inc
    from app.services import service_catalog_service as svcat

    svc = _svc_code()
    svcat.upsert_service({"serviceCode": svc, "serviceName": svc, "tier": "P2"})
    admin = {"userId": "db-1", "realName": "事件指挥"}
    incident = inc.create_incident(admin, {
        "title": "PLAT09-T03测试事件", "severity": "P2", "affectedServiceCodes": [svc]})
    iid = int(incident["incidentId"])

    with pytest.raises(AppException):
        inc.request_problem_conversion(iid, user=admin)

    inc.transition_status(iid, "ACKNOWLEDGED", user=admin)
    inc.transition_status(iid, "MITIGATING", user=admin)
    inc.transition_status(iid, "MONITORING", user=admin)
    with pytest.raises(AppException):
        inc.request_problem_conversion(iid, user=admin)  # 还没到 RESOLVED

    resolved = inc.transition_status(iid, "RESOLVED", user=admin)
    assert resolved["status"] == "RESOLVED"
    converted = inc.request_problem_conversion(iid, user=admin)
    assert converted["problemConversionRequestedAt"] is not None


def test_t03b_status_cannot_regress(db_mode):
    from app.services import incident_service as inc
    from app.services import service_catalog_service as svcat

    svc = _svc_code()
    svcat.upsert_service({"serviceCode": svc, "serviceName": svc, "tier": "P2"})
    admin = {"userId": "db-1", "realName": "事件指挥"}
    incident = inc.create_incident(admin, {
        "title": "PLAT09-T03B测试事件", "severity": "P2", "affectedServiceCodes": [svc]})
    iid = int(incident["incidentId"])
    inc.transition_status(iid, "ACKNOWLEDGED", user=admin)
    inc.transition_status(iid, "MITIGATING", user=admin)
    with pytest.raises(AppException):
        inc.transition_status(iid, "DETECTED", user=admin)


def test_internal_note_hidden_from_external_view(db_mode):
    from app.services import incident_service as inc
    from app.services import service_catalog_service as svcat

    svc = _svc_code()
    svcat.upsert_service({"serviceCode": svc, "serviceName": svc, "tier": "P2"})
    admin = {"userId": "db-1", "realName": "事件指挥"}
    incident = inc.create_incident(admin, {
        "title": "内部隔离测试事件", "severity": "P2", "affectedServiceCodes": [svc]})
    inc.add_update(int(incident["incidentId"]),
                   {"externalMessage": "对外文案", "internalNote": "内部排查细节：内网IP 10.0.0.5"},
                   user=admin)
    external_view = inc.get_incident(int(incident["incidentId"]), include_internal=False)
    assert "internalNote" not in external_view["updates"][0]
    internal_view = inc.get_incident(int(incident["incidentId"]), include_internal=True)
    assert "10.0.0.5" in internal_view["updates"][0]["internalNote"]


# ── HTTP 端点冒烟 ────────────────────────────────────────────────────────────
def test_http_endpoints(client, db_mode):
    from app.services import service_catalog_service as svcat

    svc = _svc_code()
    svcat.upsert_service({"serviceCode": svc, "serviceName": svc, "tier": "P1"})
    headers = _owner_headers()

    r = client.post("/api/v1/platform/incidents", headers=headers, json={
        "title": "HTTP冒烟测试事件", "severity": "P1", "affectedServiceCodes": [svc]})
    assert r.json()["code"] == 0, r.json()
    incident_id = r.json()["data"]["incidentId"]

    r = client.get("/api/v1/platform/incidents/overview", headers=headers)
    assert r.json()["code"] == 0, r.json()

    r = client.get("/api/v1/platform/incidents", headers=headers)
    assert r.json()["code"] == 0, r.json()

    r = client.get(f"/api/v1/platform/incidents/{incident_id}", headers=headers)
    assert r.json()["code"] == 0, r.json()

    r = client.get(f"/api/v1/platform/incidents/{incident_id}/affected-tenants", headers=headers)
    assert r.json()["code"] == 0, r.json()

    r = client.post(f"/api/v1/platform/incidents/{incident_id}/updates", headers=headers,
                    json={"externalMessage": "HTTP更新"})
    assert r.json()["code"] == 0, r.json()
    update_id = r.json()["data"]["updateId"]

    r = client.post(f"/api/v1/platform/incidents/{incident_id}/updates/{update_id}/publish",
                    headers=headers)
    assert r.json()["code"] == 0, r.json()
