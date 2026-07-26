"""选课服务兼容入口。

保留原选课状态机、容量并发控制、补退选和抽签实现，收口三类写风险：
- 新建批次必须绑定未归档正式学期；
- CLOSED→LOCKED 前验证课程、教学任务、学生主档、人数和抽签结果一致；
- LOCKED后人工退课不得作用于已归档批次，也不得破坏已被成绩/考务/考勤消费的官方名单。
"""
from __future__ import annotations

from datetime import datetime

from app.core.exceptions import AppException, not_found

from . import academic_affairs_selection_service as _legacy
from .academic_affairs_teaching_roster_service import (
    apply_locked_roster_projection,
    validate_selection_lock,
)


def __getattr__(name):
    return getattr(_legacy, name)


def create_batch(user, body) -> dict:
    from app.models import AaSelectionBatch
    from app.modules.academic_affairs.services.academic_affairs_archive_service import guard_term_writable

    term_id = getattr(body, "termId", None)
    if not term_id:
        raise AppException("VALIDATION_ERROR", "选课批次必须绑定正式学期termId")
    with _legacy.session() as db:
        _legacy._require_manage_scope(_legacy._ctx(user, db))
        guard_term_writable(db, int(term_id))
        name = (getattr(body, "batchName", None) or "").strip()
        if not name:
            raise AppException("VALIDATION_ERROR", "批次名称必填")
        batch = AaSelectionBatch(
            tenant_id=_legacy._tid(),
            batch_name=name,
            term_id=int(term_id),
            select_start_at=_legacy._parse_dt(getattr(body, "selectStartAt", None)),
            select_end_at=_legacy._parse_dt(getattr(body, "selectEndAt", None)),
            apply_scope_json=(
                __import__("json").dumps(body.applyScope, ensure_ascii=False)
                if getattr(body, "applyScope", None) else None
            ),
            rule_json=(
                __import__("json").dumps(body.rule, ensure_ascii=False)
                if getattr(body, "rule", None) else None
            ),
            remark=getattr(body, "remark", None),
            status=_legacy._BATCH_DRAFT,
        )
        db.add(batch)
        db.flush()
        _legacy._audit(db, batch.id, "SELECTION_BATCH_CREATE", f"建批次 {name}")
        db.commit()
        return _legacy._batch_dto(batch)


def lock_batch(user, batch_id) -> dict:
    from app.models import AaSelectionRecord
    from app.modules.academic_affairs.services.academic_affairs_archive_service import guard_term_writable

    with _legacy.session() as db:
        _legacy._require_manage_scope(_legacy._ctx(user, db))
        batch = _legacy._get_batch(db, int(batch_id))
        guard_term_writable(db, batch.term_id)
        if batch.status == _legacy._BATCH_LOCKED:
            return _legacy._batch_dto(batch)
        if batch.status != _legacy._BATCH_CLOSED:
            raise _legacy._invalid(f"仅 CLOSED 批次可锁定，当前 {batch.status}")

        validation = validate_selection_lock(db, batch)
        if not validation["valid"]:
            messages = [issue["message"] for issue in validation["issues"][:8]]
            suffix = "…" if len(validation["issues"]) > 8 else ""
            raise AppException(
                "DATA_CONFLICT",
                "选课名单一致性检查未通过：" + "；".join(messages) + suffix,
                details=validation,
                http_status=409,
            )

        claimed = db.query(AaSelectionRecord).filter(
            AaSelectionRecord.batch_id == batch.id,
            AaSelectionRecord.tenant_id == _legacy._tid(),
            AaSelectionRecord.status == _legacy._REC_SELECTED,
            AaSelectionRecord.is_deleted.is_(False),
        ).update(
            {AaSelectionRecord.status: _legacy._REC_LOCKED},
            synchronize_session=False,
        )
        if int(claimed or 0) != int(validation["selectedRecordCount"] or 0):
            db.rollback()
            raise AppException(
                "APPROVAL_VERSION_CONFLICT",
                "锁定期间选课名单已发生变化，请刷新后重新检查",
                http_status=409,
            )

        apply_locked_roster_projection(db, validation)
        batch.status = _legacy._BATCH_LOCKED
        batch.locked_at = datetime.utcnow()
        _legacy._audit(
            db,
            batch.id,
            "SELECTION_BATCH_LOCK",
            f"锁定正式名单 records={claimed};tasks={len(validation.get('taskStudentCounts') or {})}",
        )
        db.commit()
        return _legacy._batch_dto(batch)


def _roster_consumers(db, course) -> list[str]:
    """返回已消费该教学任务名单的业务域；当前考勤表无task_id，使用严格快照匹配防止误放行。"""
    from app.models import AaAttendanceSession, AaExamCourse, AaGradeTask, AaTeachingTask, AaTeachingTaskBatch

    if not course.teaching_task_id:
        return []
    task = db.get(AaTeachingTask, int(course.teaching_task_id))
    if not task or task.is_deleted or task.tenant_id != _legacy._tid():
        return ["教学任务已失效"]
    consumers = []
    grade_count = db.query(AaGradeTask).filter(
        AaGradeTask.tenant_id == _legacy._tid(),
        AaGradeTask.teaching_task_id == task.id,
        AaGradeTask.is_deleted.is_(False),
    ).count()
    if grade_count:
        consumers.append(f"成绩任务{grade_count}个")
    exam_count = db.query(AaExamCourse).filter(
        AaExamCourse.tenant_id == _legacy._tid(),
        AaExamCourse.teaching_task_id == task.id,
        AaExamCourse.status != "REMOVED",
        AaExamCourse.is_deleted.is_(False),
    ).count()
    if exam_count:
        consumers.append(f"考试课程{exam_count}个")
    task_batch = db.get(AaTeachingTaskBatch, int(task.batch_id)) if task.batch_id else None
    term_code = None
    if task_batch and task_batch.term_id:
        from app.models import AaTerm
        term = db.get(AaTerm, int(task_batch.term_id))
        if term:
            term_code = f"{term.year_code}-{term.term_no}"
    attendance_query = db.query(AaAttendanceSession).filter(
        AaAttendanceSession.tenant_id == _legacy._tid(),
        AaAttendanceSession.course_name == task.course_name,
        AaAttendanceSession.is_deleted.is_(False),
    )
    if task.class_id:
        attendance_query = attendance_query.filter(AaAttendanceSession.class_id == task.class_id)
    if term_code:
        attendance_query = attendance_query.filter(AaAttendanceSession.term_code == term_code)
    attendance_count = attendance_query.count()
    if attendance_count:
        consumers.append(f"考勤场次{attendance_count}个")
    return consumers


def adjust_record(user, record_id, reason) -> dict:
    """LOCKED后人工退课：仅未归档、未被下游消费的名单可调整。"""
    from app.models import AaSelectionCourse, AaSelectionRecord
    from app.modules.academic_affairs.services.academic_affairs_archive_service import guard_term_writable

    with _legacy.session() as db:
        _legacy._require_manage_scope(_legacy._ctx(user, db))
        reason = (reason or "").strip()
        if len(reason) < 5:
            raise AppException("VALIDATION_ERROR", "调整原因必填且不少于5字")
        record = db.query(AaSelectionRecord).filter(
            AaSelectionRecord.id == int(record_id),
            AaSelectionRecord.tenant_id == _legacy._tid(),
            AaSelectionRecord.is_deleted.is_(False),
        ).first()
        if not record:
            raise not_found("选课记录不存在")
        if record.status != _legacy._REC_LOCKED:
            raise _legacy._invalid("仅 LOCKED 记录可人工调整")
        course = _legacy._get_course(db, int(record.selection_course_id))
        batch = _legacy._get_batch(db, int(record.batch_id))
        guard_term_writable(db, batch.term_id)
        if batch.status == _legacy._BATCH_ARCHIVED:
            raise AppException("DATA_CONFLICT", "选课批次已归档，只读不可调整", http_status=409)
        if batch.status != _legacy._BATCH_LOCKED:
            raise _legacy._invalid(f"仅LOCKED批次可人工调整，当前 {batch.status}")
        consumers = _roster_consumers(db, course)
        if consumers:
            raise AppException(
                "DATA_CONFLICT",
                "正式名单已被下游业务使用，不可直接退课：" + "、".join(consumers) + "。请走名单变更迁移流程。",
                details={"consumers": consumers},
                http_status=409,
            )

        updated = db.query(AaSelectionRecord).filter(
            AaSelectionRecord.id == record.id,
            AaSelectionRecord.tenant_id == _legacy._tid(),
            AaSelectionRecord.status == _legacy._REC_LOCKED,
        ).update({
            AaSelectionRecord.status: _legacy._REC_DROPPED,
            AaSelectionRecord.dropped_at: datetime.utcnow(),
            AaSelectionRecord.adjust_reason: reason,
        }, synchronize_session=False)
        if not updated:
            db.rollback()
            raise AppException("APPROVAL_VERSION_CONFLICT", "名单已被他人调整，请刷新", http_status=409)
        db.query(AaSelectionCourse).filter(
            AaSelectionCourse.id == course.id,
            AaSelectionCourse.tenant_id == _legacy._tid(),
            AaSelectionCourse.selected_count > 0,
        ).update({
            AaSelectionCourse.selected_count: AaSelectionCourse.selected_count - 1,
        }, synchronize_session=False)
        if course.teaching_task_id:
            remaining = db.query(AaSelectionRecord).filter(
                AaSelectionRecord.selection_course_id == course.id,
                AaSelectionRecord.tenant_id == _legacy._tid(),
                AaSelectionRecord.status == _legacy._REC_LOCKED,
                AaSelectionRecord.is_deleted.is_(False),
            ).count()
            from app.models import AaTeachingTask
            task = db.get(AaTeachingTask, int(course.teaching_task_id))
            if task and not task.is_deleted and task.tenant_id == _legacy._tid():
                task.expected_students = int(remaining or 0)
        _legacy._audit(db, record.id, "SELECTION_RECORD_ADJUST", f"人工调整退课：{reason}")
        db.commit()
        return {"recordId": str(record.id), "status": _legacy._REC_DROPPED}


_legacy.create_batch = create_batch
_legacy.lock_batch = lock_batch
_legacy.adjust_record = adjust_record
