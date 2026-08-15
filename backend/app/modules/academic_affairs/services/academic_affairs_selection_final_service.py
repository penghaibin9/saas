"""选课域最终公开入口。

仅修正 canonical Service 静态复审确认的接口与事务问题：
- 发布批次和学生选课显式按 ORM 模型加行锁，禁止 ``type(query_result)`` 反查；
- CLOSED 补选资格只认本人真实 ``COURSE_CANCELLED`` 记录，不信任前端标志；
- 学生退课继续遵守既有 ``EnrollBody.selectionCourseId`` 请求契约；
- 学生可选课程保持 Router 既有 ``{"items": list}`` 返回契约；
- Stage C2：正式选课资格只消费选课动作生效时点的 ``StudentAcademicFact``，
  ``StudentProfile`` 仅继续提供姓名/学号等非学籍身份快照；
- Stage D：不重跑任何规则，仅把 canonical Service 已经做出的拒绝决定附加为
  deterministic ``DecisionTrace``，保留原 code/message/http 契约。

其余业务函数显式委托 ``academic_affairs_selection_service``，不修改模块对象，
不依赖导入顺序安装 monkey patch。
"""
from __future__ import annotations

import importlib
from datetime import datetime
from types import SimpleNamespace

from app.core.exceptions import AppException, not_found

from . import academic_affairs_selection_decision_trace as selection_trace
from . import academic_affairs_selection_preflight_service as batch_preflight_svc

_base = importlib.import_module(
    ".academic_affairs_selection_service",
    package=__package__,
)


def __getattr__(name):
    return getattr(_base, name)


def _selection_academic_identity(db, student, *, effective_at: datetime):
    """解析本次选课决定使用的权威学籍事实；缺失/重叠一律 fail-closed。

    选课资格是一次实时业务决定，因此 ``selection_effective_at`` 就是本次动作的
    服务端时间。后续 StudentProfile 发生转专业/转班/年级更正时，本次决定不会
    再回头读取 current projection；正式历史读取应继续使用 AcademicFact/as_of。
    """
    from .academic_affairs_student_fact_service import resolve_student_academic_fact

    fact = resolve_student_academic_fact(
        db,
        int(student.id),
        as_of=effective_at,
        required=True,
    )
    identity = SimpleNamespace(
        id=int(student.id),
        student_status=fact.student_status,
        college_id=fact.college_id,
        major_id=fact.major_id,
        class_id=fact.class_id,
        grade=fact.grade,
    )
    return identity, fact


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


def batch_preflight(user, batch_id, action: str) -> dict:
    """Admin-visible pure lifecycle preflight; archived-term/config failures become blockers, not writes."""
    from app.models import AaSelectionBatch

    with _base._core.session() as db:
        _base._core._ctx(user, db)
        batch = db.query(AaSelectionBatch).filter(
            AaSelectionBatch.id == int(batch_id),
            AaSelectionBatch.tenant_id == _base._core._tid(),
            AaSelectionBatch.is_deleted.is_(False),
        ).first()
        if not batch:
            raise not_found("选课批次不存在")
        result = batch_preflight_svc.evaluate_batch(db, batch, action)
        try:
            _base._guard_batch_writable(db, batch)
        except AppException as exc:
            result["blockers"].insert(0, {
                "code": str(getattr(exc, "code", "") or "SELECTION_TERM_NOT_WRITABLE"),
                "message": str(getattr(exc, "message", "") or str(exc)),
                "ownerRole": "ACADEMIC_ADMIN",
                "howToResolve": "处理学期归档/只读状态后重新预检",
            })
            result["allowed"] = False
            result["allowedActions"] = ["VIEW"]
        return batch_preflight_svc.public_result(result)


def open_batch(user, batch_id) -> dict:
    from app.models import AaSelectionBatch
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
        batch_preflight_svc.require_batch_action(db, batch, "OPEN")
        batch.status = _base._BATCH_OPEN
        _base._core._audit(db, batch.id, "SELECTION_BATCH_OPEN", "开选；preflight=PASS")
        db.commit()
        return _base._core._batch_dto(batch)


def close_batch(user, batch_id) -> dict:
    from app.models import AaSelectionBatch
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
        batch_preflight_svc.require_batch_action(db, batch, "CLOSE")
        batch.status = _base._BATCH_CLOSED
        _base._core._audit(db, batch.id, "SELECTION_BATCH_CLOSE", "截止选课；preflight=PASS")
        db.commit()
        return _base._core._batch_dto(batch)


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
        batch_preflight_svc.require_batch_action(db, batch, "PUBLISH")
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


def student_preflight(user, body):
    """SelectionPreflight：复用正式资格校验但绝不写记录、容量或审计。"""
    from app.models import AaSelectionBatch, AaSelectionCourse, AaSelectionRecord

    with _base._core.session() as db:
        student = _base._load_student(db)
        evaluated_at = datetime.utcnow()
        academic_identity, academic_fact = _selection_academic_identity(
            db, student, effective_at=evaluated_at
        )
        course = db.query(AaSelectionCourse).filter(
            AaSelectionCourse.id == int(body.selectionCourseId),
            AaSelectionCourse.tenant_id == _base._core._tid(),
            AaSelectionCourse.is_deleted.is_(False),
        ).first()
        if not course:
            raise not_found("可选课程供给项不存在")
        batch = db.query(AaSelectionBatch).filter(
            AaSelectionBatch.id == int(course.batch_id),
            AaSelectionBatch.tenant_id == _base._core._tid(),
            AaSelectionBatch.is_deleted.is_(False),
        ).first()
        if not batch:
            raise not_found("选课批次不存在")

        try:
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
            allow_reselect_closed = (
                batch.status == _base._BATCH_CLOSED
                and any(record.status == _base._REC_COURSE_CANCELLED for record in my_records)
            )
            _base._validate_enroll(
                db, batch, course, academic_identity, my_records,
                float(course.credit or 0),
                allow_reselect_closed=allow_reselect_closed,
            )
        except AppException as exc:
            traced = selection_trace.attach_selection_trace(
                exc, db=db, student=student, course=course, evaluated_at=evaluated_at
            )
            return {
                "allowed": False,
                "selectionCourseId": str(course.id),
                "courseName": course.course_name,
                "code": str(getattr(exc, "code", "") or "DATA_CONFLICT"),
                "message": str(getattr(exc, "message", "") or str(exc)),
                "decisionTrace": getattr(traced, "decision_trace", None),
            }

        return {
            "allowed": True,
            "selectionCourseId": str(course.id),
            "courseName": course.course_name,
            "mode": (
                "LOTTERY"
                if active_round and active_round.mode == "LOTTERY"
                else "FCFS"
            ),
            "academicFactId": str(academic_fact.id),
            "academicFactVersion": academic_fact.version_no,
            "evaluatedAt": evaluated_at.isoformat(),
        }


def student_enroll(user, body):
    from app.models import AaSelectionBatch, AaSelectionCourse, AaSelectionRecord

    with _base._core.session() as db:
        student = _base._load_student(db)
        selection_effective_at = datetime.utcnow()
        academic_identity, academic_fact = _selection_academic_identity(
            db,
            student,
            effective_at=selection_effective_at,
        )
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
        try:
            _base._guard_batch_writable(db, batch)
        except AppException as exc:
            raise selection_trace.attach_selection_trace(
                exc,
                db=db,
                student=student,
                course=course,
                evaluated_at=selection_effective_at,
            ) from exc
        if course.status != _base._COURSE_OPEN:
            exc = _base._core._invalid("课程已取消或不可选")
            raise selection_trace.attach_selection_trace(
                exc,
                db=db,
                student=student,
                course=course,
                evaluated_at=selection_effective_at,
                rule_code="SELECTION_LOCKED",
            )

        my_records = db.query(AaSelectionRecord).filter(
            AaSelectionRecord.tenant_id == _base._core._tid(),
            AaSelectionRecord.student_id == student.id,
            AaSelectionRecord.batch_id == batch.id,
            AaSelectionRecord.is_deleted.is_(False),
        ).all()
        active_round = _base._active_round(db, batch.id)
        if active_round and not active_round.allow_enroll:
            exc = _base._core._invalid("当前轮次不允许选课")
            raise selection_trace.attach_selection_trace(
                exc,
                db=db,
                student=student,
                course=course,
                evaluated_at=selection_effective_at,
                rule_code="SELECTION_LOCKED",
            )

        has_reselect_qualification = any(
            record.status == _base._REC_COURSE_CANCELLED
            for record in my_records
        )
        allow_reselect_closed = (
            batch.status == _base._BATCH_CLOSED
            and has_reselect_qualification
        )
        try:
            _base._validate_enroll(
                db,
                batch,
                course,
                academic_identity,
                my_records,
                float(course.credit or 0),
                allow_reselect_closed=allow_reselect_closed,
            )
        except AppException as exc:
            message = str(getattr(exc, "message", "") or str(exc))
            if "上课时间冲突" in message:
                _base._core._record_conflict_reject(db, batch, course, student, message)
                db.commit()
            raise selection_trace.attach_selection_trace(
                exc,
                db=db,
                student=student,
                course=course,
                evaluated_at=selection_effective_at,
            ) from exc

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
                exc = _base._core._conflict("课程容量已满")
                raise selection_trace.attach_selection_trace(
                    exc,
                    db=db,
                    student=student,
                    course=course,
                    evaluated_at=selection_effective_at,
                    rule_code="COURSE_FULL",
                )

        existing = db.query(AaSelectionRecord).filter(
            AaSelectionRecord.tenant_id == _base._core._tid(),
            AaSelectionRecord.student_id == student.id,
            AaSelectionRecord.selection_course_id == course.id,
            AaSelectionRecord.is_deleted.is_(False),
        ).with_for_update().first()
        if existing:
            if existing.status not in {
                _base._REC_DROPPED,
                _base._REC_LOST,
                _base._REC_COURSE_CANCELLED,
            }:
                exc = _base._core._conflict("已存在有效选课记录")
                raise selection_trace.attach_selection_trace(
                    exc,
                    db=db,
                    student=student,
                    course=course,
                    evaluated_at=selection_effective_at,
                    rule_code="ALREADY_SELECTED",
                )
            existing.status = next_status
            existing.round_id = active_round.id if active_round else None
            existing.enrolled_at = selection_effective_at if next_status == _base._REC_SELECTED else None
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
                enrolled_at=selection_effective_at if next_status == _base._REC_SELECTED else None,
            )
            db.add(record)

        db.flush()
        _base._core._audit(
            db,
            record.id,
            "SELECTION_ENROLL",
            (
                f"studentNo={student.student_no} course={course.course_name} "
                f"status={next_status};reselect={allow_reselect_closed};"
                f"academicFactId={academic_fact.id};academicFactVersion={academic_fact.version_no};"
                f"selectionEffectiveAt={selection_effective_at.isoformat()}"
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


def lock_batch(user, batch_id):
    """CLOSED→LOCKED 使用当前正式名单投影合同，并对批次行加锁。"""
    from app.models import AaSelectionBatch
    from .academic_affairs_teaching_roster_service import (
        apply_locked_roster_projection,
        validate_selection_lock,
    )

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
        if batch.status != _base._BATCH_CLOSED:
            raise _base._core._invalid("仅已关闭选课批次可锁定名单")
        preflight = batch_preflight_svc.require_batch_action(db, batch, "LOCK")
        validation = preflight.get("_rosterValidation") or validate_selection_lock(db, batch)
        if not validation.get("valid"):
            raise AppException(
                "DATA_CONFLICT",
                "选课名单校验未通过",
                details={"issues": list(validation.get("issues") or [])},
                http_status=409,
            )
        apply_locked_roster_projection(db, validation)
        batch.status = _base._BATCH_LOCKED
        batch.locked_at = datetime.utcnow()
        _base._core._audit(
            db,
            batch.id,
            "SELECTION_LOCK",
            "锁定选课名单并生成教学班名单版本",
        )
        db.commit()
        db.refresh(batch)
        return _base._core._batch_dto(batch)


def adjust_record(user, record_id, reason):
    """LOCKED 后人工退课：只改 Selection Final 事实，并在同事务重建 TeachingRoster 版本。"""
    from app.models import AaSelectionBatch, AaSelectionCourse, AaSelectionRecord
    from .academic_affairs_roster_consumer_service import consumer_counts
    from . import academic_affairs_selection_roster_projection_service as roster_projection

    with _base._core.session() as db:
        _base._core._require_manage_scope(_base._core._ctx(user, db))
        reason = (reason or "").strip()
        if len(reason) < 5:
            raise AppException("VALIDATION_ERROR", "调整原因必填且不少于5字")

        record = db.query(AaSelectionRecord).filter(
            AaSelectionRecord.id == int(record_id),
            AaSelectionRecord.tenant_id == _base._core._tid(),
            AaSelectionRecord.is_deleted.is_(False),
        ).with_for_update().first()
        if not record:
            raise not_found("选课记录不存在")
        if record.status != _base._REC_LOCKED:
            raise _base._core._invalid("仅 LOCKED 记录可人工调整")

        course = db.query(AaSelectionCourse).filter(
            AaSelectionCourse.id == int(record.selection_course_id),
            AaSelectionCourse.tenant_id == _base._core._tid(),
            AaSelectionCourse.is_deleted.is_(False),
        ).with_for_update().first()
        if not course:
            raise not_found("选课课程不存在")
        batch = db.query(AaSelectionBatch).filter(
            AaSelectionBatch.id == int(record.batch_id),
            AaSelectionBatch.tenant_id == _base._core._tid(),
            AaSelectionBatch.is_deleted.is_(False),
        ).with_for_update().first()
        if not batch:
            raise not_found("选课批次不存在")
        _base._guard_batch_writable(db, batch)
        if batch.status != _base._BATCH_LOCKED:
            raise _base._core._invalid("仅已锁定选课批次可人工调整正式名单")
        if not course.teaching_task_id:
            raise AppException("DATA_CONFLICT", "选课课程未绑定教学任务，无法调整正式名单", http_status=409)

        counts = consumer_counts(db, teaching_task_id=int(course.teaching_task_id))
        if int(counts.get("TOTAL") or 0) > 0:
            raise _base._core._invalid("该教学任务已冻结考勤、考务或成绩名单，不可直接调整正式名单")

        record.status = _base._REC_DROPPED
        record.dropped_at = datetime.utcnow()
        record.adjust_reason = reason
        updated = db.query(AaSelectionCourse).filter(
            AaSelectionCourse.id == course.id,
            AaSelectionCourse.tenant_id == _base._core._tid(),
            AaSelectionCourse.selected_count > 0,
        ).update({
            AaSelectionCourse.selected_count: AaSelectionCourse.selected_count - 1,
        }, synchronize_session=False)
        if not updated:
            raise AppException(
                "DATA_CONFLICT",
                "课程人数计数异常，人工退课已取消，请联系教务处",
                http_status=409,
            )

        db.flush()
        projection = roster_projection.project_selection_course_locked(
            db,
            int(course.id),
            reason=f"LOCKED 名单人工调整：{reason}",
        )
        _base._core._audit(
            db,
            record.id,
            "SELECTION_RECORD_ADJUST",
            f"人工调整退课：{reason};rosterVersionId={projection['rosterVersionId']}",
        )
        db.commit()
        return {"recordId": str(record.id), "status": _base._REC_DROPPED}
