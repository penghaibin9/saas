"""PLAT-08 服务目录、依赖与租户影响地图（真库）。

对应必测 PLAT08-T01～T03：
依赖循环拒绝 / 故障计算直接-间接受影响租户 / 无runbook-owner的P0服务阻断发布。

平台级数据不经过 _tid()，不需要 tenant_ctx 夹具；直接打真实服务函数。
"""
import pytest

from app.core.exceptions import AppException


def _owner_headers() -> dict:
    from app.core.security import create_access_token
    token = create_access_token({
        "userId": "u-platform-owner", "realName": "平台老板", "userType": "PLATFORM_SUPER_ADMIN",
        "tid": "platform", "tenantId": "1000000000000000000", "tenantName": "平台运营中心",
        "activeContextId": "ctx_platform_owner", "currentRoleCode": "PLATFORM_SUPER_ADMIN",
        "clientType": "PC",
    })
    return {"Authorization": f"Bearer {token}"}


def _mk_services(*codes: str, tier: str = "P2") -> None:
    from app.services import service_catalog_service as svcat
    for code in codes:
        svcat.upsert_service({"serviceCode": code, "serviceName": code, "tier": tier})


# ── PLAT08-T01：依赖循环拒绝 ─────────────────────────────────────────────────
def test_t01_dependency_cycle_rejected(db_mode):
    from app.services import service_catalog_service as svcat

    _mk_services("T01_A", "T01_B", "T01_C")
    svcat.add_dependency("T01_A", "T01_B")   # A 依赖 B
    svcat.add_dependency("T01_B", "T01_C")   # B 依赖 C
    # 若再让 C 依赖 A：A->B->C->A 成环
    with pytest.raises(AppException) as exc:
        svcat.add_dependency("T01_C", "T01_A")
    assert exc.value.http_status == 409


def test_t01b_self_dependency_rejected(db_mode):
    from app.services import service_catalog_service as svcat

    _mk_services("T01B_X")
    with pytest.raises(AppException):
        svcat.add_dependency("T01B_X", "T01B_X")


def test_t01c_non_cyclic_dependency_succeeds(db_mode):
    from app.services import service_catalog_service as svcat

    _mk_services("T01C_A", "T01C_B", "T01C_C")
    svcat.add_dependency("T01C_A", "T01C_B")
    out = svcat.add_dependency("T01C_A", "T01C_C")  # 同一上游多个依赖，不成环
    assert out["serviceCode"] == "T01C_A" and out["dependsOnServiceCode"] == "T01C_C"


# ── PLAT08-T02：故障计算直接/间接受影响租户 ──────────────────────────────────
def test_t02_impact_computes_direct_and_indirect_tenants(db_mode):
    from app.services import service_catalog_service as svcat

    _mk_services("T02_X", "T02_Y", "T02_Z")
    svcat.add_dependency("T02_Y", "T02_X")   # Y 依赖 X
    svcat.add_dependency("T02_Z", "T02_Y")   # Z 依赖 Y（间接依赖 X）

    svcat.record_tenant_usage("T02_X", 90001)   # 直接用 X 的租户
    svcat.record_tenant_usage("T02_Y", 90002)   # 只用 Y（间接受 X 影响）
    svcat.record_tenant_usage("T02_Z", 90003)   # 只用 Z（间接受 X 影响，跨两跳）
    svcat.record_tenant_usage("T02_X", 90002)   # 90002 同时也直接用 X

    impact = svcat.compute_service_impact("T02_X")
    assert impact["directTenants"] == ["90001", "90002"]
    assert impact["indirectTenants"] == ["90003"]  # 90002 已在 direct，不重复出现在 indirect
    assert set(impact["affectedServices"]) == {"T02_Y", "T02_Z"}
    assert impact["totalAffectedTenants"] == 3


def test_t02b_impact_unrelated_service_has_no_indirect_tenants(db_mode):
    from app.services import service_catalog_service as svcat

    _mk_services("T02B_ISOLATED")
    svcat.record_tenant_usage("T02B_ISOLATED", 90004)
    impact = svcat.compute_service_impact("T02B_ISOLATED")
    assert impact["directTenants"] == ["90004"]
    assert impact["indirectTenants"] == []
    assert impact["affectedServices"] == []


def test_t02c_impact_unknown_service_raises_404(db_mode):
    from app.services import service_catalog_service as svcat

    with pytest.raises(AppException) as exc:
        svcat.compute_service_impact("DOES_NOT_EXIST")
    assert exc.value.http_status == 404


# ── PLAT08-T03：无runbook/owner的P0服务阻断发布 ──────────────────────────────
def test_t03_p0_service_without_owner_or_runbook_blocks_release(db_mode):
    from app.services import service_catalog_service as svcat

    svcat.upsert_service({"serviceCode": "T03_P0", "serviceName": "P0服务", "tier": "P0"})
    with pytest.raises(AppException) as exc:
        svcat.assert_release_allowed("T03_P0")
    assert exc.value.details.get("hasOwner") is False
    assert exc.value.details.get("hasRunbook") is False

    svcat.upsert_service({"serviceCode": "T03_P0", "serviceName": "P0服务", "tier": "P0",
                          "ownerName": "运维小王", "runbookUrl": "https://runbook/t03"})
    svcat.assert_release_allowed("T03_P0")  # 不抛异常即通过


def test_t03b_non_p0_service_never_blocked(db_mode):
    from app.services import service_catalog_service as svcat

    svcat.upsert_service({"serviceCode": "T03B_P2", "serviceName": "非核心服务", "tier": "P2"})
    svcat.assert_release_allowed("T03B_P2")  # P2 无门禁


# ── 只读治理面 + 幂等 bootstrap ───────────────────────────────────────────────
def test_bootstrap_is_idempotent(db_mode):
    from app.services import service_catalog_service as svcat

    first = svcat.bootstrap_default_services()
    assert first == len(svcat.DEFAULT_SERVICES)
    second = svcat.bootstrap_default_services()
    assert second == 0
    codes = {s["serviceCode"] for s in svcat.list_services()}
    assert {"API_GATEWAY", "MYSQL", "REDIS"}.issubset(codes)


def test_governance_overview_flags_no_owner_and_single_point(db_mode):
    from app.services import service_catalog_service as svcat

    _mk_services("T04_UP", tier="P0")
    _mk_services("T04_DOWN", tier="P1")
    svcat.add_dependency("T04_DOWN", "T04_UP")
    overview = svcat.governance_overview()
    assert "T04_UP" in overview["noOwnerServices"]
    assert "T04_UP" in overview["singlePointServices"]  # 有下游依赖它
    assert overview["recentIncidents"] == []


# ── HTTP 端点冒烟 ────────────────────────────────────────────────────────────
def test_http_endpoints(client, db_mode):
    headers = _owner_headers()

    r = client.post("/api/v1/platform/services/bootstrap", headers=headers)
    assert r.json()["code"] == 0, r.json()

    r = client.get("/api/v1/platform/services/overview", headers=headers)
    assert r.json()["code"] == 0, r.json()

    r = client.get("/api/v1/platform/services", headers=headers)
    assert r.json()["code"] == 0, r.json()

    r = client.post("/api/v1/platform/services", headers=headers, json={
        "serviceCode": "HTTP_SVC_A", "serviceName": "HTTP服务A", "tier": "P1"})
    assert r.json()["code"] == 0, r.json()
    r = client.post("/api/v1/platform/services", headers=headers, json={
        "serviceCode": "HTTP_SVC_B", "serviceName": "HTTP服务B", "tier": "P1"})
    assert r.json()["code"] == 0, r.json()

    r = client.post("/api/v1/platform/service-dependencies", headers=headers, json={
        "serviceCode": "HTTP_SVC_A", "dependsOnServiceCode": "HTTP_SVC_B"})
    assert r.json()["code"] == 0, r.json()
    dep_id = r.json()["data"]["id"]

    r = client.get("/api/v1/platform/service-dependencies", headers=headers,
                   params={"serviceCode": "HTTP_SVC_A"})
    assert r.json()["code"] == 0 and r.json()["data"]["total"] == 1, r.json()

    r = client.get("/api/v1/platform/service-impact", headers=headers,
                   params={"serviceCode": "HTTP_SVC_B"})
    assert r.json()["code"] == 0, r.json()

    r = client.delete(f"/api/v1/platform/service-dependencies/{dep_id}", headers=headers)
    assert r.json()["code"] == 0, r.json()


def test_http_school_identity_forbidden(client, db_mode):
    from app.core.security import create_access_token
    token = create_access_token({
        "userId": "u-school-admin", "realName": "学校管理员", "userType": "TEACHER",
        "tid": "demo", "tenantId": "1000000000000000001",
        "activeContextId": "ctx", "currentRoleCode": "SCHOOL_ADMIN", "clientType": "PC",
    })
    headers = {"Authorization": f"Bearer {token}"}
    r = client.get("/api/v1/platform/services", headers=headers)
    assert r.status_code == 403
