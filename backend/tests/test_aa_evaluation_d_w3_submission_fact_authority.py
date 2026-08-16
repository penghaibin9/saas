"""D-W3 MySQL contract: student answer facts are the live submission-count authority."""
from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

import pytest
from sqlalchemy import func, select

TID = 1000000000000000001


@pytest.mark.usefixtures("db_mode")
def test_same_student_race_writes_one_answer_and_close_reconciles_task_projection():
    """Member-row serialization + READ COMMITTED must reject the second identical student submit."""
    from app.core.context import set_current_user, set_tenant
    from app.db.session import get_sessionmaker
    from app.models import AaEvaluationRecord, AaEvaluationResult, AaEvaluationTask
    from app.modules.academic_affairs.services import academic_affairs_evaluation_public_service as service
    from scripts import academic_d_evaluation_concurrency_probe as probe

    seeded = probe._seed_formal_teaching_context(student_count=2, task_count=1)
    batch_id, eval_task_ids = probe._new_open_eval_tasks(
        seeded["termId"],
        seeded["teachingTaskIds"],
        "focused-duplicate-authority",
    )
    task_id = int(eval_task_ids[0])
    student_id = int(seeded["studentIds"][0])

    barrier = threading.Barrier(2)
    with ThreadPoolExecutor(max_workers=2, thread_name_prefix="dw3-focused-duplicate") as pool:
        futures = [pool.submit(probe._submit, task_id, student_id, barrier) for _ in range(2)]
        results = [future.result(timeout=20) for future in as_completed(futures)]

    successes = [row for row in results if row["ok"]]
    failures = [row for row in results if not row["ok"]]
    assert len(successes) == 1, results
    assert len(failures) == 1, results
    assert "已提交" in failures[0]["error"]

    set_tenant({"tenantId": str(TID), "tenantCode": "dw3-focused-duplicate"})
    verify = get_sessionmaker()()
    try:
        task = verify.get(AaEvaluationTask, task_id)
        record_count = int(verify.scalar(
            select(func.count()).select_from(AaEvaluationRecord).where(
                AaEvaluationRecord.tenant_id == TID,
                AaEvaluationRecord.task_id == task_id,
                AaEvaluationRecord.evaluator_type == "STUDENT",
                AaEvaluationRecord.is_deleted.is_(False),
            )
        ) or 0)
        assert record_count == 1
        assert task is not None
        # OPEN-window writes do not serialize on this legacy projection row anymore.
        assert int(task.submitted_count or 0) == 0
    finally:
        verify.close()
        set_tenant(None)

    admin = probe._admin_user()
    set_tenant({"tenantId": str(TID), "tenantCode": "dw3-focused-duplicate"})
    set_current_user(admin)
    try:
        closed = service.close_and_score(admin, batch_id)
        assert closed["status"] == "RESULT_READY"
    finally:
        set_current_user(None)
        set_tenant(None)

    set_tenant({"tenantId": str(TID), "tenantCode": "dw3-focused-duplicate"})
    verify = get_sessionmaker()()
    try:
        task = verify.get(AaEvaluationTask, task_id)
        result = verify.scalar(select(AaEvaluationResult).where(
            AaEvaluationResult.tenant_id == TID,
            AaEvaluationResult.batch_id == int(batch_id),
            AaEvaluationResult.is_deleted.is_(False),
        ))
        assert task is not None
        assert int(task.submitted_count or 0) == 1
        assert result is not None
        assert int(result.student_count or 0) == 1
    finally:
        verify.close()
        set_tenant(None)
