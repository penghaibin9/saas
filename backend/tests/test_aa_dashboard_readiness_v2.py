"""V2 PageId AA-DASHBOARD-01：教务看板阶段 readiness 合同。"""
from datetime import date
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[2]


def _term(*, status="PUBLISHED", start=date(2026, 9, 1), end=date(2027, 1, 20), exam_week=18):
    return SimpleNamespace(
        id=1,
        year_code="2026-2027",
        term_no=1,
        term_name="2026-2027学年第一学期",
        status=status,
        start_date=start,
        end_date=end,
        teaching_weeks=20,
        exam_week_start=exam_week,
        is_current=True,
    )


def test_stage_resolution_covers_full_term_lifecycle():
    from app.modules.academic_affairs.services import academic_affairs_dashboard_readiness_service as service

    assert service._stage(None, date(2026, 8, 1))[0] == "NO_TERM"
    assert service._stage(_term(status="DRAFT"), date(2026, 8, 1))[0] == "TERM_SETUP"
    assert service._stage(_term(), date(2026, 8, 20))[0] == "PRE_TERM"
    assert service._stage(_term(), date(2026, 10, 1))[0] == "TEACHING"
    assert service._stage(_term(), date(2026, 12, 29))[0] == "EXAM"
    assert service._stage(_term(), date(2027, 2, 1))[0] == "TERM_CLOSE"
    assert service._stage(_term(status="ARCHIVED"), date(2027, 2, 1))[0] == "ARCHIVED"


def test_readiness_item_has_owner_deadline_and_real_routes():
    from app.modules.academic_affairs.services import academic_affairs_dashboard_readiness_service as service

    item = service._item(
        key="TEST",
        severity="BLOCKER",
        title="测试阻断",
        summary="需要处理",
        rule_code="DASHBOARD_TEST",
        count=2,
        route="/admin/academic-affairs/terms",
        owner_role="教务处",
        deadline="2026-08-01",
    )

    assert item["ownerRole"] == "教务处"
    assert item["deadlineLabel"] == "2026-08-01"
    assert item["route"] == "/admin/academic-affairs/terms"
    assert item["assignRoute"].startswith("/admin/approval?source=academic-readiness")
    assert "DASHBOARD_TEST" in item["assignRoute"]


def test_exam_deadline_is_computed_forward_from_term_start():
    from app.modules.academic_affairs.services import academic_affairs_dashboard_readiness_final_service as service

    deadline = service._exam_deadline({
        "term": {"startDate": "2026-09-01", "examWeekStart": 18}
    })

    assert deadline == "2026-12-29"


def test_archived_term_never_keeps_old_blocker_counts(monkeypatch):
    from app.modules.academic_affairs.services import academic_affairs_dashboard_readiness_final_service as service

    monkeypatch.setattr(service, "_mark_current", lambda data: data)
    data = service._recalculate(
        {
            "term": {"termId": None, "termLabel": "历史学期", "isCurrent": False},
            "stage": "ARCHIVED",
        },
        [{
            "key": "OLD",
            "severity": "BLOCKER",
            "count": 9,
            "deadline": None,
        }],
        scope_type="TENANT_ALL",
        scope_note="测试",
    )

    assert data["status"] == "NORMAL"
    assert data["blockerCount"] == 0
    assert data["riskCount"] == 0
    assert data["items"] == []


def test_non_school_dashboard_aggregates_are_fail_closed():
    source = (
        ROOT / "backend/app/modules/academic_affairs/services/academic_affairs_dashboard_scope_facade.py"
    ).read_text(encoding="utf-8")
    scope = (
        ROOT / "backend/app/modules/academic_affairs/services/academic_affairs_dashboard_readiness_final_service.py"
    ).read_text(encoding="utf-8")

    assert 'if scope_type == "TENANT_ALL"' in source
    assert '"scopeRestricted": True' in source
    assert "学校级汇总已 fail-closed" in source
    assert "_COLLEGE_SAFE_KEYS" in scope
    assert "全校考务、成绩与预警汇总不向学院范围放大" in scope


def test_dashboard_page_matches_v2_first_screen_and_removes_construction_labels():
    source = (
        ROOT / "frontend/src/modules/academicAffairs/views/AaDashboardView.vue"
    ).read_text(encoding="utf-8")

    for text in (
        "当前阶段",
        "阻断项",
        "风险项",
        "当前最需要处理",
        "我的教务待办",
        "今日教学运行",
        "即将到期",
        "分派责任人",
        "去处理",
        "导出准备清单",
        "成绩、考务和预警运行明细",
    ):
        assert text in source
    assert "readiness.topItems" in source
    assert "item.ownerRole" in source
    assert "item.deadlineLabel" in source
    assert "item.assignRoute" in source
    assert "LIVE=已上线" not in source
    assert "建设中=后续波次交付" not in source
    assert "moduleCards" not in source


def test_readiness_api_and_xlsx_export_are_real_endpoints():
    router = (
        ROOT / "backend/app/modules/academic_affairs/routers/dashboard_readiness_router.py"
    ).read_text(encoding="utf-8")
    bundle = (
        ROOT / "backend/app/modules/academic_affairs/routers/academic_affairs_bundle.py"
    ).read_text(encoding="utf-8")
    frontend_api = (
        ROOT / "frontend/src/modules/academicAffairs/api/academic-affairs-dashboard-readiness.api.js"
    ).read_text(encoding="utf-8")

    assert '@router.get("/readiness"' in router
    assert '@router.get("/readiness/export"' in router
    assert "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" in router
    assert '"dashboard_readiness_router"' in bundle
    assert "/academic-affairs/dashboard/readiness" in frontend_api
    assert "requestBlob" in frontend_api


def test_dashboard_public_entry_is_side_effect_free():
    source = (
        ROOT / "backend/app/modules/academic_affairs/services/academic_affairs_dashboard_scope_facade.py"
    ).read_text(encoding="utf-8")
    package = (
        ROOT / "backend/app/modules/academic_affairs/services/__init__.py"
    ).read_text(encoding="utf-8")

    assert 'data.pop("moduleCards", None)' in source
    assert "_base.dashboard =" not in source
    assert "_base.dashboard_reminders =" not in source
    assert "academic_affairs_dashboard_scope_facade as academic_affairs_service" in package


def test_readiness_runtime_compatibility_has_no_model_monkey_patch():
    final = (
        ROOT / "backend/app/modules/academic_affairs/services/academic_affairs_dashboard_readiness_final_service.py"
    ).read_text(encoding="utf-8")
    guard = (
        ROOT / "backend/app/modules/academic_affairs/services/academic_affairs_dashboard_readiness_runtime_guard.py"
    ).read_text(encoding="utf-8")

    assert "AaScheduleChange.term_id" not in final
    assert "_operation_risks(db, term)" in final
    assert "_base._operation_risks =" not in guard
    assert "_canonical._operation_risks" in guard
