"""D-W3 evaluation close/score production scale and truth contracts."""
from __future__ import annotations

import pytest
from sqlalchemy import event

TID = 1000000000000000001
BASE = "/api/v1/academic-affairs"


def _admin_headers(client):
    data = client.post(
        "/api/v1/auth/mock-login",
        json={"loginName": "school_admin01", "password": "any"},
    ).json()["data"]
    return {"Authorization": f"Bearer {data['accessToken']}"}


@pytest.mark.usefixtures("db_mode")
def test_close_score_is_constant_query_and_ignores_soft_deleted_answers(client):
    from app.core.context import set_tenant
    from app.db.session import get_sessionmaker
    from app.models import AaEvaluationBatch, AaEvaluationRecord, AaEvaluationTask, AaTerm

    set_tenant({"tenantId": str(TID)})
    db = get_sessionmaker()()
    try:
        term = AaTerm(
            tenant_id=TID,
            year_code="2031-2032",
            term_no=1,
            term_name="D-W3评教规模学期",
            teaching_weeks=18,
            status="PUBLISHED",
            is_current=False,
        )
        db.add(term)
        db.flush()
        batch = AaEvaluationBatch(
            tenant_id=TID,
            batch_name="D-W3评教规模核算",
            term_id=term.id,
            anonymous=True,
            status="OPEN",
        )
        db.add(batch)
        db.flush()
        expected = {}
        for index in range(5):
            task = AaEvaluationTask(
                tenant_id=TID,
                batch_id=batch.id,
                teaching_task_id=910000 + index,
                course_name=f"D-W3课程{index}",
                teacher_key=f"dw3_teacher_{index}",
                teacher_name=f"D-W3教师{index}",
                evaluator_type="STUDENT",
                submitted_count=2,
                status="PENDING",
            )
            db.add(task)
            db.flush()
            first = 80 + index
            second = 90 + index
            expected[int(task.teaching_task_id)] = round((first + second) / 2, 2)
            db.add_all([
                AaEvaluationRecord(
                    tenant_id=TID,
                    batch_id=batch.id,
                    task_id=task.id,
                    teacher_key=task.teacher_key,
                    evaluator_type="STUDENT",
                    answers_json="{}",
                    objective_score=first,
                ),
                AaEvaluationRecord(
                    tenant_id=TID,
                    batch_id=batch.id,
                    task_id=task.id,
                    teacher_key=task.teacher_key,
                    evaluator_type="STUDENT",
                    answers_json="{}",
                    objective_score=second,
                ),
            ])
            if index == 0:
                db.add(AaEvaluationRecord(
                    tenant_id=TID,
                    batch_id=batch.id,
                    task_id=task.id,
                    teacher_key=task.teacher_key,
                    evaluator_type="STUDENT",
                    answers_json="{}",
                    objective_score=100,
                    is_deleted=True,
                ))
        db.commit()
        batch_id = int(batch.id)
        engine = db.get_bind()
    finally:
        db.close()
        set_tenant(None)

    headers = _admin_headers(client)
    statements: list[str] = []

    def _capture(_conn, _cursor, statement, _parameters, _context, _executemany):
        normalized = statement.lstrip().upper()
        if normalized.startswith("SELECT") and "T_AA_EVALUATION_" in normalized:
            statements.append(statement)

    event.listen(engine, "before_cursor_execute", _capture)
    try:
        response = client.post(
            f"{BASE}/evaluation/batches/{batch_id}/close-score",
            headers=headers,
        )
    finally:
        event.remove(engine, "before_cursor_execute", _capture)

    assert response.status_code == 200, response.text
    assert response.json()["data"]["status"] == "RESULT_READY"
    assert len(statements) <= 5, (
        "close-score must stay constant-query: batch + tasks + authoritative submission-count "
        "aggregate + score aggregate + result prefetch; "
        f"actual evaluation SELECTs={len(statements)}"
    )

    verify = get_sessionmaker()()
    try:
        from app.models import AaEvaluationResult

        results = verify.query(AaEvaluationResult).filter(
            AaEvaluationResult.tenant_id == TID,
            AaEvaluationResult.batch_id == batch_id,
            AaEvaluationResult.is_deleted.is_(False),
        ).all()
        assert len(results) == 5
        by_task = {int(row.teaching_task_id): row for row in results}
        for teaching_task_id, average in expected.items():
            assert float(by_task[teaching_task_id].student_avg) == average
            assert int(by_task[teaching_task_id].student_count) == 2
        assert float(by_task[910000].student_avg) == 85.0, "soft-deleted answer must not affect formal score"
    finally:
        verify.close()


@pytest.mark.usefixtures("db_mode")
def test_close_score_fails_closed_when_deleted_result_occupies_unique_key(client):
    from app.core.context import set_tenant
    from app.db.session import get_sessionmaker
    from app.models import (
        AaEvaluationBatch,
        AaEvaluationRecord,
        AaEvaluationResult,
        AaEvaluationTask,
        AaTerm,
    )

    set_tenant({"tenantId": str(TID)})
    db = get_sessionmaker()()
    try:
        term = AaTerm(
            tenant_id=TID,
            year_code="2032-2033",
            term_no=1,
            term_name="D-W3软删除结果冲突学期",
            teaching_weeks=18,
            status="PUBLISHED",
            is_current=False,
        )
        db.add(term)
        db.flush()
        batch = AaEvaluationBatch(
            tenant_id=TID,
            batch_name="D-W3软删除结果冲突",
            term_id=term.id,
            anonymous=True,
            status="OPEN",
        )
        db.add(batch)
        db.flush()
        task = AaEvaluationTask(
            tenant_id=TID,
            batch_id=batch.id,
            teaching_task_id=940001,
            course_name="D-W3冲突课程",
            teacher_key="dw3_conflict_teacher",
            teacher_name="D-W3冲突教师",
            evaluator_type="STUDENT",
            submitted_count=1,
            status="PENDING",
        )
        db.add(task)
        db.flush()
        db.add(AaEvaluationRecord(
            tenant_id=TID,
            batch_id=batch.id,
            task_id=task.id,
            teacher_key=task.teacher_key,
            evaluator_type="STUDENT",
            answers_json="{}",
            objective_score=88,
        ))
        db.add(AaEvaluationResult(
            tenant_id=TID,
            batch_id=batch.id,
            teaching_task_id=task.teaching_task_id,
            teacher_key=task.teacher_key,
            teacher_name=task.teacher_name,
            course_name=task.course_name,
            student_avg=77,
            student_count=1,
            level="PASS",
            published=False,
            is_deleted=True,
        ))
        db.commit()
        batch_id = int(batch.id)
    finally:
        db.close()
        set_tenant(None)

    response = client.post(
        f"{BASE}/evaluation/batches/{batch_id}/close-score",
        headers=_admin_headers(client),
    )
    assert response.status_code == 409, response.text
    assert "软删除" in str(response.json().get("message") or "")

    verify = get_sessionmaker()()
    try:
        persisted_batch = verify.get(AaEvaluationBatch, batch_id)
        assert persisted_batch.status == "OPEN"
        persisted = verify.query(AaEvaluationResult).filter(
            AaEvaluationResult.tenant_id == TID,
            AaEvaluationResult.batch_id == batch_id,
            AaEvaluationResult.teaching_task_id == 940001,
        ).one()
        assert persisted.is_deleted is True
        assert float(persisted.student_avg) == 77.0
    finally:
        verify.close()