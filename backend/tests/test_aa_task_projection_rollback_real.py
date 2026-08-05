"""P0-6 教学任务生成与教学班投影必须在同一真实数据库事务中回滚。"""
from __future__ import annotations

import pytest

BASE = "/api/v1/academic-affairs"
TID = 1000000000000000001


def _hdr(client):
    data = client.post(
        "/api/v1/auth/mock-login",
        json={"loginName": "school_admin01", "password": "any"},
    ).json()["data"]
    return {"Authorization": f"Bearer {data['accessToken']}"}


def test_generate_batch_rolls_back_task_and_projection_facts(client, db_mode, monkeypatch):
    from app.db.session import get_sessionmaker
    from app.models import AaTeachingTask, AaTeachingTaskBatch
    from app.models.academic_affairs_teaching_class import AaTeachingClass
    from app.modules.academic_affairs.services import academic_affairs_task_service as service

    marker = "P0_ATOMIC_ROLLBACK"

    monkeypatch.setattr(
        service,
        "_generation_precheck",
        lambda db, user, college_id=None: {"programCount": 1, "warningCount": 0},
    )

    def fake_generate_tx(db, body, user):
        batch = AaTeachingTaskBatch(
            tenant_id=TID,
            term_id=int(body.termId),
            batch_name=marker,
            status="DRAFT",
        )
        db.add(batch); db.flush()
        task = AaTeachingTask(
            tenant_id=TID,
            batch_id=batch.id,
            course_id=9000001,
            course_code=marker,
            course_name="事务回滚测试课程",
            teaching_class_code=marker,
            teaching_class_name="事务回滚测试班",
            status="PENDING_ASSIGN",
        )
        db.add(task); db.flush()
        return {"batchId": str(batch.id), "tasksGenerated": 1}

    def failing_projection(db, batch_id):
        task = db.query(AaTeachingTask).filter(
            AaTeachingTask.tenant_id == TID,
            AaTeachingTask.batch_id == int(batch_id),
            AaTeachingTask.course_code == marker,
        ).one()
        db.add(AaTeachingClass(
            tenant_id=TID,
            teaching_task_id=task.id,
            term_id=1,
            course_id=task.course_id,
            class_code=marker,
            class_name="事务回滚投影班",
            class_type="ADMIN",
            source_type="TEACHING_TASK",
            status="ACTIVE",
        ))
        db.flush()
        raise RuntimeError("injected teaching-class projection failure")

    monkeypatch.setattr(service.generation, "generate_batch_tx", fake_generate_tx)
    monkeypatch.setattr(service.teaching_class, "sync_batch_teaching_classes", failing_projection)

    try:
        response = client.post(
            f"{BASE}/teaching-task-batches/generate",
            headers=_hdr(client),
            json={"termId": "1"},
        )
    except RuntimeError as exc:
        assert "injected teaching-class projection failure" in str(exc)
    else:
        assert response.status_code >= 500, response.text

    db = get_sessionmaker()()
    try:
        assert db.query(AaTeachingTaskBatch).filter(
            AaTeachingTaskBatch.tenant_id == TID,
            AaTeachingTaskBatch.batch_name == marker,
        ).count() == 0
        assert db.query(AaTeachingTask).filter(
            AaTeachingTask.tenant_id == TID,
            AaTeachingTask.course_code == marker,
        ).count() == 0
        assert db.query(AaTeachingClass).filter(
            AaTeachingClass.tenant_id == TID,
            AaTeachingClass.class_code == marker,
        ).count() == 0
    finally:
        db.close()
