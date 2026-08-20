"""D-W3 MySQL contracts for evaluation state serialization."""
from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor

import pytest
from sqlalchemy import select

TID = 1000000000000000001


def _admin_user() -> dict:
    return {
        "userId": "dw3-lock-admin",
        "loginName": "dw3_lock_admin",
        "realName": "D-W3锁验收管理员",
        "userType": "ADMIN",
        "currentRoleCode": "SCHOOL_ADMIN",
        "tenantId": str(TID),
    }


def _evaluator_user() -> dict:
    return {
        "userId": "dw3-lock-teacher",
        "loginName": "dw3_lock_teacher",
        "realName": "D-W3锁验收教师",
        "userType": "TEACHER",
        "currentRoleCode": "TEACHER",
        "tenantId": str(TID),
    }


def _bind(user: dict) -> None:
    from app.core.context import set_current_user, set_tenant

    set_tenant({"tenantId": str(TID), "tenantCode": "dw3-lock-contract"})
    set_current_user(user)


def _unbind() -> None:
    from app.core.context import set_current_user, set_tenant

    set_current_user(None)
    set_tenant(None)


def _seed_batch(*, label: str, evaluator_type: str, score: int | None = None) -> tuple[int, int]:
    from app.db.session import get_sessionmaker
    from app.models import AaEvaluationBatch, AaEvaluationRecord, AaEvaluationTask, AaTerm

    _bind(_admin_user())
    db = get_sessionmaker()()
    try:
        term = AaTerm(
            tenant_id=TID,
            year_code=f"2040-{label}",
            term_no=1,
            term_name=f"D-W3锁验收学期-{label}",
            teaching_weeks=18,
            status="PUBLISHED",
            is_current=False,
        )
        db.add(term)
        db.flush()
        batch = AaEvaluationBatch(
            tenant_id=TID,
            batch_name=f"D-W3锁验收批次-{label}",
            term_id=term.id,
            anonymous=evaluator_type == "STUDENT",
            status="OPEN",
        )
        db.add(batch)
        db.flush()
        task = AaEvaluationTask(
            tenant_id=TID,
            batch_id=batch.id,
            teaching_task_id=970000 + int(batch.id),
            course_name=f"D-W3锁验收课程-{label}",
            teacher_key="dw3_lock_target_teacher",
            teacher_name="D-W3锁验收被评教师",
            evaluator_type=evaluator_type,
            evaluator_key="dw3_lock_teacher" if evaluator_type != "STUDENT" else None,
            submitted_count=1 if score is not None else 0,
            status="SUBMITTED" if evaluator_type != "STUDENT" and score is not None else "PENDING",
        )
        db.add(task)
        db.flush()
        if score is not None:
            db.add(AaEvaluationRecord(
                tenant_id=TID,
                batch_id=batch.id,
                task_id=task.id,
                teacher_key=task.teacher_key,
                evaluator_type=evaluator_type,
                answers_json="{}",
                objective_score=score,
            ))
        db.commit()
        return int(batch.id), int(task.id)
    finally:
        db.close()
        _unbind()


def _close(batch_id: int):
    from app.modules.academic_affairs.services import academic_affairs_evaluation_public_service as service

    user = _admin_user()
    _bind(user)
    try:
        return service.close_and_score(user, batch_id)
    finally:
        _unbind()


def _publish_results(batch_id: int):
    from app.modules.academic_affairs.services import academic_affairs_evaluation_public_service as service

    user = _admin_user()
    _bind(user)
    try:
        return service.publish_results(user, batch_id)
    finally:
        _unbind()


def _submit(task_id: int):
    from app.modules.academic_affairs.services import academic_affairs_evaluation_public_service as service

    user = _evaluator_user()
    _bind(user)
    try:
        return service.submit_evaluation(
            user,
            task_id,
            {"综合评价": 91},
            91,
            "D-W3 close-submit lock contract",
        )
    finally:
        _unbind()


@pytest.mark.usefixtures("db_mode")
def test_close_waits_for_inflight_shared_submission_lock():
    """A close/score exclusive lock must not pass an in-flight submission shared lock."""
    from app.core.context import set_tenant
    from app.db.session import get_sessionmaker
    from app.models import AaEvaluationBatch, AaEvaluationResult

    batch_id, _task_id = _seed_batch(label="SHARED", evaluator_type="STUDENT", score=88)
    set_tenant({"tenantId": str(TID)})
    blocker = get_sessionmaker()()
    try:
        blocker.execute(
            select(AaEvaluationBatch).where(
                AaEvaluationBatch.id == batch_id,
                AaEvaluationBatch.tenant_id == TID,
            ).with_for_update(read=True)
        ).scalar_one()

        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(_close, batch_id)
            time.sleep(0.4)
            assert not future.done(), "close/score passed an active submission shared lock"
            blocker.commit()
            closed = future.result(timeout=15)
        assert closed["status"] == "RESULT_READY"
        assert closed["resultPublishedAt"] is None
    finally:
        blocker.rollback()
        blocker.close()
        set_tenant(None)

    verify = get_sessionmaker()()
    try:
        result = verify.scalar(select(AaEvaluationResult).where(
            AaEvaluationResult.tenant_id == TID,
            AaEvaluationResult.batch_id == batch_id,
            AaEvaluationResult.is_deleted.is_(False),
        ))
        assert result is not None
        assert float(result.student_avg) == 88.0
        assert int(result.student_count or 0) == 1
        assert result.published is False
    finally:
        verify.close()


@pytest.mark.usefixtures("db_mode")
def test_waiting_submission_rechecks_batch_after_close_commits():
    """A submission waiting behind close must observe RESULT_READY and write nothing."""
    from app.core.context import set_tenant
    from app.db.session import get_sessionmaker
    from app.models import AaEvaluationBatch, AaEvaluationRecord, AaEvaluationTask

    batch_id, task_id = _seed_batch(label="EXCLUSIVE", evaluator_type="SELF")
    set_tenant({"tenantId": str(TID)})
    blocker = get_sessionmaker()()
    try:
        batch = blocker.execute(
            select(AaEvaluationBatch).where(
                AaEvaluationBatch.id == batch_id,
                AaEvaluationBatch.tenant_id == TID,
            ).with_for_update()
        ).scalar_one()
        batch.status = "RESULT_READY"
        blocker.flush()

        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(_submit, task_id)
            time.sleep(0.4)
            assert not future.done(), "submission did not wait behind the closing batch lock"
            blocker.commit()
            with pytest.raises(Exception) as exc_info:
                future.result(timeout=15)
        assert "评教窗口未开放" in str(exc_info.value)
    finally:
        blocker.rollback()
        blocker.close()
        set_tenant(None)

    verify = get_sessionmaker()()
    try:
        task = verify.get(AaEvaluationTask, task_id)
        record_count = int(verify.scalar(select(AaEvaluationRecord.id).where(
            AaEvaluationRecord.tenant_id == TID,
            AaEvaluationRecord.task_id == task_id,
            AaEvaluationRecord.is_deleted.is_(False),
        ).limit(1)) or 0)
        assert record_count == 0
        assert task is not None
        assert int(task.submitted_count or 0) == 0
        assert task.status == "PENDING"
    finally:
        verify.close()


@pytest.mark.usefixtures("db_mode")
def test_result_publication_time_is_not_scoring_time_and_is_stable_on_republish():
    """RESULT_READY is not public; first publish sets the timestamp and retries preserve it."""
    from app.core.context import set_tenant
    from app.db.session import get_sessionmaker
    from app.models import AaEvaluationBatch, AaEvaluationResult

    batch_id, _task_id = _seed_batch(label="PUBTIME", evaluator_type="STUDENT", score=92)
    closed = _close(batch_id)
    assert closed["status"] == "RESULT_READY"
    assert closed["resultPublishedAt"] is None

    first = _publish_results(batch_id)
    assert first["published"] is True
    assert first["resultPublishedAt"]

    set_tenant({"tenantId": str(TID)})
    verify = get_sessionmaker()()
    try:
        batch = verify.get(AaEvaluationBatch, batch_id)
        result = verify.scalar(select(AaEvaluationResult).where(
            AaEvaluationResult.tenant_id == TID,
            AaEvaluationResult.batch_id == batch_id,
            AaEvaluationResult.is_deleted.is_(False),
        ))
        assert batch is not None and batch.result_published_at is not None
        assert result is not None and result.published is True
        first_published_at = batch.result_published_at
    finally:
        verify.close()
        set_tenant(None)

    time.sleep(1.1)
    second = _publish_results(batch_id)
    assert second["published"] is True

    set_tenant({"tenantId": str(TID)})
    verify = get_sessionmaker()()
    try:
        batch = verify.get(AaEvaluationBatch, batch_id)
        assert batch is not None
        assert batch.result_published_at == first_published_at
    finally:
        verify.close()
        set_tenant(None)


@pytest.mark.usefixtures("db_mode")
def test_waiting_result_publish_rechecks_batch_after_archive_commits():
    """Publish-results waiting behind archive must re-read ARCHIVED and publish nothing."""
    from app.core.context import set_tenant
    from app.db.session import get_sessionmaker
    from app.models import AaEvaluationBatch, AaEvaluationResult

    batch_id, _task_id = _seed_batch(label="ARCHIVE-RACE", evaluator_type="STUDENT", score=86)
    closed = _close(batch_id)
    assert closed["status"] == "RESULT_READY"

    set_tenant({"tenantId": str(TID)})
    blocker = get_sessionmaker()()
    try:
        batch = blocker.execute(
            select(AaEvaluationBatch).where(
                AaEvaluationBatch.id == batch_id,
                AaEvaluationBatch.tenant_id == TID,
            ).with_for_update()
        ).scalar_one()
        batch.status = "ARCHIVED"
        blocker.flush()

        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(_publish_results, batch_id)
            time.sleep(0.4)
            assert not future.done(), "publish-results did not wait behind archive batch lock"
            blocker.commit()
            with pytest.raises(Exception) as exc_info:
                future.result(timeout=15)
        assert "仅 RESULT_READY 批次可发布结果" in str(exc_info.value)
    finally:
        blocker.rollback()
        blocker.close()
        set_tenant(None)

    verify = get_sessionmaker()()
    try:
        batch = verify.get(AaEvaluationBatch, batch_id)
        result = verify.scalar(select(AaEvaluationResult).where(
            AaEvaluationResult.tenant_id == TID,
            AaEvaluationResult.batch_id == batch_id,
            AaEvaluationResult.is_deleted.is_(False),
        ))
        assert batch is not None and batch.status == "ARCHIVED"
        assert batch.result_published_at is None
        assert result is not None and result.published is False
    finally:
        verify.close()
