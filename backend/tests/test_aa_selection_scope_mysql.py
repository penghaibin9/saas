"""D6：Selection Final 读侧真实 MySQL 学院范围合同。

同一个选课批次故意同时挂软件学院/机械学院教学任务，验证学院账号不能因为
“看得到批次”就把另一个学院的课程、名单和统计聚合带出来。测试只消费既有
AaSelection* 事实与教学任务归属，不创建第二套选课事实。
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.core.exceptions import AppException
from app.modules.academic_affairs.services import academic_affairs_selection_read_service as read

TID = 1000000000000000001


def _seed_mixed_batch(db_mode):
    from app.db.session import get_sessionmaker
    from app.models import (
        AaCourse,
        AaSelectionBatch,
        AaSelectionCourse,
        AaSelectionRecord,
        AaTeachingTask,
        AaTeachingTaskBatch,
        AaTerm,
        College,
        Major,
        SchoolClass,
        StudentProfile,
    )

    db = get_sessionmaker()()
    try:
        term = AaTerm(
            tenant_id=TID,
            year_code="2098-2099",
            term_no=1,
            term_name="D6学院范围回归学期",
            teaching_weeks=18,
            status="PUBLISHED",
            is_current=False,
        )
        soft = College(tenant_id=TID, college_name="D6软件学院", status="ACTIVE")
        mech = College(tenant_id=TID, college_name="D6机械学院", status="ACTIVE")
        db.add_all([term, soft, mech])
        db.flush()

        soft_major = Major(
            tenant_id=TID, college_id=soft.id, major_name="D6软件技术", status="ACTIVE"
        )
        mech_major = Major(
            tenant_id=TID, college_id=mech.id, major_name="D6机械制造", status="ACTIVE"
        )
        db.add_all([soft_major, mech_major])
        db.flush()

        soft_class = SchoolClass(
            tenant_id=TID,
            major_id=soft_major.id,
            class_name="D6软件2401",
            grade="2024",
            status="ACTIVE",
        )
        mech_class = SchoolClass(
            tenant_id=TID,
            major_id=mech_major.id,
            class_name="D6机械2401",
            grade="2024",
            status="ACTIVE",
        )
        db.add_all([soft_class, mech_class])
        db.flush()

        soft_course = AaCourse(
            tenant_id=TID,
            course_code="D6SOFT01",
            course_name="D6软件学院选修",
            credit=2,
            owner_college_id=soft.id,
            status="ENABLED",
        )
        mech_course = AaCourse(
            tenant_id=TID,
            course_code="D6MECH01",
            course_name="D6机械学院选修",
            credit=2,
            owner_college_id=mech.id,
            status="ENABLED",
        )
        db.add_all([soft_course, mech_course])
        db.flush()

        soft_task_batch = AaTeachingTaskBatch(
            tenant_id=TID,
            term_id=term.id,
            batch_name="D6软件教学任务批次",
            college_id=soft.id,
            status="APPROVED",
        )
        mech_task_batch = AaTeachingTaskBatch(
            tenant_id=TID,
            term_id=term.id,
            batch_name="D6机械教学任务批次",
            college_id=mech.id,
            status="APPROVED",
        )
        db.add_all([soft_task_batch, mech_task_batch])
        db.flush()

        soft_task = AaTeachingTask(
            tenant_id=TID,
            batch_id=soft_task_batch.id,
            course_id=soft_course.id,
            course_code=soft_course.course_code,
            course_name=soft_course.course_name,
            class_id=soft_class.id,
            teaching_class_name=soft_class.class_name,
            teacher_key="d6_soft_teacher",
            teacher_name="D6软件教师",
            status="READY",
            weekly_hours=2,
            total_hours=36,
            start_week=1,
            end_week=18,
        )
        mech_task = AaTeachingTask(
            tenant_id=TID,
            batch_id=mech_task_batch.id,
            course_id=mech_course.id,
            course_code=mech_course.course_code,
            course_name=mech_course.course_name,
            class_id=mech_class.id,
            teaching_class_name=mech_class.class_name,
            teacher_key="d6_mech_teacher",
            teacher_name="D6机械教师",
            status="READY",
            weekly_hours=2,
            total_hours=36,
            start_week=1,
            end_week=18,
        )
        db.add_all([soft_task, mech_task])
        db.flush()

        batch = AaSelectionBatch(
            tenant_id=TID,
            term_id=term.id,
            batch_name="D6混合学院选课批次",
            status="OPEN",
        )
        db.add(batch)
        db.flush()

        soft_offer = AaSelectionCourse(
            tenant_id=TID,
            batch_id=batch.id,
            course_id=soft_course.id,
            teaching_task_id=soft_task.id,
            course_name=soft_course.course_name,
            capacity=50,
            min_capacity=1,
            selected_count=1,
            status="OPEN",
        )
        mech_offer = AaSelectionCourse(
            tenant_id=TID,
            batch_id=batch.id,
            course_id=mech_course.id,
            teaching_task_id=mech_task.id,
            course_name=mech_course.course_name,
            capacity=50,
            min_capacity=1,
            selected_count=1,
            status="OPEN",
        )
        db.add_all([soft_offer, mech_offer])
        db.flush()

        soft_student = StudentProfile(
            tenant_id=TID,
            student_no="D6SOFT2401",
            real_name="D6软件学生",
            college_id=soft.id,
            major_id=soft_major.id,
            class_id=soft_class.id,
            grade="2024",
            student_status="NORMAL",
            status="ACTIVE",
        )
        mech_student = StudentProfile(
            tenant_id=TID,
            student_no="D6MECH2401",
            real_name="D6机械学生",
            college_id=mech.id,
            major_id=mech_major.id,
            class_id=mech_class.id,
            grade="2024",
            student_status="NORMAL",
            status="ACTIVE",
        )
        db.add_all([soft_student, mech_student])
        db.flush()

        db.add_all([
            AaSelectionRecord(
                tenant_id=TID,
                batch_id=batch.id,
                selection_course_id=soft_offer.id,
                course_id=soft_course.id,
                student_id=soft_student.id,
                student_no=soft_student.student_no,
                student_name=soft_student.real_name,
                status="SELECTED",
            ),
            AaSelectionRecord(
                tenant_id=TID,
                batch_id=batch.id,
                selection_course_id=mech_offer.id,
                course_id=mech_course.id,
                student_id=mech_student.id,
                student_no=mech_student.student_no,
                student_name=mech_student.real_name,
                status="SELECTED",
            ),
        ])
        db.commit()
        return {
            "batch": int(batch.id),
            "soft_college": int(soft.id),
            "soft_class": int(soft_class.id),
            "soft_offer": int(soft_offer.id),
            "mech_offer": int(mech_offer.id),
        }
    finally:
        db.close()


def _ctx(scope_type, *, class_ids=(), college_ids=()):
    class_ids = {int(value) for value in class_ids}
    return SimpleNamespace(
        scope_type=scope_type,
        college_ids={int(value) for value in college_ids},
        allowed_class_ids=lambda _db: set(class_ids) if scope_type == "COLLEGE" else None,
    )


def _install_ctx(monkeypatch, ctx):
    monkeypatch.setattr(read._core, "_tid", lambda: TID)
    monkeypatch.setattr(read._core, "_ctx", lambda _user, _db: ctx)


def test_college_scope_filters_mixed_batch_courses_and_stats(db_mode, monkeypatch):
    ids = _seed_mixed_batch(db_mode)
    _install_ctx(
        monkeypatch,
        _ctx(
            "COLLEGE",
            class_ids=[ids["soft_class"]],
            college_ids=[ids["soft_college"]],
        ),
    )

    courses, total = read.list_courses({}, ids["batch"], 1, 50)
    assert total == 1
    assert [int(row["selectionCourseId"]) for row in courses] == [ids["soft_offer"]]

    stats = read.batch_stats({}, ids["batch"])
    assert stats["courseCount"] == 1
    assert stats["totalCapacity"] == 50
    assert stats["totalSelected"] == 1
    assert stats["recordCount"] == 1


def test_college_scope_denies_other_college_roster_in_same_visible_batch(db_mode, monkeypatch):
    ids = _seed_mixed_batch(db_mode)
    _install_ctx(
        monkeypatch,
        _ctx(
            "COLLEGE",
            class_ids=[ids["soft_class"]],
            college_ids=[ids["soft_college"]],
        ),
    )

    with pytest.raises(AppException) as exc:
        read.course_roster({}, ids["mech_offer"], 1, 50)
    assert exc.value.code == "NO_DATA_SCOPE"
    assert exc.value.http_status == 403


def test_tenant_all_scope_sees_both_courses_in_mixed_batch(db_mode, monkeypatch):
    ids = _seed_mixed_batch(db_mode)
    _install_ctx(monkeypatch, _ctx("TENANT_ALL"))

    courses, total = read.list_courses({}, ids["batch"], 1, 50)
    assert total == 2
    assert {int(row["selectionCourseId"]) for row in courses} == {
        ids["soft_offer"], ids["mech_offer"]
    }


def test_college_scope_without_config_fails_closed(db_mode, monkeypatch):
    ids = _seed_mixed_batch(db_mode)
    _install_ctx(monkeypatch, _ctx("COLLEGE"))

    with pytest.raises(AppException) as exc:
        read.list_courses({}, ids["batch"], 1, 50)
    assert exc.value.code == "NO_DATA_SCOPE"
    assert exc.value.http_status == 403
