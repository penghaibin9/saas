from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.api.v1 import data_exchange
from app.core import rbac09_permission_bundles as bundles
from app.services import file_access_service as file_access


def _canonical_default_resolver():
    """Load the committed production default policy without inheriting mutable pytest seams."""
    module_path = Path(file_access.__file__).resolve()
    spec = importlib.util.spec_from_file_location("_rbac09_file_access_contract", module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module._default_resolver


def _user(user_id: int = 41) -> dict:
    return {
        "userId": user_id,
        "tenantId": 1000000000000000001,
        "currentRoleCode": "CUSTOM_RBAC09_TEST",
        "loginName": f"rbac09-{user_id}",
    }


def _binding(subject_type: str, subject_id: str | None = None):
    return SimpleNamespace(
        is_deleted=False,
        status="ACTIVE",
        subject_type=subject_type,
        subject_id=subject_id,
        batch_id=None,
    )


def test_rbac09_bundle_catalog_and_legacy_scope_are_frozen():
    catalog = {item["bundleCode"]: item for item in bundles.permission_bundle_catalog()}
    assert set(catalog) == {
        "FILE_GOVERNANCE_VIEW",
        "FILE_QUOTA_ADMIN",
        "FILE_RETENTION_ADMIN",
        "FILE_CLEANUP_EXECUTOR",
        "FILE_LEGAL_HOLD_ADMIN",
        "FILE_SCAN_OPERATOR",
        "DATA_EXCHANGE_VIEW_OWN",
        "DATA_EXCHANGE_VIEW_TENANT",
        "DATA_EXCHANGE_CONFIRM",
        "DATA_EXCHANGE_DOWNLOAD",
        "DATA_EXCHANGE_REVOKE",
        "DATA_EXCHANGE_RETRY",
    }
    assert catalog["FILE_GOVERNANCE_VIEW"]["denies"] == "文件原文预览与下载"
    assert catalog["DATA_EXCHANGE_DOWNLOAD"]["permissions"] == (
        bundles.DATA_EXCHANGE_DOWNLOAD,
    )
    assert bundles.LEGACY_ALIAS_BY_PERMISSION[bundles.DATA_EXCHANGE_VIEW_OWN] == (
        "systemAdmin.user.import",
    )
    assert bundles.DATA_EXCHANGE_VIEW_TENANT not in bundles.LEGACY_ALIAS_BY_PERMISSION


def test_legacy_alias_is_audited_without_widening_tenant_scope(monkeypatch):
    recorded: list[tuple[str, str]] = []

    monkeypatch.setattr(
        bundles,
        "has_permission",
        lambda user, code: code in {"systemAdmin.user.import"},
    )
    monkeypatch.setattr(
        bundles,
        "_record_legacy_alias_use",
        lambda user, legacy, target: recorded.append((legacy, target)),
    )

    allowed, legacy = bundles.permission_decision(_user(), bundles.DATA_EXCHANGE_CONFIRM)
    assert allowed is True
    assert legacy == "systemAdmin.user.import"
    assert recorded == [("systemAdmin.user.import", bundles.DATA_EXCHANGE_CONFIRM)]

    assert bundles.has_permission_compat(_user(), bundles.DATA_EXCHANGE_VIEW_OWN) is True
    assert bundles.has_permission_compat(_user(), bundles.DATA_EXCHANGE_VIEW_TENANT) is False


def test_view_only_permission_does_not_imply_confirm_download_or_revoke(monkeypatch):
    monkeypatch.setattr(
        bundles,
        "has_permission",
        lambda user, code: code == bundles.DATA_EXCHANGE_VIEW_OWN,
    )
    actor = _user()
    assert bundles.has_permission_compat(actor, bundles.DATA_EXCHANGE_VIEW_OWN) is True
    assert bundles.has_permission_compat(actor, bundles.DATA_EXCHANGE_CONFIRM) is False
    assert bundles.has_permission_compat(actor, bundles.DATA_EXCHANGE_DOWNLOAD) is False
    assert bundles.has_permission_compat(actor, bundles.DATA_EXCHANGE_REVOKE) is False
    assert bundles.has_permission_compat(actor, bundles.DATA_EXCHANGE_RETRY) is False


def test_file_governance_permission_never_bypasses_business_content_relation(monkeypatch):
    actor = _user()
    ordinary = SimpleNamespace(
        owner_user_id=88,
        created_by=88,
        biz_type="ATTACHMENT",
        biz_id="student-9001",
    )
    mental = SimpleNamespace(
        owner_user_id=88,
        created_by=88,
        biz_type="MENTAL",
        biz_id="student-9001",
    )
    canonical = _canonical_default_resolver()
    monkeypatch.setattr(
        file_access,
        "has_permission",
        lambda user, code: code == "systemAdmin.file.manage",
    )

    # RBAC-09 governance roles never become file-content administrators.
    assert file_access._is_file_admin(actor) is False
    assert canonical(None, ordinary, [], actor, "meta") is False
    assert canonical(None, mental, [], actor, "meta") is False

    # BUSINESS_OBJECT/TENANT only describe ownership; they are not subject authorization.
    assert canonical(None, ordinary, [_binding("BUSINESS_OBJECT")], actor, "meta") is False
    assert canonical(None, ordinary, [_binding("TENANT")], actor, "meta") is False

    # An explicit binding to the current subject remains a legitimate business relationship.
    assert canonical(
        None,
        ordinary,
        [_binding("USER", str(actor["userId"]))],
        actor,
        "meta",
    ) is True

    # The committed production default policy preserves owner access. Runtime tests may inject a
    # stricter resolver seam independently; that must not rewrite the canonical contract itself.
    owner = _user(88)
    assert canonical(None, ordinary, [], owner, "download") is True


def test_scan_operator_can_retry_but_cannot_download_infected_file(monkeypatch):
    actor = _user()
    infected = SimpleNamespace(
        tenant_id=actor["tenantId"],
        is_deleted=False,
        status="REJECTED",
        scan_status="INFECTED",
        owner_user_id=actor["userId"],
        created_by=actor["userId"],
        biz_type="ATTACHMENT",
        biz_id="student-9001",
    )
    monkeypatch.setattr(file_access, "current_tenant_id", lambda: actor["tenantId"])
    monkeypatch.setattr(
        file_access,
        "has_permission_compat",
        lambda user, code: code in {
            bundles.FILE_SCAN_RETRY,
            bundles.FILE_GOVERNANCE_VIEW,
        },
    )
    monkeypatch.setattr(file_access, "authorize_file_object", lambda *args, **kwargs: False)

    assert file_access._allowed_actions(infected, actor, [], None) == [
        "viewMetadata",
        "retryScan",
        "viewAudit",
    ]

    monkeypatch.undo()
    monkeypatch.setattr(file_access, "current_tenant_id", lambda: actor["tenantId"])
    assert file_access.authorize_file_object(
        infected,
        [],
        actor,
        action="download",
        db=None,
    ) is False


def test_data_exchange_route_permissions_drop_sensitive_audit_escalation():
    assert "systemAdmin.audit.sensitive.view" not in data_exchange.VIEW_PERMISSIONS
    assert "systemAdmin.audit.sensitive.view" not in data_exchange.DOWNLOAD_PERMISSIONS
    assert "systemAdmin.audit.sensitive.view" not in data_exchange.REVOKE_PERMISSIONS
    assert data_exchange.REVOKE_PERMISSIONS == (bundles.DATA_EXCHANGE_REVOKE,)
    assert bundles.DATA_EXCHANGE_CONFIRM in data_exchange.CONFIRM_PERMISSIONS
    assert bundles.DATA_EXCHANGE_RETRY in data_exchange.RETRY_PERMISSIONS


def test_rbac09_source_contract_has_no_governance_content_bypass_and_frontend_is_atomic():
    repo_root = Path(__file__).resolve().parents[2]
    file_access_source = (
        repo_root / "backend/app/services/file_access_service.py"
    ).read_text(encoding="utf-8")
    data_exchange_source = (
        repo_root / "backend/app/api/v1/data_exchange.py"
    ).read_text(encoding="utf-8")
    catalog_source = (
        repo_root / "frontend/src/modules/system/systemManagementCatalog.js"
    ).read_text(encoding="utf-8")

    deny_only_shim = file_access_source.split("def _is_file_admin", 1)[1].split(
        "def _binding_subject_allows", 1
    )[0]
    assert "return False" in deny_only_shim
    assert "has_permission(" not in deny_only_shim
    assert "systemAdmin.audit.sensitive.view" not in data_exchange_source
    assert 'subject_type in {"BUSINESS_OBJECT", "TENANT"}' in file_access_source
    for code in (
        "systemAdmin.dataExchange.viewOwn",
        "systemAdmin.dataExchange.viewTenant",
        "systemAdmin.dataExchange.confirm",
        "systemAdmin.dataExchange.download",
        "systemAdmin.dataExchange.revoke",
        "systemAdmin.dataExchange.retry",
        "systemAdmin.fileGovernance.view",
        "systemAdmin.fileGovernance.quota.manage",
        "systemAdmin.fileGovernance.retention.manage",
        "systemAdmin.fileGovernance.cleanup.execute",
        "systemAdmin.fileGovernance.legalHold.manage",
        "systemAdmin.fileGovernance.scan.retry",
    ):
        assert code in catalog_source
    assert "permissionKey: 'systemAdmin.file.manage'" not in catalog_source
    assert "permissionKey: 'system.user.import', view: 'data-exchange'" not in catalog_source


def test_service_policy_is_exact_tenant_short_lived_and_evidenced():
    context = {
        "subjectType": "SERVICE",
        "serviceId": "file-scan-worker",
        "tenantId": 1001,
        "tokenTtlSeconds": 300,
        "traceId": "trace-rbac09",
    }
    evidence = bundles.authorize_service_job(
        context,
        job_type="FILE_SCAN",
        tenant_id=1001,
        payload_fields={"fileId", "attempt"},
        payload_bytes=1024,
    )
    assert evidence["allowed"] is True
    assert evidence["policyVersion"] == bundles.SERVICE_POLICY_VERSION
    assert evidence["traceId"] == "trace-rbac09"
    assert len(evidence["evidenceHash"]) == 64


def test_service_policy_rejects_human_wildcard_long_token_and_unknown_fields():
    from app.core.exceptions import AppException

    valid = {
        "subjectType": "SERVICE",
        "serviceId": "cleanup-worker",
        "tenantId": 7,
        "tokenTtlSeconds": 600,
    }
    rejected = [
        {**valid, "subjectType": "USER", "userId": 9},
        {**valid, "tenantId": "*"},
        {**valid, "tokenTtlSeconds": 3600},
    ]
    for context in rejected:
        with pytest.raises(AppException) as exc:
            bundles.authorize_service_job(
                context,
                job_type="FILE_RETENTION_CLEANUP",
                tenant_id=7,
                payload_fields={"previewId"},
            )
        assert exc.value.code == "SERVICE_POLICY_DENIED"
    with pytest.raises(AppException):
        bundles.authorize_service_job(
            valid,
            job_type="FILE_RETENTION_CLEANUP",
            tenant_id=7,
            payload_fields={"previewId", "rawSql"},
        )
