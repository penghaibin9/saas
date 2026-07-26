"""教学任务服务兼容入口。

仅覆盖批次生成：教学周优先读取 AaTerm.teaching_weeks，其次使用考试周起始、校历教学事件、
学期日期推算；只有历史学期完全缺配置时才回退18周并记录告警。其余任务状态机委托原服务。
"""
from __future__ import annotations

import logging
import math
from datetime import datetime

from sqlalchemy import select

from app.core.exceptions import AppException
from app.services.db_service import _tid, session

from . import academic_affairs_task_service as _legacy

_LOG = logging.getLogger(__name__)
_FALLBACK_WEEKS = 18
_MIN_WEEKS = 1
_MAX_WEEKS = 30


def __getattr__(name):
    return getattr(_legacy, name)


def _bounded(value):
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return number if _MIN_WEEKS <= number <= _MAX_WEEKS else None


def resolve_teaching_weeks(db, term_id):
    """返回 ``(教学周数, 来源)``，不把18周当作正式制度。"""
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
            last_day = max(teaching_ends)
            weeks = _bounded(math.ceil(((last_day - term.start_date).days + 1) / 7))
            if weeks:
                return weeks, "CALENDAR_TEACHING_EVENTS"

    if term.start_date and term.end_date and term.end_date >= term.start_date:
        weeks = _bounded(math.ceil(((term.end_date - term.start_date).days + 1) / 7))
        if weeks:
            return weeks, "TERM_DATE_RANGE"

    _LOG.warning(
        "term %s has no reliable teaching-week configuration; fallback=%s",
        term_id,
        _FALLBACK_WEEKS,
    )
    return _FALLBACK_WEEKS, "LEGACY_FALLBACK_18"


def generate_batch(body, user) -> dict:
    """按已发布方案生成任务，教学周由学期时间轴决定。"""
    term_id = int(body.termId)
    college_id = int(body.collegeId) if getattr(body, "collegeId", None) else None

    with session() as db:
        from app.models import (
            AaCourse,
            AaProgram,
            AaProgramBinding,
            AaProgramCourse,
            AaTeachingTask,
            AaTeachingTaskBatch,
            SchoolClass,
        )
        from app.modules.academic_affairs.services.academic_affairs_archive_service import guard_term_writable
        from app.modules.academic_affairs.services.academic_affairs_stats_service import (
            _resolve_scope,
            _validate_college_param,
        )

        guard_term_writable(db, term_id)
        teaching_weeks, week_source = resolve_teaching_weeks(db, term_id)
        scope = _resolve_scope(user, db)
        _validate_college_param(scope, college_id)
        if not scope.all and not college_id:
            if len(scope.college_ids) == 1:
                college_id = next(iter(scope.college_ids))
            else:
                raise AppException("VALIDATION_ERROR", "请指定学院后再生成教学任务")

        batch_conditions = [
            AaTeachingTaskBatch.tenant_id == _tid(),
            AaTeachingTaskBatch.term_id == term_id,
            AaTeachingTaskBatch.status == "DRAFT",
            AaTeachingTaskBatch.is_deleted.is_(False),
        ]
        if college_id:
            batch_conditions.append(AaTeachingTaskBatch.college_id == college_id)
        batch = db.scalars(select(AaTeachingTaskBatch).where(*batch_conditions)).first()
        if not batch:
            batch = AaTeachingTaskBatch(
                tenant_id=_tid(),
                term_id=term_id,
                batch_name=getattr(body, "batchName", None) or f"学期{term_id}教学任务",
                college_id=college_id,
                generate_at=datetime.utcnow(),
                status="DRAFT",
            )
            db.add(batch)
            db.flush()

        made = 0
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

                    for program_course in courses:
                        if not program_course.course_id:
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
                        total_hours = int(course.hours_total or 0) if course else 0
                        course_code = course.course_code if course else ""
                        course_name = course.course_name if course else ""
                        weekly_hours = math.ceil(total_hours / teaching_weeks) if total_hours else None
                        db.add(AaTeachingTask(
                            tenant_id=_tid(),
                            batch_id=batch.id,
                            course_id=program_course.course_id,
                            course_code=course_code,
                            course_name=course_name,
                            class_id=school_class.id,
                            teaching_class_code=_legacy._teaching_class_code(
                                term_id, course_code, school_class.id
                            ),
                            teaching_class_name=f"{course_name}({school_class.class_name})",
                            total_hours=total_hours,
                            weekly_hours=weekly_hours,
                            start_week=1,
                            end_week=teaching_weeks,
                            status="PENDING_ASSIGN",
                        ))
                        made += 1

        _legacy._audit(
            db,
            "AA_TASK_BATCH",
            batch.id,
            "GENERATE",
            f"+{made};teachingWeeks={teaching_weeks};source={week_source}",
        )
        db.commit()
        db.refresh(batch)
        return {
            "batchId": str(batch.id),
            "batchName": batch.batch_name,
            "status": batch.status,
            "tasksGenerated": made,
            "teachingWeeks": teaching_weeks,
            "teachingWeeksSource": week_source,
        }
