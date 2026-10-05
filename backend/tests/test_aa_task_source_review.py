"""重复来源核对：隔离 MySQL 正式接口；只读，不确认承接。"""
from __future__ import annotations

import pytest

from tests.test_aa_v5_school_schedule_gate import _facts
from tests.test_aa_schedule import BASE, TID


def _pair(client):
    from app.db.session import get_sessionmaker
    from app.models import (AaProgram, AaProgramBinding, AaProgramCourse, AaTeachingClass,
        AaTeachingClassMember, AaTeachingClassRosterVersion, AaTeachingClassTeacher,
        AaTeachingTask, AaTeachingTaskBatch, StudentProfile)
    from app.modules.academic_affairs.services.academic_affairs_teaching_class_core_service import _roster_hash

    facts = _facts(client)
    with get_sessionmaker()() as db:
        old = db.get(AaTeachingTask, int(facts["tasks"][0]["taskId"]))
        old.formation_mode = "ADMIN_FIXED"
        source = db.get(AaProgramCourse, old.source_program_course_id)
        program = db.get(AaProgram, source.program_id)
        successor = AaProgram(tenant_id=TID, major_id=program.major_id, grade_year=program.grade_year,
            program_name="后继来源核对方案", series_key=program.series_key,
            prev_version_id=program.id, version=2, status="ENABLED")
        db.add(successor); db.flush()
        next_source = AaProgramCourse(tenant_id=TID, program_id=successor.id, course_id=old.course_id,
            course_name=old.course_name, open_term_no=source.open_term_no,
            formation_mode="ADMIN_FIXED", credit_snapshot=source.credit_snapshot)
        batch = AaTeachingTaskBatch(tenant_id=TID, term_id=facts["termId"],
            college_id=int(facts["tasks"][0]["collegeId"]), batch_name="后继来源核对批次", status="APPROVED")
        db.add_all([next_source, batch]); db.flush()
        new = AaTeachingTask(tenant_id=TID, batch_id=batch.id, course_id=old.course_id, course_name=old.course_name,
            class_id=old.class_id, source_program_course_id=next_source.id, formation_mode="ADMIN_FIXED",
            teacher_key=old.teacher_key, teacher_name=old.teacher_name, status="READY",
            weekly_hours=old.weekly_hours, total_hours=old.total_hours,
            start_week=old.start_week, end_week=old.end_week, teaching_class_name=old.teaching_class_name)
        db.add(new); db.flush()
        binding = db.query(AaProgramBinding).filter(AaProgramBinding.program_id == program.id,
            AaProgramBinding.tenant_id == TID, AaProgramBinding.class_id == old.class_id).one()
        binding.status = "SUPERSEDED"
        db.add(AaProgramBinding(tenant_id=TID, program_id=successor.id, major_id=program.major_id,
            class_id=old.class_id, grade_year=program.grade_year, status="ACTIVE"))
        old_class = db.query(AaTeachingClass).filter(AaTeachingClass.tenant_id == TID,
            AaTeachingClass.teaching_task_id == old.id).one()
        teacher = db.query(AaTeachingClassTeacher).filter(AaTeachingClassTeacher.tenant_id == TID,
            AaTeachingClassTeacher.teaching_class_id == old_class.id).one()
        new.teacher_id = teacher.teacher_id
        db.add_all([StudentProfile(id=student_id, tenant_id=TID,
            student_no=f"SOURCE-REVIEW-{student_id}", real_name=f"来源核对虚构学生{student_id}",
            class_id=old.class_id, major_id=program.major_id, college_id=batch.college_id,
            status="ACTIVE") for student_id in (711, 712)])
        new_class = AaTeachingClass(tenant_id=TID, teaching_task_id=new.id, term_id=facts["termId"],
            course_id=old.course_id, class_code=old_class.class_code + "-NEXT", class_name=old_class.class_name,
            class_type="ADMIN", source_type="TEACHING_TASK", source_id=new.id, status="ACTIVE")
        db.add(new_class); db.flush()
        db.add(AaTeachingClassTeacher(tenant_id=TID, teaching_class_id=new_class.id,
            teacher_id=teacher.teacher_id, teacher_key=teacher.teacher_key,
            role_type="PRIMARY", start_week=old.start_week, end_week=old.end_week, status="ACTIVE"))
        for task, teaching_class in ((old, old_class), (new, new_class)):
            teaching_class.source_type = "TEACHING_TASK"
            teaching_class.source_id = task.id
            teaching_class.class_type = "ADMIN"
            teaching_class.roster_status = "LOCKED"
            version = AaTeachingClassRosterVersion(tenant_id=TID, teaching_class_id=teaching_class.id,
                version_no=1, source_type="ADMIN_CLASS", source_id=task.class_id,
                member_count=2, roster_hash=_roster_hash((711, 712)), status="LOCKED")
            db.add(version); db.flush()
            teaching_class.current_roster_version_id = version.id
            teaching_class.current_roster_version_no = 1
            for student_id in (711, 712):
                db.add(AaTeachingClassMember(tenant_id=TID, teaching_class_id=teaching_class.id,
                    roster_version_id=version.id, student_id=student_id,
                    source_type="ADMIN_CLASS", source_id=task.class_id, status="ACTIVE"))
        facts.update(oldId=str(old.id), newId=str(new.id), newSourceId=next_source.id, newClassId=new_class.id)
        db.commit()
    return facts


def _review(client, facts, *, headers=None, other_id=None):
    return client.get(f"{BASE}/teaching-tasks/{facts['oldId']}/source-review",
        headers=headers or facts["school"], params={"otherTaskId": other_id or facts["newId"]})


def test_proven_pair_is_checked_but_not_confirmed_and_does_not_write(client, db_mode):
    from app.db.session import get_sessionmaker
    from app.models import AaTeachingTask, AffairsAuditTrail
    facts = _pair(client)
    with get_sessionmaker()() as db:
        before = [(t.id, t.version, t.status, t.source_program_course_id, t.teacher_id)
            for t in db.query(AaTeachingTask).filter(AaTeachingTask.id.in_([int(facts['oldId']), int(facts['newId'])])).all()]
        audit_count = db.query(AffairsAuditTrail).filter(AffairsAuditTrail.tenant_id == TID).count()
    response = _review(client, facts)
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["status"] == "CHECKED", data
    assert data["reviewOnly"] is True
    assert "canConfirm" not in data
    assert data["taskIds"] == [facts["oldId"], facts["newId"]]
    assert all(row["teacherIdentityProven"] for row in data["tasks"])
    assert all(row["rosterCount"] == 2 for row in data["tasks"])
    assert all(row["status"] == "PASS" for row in data["checks"])
    with get_sessionmaker()() as db:
        after = [(t.id, t.version, t.status, t.source_program_course_id, t.teacher_id)
            for t in db.query(AaTeachingTask).filter(AaTeachingTask.id.in_([int(facts['oldId']), int(facts['newId'])])).all()]
        assert after == before
        assert db.query(AffairsAuditTrail).filter(AffairsAuditTrail.tenant_id == TID).count() == audit_count


@pytest.mark.parametrize("change,code", [
    ("formation_missing", "FORMATION"), ("formation_mismatch", "FORMATION"),
    ("hours", "HOURS"), ("window", "HOURS"), ("lineage", "LINEAGE"),
    ("teacher", "TEACHER"), ("roster", "ROSTER"), ("schedule", "SUCCESSOR_CONSUMPTION"),
    ("cycle", "LINEAGE"), ("binding", "BINDING"), ("class_term", "ROSTER"),
    ("teacher_history", "SUCCESSOR_PROJECTION"),
    ("missing_student", "ROSTER"), ("roster_hash", "ROSTER"),
])
def test_real_mismatch_or_unknown_blocks_source_review(client, db_mode, change, code):
    from app.db.session import get_sessionmaker
    from app.models import (AaProgram, AaProgramBinding, AaProgramCourse, AaScheduleBatch, AaScheduleItem,
        AaTeachingClass, AaTeachingClassMember, AaTeachingClassRosterVersion,
        AaTeachingTask, AffairsAuditTrail, StudentProfile)
    facts = _pair(client)
    with get_sessionmaker()() as db:
        new = db.get(AaTeachingTask, int(facts["newId"]))
        source = db.get(AaProgramCourse, facts["newSourceId"])
        if change == "formation_missing":
            new.formation_mode = source.formation_mode = None
        elif change == "formation_mismatch":
            new.formation_mode = source.formation_mode = "SELECTABLE"
        elif change == "hours": new.total_hours += 1
        elif change == "window": new.start_week = 2
        elif change == "lineage": db.get(AaProgram, source.program_id).prev_version_id = None
        elif change == "cycle":
            successor = db.get(AaProgram, source.program_id)
            db.get(AaProgram, successor.prev_version_id).prev_version_id = successor.id
        elif change == "binding":
            db.query(AaProgramBinding).filter(AaProgramBinding.program_id == source.program_id,
                AaProgramBinding.tenant_id == TID).one().status = "SUPERSEDED"
        elif change == "class_term": db.get(AaTeachingClass, facts["newClassId"]).term_id += 1
        elif change == "teacher_history":
            db.add(AffairsAuditTrail(tenant_id=TID, biz_type="AA_TEACHING_CLASS_TEACHER",
                biz_id=facts["newClassId"], action="TEACHER_RELATION_UPDATE",
                detail="隔离前置事实：正式任课曾调整后恢复同值"))
        elif change == "teacher": new.teacher_id = 999999999
        elif change == "roster":
            member = db.query(AaTeachingClassMember).filter(AaTeachingClassMember.teaching_class_id == facts["newClassId"]).first()
            member.student_id = 713
        elif change == "missing_student": db.get(StudentProfile, 711).is_deleted = True
        elif change == "roster_hash":
            clazz = db.get(AaTeachingClass, facts["newClassId"])
            db.get(AaTeachingClassRosterVersion, clazz.current_roster_version_id).roster_hash = "0" * 64
        elif change == "schedule":
            batch = AaScheduleBatch(tenant_id=TID, term_id=facts["termId"], batch_name="后继已消费课表", status="DRAFT")
            db.add(batch); db.flush()
            db.add(AaScheduleItem(tenant_id=TID, batch_id=batch.id, task_id=new.id,
                weekday=2, slot_no=1, start_week=1, end_week=18, week_parity="ALL", status="EFFECTIVE"))
        db.commit()
    response = _review(client, facts)
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["status"] == "BLOCKED", data
    assert any(row["code"] == code and row["status"] == "BLOCKED" for row in data["checks"]), data


def test_college_can_review_own_pair_but_not_other_college(client, db_mode):
    facts = _pair(client)
    assert _review(client, facts, headers=facts["college"]).status_code == 200
    response = _review(client, facts, headers=facts["college"], other_id=facts["tasks"][1]["taskId"])
    assert response.status_code == 403, response.text
    assert "后继来源核对方案" not in response.text


def test_missing_or_same_task_is_not_a_valid_pair(client, db_mode):
    facts = _pair(client)
    assert _review(client, facts, other_id="999999999").status_code == 404
    assert _review(client, facts, other_id=facts["oldId"]).status_code == 400


def test_foreign_tenant_task_cannot_leak_source_review(client, db_mode):
    from app.db.session import get_sessionmaker
    from app.models import AaTeachingTask
    facts = _pair(client)
    with get_sessionmaker()() as db:
        db.get(AaTeachingTask, int(facts["newId"])).tenant_id = TID + 1
        db.commit()
    response = _review(client, facts)
    assert response.status_code == 404, response.text
    assert "后继来源核对方案" not in response.text
