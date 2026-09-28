"""教学任务批次生成器。

只负责根据学期时间轴、canonical Program activation、方案课程和行政班生成本学期应开任务；
不覆盖公开 Service，不管理工作台状态机，也不建立第二套执行计划事实。
"""
from __future__ import annotations

import math
import re
from datetime import datetime

from sqlalchemy import and_, exists, or_, select

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


def _resolve_binding_for_class(db, program, binding, school_class, *, term_end=None):
    scope = {
        "tenant_id": _tid(),
        "major_id": int(school_class.major_id) if school_class.major_id else binding.major_id,
        "grade_year": str(school_class.grade or binding.grade_year or program.grade_year or "").strip(),
        "class_id": int(school_class.id),
    }
    resolution = program_activation.resolve_program_for_scope(
        db,
        **scope,
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
    selected = (
        int(resolution.program.id) == int(program.id)
        and int(resolution.binding.id) == int(binding.id)
    )
    if not selected or term_end is None:
        return selected
    # Only current bindings are generated; they must also match the term-end replay.
    historical = program_activation.resolve_program_for_scope(db, **scope, as_of=term_end)
    if (historical.status != "RESOLVED" or not historical.program or not historical.binding
            or int(historical.program.id) != int(program.id)
            or int(historical.binding.id) != int(binding.id)):
        raise AppException(
            "DATA_CONFLICT",
            f"班级“{school_class.class_name}”当前绑定在该学期结束时尚未生效，或期末适用的是另一方案版本，不能生成历史学期教学任务",
            details={
                "blocker": "PROGRAM_BINDING_NOT_EFFECTIVE_AT_TERM_END",
                "classId": str(school_class.id),
                "programId": str(program.id),
                "bindingId": str(binding.id),
                "historicalRule": historical.rule,
            },
            http_status=409,
        )
    return True


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
    """责任来自批次；核对正式课程/成班来源，不把跨院学生误作责任污染。"""
    from app.models import AaCourse, AaTeachingClass, AaTeachingTask, SchoolClass

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
            AaCourse,
            and_(
                AaCourse.id == AaTeachingTask.course_id,
                AaCourse.tenant_id == tenant_id,
                AaCourse.is_deleted.is_(False),
            ),
        )
        .where(
            AaTeachingTask.tenant_id == tenant_id,
            AaTeachingTask.batch_id == int(batch.id),
            AaTeachingTask.is_deleted.is_(False),
            or_(
                AaCourse.id.is_(None),
                and_(AaTeachingTask.class_id.is_not(None), SchoolClass.id.is_(None)),
                and_(
                    AaTeachingTask.class_id.is_(None),
                    or_(AaTeachingTask.formation_mode.is_(None),
                        AaTeachingTask.formation_mode.not_in(("SELECTABLE", "MERGED", "RETAKE", "LAYERED"))),
                    ~exists(select(AaTeachingClass.id).where(
                        AaTeachingClass.tenant_id == tenant_id,
                        AaTeachingClass.teaching_task_id == AaTeachingTask.id,
                        AaTeachingClass.term_id == int(batch.term_id),
                        AaTeachingClass.course_id == AaTeachingTask.course_id,
                        AaTeachingClass.is_deleted.is_(False),
                    )),
                ),
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


def _existing_term_task_rows(db, *, term_id: int, course_id: int, class_id: int):
    """Current-read lookup across all live batches for one tenant/term/course/class."""
    from app.models import AaTeachingTask, AaTeachingTaskBatch

    return db.execute(
        select(AaTeachingTask.id, AaTeachingTaskBatch.id, AaTeachingTaskBatch.college_id)
        .join(AaTeachingTaskBatch, AaTeachingTaskBatch.id == AaTeachingTask.batch_id)
        .where(
            AaTeachingTask.tenant_id == _tid(),
            AaTeachingTask.is_deleted.is_(False),
            AaTeachingTask.course_id == int(course_id),
            AaTeachingTask.class_id == int(class_id),
            AaTeachingTaskBatch.tenant_id == _tid(),
            AaTeachingTaskBatch.term_id == int(term_id),
            AaTeachingTaskBatch.is_deleted.is_(False),
        )
        .order_by(AaTeachingTask.id.asc())
        .limit(2)
        .with_for_update()
    ).all()


def _locked_term_statement(term_id: int):
    """Lock and refresh an already-loaded term so archive races fail closed."""
    from app.models import AaTerm

    return (
        select(AaTerm)
        .where(
            AaTerm.id == int(term_id),
            AaTerm.tenant_id == _tid(),
            AaTerm.is_deleted.is_(False),
        )
        .execution_options(populate_existing=True)
        .with_for_update()
    )


def generate_batch_tx(db, body, user) -> dict:
    term_id = int(body.termId)

    from app.models import (
        AaCourse, AaProgram, AaProgramBinding, AaProgramCourse, AaTeachingTask,
        AaTeachingTaskBatch, AaTerm, SchoolClass,
    )
    from app.modules.academic_affairs.services.academic_affairs_archive_service import guard_term_writable
    from .academic_affairs_task_service import _generation_college

    college_id, scope = _generation_college(db, user, getattr(body, "collegeId", None))

    guard_term_writable(db, term_id)
    # Serializes school-wide and college-specific generation for this tenant/term.
    # Recheck after acquiring the row lock because archive may race the first guard.
    term = db.scalars(_locked_term_statement(term_id)).first()
    if not term or term.is_deleted or term.tenant_id != _tid():
        raise AppException("VALIDATION_ERROR", "学期不存在，无法生成教学任务")
    if str(term.status or "").upper() == "ARCHIVED":
        raise AppException("TERM_ARCHIVED", "该学期已归档封存，禁止修改", http_status=409)
    teaching_weeks, week_source = resolve_teaching_weeks(db, term_id)
    conditions = _editable_batch_conditions(AaTeachingTaskBatch, term_id, college_id)
    candidates = db.scalars(
        select(AaTeachingTaskBatch)
        .where(*conditions)
        .order_by(AaTeachingTaskBatch.id.asc())
        .limit(2).with_for_update()
    ).all()
    batch = _choose_editable_batch(candidates, term_id=term_id, college_id=college_id)
    if batch and college_id is not None:
        _guard_college_editable_batch_integrity(db, batch)

    def create_batch():
        from .academic_affairs_task_batch_inventory_service import canonical_editable_scope_key
        from sqlalchemy.exc import IntegrityError
        created = AaTeachingTaskBatch(
            tenant_id=_tid(), term_id=term_id,
            batch_name=getattr(body, "batchName", None) or f"学期{term_id}教学任务",
            college_id=college_id, generate_at=datetime.utcnow(), status="DRAFT",
            editable_scope_key=canonical_editable_scope_key(term_id, college_id),
        )
        db.add(created)
        try:
            db.flush()
        except IntegrityError as exc:
            db.rollback()
            if "uk_aa_task_batch_editable_scope" not in str(exc.orig):
                raise
            raise AppException("DATA_CONFLICT", "该学院同时产生了可编辑批次，请刷新后继续原批次") from exc
        return created

    made = 0
    skipped_existing = 0
    expected_pairs = set()
    seen_pairs = set()
    same_scope_existing_batch_ids = set()
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
        course_query = select(AaProgramCourse).where(
            AaProgramCourse.tenant_id == _tid(),
            AaProgramCourse.program_id == program.id,
            AaProgramCourse.is_deleted.is_(False),
        )
        if college_id:
            course_query = course_query.join(AaCourse, AaCourse.id == AaProgramCourse.course_id).where(
                AaCourse.tenant_id == _tid(), AaCourse.is_deleted.is_(False),
                AaCourse.owner_college_id == college_id,
            )
        courses = db.scalars(course_query).all()
        if not courses:
            continue
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
                if not scope.all and not scope.college_ids and scope.class_ids and school_class.id not in scope.class_ids:
                    continue
                if not _resolve_binding_for_class(db, program, binding, school_class):
                    continue
                current_semester = resolve_class_semester(term, school_class)
                if current_semester is None:
                    unresolved_classes += 1
                    continue
                binding_time_checked = False
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
                    pair = (int(program_course.course_id), int(school_class.id))
                    if pair in seen_pairs:
                        continue
                    seen_pairs.add(pair)
                    expected_pairs.add(pair)
                    existing_rows = _existing_term_task_rows(
                        db, term_id=term_id, course_id=pair[0], class_id=pair[1],
                    )
                    if len(existing_rows) > 1:
                        raise AppException(
                            "DATA_CONFLICT",
                            "本学期同一课程与行政班已存在多条正式任务，已停止生成，请核对现有批次",
                            details={"blocker": "TASK_GENERATION_EXISTING_TASK_CONFLICT"},
                            http_status=409,
                        )
                    if existing_rows:
                        _task_id, existing_batch_id, existing_college_id = existing_rows[0]
                        if existing_college_id != college_id:
                            raise AppException(
                                "DATA_CONFLICT",
                                "目标课程与行政班已落入其他管理范围的正式批次，已停止生成，请由该范围责任人核对",
                                details={"blocker": "TASK_GENERATION_SCOPE_CONFLICT"},
                                http_status=409,
                            )
                        skipped_existing += 1
                        same_scope_existing_batch_ids.add(str(existing_batch_id))
                        continue
                    course = tenant_get(db, AaCourse, int(program_course.course_id), tenant_id=_tid())
                    if not course or course.is_deleted or course.tenant_id != _tid():
                        unresolved_program_courses += 1
                        continue
                    if not binding_time_checked:
                        if not _resolve_binding_for_class(
                            db, program, binding, school_class, term_end=term.end_date
                        ):
                            continue
                        binding_time_checked = True
                    formation_mode = _snapshot_program_course_formation(program_course)
                    total_hours = int(course.hours_total or 0)
                    course_code = course.course_code or ""
                    course_name = course.course_name or ""
                    weekly_hours = math.ceil(total_hours / teaching_weeks) if total_hours else None
                    if batch is None:
                        batch = create_batch()
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

    if (
        made == 0
        and expected_pairs
        and skipped_existing == len(expected_pairs)
        and (batch is None or str(batch.id) not in same_scope_existing_batch_ids)
    ):
        visible_batch_ids = sorted(same_scope_existing_batch_ids)
        reference = f"现有正式批次 #{visible_batch_ids[0]}" if visible_batch_ids else "现有正式批次"
        raise AppException(
            "DATA_CONFLICT",
            f"本学期应开课程已存在于{reference}，未新建空批次或重复任务；请在本学院任务列表核对",
            details={
                "blocker": "TASK_GENERATION_ALREADY_EXISTS",
                "existingTaskCount": skipped_existing,
            },
            http_status=409,
        )
    if batch is None:
        # Preserve the existing diagnostic batch behavior when no target-term pair
        # could be resolved (for example all source courses are out of term).
        batch = create_batch()

    audit_detail = (
        f"+{made};skippedExisting={skipped_existing};teachingWeeks={teaching_weeks};source={week_source};"
        f"unresolvedClasses={unresolved_classes};"
        f"unresolvedProgramCourses={unresolved_program_courses};"
        f"outOfTermSkipped={out_of_term_courses}"
    )
    core._audit(db, "AA_TASK_BATCH", batch.id, "GENERATE", audit_detail)
    return {
        "batchId": str(batch.id), "batchName": batch.batch_name, "status": batch.status,
        "tasksGenerated": made, "tasksSkippedExisting": skipped_existing, "teachingWeeks": teaching_weeks,
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
