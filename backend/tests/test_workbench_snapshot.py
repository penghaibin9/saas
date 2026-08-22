from __future__ import annotations

from datetime import datetime, timedelta

from app.core.security import create_access_token

TENANT_ID = 1000000000000000001


def _headers(user_type: str, role: str) -> dict:
    token = create_access_token({
        "userId": "u-teacher" if user_type != "STUDENT" else "u-student",
        "realName": "王老师" if user_type != "STUDENT" else "学生甲",
        "userType": user_type,
        "tenantId": str(TENANT_ID),
        "tid": "demo",
        "activeContextId": "ctx",
        "currentRoleCode": role,
        "clientType": "PC",
    })
    return {"Authorization": f"Bearer {token}"}


def test_admin_workbench_snapshot_contract(client, db_mode):
    response = client.get(
        "/api/v1/admin/workbench-snapshot?pageSize=8",
        headers=_headers("TEACHER", "COUNSELOR"),
    )
    payload = response.json()
    assert payload["code"] == 0, payload
    data = payload["data"]
    assert set(data) == {"summary", "count", "todos", "messages"}
    assert data["summary"]["role"] == "COUNSELOR"
    assert data["todos"]["page"] == 1
    assert data["todos"]["pageSize"] == 8
    assert isinstance(data["todos"]["items"], list)
    assert isinstance(data["count"]["byType"], dict)
    assert data["messages"]["unread"] >= 0


def test_student_cannot_access_admin_workbench_snapshot(client, db_mode):
    payload = client.get(
        "/api/v1/admin/workbench-snapshot",
        headers=_headers("STUDENT", "STUDENT"),
    ).json()
    assert payload["code"] == 403001
    assert payload["bizCode"] == "NO_PERMISSION"


def test_unified_todo_completed_at_stamped_on_status_transition(db_mode):
    """TP-W02：completed_at 只在 status 真正变为 DONE 时写；改备注等无关编辑（会刷新
    CommonMixin 的 updated_at）不得动它；DONE 被重开也要清空，不留一个撒谎的旧时间戳。"""
    from app.db.session import get_sessionmaker
    from app.models import UnifiedTodo

    db = get_sessionmaker()()
    todo = UnifiedTodo(
        tenant_id=TENANT_ID, source_module="student-affairs", source_biz_type="LEAVE",
        source_biz_id=920001, todo_type="LEAVE_APPROVAL", assignee_id=1,
        title="请假待审", status="PENDING")
    db.add(todo)
    db.commit()
    assert todo.completed_at is None

    todo.status = "DONE"
    db.commit()
    stamped_at = todo.completed_at
    assert stamped_at is not None

    # Editing an unrelated field bumps updated_at (CommonMixin onupdate) but must leave the
    # completion fact alone.
    todo.remark = "补充说明"
    db.commit()
    assert todo.completed_at == stamped_at

    # Reopening clears the stale completion fact rather than leaving yesterday's timestamp on
    # a todo that is PENDING again.
    todo.status = "PENDING"
    db.commit()
    assert todo.completed_at is None
    db.close()


def test_workbench_summary_matches_approval_authority(client, db_mode):
    """TP-W03：pending/overdue/nearDeadline/doneToday 全部下钻到 Approval 页
    （/admin/approval/todos、/admin/approval/done），数字必须和 Approval 自己的 /approvals/summary
    完全一致——不能继续用 UnifiedTodo 聚合（会把非审批待办也计进去，点开卡片却对不上）。"""
    from app.db.session import get_sessionmaker
    from app.models import UnifiedTodo, WorkflowInstance, WorkflowTask
    from app.services.message_identity import resolve_message_user_id

    now = datetime.utcnow()
    todo_assignee_id = resolve_message_user_id({"userId": "u-teacher"})
    db = get_sessionmaker()()

    def _task(node, status, deadline=None, acted_at=None):
        inst = WorkflowInstance(
            tenant_id=TENANT_ID, workflow_code="LEAVE_WF", source_module="student-affairs",
            source_biz_type="LEAVE", source_biz_id=930000 + node, applicant_id=1,
            status="RUNNING" if status == "PENDING" else "APPROVED", current_node="NODE_1")
        db.add(inst)
        db.flush()
        db.add(WorkflowTask(
            tenant_id=TENANT_ID, instance_id=inst.id, node_code="NODE_1",
            assignee_id=todo_assignee_id, status=status, deadline_at=deadline, acted_at=acted_at))

    # One overdue pending, one near-deadline pending, one done-today, one normal pending.
    _task(1, "PENDING", deadline=now - timedelta(hours=2))
    _task(2, "PENDING", deadline=now + timedelta(hours=1))
    _task(3, "APPROVED", acted_at=now)
    _task(4, "PENDING")
    # A non-approval UnifiedTodo (mirrors AA_GRADE_ENTRY: no WorkflowTask backing it at all).
    # It must NOT inflate the workbench summary that Approval-authority cues read from.
    db.add(UnifiedTodo(
        tenant_id=TENANT_ID, source_module="academic-affairs", source_biz_type="AA_GRADE_TASK",
        source_biz_id=1, todo_type="AA_GRADE_ENTRY", assignee_id=todo_assignee_id,
        title="待录成绩", status="PENDING"))
    db.commit()
    db.close()

    approval_summary = client.get(
        "/api/v1/approvals/summary", headers=_headers("TEACHER", "COUNSELOR"),
    ).json()["data"]

    payload = client.get(
        "/api/v1/admin/workbench-snapshot?pageSize=8",
        headers=_headers("TEACHER", "COUNSELOR"),
    ).json()
    assert payload["code"] == 0, payload
    summary = payload["data"]["summary"]
    assert summary["pending"] == approval_summary["total"] == 3, (summary, approval_summary)
    assert summary["overdue"] == approval_summary["overdue"] == 1
    assert summary["nearDeadline"] == approval_summary["nearDeadline"] == 1
    assert summary["doneToday"] == approval_summary["doneToday"] == 1
    # The grade-entry todo is real and must still show up in the UnifiedTodo-authority count
    # that the inline "最近待办" widget and its own typeCue use — just not in this summary.
    assert payload["data"]["count"]["byType"].get("AA_GRADE_ENTRY") == 1
