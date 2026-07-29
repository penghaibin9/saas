"""选课域最终公开入口。

仅修正 canonical Service 静态复审确认的接口与事务问题：
- 发布批次和学生选课显式按 ORM 模型加行锁，禁止 ``type(query_result)`` 反查；
- CLOSED 补选资格只认本人真实 ``COURSE_CANCELLED`` 记录，不信任前端标志；
- 学生退课继续遵守既有 ``EnrollBody.selectionCourseId`` 请求契约；
- 学生可选课程保持 Router 既有 ``{"items": list}`` 返回契约。

其余业务函数显式委托 ``academic_affairs_selection_service``，不修改模块对象，
不依赖导入顺序安装 monkey patch。
"""
from __future__ import annotations

import importlib
from datetime import datetime

from app.core.exceptions import AppException, not_found

_base = importlib.import_module(
    ".academic_affairs_selection_service",
    package=__package__,
)


def __getattr__(name):
    return getattr(_base, name)


def student_courses(user, batch_id=None):
    """保持原 Router 契约：返回批次数组，由 Router 包装为 ``data.items``。"""
    payload = _base.student_courses(user, batch_id)
    if isinstance(payload, list):
        return payload
    if not isinstance(payload, dict) or not payload.get("batch"):
        return []
    return [{
        "batch": payload["batch"],
        "round": payload.get("round"),
        "courses": list(payload.get("items") or []),
    }]


def publish_batch(user, batch_id) -> dict:
    from app.models import AaSelectionBatch, AaSelectionCourse

    with _base._core.session() as db:
        _base._core._require_manage_scope(_base._core._ctx(user, db))
        batch = db.query(AaSelectionBatch).filter(
            AaSelectionBatch.id == int(batch_id),
            AaSelectionBatch.tenant_id == _base._core._tid(),
            AaSelectionBatch.is_deleted.is_(False),
        ).with_for_update().first()
        if not batch:
            raise not_found("选课批次不存在")
        _base._guard_batch_writable(db, batch)
        if batch.status != _base._BATCH_DRAFT:
            raise _base._core._invalid(f"仅 DRAFT 批次可发布，当前 {batch.status}")

        courses = db.query(AaSelectionCourse).filter(
            AaSelectionCourse.batch_id == batch.id,
            AaSelectionCourse.tenant_id == _base._core._tid(),
            AaSelectionCourse.status == _base._COURSE_OPEN,
            AaSelectionCourse.is_deleted.is_(False),
        ).all()
        if not courses:
            raise AppException("VALIDATION_ERROR", "批次未配置任何有效可选课程，不可发布")
        invalid = [
            row for row in courses
            if int(row.capacity or 0) <= 0
            or int(row.min_capacity or 0) < 0
            or int(row.min_capacity or 0) > int(row.capacity or 0)
        ]
        if invalid:
            raise AppException(
                "DATA_CONFLICT",
                f"有 {len(invalid)} 门课程容量或开班下限配置无效",
                details={"selectionCourseIds": [str(row.id) for row in invalid]},
                http_status=409,
            )

        batch.status = _base._BATCH_PUBLISHED
        _base._core._audit(
            db,
            batch.id,
            "SELECTION_BATCH_PUBLISH",
            f"发布批次；课程{len(courses)}门",
        )
        db.commit()
        return _base._core._batch_dto(batch)


def student_enroll(user, body):
    from app.models import AaSelectionBatch, AaSelectionCourse, AaSelectionRecord

    with _base._core.session() as db:
        student = _base._load_student(db)
        course = db.query(AaSelectionCourse).filter(
            AaSelectionCourse.id == int(body.selectionCourseId),
            AaSelectionCourse.tenant_id == _base._core._tid(),
            AaSelectionCourse.is_deleted.is_(False),
        ).with_for_update().first()
        if not course:
            raise not_found("可选课程供给项不存在")
        batch = db.query(AaSelectionBatch).filter(
            AaSelectionBatch.id == int(course.batch_id),
            AaSelectionBatch.tenant_id == _base._core._tid(),
            AaSelectionBatch.is_deleted.is_(False),
        ).with_for_update().first()
        if not batch:
            raise not_found("选课批次不存在")
        _base._guard_batch_writable(db, batch)
        if course.status != _base._COURSE_OPEN:
            raise _base._core._invalid("课程已取消或不可选")

        my_records = db.query(AaSelectionRecord).filter(
            AaSelectionRecord.tenant_id == _base._core._tid(),
            AaSelectionRecord.student_id == student.id,
            AaSelectionRecord.batch_id == batch.id,
            AaSelectionRecord.is_deleted.is_(False),
        ).all()
        active_round = _base._active_round(db, batch.id)
        if active_round and not active_round.allow_enroll:
            raise _base._core._invalid("当前轮次不允许选课")

        has_reselect_qualification = any(
            record.status == _base._REC_COURSE_CANCELLED
            for record in my_records
        )
        allow_reselect_closed = (
            batch.status == _base._BATCH_CLOSED
            and has_reselect_qualification
        )
        _base._validate_enroll(
            db,
            batch,
            course,
            student,
            my_records,
            float(course.credit or 0),
            allow_reselect_closed=allow_reselect_closed,
        )

        lottery = bool(
            batch.status == _base._BATCH_OPEN
            and active_round
            and active_round.mode == "LOTTERY"
        )
        next_status = _base._REC_PENDING if lottery else _base._REC_SELECTED
        if not lottery:
            updated = db.query(AaSelectionCourse).filter(
                AaSelectionCourse.id == course.id,
                AaSelectionCourse.tenant_id == _base._core._tid(),
                AaSelectionCourse.status == _base._COURSE_OPEN,
                AaSelectionCourse.selected_count < AaSelectionCourse.capacity,
            ).update({
                AaSelectionCourse.selected_count: AaSelectionCourse.selected_count + 1,
            }, synchronize_session=False)
            if not updated:
                raise _base._core._conflict("课程容量已满")

        existing = db.query(AaSelectionRecord).filter(
            AaSelectionRecord.tenant_id == _base._core._tid(),
            AaSelectionRecord.student_id == student.id,
            AaSelectionRecord.selection_course_id == course.id,
            AaSelectionRecord.is_deleted.is_(False),
        ).with_for_update().first()
        now = datetime.utcnow()
        if existing:
            if existing.status not in {
                _base._REC_DROPPED,
                _base._REC_LOST,
                _base._REC_COURSE_CANCELLED,
            }:
                raise _base._core._conflict("已存在有效选课记录")
            existing.status = next_status
            existing.round_id = active_round.id if active_round else None
            existing.enrolled_at = now if next_status == _base._REC_SELECTED else None
            existing.dropped_at = None
            existing.drop_reason = None
            existing.adjust_reason = None
            record = existing
        else:
            record = AaSelectionRecord(
                tenant_id=_base._core._tid(),
                batch_id=batch.id,
                selection_course_id=course.id,
                student_id=student.id,
                student_no=student.student_no,
                student_name=student.real_name,
                course_id=course.course_id,
                course_name=course.course_name,
                credit=course.credit,
                round_id=active_round.id if active_round else None,
                status=next_status,
                enrolled_at=now if next_status == _base._REC_SELECTED else None,
            )
            db.add(record)

        db.flush()
        _base._core._audit(
            db,
            record.id,
            "SELECTION_ENROLL",
            (
                f"studentNo={student.student_no} course={course.course_name} "
                f"status={next_status};reselect={allow_reselect_closed}"
            ),
        )
        db.commit()
        return _base._core._record_dto(record)


def student_drop(user, body):
    """兼容既有 EnrollBody：按 selectionCourseId 定位本人记录。"""
    from app.models import AaSelectionBatch, AaSelectionCourse, AaSelectionRecord

    with _base._core.session() as db:
        student = _base._load_student(db)
        course_id = int(body.selectionCourseId)
        record = db.query(AaSelectionRecord).filter(
            AaSelectionRecord.selection_course_id == course_id,
            AaSelectionRecord.tenant_id == _base._core._tid(),
            AaSelectionRecord.student_id == student.id,
            AaSelectionRecord.is_deleted.is_(False),
        ).with_for_update().first()
        if not record:
            raise not_found("选课记录不存在")
        batch = db.query(AaSelectionBatch).filter(
            AaSelectionBatch.id == int(record.batch_id),
            AaSelectionBatch.tenant_id == _base._core._tid(),
            AaSelectionBatch.is_deleted.is_(False),
        ).with_for_update().first()
        if not batch:
            raise not_found("选课批次不存在")
        _base._guard_batch_writable(db, batch)
        if batch.status != _base._BATCH_OPEN:
            raise _base._core._invalid("当前不在退课窗口")
        active_round = _base._active_round(db, batch.id)
        if active_round and not active_round.allow_drop:
            raise _base._core._invalid("当前轮次不允许退课")
        if record.status not in {_base._REC_SELECTED, _base._REC_PENDING}:
            raise _base._core._invalid("当前记录不可退课")

        previous = record.status
        record.status = _base._REC_DROPPED
        record.dropped_at = datetime.utcnow()
        if previous == _base._REC_SELECTED:
            updated = db.query(AaSelectionCourse).filter(
                AaSelectionCourse.id == record.selection_course_id,
                AaSelectionCourse.tenant_id == _base._core._tid(),
                AaSelectionCourse.selected_count > 0,
            ).update({
                AaSelectionCourse.selected_count: AaSelectionCourse.selected_count - 1,
            }, synchronize_session=False)
            if not updated:
                raise AppException(
                    "DATA_CONFLICT",
                    "课程人数计数异常，退课已取消，请联系教务处",
                    http_status=409,
                )

        _base._core._audit(
            db,
            record.id,
            "SELECTION_DROP",
            f"studentNo={student.student_no};from={previous}",
        )
        db.commit()
        return _base._core._record_dto(record)
