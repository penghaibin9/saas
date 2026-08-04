"""选课域唯一公开 Service。

原列表、统计、冲突报表和归档导出保存在 ``academic_affairs_selection_core_service``；本文件显式收口：
- 所有写动作在同一事务校验正式学期未封存；
- 学生本人只使用稳定账号绑定；
- 已修与先修规则按稳定 courseCode 和统一有效成绩判断；
- 先到先得、抽签、补退选继续复用同一批次/记录状态机；
- CLOSED→LOCKED 前执行名单一致性校验并生成独立教学班名单版本；
- LOCKED 后人工退课使用真实 R9 消费者快照判断，不按课程名模糊猜测；
- 人工调整、容量、预计人数和新名单版本在同一事务完成。

不修改其它模块函数，不依赖 Facade 导入顺序。
"""
from __future__ import annotations

import json
from datetime import datetime

from sqlalchemy import select

from app.core.context import get_current_user_ctx
from app.core.exceptions import AppException, not_found

from . import academic_affairs_grade_service as grade_service
from . import academic_affairs_selection_core_service as _core
from . import academic_affairs_selection_roster_projection_service as roster_projection
from . import academic_affairs_teaching_class_service as teaching_class_service
from .academic_affairs_roster_consumer_service import consumer_counts
from .academic_affairs_teaching_roster_service import (
    apply_locked_roster_projection,
    validate_selection_lock,
)

_BATCH_DRAFT = _core._BATCH_DRAFT
_BATCH_PUBLISHED = _core._BATCH_PUBLISHED
_BATCH_OPEN = _core._BATCH_OPEN
_BATCH_CLOSED = _core._BATCH_CLOSED
_BATCH_LOCKED = _core._BATCH_LOCKED
_BATCH_ARCHIVED = _core._BATCH_ARCHIVED
_REC_SELECTED = _core._REC_SELECTED
_REC_LOCKED = _core._REC_LOCKED
_REC_DROPPED = _core._REC_DROPPED
_REC_COURSE_CANCELLED = _core._REC_COURSE_CANCELLED
_REC_PENDING = _core._REC_PENDING
_REC_LOST = _core._REC_LOST
_COURSE_OPEN = _core._COURSE_OPEN
_COURSE_CANCELLED = _core._COURSE_CANCELLED


def __getattr__(name):
    """未重写的只读列表、统计、冲突报表和归档导出显式复用稳定 core。"""
    return getattr(_core, name)


def _guard_batch_writable(db, batch):
    from . import academic_affairs_archive_service as archive_service

    if not getattr(batch, "term_id", None):
        raise AppException("DATA_CONFLICT", "选课批次必须绑定正式学期termId", http_status=409)
    archive_service.guard_term_writable(db, int(batch.term_id))
    return batch


def _load_student(db):
    from app.services.mobile_student_identity_facade import resolve_student

    student = resolve_student(db, get_current_user_ctx() or {})
    if not student:
        raise not_found("当前账号尚未绑定唯一学生档案")
    return student


def _passed_course_codes(db, student) -> set[str]:
    from app.models import AcademicGrade, AcademicStudent

    academic_student = db.query(AcademicStudent).filter(
        AcademicStudent.tenant_id == _core._tid(),
        AcademicStudent.student_id == int(student.id),
        AcademicStudent.is_deleted.is_(False),
    ).first()
    if not academic_student:
        return set()
    rows = db.query(AcademicGrade).filter(
        AcademicGrade.tenant_id == _core._tid(),
        AcademicGrade.acad_student_id == academic_student.id,
        AcademicGrade.record_status == "ACTIVE",
        AcademicGrade.is_deleted.is_(False),
    ).all()
    return {
        str(row.course_code or "").strip().upper()
        for row in grade_service.effective_grade_rows(rows)
        if str(row.pass_status or "").upper() == "PASSED"
        and str(row.course_code or "").strip()
    }




def _load_prerequisite_codes(course) -> set[str]:
    """读取课程正式先修代码；损坏配置必须阻断选课，禁止静默当作无先修课。"""
    raw = getattr(course, "prerequisite_codes_json", None)
    if raw in (None, "", []):
        return set()
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            raise AppException(
                "DATA_CONFLICT",
                "课程先修规则JSON损坏，请联系教务管理员修复后再选课",
                details={"courseCode": str(getattr(course, "course_code", "") or "")},
                http_status=409,
            ) from exc
    if not isinstance(raw, list):
        raise AppException(
            "DATA_CONFLICT",
            "课程先修规则格式错误，必须是课程代码数组",
            details={"courseCode": str(getattr(course, "course_code", "") or "")},
            http_status=409,
        )
    return {str(code).strip().upper() for code in raw if str(code).strip()}

def _active_round(db, batch_id):
    from app.models import AaSelectionRound

    return db.query(AaSelectionRound).filter(
        AaSelectionRound.tenant_id == _core._tid(),
        AaSelectionRound.batch_id == int(batch_id),
        AaSelectionRound.status == "OPEN",
        AaSelectionRound.is_deleted.is_(False),
    ).first()


def _validate_enroll(db, batch, course, student, my_records, add_credit, *, allow_reselect_closed=False):
    from app.models import AaCourse, AaSelectionCourse
    from app.modules.academic_affairs.services.academic_affairs_schedule_service import _weeks_overlap
    from app.modules.academic_affairs.services.academic_affairs_status_service import is_enrolled

    if not is_enrolled(getattr(student, "student_status", None)):
        raise AppException("NO_DATA_SCOPE", "当前学籍状态不可选课")
    if batch.status != _BATCH_OPEN:
        if not (allow_reselect_closed and batch.status == _BATCH_CLOSED):
            raise _core._invalid("不在选课时间内")

    if batch.apply_scope_json:
        try:
            scope = json.loads(batch.apply_scope_json)
        except (TypeError, ValueError):
            scope = {}
        college_ids = {int(x) for x in (scope.get("collegeIds") or []) if str(x).isdigit()}
        major_ids = {int(x) for x in (scope.get("majorIds") or []) if str(x).isdigit()}
        grade_years = {str(x) for x in (scope.get("gradeYears") or []) if str(x).strip()}
        if college_ids and int(getattr(student, "college_id", 0) or 0) not in college_ids:
            raise AppException("NO_DATA_SCOPE", "当前学生不在本轮选课学院范围内")
        if major_ids and int(getattr(student, "major_id", 0) or 0) not in major_ids:
            raise AppException("NO_DATA_SCOPE", "当前学生不在本轮选课专业范围内")
        if grade_years and str(getattr(student, "grade", "") or "") not in grade_years:
            raise AppException("NO_DATA_SCOPE", "当前学生不在本轮选课年级范围内")

    selected_course_ids = {
        int(r.selection_course_id) for r in my_records
        if r.status in (_REC_SELECTED, _REC_LOCKED)
    }
    if int(course.id) in selected_course_ids:
        raise _core._invalid("该课程已选，不可重复选择")

    active_selected = db.query(AaSelectionCourse).filter(
        AaSelectionCourse.tenant_id == _core._tid(),
        AaSelectionCourse.id.in_(selected_course_ids or {-1}),
        AaSelectionCourse.is_deleted.is_(False),
    ).all()
    selected_codes = {str(item.course_code or "").strip().upper() for item in active_selected}
    if str(course.course_code or "").strip().upper() in selected_codes:
        raise _core._invalid("同一课程代码已存在在途选课记录")

    passed_codes = _passed_course_codes(db, student)
    target_code = str(course.course_code or "").strip().upper()
    if target_code and target_code in passed_codes:
        raise _core._invalid("该课程已修读通过，不可重复选课")

    source_course = db.query(AaCourse).filter(
        AaCourse.tenant_id == _core._tid(),
        AaCourse.course_code == course.course_code,
        AaCourse.is_deleted.is_(False),
    ).order_by(AaCourse.version.desc(), AaCourse.id.desc()).first()
    prerequisites = _load_prerequisite_codes(source_course) if source_course else set()
    missing = sorted(prerequisites - passed_codes)
    if missing:
        raise _core._invalid(f"未满足先修课程：{','.join(missing)}")

    projected_credit = sum(float(item.credit or 0) for item in active_selected) + float(add_credit or 0)
    if float(batch.max_credit or 0) > 0 and projected_credit > float(batch.max_credit):
        raise _core._invalid("超过本轮选课最大学分限制")

    for item in active_selected:
        if item.weekday != course.weekday or item.start_slot is None or item.end_slot is None:
            continue
        if _weeks_overlap(item.teaching_weeks_json, course.teaching_weeks_json) and not (
            int(item.end_slot) < int(course.start_slot) or int(course.end_slot) < int(item.start_slot)
        ):
            raise _core._invalid(f"与已选课程{item.course_name}上课时间冲突")

    if int(course.selected_count or 0) >= int(course.capacity or 0):
        raise _core._invalid("课程容量已满")


def _lock_course_row(db, course_id):
    from app.models import AaSelectionCourse

    stmt = select(AaSelectionCourse).where(
        AaSelectionCourse.id == int(course_id),
        AaSelectionCourse.tenant_id == _core._tid(),
        AaSelectionCourse.is_deleted.is_(False),
    ).with_for_update()
    course = db.execute(stmt).scalar_one_or_none()
    if not course:
        raise not_found("选课课程不存在")
    return course


def enroll(user, course_id, *, lottery=False):
    with _core.session() as db:
        _core._ctx(user, db)
        student = _load_student(db)
        course = _lock_course_row(db, course_id)
        batch = _core._batch(db, course.batch_id)
        _guard_batch_writable(db, batch)
        my_records = _core._my_records(db, batch.id, student.id)
        _validate_enroll(db, batch, course, student, my_records, course.credit)
        round_row = _active_round(db, batch.id)
        if round_row and round_row.mode == "LOTTERY":
            lottery = True
        now = datetime.utcnow()
        record = _core._create_record(
            db,
            batch=batch,
            course=course,
            student=student,
            status=_REC_PENDING if lottery else _REC_SELECTED,
            selected_at=now,
        )
        if not lottery:
            course.selected_count = int(course.selected_count or 0) + 1
        _core._audit(db, record.id, "SELECTION_ENROLL", "学生选课")
        db.commit()
        return _core._record_view(record, course)


def drop(user, course_id):
    with _core.session() as db:
        _core._ctx(user, db)
        student = _load_student(db)
        course = _lock_course_row(db, course_id)
        batch = _core._batch(db, course.batch_id)
        _guard_batch_writable(db, batch)
        if batch.status != _BATCH_OPEN:
            raise _core._invalid("不在退课时间内")
        record = _core._active_record(db, batch.id, course.id, student.id, for_update=True)
        if not record:
            raise not_found("当前课程没有可退选记录")
        if record.status == _REC_LOCKED:
            raise _core._invalid("选课名单已锁定，不可自行退课")
        record.status = _REC_DROPPED
        record.dropped_at = datetime.utcnow()
        if record.status != _REC_PENDING:
            course.selected_count = max(0, int(course.selected_count or 0) - 1)
        _core._audit(db, record.id, "SELECTION_DROP", "学生退课")
        db.commit()
        return _core._record_view(record, course)


def lock_batch(user, batch_id):
    with _core.session() as db:
        _core._require_school(_core._ctx(user, db))
        batch = _core._batch(db, batch_id, for_update=True)
        _guard_batch_writable(db, batch)
        if batch.status != _BATCH_CLOSED:
            raise _core._invalid("仅已关闭选课批次可锁定名单")
        validate_selection_lock(db, batch)
        result = apply_locked_roster_projection(db, batch, actor_user=user)
        batch.status = _BATCH_LOCKED
        batch.locked_at = datetime.utcnow()
        _core._audit(db, batch.id, "SELECTION_LOCK", "锁定选课名单并生成教学班名单版本")
        db.commit()
        return result


def admin_drop(user, record_id, reason):
    with _core.session() as db:
        _core._require_school(_core._ctx(user, db))
        record = _core._record(db, record_id, for_update=True)
        course = _lock_course_row(db, record.selection_course_id)
        batch = _core._batch(db, record.batch_id)
        _guard_batch_writable(db, batch)
        if record.status not in (_REC_SELECTED, _REC_LOCKED):
            raise _core._invalid("该选课记录当前不可退课")
        if record.status == _REC_LOCKED:
            counts = consumer_counts(db, course.teaching_task_id, student_id=record.student_id)
            if any(int(value or 0) > 0 for value in counts.values()):
                raise _core._invalid("该学生已产生考勤、成绩或评教等下游事实，不可直接退课")
        record.status = _REC_DROPPED
        record.dropped_at = datetime.utcnow()
        course.selected_count = max(0, int(course.selected_count or 0) - 1)
        roster_projection.apply_admin_drop(db, record, reason=reason, actor_user=user)
        _core._audit(db, record.id, "SELECTION_ADMIN_DROP", reason)
        db.commit()
        return _core._record_view(record, course)


def reselect(user, course_id):
    with _core.session() as db:
        _core._require_school(_core._ctx(user, db))
        student = _load_student(db)
        course = _lock_course_row(db, course_id)
        batch = _core._batch(db, course.batch_id)
        _guard_batch_writable(db, batch)
        my_records = _core._my_records(db, batch.id, student.id)
        _validate_enroll(db, batch, course, student, my_records, course.credit, allow_reselect_closed=True)
        record = _core._create_record(
            db,
            batch=batch,
            course=course,
            student=student,
            status=_REC_SELECTED,
            selected_at=datetime.utcnow(),
        )
        course.selected_count = int(course.selected_count or 0) + 1
        _core._audit(db, record.id, "SELECTION_RESELECT", "管理员补选")
        db.commit()
        return _core._record_view(record, course)
