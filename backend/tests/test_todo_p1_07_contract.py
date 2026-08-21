from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

from app.services.todo_route_registry import resolve_todo_route, route_contract_snapshot
from app.services.workbench_todo_service import _todo_dict


ROOT = Path(__file__).resolve().parents[2]


def test_pc_exact_todo_routes_exist_in_generated_route_index():
    index = json.loads((ROOT / "shared/generated/route-index.json").read_text(encoding="utf-8"))
    patterns = set(index.get("patterns") or [])
    exact = route_contract_snapshot()["pcExact"]
    assert exact
    for spec in exact.values():
        pattern = spec["pathTemplate"].replace("{recordId}", ":recordId")
        # generated index uses domain-specific parameter names; compare normalized static shape.
        normalized = pattern.rsplit("/:", 1)[0]
        assert any(p.startswith(normalized + "/:") for p in patterns), spec
        assert spec["routeName"].startswith("todo-route:")
        assert not spec["routeName"].startswith("studentAffairs.")


def test_typed_todo_dto_contains_record_route_actions_and_version():
    row = SimpleNamespace(
        id=101,
        todo_type="RISK_HANDLE",
        title="处置风险",
        source_biz_type="RISK",
        source_biz_id=88,
        source_module="student-affairs",
        due_at=None,
        created_at=datetime(2026, 8, 8, 8, 0, 0),
        status="PENDING",
        version=7,
    )
    dto = _todo_dict(row, client="pc")
    assert dto["recordId"] == "88"
    assert dto["routeName"] == "todo-route:student-affairs-risk-detail"
    assert dto["routePath"] == "/admin/student-affairs/risk/88"
    assert dto["routeParams"] == {"recordId": "88"}
    assert dto["query"] == {}
    assert dto["routeExact"] is True
    assert dto["allowedActions"] == ["OPEN", "COMPLETE"]
    assert dto["version"] == 7


def test_unimplemented_detail_route_is_explicitly_non_exact_but_keeps_record_id():
    route = resolve_todo_route("LEAVE_APPROVAL", 55, client="pc")
    assert route == {
        "routeName": "todo-route:student-affairs-leave-queue",
        "routeParams": {"recordId": "55"},
        "query": {"status": "PENDING", "recordId": "55"},
        "path": "/admin/student-affairs/leave",
        # V3 §4.4：PC 队列页没有对象聚焦能力，focusMode 显式为 NONE，exact 仍是 False。
        "focusMode": "NONE",
        "exact": False,
    }


def test_unknown_todo_type_does_not_invent_a_route():
    assert resolve_todo_route("UNKNOWN_NEW_TODO", 1, client="pc") is None
    assert resolve_todo_route("UNKNOWN_NEW_TODO", 1, client="studentMini") is None
    assert resolve_todo_route("UNKNOWN_NEW_TODO", 1, client="studentPc") is None


# ---------------------------------------------------------------------------
# S3：Student PC typed todo target（V3 施工手册 Lane S / S3，PR #183 合并后补齐）
# ---------------------------------------------------------------------------

def test_student_pc_todo_route_targets_real_campus_service_tab():
    """LEAVE_APPROVAL 之前在 studentPc client 下恒为 None（fail-closed）；
    现在必须落到 AffairsFourEndView.vue 真实存在的 leave 分 tab。"""
    route = resolve_todo_route("LEAVE_APPROVAL", 55, client="studentPc")
    assert route == {
        "routeName": "todo-route:student-pc-leave",
        "routeParams": {"recordId": "55"},
        "query": {"tab": "leave", "recordId": "55"},
        "path": "/campus-service",
        # AffairsFourEndView.vue 目前不读 recordId 定位具体那条，诚实标 NONE/False，
        # 不能因为 Mini 端同类型已经是 LIST_FOCUS 就跟着假装 PC 端也精确。
        "focusMode": "NONE",
        "exact": False,
    }


def test_student_pc_todo_route_covers_affairs_and_academic_and_internship():
    """S3 覆盖的业务类型必须都落在 Student PC 真实存在的路由上，不多不少。"""
    cases = {
        "AID_APPROVAL": ("/campus-service", "aid"),
        "FUNDING_APPROVAL": ("/campus-service", "funding"),
        "DISCIPLINE_APPROVAL": ("/campus-service", "discipline"),
        "ACAD_WARNING_HANDLE": ("/academic", "warning"),
    }
    for todo_type, (path, tab) in cases.items():
        route = resolve_todo_route(todo_type, 1, client="studentPc")
        assert route["path"] == path, todo_type
        assert route["query"]["tab"] == tab, todo_type
        assert route["focusMode"] == "NONE"
        assert route["exact"] is False

    for todo_type in ("INTERN_WEEKLY_REVIEW", "INTERN_LEAVE_APPROVAL", "INTERN_EXCEPTION_HANDLE"):
        route = resolve_todo_route(todo_type, 1, client="studentPc")
        assert route["path"] == "/internship", todo_type
        assert "tab" not in route["query"]


def test_student_pc_todo_route_does_not_leak_staff_only_todo_types():
    """RISK_HANDLE/AA_GRADE_ENTRY/GD_* 等是教职工处理的待办，不是学生本人的待办；
    studentPc 分支不得替它们发明一个学生端目标。"""
    for todo_type in ("RISK_HANDLE", "AA_GRADE_ENTRY", "GD_PROPOSAL_REVIEW",
                      "GD_FINAL_REVIEW", "AA_SCHEDULE_CHANGE_APPROVAL",
                      "EMPLOYMENT_FOLLOWUP", "DORM_TRANSFER"):
        assert resolve_todo_route(todo_type, 1, client="studentPc") is None, todo_type


def test_student_pc_typed_todo_dto_carries_real_target_via_todo_dict():
    row = SimpleNamespace(
        id=201,
        todo_type="LEAVE_APPROVAL",
        title="请假审批",
        source_biz_type="LEAVE",
        source_biz_id=9001,
        source_module="student-affairs",
        due_at=None,
        created_at=datetime(2026, 8, 8, 8, 0, 0),
        status="PENDING",
        version=1,
    )
    dto = _todo_dict(row, client="studentPc")
    assert dto["routePath"] == "/campus-service"
    assert dto["query"] == {"tab": "leave", "recordId": "9001"}
    assert dto["routeExact"] is False
    assert dto["focusMode"] == "NONE"
    assert dto["allowedActions"] == ["OPEN", "COMPLETE"]


def test_student_pc_route_contract_snapshot_registered():
    snapshot = route_contract_snapshot()
    assert "studentPc" in snapshot
    assert snapshot["studentPc"]["LEAVE_APPROVAL"]["path"] == "/campus-service"
    assert snapshot["studentPc"]["LEAVE_APPROVAL"]["query"] == {"tab": "leave"}


def test_action_projection_build_todo_action_consumes_registry_focus_result():
    """S3 顺带修复：build_todo_action() 之前把 focusMode 恒定写死成 NONE、routeExact
    重新用写死的 NONE 计算一遍——即便 todo_route_registry 已经算出真实结论也会被
    悄悄压回 NONE/False。现在必须原样消费 todo 字典里 registry 已经算出的
    focusMode/routeExact，不能再自己重新判断一遍。"""
    from app.student_portal.services.action_projection_service import build_todo_action

    todo = {
        "todoId": "301",
        "todoType": "LEAVE_APPROVAL",
        "title": "请假审批",
        "bizType": "LEAVE",
        "recordId": "9001",
        "routeName": "todo-route:student-pc-leave",
        "routePath": "/campus-service",
        "query": {"tab": "leave", "recordId": "9001"},
        "routeExact": False,
        "focusMode": "NONE",
        "allowedActions": ["OPEN", "COMPLETE"],
        "version": 1,
    }
    action = build_todo_action(todo)
    assert action["disabledReason"] is None
    assert action["target"]["path"] == "/campus-service"
    assert action["target"]["query"] == {"tab": "leave", "recordId": "9001"}
    assert action["target"]["routeExact"] is False
    assert action["focusMode"] == "NONE"
    assert action["allowedActions"] == ["OPEN"]


def test_action_projection_build_todo_action_still_fails_closed_without_route():
    """未登记的 todoType（routePath 仍为 None）必须继续 fail-closed，不能因为
    上面那个修复就意外开始猜路由。"""
    from app.student_portal.services.action_projection_service import build_todo_action

    todo = {
        "todoId": "302", "todoType": "AA_GRADE_ENTRY", "title": "录入成绩",
        "bizType": "AA_GRADE_ENTRY", "recordId": "9002",
        "routeName": None, "routePath": None, "query": {},
        "routeExact": False, "focusMode": "NONE",
        "allowedActions": [], "version": 1,
    }
    action = build_todo_action(todo)
    assert action["target"] is None
    assert action["disabledReason"]
