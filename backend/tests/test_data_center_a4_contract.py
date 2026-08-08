"""A4 / P0-06 数据驾驶舱服务端化静态合同。"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_formal_facade_has_no_browser_report_context_or_kpi_truth():
    src = _read("frontend/src/modules/dataCenter/api/dataCenter.api.js")
    forbidden = (
        "@/mocks/dataCenter",
        "shouldTryReal",
        "overviewMetrics",
        "lifecycleFunnel",
        "riskStats",
        "collegeRankings",
        "majorRankings",
        "classRankings",
        "drilldownStudents",
        "mockRuntime",
        "roleProfiles",
        "reportList",
        "reportDetailMap",
        "auditLogs.push",
        "reportSeq",
        "auditSeq",
        "taskId: `EXP-",
        "Math.round(funnel.totalCount * ratio)",
    )
    for token in forbidden:
        assert token not in src, f"数据驾驶舱正式 facade 禁止浏览器真值：{token}"

    for path in (
        "/data-center/context",
        "/stats/overview",
        "/stats/lifecycle-board",
        "/stats/rankings",
        "/stats/risk-board",
        "/stats/drilldown",
        "/data-center/reports",
        "/data-center/audit-logs",
    ):
        assert path in src

    assert "已禁止浏览器估算" in src
    assert "已禁止返回全校学生冒充命中名单" in src
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


def test_only_real_registered_caliber_is_advertised_and_accepted():
    api = _read("backend/app/api/v1/data_center.py")
    stats_api = _read("backend/app/api/v1/stats.py")
    dashboard = _read("frontend/src/views/admin/dataCenter/DataCenterDashboardView.vue")

    assert 'SupportedCaliber = Literal["REGISTERED"]' in api
    assert 'item.get("value") == "REGISTERED"' in api
    assert "def _require_supported_caliber" in stats_api
    assert 'value != "REGISTERED"' in stats_api
    assert "UNSUPPORTED_CALIBER" in stats_api
    assert "NATURAL 自然口径尚未形成跨域真实查询合同" in stats_api
    assert "caliber: 'REGISTERED'" in dashboard


def test_lifecycle_page_does_not_expose_unsupported_filters_or_fake_rule_drilldown():
    page = _read("frontend/src/views/admin/dataCenter/DataCenterLifecycleView.vue")
    for token in (
        "AdvancedFilter",
        "collegeId",
        "majorId",
        "classId",
        "timeRange",
        "getDrilldownStudents",
        "exportData",
        "AppConfirmDialog",
    ):
        assert token not in page, f"生命周期页不得暴露未服务端化能力：{token}"
    for token in ("meta.source", "meta.qualityFlags", "meta.scope", "meta.asOf"):
        assert token in page
    assert "已禁止浏览器估算" in _read("frontend/src/modules/dataCenter/api/dataCenter.api.js")
    assert "本页不返回“全校学生”冒充命中名单" in page


def test_risk_page_distinguishes_unconfigured_from_zero_and_has_no_fake_actions():
    page = _read("frontend/src/views/admin/dataCenter/DataCenterRiskView.vue")
    for token in ("getDrilldownStudents", "sendRiskReminder", "exportData", "AppConfirmDialog"):
        assert token not in page, f"风险页不得暴露未形成正式合同的能力：{token}"
    assert "空白代表未配置，不代表 0" in page
    assert "系统不会用 0 或演示曲线填充" in page
    assert "meta.qualityFlags" in page and "meta.source" in page and "meta.asOf" in page


def test_data_center_layout_context_failure_is_explicit_and_fail_closed():
    page = _read("frontend/src/views/admin/dataCenter/AdminDataCenterLayout.vue")
    assert "ctxError" in page
    assert "<ErrorState" in page
    assert "@retry=\"loadContext\"" in page
    assert "this.ctx = null" in page
    assert "默认角色" in page or "绝不构造" in page


def test_dashboard_and_ranking_surface_data_contract_without_fake_export():
    dashboard = _read("frontend/src/views/admin/dataCenter/DataCenterDashboardView.vue")
    ranking = _read("frontend/src/views/admin/dataCenter/DataCenterRankingView.vue")
    for page in (dashboard, ranking):
        assert "exportData" not in page
        assert "演示态" not in page
        assert "meta.qualityFlags" in page
        assert "meta.source" in page
        assert "meta.scope" in page
        assert "meta.asOf" in page
    assert "RANKING_PROXY_CALIBER" not in ranking  # 由服务端 meta 返回，页面不得硬编码口径结果
    assert "ranking.note" in ranking
    assert "metricKey: 'ALL'" in ranking


def test_facade_preserves_viewed_version_instead_of_fetching_latest_before_write():
    src = _read("frontend/src/modules/dataCenter/api/dataCenter.api.js")
    assert "const viewedReportVersions = new Map()" in src
    assert "function rememberReport" in src
    assert "function viewedVersion" in src
    assert "缺少报表版本，请刷新" in src
    # 不允许 update/void/publish 前额外拉详情并拿最新 version，避免绕过 stale-write 409。
    update_block = src[src.index("async updateReport"):src.index("async publishReport")]
    assert "getReportDetail" not in update_block


def test_unimplemented_export_reminder_and_unsupported_drilldowns_fail_closed():
    service = _read("backend/app/services/data_center_service.py")
    facade = _read("frontend/src/modules/dataCenter/api/dataCenter.api.js")
    assert '"exportOverview": _permission_action' in service
    assert '"batchRemind": _permission_action' in service
    assert "hidden=True" in service
    assert "exportData()" in facade and "已禁止本地假任务" in facade
    assert "sendRiskReminder()" in facade and "已禁止本地假成功" in facade
    assert "metricKey !== 'ALL'" in facade
    assert "riskLevel" in facade and "已禁止浏览器筛选冒充服务端结果" in facade
