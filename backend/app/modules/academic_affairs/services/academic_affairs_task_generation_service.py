"""教学任务批次生成器。

只负责根据学期时间轴、已启用方案、方案绑定和行政班生成本学期应开任务；
不覆盖公开 Service，不管理工作台状态机，也不建立第二套执行计划事实。
"""
from __future__ import annotations

import logging
import math
import re
from datetime import datetime

from sqlalchemy import select

from app.core.exceptions import AppException
from app.services.db_service import _tid, session

from . import academic_affairs_task_core_service as core

_LOG = logging.getLogger(__name__)
_FALLBACK_WEEKS = 18
_MIN_WEEKS = 1
_MAX_WEEKS = 30
_MAX_PROGRAM_TERM = 20


def _bounded(value):
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return number if _MIN_WEEKS <= number <= _MAX_WEEKS else None


def _year_number(value):
    match = re.search(r"(19|20)\d{2}", str(value or ""))
    return int(match.group(0)) if match else None


def resolve_class_semester(term, school_class):
    academic_year = _year_number(getattr(term, "year_code", None))
    admission_year = _year_number(getattr(school_class, "grade", None))
    try:
        term_no = int(getattr(term, "term_no", None))
    except (TypeError, ValueError):
        return None
    if academic_year is None or admission_year is None or term_no not in {1, 2}:
        return None
    semester = (academic_year - admission_year) * 2 + term_no
    return semester if 1 <= semester <= _MAX_PROGRAM_TERM else None


def resolve_teaching_weeks(db, term_id):
    """返回 ``(教学周数, 来源)``，18周仅作为有告警的历史兼容兜底。"""
    from app.models import AaCalendarEvent, AaTerm

    term = db.query(AaTerm).filter(
        AaTerm.id == int(term_id),
        AaTerm.tenant_id == _tid(),
        AaTerm.is_deleted.is_(False),
    ).first()
    if not term:
        raise AppException("VALIDATION_ERROR", "学期不存在，无法生成教学任务")
    configured = _bounded(term.teaching_weeks)
    if configured:
        return configured, "TERM_TEACHING_WEEKS"
    exam_start = _bounded(term.exam_week_start)
    if exam_start and exam_start > 1:
        return exam_start - 1, "TERM_EXAM_WEEK_START"
    if term.start_date:
        events = db.query(AaCalendarEvent).filter(
            AaCalendarEvent.tenant_id == _tid(),
            AaCalendarEvent.term_id == int(term_id),
            AaCalendarEvent.event_type == "TEACHING",
            AaCalendarEvent.is_deleted.is_(False),
        ).all()
        teaching_ends = [event.end_date or event.start_date for event in events if event.end_date or event.start_date]
        if teaching_ends:
            weeks = _bounded(math.ceil(((max(teaching_ends) - term.start_date).days + 1) / 7))
            if weeks:
                return weeks, "CALENDAR_TEACHING_EVENTS"
    if term.start_date and term.end_date and term.end_date >= term.start_date:
        weeks = _bounded(math.ceil(((term.end_date - term.start_date).days + 1) / 7))
        if weeks:
            return weeks, "TERM_DATE_RANGE"
    _LOG.warning("term %s has no reliable teaching-week configuration; fallback=%s", term_id, _FALLBACK_WEEKS)
    return _FALLBACK_WEEKS, "LEGACY_FALLBACK_18"


def generate_batch_tx(db, body, user) -> dict:
    term_id = int(body.termId)
    college_id = int(body.collegeId) if getattr(body, "collegeId", None) else None

    from app.models import (
        AaCourse, AaProgram, AaProgramBinding, AaProgramCourse, AaTeachingTask,
        AaTeachingTaskBatch, AaTerm, SchoolClass,
    )
    from app.modules.academic_affairs.services.academic_affairs_archive_service import guard_term_writable
    from app.modules.academic_affairs.services.academic_affairs_stats_service import _resolve_scope, _validate_college_param

    guard_term_writable(db, term_id)
    term = db.get(AaTerm, term_id)
    if not term or term.is_deleted or term.tenant_id != _tid():
        raise AppException("VALIDATION_ERROR", "学期不存在，无法生成教学任务")
    teaching_weeks, week_source = resolve_teaching_weeks(db, term_id)
    scope = _resolve_scope(user, db)
    _validate_college_param(scope, college_id)
    if not scope.all and not college_id:
        if len(scope.college_ids) == 1:
            college_id = next(iter(scope.college_ids))
        else:
            raise AppException("VALIDATION_ERROR", "请指定学院后再生成教学任务")

    conditions = [
        AaTeachingTaskBatch.tenant_id == _tid(),
        AaTeachingTaskBatch.term_id == term_id,
        AaTeachingTaskBatch.status == "DRAFT",
        AaTeachingTaskBatch.is_deleted.is_(False),
    ]
    if college_id:
        conditions.append(AaTeachingTaskBatch.college_id == college_id)
    batch = db.scalars(select(AaTeachingTaskBatch).where(*conditions)).first()
    if not batch:
        batch = AaTeachingTaskBatch(
            tenant_id=_tid(), term_id=term_id,
            batch_name=getattr(body, "batchName", None) or f"学期{term_id}教学任务",
            college_id=college_id, generate_at=datetime.utcnow(), status="DRAFT",
        )
        db.add(batch)
        db.flush()

    made = 0
    unresolved_classes = 0
    unresolved_program_courses = 0
    out_of_term_courses = 0
    programs = db.scalars(select(AaProgram).where(
        AaProgram.tenant_id == _tid(),
        AaProgram.status == "ENABLED",
        AaProgram.is_deleted.is_(False),
    )).all()
    for program in programs:
        bindings = db.scalars(select(AaProgramBinding).where(
            AaProgramBinding.tenant_id == _tid(),
            AaProgramBinding.program_id == program.id,
            AaProgramBinding.status == "ACTIVE",
            AaProgramBinding.is_deleted.is_(False),
        )).all()
        courses = db.scalars(select(AaProgramCourse).where(
            AaProgramCourse.tenant_id == _tid(),
            AaProgramCourse.program_id == program.id,
            AaProgramCourse.is_deleted.is_(False),
        )).all()
        for binding in bindings:
            if binding.class_id:
                target_classes = [db.get(SchoolClass, int(binding.class_id))]
            else:
                target_classes = db.scalars(select(SchoolClass).where(
                    SchoolClass.tenant_id == _tid(),
                    SchoolClass.major_id == binding.major_id,
                    SchoolClass.grade == binding.grade_year,
                    SchoolClass.class_status == "NORMAL",
                    SchoolClass.is_deleted.is_(False),
                )).all()
            for school_class in target_classes:
                if not school_class:
                    continue
                if college_id:
                    from app.models import Major
                    major = db.get(Major, int(school_class.major_id)) if school_class.major_id else None
                    if not major or major.college_id != college_id:
                        continue
                if not scope.all and scope.class_ids and school_class.id not in scope.class_ids:
                    continue
                current_semester = resolve_class_semester(term, school_class)
                if current_semester is None:
                    unresolved_classes += 1
                    continue
                for program_course in courses:
                    try:
                        open_term_no = int(program_course.open_term_no)
                    except (TypeError, ValueError):
                        unresolved_program_courses += 1
                        continue
                    if open_term_no != current_semester:
                        out_of_term_courses += 1
                        continue
                    if not program_course.course_id:
                        unresolved_program_courses += 1
                        continue
                    existing = db.scalars(select(AaTeachingTask).where(
                        AaTeachingTask.tenant_id == _tid(),
                        AaTeachingTask.batch_id == batch.id,
                        AaTeachingTask.course_id == program_course.course_id,
                        AaTeachingTask.class_id == school_class.id,
                        AaTeachingTask.is_deleted.is_(False),
                    )).first()
                    if existing:
                        continue
                    course = db.get(AaCourse, int(program_course.course_id))
                    if not course or course.is_deleted or course.tenant_id != _tid():
                        unresolved_program_courses += 1
                        continue
                    total_hours = int(course.hours_total or 0)
                    course_code = course.course_code or ""
                    course_name = course.course_name or ""
                    weekly_hours = math.ceil(total_hours / teaching_weeks) if total_hours else None
                    db.add(AaTeachingTask(
                        tenant_id=_tid(), batch_id=batch.id,
                        course_id=program_course.course_id,
                        course_code=course_code, course_name=course_name,
                        class_id=school_class.id,
                        teaching_class_code=core._teaching_class_code(term_id, course_code, school_class.id),
                        teaching_class_name=f"{course_name}({school_class.class_name})",
                        total_hours=total_hours, weekly_hours=weekly_hours,
                        start_week=1, end_week=teaching_weeks, status="PENDING_ASSIGN",
                    ))
                    made += 1

    audit_detail = (
        f"+{made};teachingWeeks={teaching_weeks};source={week_source};"
        f"unresolvedClasses={unresolved_classes};"
        f"unresolvedProgramCourses={unresolved_program_courses};"
        f"outOfTermSkipped={out_of_term_courses}"
    )
    core._audit(db, "AA_TASK_BATCH", batch.id, "GENERATE", audit_detail)
    return {
        "batchId": str(batch.id), "batchName": batch.batch_name, "status": batch.status,
        "tasksGenerated": made, "teachingWeeks": teaching_weeks,
        "teachingWeeksSource": week_source, "unresolvedClasses": unresolved_classes,
        "unresolvedProgramCourses": unresolved_program_courses,
        "outOfTermCoursesSkipped": out_of_term_courses,
    }


def generate_batch(body, user) -> dict:
    """兼容入口；公开服务可复用 ``generate_batch_tx`` 参与更大原子事务。"""
    with session() as db:
        result = generate_batch_tx(db, body, user)
        db.commit()
        return result
