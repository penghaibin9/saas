"""安全教育：课程配置、学生真实学习和教师范围内审核。

同一实习记录与课程只保留一条完成记录。课程版本升级复用该记录并把旧结果
写入 append-only 审计，避免唯一键冲突；多条进行中实习时，学生读取列表必须
显式选择 batchId，按课程/完成记录办理时再由服务端反查并校验本人批次。
"""
from __future__ import annotations

import hashlib
from datetime import datetime

from sqlalchemy import select

from app.core.exceptions import AppException, not_found
from app.models import (
    InternshipAuditTrail, InternshipRecord, InternshipSafetyCompletion,
    InternshipSafetyCourse,
)
from app.services.db_service import _as_id, _tid, session


def _hash(value: str) -> str:
    return hashlib.sha256((value or "").encode("utf-8")).hexdigest()


def _audit(db, row, action, user=None, detail=None):
    db.add(InternshipAuditTrail(
        tenant_id=_tid(), target_id=row.id, target_type="INTERNSHIP_SAFETY",
        action=action, operator_name=(user or {}).get("realName") or "系统",
        detail_json=detail or {}, occurred_at=datetime.utcnow()))


def _completion_row(row):
    if not row:
        return None
    return {
        "id": str(row.id), "internshipId": str(row.internship_id),
        "batchId": str(row.batch_id or ""), "courseId": str(row.course_id),
        "courseVersion": row.course_version, "status": row.status,
        "startedAt": row.started_at, "submittedAt": row.submitted_at,
        "completedAt": row.completed_at,
        "studiedMinutes": int(row.studied_minutes or 0),
        "attemptCount": int(row.attempt_count or 0), "score": row.score,
        "passed": bool(row.passed),
        "commitmentConfirmed": bool(row.commitment_confirmed),
        "commitmentAt": row.commitment_at, "reviewedAt": row.reviewed_at,
        "version": int(row.version or 0),
    }


def _course_row(course, completion=None):
    current = bool(
        completion and
        str(completion.course_version or "") == str(course.course_version or ""))
    effective = completion if current else None
    return {
        "id": str(course.id), "batchId": str(course.batch_id or ""),
        "title": course.title, "status": course.status,
        "courseVersion": course.course_version,
        "requiredMinutes": int(course.required_minutes or 0),
        "passingScore": int(course.passing_score or 0),
        "maxAttempts": int(course.max_attempts or 0),
        "requireCommitment": bool(course.require_commitment),
        "contentSnapshot": course.content_snapshot,
        "contentHash": _hash(course.content_snapshot or ""),
        "completionStatus": effective.status if effective else "NOT_STARTED",
        "studiedMinutes": int(effective.studied_minutes or 0) if effective else 0,
        "remainingAttempts": max(
            0, int(course.max_attempts or 0) - int(effective.attempt_count or 0)
        ) if effective else int(course.max_attempts or 0),
        "commitmentConfirmed": bool(effective and effective.commitment_confirmed),
        "currentVersion": current or completion is None,
        "blocksOnboard": not effective or effective.status != "PASSED",
    }


def _completion_query(internship_id, course_id):
    return select(InternshipSafetyCompletion).where(
        InternshipSafetyCompletion.tenant_id == _tid(),
        InternshipSafetyCompletion.internship_id == internship_id,
        InternshipSafetyCompletion.course_id == course_id,
        InternshipSafetyCompletion.is_deleted.is_(False),
    )


def _my_student(db, user):
    from app.services.mobile_student_service import _require_student, resolve_student
    student = resolve_student(db, _require_student(user))
    if not student:
        raise AppException("NO_PERMISSION", "无法解析当前登录学生身份")
    return student


def _my_context(db, user, *, batch_id=None, for_write=True):
    from app.modules.internship.services.internship_record_resolver import (
        resolve_student_internship_context,
    )
    student = _my_student(db, user)
    ctx = resolve_student_internship_context(
        db, student=student, batch_id=batch_id, for_write=for_write)
    if not ctx.record:
        raise AppException("DATA_CONFLICT", ctx.message or "当前没有可操作的实习记录")
    if for_write and ctx.mode != "active":
        raise AppException("DATA_CONFLICT", "写操作只能针对进行中的实习批次")
    return student, ctx.record, ctx


def _course_and_context(db, course_id, user, *, for_write=True):
    course = db.get(InternshipSafetyCourse, _as_id(course_id))
    if (not course or course.tenant_id != _tid() or course.is_deleted or
            course.status != "ACTIVE" or not course.batch_id):
        raise not_found("当前批次安全教育课程不存在")
    student, record, ctx = _my_context(
        db, user, batch_id=course.batch_id, for_write=for_write)
    if record.batch_id != course.batch_id:
        raise AppException("NO_PERMISSION", "该课程不属于当前学生选择的实习批次")
    return course, student, record, ctx


def _reset_for_course_version(db, row, course, user=None, *, start=False):
    before = {
        "courseVersion": row.course_version,
        "courseContentHash": row.course_content_hash,
        "status": row.status,
        "startedAt": row.started_at.isoformat() if row.started_at else None,
        "submittedAt": row.submitted_at.isoformat() if row.submitted_at else None,
        "completedAt": row.completed_at.isoformat() if row.completed_at else None,
        "studiedMinutes": int(row.studied_minutes or 0),
        "attemptCount": int(row.attempt_count or 0), "score": row.score,
        "passed": bool(row.passed),
        "commitmentConfirmed": bool(row.commitment_confirmed),
        "commitmentAt": row.commitment_at.isoformat() if row.commitment_at else None,
        "reviewedByName": row.reviewed_by_name,
        "reviewedAt": row.reviewed_at.isoformat() if row.reviewed_at else None,
        "recordVersion": int(row.version or 0),
    }
    row.course_version = course.course_version
    row.course_content_snapshot = course.content_snapshot
    row.course_content_hash = _hash(course.content_snapshot or "")
    row.started_at = datetime.utcnow() if start else None
    row.submitted_at = None
    row.completed_at = None
    row.studied_minutes = 0
    row.answer_snapshot = None
    row.attempt_count = 0
    row.score = None
    row.passed = False
    row.commitment_confirmed = False
    row.commitment_at = None
    row.commitment_content_hash = None
    row.commitment_device_digest = None
    row.evidence_file_id = None
    row.reviewed_by_name = None
    row.reviewed_by_user_id = None
    row.reviewed_at = None
    row.status = "IN_PROGRESS" if start else "NOT_STARTED"
    row.rule_version = course.rule_version
    row.version = int(row.version or 0) + 1
    _audit(db, row, "COURSE_VERSION_RESET", user, {
        "before": before,
        "after": {
            "courseVersion": course.course_version,
            "courseContentHash": row.course_content_hash,
            "status": row.status, "recordVersion": int(row.version or 0),
        },
    })
    return row


def _restart_failed(db, row, course, user=None):
    if int(row.attempt_count or 0) >= int(course.max_attempts or 0):
        raise AppException("DATA_CONFLICT", "已超过最大尝试次数")
    row.status = "IN_PROGRESS"
    row.started_at = datetime.utcnow()
    row.submitted_at = None
    row.completed_at = None
    row.score = None
    row.passed = False
    row.answer_snapshot = None
    row.studied_minutes = 0
    row.commitment_confirmed = False
    row.commitment_at = None
    row.commitment_content_hash = None
    row.commitment_device_digest = None
    row.reviewed_by_name = None
    row.reviewed_by_user_id = None
    row.reviewed_at = None
    row.version = int(row.version or 0) + 1
    _audit(db, row, "RESTART", user, {
        "courseVersion": course.course_version,
        "completedAttempts": int(row.attempt_count or 0),
        "newVersion": int(row.version or 0),
    })
    return row


def list_courses(batch_id, user=None):
    with session() as db:
        rows = db.scalars(select(InternshipSafetyCourse).where(
            InternshipSafetyCourse.tenant_id == _tid(),
            InternshipSafetyCourse.batch_id == _as_id(batch_id),
            InternshipSafetyCourse.is_deleted.is_(False)).order_by(
                InternshipSafetyCourse.id.asc())).all()
        return [_course_row(row) for row in rows]


def create_course(body, user=None):
    b = body or {}
    try:
        required_minutes = int(b.get("requiredMinutes", 60))
        passing_score = int(b.get("passingScore", 80))
        max_attempts = int(b.get("maxAttempts", 3))
    except (TypeError, ValueError):
        raise AppException("VALIDATION_ERROR", "学习时长、通过分和尝试次数必须为整数")
    if required_minutes < 0 or not 0 <= passing_score <= 100 or max_attempts < 1:
        raise AppException("VALIDATION_ERROR", "课程时长须≥0、通过分须0-100、尝试次数须≥1")
    title = str(b.get("title") or "").strip()
    version = str(b.get("courseVersion") or "v1").strip()
    content = str(b.get("contentSnapshot") or "").strip()
    if not title or not content:
        raise AppException("VALIDATION_ERROR", "课程名称和正文快照必填")
    if not b.get("batchId"):
        raise AppException("VALIDATION_ERROR", "安全教育课程必须关联实习批次")
    with session() as db:
        from app.models import InternshipBatch
        batch = db.get(InternshipBatch, _as_id(b["batchId"]))
        if not batch or batch.tenant_id != _tid() or batch.is_deleted:
            raise not_found("实习批次不存在")
        if batch.status not in ("DRAFT", "RUNNING"):
            raise AppException("DATA_CONFLICT", "已结束、归档或作废批次不能新增课程")
        duplicate = db.scalars(select(InternshipSafetyCourse).where(
            InternshipSafetyCourse.tenant_id == _tid(),
            InternshipSafetyCourse.batch_id == batch.id,
            InternshipSafetyCourse.title == title,
            InternshipSafetyCourse.course_version == version,
            InternshipSafetyCourse.is_deleted.is_(False))).first()
        if duplicate:
            raise AppException("DATA_CONFLICT", "当前批次已有同名同版本安全课程")
        row = InternshipSafetyCourse(
            tenant_id=_tid(), batch_id=batch.id, title=title,
            course_version=version, required_minutes=required_minutes,
            passing_score=passing_score, max_attempts=max_attempts,
            require_commitment=bool(b.get("requireCommitment", True)),
            content_snapshot=content, material_file_ids=b.get("materialFileIds") or [],
            status=b.get("status") or "ACTIVE")
        db.add(row)
        db.flush()
        _audit(db, row, "COURSE_CREATE", user, {
            "courseVersion": row.course_version, "batchId": str(batch.id),
            "contentHash": _hash(content), "version": int(row.version or 0),
        })
        db.commit()
        return _course_row(row)


def list_my_courses(user, batch_id=None):
    with session() as db:
        _, record, _ = _my_context(db, user, batch_id=batch_id, for_write=False)
        courses = db.scalars(select(InternshipSafetyCourse).where(
            InternshipSafetyCourse.tenant_id == _tid(),
            InternshipSafetyCourse.batch_id == record.batch_id,
            InternshipSafetyCourse.status == "ACTIVE",
            InternshipSafetyCourse.is_deleted.is_(False)).order_by(
                InternshipSafetyCourse.id.asc())).all()
        completions = db.scalars(select(InternshipSafetyCompletion).where(
            InternshipSafetyCompletion.tenant_id == _tid(),
            InternshipSafetyCompletion.internship_id == record.id,
            InternshipSafetyCompletion.is_deleted.is_(False))).all()
        cmap = {row.course_id: row for row in completions}
        return [_course_row(course, cmap.get(course.id)) for course in courses]


def list_my_completions(user, batch_id=None):
    with session() as db:
        _, record, _ = _my_context(db, user, batch_id=batch_id, for_write=False)
        rows = db.scalars(select(InternshipSafetyCompletion).where(
            InternshipSafetyCompletion.tenant_id == _tid(),
            InternshipSafetyCompletion.internship_id == record.id,
            InternshipSafetyCompletion.is_deleted.is_(False)).order_by(
                InternshipSafetyCompletion.id.asc())).all()
        return [_completion_row(row) for row in rows]


def get_my_course_detail(course_id, user):
    with session() as db:
        course, _, record, _ = _course_and_context(db, course_id, user, for_write=False)
        completion = db.scalar(_completion_query(record.id, course.id))
        return {**_course_row(course, completion), "completion": _completion_row(completion)}


def start_my_course(course_id, user):
    with session() as db:
        course, student, record, _ = _course_and_context(db, course_id, user, for_write=True)
        row = db.scalar(_completion_query(record.id, course.id).with_for_update())
        if row and str(row.course_version or "") != str(course.course_version or ""):
            _reset_for_course_version(db, row, course, user, start=True)
            db.commit()
            return _completion_row(row)
        if row:
            if row.status == "NOT_STARTED":
                row.status = "IN_PROGRESS"
                row.started_at = datetime.utcnow()
                row.version = int(row.version or 0) + 1
                _audit(db, row, "START", user, {
                    "courseVersion": course.course_version,
                    "newVersion": int(row.version or 0),
                })
                db.commit()
            elif row.status == "FAILED":
                _restart_failed(db, row, course, user)
                db.commit()
            return _completion_row(row)
        row = InternshipSafetyCompletion(
            tenant_id=_tid(), internship_id=record.id, batch_id=record.batch_id,
            student_id=student.id, course_id=course.id,
            course_version=course.course_version,
            course_content_snapshot=course.content_snapshot,
            course_content_hash=_hash(course.content_snapshot or ""),
            started_at=datetime.utcnow(), status="IN_PROGRESS",
            review_mode="TEACHER_REVIEW", rule_version=course.rule_version)
        db.add(row)
        db.flush()
        _audit(db, row, "START", user, {"courseVersion": course.course_version})
        db.commit()
        return _completion_row(row)


def submit_my_course(course_id, body, user):
    b = body or {}
    if "passed" in b:
        raise AppException("VALIDATION_ERROR", "学生不得提交 passed 字段")
    with session() as db:
        course, _, record, _ = _course_and_context(db, course_id, user, for_write=True)
        row = db.scalar(_completion_query(record.id, course.id).with_for_update())
        if not row:
            raise not_found("请先开始当前批次安全课程")
        if str(row.course_version or "") != str(course.course_version or ""):
            raise AppException("DATA_CONFLICT", "课程版本已更新，请重新打开并开始最新课程")
        if b.get("expectedVersion") is None or int(b["expectedVersion"]) != int(row.version or 0):
            raise AppException("DATA_CONFLICT", "学习记录版本已变化")
        if row.status != "IN_PROGRESS":
            raise AppException("DATA_CONFLICT", "仅学习中的课程可提交")
        if int(row.attempt_count or 0) >= int(course.max_attempts or 0):
            raise AppException("DATA_CONFLICT", "已超过最大尝试次数")
        if course.require_commitment and not row.commitment_confirmed:
            raise AppException("DATA_CONFLICT", "请先确认安全承诺")
        now = datetime.utcnow()
        elapsed = max(0, int((now - row.started_at).total_seconds() // 60)) if row.started_at else 0
        try:
            claimed = max(0, int(
                b.get("studiedMinutes") if b.get("studiedMinutes") is not None else elapsed))
        except (TypeError, ValueError):
            raise AppException("VALIDATION_ERROR", "学习时长格式错误")
        trusted = min(claimed, elapsed)
        if trusted < int(course.required_minutes or 0):
            raise AppException(
                "DATA_CONFLICT",
                f"可信学习时长不足，应完成 {course.required_minutes} 分钟，当前 {trusted} 分钟")
        row.studied_minutes = trusted
        row.answer_snapshot = b.get("answers") or None
        row.submitted_at = now
        row.attempt_count = int(row.attempt_count or 0) + 1
        row.status = "PENDING_REVIEW"
        row.version = int(row.version or 0) + 1
        _audit(db, row, "SUBMIT", user, {
            "trustedMinutes": trusted, "claimedMinutes": claimed,
            "attempt": int(row.attempt_count or 0), "newVersion": int(row.version or 0),
        })
        db.commit()
        return _completion_row(row)


def commit_my_completion(completion_id, body, user):
    b = body or {}
    if not b.get("contentHash"):
        raise AppException("VALIDATION_ERROR", "承诺正文哈希必填")
    with session() as db:
        student = _my_student(db, user)
        row = db.scalar(select(InternshipSafetyCompletion).where(
            InternshipSafetyCompletion.id == _as_id(completion_id),
            InternshipSafetyCompletion.tenant_id == _tid(),
            InternshipSafetyCompletion.student_id == student.id,
            InternshipSafetyCompletion.is_deleted.is_(False)).with_for_update())
        if not row:
            raise not_found("安全教育完成记录不存在")
        record = db.get(InternshipRecord, row.internship_id)
        if not record or record.student_id != student.id or record.tenant_id != _tid():
            raise AppException("NO_PERMISSION", "该学习记录不属于当前学生")
        _my_context(db, user, batch_id=row.batch_id, for_write=True)
        course = db.get(InternshipSafetyCourse, row.course_id)
        if not course or course.tenant_id != _tid() or course.is_deleted:
            raise not_found("安全教育课程不存在")
        if str(row.course_version or "") != str(course.course_version or ""):
            raise AppException("DATA_CONFLICT", "课程版本已更新，请重新打开并开始最新课程")
        if b.get("expectedVersion") is None or int(b["expectedVersion"]) != int(row.version or 0):
            raise AppException("DATA_CONFLICT", "学习记录版本已变化")
        if str(b.get("contentHash")) != str(row.course_content_hash or ""):
            raise AppException("DATA_CONFLICT", "课程正文已变化，请重新打开最新课程")
        if row.commitment_confirmed:
            return _completion_row(row)
        if row.status != "IN_PROGRESS":
            raise AppException("DATA_CONFLICT", "仅学习中的课程可确认安全承诺")
        row.commitment_confirmed = True
        row.commitment_at = datetime.utcnow()
        row.commitment_content_hash = b["contentHash"]
        row.commitment_device_digest = _hash(str(b.get("deviceDigest") or ""))
        row.version = int(row.version or 0) + 1
        _audit(db, row, "COMMITMENT_CONFIRM", user, {
            "contentHash": row.commitment_content_hash,
            "newVersion": int(row.version or 0),
        })
        db.commit()
        return _completion_row(row)


def teacher_review_completion(completion_id, score=None, action=None, comment=None,
                              expected_version=None, user=None):
    with session() as db:
        row = db.scalar(select(InternshipSafetyCompletion).where(
            InternshipSafetyCompletion.id == _as_id(completion_id),
            InternshipSafetyCompletion.tenant_id == _tid(),
            InternshipSafetyCompletion.is_deleted.is_(False)).with_for_update())
        if not row:
            raise not_found("安全教育完成记录不存在")
        from app.modules.internship.services.internship_scope import assert_internship_record_scope
        assert_internship_record_scope(db, row.internship_id, user, "安全教育审核")
        if expected_version is None or int(expected_version) != int(row.version or 0):
            raise AppException("DATA_CONFLICT", "学习记录版本已变化")
        if row.status != "PENDING_REVIEW":
            raise AppException("DATA_CONFLICT", "仅待审核记录可处理")
        course = db.get(InternshipSafetyCourse, row.course_id)
        if (not course or course.tenant_id != _tid() or course.is_deleted or
                str(row.course_version or "") != str(course.course_version or "")):
            raise AppException("DATA_CONFLICT", "课程版本已更新，旧版本完成记录不可审核通过")
        normalized = str(action or "APPROVE").upper()
        if normalized == "APPROVE":
            try:
                parsed_score = int(score)
            except (TypeError, ValueError):
                raise AppException("VALIDATION_ERROR", "审核分数必须为0-100的整数")
            if not 0 <= parsed_score <= 100:
                raise AppException("VALIDATION_ERROR", "审核分数必须在0-100之间")
            row.score = parsed_score
            row.passed = (
                parsed_score >= int(course.passing_score or 0)
                and int(row.studied_minutes or 0) >= int(course.required_minutes or 0)
                and (not course.require_commitment or row.commitment_confirmed))
            row.status = "PASSED" if row.passed else "FAILED"
        elif normalized == "REJECT":
            if len(str(comment or "").strip()) < 5:
                raise AppException("VALIDATION_ERROR", "驳回原因必填且不少于5字")
            row.passed = False
            row.status = "FAILED"
        else:
            raise AppException("VALIDATION_ERROR", "action 必须为 APPROVE/REJECT")
        row.reviewed_by_name = (user or {}).get("realName") or "系统"
        row.reviewed_by_user_id = str((user or {}).get("userId") or "")
        row.reviewed_at = datetime.utcnow()
        row.completed_at = datetime.utcnow()
        row.version = int(row.version or 0) + 1
        _audit(db, row, "REVIEW", user, {
            "action": normalized, "result": row.status, "score": row.score,
            "comment": str(comment or "").strip(), "newVersion": int(row.version or 0),
        })
        db.commit()
        return _completion_row(row)


def ensure_completion(body, user=None):
    """学校端分配课程；课程升级时复用唯一完成记录并重置为未开始。"""
    b = body or {}
    if not b.get("internshipId") or not b.get("courseId"):
        raise AppException("VALIDATION_ERROR", "internshipId 与 courseId 必填")
    with session() as db:
        from app.modules.internship.services.internship_scope import assert_internship_record_scope
        record = assert_internship_record_scope(db, b["internshipId"], user, "创建安全教育记录")
        course = db.get(InternshipSafetyCourse, _as_id(b["courseId"]))
        if (not course or course.tenant_id != _tid() or course.is_deleted or
                course.status != "ACTIVE" or course.batch_id != record.batch_id):
            raise not_found("当前批次安全教育课程不可用")
        row = db.scalar(_completion_query(record.id, course.id).with_for_update())
        if row:
            if str(row.course_version or "") != str(course.course_version or ""):
                _reset_for_course_version(db, row, course, user, start=False)
                db.commit()
            return _completion_row(row)
        row = InternshipSafetyCompletion(
            tenant_id=_tid(), internship_id=record.id, batch_id=record.batch_id,
            student_id=record.student_id, course_id=course.id,
            course_version=course.course_version,
            course_content_snapshot=course.content_snapshot,
            course_content_hash=_hash(course.content_snapshot or ""),
            status="NOT_STARTED", review_mode="TEACHER_REVIEW",
            rule_version=course.rule_version)
        db.add(row)
        db.flush()
        _audit(db, row, "ASSIGN", user, {"courseVersion": course.course_version})
        db.commit()
        return _completion_row(row)
