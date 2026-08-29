"""P1-07 / AA-009-B targeted MySQL regression for active-origin uniqueness."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import pytest
from sqlalchemy import func, select

from app.core.exceptions import AppException
from app.modules.academic_affairs.services import academic_affairs_schedule_change_r3_service as svc

TID = 1000000000000000810
COLLEGE_UID = 92001
ACADEMIC_UID = 92002
SCHOOL_USER = {"userId": f"db-{COLLEGE_UID}", "loginName": "aa-r3-origin-school", "currentRoleCode": "ACADEMIC_ADMIN"}
ACADEMIC_USER = {"userId": f"db-{ACADEMIC_UID}", "loginName": "aa-r3-origin-final", "currentRoleCode": "ACADEMIC_ADMIN"}


def _patch(monkeypatch):
    monkeypatch.setattr(svc._legacy, "_tid", lambda: TID)
    monkeypatch.setattr(svc._legacy, "build_affairs_context", lambda *_a, **_k: SimpleNamespace(scope_type="TENANT_ALL"))
    monkeypatch.setattr(svc._legacy, "_detect_conflict", lambda *_a, **_k: None)
    monkeypatch.setattr(svc._legacy, "_todo_upsert", lambda *_a, **_k: None)
    monkeypatch.setattr(svc._legacy, "_todo_done", lambda *_a, **_k: None)
    monkeypatch.setattr(svc._legacy, "_msg", lambda *_a, **_k: None)
    monkeypatch.setattr(
        svc._legacy,
        "_schedule_change_assignee",
        lambda _db, node, _change: COLLEGE_UID if node == "COLLEGE_REVIEW" else ACADEMIC_UID,
    )

    def fake_open_wf(db, cid, applicant_id, title, first_node, change=None):
        from app.models import WorkflowInstance, WorkflowTask
        inst = WorkflowInstance(
            tenant_id=TID,
            workflow_code="ACAD_SCHEDULE_CHANGE",
            source_module="academic-affairs",
            source_biz_type="AA_SCHEDULE_CHANGE",
            source_biz_id=int(cid),
            applicant_id=int(applicant_id or 0),
            title=title,
            status="RUNNING",
            current_node=first_node,
        )
        db.add(inst); db.flush()
        db.add(WorkflowTask(
            tenant_id=TID,
            instance_id=inst.id,
            node_code=first_node,
            assignee_id=COLLEGE_UID,
            status="PENDING",
        ))
        return inst

    monkeypatch.setattr(svc._legacy, "_open_wf", fake_open_wf)


def _seed_origins():
    from app.db.session import get_sessionmaker
    from app.models import AaScheduleBatch, AaScheduleItem, Tenant

    db = get_sessionmaker()()
    try:
        if db.get(Tenant, TID) is None:
            db.add(Tenant(
                id=TID,
                tenant_code="aa-r3-origin-unique",
                school_name="AA R3 原课位唯一学校",
                short_name="AA R3 原课位",
                deploy_mode="SAAS",
                db_mode="SHARED",
                status="ACTIVE",
            ))
            db.flush()
        batch = AaScheduleBatch(tenant_id=TID, term_id=99001, batch_name="R3 已发布课表", status="PUBLISHED")
        db.add(batch); db.flush()
        origins = []
        for index in (1, 2):
            item = AaScheduleItem(
                tenant_id=TID,
                batch_id=batch.id,
                task_id=99000 + index,
                course_id=98000 + index,
                course_name=f"R3 课程 {index}",
                class_id=97000 + index,
                class_name=f"R3 班级 {index}",
                teacher_key=f"r3-teacher-{index}",
                teacher_name=f"R3 教师 {index}",
                weekday=index,
                slot_no=2,
                start_week=1,
                end_week=18,
                week_parity="ALL",
                classroom_text=f"R3-A10{index}",
                status="EFFECTIVE",
                source="MANUAL",
            )
            db.add(item); db.flush(); origins.append(int(item.id))
        db.commit()
        return {"batch": int(batch.id), "origin1": origins[0], "origin2": origins[1]}
    finally:
        db.close()


def _body(origin_id, change_type="STOP"):
    values = {
        "originItemId": origin_id,
        "changeType": change_type,
        "reason": "R3 调停课并发唯一性测试原因",
        "makeupPlan": "后续补课安排已确认" if change_type == "STOP" else "",
        "targetWeekday": None,
        "targetSlotNo": None,
        "targetStartWeek": None,
        "targetEndWeek": None,
        "targetWeekParity": None,
        "targetClassroom": None,
    }
    if change_type in {"ADJUST", "MAKEUP"}:
        values.update({"targetWeekday": 6, "targetSlotNo": 4, "targetClassroom": "R3-B201"})
    return SimpleNamespace(**values)


def _active_count(origin_id):
    from app.db.session import get_sessionmaker
    from app.models import AaScheduleChange
    db = get_sessionmaker()()
    try:
        return int(db.scalar(select(func.count(AaScheduleChange.id)).where(
            AaScheduleChange.tenant_id == TID,
            AaScheduleChange.origin_item_id == int(origin_id),
            AaScheduleChange.status.in_(svc._legacy._ACTIVE),
            AaScheduleChange.is_deleted.is_(False),
        )) or 0)
    finally:
        db.close()


def test_two_concurrent_submits_same_origin_only_one_succeeds(db_mode, monkeypatch):
    _patch(monkeypatch); ids = _seed_origins(); body = _body(ids["origin1"])
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(svc.submit, body, SCHOOL_USER) for _ in range(2)]
        success = 0; conflict = 0
        for future in futures:
            try:
                future.result(timeout=15); success += 1
            except AppException as exc:
                assert exc.code == "DATA_CONFLICT"
                assert exc.details.get("existingChangeId")
                conflict += 1
    assert (success, conflict) == (1, 1)
    assert _active_count(ids["origin1"]) == 1


def test_existing_active_change_returns_409_with_existing_change_id(db_mode, monkeypatch):
    _patch(monkeypatch); ids = _seed_origins(); first = svc.submit(_body(ids["origin1"]), SCHOOL_USER)
    with pytest.raises(AppException) as exc:
        svc.submit(_body(ids["origin1"]), SCHOOL_USER)
    assert exc.value.code == "DATA_CONFLICT"
    assert exc.value.http_status == 409
    assert exc.value.details["existingChangeId"] == first["changeId"]


def test_terminal_adjust_fails_if_origin_already_changed_and_creates_no_new_item(db_mode, monkeypatch):
    _patch(monkeypatch); ids = _seed_origins()
    from app.db.session import get_sessionmaker
    from app.models import AaScheduleChange, AaScheduleItem, WorkflowInstance, WorkflowTask

    db = get_sessionmaker()()
    try:
        origin = db.get(AaScheduleItem, ids["origin1"])
        origin.status = "CHANGED"
        change = AaScheduleChange(
            tenant_id=TID, term_id=99001, batch_id=ids["batch"], origin_item_id=origin.id,
            task_id=origin.task_id, change_type="ADJUST", course_name=origin.course_name,
            class_id=origin.class_id, class_name=origin.class_name, teacher_key=origin.teacher_key,
            teacher_name=origin.teacher_name, origin_weekday=origin.weekday, origin_slot_no=origin.slot_no,
            origin_start_week=origin.start_week, origin_end_week=origin.end_week,
            origin_week_parity=origin.week_parity, origin_classroom=origin.classroom_text,
            target_weekday=6, target_slot_no=4, target_start_week=1, target_end_week=18,
            target_week_parity="ALL", target_classroom="R3-B201", reason="终审原课位不变量测试",
            applicant_id=COLLEGE_UID, status="COLLEGE_REVIEW", current_node="ACADEMIC_REVIEW", version=1,
        )
        db.add(change); db.flush()
        inst = WorkflowInstance(
            tenant_id=TID, workflow_code="ACAD_SCHEDULE_CHANGE", source_module="academic-affairs",
            source_biz_type="AA_SCHEDULE_CHANGE", source_biz_id=change.id, applicant_id=COLLEGE_UID,
            title="R3 终审", status="RUNNING", current_node="ACADEMIC_REVIEW",
        )
        db.add(inst); db.flush()
        task = WorkflowTask(
            tenant_id=TID, instance_id=inst.id, node_code="ACADEMIC_REVIEW",
            assignee_id=ACADEMIC_UID, status="PENDING",
        )
        db.add(task); change.workflow_instance_id = inst.id
        db.commit(); cid = int(change.id); task_id = int(task.id)
    finally:
        db.close()

    with pytest.raises(AppException) as exc:
        svc.review(cid, ACADEMIC_USER, "APPROVE", expected_version=1)
    assert exc.value.code == "DATA_CONFLICT"

    db = get_sessionmaker()()
    try:
        change = db.get(AaScheduleChange, cid)
        task = db.get(WorkflowTask, task_id)
        new_items = db.query(AaScheduleItem).filter(AaScheduleItem.change_id == cid).count()
        assert (change.status, change.version) == ("COLLEGE_REVIEW", 1)
        assert task.status == "PENDING"
        assert new_items == 0
    finally:
        db.close()


def test_different_origins_do_not_block_each_other(db_mode, monkeypatch):
    _patch(monkeypatch); ids = _seed_origins()
    with ThreadPoolExecutor(max_workers=2) as pool:
        a = pool.submit(svc.submit, _body(ids["origin1"]), SCHOOL_USER)
        b = pool.submit(svc.submit, _body(ids["origin2"]), SCHOOL_USER)
        assert a.result(timeout=15)["status"] == "SUBMITTED"
        assert b.result(timeout=15)["status"] == "SUBMITTED"
    assert _active_count(ids["origin1"]) == 1
    assert _active_count(ids["origin2"]) == 1


def test_makeup_keeps_origin_but_still_allows_only_one_active_change_at_a_time(db_mode, monkeypatch):
    _patch(monkeypatch); ids = _seed_origins()
    first = svc.submit(_body(ids["origin1"], "MAKEUP"), SCHOOL_USER)
    from app.db.session import get_sessionmaker
    from app.models import AaScheduleItem
    db = get_sessionmaker()()
    try:
        assert db.get(AaScheduleItem, ids["origin1"]).status == "EFFECTIVE"
    finally:
        db.close()
    with pytest.raises(AppException) as exc:
        svc.submit(_body(ids["origin1"], "MAKEUP"), SCHOOL_USER)
    assert exc.value.code == "DATA_CONFLICT"
    assert exc.value.details["existingChangeId"] == first["changeId"]
