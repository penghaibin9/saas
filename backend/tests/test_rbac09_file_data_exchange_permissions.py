from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from app.api.v1 import data_exchange
from app.core import rbac09_permission_bundles as bundles
from app.services import file_access_service as file_access


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

    # 兼容旧账号导入权限时只能保留本人任务和既有动作，不能升级成全校任务查看。
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
    monkeypatch.setattr(
        file_access,
        "has_permission",
        lambda user, code: code == "systemAdmin.file.manage",
    )

    # 历史导入符号只用于平滑升级，始终拒绝内容管理员旁路。
    assert file_access._is_file_admin(actor) is False
    assert file_access._default_resolver(None, ordinary, [], actor, "meta") is False
    assert file_access._default_resolver(None, mental, [], actor, "meta") is False

    # BUSINESS_OBJECT/TENANT 只描述文件归属，不描述当前访问者，不能作为内容授权。
    assert file_access._default_resolver(
        None,
        ordinary,
        [_binding("BUSINESS_OBJECT")],
        actor,
        "meta",
    ) is False
    assert file_access._default_resolver(
        None,
        ordinary,
        [_binding("TENANT")],
        actor,
        "meta",
    ) is False

    # 明确指向当前主体的绑定仍然是合法关系。
    assert file_access._default_resolver(
        None,
        ordinary,
        [_binding("USER", str(actor["userId"]))],
        actor,
        "meta",
    ) is True

    owner = _user(88)
    assert file_access._default_resolver(None, ordinary, [], owner, "download") is True


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

    # 即使是文件所有者和扫描操作员，感染/拒绝文件也不能通过下载安全门。
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

    assert "systemAdmin.file.manage" not in file_access_source
    assert "return False" in file_access_source.split("def _is_file_admin", 1)[1].split("def _binding_subject_allows", 1)[0]
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
