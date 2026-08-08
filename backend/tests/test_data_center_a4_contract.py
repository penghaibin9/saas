"""A4 / P0-06 数据驾驶舱服务端化静态合同。"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_formal_facade_has_no_browser_report_or_context_truth():
    src = _read("frontend/src/modules/dataCenter/api/dataCenter.api.js")
    forbidden = (
        "mockRuntime",
        "roleProfiles",
        "reportList",
        "reportDetailMap",
        "auditLogs.push",
        "reportSeq",
        "auditSeq",
        "taskId: `EXP-",
    )
    for token in forbidden:
        assert token not in src, f"数据驾驶舱正式 facade 禁止浏览器真值：{token}"
    assert "real('/data-center/context')" in src
    assert "real('/data-center/reports'" in src
    assert "real('/data-center/audit-logs'" in src
    assert "已禁止本地假任务" in src
    assert "已禁止本地假成功" in src


def test_report_truth_has_work_copy_and_append_only_published_version():
    model = _read("backend/app/models/data_center.py")
    service = _read("backend/app/services/data_center_service.py")
    migration = _read("backend/alembic/versions/20260808_data_center_reports.py")
    db_base = _read("backend/app/db/base.py")

    assert "class DataCenterReport(" in model
    assert "class DataCenterReportVersion(" in model
    assert 'UniqueConstraint("tenant_id", "report_id", "version_no"' in model
    assert "snapshot_json" in model and "metrics_json" in model and "quality_flags_json" in model
    assert 'revision = "20260808_dc_report"' in migration
    assert 'down_revision = "20260808_aa_gpa_policy"' in migration
    assert "data_center as _data_center" in db_base
    assert "DataCenterReportVersion(" in service
    assert "published_version_no" in service
    assert "with_for_update()" in service
    assert "DATA_VERSION_CONFLICT" in service


def test_report_actions_are_server_permissioned_versioned_and_audited():
    service = _read("backend/app/services/data_center_service.py")
    for code in (
        "dataCenter.report.view",
        "dataCenter.report.manage",
        "dataCenter.report.publish",
        "dataCenter.report.void",
    ):
        assert code in service
    for action in (
        "DATA_CENTER_REPORT_CREATE",
        "DATA_CENTER_REPORT_UPDATE",
        "DATA_CENTER_REPORT_PUBLISH",
        "DATA_CENTER_REPORT_WITHDRAW",
        "DATA_CENTER_REPORT_VOID",
    ):
        assert action in service
    assert "record_critical(" in service and "db=db" in service
    assert "已发布报表需先撤回后才能编辑" in service
    assert "仅已发布报表可以撤回" in service


def test_context_and_school_bi_are_server_scoped_fail_closed():
    service = _read("backend/app/services/data_center_service.py")
    stats_api = _read("backend/app/api/v1/stats.py")
    router = _read("backend/app/api/v1/router.py")

    assert "build_affairs_context" in service
    assert 'ctx.scope_type != "TENANT_ALL"' in service
    assert "数据驾驶舱校级指标仅对全校数据范围角色开放" in service
    assert "TenantBrandConfig" in service
    assert "data_center_router" in router
    for key in ("asOf", "caliber", "scope", "source", "qualityFlags"):
        assert f'"{key}"' in stats_api
    assert "不以 0 或演示" in stats_api


def test_facade_preserves_viewed_version_instead_of_fetching_latest_before_write():
    src = _read("frontend/src/modules/dataCenter/api/dataCenter.api.js")
    assert "const viewedReportVersions = new Map()" in src
    assert "function rememberReport" in src
    assert "function viewedVersion" in src
    assert "缺少报表版本，请刷新" in src
    # 不允许 update/void/publish 前额外拉详情并拿最新 version，避免绕过 stale-write 409。
    update_block = src[src.index("async updateReport"):src.index("async publishReport")]
    assert "getReportDetail" not in update_block


def test_no_fake_export_or_reminder_backend_contract_is_advertised():
    service = _read("backend/app/services/data_center_service.py")
    facade = _read("frontend/src/modules/dataCenter/api/dataCenter.api.js")
    assert '"exportOverview": _permission_action' in service
    assert '"batchRemind": _permission_action' in service
    assert "hidden=True" in service
    assert "exportData()" in facade and "已禁止本地假任务" in facade
    assert "sendRiskReminder()" in facade and "已禁止本地假成功" in facade
