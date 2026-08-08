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


def _assert_caliber_body_validation(resp) -> None:
    """Pydantic body 枚举错误遵循全仓冻结合同：HTTP 400 + VALIDATION_ERROR。"""
    assert resp.status_code == 400, resp.text
    payload = resp.json()
    assert payload.get("bizCode") == "VALIDATION_ERROR"
    assert payload.get("message") == "参数校验失败"
    details = payload.get("details") or []
    assert any(item.get("field") == "caliber" for item in details), payload


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
    assert data["filterOptions"]["calibers"] == [{"value": "REGISTERED", "label": "在册口径"}]


def test_unsupported_natural_caliber_fails_closed_in_bi_and_reports(client, db_mode):
    headers = _headers(client)
    for path in (
        "/api/v1/stats/overview?caliber=NATURAL",
        "/api/v1/stats/lifecycle?caliber=NATURAL",
        "/api/v1/stats/lifecycle-board?caliber=NATURAL",
    ):
        resp = client.get(path, headers=headers)
        assert resp.status_code == 422, (path, resp.text)
        payload = resp.json()
        assert payload.get("bizCode") == "UNSUPPORTED_CALIBER"
        assert "禁止仅更换标签" in payload.get("message", "")

    create = client.post(f"{BASE}/reports", headers=headers, json={
        "name": "自然口径不得伪装报表",
        "category": "ACADEMIC",
        "cycle": "MONTHLY",
        "caliber": "NATURAL",
        "scopeName": "全校",
    })
    _assert_caliber_body_validation(create)

    row = _create(client, headers, "在册口径更新保护报表")
    update = client.put(f"{BASE}/reports/{row['id']}", headers=headers, json={
        "version": row["version"],
        "caliber": "NATURAL",
    })
    _assert_caliber_body_validation(update)


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


def test_publish_freezes_metrics_and_config_snapshots_across_republish(client, db_mode):
    from sqlalchemy import select
    from app.db.session import get_sessionmaker
    from app.models.data_center import DataCenterReportVersion

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

    # 撤回后工作副本不再冒充发布指标；V1 历史快照仍然存在。
    withdrawn_detail = client.get(f"{BASE}/reports/{rid}", headers=headers).json()["data"]
    assert withdrawn_detail["metrics"] == []
    assert withdrawn_detail["meta"]["asOf"] is None
    assert any(x["code"] == "NOT_PUBLISHED" for x in withdrawn_detail["meta"]["qualityFlags"])

    republished = client.post(f"{BASE}/reports/{rid}/publish", headers=headers,
                              json={"version": e["version"]})
    assert republished.status_code == 200
    assert republished.json()["data"]["publishedVersion"] == 2

    versions2 = client.get(f"{BASE}/reports/{rid}/versions", headers=headers).json()["data"]["items"]
    assert [x["versionNo"] for x in versions2] == [2, 1]
    assert versions2[1]["asOf"] == v1_as_of

    db = get_sessionmaker()()
    try:
        snapshots = db.scalars(select(DataCenterReportVersion).where(
            DataCenterReportVersion.tenant_id == TID,
            DataCenterReportVersion.report_id == int(rid),
        ).order_by(DataCenterReportVersion.version_no)).all()
        assert len(snapshots) == 2
        assert snapshots[0].snapshot_json["description"] == "A4真实专题报表"
        assert snapshots[1].snapshot_json["description"] == "撤回后修改工作副本"
        assert snapshots[0].snapshot_json != snapshots[1].snapshot_json
        assert snapshots[0].metrics_json
        assert snapshots[1].metrics_json
    finally:
        db.close()


def test_report_void_is_traceable_and_audit_is_tenant_isolated(client, db_mode):
    from datetime import datetime
    from app.db.session import get_sessionmaker
    from app.models.audit import SecurityAuditLog

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

    # 同 resourceId 的其它租户审计必须被 tenant 条件隔离。
    db = get_sessionmaker()()
    try:
        db.add(SecurityAuditLog(
            tenant_id=TID + 999,
            operator_id=999,
            operator_name="跨租户伪记录",
            current_role="SCHOOL_ADMIN",
            data_scope="TENANT_ALL",
            action="DATA_CENTER_REPORT_VOID",
            resource="data_center_report",
            resource_id=str(rid),
            result="SUCCESS",
            detail_json={"reason": "不应泄露"},
            created_at=datetime.utcnow(),
        ))
        db.commit()
    finally:
        db.close()

    audits = client.get(f"{BASE}/audit-logs?targetId={rid}&limit=50", headers=headers).json()["data"]
    actions = {x["action"] for x in audits}
    assert "DATA_CENTER_REPORT_CREATE" in actions
    assert "DATA_CENTER_REPORT_VOID" in actions
    assert all(x["userName"] != "跨租户伪记录" for x in audits)


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

    lifecycle = client.get("/api/v1/stats/lifecycle-board?caliber=REGISTERED", headers=headers)
    assert lifecycle.status_code == 200
    lifecycle_meta = lifecycle.json()["data"]["meta"]
    assert any(x["code"] == "TREND_SERIES_NOT_CONFIGURED" for x in lifecycle_meta["qualityFlags"])

    risk = client.get("/api/v1/stats/risk-board", headers=headers)
    assert risk.status_code == 200
    risk_meta = risk.json()["data"]["meta"]
    risk_codes = {x["code"] for x in risk_meta["qualityFlags"]}
    assert {"RISK_STATUS_CALIBER_PARTIAL", "RISK_TREND_NOT_CONFIGURED", "INTERNSHIP_RISK_NOT_UNIFIED"} <= risk_codes
