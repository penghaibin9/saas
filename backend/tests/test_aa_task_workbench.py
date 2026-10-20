"""教学任务工作台状态机、阻断项与范围行为回归。"""
from types import SimpleNamespace


def _task(status, *, teacher_key="T001"):
    return SimpleNamespace(
        status=status, teacher_key=teacher_key,
        course_name="数据库原理", course_code="DB101",
    )


def test_assigned_waiting_teacher_is_a_batch_blocker():
    from app.modules.academic_affairs.services.academic_affairs_task_service import _summary

    result = _summary([
        _task("PENDING_ASSIGN", teacher_key=""),
        _task("ASSIGNED"), _task("REJECTED_BY_TEACHER"),
        _task("TEACHER_CONFIRMED"),
    ])
    assert result["canAdvance"] is False
    assert result["unassignedCount"] == 1
    assert result["waitingTeacherCount"] == 1
    assert result["teacherRejectedCount"] == 1
    assert {"UNASSIGNED", "WAIT_TEACHER", "TEACHER_REJECTED"} <= {
        item["code"] for item in result["blockers"]
    }


def test_all_teacher_confirmed_tasks_can_advance_to_review():
    from app.modules.academic_affairs.services.academic_affairs_task_service import _summary

    result = _summary([_task("TEACHER_CONFIRMED"), _task("TEACHER_CONFIRMED")])
    assert result["canAdvance"] is True
    assert result["teacherConfirmRate"] == 100.0
    assert result["blockers"] == []


def test_missing_stable_teacher_key_blocks_even_when_status_looks_confirmed():
    from app.modules.academic_affairs.services.academic_affairs_task_service import _summary

    result = _summary([_task("TEACHER_CONFIRMED", teacher_key="")])
    assert result["canAdvance"] is False
    assert result["blockers"][0]["code"] == "TEACHER_KEY_MISSING"


def test_next_action_preserves_college_then_academic_review_chain():
    from app.modules.academic_affairs.services.academic_affairs_task_service import _batch_next_action, _summary

    ready = _summary([_task("TEACHER_CONFIRMED")])
    draft = _batch_next_action(SimpleNamespace(status="DRAFT"), ready)
    college_confirmed = _batch_next_action(SimpleNamespace(status="COLLEGE_CONFIRMED"), ready)
    assert draft["code"] == "COLLEGE_CONFIRM"
    assert "学院" in draft["label"]
    assert college_confirmed["code"] == "ACADEMIC_REVIEW"
    assert "教务终审" in college_confirmed["label"]


def test_empty_task_management_scope_is_fail_closed():
    from app.modules.academic_affairs.services.academic_affairs_task_service import TaskManageScope

    assert TaskManageScope(role="ACADEMIC_TEACHER").blocked is True
    assert TaskManageScope(class_ids={10}, role="COLLEGE_ADMIN").blocked is False
    assert TaskManageScope(all=True, role="ACADEMIC_ADMIN").blocked is False


def test_public_task_service_is_single_explicit_entry():
    from app.modules.academic_affairs.services import academic_affairs_task_service as service

    assert service.get_batch_workbench.__module__.endswith("academic_affairs_task_service")
    assert service.submit_batch.__module__.endswith("academic_affairs_task_service")
    assert service.generate_batch.__module__.endswith("academic_affairs_task_service")
    assert "facade" not in service.submit_batch.__module__


def test_task_queue_pagination_and_summary_use_database_counts(client, db_mode):
    from sqlalchemy import event
    from app.db.session import get_engine, get_sessionmaker
    from app.models import AaTerm, AaTeachingTaskBatch, AaTeachingTask
    tid = 1000000000000000001
    with get_sessionmaker()() as db:
        term = AaTerm(tenant_id=tid, year_code="QUEUE-2026", term_no=1)
        db.add(term); db.flush()
        batch = AaTeachingTaskBatch(tenant_id=tid, term_id=term.id, batch_name="分页验收批次")
        db.add(batch); db.flush()
        rows = [AaTeachingTask(tenant_id=tid, batch_id=batch.id, course_id=1,
                 course_code=f"Q{i:04}", course_name=f"实践100%课程{i}",
                 teacher_key="academic01", status="READY") for i in range(123)]
        rows += [AaTeachingTask(tenant_id=tid, batch_id=batch.id, course_id=1,
                   course_name="其他课程", teacher_key="  ", status="TEACHER_CONFIRMED")]
        db.add_all(rows); db.commit(); bid, term_id = str(batch.id), str(term.id)
    token = client.post("/api/v1/auth/mock-login", json={"loginName":"school_admin01","password":"any"}).json()["data"]["accessToken"]
    headers = {"Authorization": f"Bearer {token}"}
    statements = []
    def capture(_conn, _cursor, statement, _params, _context, _many):
        if statement.lstrip().lower().startswith("select") and "t_aa_teaching_task" in statement:
            statements.append(statement.lower())
    engine = get_engine(); event.listen(engine, "before_cursor_execute", capture)
    try:
        result = client.get(f"/api/v1/academic-affairs/teaching-task-batches/{bid}/tasks", headers=headers,
                            params={"keyword":"100%", "page":3, "pageSize":50})
        assert result.status_code == 200, result.text
        data = result.json()["data"]
        assert data["total"] == 123 and len(data["items"]) == 23
        assert data["items"][0]["courseCode"] == "Q0100"
        workbench = client.get(f"/api/v1/academic-affairs/teaching-task-batches/{bid}/workbench", headers=headers)
        assert workbench.status_code == 200, workbench.text
        summary = workbench.json()["data"]
        assert summary["taskTotal"] == 124 and summary["readyCount"] == 123
        assert summary["blockers"][0]["code"] == "TEACHER_KEY_MISSING"
        batches = client.get("/api/v1/academic-affairs/teaching-task-batches", headers=headers,
                             params={"termId":term_id,"keyword":"分页验收"}).json()["data"]
        assert batches["total"] == 1
        assert batches["items"][0]["taskTotal"] == 124
        assert batches["items"][0]["termLabel"] == "QUEUE-2026 第1学期"
    finally:
        event.remove(engine, "before_cursor_execute", capture)
    detail_queries = [s for s in statements if "t_aa_teaching_task.id" in s and "order by" in s]
    assert detail_queries and all("limit" in s for s in detail_queries)
    assert any("group by" in s for s in statements)
