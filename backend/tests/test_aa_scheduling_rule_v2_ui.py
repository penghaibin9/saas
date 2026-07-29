"""V2-03 排课规则管理PC静态合同。"""
from pathlib import Path


def _view_source() -> str:
    return (
        Path(__file__).resolve().parents[2]
        / "frontend" / "src" / "modules" / "academicAffairs" / "views" / "AaSchedulingConsoleView.vue"
    ).read_text(encoding="utf-8")


def test_rule_editor_is_inline_business_form_not_drawer_or_json_console():
    source = _view_source()

    assert "AppDrawer" not in source
    assert "JSON.stringify(row.ruleValue)" not in source
    assert "JSON.parse(this.ruleForm" not in source
    assert "规则值(JSON)" not in source
    assert "规则键" not in source
    assert "新增排课规则" in source
    assert "业务参数" in source
    assert "生效范围" in source
    assert "学校未配置时采用的安全默认值" in source


def test_rule_editor_has_controls_for_every_supported_business_shape():
    source = _view_source()

    for control in (
        "WEEK_RANGE",
        "WEEKDAY_MULTI",
        "SLOT_MULTI",
        "FORBIDDEN_GRID",
        "INTEGER",
        "BOOLEAN",
    ):
        assert control in source
    assert "选择允许自动排课的星期" in source
    assert "选择允许自动排课的节次" in source
    assert "勾选全校统一禁排时段" in source


def test_rule_page_fails_closed_when_context_catalog_or_term_state_is_unknown():
    source = _view_source()

    assert "catalogError" in source
    assert "termError" in source
    assert "this.termInfo" in source
    assert "!this.catalogError" in source
    assert "!this.termError" in source
    assert "学期状态加载失败，已禁止修改排课规则" in source
    assert "当前角色为只读查看" in source
    assert "该学期已经归档" in source


def test_rule_page_keeps_existing_auto_schedule_and_conflict_workflows():
    source = _view_source()

    assert "试排预览" in source
    assert "一键自动排课" in source
    assert "清除自动排课结果" in source
    assert "教师不可排时间" in source
    assert "冲突报告" in source
    assert "HARD 物理冲突" in source
