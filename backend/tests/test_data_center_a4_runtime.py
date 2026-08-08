"""A4 / P0-06：数据驾驶舱真实 MySQL 持久化、版本、权限与审计回归。"""
from __future__ import annotations

TID = 1000000000000000001
BASE = "/api/v1/data-center"


def _headers(client, login_name: str = "school_admin01") -> dict:
    data = client.post("/api/v1/auth/mock-login",
                       json={"loginName": login_name, "password": "any"}).json()["data"]
    return {"Authorization": f"Bearer {data['accessToken']}"}


def _create(client, headers, name="A4就业质量月报") -> dict:
    resp = client.post(f"{BASE}/reports", headers=headers, json={
        "name": name,
        "category": "EMPLOYMENT",
        "cycle": "MONTHLY",
        "caliber": "REGISTERED",
        "scopeName": "全校",
        "description": "A4真实专题报表",
    })
    assert resp.status_code == 200, resp.text
    payload = resp.json()
    assert payload["code"] == 0, payload
    return payload["data"]


def test_data_center_context_is_server_truth_and_export_is_fail_closed(client, db_mode):
    headers = _headers(client)
    resp = client.get(f"{BASE}/context", headers=headers)
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["tenantBrandConfig"]["tenantId"] == str(TID)
    assert data["currentRole"]["roleCode"] == "SCHOOL_ADMIN"
    assert data["dataScope"]["scopeType"] == "TENANT_ALL"
    assert data["dataScope"]["scopeName"] == "全校"
    assert data["permissionActions"]["viewDashboard"]["allowed"] is True
    assert data["permissionActions"]["createReport"]["allowed"] is True
    assert data["permissionActions"]["exportReport"]["visible"] is False
    assert data["permissionActions"]["exportReport"]["allowed"] is False
    assert "正式文件任务链" in data["permissionActions"]["exportReport"]["reason"]


def test_report_persists_across_relogin_and_stale_version_conflicts(client, db_mode):
    headers = _headers(client)
    created = _create(client, headers)
    rid = created["id"]
    version = created["version"]

    # 模拟刷新/重新登录后的第二次会话读取：真值必须仍在 MySQL，而不是浏览器数组。
    fresh_headers = _headers(client)
    listed = client.get(f"{BASE}/reports?page=1&pageSize=100", headers=fresh_headers).json()["data"]
    assert rid in {str(x["id"]) for x in listed["items"]}

    updated = client.put(f"{BASE}/reports/{rid}", headers=fresh_headers, json={
        "version": version, "name": "A4就业质量月报（修订）",
    })
    assert updated.status_code == 200, updated.text
    new_version = updated.json()["data"]["version"]
    assert new_version == version + 1

    stale = client.put(f"{BASE}/reports/{rid}", headers=headers, json={
        "version": version, "description": "陈旧页面覆盖",
    })
    assert stale.status_code == 409
    assert stale.json()["bizCode"] == "DATA_VERSION_CONFLICT"


def test_publish_freezes_metrics_with_metadata_and_requires_withdraw_before_edit(client, db_mode):
    headers = _headers(client)
    created = _create(client, headers, "A4发布冻结验证报表")
    rid = created["id"]

    published = client.post(f"{BASE}/reports/{rid}/publish", headers=headers,
                            json={"version": created["version"]})
    assert published.status_code == 200, published.text
    pub = published.json()["data"]
    assert pub["status"] == "PUBLISHED"
    assert pub["publishedVersion"] == 1

    detail = client.get(f"{BASE}/reports/{rid}", headers=headers).json()["data"]
    assert detail["status"] == "PUBLISHED"
    assert detail["publishedVersion"] == 1
    assert isinstance(detail["metrics"], list) and detail["metrics"]
    meta = detail["meta"]
    assert meta["asOf"]
    assert meta["caliber"] == "REGISTERED"
    assert meta["scope"]["scopeType"] == "TENANT_ALL"
    assert isinstance(meta["source"], list) and meta["source"]
    assert isinstance(meta["qualityFlags"], list)

    blocked_edit = client.put(f"{BASE}/reports/{rid}", headers=headers, json={
        "version": detail["version"], "description": "不能直接改已发布版本",
    })
    assert blocked_edit.status_code == 409

    versions = client.get(f"{BASE}/reports/{rid}/versions", headers=headers).json()["data"]["items"]
    assert [x["versionNo"] for x in versions] == [1]
    v1_as_of = versions[0]["asOf"]

    withdrawn = client.post(f"{BASE}/reports/{rid}/withdraw", headers=headers,
                            json={"version": detail["version"]})
    assert withdrawn.status_code == 200
    w = withdrawn.json()["data"]
    assert w["status"] == "WITHDRAWN"

    edited = client.put(f"{BASE}/reports/{rid}", headers=headers, json={
        "version": w["version"], "description": "撤回后修改工作副本",
    })
    assert edited.status_code == 200
    e = edited.json()["data"]

    republished = client.post(f"{BASE}/reports/{rid}/publish", headers=headers,
                              json={"version": e["version"]})
    assert republished.status_code == 200
    assert republished.json()["data"]["publishedVersion"] == 2

    versions2 = client.get(f"{BASE}/reports/{rid}/versions", headers=headers).json()["data"]["items"]
    assert [x["versionNo"] for x in versions2] == [2, 1]
    assert versions2[1]["asOf"] == v1_as_of


def test_report_void_is_traceable_and_audit_is_real(client, db_mode):
    headers = _headers(client)
    created = _create(client, headers, "A4作废审计验证报表")
    rid = created["id"]

    voided = client.post(f"{BASE}/reports/{rid}/void", headers=headers, json={
        "version": created["version"], "reason": "业务口径已废弃，不再使用",
    })
    assert voided.status_code == 200
    row = voided.json()["data"]
    assert row["status"] == "VOIDED"

    detail = client.get(f"{BASE}/reports/{rid}", headers=headers).json()["data"]
    assert detail["voidInfo"]["reason"] == "业务口径已废弃，不再使用"

    audits = client.get(f"{BASE}/audit-logs?targetId={rid}&limit=50", headers=headers).json()["data"]
    actions = {x["action"] for x in audits}
    assert "DATA_CENTER_REPORT_CREATE" in actions
    assert "DATA_CENTER_REPORT_VOID" in actions


def test_non_tenant_all_role_cannot_read_schoolwide_reports(client, db_mode):
    headers = _headers(client, "teacher01")
    context = client.get(f"{BASE}/context", headers=headers)
    assert context.status_code == 200
    ctx = context.json()["data"]
    assert ctx["dataScope"]["scopeType"] != "TENANT_ALL"
    assert ctx["permissionActions"]["viewReports"]["allowed"] is False

    denied = client.get(f"{BASE}/reports?page=1&pageSize=20", headers=headers)
    assert denied.status_code == 403
    assert denied.json()["bizCode"] in {"NO_DATA_SCOPE", "NO_PERMISSION"}


def test_school_bi_dto_exposes_asof_caliber_scope_source_and_quality(client, db_mode):
    headers = _headers(client)
    overview = client.get("/api/v1/stats/overview?caliber=REGISTERED", headers=headers)
    assert overview.status_code == 200
    meta = overview.json()["data"]["meta"]
    assert meta["asOf"]
    assert meta["caliber"] == "REGISTERED"
    assert meta["scope"] == {"scopeType": "TENANT_ALL", "scopeName": "全校"}
    assert isinstance(meta["source"], list) and meta["source"]
    assert isinstance(meta["qualityFlags"], list)
