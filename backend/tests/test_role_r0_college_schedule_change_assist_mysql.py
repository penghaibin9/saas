"""隔离库构造正式源课位，验证学院代办接口；不是排课发布或学校验收证据。"""
from datetime import datetime

import pytest
from sqlalchemy import select

from affairs_contract_test_support import role_headers

TID = 1000000000000000001
BASE = "/api/v1/academic-affairs/schedule-change"


@pytest.fixture
def assist_case(db_mode):
    from app.db.session import get_sessionmaker
    from app.models import (AaCourse, AaScheduleBatch, AaScheduleItem, AaScheduleScopeHead,
                            AaTeachingClass, AaTeachingClassTeacher, AaTeachingTask,
                            AaTeachingTaskBatch, AaTerm, College, Major, Role,
                            RoleAssignmentScope, SchoolClass, User, UserRole)
    from tests.support_schedule_change_identity import seed_schedule_change_identity

    headers = {name: role_headers("COLLEGE_ACADEMIC", login_name=f"r0-assist-{name}", real_name=f"学院教务{name}")
               for name in ("own", "peer", "other", "unscoped", "school")}
    headers["teacher"] = role_headers("ACADEMIC_TEACHER", login_name="r0-assist-teacher", real_name="正式任课教师")
    with get_sessionmaker()() as db:
        colleges = [College(tenant_id=TID, college_name=f"R0协助学院{i}", status="ACTIVE") for i in (1, 2)]
        db.add_all(colleges)
        term = AaTerm(tenant_id=TID, year_code="2098-2099", term_no=1, term_name="协助登记回归学期",
                      start_date=datetime(2098, 9, 1), end_date=datetime(2099, 1, 31),
                      teaching_weeks=18, status="PUBLISHED", is_current=True)
        db.add(term)
        db.flush()
        own, other = [int(c.id) for c in colleges]
        major = Major(tenant_id=TID, college_id=own, major_name="协助登记专业", status="ACTIVE")
        db.add(major)
        db.flush()
        school_class = SchoolClass(tenant_id=TID, major_id=major.id, class_name="协助登记一班", grade="2098", status="ACTIVE")
        db.add(school_class)
        db.flush()
        batch = AaScheduleBatch(tenant_id=TID, term_id=term.id, batch_name="协助登记正式课表", status="PUBLISHED")
        db.add(batch)
        db.flush()
        db.add(AaScheduleScopeHead(tenant_id=TID, term_id=term.id, scope_type="SCHOOL", scope_id=0, active_batch_id=batch.id))
        role = db.scalars(select(Role).where(Role.tenant_id == TID, Role.role_code == "COLLEGE_ACADEMIC")).one()
        users = {name: db.scalars(select(User).where(User.tenant_id == TID, User.login_name == f"r0-assist-{name}")).one()
                 for name in ("own", "peer", "other", "unscoped", "school")}
        for name, college_id in (("own", own), ("peer", own), ("other", other), ("school", 0)):
            member = db.scalars(select(UserRole).where(UserRole.tenant_id == TID,
                UserRole.user_id == users[name].id, UserRole.role_id == role.id)).one()
            db.add(RoleAssignmentScope(tenant_id=TID, user_role_id=member.id, user_id=users[name].id,
                role_code="COLLEGE_ACADEMIC", scope_type="SCHOOL" if name == "school" else "COLLEGE",
                scope_id=college_id, effective_at=datetime(2020, 1, 1), status="ACTIVE"))
        origins = {}
        relation_id = None
        cases = [("own", own, other, TID, False), ("other", other, own, TID, False),
                 ("unknown", None, None, TID, False), ("foreign", own, own, TID + 1, False),
                 ("deleted", own, own, TID, True)]
        for index, (name, owner, batch_owner, tenant_id, deleted) in enumerate(cases, 1):
            course = AaCourse(tenant_id=tenant_id, course_code=f"R0-ASSIST-{name}", course_name=name,
                              owner_college_id=owner, status="ENABLED")
            task_batch = AaTeachingTaskBatch(tenant_id=tenant_id, term_id=term.id, batch_name=name,
                                             college_id=batch_owner, status="APPROVED")
            db.add_all([course, task_batch])
            db.flush()
            task = AaTeachingTask(tenant_id=tenant_id, batch_id=task_batch.id, course_id=course.id,
                teacher_key="stale-key", teacher_name="历史快照教师", class_id=school_class.id if name != "unknown" else None,
                start_week=1, end_week=18, status="READY", is_deleted=deleted)
            db.add(task)
            db.flush()
            item = AaScheduleItem(tenant_id=TID, batch_id=batch.id, task_id=task.id, course_id=course.id,
                course_name=f"协助登记{name}", class_id=school_class.id, class_name=school_class.class_name,
                teacher_key="stale-key", teacher_name="历史快照教师", weekday=1, slot_no=index,
                start_week=1, end_week=18, week_parity="ALL", classroom_text="A101", status="EFFECTIVE")
            db.add(item)
            teaching_class = AaTeachingClass(tenant_id=tenant_id, teaching_task_id=task.id, term_id=term.id,
                course_id=course.id, class_code=f"ASSIST-{name}", class_name=name)
            db.add(teaching_class)
            db.flush()
            relation = AaTeachingClassTeacher(tenant_id=tenant_id, teaching_class_id=teaching_class.id,
                teacher_key="r0-assist-teacher", teacher_name="正式任课教师", start_week=1, end_week=18, status="ACTIVE")
            db.add(relation)
            db.flush()
            origins[name] = int(item.id)
            if name == "own":
                relation_id = int(relation.id)
        orphan = AaScheduleItem(tenant_id=TID, batch_id=batch.id, teacher_key="r0-assist-teacher",
            teacher_name="正式任课教师", weekday=1, slot_no=8, start_week=1, end_week=18, status="EFFECTIVE")
        db.add(orphan)
        seed_schedule_change_identity(db, college_ids=[own, other])
        db.commit()
        origins["orphan"] = int(orphan.id)
        return {"headers": headers, "origins": origins, "uid": int(users["own"].id),
                "term": int(term.id), "relation": relation_id}


def _body(origin_id, change_type="ADJUST"):
    return {"originItemId": str(origin_id), "changeType": change_type, "reason": "本院教学安排调整申请",
            "targetWeekday": 2, "targetSlotNo": 2, "targetStartWeek": 1, "targetEndWeek": 1,
            "targetWeekParity": "ALL", "targetClassroom": "A101", "makeupPlan": "后续按原教学计划统一补课"}


def _counts():
    from app.db.session import get_sessionmaker
    from app.models import AaScheduleChange, AffairsAuditTrail, WorkflowInstance
    with get_sessionmaker()() as db:
        return (db.query(AaScheduleChange).count(),
                db.query(AffairsAuditTrail).filter(AffairsAuditTrail.biz_type == "AA_SCHEDULE_CHANGE").count(),
                db.query(WorkflowInstance).filter(WorkflowInstance.source_biz_type == "AA_SCHEDULE_CHANGE").count())


@pytest.mark.parametrize("change_type", ["ADJUST", "STOP", "MAKEUP"])
def test_college_assist_submit_readback_and_cancel_keep_real_operator_and_teacher(client, assist_case, change_type):
    from app.db.session import get_sessionmaker
    from app.models import AaScheduleChange, AaScheduleItem, AffairsAuditTrail, WorkflowInstance, WorkflowTask

    case = assist_case
    headers = case["headers"]["own"]
    body = _body(case["origins"]["own"], change_type)
    origin = client.get(f"{BASE}/origin-items/{body['originItemId']}", headers=headers)
    assert origin.status_code == 200, origin.text
    assert origin.json()["data"]["teacherName"] == "正式任课教师"
    if change_type != "STOP":
        checked = client.post(f"{BASE}/conflict-check", headers=headers, json=body)
        assert checked.status_code == 200, checked.text
        assert not checked.json()["data"]["conflict"]
    created = client.post(BASE, headers=headers, json=body)
    assert created.status_code == 200, created.text
    change_id = int(created.json()["data"]["changeId"])
    with get_sessionmaker()() as db:
        change = db.get(AaScheduleChange, change_id)
        assert change.applicant_id == case["uid"]
        assert change.teacher_key == "r0-assist-teacher"
        assert change.teacher_name == "正式任课教师"
        assert change.status == "SUBMITTED"
        assert db.get(AaScheduleItem, case["origins"]["own"]).status == "EFFECTIVE"
        workflow = db.get(WorkflowInstance, change.workflow_instance_id)
        assert workflow.applicant_id == case["uid"]
        assert workflow.status == "RUNNING"
        task = db.query(WorkflowTask).filter(WorkflowTask.instance_id == workflow.id).one()
        assert task.assignee_id and task.assignee_id != case["uid"]
        assert db.query(AffairsAuditTrail).filter(AffairsAuditTrail.biz_type == "AA_SCHEDULE_CHANGE",
            AffairsAuditTrail.biz_id == change_id, AffairsAuditTrail.operator == "学院教务own").count() == 1
    detail = client.get(f"{BASE}/{change_id}", headers=headers)
    assert detail.status_code == 200, detail.text
    assert detail.json()["data"]["canCancel"] is True
    ledger = client.get(BASE, headers=headers)
    assert any(int(row["changeId"]) == change_id for row in ledger.json()["data"]["items"])
    assert client.post(f"{BASE}/{change_id}/approve", headers=headers,
                       json={"expectedVersion": 0, "comment": "不允许自审"}).status_code == 403
    assert client.post(f"{BASE}/{change_id}/cancel", headers=case["headers"]["peer"], json={}).status_code == 403
    duplicate = client.post(BASE, headers=headers, json=body)
    assert duplicate.status_code == 409, duplicate.text
    cancelled = client.post(f"{BASE}/{change_id}/cancel", headers=headers, json={"reason": "申请内容需要重新核对"})
    assert cancelled.status_code == 200, cancelled.text
    with get_sessionmaker()() as db:
        assert db.get(AaScheduleChange, change_id).status == "CANCELLED"
        assert db.get(AaScheduleItem, case["origins"]["own"]).status == "EFFECTIVE"


@pytest.mark.parametrize("name", ["other", "unknown", "foreign", "deleted", "orphan"])
def test_college_assist_cannot_read_probe_or_submit_outside_valid_offering_scope(client, assist_case, name):
    headers = assist_case["headers"]["own"]
    body = _body(assist_case["origins"][name])
    before = _counts()
    assert client.get(f"{BASE}/origin-items/{body['originItemId']}", headers=headers).status_code == 403
    assert client.post(f"{BASE}/conflict-check", headers=headers, json=body).status_code == 403
    assert client.post(BASE, headers=headers, json=body).status_code == 403
    assert _counts() == before


@pytest.mark.parametrize("name", ["unscoped", "school"])
def test_college_assist_requires_college_scope_even_with_school_scope_claim(client, assist_case, name):
    before = _counts()
    response = client.post(BASE, headers=assist_case["headers"][name], json=_body(assist_case["origins"]["own"]))
    assert response.status_code == 403, response.text
    assert _counts() == before


def test_college_assist_rechecks_teacher_relation_at_submit(client, assist_case):
    from app.db.session import get_sessionmaker
    from app.models import AaTeachingClassTeacher

    case = assist_case
    headers = case["headers"]["own"]
    assert client.get(f"{BASE}/origin-items/{case['origins']['own']}", headers=headers).status_code == 200
    with get_sessionmaker()() as db:
        db.get(AaTeachingClassTeacher, case["relation"]).status = "INACTIVE"
        db.commit()
    before = _counts()
    result = client.post(BASE, headers=headers, json=_body(case["origins"]["own"]))
    assert result.status_code == 409, result.text
    assert _counts() == before
