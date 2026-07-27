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
from app.core.exceptions import AppException, no_data_scope, not_found

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
        raise no_data_scope("当前学籍状态不可选课")
    if batch.status != _BATCH_OPEN:
        if not (allow_reselect_closed and batch.status == _BATCH_CLOSED):
            raise _core._invalid("不在选课时间内")

    if batch.apply_scope_json:
        try:
            scope = json.loads(batch.apply_scope_json)
        except (TypeError, ValueError, json.JSONDecodeError):
            raise AppException("DATA_CONFLICT", "选课批次适用范围配置损坏，请联系教务处修复", http_status=409)
        if scope:
            grade_ok = not scope.get("grades") or student.grade in scope["grades"]
            major_ok = not scope.get("majorIds") or str(student.major_id) in {str(value) for value in scope["majorIds"]}
            class_ok = not scope.get("classIds") or str(student.class_id) in {str(value) for value in scope["classIds"]}
            if not (grade_ok and major_ok and class_ok):
                raise AppException("VALIDATION_ERROR", "不在本批次适用范围内")

    for record in my_records:
        if int(record.course_id or 0) == int(course.course_id) and record.status in {_REC_SELECTED, _REC_LOCKED, _REC_PENDING}:
            raise _core._conflict("已选过该课程或已有待抽签志愿")

    target = db.query(AaCourse).filter(
        AaCourse.id == int(course.course_id),
        AaCourse.tenant_id == _core._tid(),
        AaCourse.is_deleted.is_(False),
    ).first()
    if not target:
        raise AppException("DATA_CONFLICT", "选课课程版本不存在", http_status=409)
    target_code = str(target.course_code or "").strip().upper()
    if not target_code:
        raise AppException(
            "DATA_CONFLICT",
            "课程缺少稳定courseCode，禁止用于正式选课",
            details={"courseId": str(target.id)},
            http_status=409,
        )

    passed_codes = _passed_course_codes(db, student)
    if target_code in passed_codes:
        raise AppException("VALIDATION_ERROR", "该课程已通过，不可再选（重修请走重修报名）")

    if target.prerequisite_codes_json:
        try:
            prerequisites = {
                str(value).strip().upper()
                for value in (json.loads(target.prerequisite_codes_json) or [])
                if str(value).strip()
            }
        except (TypeError, ValueError, json.JSONDecodeError):
            raise AppException("DATA_CONFLICT", "课程先修规则配置损坏，请联系教务处修复", http_status=409)
        missing = prerequisites - passed_codes
        if missing:
            labels = {
                str(row.course_code or "").strip().upper(): row.course_name
                for row in db.query(AaCourse).filter(
                    AaCourse.tenant_id == _core._tid(),
                    AaCourse.course_code.in_(sorted(missing)),
                    AaCourse.is_deleted.is_(False),
                ).all()
            }
            readable = [f"{code} {labels.get(code, '')}".strip() for code in sorted(missing)]
            raise AppException("VALIDATION_ERROR", f"未满足先修课程要求：{', '.join(readable)}")

    target_slots = _core._task_slots(db, course.teaching_task_id)
    if target_slots:
        selected_course_ids = [
            record.selection_course_id for record in my_records
            if record.status in {_REC_SELECTED, _REC_LOCKED}
        ]
        if selected_course_ids:
            task_rows = db.query(AaSelectionCourse.teaching_task_id).filter(
                AaSelectionCourse.id.in_(selected_course_ids),
                AaSelectionCourse.tenant_id == _core._tid(),
            ).all()
            for (task_id,) in task_rows:
                for weekday_left, slot_left, start_left, end_left, parity_left in _core._task_slots(db, task_id):
                    for weekday_right, slot_right, start_right, end_right, parity_right in target_slots:
                        if (
                            weekday_left == weekday_right
                            and slot_left == slot_right
                            and _weeks_overlap(
                                start_left, end_left, parity_left,
                                start_right, end_right, parity_right,
                            )
                        ):
                            message = f"与已选课程上课时间冲突（周{weekday_left}第{slot_left}节）"
                            _core._record_conflict_reject(db, batch, course, student, message)
                            raise _core._conflict(message)

    maximum = _core._rule(db, batch, "maxCredits", 0)
    if maximum and float(maximum) > 0:
        current = sum(
            float(record.credit or 0)
            for record in my_records
            if record.status in {_REC_SELECTED, _REC_LOCKED, _REC_PENDING}
        )
        if current + float(add_credit or 0) > float(maximum):
            raise AppException("VALIDATION_ERROR", f"超过本批次选课学分上限 {maximum}")


def create_batch(user, body) -> dict:
    from app.models import AaSelectionBatch, AaTerm
    from . import academic_affairs_archive_service as archive_service

    term_id = getattr(body, "termId", None)
    if not term_id:
        raise AppException("VALIDATION_ERROR", "选课批次必须绑定正式学期termId")
    with _core.session() as db:
        _core._require_manage_scope(_core._ctx(user, db))
        term = db.query(AaTerm).filter(
            AaTerm.id == int(term_id),
            AaTerm.tenant_id == _core._tid(),
            AaTerm.is_deleted.is_(False),
        ).first()
        if not term:
            raise not_found("学期不存在")
        archive_service.guard_term_writable(db, term.id)
        name = str(getattr(body, "batchName", None) or "").strip()
        if not name:
            raise AppException("VALIDATION_ERROR", "批次名称必填")
        start = _core._parse_dt(getattr(body, "selectStartAt", None))
        end = _core._parse_dt(getattr(body, "selectEndAt", None))
        if start and end and end <= start:
            raise AppException("VALIDATION_ERROR", "选课结束时间必须晚于开始时间")
        row = AaSelectionBatch(
            tenant_id=_core._tid(),
            batch_name=name,
            term_id=term.id,
            select_start_at=start,
            select_end_at=end,
            apply_scope_json=(
                json.dumps(body.applyScope, ensure_ascii=False)
                if getattr(body, "applyScope", None) else None
            ),
            rule_json=(
                json.dumps(body.rule, ensure_ascii=False)
                if getattr(body, "rule", None) else None
            ),
            remark=getattr(body, "remark", None),
            status=_BATCH_DRAFT,
        )
        db.add(row)
        db.flush()
        _core._audit(db, row.id, "SELECTION_BATCH_CREATE", f"建批次 {name};termId={term.id}")
        db.commit()
        return _core._batch_dto(row)


def publish_batch(user, batch_id) -> dict:
    from app.models import AaSelectionCourse

    with _core.session() as db:
        _core._require_manage_scope(_core._ctx(user, db))
        batch = db.query(type(_core._get_batch(db, int(batch_id)))).filter_by(id=int(batch_id)).with_for_update().first()
        _guard_batch_writable(db, batch)
        if batch.status != _BATCH_DRAFT:
            raise _core._invalid(f"仅 DRAFT 批次可发布，当前 {batch.status}")
        courses = db.query(AaSelectionCourse).filter(
            AaSelectionCourse.batch_id == batch.id,
            AaSelectionCourse.tenant_id == _core._tid(),
            AaSelectionCourse.status == _COURSE_OPEN,
            AaSelectionCourse.is_deleted.is_(False),
        ).all()
        if not courses:
            raise AppException("VALIDATION_ERROR", "批次未配置任何有效可选课程，不可发布")
        invalid = [row for row in courses if int(row.capacity or 0) <= 0 or int(row.min_capacity or 0) < 0]
        if invalid:
            raise AppException(
                "DATA_CONFLICT",
                f"有 {len(invalid)} 门课程容量或开班下限配置无效",
                details={"selectionCourseIds": [str(row.id) for row in invalid]},
                http_status=409,
            )
        batch.status = _BATCH_PUBLISHED
        _core._audit(db, batch.id, "SELECTION_BATCH_PUBLISH", f"发布批次；课程{len(courses)}门")
        db.commit()
        return _core._batch_dto(batch)


def open_batch(user, batch_id) -> dict:
    with _core.session() as db:
        _core._require_manage_scope(_core._ctx(user, db))
        batch = _core._get_batch(db, int(batch_id))
        _guard_batch_writable(db, batch)
        if batch.status != _BATCH_PUBLISHED:
            raise _core._invalid(f"仅 PUBLISHED 批次可开选，当前 {batch.status}")
        batch.status = _BATCH_OPEN
        _core._audit(db, batch.id, "SELECTION_BATCH_OPEN", "开选")
        db.commit()
        return _core._batch_dto(batch)


def close_batch(user, batch_id) -> dict:
    with _core.session() as db:
        _core._require_manage_scope(_core._ctx(user, db))
        batch = _core._get_batch(db, int(batch_id))
        _guard_batch_writable(db, batch)
        if batch.status != _BATCH_OPEN:
            raise _core._invalid(f"仅 OPEN 批次可截止，当前 {batch.status}")
        active_round = _active_round(db, batch.id)
        if active_round:
            raise _core._invalid(f"第{active_round.round_no}轮仍在开放，请先关闭轮次")
        batch.status = _BATCH_CLOSED
        _core._audit(db, batch.id, "SELECTION_BATCH_CLOSE", "截止选课")
        db.commit()
        return _core._batch_dto(batch)


def save_rule(user, batch_id, rule) -> dict:
    with _core.session() as db:
        _core._require_manage_scope(_core._ctx(user, db))
        batch = _core._get_batch(db, int(batch_id))
        _guard_batch_writable(db, batch)
        if batch.status not in {_BATCH_DRAFT, _BATCH_PUBLISHED}:
            raise _core._invalid("仅 DRAFT/PUBLISHED 批次可改规则")
        batch.rule_json = json.dumps(rule, ensure_ascii=False) if rule else None
        _core._audit(db, batch.id, "SELECTION_RULE_UPDATE", "保存选课规则")
        db.commit()
        return _core._batch_dto(batch)


def add_course(user, batch_id, body) -> dict:
    from app.models import AaCourse, AaSelectionCourse, AaTeachingTask, AaTeachingTaskBatch

    with _core.session() as db:
        _core._require_manage_scope(_core._ctx(user, db))
        batch = _core._get_batch(db, int(batch_id))
        _guard_batch_writable(db, batch)
        if batch.status not in {_BATCH_DRAFT, _BATCH_PUBLISHED}:
            raise _core._invalid("仅 DRAFT/PUBLISHED 批次可增课程")
        course = db.query(AaCourse).filter(
            AaCourse.id == int(body.courseId),
            AaCourse.tenant_id == _core._tid(),
            AaCourse.is_deleted.is_(False),
        ).first()
        if not course:
            raise not_found("课程不存在")
        if not str(course.course_code or "").strip():
            raise AppException("DATA_CONFLICT", "课程缺少稳定courseCode，不能进入选课供给", http_status=409)
        task_id = int(body.teachingTaskId) if getattr(body, "teachingTaskId", None) else None
        teacher_key = teacher_name = None
        if task_id:
            task = db.query(AaTeachingTask).filter(
                AaTeachingTask.id == task_id,
                AaTeachingTask.tenant_id == _core._tid(),
                AaTeachingTask.is_deleted.is_(False),
            ).first()
            if not task:
                raise not_found("教学任务不存在")
            task_batch = db.query(AaTeachingTaskBatch).filter(
                AaTeachingTaskBatch.id == task.batch_id,
                AaTeachingTaskBatch.tenant_id == _core._tid(),
                AaTeachingTaskBatch.is_deleted.is_(False),
            ).first()
            if not task_batch or int(task_batch.term_id or 0) != int(batch.term_id):
                raise AppException("DATA_CONFLICT", "教学任务与选课批次不属于同一学期", http_status=409)
            if int(task.course_id or 0) != int(course.id):
                raise AppException("DATA_CONFLICT", "教学任务课程与所选课程版本不一致", http_status=409)
            teacher_key, teacher_name = task.teacher_key, task.teacher_name
        duplicate = db.query(AaSelectionCourse).filter(
            AaSelectionCourse.tenant_id == _core._tid(),
            AaSelectionCourse.batch_id == batch.id,
            AaSelectionCourse.course_id == course.id,
            AaSelectionCourse.teaching_task_id == task_id,
            AaSelectionCourse.is_deleted.is_(False),
        ).first()
        if duplicate:
            raise AppException("VALIDATION_ERROR", "该课程（教学班）已在本批次")
        capacity = int(getattr(body, "capacity", 0) or 0)
        minimum = int(getattr(body, "minCapacity", 0) or 0)
        if capacity <= 0 or minimum < 0 or minimum > capacity:
            raise AppException("VALIDATION_ERROR", "容量须大于0，开班下限须在0至容量之间")
        row = AaSelectionCourse(
            tenant_id=_core._tid(),
            batch_id=batch.id,
            course_id=course.id,
            course_name=course.course_name,
            teaching_task_id=task_id,
            teacher_key=teacher_key,
            teacher_name=teacher_name,
            credit=course.credit,
            capacity=capacity,
            min_capacity=minimum,
            selected_count=0,
            status=_COURSE_OPEN,
        )
        db.add(row)
        db.flush()
        _core._audit(db, batch.id, "SELECTION_COURSE_ADD", f"增课程 {row.course_name};courseId={course.id}")
        db.commit()
        return _core._course_dto(row)


def update_course(user, course_id, body) -> dict:
    with _core.session() as db:
        _core._require_manage_scope(_core._ctx(user, db))
        course = _core._get_course(db, int(course_id))
        batch = _core._get_batch(db, int(course.batch_id))
        _guard_batch_writable(db, batch)
        if batch.status in {_BATCH_LOCKED, _BATCH_ARCHIVED}:
            raise _core._invalid("批次已锁定，不可改课程容量/规则")
        if getattr(body, "capacity", None) is not None:
            capacity = int(body.capacity)
            if capacity <= 0 or capacity < int(course.selected_count or 0):
                raise AppException("VALIDATION_ERROR", f"容量须大于0且不可小于已选人数 {course.selected_count}")
            course.capacity = capacity
        if getattr(body, "minCapacity", None) is not None:
            minimum = int(body.minCapacity)
            if minimum < 0 or minimum > int(course.capacity or 0):
                raise AppException("VALIDATION_ERROR", "开班下限须在0至容量之间")
            course.min_capacity = minimum
        _core._audit(db, batch.id, "SELECTION_COURSE_UPDATE", f"改课程 {course.course_name} 容量/下限")
        db.commit()
        return _core._course_dto(course)


def cancel_course(user, course_id, reason="人数不足取消开课") -> dict:
    from app.models import AaSelectionRecord

    with _core.session() as db:
        _core._require_manage_scope(_core._ctx(user, db))
        course = _core._get_course(db, int(course_id))
        batch = _core._get_batch(db, int(course.batch_id))
        _guard_batch_writable(db, batch)
        if batch.status != _BATCH_CLOSED:
            raise _core._invalid("仅 CLOSED 批次可取消低人数课程")
        if course.status == _COURSE_CANCELLED:
            return _core._course_dto(course)
        course.status = _COURSE_CANCELLED
        cancelled = db.query(AaSelectionRecord).filter(
            AaSelectionRecord.selection_course_id == course.id,
            AaSelectionRecord.tenant_id == _core._tid(),
            AaSelectionRecord.status.in_([_REC_SELECTED, _REC_PENDING]),
            AaSelectionRecord.is_deleted.is_(False),
        ).update({AaSelectionRecord.status: _REC_COURSE_CANCELLED}, synchronize_session=False)
        course.selected_count = 0
        _core._audit(
            db,
            batch.id,
            "SELECTION_COURSE_CANCEL",
            f"取消开课 {course.course_name};records={cancelled};reason={str(reason or '')[:200]}",
        )
        db.commit()
        return _core._course_dto(course)


def student_courses(user, batch_id=None):
    from app.models import AaSelectionBatch, AaSelectionCourse, AaSelectionRecord

    with _core.session() as db:
        student = _load_student(db)
        batch = _core._get_batch(db, int(batch_id)) if batch_id else db.query(AaSelectionBatch).filter(
            AaSelectionBatch.tenant_id == _core._tid(),
            AaSelectionBatch.status.in_([_BATCH_OPEN, _BATCH_CLOSED]),
            AaSelectionBatch.is_deleted.is_(False),
        ).order_by(AaSelectionBatch.id.desc()).first()
        if not batch:
            return {"batch": None, "items": []}
        active_round = _active_round(db, batch.id)
        if active_round and active_round.mode == "LOTTERY":
            can_enroll = bool(active_round.allow_enroll)
        else:
            can_enroll = batch.status == _BATCH_OPEN and (not active_round or bool(active_round.allow_enroll))
        records = db.query(AaSelectionRecord).filter(
            AaSelectionRecord.tenant_id == _core._tid(),
            AaSelectionRecord.student_id == student.id,
            AaSelectionRecord.batch_id == batch.id,
            AaSelectionRecord.is_deleted.is_(False),
        ).all()
        by_course = {int(row.selection_course_id): row for row in records}
        courses = db.query(AaSelectionCourse).filter(
            AaSelectionCourse.tenant_id == _core._tid(),
            AaSelectionCourse.batch_id == batch.id,
            AaSelectionCourse.status == _COURSE_OPEN,
            AaSelectionCourse.is_deleted.is_(False),
        ).order_by(AaSelectionCourse.id).all()
        items = []
        for course in courses:
            item = _core._course_dto(course)
            record = by_course.get(int(course.id))
            item["myStatus"] = record.status if record else None
            item["myRecordId"] = str(record.id) if record else None
            item["canEnroll"] = can_enroll and (
                record is None or record.status in {_REC_DROPPED, _REC_LOST, _REC_COURSE_CANCELLED}
            )
            item["roundId"] = str(active_round.id) if active_round else None
            item["roundMode"] = active_round.mode if active_round else "FCFS"
            items.append(item)
        return {
            "batch": _core._batch_dto(batch),
            "round": (
                {
                    "roundId": str(active_round.id),
                    "roundNo": active_round.round_no,
                    "roundName": active_round.round_name,
                    "mode": active_round.mode,
                    "allowEnroll": bool(active_round.allow_enroll),
                    "allowDrop": bool(active_round.allow_drop),
                }
                if active_round else None
            ),
            "items": items,
        }


def student_enroll(user, body):
    from app.models import AaSelectionRecord

    with _core.session() as db:
        student = _load_student(db)
        course = db.query(type(_core._get_course(db, int(body.selectionCourseId)))).filter_by(
            id=int(body.selectionCourseId)
        ).with_for_update().first()
        batch = _core._get_batch(db, int(course.batch_id))
        _guard_batch_writable(db, batch)
        if course.status != _COURSE_OPEN:
            raise _core._invalid("课程已取消或不可选")
        active_round = _active_round(db, batch.id)
        if active_round and not active_round.allow_enroll:
            raise _core._invalid("当前轮次不允许选课")
        allow_reselect_closed = batch.status == _BATCH_CLOSED and active_round is not None
        my_records = db.query(AaSelectionRecord).filter(
            AaSelectionRecord.tenant_id == _core._tid(),
            AaSelectionRecord.student_id == student.id,
            AaSelectionRecord.batch_id == batch.id,
            AaSelectionRecord.is_deleted.is_(False),
        ).all()
        _validate_enroll(
            db,
            batch,
            course,
            student,
            my_records,
            float(course.credit or 0),
            allow_reselect_closed=allow_reselect_closed,
        )

        lottery = bool(active_round and active_round.mode == "LOTTERY")
        status = _REC_PENDING if lottery else _REC_SELECTED
        if not lottery:
            updated = db.query(type(course)).filter(
                type(course).id == course.id,
                type(course).tenant_id == _core._tid(),
                type(course).status == _COURSE_OPEN,
                type(course).selected_count < type(course).capacity,
            ).update({type(course).selected_count: type(course).selected_count + 1}, synchronize_session=False)
            if not updated:
                raise _core._conflict("课程容量已满")

        existing = db.query(AaSelectionRecord).filter(
            AaSelectionRecord.tenant_id == _core._tid(),
            AaSelectionRecord.student_id == student.id,
            AaSelectionRecord.selection_course_id == course.id,
            AaSelectionRecord.is_deleted.is_(False),
        ).first()
        now = datetime.utcnow()
        if existing:
            if existing.status not in {_REC_DROPPED, _REC_LOST, _REC_COURSE_CANCELLED}:
                raise _core._conflict("已存在有效选课记录")
            existing.status = status
            existing.round_id = active_round.id if active_round else None
            existing.enrolled_at = now if status == _REC_SELECTED else None
            existing.dropped_at = None
            existing.drop_reason = None
            existing.adjust_reason = None
            record = existing
        else:
            record = AaSelectionRecord(
                tenant_id=_core._tid(),
                batch_id=batch.id,
                selection_course_id=course.id,
                student_id=student.id,
                student_no=student.student_no,
                student_name=student.real_name,
                course_id=course.course_id,
                course_name=course.course_name,
                credit=course.credit,
                round_id=active_round.id if active_round else None,
                status=status,
                enrolled_at=now if status == _REC_SELECTED else None,
            )
            db.add(record)
        db.flush()
        _core._audit(
            db,
            record.id,
            "SELECTION_ENROLL",
            f"studentNo={student.student_no} course={course.course_name} status={status}",
        )
        db.commit()
        return _core._record_dto(record)


def student_drop(user, body):
    from app.models import AaSelectionCourse, AaSelectionRecord

    with _core.session() as db:
        student = _load_student(db)
        record = db.query(AaSelectionRecord).filter(
            AaSelectionRecord.id == int(body.recordId),
            AaSelectionRecord.tenant_id == _core._tid(),
            AaSelectionRecord.student_id == student.id,
            AaSelectionRecord.is_deleted.is_(False),
        ).with_for_update().first()
        if not record:
            raise not_found("选课记录不存在")
        batch = _core._get_batch(db, int(record.batch_id))
        _guard_batch_writable(db, batch)
        active_round = _active_round(db, batch.id)
        if batch.status != _BATCH_OPEN:
            raise _core._invalid("当前不在退课窗口")
        if active_round and not active_round.allow_drop:
            raise _core._invalid("当前轮次不允许退课")
        if record.status not in {_REC_SELECTED, _REC_PENDING}:
            raise _core._invalid("当前记录不可退课")
        previous = record.status
        record.status = _REC_DROPPED
        record.dropped_at = datetime.utcnow()
        record.drop_reason = str(getattr(body, "reason", None) or "").strip() or None
        if previous == _REC_SELECTED:
            updated = db.query(AaSelectionCourse).filter(
                AaSelectionCourse.id == record.selection_course_id,
                AaSelectionCourse.tenant_id == _core._tid(),
                AaSelectionCourse.selected_count > 0,
            ).update({AaSelectionCourse.selected_count: AaSelectionCourse.selected_count - 1}, synchronize_session=False)
            if not updated:
                raise AppException("DATA_CONFLICT", "课程人数计数异常，退课已取消，请联系教务处", http_status=409)
        _core._audit(db, record.id, "SELECTION_DROP", f"studentNo={student.student_no};from={previous}")
        db.commit()
        return _core._record_dto(record)


def my_selections(user, batch_id=None):
    from app.models import AaSelectionRecord

    with _core.session() as db:
        student = _load_student(db)
        query = db.query(AaSelectionRecord).filter(
            AaSelectionRecord.tenant_id == _core._tid(),
            AaSelectionRecord.student_id == student.id,
            AaSelectionRecord.is_deleted.is_(False),
        )
        if batch_id:
            query = query.filter(AaSelectionRecord.batch_id == int(batch_id))
        return [_core._record_dto(row) for row in query.order_by(AaSelectionRecord.id.desc()).all()]


def student_reselect_guide(user, batch_id=None):
    from app.models import AaSelectionBatch, AaSelectionCourse, AaSelectionRecord

    with _core.session() as db:
        student = _load_student(db)
        query = db.query(AaSelectionRecord).filter(
            AaSelectionRecord.tenant_id == _core._tid(),
            AaSelectionRecord.student_id == student.id,
            AaSelectionRecord.status == _REC_COURSE_CANCELLED,
            AaSelectionRecord.is_deleted.is_(False),
        )
        if batch_id:
            query = query.filter(AaSelectionRecord.batch_id == int(batch_id))
        cancelled = query.all()
        output = []
        for current_batch_id in sorted({int(row.batch_id) for row in cancelled}):
            batch = db.query(AaSelectionBatch).filter(
                AaSelectionBatch.id == current_batch_id,
                AaSelectionBatch.tenant_id == _core._tid(),
                AaSelectionBatch.is_deleted.is_(False),
            ).first()
            if not batch or batch.status != _BATCH_CLOSED:
                continue
            courses = db.query(AaSelectionCourse).filter(
                AaSelectionCourse.batch_id == batch.id,
                AaSelectionCourse.tenant_id == _core._tid(),
                AaSelectionCourse.status == _COURSE_OPEN,
                AaSelectionCourse.is_deleted.is_(False),
            ).all()
            output.append({
                "batch": _core._batch_dto(batch),
                "cancelledRecords": [
                    _core._record_dto(row) for row in cancelled if int(row.batch_id) == batch.id
                ],
                "availableCourses": [
                    _core._course_dto(row)
                    for row in courses
                    if int(row.selected_count or 0) < int(row.capacity or 0)
                ],
            })
        return output


def lock_batch(user, batch_id) -> dict:
    from app.models import AaSelectionRecord

    with _core.session() as db:
        _core._require_manage_scope(_core._ctx(user, db))
        batch = _core._get_batch(db, int(batch_id))
        _guard_batch_writable(db, batch)
        if batch.status == _BATCH_LOCKED:
            return _core._batch_dto(batch)
        if batch.status != _BATCH_CLOSED:
            raise _core._invalid(f"仅 CLOSED 批次可锁定，当前 {batch.status}")
        validation = validate_selection_lock(db, batch)
        if not validation.get("valid"):
            issues = list(validation.get("issues") or [])
            messages = [str(item.get("message") or item) for item in issues[:8]]
            raise AppException(
                "DATA_CONFLICT",
                "选课名单一致性检查未通过：" + "；".join(messages),
                details=validation,
                http_status=409,
            )
        claimed = db.query(AaSelectionRecord).filter(
            AaSelectionRecord.batch_id == batch.id,
            AaSelectionRecord.tenant_id == _core._tid(),
            AaSelectionRecord.status == _REC_SELECTED,
            AaSelectionRecord.is_deleted.is_(False),
        ).update({AaSelectionRecord.status: _REC_LOCKED}, synchronize_session=False)
        if int(claimed or 0) != int(validation.get("selectedRecordCount") or 0):
            db.rollback()
            raise AppException("APPROVAL_VERSION_CONFLICT", "锁定期间选课名单已变化，请刷新后重试", http_status=409)
        apply_locked_roster_projection(db, validation)
        batch.status = _BATCH_LOCKED
        batch.locked_at = datetime.utcnow()
        _core._audit(
            db,
            batch.id,
            "SELECTION_BATCH_LOCK",
            f"records={claimed};tasks={len(validation.get('taskStudentCounts') or {})}",
        )
        db.commit()
        return _core._batch_dto(batch)


def adjust_record(user, record_id, reason) -> dict:
    from app.models import AaSelectionCourse, AaSelectionRecord

    reason_text = str(reason or "").strip()
    if len(reason_text) < 5:
        raise AppException("VALIDATION_ERROR", "调整原因必填且不少于5字")
    with _core.session() as db:
        _core._require_manage_scope(_core._ctx(user, db))
        record = db.query(AaSelectionRecord).filter(
            AaSelectionRecord.id == int(record_id),
            AaSelectionRecord.tenant_id == _core._tid(),
            AaSelectionRecord.is_deleted.is_(False),
        ).with_for_update().first()
        if not record:
            raise not_found("选课记录不存在")
        if record.status != _REC_LOCKED:
            raise _core._invalid("仅 LOCKED 记录可人工调整")
        course = db.query(AaSelectionCourse).filter(
            AaSelectionCourse.id == int(record.selection_course_id),
            AaSelectionCourse.tenant_id == _core._tid(),
            AaSelectionCourse.is_deleted.is_(False),
        ).with_for_update().first()
        if not course:
            raise not_found("选课课程不存在")
        batch = _core._get_batch(db, int(record.batch_id))
        _guard_batch_writable(db, batch)
        if batch.status != _BATCH_LOCKED:
            raise _core._invalid(f"仅 LOCKED 批次可人工调整，当前 {batch.status}")
        if not course.teaching_task_id:
            raise AppException("DATA_CONFLICT", "该课程未关联教学任务，无法生成新正式名单版本", http_status=409)
        teaching_class = teaching_class_service.ensure_teaching_class_for_task(
            db,
            int(course.teaching_task_id),
            initialize_admin_roster=False,
        )
        consumers = consumer_counts(db, teaching_class_id=int(teaching_class.id))
        if int(consumers.get("TOTAL") or 0) > 0:
            raise AppException(
                "DATA_CONFLICT",
                "正式名单已被考勤、考务或成绩使用，不可直接退课；请先退回下游任务并走名单换版流程",
                details={"consumers": consumers, "teachingClassId": str(teaching_class.id)},
                http_status=409,
            )
        updated = db.query(AaSelectionRecord).filter(
            AaSelectionRecord.id == record.id,
            AaSelectionRecord.tenant_id == _core._tid(),
            AaSelectionRecord.status == _REC_LOCKED,
        ).update({
            AaSelectionRecord.status: _REC_DROPPED,
            AaSelectionRecord.dropped_at: datetime.utcnow(),
            AaSelectionRecord.adjust_reason: reason_text,
        }, synchronize_session=False)
        if not updated:
            db.rollback()
            raise AppException("APPROVAL_VERSION_CONFLICT", "名单已被他人调整，请刷新", http_status=409)
        db.query(AaSelectionCourse).filter(
            AaSelectionCourse.id == course.id,
            AaSelectionCourse.tenant_id == _core._tid(),
            AaSelectionCourse.selected_count > 0,
        ).update({AaSelectionCourse.selected_count: AaSelectionCourse.selected_count - 1}, synchronize_session=False)
        db.flush()
        projection = roster_projection.project_selection_course_locked(
            db,
            int(course.id),
            reason=f"锁定名单人工退课：{reason_text}",
        )
        _core._audit(
            db,
            record.id,
            "SELECTION_RECORD_ADJUST",
            (
                f"人工调整退课：{reason_text};teachingClassId={projection['teachingClassId']};"
                f"rosterVersionId={projection['rosterVersionId']};members={projection['memberCount']}"
            ),
        )
        db.commit()
        return {
            "recordId": str(record.id),
            "status": _REC_DROPPED,
            "teachingClassId": projection["teachingClassId"],
            "rosterVersionId": projection["rosterVersionId"],
            "rosterVersionNo": projection["versionNo"],
            "memberCount": projection["memberCount"],
        }


def archive_batch(user, batch_id) -> dict:
    with _core.session() as db:
        _core._require_manage_scope(_core._ctx(user, db))
        batch = _core._get_batch(db, int(batch_id))
        _guard_batch_writable(db, batch)
        if batch.status == _BATCH_ARCHIVED:
            return _core._batch_dto(batch)
        if batch.status != _BATCH_LOCKED:
            raise _core._invalid(f"仅 LOCKED 批次可归档，当前 {batch.status}")
        batch.status = _BATCH_ARCHIVED
        _core._audit(db, batch.id, "SELECTION_BATCH_ARCHIVE", "正式名单锁定后归档")
        db.commit()
        return _core._batch_dto(batch)


def run_time_tick(user):
    from app.models import AaSelectionBatch

    with _core.session() as db:
        _core._require_manage_scope(_core._ctx(user, db))
        now = datetime.utcnow()
        opened = closed = skipped = 0
        candidates = db.query(AaSelectionBatch).filter(
            AaSelectionBatch.tenant_id == _core._tid(),
            AaSelectionBatch.status.in_([_BATCH_PUBLISHED, _BATCH_OPEN]),
            AaSelectionBatch.is_deleted.is_(False),
        ).with_for_update().all()
        for batch in candidates:
            try:
                _guard_batch_writable(db, batch)
            except AppException:
                skipped += 1
                continue
            if (
                batch.status == _BATCH_PUBLISHED
                and batch.select_start_at is not None
                and batch.select_start_at <= now
            ):
                batch.status = _BATCH_OPEN
                _core._audit(db, batch.id, "SELECTION_BATCH_AUTO_OPEN", "定时开选")
                opened += 1
            elif (
                batch.status == _BATCH_OPEN
                and batch.select_end_at is not None
                and batch.select_end_at <= now
                and not _active_round(db, batch.id)
            ):
                batch.status = _BATCH_CLOSED
                _core._audit(db, batch.id, "SELECTION_BATCH_AUTO_CLOSE", "定时截止")
                closed += 1
        db.commit()
        return {"opened": opened, "closed": closed, "skippedArchivedTerms": skipped, "tickAt": now.isoformat()}
