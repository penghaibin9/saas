"""承接后的排课消费者：隔离 MySQL 初始事实与正式 HTTP 命令。"""
from __future__ import annotations

import pytest
from tests.test_aa_task_source_review import _pair
from tests.test_aa_v5_school_schedule_gate import _candidate, _summary
from tests.test_aa_schedule import BASE, TID


def _handoff(facts):
    from app.db.session import get_sessionmaker
    from app.models import AaTeachingTask, AaTeachingTaskSourceHandoff
    with get_sessionmaker()() as db:
        old = db.get(AaTeachingTask, int(facts["oldId"]))
        new = db.get(AaTeachingTask, int(facts["newId"]))
        new.course_name = old.course_name
        # 已正式确认的承接是此消费者回归的隔离初始事实；确认命令另有专属回归。
        db.add(AaTeachingTaskSourceHandoff(tenant_id=TID, term_id=facts["termId"],
            execution_task_id=old.id, successor_task_id=new.id,
            execution_source_id=old.source_program_course_id,
            successor_source_id=new.source_program_course_id,
            source_fingerprint="a" * 64, reason="隔离消费者已有正式承接事实",
            confirmed_by=1, idempotency_key="schedule-consumer-pair", payload_hash="b" * 64))
        db.commit()


def test_handoff_gate_counts_original_once_and_preserves_original_item(client, db_mode):
    from app.db.session import get_sessionmaker
    from app.models import AaScheduleItem, AaTeachingTask
    facts = _pair(client)
    batch_id = _candidate(client, facts, 0, pre_publish=False)
    before = _summary(client, facts, batch_id)
    assert before["duplicateTaskGroupCount"] == 1, before
    with get_sessionmaker()() as db:
        item = db.query(AaScheduleItem).filter(AaScheduleItem.batch_id == int(batch_id)).one()
        item_identity = (item.id, item.task_id, item.start_week, item.end_week, item.status)
    _handoff(facts)
    after = _summary(client, facts, batch_id)
    assert after["totalTasks"] == 1 and after["expectedContactHours"] == 18, after
    assert after["duplicateTaskGroupCount"] == 0 and after["missingContactHours"] == 0, after
    response = client.post(f"{BASE}/schedule-batches/{batch_id}/pre-publish", headers=facts["school"])
    assert response.status_code == 200, response.text
    with get_sessionmaker()() as db:
        item = db.get(AaScheduleItem, item_identity[0])
        assert (item.id, item.task_id, item.start_week, item.end_week, item.status) == item_identity
        assert db.get(AaTeachingTask, int(facts["newId"])).status == "READY"


@pytest.mark.parametrize("preflight", [False, True])
def test_explicit_successor_schedule_is_rejected_without_forwarding(client, db_mode, preflight):
    from app.db.session import get_sessionmaker
    from app.models import AaScheduleItem
    facts = _pair(client)
    batch_id = _candidate(client, facts, 0, add_item=False, pre_publish=False)
    _handoff(facts)
    body = {"taskId": facts["newId"], "classId": facts["tasks"][0]["classId"],
        "weekday": 1, "slotNo": 1, "startWeek": 1, "endWeek": 18,
        "weekParity": "ALL", "classroom": "发布测试教室0"}
    suffix = "/preflight" if preflight else ""
    response = client.post(f"{BASE}/schedule-batches/{batch_id}/items{suffix}",
        headers=facts["school"], json=body)
    assert response.status_code == 409, response.text
    assert "TASK_EXECUTION_HANDOFF" in response.text
    with get_sessionmaker()() as db:
        assert db.query(AaScheduleItem).filter(AaScheduleItem.batch_id == int(batch_id)).count() == 0


def test_import_preload_rejects_successor_and_name_match_uses_original(client, db_mode):
    from app.db.session import get_sessionmaker
    from app.models import AaScheduleItem
    facts = _pair(client)
    batch_id = _candidate(client, facts, 0, add_item=False, pre_publish=False)
    _handoff(facts)
    task = facts["tasks"][0]
    row = {"courseName": task["courseName"], "teacherKey": task["teacherKey"],
        "classId": task["classId"], "weekday": 1, "slotNo": 1,
        "startWeek": 1, "endWeek": 18, "weekParity": "ALL", "classroom": "发布测试教室0"}
    response = client.post(f"{BASE}/schedule-batches/{batch_id}/import", headers=facts["school"],
        json={"items": [{**row, "taskId": facts["newId"]}, row], "atomic": True})
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["committed"] is False and data["imported"] == 0, data
    assert data["errors"][0]["details"]["blocker"] == "TASK_EXECUTION_HANDOFF", data
    response = client.post(f"{BASE}/schedule-batches/{batch_id}/import", headers=facts["school"],
        json={"items": [row], "atomic": True})
    assert response.status_code == 200 and response.json()["data"]["imported"] == 1, response.text
    with get_sessionmaker()() as db:
        item = db.query(AaScheduleItem).filter(AaScheduleItem.batch_id == int(batch_id)).one()
        assert str(item.task_id) == facts["oldId"]


def test_autoschedule_pending_excludes_successor_but_keeps_original(client, db_mode):
    from app.core.context import get_tenant, set_tenant
    from app.db.session import get_sessionmaker
    from app.models import AaScheduleBatch
    from app.modules.academic_affairs.services.academic_affairs_autoschedule_final_service import _pending_tasks_for_batch
    facts = _pair(client)
    batch_id = _candidate(client, facts, 0, add_item=False, pre_publish=False)
    _handoff(facts)
    previous = get_tenant()
    set_tenant(TID)
    try:
        with get_sessionmaker()() as db:
            batch = db.get(AaScheduleBatch, int(batch_id))
            pending, invalid = _pending_tasks_for_batch(db, batch, 18, lock=True)
            assert {str(row[0].id) for row in pending} == {facts["oldId"]}
            assert not invalid
    finally:
        set_tenant(previous)


def test_optimizer_snapshot_includes_handoff_and_invalidates_prior_revision(client, db_mode):
    from app.core.context import get_tenant, set_tenant, get_current_user_ctx, set_current_user
    from app.db.session import get_sessionmaker
    from app.models import (User, Role, UserRole, StudentProfile, AaScheduleRule,
        AaTeachingClass, AaTeachingClassRosterVersion)
    from app.modules.academic_affairs.services.academic_affairs_roster_consumer_service import roster_hash
    from app.modules.academic_affairs.services.schedule_optimizer_source_service import capture_source
    facts = _pair(client)
    batch_id = _candidate(client, facts, 0, add_item=False, pre_publish=False)
    with get_sessionmaker()() as db:
        account = db.query(User).filter(User.tenant_id == TID, User.login_name == "school_admin01").one()
        role = db.query(Role).join(UserRole, UserRole.role_id == Role.id).filter(
            Role.tenant_id == TID, Role.role_code == "SCHOOL_ADMIN", UserRole.user_id == account.id).one()
        user = {"userId": f"db-{account.id}", "tenantId": str(TID),
            "loginName": account.login_name, "currentRoleCode": role.role_code,
            "activeContextId": f"role:{role.id}", "userType": account.user_type}
        for student_id in (711, 712):
            if db.get(StudentProfile, student_id) is None:
                db.add(StudentProfile(id=student_id, tenant_id=TID, student_no=f"HANDOFF-{student_id}",
                    real_name="隔离名单测试学生", status="ACTIVE"))
        for teaching_class in db.query(AaTeachingClass).filter(AaTeachingClass.tenant_id == TID,
                AaTeachingClass.teaching_task_id.in_([int(facts["oldId"]), int(facts["newId"])])):
            version = db.get(AaTeachingClassRosterVersion, teaching_class.current_roster_version_id)
            version.roster_hash = roster_hash([711, 712])
        db.add(AaScheduleRule(tenant_id=TID, term_id=facts["termId"], batch_id=int(batch_id),
            rule_key="AUTO_WEEKDAYS", rule_value_json="[1,2,3,4,5]", status="ENABLED"))
        db.commit()
    previous_tenant, previous_user = get_tenant(), get_current_user_ctx()
    set_tenant(TID); set_current_user(user)
    try:
        with get_sessionmaker()() as db:
            before, before_revision = capture_source(db, user, batch_id)
        assert set(before["targetTaskIds"]) == {facts["oldId"], facts["newId"]}
        assert before["executionHandoffs"] == []
        _handoff(facts)
        with get_sessionmaker()() as db:
            after, after_revision = capture_source(db, user, batch_id, lock=True)
        assert after["targetTaskIds"] == [facts["oldId"]]
        assert after_revision != before_revision
        assert after["executionHandoffs"][0]["successor_task_id"] == facts["newId"]
        assert after["executionHandoffs"][0]["execution_task_id"] == facts["oldId"]
    finally:
        set_current_user(previous_user); set_tenant(previous_tenant)


def test_existing_successor_item_cannot_be_adjusted_or_published(client, db_mode):
    from app.db.session import get_sessionmaker
    from app.models import AaScheduleItem, AaTeachingTask
    facts = _pair(client)
    batch_id = _candidate(client, facts, 0, add_item=False, pre_publish=False)
    _handoff(facts)
    # 隔离反例：异常旧课位即使预载到内存，也不能开放后继执行或被完整性忽略。
    with get_sessionmaker()() as db:
        task = db.get(AaTeachingTask, int(facts["newId"]))
        item = AaScheduleItem(tenant_id=TID, batch_id=int(batch_id), task_id=task.id,
            course_id=task.course_id, class_id=task.class_id, teacher_key=task.teacher_key,
            weekday=1, slot_no=1, start_week=1, end_week=18, week_parity="ALL",
            status="EFFECTIVE", source="IMPORT")
        db.add(item); db.flush(); item_id = item.id; db.commit()
    summary = _summary(client, facts, batch_id)
    assert summary["orphanItemCount"] == 1 and summary["complete"] is False, summary
    response = client.put(f"{BASE}/schedule-items/{item_id}/move", headers=facts["school"],
        json={"weekday": 2, "slotNo": 1})
    assert response.status_code == 409 and "TASK_EXECUTION_HANDOFF" in response.text, response.text
    response = client.post(f"{BASE}/schedule-batches/{batch_id}/pre-publish", headers=facts["school"])
    assert response.status_code == 409, response.text
    with get_sessionmaker()() as db:
        item = db.get(AaScheduleItem, item_id)
        assert item.weekday == 1 and str(item.task_id) == facts["newId"]


def test_optimizer_readiness_applies_handoff_filter_before_task_limit(client, db_mode):
    from app.db.session import get_sessionmaker
    from app.models import AaTeachingTask, AaTeachingTaskSourceHandoff
    facts = _pair(client)
    batch_id = _candidate(client, facts, 0, add_item=False, pre_publish=False)
    _handoff(facts)
    with get_sessionmaker()() as db:
        original = db.get(AaTeachingTask, int(facts["oldId"]))
        successor = db.get(AaTeachingTask, int(facts["newId"]))
        # 隔离规模反例：1001条历史后继不应占用1000个独立执行任务的限额。
        historical = [AaTeachingTask(tenant_id=TID, batch_id=successor.batch_id,
            course_id=successor.course_id, class_id=successor.class_id,
            source_program_course_id=successor.source_program_course_id,
            course_name=original.course_name, status="READY", formation_mode="ADMIN_FIXED",
            teacher_key=original.teacher_key, teacher_name=original.teacher_name,
            weekly_hours=1, total_hours=18, start_week=1, end_week=18,
            teaching_class_name=original.teaching_class_name) for _ in range(1000)]
        db.add_all(historical); db.flush()
        db.add_all([AaTeachingTaskSourceHandoff(tenant_id=TID, term_id=facts["termId"],
            execution_task_id=original.id, successor_task_id=task.id,
            execution_source_id=original.source_program_course_id,
            successor_source_id=task.source_program_course_id,
            source_fingerprint="a" * 64, reason="隔离历史规模承接初始事实", confirmed_by=1,
            idempotency_key=f"readiness-limit-{task.id}", payload_hash="b" * 64) for task in historical])
        db.commit()
    response = client.get(f"{BASE}/scheduling/batches/{batch_id}/optimizer/readiness", headers=facts["school"])
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["summary"]["taskCount"] == 1 and data["summary"]["truncated"] is False, data
    assert not any(row["code"] == "SOURCE_READ_LIMIT" for row in data["blockers"]), data
    context = client.get(f"{BASE}/scheduling/batches/{batch_id}/optimizer/context", headers=facts["school"])
    assert context.status_code == 200, context.text
    current = context.json()["data"]
    assert current["summary"]["taskCount"] == 1, current
    assert not any(row["code"] == "SOURCE_READ_LIMIT" for row in current["blockers"]), current


def test_optimizer_readiness_does_not_hide_malformed_handoff(client, db_mode):
    from app.db.session import get_sessionmaker
    from app.models import AaTeachingTaskSourceHandoff
    facts = _pair(client)
    batch_id = _candidate(client, facts, 0, add_item=False, pre_publish=False)
    _handoff(facts)
    with get_sessionmaker()() as db:
        relation = db.query(AaTeachingTaskSourceHandoff).filter(
            AaTeachingTaskSourceHandoff.tenant_id == TID,
            AaTeachingTaskSourceHandoff.successor_task_id == int(facts["newId"])).one()
        relation.successor_source_id += 1
        db.commit()
    response = client.get(f"{BASE}/scheduling/batches/{batch_id}/optimizer/readiness", headers=facts["school"])
    assert response.status_code == 409 and "TASK_HANDOFF_REFERENCE_INVALID" in response.text, response.text
