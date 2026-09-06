"""PLAT-D-C0 production-characterization locks.

These tests intentionally exercise or inspect the current authorities without
registering a PLAT-D route, model, migration, or shared UI integration.  They
form the safety net for the private C1-C4 implementation.
"""
from __future__ import annotations

import inspect
import re
from pathlib import Path
from types import SimpleNamespace

from app.services import approval_runtime_service, workbench_todo_service
from app.services.todo_route_registry import resolve_todo_route, route_contract_snapshot


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_student_todo_audience_is_assignee_user_id_only():
    source = inspect.getsource(workbench_todo_service._visibility_cond)

    student_branch = source.split("if _is_student(user):", 1)[1].split(
        "# 教职工", 1
    )[0]
    assert "UnifiedTodo.assignee_id == uid" in student_branch
    assert "UnifiedTodo.student_id" not in student_branch


def test_unknown_todo_completion_and_capability_fail_closed():
    assert workbench_todo_service._completion_mode("UNREGISTERED_PLAT_D_TYPE") == "DOMAIN_COMMAND"

    row = SimpleNamespace(
        id=9,
        todo_type="UNREGISTERED_PLAT_D_TYPE",
        title="unknown",
        source_biz_type="UNKNOWN",
        source_biz_id=99,
        source_module="unknown",
        status="PENDING",
        due_at=None,
        created_at=None,
        version=1,
    )
    dto = workbench_todo_service._todo_dict(row, client="pc")
    assert dto["allowedActions"] == []
    assert dto["routeName"] is None
    assert dto["routeExact"] is False


def test_todo_route_authority_covers_all_four_clients_and_is_honest():
    snapshot = route_contract_snapshot()
    assert {"pcExact", "pcList", "studentPc", "studentMini", "teacherMini"} <= set(snapshot)

    for client in ("pc", "studentPc", "studentMini", "teacherMini"):
        assert resolve_todo_route("UNKNOWN_PLAT_D_TYPE", 1, client=client) is None

    exact = resolve_todo_route("RISK_HANDLE", 77, client="pc")
    assert exact and exact["focusMode"] == "DETAIL" and exact["exact"] is True

    inexact = resolve_todo_route("ACAD_WARNING_HANDLE", 77, client="studentPc")
    assert inexact and inexact["focusMode"] == "NONE" and inexact["exact"] is False


def test_base_portal_has_exactly_two_real_header_search_inputs_and_current_concat_seam():
    source = (REPO_ROOT / "frontend/src/layouts/BasePortalLayout.vue").read_text(encoding="utf-8")
    template = source.split("<script", 1)[0]
    search_block = template.split('<div class="bpl-search">', 1)[1].split(
        '<div class="bpl-top-r">', 1
    )[0]

    inputs = re.findall(r"<input\b", search_block)
    assert len(inputs) == 2
    assert 'ref="stuInput"' in search_block
    assert 'ref="fnInput"' in search_block
    assert 'placeholder="搜学生（姓名 / 学号）"' in search_block
    assert 'placeholder="搜功能、帮助文档、流程图"' in search_block

    # C1 builds the private typed target first.  This shared seam remains an
    # explicit integration blocker until the Header owner is released.
    assert "const p = '/admin/student/' + s.id" in source


def test_domain_allowed_actions_remain_server_derived_and_unknown_is_not_opened():
    known = SimpleNamespace(
        id=10,
        todo_type="LEAVE_APPROVAL",
        title="leave",
        source_biz_type="LEAVE",
        source_biz_id=100,
        source_module="student-affairs",
        status="PENDING",
        due_at=None,
        created_at=None,
        version=2,
    )
    dto = workbench_todo_service._todo_dict(known, client="pc")
    assert dto["allowedActions"] == ["OPEN"]
    assert "COMPLETE" not in dto["allowedActions"]


def test_approval_transfer_runtime_is_task_scoped_and_aggregates_workload():
    transfer_source = inspect.getsource(approval_runtime_service.transfer)
    targets_source = inspect.getsource(approval_runtime_service.transfer_targets)

    assert 'expected_status="PENDING"' in transfer_source
    assert '"status": "TRANSFERRED"' in transfer_source
    assert 'status="PENDING"' in transfer_source
    assert "deadline_at=task.deadline_at" in transfer_source

    # Current main installs approval_production_guard over the legacy function.
    # Characterize the effective runtime Authority, not the stale fallback body.
    assert "task_id" in inspect.signature(approval_runtime_service.transfer_targets).parameters
    assert "_load_policy" in targets_source
    assert "_assert_transfer_policy" in targets_source
    assert "assert_transfer_target_scope" in targets_source
    assert ".group_by(WorkflowTask.assignee_id)" in targets_source
    assert "for row in users:" not in targets_source
