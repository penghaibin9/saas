"""V3 §5–§6：HomeProjection / Agenda / freshness 合同。

覆盖 V3 深审 P1-11（Home 必须复用 message/todo Authority，不得复制本人可见性）与
P1-12（写后不能只 invalidate，必须 bump projectionVersion）。
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.core.student_lifecycle import STUDENT_LIFECYCLE_STAGES
from app.services import message_center_service as messages
from app.services import mobile_agenda_projection_service as agenda
from app.services import mobile_freshness_service as freshness
from app.services import mobile_student_home_projection as home

REPO_ROOT = Path(__file__).resolve().parents[2]
PAGES_JSON = REPO_ROOT / "miniapp" / "src" / "pages.json"
HOME_SOURCE = REPO_ROOT / "backend" / "app" / "services" / "mobile_student_home_projection.py"
AGENDA_SOURCE = REPO_ROOT / "backend" / "app" / "services" / "mobile_agenda_projection_service.py"


def _miniapp_routes() -> set[str]:
    manifest = json.loads(PAGES_JSON.read_text(encoding="utf-8"))
    routes = {"/" + page["path"] for page in manifest.get("pages", [])}
    for package in manifest.get("subPackages", []):
        root = str(package.get("root", "")).strip("/")
        for page in package.get("pages", []):
            routes.add(f"/{root}/{page['path']}")
    return routes


# ── §5.1 真值缺失必须是 None，不得用 0/100 冒充 ──

def test_stage_progress_is_derived_from_the_canonical_lifecycle_only():
    assert home._stage_progress(None) is None
    assert home._stage_progress("") is None
    assert home._stage_progress("NOT_A_REAL_STAGE") is None
    first = home._stage_progress(STUDENT_LIFECYCLE_STAGES[0])
    last = home._stage_progress(STUDENT_LIFECYCLE_STAGES[-1])
    assert 0 < first < last == 100
    # 序列内单调不减
    values = [home._stage_progress(stage) for stage in STUDENT_LIFECYCLE_STAGES]
    assert values == sorted(values)


def test_credit_rate_is_none_when_the_program_is_unresolved():
    # 培养方案未解析 → requiredCredits 为 None → 必须是 None，让前端显示“—”
    assert home._credit_rate(60.0, None) is None
    assert home._credit_rate(None, 150.0) is None
    assert home._credit_rate(60.0, 0) is None, "应修学分为 0 不能当成 100% 完成"
    assert home._credit_rate(75.0, 150.0) == 50
    assert home._credit_rate(200.0, 150.0) == 100, "超修不得超过 100%"
    assert home._credit_rate(0.0, 150.0) == 0


# ── §4.3 Service Entry Registry ──

def test_every_service_entry_points_at_a_real_page():
    routes = _miniapp_routes()
    for entry in home.SERVICE_ENTRIES:
        assert entry["path"] in routes, f"{entry['key']} 指向不存在的页面 {entry['path']}"


def test_selection_is_not_offered_until_it_reaches_main():
    """§4.3 + S0 GATE-146：选课尚未进入 latest main，不得下发入口。"""
    keys = {entry["key"] for entry in home.SERVICE_ENTRIES}
    assert "SELECTION" not in keys
    paths = {entry["path"] for entry in home.SERVICE_ENTRIES}
    assert "/pages/student/academic-affairs/selection" not in paths


def test_quick_services_are_filtered_by_stage_and_capped():
    freshman = {row["key"] for row in home.quick_services("ADMITTED")}
    assert "ORIENTATION" in freshman
    assert "GRADUATION" not in freshman, "新生阶段不应出现毕业设计入口"

    enrolled = {row["key"] for row in home.quick_services("ENROLLED")}
    assert {"LEAVE", "AID", "FUNDING", "SCHEDULE"} <= enrolled
    assert "ORIENTATION" not in enrolled

    # 无阶段限制的通用服务在任何阶段都在
    for stage in ("ADMITTED", "ENROLLED", "GRADUATED"):
        assert "GENERIC_SERVICE" in {row["key"] for row in home.quick_services(stage)}

    assert len(home.quick_services("ENROLLED")) <= home.QUICK_SERVICE_LIMIT


def test_quick_service_actions_are_entry_only_and_never_claim_object_focus():
    for row in home.quick_services("ENROLLED"):
        action = row["action"]
        assert action["target"]["focusMode"] == "NONE"
        assert action["target"]["routeExact"] is False
        assert action["recordId"] is None


# ── §5.1 首屏条数上限 ──

def test_home_first_screen_limits_match_the_manual():
    limits = home.home_projection_snapshot()["limits"]
    assert limits["today"] == 3
    assert limits["todos"] == 3
    assert limits["notices"] == 3
    assert limits["blockers"] == 2


# ── P1-11：不得复制本人可见性 ──

def test_home_projection_reuses_the_message_visibility_authority():
    source = HOME_SOURCE.read_text(encoding="utf-8")
    # 不得在 Home 里出现任何 receiver 过滤的痕迹
    for forbidden in ("receiver_user_id", "receiver_id", "receiver_context_key", "UnifiedMessage"):
        assert forbidden not in source, f"HomeProjection 复制了消息可见性判定：{forbidden}"
    # 必须走 message_center / workbench_todo 的读接口
    assert "message_svc.list_messages(" in source
    assert "message_svc.count_messages(" in source
    assert "todo_svc.list_todos(" in source
    # 且待办必须按 studentMini 解析 typed route
    assert 'client="studentMini"' in source


def test_message_center_exposes_its_visibility_helper_for_reuse():
    assert callable(messages.visibility_condition)
    # fail-closed：解析不出 uid 时不给可见性条件
    assert messages.visibility_condition({}) is None


def test_home_projection_does_not_reimplement_business_state_machines():
    source = HOME_SOURCE.read_text(encoding="utf-8")
    for forbidden in ("AffairsLeave", "AaScheduleItem", "GraduationTask", "InternshipRecord"):
        assert forbidden not in source, f"HomeProjection 复制了业务状态机：{forbidden}"


# ── §5.4 freshness ──

def test_every_declared_projection_is_bumpable_and_unknown_ones_fail_loudly():
    for projection in freshness.PROJECTIONS:
        # 不应抛 ValueError；Redis 不可用时返回 None 属于正常降级
        freshness.bump({"tenantId": 1, "studentId": 1}, projection)
    with pytest.raises(ValueError):
        freshness.bump({"tenantId": 1, "studentId": 1}, "not_a_projection")


def test_projection_version_is_stable_shaped_and_never_empty():
    version = freshness.projection_version({"tenantId": 1, "studentId": 1})
    assert isinstance(version, str) and version


def test_home_cache_key_carries_the_schema_version():
    from app.services.mobile_student_service import _home_cache_key
    key = _home_cache_key({"tenantId": 7, "studentId": 42})
    assert f"v{home.HOME_VERSION}" in key
    assert "42" in key


def test_write_paths_bump_a_projection_rather_than_only_dropping_the_cache():
    source = (REPO_ROOT / "backend" / "app" / "services" / "mobile_student_service.py").read_text(encoding="utf-8")
    assert "def invalidate_home_cache(user: dict, *projections: str)" in source
    assert "freshness.bump(user or {}, projection)" in source
    # 每个调用点都必须声明自己影响哪个域
    call_sites = [
        line for line in source.splitlines()
        if "invalidate_home_cache(u" in line and not line.lstrip().startswith("def ")
    ]
    assert call_sites, "找不到任何写后失效调用点"
    for line in call_sites:
        assert '"' in line, f"写后失效未声明受影响的投影域：{line.strip()}"


# ── §6 Agenda ──

def test_agenda_window_and_page_size_are_bounded():
    snapshot = agenda.agenda_contract_snapshot()
    assert snapshot["defaultDays"] == 7
    assert snapshot["maxDays"] <= 14
    assert snapshot["pageSizeDefault"] == 20
    assert snapshot["pageSizeMax"] == 50
    assert snapshot["homeTodayLimit"] == 3

    start, end = agenda._window(7)
    assert (end - start).days == 6
    # 越界请求被夹住，而不是放大扫描范围
    start, end = agenda._window(999)
    assert (end - start).days == agenda.MAX_DAYS - 1
    start, end = agenda._window(0)
    assert start == end


def test_agenda_is_a_read_only_projection_with_no_writes():
    source = AGENDA_SOURCE.read_text(encoding="utf-8")
    for forbidden in ("db.add(", "db.commit(", "db.delete(", "sql_update", "insert("):
        assert forbidden not in source, f"Agenda 必须是纯读投影，发现写操作：{forbidden}"


def test_agenda_does_not_reimplement_teaching_week_math():
    source = AGENDA_SOURCE.read_text(encoding="utf-8")
    assert "teaching_week_for_date" in source, "周次必须消费教务校历真值"
    # 不得自己按开学日期算周次
    assert "start_date" not in source
    assert "// 7" not in source and "days // 7" not in source


def test_agenda_queries_are_windowed_not_whole_term():
    source = AGENDA_SOURCE.read_text(encoding="utf-8")
    assert "AaExamCourse.exam_date >= start.isoformat()" in source
    assert "AaExamCourse.exam_date <= end.isoformat()" in source
    assert "UnifiedTodo.due_at >= window_start" in source
    assert "AaScheduleItem.weekday.in_(sorted(weekdays))" in source


def test_agenda_cursor_is_keyset_and_monotonic():
    early = {"startAt": "2026-08-19T09:00:00", "eventId": "academic-course:1:2026-08-19"}
    late = {"startAt": "2026-08-19T14:00:00", "eventId": "academic-course:2:2026-08-19"}
    assert agenda._cursor_of(early) < agenda._cursor_of(late)
    # 同一时刻靠 eventId 稳定区分，翻页不会漏条/重复
    same_time = {"startAt": "2026-08-19T09:00:00", "eventId": "academic-course:2:2026-08-19"}
    assert agenda._cursor_of(early) < agenda._cursor_of(same_time)


def test_agenda_sorts_exams_before_deadlines_before_courses_at_the_same_moment():
    rows = [
        {"startAt": "2026-08-19T09:00:00", "kind": "COURSE", "eventId": "c"},
        {"startAt": "2026-08-19T09:00:00", "kind": "EXAM", "eventId": "e"},
        {"startAt": "2026-08-19T09:00:00", "kind": "DEADLINE", "eventId": "d"},
    ]
    rows.sort(key=agenda._sort_key)
    assert [row["kind"] for row in rows] == ["EXAM", "DEADLINE", "COURSE"]


def test_home_today_failure_does_not_break_the_whole_home(monkeypatch):
    """首页是聚合投影：Agenda 读失败只应缺这一块，不能让整张首页 500。"""
    def boom(*args, **kwargs):
        raise RuntimeError("agenda source down")

    monkeypatch.setattr(agenda, "list_student_agenda", boom)
    assert agenda.today_for_home({"tenantId": 1, "studentId": 1}) == []
