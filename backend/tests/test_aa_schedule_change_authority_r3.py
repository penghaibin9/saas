"""P1-06 / AA-009-A targeted MySQL regression for schedule-change review Authority/CAS."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import pytest
from sqlalchemy import func, select

from app.core.exceptions import AppException
from app.modules.academic_affairs.services import academic_affairs_schedule_change_r3_service as svc

TID = 1000000000000000809
COLLEGE_UID = 91001
ACADEMIC_UID = 91002
COLLEGE_USER = {"userId": f"db-{COLLEGE_UID}", "loginName": "aa-r3-change-college", "currentRoleCode": "COLLEGE_ADMIN"}
OTHER_USER = {"userId": "db-91999", "loginName": "aa-r3-change-other", "currentRoleCode": "COLLEGE_ADMIN"}
ACADEMIC_USER = {"userId": f"db-{ACADEMIC_UID}", "loginName": "aa-r3-change-academic", "currentRoleCode": "ACADEMIC_ADMIN"}


def _patch(monkeypatch):
    monkeypatch.setattr(svc._legacy, "_tid", lambda: TID)
    monkeypatch.setattr(
        svc._legacy,
        "_schedule_change_assignee",
        lambda _db, node, _change: COLLEGE_UID if node == "COLLEGE_REVIEW" else ACADEMIC_UID,
    )
    monkeypatch.setattr(svc._legacy, "_msg", lambda *_a, **_k: None)
    monkeypatch.setattr(svc._legacy, "build_affairs_context", lambda *_a, **_k: SimpleNamespace(scope_type="TENANT_ALL"))


def _seed(status="SUBMITTED", current_node="COLLEGE_REVIEW", assignee_id=COLLEGE_UID, version=0, change_type="STOP"):
    from app.db.session import get_sessionmaker
    from app.models import (
        AaScheduleBatch,
        AaScheduleChange,
        AaScheduleItem,
        Tenant,
        UnifiedTodo,
        WorkflowInstance,
        WorkflowTask,
    )

    db = get_sessionmaker()()
    try:
        if db.get(Tenant, TID) is None:
            db.add(Tenant(
                id=TID,
                tenant_code="aa-r3-change-authority",
                school_name="AA R3 调停课 Authority 学校",
                short_name="AA R3 调停课",
                deploy_mode="SAAS",
                db_mode="SHARED",
                status="ACTIVE",
            ))
            db.flush()
        batch = AaScheduleBatch(tenant_id=TID, term_id=88001, batch_name="R3 调停课正式课表", status="PUBLISHED")
        db.add(batch); db.flush()
        origin = AaScheduleItem(
            tenant_id=TID,
            batch_id=batch.id,
            course_name="R3 操作系统",
            class_id=88101,
            class_name="R3 计科1班",
            teacher_key="aa-r3-change-teacher",
            teacher_name="R3 教师",
            weekday=2,
            slot_no=3,
            start_week=1,
            end_week=18,
            week_parity="ALL",
            classroom_text="A101",
            status="EFFECTIVE",
            source="MANUAL",
        )
        db.add(origin); db.flush()
        change = AaScheduleChange(
            tenant_id=TID,
            term_id=88001,
            batch_id=batch.id,
            origin_item_id=origin.id,
            change_type=change_type,
            course_name=origin.course_name,
            class_id=origin.class_id,
            class_name=origin.class_name,
            teacher_key=origin.teacher_key,
            teacher_name=origin.teacher_name,
            origin_weekday=origin.weekday,
            origin_slot_no=origin.slot_no,
            origin_start_week=origin.start_week,
            origin_end_week=origin.end_week,
            origin_week_parity=origin.week_parity,
            origin_classroom=origin.classroom_text,
            makeup_plan="后续统一补课安排",
            reason="R3 调停课测试原因",
            applicant_id=COLLEGE_UID,
            current_node=current_node,
            status=status,
            version=version,
        )
        db.add(change); db.flush()
        inst = WorkflowInstance(
            tenant_id=TID,
            workflow_code="ACAD_SCHEDULE_CHANGE",
            source_module="academic-affairs",
            source_biz_type="AA_SCHEDULE_CHANGE",
            source_biz_id=change.id,
            applicant_id=COLLEGE_UID,
            title="R3 调停课审批",
            status="RUNNING",
            current_node=current_node,
        )
        db.add(inst); db.flush()
        task = WorkflowTask(
            tenant_id=TID,
            instance_id=inst.id,
            node_code=current_node,
            assignee_id=assignee_id,
            status="PENDING",
        )
        db.add(task)
        db.add(UnifiedTodo(
            tenant_id=TID,
            source_module="academic-affairs",
            source_biz_type="AA_SCHEDULE_CHANGE",
            source_biz_id=change.id,
            todo_type="AA_SCHEDULE_CHANGE_APPROVAL",
            assignee_id=assignee_id,
            title="R3 调停课待办",
            status="PENDING",
            remark=current_node,
        ))
        change.workflow_instance_id = inst.id
        db.commit()
        return {"change": int(change.id), "task": int(task.id), "origin": int(origin.id), "instance": int(inst.id)}
    finally:
        db.close()


def _facts(ids):
    from app.db.session import get_sessionmaker
    from app.models import AaScheduleChange, WorkflowTask

    db = get_sessionmaker()()
    try:
        change = db.get(AaScheduleChange, ids["change"])
        tasks = db.scalars(select(WorkflowTask).where(WorkflowTask.instance_id == ids["instance"]).order_by(WorkflowTask.id)).all()
        return (
            change.status,
            change.current_node,
            int(change.version or 0),
            [(t.node_code, int(t.assignee_id), t.status) for t in tasks],
        )
    finally:
        db.close()


def _decision_audits(change_id):
    from app.db.session import get_sessionmaker
    from app.models import AffairsAuditTrail

    db = get_sessionmaker()()
    try:
        return int(db.scalar(select(func.count(AffairsAuditTrail.id)).where(
            AffairsAuditTrail.tenant_id == TID,
            AffairsAuditTrail.biz_type == "AA_SCHEDULE_CHANGE",
            AffairsAuditTrail.biz_id == int(change_id),
            AffairsAuditTrail.action.in_(["STEP", "REJECT", "APPROVE"]),
        )) or 0)
    finally:
        db.close()


def test_assignee_can_approve_current_node_with_matching_version(db_mode, monkeypatch):
    _patch(monkeypatch); ids = _seed()
    row = svc.review(ids["change"], COLLEGE_USER, "APPROVE", expected_version=0)
    assert row["currentNode"] == "ACADEMIC_REVIEW"
    assert row["version"] == 1
    status, node, version, tasks = _facts(ids)
    assert (status, node, version) == ("COLLEGE_REVIEW", "ACADEMIC_REVIEW", 1)
    assert tasks[0][2] == "APPROVED"
    assert tasks[1] == ("ACADEMIC_REVIEW", ACADEMIC_UID, "PENDING")


def test_same_permission_non_assignee_gets_403_and_no_side_effects(db_mode, monkeypatch):
    _patch(monkeypatch); ids = _seed(); before = _facts(ids)
    with pytest.raises(AppException) as exc:
        svc.review(ids["change"], OTHER_USER, "APPROVE", expected_version=0)
    assert exc.value.code == "NO_DATA_SCOPE"
    assert _facts(ids) == before
    assert _decision_audits(ids["change"]) == 0


def test_previous_node_assignee_cannot_approve_next_node(db_mode, monkeypatch):
    _patch(monkeypatch); ids = _seed()
    svc.review(ids["change"], COLLEGE_USER, "APPROVE", expected_version=0)
    with pytest.raises(AppException) as exc:
        svc.review(ids["change"], COLLEGE_USER, "APPROVE", expected_version=1)
    assert exc.value.code == "NO_DATA_SCOPE"
    assert _facts(ids)[0:3] == ("COLLEGE_REVIEW", "ACADEMIC_REVIEW", 1)


def test_stale_expected_version_returns_409_and_preserves_task_and_audit(db_mode, monkeypatch):
    _patch(monkeypatch); ids = _seed(); before = _facts(ids)
    with pytest.raises(AppException) as exc:
        svc.review(ids["change"], COLLEGE_USER, "APPROVE", expected_version=7)
    assert exc.value.code == "APPROVAL_VERSION_CONFLICT"
    assert exc.value.http_status == 409
    assert _facts(ids) == before
    assert _decision_audits(ids["change"]) == 0


def test_concurrent_approve_and_reject_only_one_decision_commits(db_mode, monkeypatch):
    _patch(monkeypatch); ids = _seed()
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [
            pool.submit(svc.review, ids["change"], COLLEGE_USER, "APPROVE", "", expected_version=0),
            pool.submit(svc.review, ids["change"], COLLEGE_USER, "REJECT", "不同意本次调停课申请", expected_version=0),
        ]
        success = 0
        conflicts = 0
        for future in futures:
            try:
                future.result(timeout=15)
                success += 1
            except AppException as exc:
                assert exc.code == "APPROVAL_VERSION_CONFLICT"
                conflicts += 1
    assert (success, conflicts) == (1, 1)
    assert _facts(ids)[2] == 1
    assert _decision_audits(ids["change"]) == 1


def test_review_and_cancel_race_is_serialized_by_change_first_lock(db_mode, monkeypatch):
    _patch(monkeypatch); ids = _seed()
    with ThreadPoolExecutor(max_workers=2) as pool:
        review_f = pool.submit(svc.review, ids["change"], COLLEGE_USER, "APPROVE", "", expected_version=0)
        cancel_f = pool.submit(svc.cancel, ids["change"], COLLEGE_USER, "并发撤销")
        outcomes = []
        for future in (review_f, cancel_f):
            try:
                outcomes.append(("ok", future.result(timeout=15)["status"]))
            except AppException as exc:
                outcomes.append(("err", exc.code))
    status, node, version, tasks = _facts(ids)
    assert status in {"COLLEGE_REVIEW", "CANCELLED"}
    assert version in {1, 2}
    # Any two successes must be explainable as serial college-approve then legal cancel;
    # there is never a stale overwrite or two PENDING tasks left active after cancellation.
    if status == "CANCELLED":
        assert all(task[2] != "PENDING" for task in tasks)
    assert any(kind == "ok" for kind, _ in outcomes)


def test_unresolvable_actor_id_fails_closed(db_mode, monkeypatch):
    _patch(monkeypatch); ids = _seed(); before = _facts(ids)
    bad_user = {"userId": "u-not-numeric", "currentRoleCode": "COLLEGE_ADMIN"}
    with pytest.raises(AppException) as exc:
        svc.review(ids["change"], bad_user, "APPROVE", expected_version=0)
    assert exc.value.code == "NO_DATA_SCOPE"
    assert _facts(ids) == before
