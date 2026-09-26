"""V5 学校发布门禁：真实 MySQL、真实范围与正式 HTTP 命令。

培养方案、已确认教学任务是本测试的隔离初始事实；课表从创建、排课、
预发布到正式发布全部走现有接口。不得替换完整性、权限或学校门禁函数。
本文件只能由主控在独立测试库中串行执行，不用于日常沙箱清理。
"""
from __future__ import annotations

from datetime import datetime

import pytest

from tests.test_aa_schedule import BASE, TID, _hdr, _item


def _facts(client, *, mode="OFFERING_UNIT", shared_teacher=False):
    from app.db.session import get_sessionmaker
    from app.models import (
        AaClassroom, AaCourse, AaProgram, AaProgramBinding, AaProgramCourse,
        AaTeachingClass, AaTeachingClassTeacher, AaTeachingTask, AaTeachingTaskBatch,
        AaTimeSlot, College, Major, PlatformConfig, Role, RolePermission, SchoolClass, StaffAssignment, User,
    )
    from tests.support_academic_review_identity import _ensure_permission, seed_college_review_scope
    from tests.support_schedule_change_identity import seed_schedule_change_identity

    headers = _hdr(client, "school_admin01")
    response = client.post(f"{BASE}/terms", headers=headers, json={
        "yearCode": "2041-2042", "termNo": 1, "termName": "学校发布门禁学期",
        "startDate": "2041-09-01", "endDate": "2042-01-31", "teachingWeeks": 18,
    })
    assert response.status_code == 200, response.text
    term_id = int(response.json()["data"]["termId"])
    response = client.post(f"{BASE}/terms/{term_id}/publish", headers=headers)
    assert response.status_code == 200, response.text
    facts = {"termId": term_id, "mode": mode, "tasks": []}
    with get_sessionmaker()() as db:
        db.add(PlatformConfig(tenant_id=TID, config_type="ACAD_RULE", config_key="PUBLIC_SCHEDULE_MODE",
            config_json={"mode": mode}, enabled=True, status="ACTIVE"))
        db.add(AaTimeSlot(tenant_id=TID, slot_no=1, slot_name="第一节",
            start_time="08:00", end_time="08:45", enabled=True, status="ENABLED"))
        colleges = [College(tenant_id=TID, code=f"V5-GATE-{index}", college_name=f"发布门禁学院{index}",
            status="ACTIVE") for index in range(2)]
        db.add_all(colleges); db.flush()
        seed_college_review_scope(db, college_ids=[colleges[0].id])
        users = seed_schedule_change_identity(db, college_ids=[colleges[0].id])
        db.add(StaffAssignment(tenant_id=TID, user_id=users["school_admin01"], org_type="SCHOOL",
            org_node_id=TID, assignment_type="ACADEMIC_REVIEWER", is_primary=True,
            effective_at=datetime(2020, 1, 1), status="ACTIVE", source_type="MANUAL",
            reason="学校课表发布门禁真实责任岗位"))
        for role_code in ("SCHOOL_ADMIN", "COLLEGE_ADMIN"):
            role = db.query(Role).filter(Role.tenant_id == TID, Role.role_code == role_code).one()
            for code in ("academicAffairs.schedule.view", "academicAffairs.schedule.edit"):
                permission = _ensure_permission(db, code)
                if not db.query(RolePermission).filter(RolePermission.tenant_id == TID,
                    RolePermission.role_id == role.id, RolePermission.permission_id == permission.id).first():
                    db.add(RolePermission(tenant_id=TID, role_id=role.id,
                        permission_id=permission.id, status="ACTIVE"))
        teachers = [User(tenant_id=TID, login_name=f"v5_gate_teacher_{index}", real_name=f"发布测试教师{index}",
            user_type="TEACHER", password_hash="x", status="ACTIVE") for index in range(2)]
        db.add_all(teachers)
        for index in range(2):
            db.add(AaClassroom(tenant_id=TID, building_code="V5G", building_name="发布测试楼",
                room_code=str(index), room_name=f"发布测试教室{index}", capacity=100,
                room_type="LECTURE", allow_schedule=True, status="AVAILABLE"))
        db.flush()
        for index, college in enumerate(colleges):
            teacher = teachers[0 if shared_teacher else index]
            major = Major(tenant_id=TID, college_id=college.id, major_name=f"发布测试专业{index}", status="ACTIVE")
            db.add(major); db.flush()
            clazz = SchoolClass(tenant_id=TID, major_id=major.id, class_name=f"发布测试班{index}",
                grade="2041", class_status="NORMAL", status="ACTIVE")
            program = AaProgram(tenant_id=TID, major_id=major.id, grade_year="2041",
                program_name=f"发布测试培养方案{index}", series_key=f"V5-GATE-{index}", status="PUBLISHED")
            course = AaCourse(tenant_id=TID, course_code=f"V5-GATE-C{index}", course_name=f"发布测试课程{index}",
                owner_college_id=college.id, credit=1,
                category="PUBLIC_BASIC" if mode == "SCHOOL_CENTRALIZED" and index == 0 else "MAJOR_CORE")
            db.add_all([clazz, program, course]); db.flush()
            source = AaProgramCourse(tenant_id=TID, program_id=program.id, course_id=course.id,
                course_name=course.course_name, open_term_no=1, formation_mode="ADMIN_FIXED", credit_snapshot=1)
            batch = AaTeachingTaskBatch(tenant_id=TID, term_id=term_id, college_id=college.id,
                batch_name=f"发布测试教学任务{index}", status="APPROVED")
            db.add_all([source, batch]); db.flush()
            db.add(AaProgramBinding(tenant_id=TID, program_id=program.id, major_id=major.id, class_id=clazz.id,
                grade_year="2041", bound_at=datetime(2041, 8, 1), status="ACTIVE"))
            task = AaTeachingTask(tenant_id=TID, batch_id=batch.id, course_id=course.id,
                source_program_course_id=source.id, course_name=course.course_name, class_id=clazz.id,
                teaching_class_name=clazz.class_name, teacher_key=teacher.login_name, teacher_name=teacher.real_name,
                status="READY", weekly_hours=1, total_hours=18, start_week=1, end_week=18)
            db.add(task); db.flush()
            teaching_class = AaTeachingClass(tenant_id=TID, teaching_task_id=task.id, term_id=term_id,
                course_id=course.id, class_code=f"V5-GATE-TC{index}", class_name=clazz.class_name, status="ACTIVE")
            db.add(teaching_class); db.flush()
            db.add(AaTeachingClassTeacher(tenant_id=TID, teaching_class_id=teaching_class.id,
                teacher_id=teacher.id, teacher_key=teacher.login_name, teacher_name=teacher.real_name,
                role_type="PRIMARY", start_week=1, end_week=18, status="ACTIVE"))
            facts["tasks"].append({"taskId": str(task.id), "collegeId": str(college.id),
                "classId": str(clazz.id), "courseName": course.course_name, "className": clazz.class_name,
                "teacherKey": teacher.login_name, "teacherName": teacher.real_name})
        db.commit()
    facts["school"] = _hdr(client, "school_admin01")
    facts["college"] = _hdr(client, "college_admin01")
    _assert_task_reconciliation(facts)
    return facts


def _assert_task_reconciliation(facts):
    from app.core.context import get_tenant, set_tenant
    from app.db.session import get_sessionmaker
    from app.modules.academic_affairs.services import academic_affairs_archive_rule_evaluator as evaluator

    previous = get_tenant()
    set_tenant(TID)
    try:
        with get_sessionmaker()() as db:
            result = evaluator.evaluate_teaching_task(db, facts["termId"])
            assert result["result"] == "PASS", result
            evidence = next(row for row in result["evidence"] if row["type"] == "TASK_RECONCILIATION")
            assert evidence["expected"] == evidence["actual"] == 2
    finally:
        set_tenant(previous)


def _candidate(client, facts, index, *, weekday=None, room=None, add_item=True, pre_publish=True):
    task = facts["tasks"][index]
    college_id = None if facts["mode"] == "SCHOOL_CENTRALIZED" and index == 0 else task["collegeId"]
    response = client.post(f"{BASE}/schedule-batches", headers=facts["school"], json={
        "termId": str(facts["termId"]), "collegeId": college_id, "batchName": f"发布候选{index}",
    })
    assert response.status_code == 200, response.text
    batch_id = response.json()["data"]["batchId"]
    if add_item:
        response = _item(client, facts["school"], batch_id,
            **{key: value for key, value in task.items() if key != "collegeId"},
            weekday=weekday or index + 1, classroom=room or f"发布测试教室{index}")
        assert response.status_code == 200, response.text
    if pre_publish:
        response = client.post(f"{BASE}/schedule-batches/{batch_id}/pre-publish", headers=facts["school"])
        assert response.status_code == 200, response.text
        assert response.json()["data"]["status"] == "PRE_PUBLISHED"
    return str(batch_id)


def _summary(client, facts, batch_id):
    response = client.get(f"{BASE}/schedule-batches/{batch_id}/summary", headers=facts["school"])
    assert response.status_code == 200, response.text
    return response.json()["data"]


def _snapshot(facts):
    """失败发布不能留下正式头、业务发布流水、状态或成功审计的半截事实。"""
    from app.db.session import get_sessionmaker
    from app.models import AaScheduleBatch, AaSchedulePublish, AaScheduleScopeHead, AffairsAuditTrail

    with get_sessionmaker()() as db:
        batches = db.query(AaScheduleBatch).filter(AaScheduleBatch.tenant_id == TID,
            AaScheduleBatch.term_id == facts["termId"]).order_by(AaScheduleBatch.id).all()
        ids = [row.id for row in batches]
        return {
            "batches": [(row.id, row.status, row.publish_at) for row in batches],
            "heads": [(row.id, row.scope_type, row.scope_id, row.active_batch_id, row.version)
                for row in db.query(AaScheduleScopeHead).filter(AaScheduleScopeHead.tenant_id == TID,
                    AaScheduleScopeHead.term_id == facts["termId"]).order_by(AaScheduleScopeHead.id)],
            "publishes": [(row.id, row.batch_id, row.action, row.notified_count)
                for row in db.query(AaSchedulePublish).filter(AaSchedulePublish.tenant_id == TID,
                    AaSchedulePublish.term_id == facts["termId"]).order_by(AaSchedulePublish.id)],
            "audits": [(row.id, row.biz_id, row.action, row.detail)
                for row in db.query(AffairsAuditTrail).filter(AffairsAuditTrail.tenant_id == TID,
                    AffairsAuditTrail.biz_type == "AA_SCHEDULE_BATCH", AffairsAuditTrail.biz_id.in_(ids))
                    .order_by(AffairsAuditTrail.id)],
        }


def _assert_school_rejects(client, facts, batch_id):
    summary = _summary(client, facts, batch_id)
    assert summary["complete"] is True, summary  # 当前批次本身已经准备完成。
    assert summary["schoolGate"]["ready"] is False, summary
    assert summary["schoolGate"]["blockers"], summary
    before = _snapshot(facts)
    response = client.post(f"{BASE}/schedule-batches/{batch_id}/publish", headers=facts["school"])
    assert response.status_code == 409, response.text
    assert _snapshot(facts) == before


def test_school_publish_rejects_missing_public_candidate(client, db_mode):
    facts = _facts(client, mode="SCHOOL_CENTRALIZED")
    professional = _candidate(client, facts, 1)
    _assert_school_rejects(client, facts, professional)


@pytest.mark.parametrize("other_has_item", [True, False], ids=["other-college-draft", "other-college-missing-course"])
def test_school_publish_rejects_another_college_not_ready(client, db_mode, other_has_item):
    facts = _facts(client)
    ready = _candidate(client, facts, 0)
    _candidate(client, facts, 1, add_item=other_has_item, pre_publish=False)
    _assert_school_rejects(client, facts, ready)


@pytest.mark.parametrize("resource", ["teacher", "classroom"])
def test_school_publish_rejects_conflict_between_two_pre_published_candidates(client, db_mode, resource):
    facts = _facts(client, shared_teacher=resource == "teacher")
    first = _candidate(client, facts, 0, weekday=1)
    second = _candidate(client, facts, 1, weekday=1,
        room="发布测试教室0" if resource == "classroom" else None)
    # 两批分别预发布成功且内部无冲突，冲突只存在于尚未正式发布的不同范围之间。
    assert _summary(client, facts, second)["complete"] is True
    _assert_school_rejects(client, facts, first)


@pytest.mark.parametrize("mode", ["SCHOOL_CENTRALIZED", "OFFERING_UNIT"])
def test_all_required_scopes_ready_allows_school_publish_but_rejects_college(client, db_mode, mode):
    facts = _facts(client, mode=mode)
    batches = [_candidate(client, facts, index) for index in range(2)]
    assert all(_summary(client, facts, batch)["schoolGate"]["ready"] is True for batch in batches)
    college_batch = batches[1] if mode == "SCHOOL_CENTRALIZED" else batches[0]
    # 学院具备排课编辑权限；仍不得代替学校执行正式发布（不能只测无权限403）。
    if mode == "SCHOOL_CENTRALIZED":
        from app.db.session import get_sessionmaker
        from tests.support_academic_review_identity import seed_college_review_scope
        with get_sessionmaker()() as db:
            seed_college_review_scope(db, college_ids=[facts["tasks"][1]["collegeId"]]); db.commit()
        facts["college"] = _hdr(client, "college_admin01")
    before = _snapshot(facts)
    denied = client.post(f"{BASE}/schedule-batches/{college_batch}/publish", headers=facts["college"])
    assert denied.status_code == 403, denied.text
    assert _snapshot(facts) == before
    for batch_id in batches:
        response = client.post(f"{BASE}/schedule-batches/{batch_id}/publish", headers=facts["school"])
        assert response.status_code == 200, response.text
        assert response.json()["data"]["status"] == "PUBLISHED"
        readback = client.get(f"{BASE}/schedule-batches/{batch_id}", headers=facts["school"])
        assert readback.status_code == 200, readback.text
        assert readback.json()["data"]["status"] == "PUBLISHED"
        assert str(readback.json()["data"]["activeTruth"]["activeBatchId"]) == batch_id
    after = _snapshot(facts)
    assert {str(row[3]) for row in after["heads"]} == set(batches)
    assert len(after["publishes"]) == 2
    assert len([row for row in after["audits"] if row[2] == "PUBLISH"]) == 2


def test_expired_school_assignment_blocks_summary_and_publish_without_changing_candidates(client, db_mode):
    from datetime import timedelta
    from app.db.session import get_sessionmaker
    from app.models import StaffAssignment, User

    facts = _facts(client)
    batches = [_candidate(client, facts, index) for index in range(2)]
    assert _summary(client, facts, batches[0])["schoolGate"]["ready"] is True
    with get_sessionmaker()() as db:
        user = db.query(User).filter(User.tenant_id == TID, User.login_name == "school_admin01").one()
        assignment = db.query(StaffAssignment).filter(StaffAssignment.tenant_id == TID,
            StaffAssignment.user_id == user.id, StaffAssignment.org_type == "SCHOOL").one()
        assignment.expires_at = datetime.utcnow() - timedelta(seconds=1)
        db.commit()
    summary = _summary(client, facts, batches[0])
    assert summary["complete"] is True and summary["schoolGate"]["ready"] is False
    assert any(row["code"] == "SCHOOL_PUBLISHER_UNRESOLVED" for row in summary["schoolGate"]["blockers"])
    before = _snapshot(facts)
    denied = client.post(f"{BASE}/schedule-batches/{batches[0]}/publish", headers=facts["school"])
    assert denied.status_code == 403, denied.text
    assert _snapshot(facts) == before
