"""D-W3 evaluation read-side SQL pagination and aggregate contracts."""
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
def test_evaluation_batch_and_result_lists_are_true_db_pages(client):
    from app.core.context import set_tenant
    from app.db.session import get_sessionmaker
    from app.models import AaEvaluationBatch, AaEvaluationResult

    set_tenant({"tenantId": str(TID)})
    db = get_sessionmaker()()
    try:
        batch_ids = []
        for index in range(5):
            batch = AaEvaluationBatch(
                tenant_id=TID,
                batch_name=f"D-W3分页批次-{index}",
                anonymous=True,
                status="DRAFT",
            )
            db.add(batch)
            db.flush()
            batch_ids.append(int(batch.id))
        result_batch = AaEvaluationBatch(
            tenant_id=TID,
            batch_name="D-W3结果分页批次",
            anonymous=True,
            status="RESULT_READY",
        )
        db.add(result_batch)
        db.flush()
        for index in range(5):
            db.add(AaEvaluationResult(
                tenant_id=TID,
                batch_id=result_batch.id,
                teaching_task_id=920000 + index,
                teacher_key=f"dw3_page_teacher_{index}",
                teacher_name=f"D-W3分页教师{index}",
                course_name=f"D-W3分页课程{index}",
                student_avg=80 + index,
                student_count=10,
                level="GOOD",
                published=True,
            ))
        db.add(AaEvaluationResult(
            tenant_id=TID,
            batch_id=result_batch.id,
            teaching_task_id=929999,
            teacher_key="dw3_deleted_page_teacher",
            teacher_name="D-W3已删除分页教师",
            course_name="D-W3已删除分页课程",
            student_avg=0,
            student_count=999,
            level="NEED_IMPROVE",
            published=True,
            is_deleted=True,
        ))
        db.commit()
        result_batch_id = int(result_batch.id)
    finally:
        db.close()
        set_tenant(None)

    headers = _admin_headers(client)
    batches = client.get(
        f"{BASE}/evaluation/batches",
        headers=headers,
        params={"status": "DRAFT", "page": 2, "pageSize": 2},
    )
    assert batches.status_code == 200, batches.text
    batch_data = batches.json()["data"]
    assert batch_data["total"] == 5
    assert len(batch_data["items"]) == 2
    assert {int(row["batchId"]) for row in batch_data["items"]}.issubset(set(batch_ids))

    oversized = client.get(
        f"{BASE}/evaluation/batches",
        headers=headers,
        params={"page": 1, "pageSize": 101},
    )
    assert oversized.status_code in (400, 422), oversized.text

    results = client.get(
        f"{BASE}/evaluation/batches/{result_batch_id}/results",
        headers=headers,
        params={"page": 2, "pageSize": 2},
    )
    assert results.status_code == 200, results.text
    result_data = results.json()["data"]
    assert result_data["total"] == 5, "soft-deleted evaluation result must stay out of list totals"
    assert len(result_data["items"]) == 2
    assert all(row["teacherName"] != "D-W3已删除分页教师" for row in result_data["items"])


@pytest.mark.usefixtures("db_mode")
def test_evaluation_stats_use_sql_aggregates_not_table_materialization(client):
    from app.core.context import set_tenant
    from app.db.session import get_sessionmaker
    from app.models import AaEvaluationBatch, AaEvaluationResult, AaEvaluationTask

    set_tenant({"tenantId": str(TID)})
    db = get_sessionmaker()()
    try:
        batch = AaEvaluationBatch(
            tenant_id=TID,
            batch_name="D-W3统计聚合批次",
            anonymous=True,
            status="RESULT_READY",
        )
        db.add(batch)
        db.flush()
        for index, (score, level) in enumerate(((95, "EXCELLENT"), (85, "GOOD"), (65, "PASS"))):
            db.add(AaEvaluationResult(
                tenant_id=TID,
                batch_id=batch.id,
                teaching_task_id=930000 + index,
                teacher_key=f"dw3_stats_teacher_{index}",
                teacher_name=f"D-W3统计教师{index}",
                course_name=f"D-W3统计课程{index}",
                student_avg=score,
                student_count=20,
                level=level,
                published=True,
            ))
        db.add(AaEvaluationResult(
            tenant_id=TID,
            batch_id=batch.id,
            teaching_task_id=939999,
            teacher_key="dw3_deleted_stats_teacher",
            teacher_name="D-W3已删除统计教师",
            course_name="D-W3已删除统计课程",
            student_avg=0,
            student_count=1000,
            level="NEED_IMPROVE",
            published=True,
            is_deleted=True,
        ))
        db.add_all([
            AaEvaluationTask(
                tenant_id=TID,
                batch_id=batch.id,
                teaching_task_id=930000,
                evaluator_type="STUDENT",
                submitted_count=20,
                status="PENDING",
            ),
            AaEvaluationTask(
                tenant_id=TID,
                batch_id=batch.id,
                teaching_task_id=930001,
                evaluator_type="STUDENT",
                submitted_count=0,
                status="PENDING",
            ),
            AaEvaluationTask(
                tenant_id=TID,
                batch_id=batch.id,
                teaching_task_id=930002,
                evaluator_type="SUPERVISOR",
                submitted_count=1,
                status="SUBMITTED",
            ),
        ])
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
        response = client.get(
            f"{BASE}/evaluation/batches/{batch_id}/stats",
            headers=headers,
        )
    finally:
        event.remove(engine, "before_cursor_execute", _capture)

    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["resultCount"] == 3, "soft-deleted result must not re-enter formal statistics"
    assert data["overallAvg"] == pytest.approx(81.67, abs=0.01)
    assert data["byLevel"] == {"EXCELLENT": 1, "GOOD": 1, "PASS": 1}
    assert data["participation"]["STUDENT"] == {"total": 2, "submitted": 1, "rate": 50.0}
    assert data["participation"]["SUPERVISOR"] == {"total": 1, "submitted": 1, "rate": 100.0}
    assert len(statements) <= 3, (
        "evaluation stats must stay aggregate-only: summary + level distribution + participation; "
        f"actual evaluation SELECTs={len(statements)}"
    )
