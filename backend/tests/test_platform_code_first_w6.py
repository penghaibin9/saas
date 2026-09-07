from __future__ import annotations


def _healthy_business():
    return {
        "tenantTotal": 9, "tenantTrial": 1, "tenantActive": 8, "tenantExpired": 0, "tenantDisabled": 0,
        "studentTotal": 100, "userTotal": 20, "todayLogin": 3, "weekLogin": 10,
        "todayImport": 0, "todayExport": 0, "todayUpload": 0, "todayApproval": 0,
        "storageUsedMb": 999999, "expiringTenants": [], "abnormalTenants": [], "recentAudits": [],
        "systemHealth": "UP", "dbStatus": "OK", "fileDirStatus": "OK", "todoPending": 0, "approvalPending": 0,
    }


def _patch_healthy_sources(monkeypatch):
    monkeypatch.setattr("app.services.platform_service.overview", _healthy_business)
    monkeypatch.setattr("app.services.foundation_operations_service.foundation_overview", lambda: {
        "fileFoundation": {"totalBytes": 2 * 1024 * 1024},
        "coverage": {"status": "OK", "totalTenantCount": 1, "successTenantCount": 1, "failedTenantCount": 0},
    })
    monkeypatch.setattr("app.services.service_catalog_service.governance_overview", lambda: {"degradedCount": 0, "noOwnerCount": 0})
    monkeypatch.setattr("app.services.incident_service.governance_overview", lambda: {"p0p1ActiveCount": 0, "unacknowledgedCount": 0})
    monkeypatch.setattr("app.services.change_management_service.governance_overview", lambda: {"pendingApprovalCount": 0, "freezeConflictCount": 0})
    monkeypatch.setattr("app.services.customer_health_service.governance_overview", lambda: {"atRiskCount": 0})
    monkeypatch.setattr("app.services.platform_overview_service._tenant_lifecycle_projection", lambda: {
        "tenantTotal": 1,
        "counts": {"trial": 0, "active": 1, "expired": 0, "disabled": 0},
        "tenantUnresolved": 0,
        "unresolvedTenants": [],
    })


def test_w6_storage_uses_file_foundation_not_local_upload_scalar(monkeypatch):
    _patch_healthy_sources(monkeypatch)
    from app.services.platform_overview_service import overview

    board = overview()
    assert board["storageUsedBytes"] == 2 * 1024 * 1024
    assert board["storageUsedMb"] == 2.0
    assert board["storageUsedMb"] != 999999
    assert board["fileDirStatus"] == "LEGACY_NOT_AUTHORITATIVE"
    assert board["dataQuality"]["complete"] is True


def test_w6_failed_source_is_unknown_not_zero(monkeypatch):
    _patch_healthy_sources(monkeypatch)

    def fail_incidents():
        raise RuntimeError("incident backend unavailable")

    monkeypatch.setattr("app.services.incident_service.governance_overview", fail_incidents)
    from app.services.platform_overview_service import overview

    board = overview()
    assert board["dataQuality"]["sources"]["incidents"]["status"] == "UNKNOWN"
    assert board["incidents"] == {}
    assert board["dataQuality"]["complete"] is False
    assert board["systemHealth"] == "DEGRADED"
    assert any(item["sourceCard"] == "DATA_QUALITY" and "incidents" in item["text"] for item in board["operationalRisks"])


def test_w6_unresolved_tenant_is_not_counted_as_disabled(monkeypatch):
    _patch_healthy_sources(monkeypatch)
    monkeypatch.setattr("app.services.platform_overview_service._tenant_lifecycle_projection", lambda: {
        "tenantTotal": 2,
        "counts": {"trial": 0, "active": 1, "expired": 0, "disabled": 0},
        "tenantUnresolved": 1,
        "unresolvedTenants": [{"tenantId": "2", "tenantName": "未知学校", "error": "bad state"}],
    })
    from app.services.platform_overview_service import overview

    board = overview()
    assert board["tenantTotal"] == 2
    assert board["tenantActive"] == 1
    assert board["tenantDisabled"] == 0
    assert board["tenantUnresolved"] == 1
    assert board["dataQuality"]["sources"]["tenantLifecycle"]["status"] == "DEGRADED"


def test_w6_partial_file_coverage_is_degraded(monkeypatch):
    _patch_healthy_sources(monkeypatch)
    monkeypatch.setattr("app.services.foundation_operations_service.foundation_overview", lambda: {
        "fileFoundation": {"totalBytes": 1024},
        "coverage": {"status": "DEGRADED", "totalTenantCount": 2, "successTenantCount": 1, "failedTenantCount": 1},
    })
    from app.services.platform_overview_service import overview

    board = overview()
    quality = board["dataQuality"]["sources"]["fileFoundation"]
    assert quality["status"] == "DEGRADED"
    assert quality["coverage"]["failedTenantCount"] == 1
    assert board["dataQuality"]["complete"] is False
