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


def _assert_task_reconciliation(facts, expected_count=2):
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
            assert evidence["expected"] == evidence["actual"] == expected_count
    finally:
        set_tenant(previous)


def _candidate(client, facts, index, *, weekday=None, room=None, add_item=True, pre_publish=True, name=None):
    task = facts["tasks"][index]
    college_id = None if facts["mode"] == "SCHOOL_CENTRALIZED" and index == 0 else task["collegeId"]
    response = client.post(f"{BASE}/schedule-batches", headers=facts["school"], json={
        "termId": str(facts["termId"]), "collegeId": college_id, "batchName": name or f"发布候选{index}",
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


@pytest.mark.parametrize("cross_batch_college", [False, True], ids=["same-college", "different-batch-college"])
def test_duplicate_ready_tasks_require_source_review_even_when_both_fully_scheduled(client, db_mode, cross_batch_college):
    from app.db.session import get_sessionmaker
    from app.models import AaTeachingClass, AaTeachingClassTeacher, AaTeachingTask, AaTeachingTaskBatch

    facts = _facts(client)
    batch_id = _candidate(client, facts, 0, pre_publish=False)
    original_fact = facts["tasks"][0]
    # 隔离回归初始事实：复现旧数据中的同课程同班跨批次重复任务。
    with get_sessionmaker()() as db:
        original = db.get(AaTeachingTask, int(original_fact["taskId"]))
        duplicate_batch = AaTeachingTaskBatch(tenant_id=TID, term_id=facts["termId"],
            college_id=int(facts["tasks"][1]["collegeId"] if cross_batch_college else original_fact["collegeId"]),
            batch_name="重复来源回归批次", status="APPROVED")
        db.add(duplicate_batch); db.flush()
        duplicate = AaTeachingTask(tenant_id=TID, batch_id=duplicate_batch.id,
            course_id=original.course_id, source_program_course_id=original.source_program_course_id,
            class_id=original.class_id, course_name=original.course_name,
            teacher_key=original.teacher_key, teacher_name=original.teacher_name,
            status="READY", weekly_hours=1, total_hours=18, start_week=1, end_week=18)
        db.add(duplicate); db.flush()
        teaching_class = AaTeachingClass(tenant_id=TID, teaching_task_id=duplicate.id,
            term_id=facts["termId"], course_id=duplicate.course_id,
            class_code="V5-DUPLICATE-TC", class_name="重复来源回归教学班", status="ACTIVE")
        db.add(teaching_class); db.flush()
        original_class = db.query(AaTeachingClass).filter(AaTeachingClass.tenant_id == TID,
            AaTeachingClass.teaching_task_id == original.id).one()
        relation = db.query(AaTeachingClassTeacher).filter(AaTeachingClassTeacher.tenant_id == TID,
            AaTeachingClassTeacher.teaching_class_id == original_class.id).one()
        db.add(AaTeachingClassTeacher(tenant_id=TID, teaching_class_id=teaching_class.id,
            teacher_id=relation.teacher_id, teacher_key=relation.teacher_key, teacher_name=relation.teacher_name,
            role_type="PRIMARY", start_week=1, end_week=18, status="ACTIVE"))
        duplicate_id = str(duplicate.id)
        db.commit()
    response = _item(client, facts["school"], batch_id,
        **{key: value for key, value in {**original_fact, "taskId": duplicate_id}.items() if key != "collegeId"},
        weekday=3, classroom="发布测试教室0")
    assert response.status_code == 200, response.text
    summary = _summary(client, facts, batch_id)
    assert summary["scheduledContactHours"] == summary["expectedContactHours"] == 36
    assert summary["missingContactHours"] == summary["excessContactHours"] == 0
    assert summary["complete"] is False and summary["canPrePublish"] is False
    assert summary["duplicateTaskGroupCount"] == 1
    assert {row["taskId"] for row in summary["taskQueue"]} == {original_fact["taskId"], duplicate_id}
    assert len(summary["taskQueue"]) == 2
    assert all(row["issueType"] == "SOURCE_CONFLICT" and row["canSchedule"] is False for row in summary["taskQueue"])
    assert summary["workflow"]["nextAction"]["code"] == "TEACHING_TASKS"
    before = _snapshot(facts)
    response = client.post(f"{BASE}/schedule-batches/{batch_id}/pre-publish", headers=facts["school"])
    assert response.status_code == 409, response.text
    assert response.json()["details"]["duplicateTaskGroupCount"] == 1
    assert _snapshot(facts) == before


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


def test_other_scope_draft_cannot_displace_current_formal_schedule(client, db_mode):
    from app.db.session import get_sessionmaker
    from app.models import AaScheduleItem

    facts = _facts(client, shared_teacher=True)
    originals = [_candidate(client, facts, index) for index in range(2)]
    for original in originals:
        response = client.post(f"{BASE}/schedule-batches/{original}/publish", headers=facts["school"])
        assert response.status_code == 200, response.text
    response = client.post(f"{BASE}/schedule-batches", headers=facts["school"], json={
        "termId": str(facts["termId"]), "collegeId": facts["tasks"][1]["collegeId"],
        "batchName": "尚未纳入发布的另院试验草稿",
    })
    assert response.status_code == 200, response.text
    unrelated = response.json()["data"]["batchId"]
    response = client.post(f"{BASE}/schedule-batches/{originals[0]}/correction-draft",
        headers=facts["school"], json={"reason": "隔离回归：保留原课位核验本院换版"})
    assert response.status_code == 200, response.text
    correction = response.json()["data"]["batchId"]
    response = client.post(f"{BASE}/schedule-batches/{correction}/pre-publish", headers=facts["school"])
    assert response.status_code == 200, response.text
    summary = _summary(client, facts, correction)
    assert summary["schoolGate"]["ready"] is True, summary
    assert set(summary["schoolGate"]["requiredBatchIds"]) == {str(correction), originals[1]}
    with get_sessionmaker()() as db:
        own_item = db.query(AaScheduleItem).filter(AaScheduleItem.tenant_id == TID,
            AaScheduleItem.batch_id == int(correction), AaScheduleItem.status == "EFFECTIVE").one()
        own_item_id = own_item.id
    preflight = client.post(f"{BASE}/schedule-items/{own_item_id}/move-preflight",
        headers=facts["school"], json={"weekday": 2, "slotNo": 1})
    assert preflight.status_code == 200, preflight.text
    assert preflight.json()["data"]["allowed"] is False
    assert preflight.json()["data"]["conflict"]["type"] == "TEACHER"
    response = client.post(f"{BASE}/schedule-batches/{correction}/publish", headers=facts["school"])
    assert response.status_code == 200, response.text
    other = client.get(f"{BASE}/schedule-batches/{originals[1]}", headers=facts["school"]).json()["data"]
    assert str(other["activeTruth"]["activeBatchId"]) == originals[1]
    draft = client.get(f"{BASE}/schedule-batches/{unrelated}", headers=facts["school"]).json()["data"]
    assert draft["status"] == "DRAFT"


def test_unresolved_initial_scope_candidates_reject_without_guessing_latest(client, db_mode):
    facts = _facts(client)
    first = _candidate(client, facts, 0)
    _candidate(client, facts, 1)
    _candidate(client, facts, 1, add_item=False, pre_publish=False, name="无正式头的第二份待定版本")
    before = _snapshot(facts)
    response = client.post(f"{BASE}/schedule-batches/{first}/publish", headers=facts["school"])
    assert response.status_code == 409, response.text
    assert "多个待定课表版本" in response.json()["message"]
    assert _snapshot(facts) == before


def test_invalid_other_formal_head_cannot_fall_back_to_draft(client, db_mode):
    from app.db.session import get_sessionmaker
    from app.models import AaScheduleScopeHead

    facts = _facts(client)
    originals = [_candidate(client, facts, index) for index in range(2)]
    for original in originals:
        response = client.post(f"{BASE}/schedule-batches/{original}/publish", headers=facts["school"])
        assert response.status_code == 200, response.text
    _candidate(client, facts, 1, name="另一学院未关联的后继候选")
    first = _candidate(client, facts, 0, name="本院精确请求后继候选")
    with get_sessionmaker()() as db:
        # 隔离初始异常：另一学院正式头错误指向本院批次，不能把它当作“没有正式版”。
        head = db.query(AaScheduleScopeHead).filter(AaScheduleScopeHead.tenant_id == TID,
            AaScheduleScopeHead.term_id == facts["termId"],
            AaScheduleScopeHead.scope_id == int(facts["tasks"][1]["collegeId"])).one()
        head.active_batch_id = int(originals[0]); db.commit()
    before = _snapshot(facts)
    response = client.post(f"{BASE}/schedule-batches/{first}/publish", headers=facts["school"])
    assert response.status_code == 409, response.text
    assert "当前正式课表依据异常" in response.json()["message"]
    assert _snapshot(facts) == before


def _historical_formal(facts, *, no_auto=True, college=False, defect=None):
    """隔离初始事实：已发布历史课位保留，非本轮应排任务仍占用全校资源。"""
    from app.db.session import get_sessionmaker
    from app.models import AaClassroom, AaScheduleBatch, AaScheduleItem, AaScheduleScopeHead, AaTeachingTask

    first = facts["tasks"][0]
    with get_sessionmaker()() as db:
        task = db.get(AaTeachingTask, int(first["taskId"]))
        task.no_auto_schedule = no_auto
        batch = AaScheduleBatch(tenant_id=TID, term_id=facts["termId"],
            college_id=int(first["collegeId"]) if college else None,
            batch_name="保留历史正式课位", status="PUBLISHED", publish_at=datetime(2041, 9, 1))
        db.add(batch); db.flush()
        room = db.query(AaClassroom).filter(AaClassroom.tenant_id == TID,
            AaClassroom.room_name == "发布测试教室0").one()
        db.add(AaScheduleItem(tenant_id=TID, batch_id=batch.id,
            task_id=None if defect == "orphan" else int(facts["tasks"][1]["taskId"])
                if defect == "out-of-scope" else task.id,
            course_id=task.course_id, course_name=task.course_name,
            class_id=task.class_id, class_name=first["className"],
            teacher_key=task.teacher_key, teacher_name=task.teacher_name,
            weekday=2 if defect == "resource" else 1, slot_no=1,
            start_week=1, end_week=17 if defect == "incomplete" else 18, week_parity="ALL",
            classroom_id=room.id, classroom_text=room.room_name, status="EFFECTIVE",
            objection_status="PENDING" if defect == "objection" else None))
        db.add(AaScheduleScopeHead(tenant_id=TID, term_id=facts["termId"],
            scope_type="COLLEGE" if college else "SCHOOL",
            scope_id=int(first["collegeId"]) if college else 0,
            active_batch_id=batch.id, version=1, published_at=datetime(2041, 9, 1)))
        batch_id = str(batch.id)
        db.commit()
    return batch_id


@pytest.mark.parametrize("no_auto", [False, True], ids=["actual-current-subset", "historical-no-auto"])
def test_school_formal_coverage_uses_actual_tasks_without_losing_old_items(client, db_mode, no_auto):
    facts = _facts(client, mode="HYBRID")
    current = _candidate(client, facts, 1)
    historical = _historical_formal(facts, no_auto=no_auto)
    summary = _summary(client, facts, current)
    assert summary["schoolGate"]["ready"] is True, summary
    assert set(summary["schoolGate"]["requiredBatchIds"]) == ({current} if no_auto else {current, historical})
    response = client.post(f"{BASE}/schedule-batches/{current}/publish", headers=facts["school"])
    assert response.status_code == 200, response.text
    readback = client.get(f"{BASE}/schedule-batches/{historical}", headers=facts["school"])
    assert readback.status_code == 200, readback.text
    assert readback.json()["data"]["status"] == "PUBLISHED"
    assert str(readback.json()["data"]["activeTruth"]["activeBatchId"]) == historical


@pytest.mark.parametrize("defect,code", [
    ("resource", "SCHOOL_FORMAL_CONFLICT"), ("objection", "SCHOOL_OBJECTIONS_PENDING"),
    ("orphan", "SCHOOL_UNIT_NOT_READY"), ("out-of-scope", "SCHOOL_UNIT_NOT_READY"),
    ("incomplete", "SCHOOL_UNIT_NOT_READY"),
])
def test_other_formal_items_cannot_escape_checks_by_leaving_required_tasks(client, db_mode, defect, code):
    facts = _facts(client, mode="HYBRID", shared_teacher=defect == "resource")
    current = _candidate(client, facts, 1)
    _historical_formal(facts, no_auto=defect != "incomplete", college=defect == "out-of-scope", defect=defect)
    summary = _summary(client, facts, current)
    assert summary["complete"] is True, summary
    assert summary["schoolGate"]["ready"] is False, summary
    assert code in {row["code"] for row in summary["schoolGate"]["blockers"]}, summary
    if defect == "resource":
        assert summary["schoolGate"]["hardConflicts"] == 1
        assert summary["schoolGate"]["formalHardConflicts"] == 1
    before = _snapshot(facts)
    response = client.post(f"{BASE}/schedule-batches/{current}/publish", headers=facts["school"])
    assert response.status_code == 409, response.text
    assert _snapshot(facts) == before


def _append_approved_tasks(facts):
    """隔离新增前置事实：两院均已有真实方案来源的新批准任务，不替换门禁。"""
    from app.db.session import get_sessionmaker
    from app.models import AaCourse, AaProgramCourse, AaTeachingClass, AaTeachingClassTeacher, AaTeachingTask, User

    with get_sessionmaker()() as db:
        for index, fact in enumerate(facts["tasks"][:2]):
            original = db.get(AaTeachingTask, int(fact["taskId"]))
            source = db.get(AaProgramCourse, original.source_program_course_id)
            course = AaCourse(tenant_id=TID, course_code=f"V5-NEW-{index}",
                course_name=f"新增接力课程{index}", owner_college_id=int(fact["collegeId"]),
                credit=1, category="MAJOR_CORE", status="ENABLED")
            db.add(course); db.flush()
            added_source = AaProgramCourse(tenant_id=TID, program_id=source.program_id,
                course_id=course.id, course_name=course.course_name, open_term_no=1,
                formation_mode="ADMIN_FIXED", credit_snapshot=1)
            db.add(added_source); db.flush()
            task = AaTeachingTask(tenant_id=TID, batch_id=original.batch_id,
                course_id=course.id, source_program_course_id=added_source.id, class_id=original.class_id,
                course_name=course.course_name, teacher_key=original.teacher_key,
                teacher_name=original.teacher_name, status="READY", weekly_hours=1,
                total_hours=18, start_week=1, end_week=18)
            db.add(task); db.flush()
            teaching_class = AaTeachingClass(tenant_id=TID, teaching_task_id=task.id,
                term_id=facts["termId"], course_id=course.id, class_code=f"V5-NEW-TC-{index}",
                class_name=fact["className"], status="ACTIVE")
            db.add(teaching_class); db.flush()
            teacher = db.query(User).filter(User.tenant_id == TID, User.login_name == task.teacher_key).one()
            db.add(AaTeachingClassTeacher(tenant_id=TID, teaching_class_id=teaching_class.id,
                teacher_id=teacher.id, teacher_key=teacher.login_name, teacher_name=teacher.real_name,
                role_type="PRIMARY", start_week=1, end_week=18, status="ACTIVE"))
            facts["tasks"].append({**fact, "taskId": str(task.id), "courseName": course.course_name})
        db.commit()
    _assert_task_reconciliation(facts, expected_count=4)


def _prepared_corrections(client, facts, originals):
    corrections = []
    for index, original in enumerate(originals):
        response = client.post(f"{BASE}/schedule-batches/{original}/correction-draft",
            headers=facts["school"], json={"reason": "隔离回归：两院正式版本协同纠错"})
        assert response.status_code == 200, response.text
        correction = str(response.json()["data"]["batchId"])
        if len(facts["tasks"]) > 2:
            task = facts["tasks"][index + 2]
            response = _item(client, facts["school"], correction,
                **{key: value for key, value in task.items() if key != "collegeId"},
                weekday=index + 3, classroom=f"发布测试教室{index}")
            assert response.status_code == 200, response.text
        response = client.post(f"{BASE}/schedule-batches/{correction}/pre-publish", headers=facts["school"])
        assert response.status_code == 200, response.text
        corrections.append(correction)
    return corrections


def test_two_colleges_with_new_tasks_can_publish_linked_corrections_in_safe_order(client, db_mode):
    facts = _facts(client)
    originals = [_candidate(client, facts, index) for index in range(2)]
    for original in originals:
        response = client.post(f"{BASE}/schedule-batches/{original}/publish", headers=facts["school"])
        assert response.status_code == 200, response.text
    _append_approved_tasks(facts)
    corrections = _prepared_corrections(client, facts, originals)
    for correction in corrections:
        summary = _summary(client, facts, correction)
        assert summary["schoolGate"]["ready"] is True, summary
        assert set(summary["schoolGate"]["requiredBatchIds"]) == set(corrections)
    response = client.post(f"{BASE}/schedule-batches/{corrections[0]}/publish", headers=facts["school"])
    assert response.status_code == 200, response.text
    other = client.get(f"{BASE}/schedule-batches/{originals[1]}", headers=facts["school"]).json()["data"]
    assert str(other["activeTruth"]["activeBatchId"]) == originals[1]
    response = client.post(f"{BASE}/schedule-batches/{corrections[1]}/publish", headers=facts["school"])
    assert response.status_code == 200, response.text
    assert {str(row[3]) for row in _snapshot(facts)["heads"]} == set(corrections)
    for original in originals:
        readback = client.get(f"{BASE}/schedule-batches/{original}", headers=facts["school"])
        assert readback.json()["data"]["status"] == "SUPERSEDED"


@pytest.mark.parametrize("defect", ["multiple", "mismatched", "old-resource", "old-incomplete"])
def test_linked_correction_selection_rejects_ambiguous_versions_and_live_resource_conflict(client, db_mode, defect):
    from app.db.session import get_sessionmaker
    from app.models import AaScheduleBatch, AaScheduleItem

    facts = _facts(client, shared_teacher=defect == "old-resource")
    originals = [_candidate(client, facts, index) for index in range(2)]
    for original in originals:
        response = client.post(f"{BASE}/schedule-batches/{original}/publish", headers=facts["school"])
        assert response.status_code == 200, response.text
    corrections = _prepared_corrections(client, facts, originals)
    with get_sessionmaker()() as db:
        # 隔离异常前置：不是正常办理成功证据，最终命令必须拒绝且无副作用。
        if defect == "multiple":
            db.add(AaScheduleBatch(tenant_id=TID, term_id=facts["termId"],
                college_id=int(facts["tasks"][1]["collegeId"]), batch_name="重复关联预发布版本",
                status="PRE_PUBLISHED", supersedes_batch_id=int(originals[1])))
        elif defect == "mismatched":
            db.get(AaScheduleBatch, int(corrections[1])).supersedes_batch_id = int(originals[0])
        elif defect == "old-incomplete":
            old_item = db.query(AaScheduleItem).filter(AaScheduleItem.tenant_id == TID,
                AaScheduleItem.batch_id == int(originals[1]), AaScheduleItem.status == "EFFECTIVE").one()
            old_item.end_week = 17
        else:
            for index, correction in enumerate(corrections):
                item = db.query(AaScheduleItem).filter(AaScheduleItem.tenant_id == TID,
                    AaScheduleItem.batch_id == int(correction), AaScheduleItem.status == "EFFECTIVE").one()
                item.weekday = index + 2
        db.commit()
    if defect == "old-resource":
        summary = _summary(client, facts, corrections[0])
        assert summary["complete"] is True
        assert summary["schoolGate"]["hardConflicts"] == 0
        assert summary["schoolGate"]["formalHardConflicts"] == 1
        assert any(row["code"] == "SCHOOL_FORMAL_CONFLICT" for row in summary["schoolGate"]["blockers"])
    elif defect == "old-incomplete":
        summary = _summary(client, facts, corrections[0])
        assert summary["complete"] is True
        assert summary["schoolGate"]["ready"] is False
        assert any(row["code"] == "SCHOOL_UNIT_NOT_READY" for row in summary["schoolGate"]["blockers"])
    before = _snapshot(facts)
    response = client.post(f"{BASE}/schedule-batches/{corrections[0]}/publish", headers=facts["school"])
    assert response.status_code == 409, response.text
    expected = "多个待定课表版本" if defect == "multiple" else "关联不一致" if defect == "mismatched" else "漏排" if defect == "old-incomplete" else "正式课表"
    assert expected in response.json()["message"]
    assert _snapshot(facts) == before
