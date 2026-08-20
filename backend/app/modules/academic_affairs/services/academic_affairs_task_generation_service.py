"""教学任务批次生成器。

只负责根据学期时间轴、canonical Program activation、方案课程和行政班生成本学期应开任务；
不覆盖公开 Service，不管理工作台状态机，也不建立第二套执行计划事实。
"""
from __future__ import annotations

import math
import re
from datetime import datetime

from sqlalchemy import and_, or_, select

from app.core.exceptions import AppException
from app.core.tenant_scoped import tenant_get
from app.services.db_service import _tid, session

from . import academic_affairs_program_activation_service as program_activation
from . import academic_affairs_task_core_service as core
from .academic_affairs_task_formation_policy import normalize_formation_mode

_MIN_WEEKS = 1
_MAX_WEEKS = 30
_MAX_PROGRAM_TERM = 20
_BATCH_SCOPE_SAMPLE_LIMIT = 20
_EDITABLE_BATCH_STATUSES = ("DRAFT", "RETURNED")


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
    """返回 ``(教学周数, 来源)``；正式 Task writer 无可靠事实时必须 fail-closed。"""
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
    raise AppException(
        "DATA_CONFLICT",
        "当前学期缺少可证明的教学周配置，禁止按18周猜测生成正式教学任务；请先补齐教学周数、考试周或校历日期",
        details={"termId": str(term_id), "blocker": "TEACHING_WEEKS_UNRESOLVED"},
        http_status=409,
    )


def _resolve_binding_for_class(db, program, binding, school_class):
    resolution = program_activation.resolve_program_for_scope(
        db,
        tenant_id=_tid(),
        major_id=int(school_class.major_id) if school_class.major_id else binding.major_id,
        grade_year=str(school_class.grade or binding.grade_year or program.grade_year or "").strip(),
        class_id=int(school_class.id),
    )
    if resolution.status != "RESOLVED":
        raise AppException(
            "DATA_CONFLICT",
            f"班级“{school_class.class_name}”适用培养方案无法唯一解析：{resolution.message}",
            details={
                "blocker": "PROGRAM_ACTIVATION_UNRESOLVED",
                "classId": str(school_class.id),
                "majorId": str(school_class.major_id or binding.major_id or ""),
                "gradeYear": str(school_class.grade or binding.grade_year or program.grade_year or ""),
                "resolutionStatus": resolution.status,
                "resolutionRule": resolution.rule,
            },
            http_status=409,
        )
    return (
        int(resolution.program.id) == int(program.id)
        and int(resolution.binding.id) == int(binding.id)
    )


def _editable_batch_conditions(batch_model, term_id: int, college_id: int | None):
    """Return exact management scope for the one reusable editable task batch.

    DRAFT and RETURNED are both editable by the canonical task workflow. Generation
    must therefore resume either state instead of silently creating a second DRAFT
    beside a RETURNED batch. ``college_id`` remains management scope, not course owner.
    """
    conditions = [
        batch_model.tenant_id == _tid(),
        batch_model.term_id == int(term_id),
        batch_model.status.in_(_EDITABLE_BATCH_STATUSES),
        batch_model.is_deleted.is_(False),
    ]
    conditions.append(
        batch_model.college_id == int(college_id)
        if college_id is not None
        else batch_model.college_id.is_(None)
    )
    return conditions


def _choose_editable_batch(candidates, *, term_id: int, college_id: int | None):
    """Choose one exact-scope editable batch; conflicting historical rows fail closed."""
    rows = list(candidates or [])
    if len(rows) > 1:
        raise AppException(
            "DATA_CONFLICT",
            "同一学期和管理范围存在多条可编辑教学任务批次，禁止猜测继续生成；请先完成批次归并或归档",
            details={
                "blocker": "TASK_BATCH_EDITABLE_SCOPE_CONFLICT",
                "termId": str(term_id),
                "collegeId": str(college_id) if college_id is not None else "",
                "scope": f"COLLEGE:{college_id}" if college_id is not None else "SCHOOL",
                "batchIds": [str(row.id) for row in rows[:2]],
                "batchStatuses": [str(row.status or "") for row in rows[:2]],
            },
            http_status=409,
        )
    return rows[0] if rows else None


def _college_editable_batch_integrity_statement(batch):
    """Return one bounded query for legacy college-batch scope contamination.

    Before A-C4 introduces an explicit formation snapshot, every task already
    present in a college-scoped editable batch must still be provably tied to an
    administrative class whose major belongs to that same management college.
    Classless tasks are intentionally rejected here rather than guessed legal.
    """
    from app.models import AaTeachingTask, Major, SchoolClass

    college_id = int(batch.college_id)
    tenant_id = _tid()
    return (
        select(AaTeachingTask.id)
        .outerjoin(
            SchoolClass,
            and_(
                SchoolClass.id == AaTeachingTask.class_id,
                SchoolClass.tenant_id == tenant_id,
                SchoolClass.is_deleted.is_(False),
            ),
        )
        .outerjoin(
            Major,
            and_(
                Major.id == SchoolClass.major_id,
                Major.tenant_id == tenant_id,
                Major.is_deleted.is_(False),
            ),
        )
        .where(
            AaTeachingTask.tenant_id == tenant_id,
            AaTeachingTask.batch_id == int(batch.id),
            AaTeachingTask.is_deleted.is_(False),
            or_(
                AaTeachingTask.class_id.is_(None),
                SchoolClass.id.is_(None),
                Major.id.is_(None),
                Major.college_id != college_id,
            ),
        )
        .order_by(AaTeachingTask.id.asc())
        .limit(_BATCH_SCOPE_SAMPLE_LIMIT + 1)
    )


def _guard_college_editable_batch_integrity(db, batch) -> None:
    """Fail closed before appending to a historically contaminated college batch."""
    if getattr(batch, "college_id", None) is None:
        return
    invalid_ids = [int(value) for value in db.scalars(
        _college_editable_batch_integrity_statement(batch)
    ).all()]
    if not invalid_ids:
        return
    sample_ids = invalid_ids[:_BATCH_SCOPE_SAMPLE_LIMIT]
    raise AppException(
        "DATA_CONFLICT",
        "已有学院教学任务可编辑批次包含无法证明属于该学院的历史任务，禁止继续追加；请先核对批次归属",
        details={
            "blocker": "TASK_BATCH_SCOPE_CONTAMINATED",
            "batchId": str(batch.id),
            "collegeId": str(batch.college_id),
            "sampleTaskIds": [str(value) for value in sample_ids],
            "sampleTruncated": len(invalid_ids) > _BATCH_SCOPE_SAMPLE_LIMIT,
        },
        http_status=409,
    )


def _snapshot_program_course_formation(program_course) -> str | None:
    """Copy only the explicit source-row formation; missing legacy truth stays NULL."""
    try:
        return normalize_formation_mode(getattr(program_course, "formation_mode", None))
    except ValueError as exc:
        raise AppException(
            "DATA_CONFLICT",
            "培养方案课程的 formationMode 非法，禁止生成带伪来源的教学任务",
            details={
                "blocker": "PROGRAM_COURSE_FORMATION_INVALID",
                "programCourseId": str(getattr(program_course, "id", "") or ""),
                "formationMode": str(getattr(program_course, "formation_mode", "") or ""),
            },
            http_status=409,
        ) from exc


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
    term = tenant_get(db, AaTerm, term_id, tenant_id=_tid())
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

    conditions = _editable_batch_conditions(AaTeachingTaskBatch, term_id, college_id)
    candidates = db.scalars(
        select(AaTeachingTaskBatch)
        .where(*conditions)
        .order_by(AaTeachingTaskBatch.id.asc())
        .limit(2)
    ).all()
    batch = _choose_editable_batch(candidates, term_id=term_id, college_id=college_id)
    if batch and college_id is not None:
        _guard_college_editable_batch_integrity(db, batch)
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
        AaProgram.status.in_(sorted(program_activation.CURRENT_EFFECTIVE_PROGRAM_STATUSES)),
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
                target_classes = [tenant_get(db, SchoolClass, int(binding.class_id), tenant_id=_tid())]
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
                    major = tenant_get(db, Major, int(school_class.major_id), tenant_id=_tid()) if school_class.major_id else None
                    if not major or major.college_id != college_id:
                        continue
                if not scope.all and scope.class_ids and school_class.id not in scope.class_ids:
                    continue
                if not _resolve_binding_for_class(db, program, binding, school_class):
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
                    course = tenant_get(db, AaCourse, int(program_course.course_id), tenant_id=_tid())
                    if not course or course.is_deleted or course.tenant_id != _tid():
                        unresolved_program_courses += 1
                        continue
                    formation_mode = _snapshot_program_course_formation(program_course)
                    total_hours = int(course.hours_total or 0)
                    course_code = course.course_code or ""
                    course_name = course.course_name or ""
                    weekly_hours = math.ceil(total_hours / teaching_weeks) if total_hours else None
                    db.add(AaTeachingTask(
                        tenant_id=_tid(), batch_id=batch.id,
                        course_id=program_course.course_id,
                        course_code=course_code, course_name=course_name,
                        class_id=school_class.id,
                        source_program_course_id=program_course.id,
                        formation_mode=formation_mode,
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
