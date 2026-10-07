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


@pytest.mark.parametrize("scope_case", ["college_own", "college_other", "college_empty", "teacher_own", "teacher_other", "tenant_all", "unknown"])
def test_public_round_list_enforces_the_installed_selection_scope(db_mode, monkeypatch, scope_case):
    import importlib

    from app.db.session import get_sessionmaker
    from app.models import AaSelectionBatch, AaSelectionCourse, AaSelectionRound, AaTeachingTask
    from app.modules.academic_affairs.services import academic_affairs_selection_round_service as rounds

    ids = _seed_mixed_batch(db_mode)
    db = get_sessionmaker()()
    try:
        original = db.get(AaSelectionBatch, ids["batch"])
        other_offer = db.get(AaSelectionCourse, ids["mech_offer"])
        other_task = db.get(AaTeachingTask, other_offer.teaching_task_id)
        other_class_id = int(other_task.class_id)
        other_batch = AaSelectionBatch(
            tenant_id=TID, term_id=original.term_id, batch_name="D6外院独占轮次批次", status="OPEN",
        )
        db.add(other_batch)
        db.flush()
        db.add(AaSelectionCourse(
            tenant_id=TID, batch_id=other_batch.id, course_id=other_offer.course_id,
            teaching_task_id=other_offer.teaching_task_id, course_name=other_offer.course_name,
            capacity=50, min_capacity=1, selected_count=0, status="OPEN",
        ))
        own_round = AaSelectionRound(
            tenant_id=TID, batch_id=ids["batch"], round_no=1, round_name="D6混合批次轮次", status="OPEN",
        )
        other_round = AaSelectionRound(
            tenant_id=TID, batch_id=other_batch.id, round_no=1, round_name="D6外院轮次", status="OPEN",
        )
        db.add_all([own_round, other_round])
        db.flush()
        other_batch_id = int(other_batch.id)
        expected_round_id = int(own_round.id)
        db.commit()
    finally:
        db.close()

    if scope_case == "tenant_all":
        ctx = _ctx("TENANT_ALL")
    elif scope_case == "college_empty":
        ctx = _ctx("COLLEGE")
    elif scope_case == "unknown":
        ctx = _ctx("NONE")
    else:
        ctx = _ctx("COLLEGE", class_ids=[ids["soft_class"]], college_ids=[ids["soft_college"]])
        if scope_case.startswith("teacher_"):
            # A coincidental class grant must not make another teacher's batch visible.
            ctx = _ctx("COLLEGE", class_ids=[ids["soft_class"], other_class_id])
            ctx.role_codes = {"ACADEMIC_TEACHER"}
            ctx.user_id = "d6_soft_teacher"
            ctx.login_name = "d6_soft_teacher"
    _install_ctx(monkeypatch, ctx)
    round_core = importlib.import_module(
        "app.modules.academic_affairs.services.academic_affairs_selection_round_core_service"
    )
    monkeypatch.setattr(round_core, "_tid", lambda: TID)
    monkeypatch.setattr(round_core, "_ctx", lambda _user, _db: ctx)
    batch_id = other_batch_id if scope_case.endswith("_other") else ids["batch"]
    if scope_case in {"college_other", "college_empty", "teacher_other", "unknown"}:
        with pytest.raises(AppException) as exc:
            rounds.list_rounds({}, batch_id)
        assert exc.value.code == "NO_DATA_SCOPE"
        assert exc.value.http_status == 403
    else:
        result = rounds.list_rounds({}, batch_id)
        assert [int(row["roundId"]) for row in result] == [expected_round_id]
        assert all(int(row["batchId"]) == batch_id for row in result)
