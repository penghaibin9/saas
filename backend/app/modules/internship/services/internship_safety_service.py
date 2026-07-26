"""安全教育：课程管理、学生真实学习、教师范围内审核。

一门课程在一条实习记录下只有一条完成记录。课程升级时复用该记录并重置为
新版本，旧版本结果完整写入 append-only 审计，避免唯一键冲突，也避免旧通过
记录冒充新版本通过。
"""
from __future__ import annotations

import hashlib
from datetime import datetime

from sqlalchemy import select

from app.core.exceptions import AppException, not_found
from app.models import (
    InternshipAuditTrail, InternshipSafetyCompletion, InternshipSafetyCourse,
)
from app.services.db_service import _as_id, _tid, session


def _hash(value: str) -> str:
    return hashlib.sha256((value or "").encode("utf-8")).hexdigest()


def _audit(db, x, action, user=None, detail=None):
    db.add(InternshipAuditTrail(
        tenant_id=_tid(), target_id=x.id, target_type="INTERNSHIP_SAFETY",
        action=action, operator_name=(user or {}).get("realName") or "系统",
        detail_json=detail or {}, occurred_at=datetime.utcnow()))


def _completion_row(x):
    if not x:
        return None
    return {
        "id": str(x.id),
        "courseId": str(x.course_id),
        "courseVersion": x.course_version,
        "status": x.status,
        "startedAt": x.started_at,
        "submittedAt": x.submitted_at,
        "completedAt": x.completed_at,
        "studiedMinutes": int(x.studied_minutes or 0),
        "attemptCount": int(x.attempt_count or 0),
        "score": x.score,
        "passed": bool(x.passed),
        "commitmentConfirmed": bool(x.commitment_confirmed),
        "commitmentAt": x.commitment_at,
        "reviewedAt": x.reviewed_at,
        "version": int(x.version or 0),
    }


def _course_row(x, completion=None):
    current = bool(completion and str(completion.course_version or "") == str(x.course_version or ""))
    effective = completion if current else None
    return {
        "id": str(x.id), "title": x.title, "status": x.status,
        "courseVersion": x.course_version, "requiredMinutes": x.required_minutes,
        "passingScore": x.passing_score, "maxAttempts": x.max_attempts,
        "requireCommitment": bool(x.require_commitment),
        "contentSnapshot": x.content_snapshot,
        "contentHash": _hash(x.content_snapshot or ""),
        "completionStatus": effective.status if effective else "NOT_STARTED",
        "studiedMinutes": int(effective.studied_minutes or 0) if effective else 0,
        "remainingAttempts": max(0, int(x.max_attempts or 0) - int(effective.attempt_count or 0)) if effective else int(x.max_attempts or 0),
        "commitmentConfirmed": bool(effective and effective.commitment_confirmed),
        "currentVersion": current or completion is None,
        "blocksOnboard": not effective or effective.status != "PASSED",
    }


def _completion_query(rec_id, course_id):
    return select(InternshipSafetyCompletion).where(
        InternshipSafetyCompletion.tenant_id == _tid(),
        InternshipSafetyCompletion.internship_id == rec_id,
        InternshipSafetyCompletion.course_id == course_id,
        InternshipSafetyCompletion.is_deleted.is_(False),
    )


def _reset_for_course_version(db, x, course, user=None, *, start: bool):
    """在唯一记录上切换课程版本；旧证据写审计后再重置。"""
    before = {
        "courseVersion": x.course_version,
        "courseContentHash": x.course_content_hash,
        "status": x.status,
        "startedAt": x.started_at.isoformat() if x.started_at else None,
        "submittedAt": x.submitted_at.isoformat() if x.submitted_at else None,
        "completedAt": x.completed_at.isoformat() if x.completed_at else None,
        "studiedMinutes": int(x.studied_minutes or 0),
        "attemptCount": int(x.attempt_count or 0),
        "score": x.score,
        "passed": bool(x.passed),
        "commitmentConfirmed": bool(x.commitment_confirmed),
        "commitmentAt": x.commitment_at.isoformat() if x.commitment_at else None,
        "reviewedByName": x.reviewed_by_name,
        "reviewedAt": x.reviewed_at.isoformat() if x.reviewed_at else None,
        "recordVersion": int(x.version or 0),
    }
    x.course_version = course.course_version
    x.course_content_snapshot = course.content_snapshot
    x.course_content_hash = _hash(course.content_snapshot or "")
    x.started_at = datetime.utcnow() if start else None
    x.submitted_at = None
    x.completed_at = None
    x.studied_minutes = 0
    x.answer_snapshot = None
    x.attempt_count = 0
    x.score = None
    x.passed = False
    x.commitment_confirmed = False
    x.commitment_at = None
    x.commitment_content_hash = None
    x.commitment_device_digest = None
    x.evidence_file_id = None
    x.reviewed_by_name = None
    x.reviewed_by_user_id = None
    x.reviewed_at = None
    x.status = "IN_PROGRESS" if start else "NOT_STARTED"
    x.rule_version = course.rule_version
    x.version = int(x.version or 0) + 1
    _audit(db, x, "COURSE_VERSION_RESET", user, {
        "before": before,
        "after": {
            "courseVersion": course.course_version,
            "courseContentHash": x.course_content_hash,
            "status": x.status,
            "recordVersion": int(x.version or 0),
        },
    })
    return x


def _restart_failed(db, x, course, user=None):
    if int(x.attempt_count or 0) >= int(course.max_attempts or 0):
        raise AppException("DATA_CONFLICT", "已超过最大尝试次数")
    x.status = "IN_PROGRESS"
    x.started_at = datetime.utcnow()
    x.submitted_at = None
    x.completed_at = None
    x.score = None
    x.passed = False
    x.answer_snapshot = None
    x.studied_minutes = 0
    x.commitment_confirmed = False
    x.commitment_at = None
    x.commitment_content_hash = None
    x.commitment_device_digest = None
    x.reviewed_by_name = None
    x.reviewed_by_user_id = None
    x.reviewed_at = None
    x.version = int(x.version or 0) + 1
    _audit(db, x, "RESTART", user, {
        "courseVersion": course.course_version,
        "completedAttempts": int(x.attempt_count or 0),
        "newVersion": int(x.version or 0),
    })
    return x


def list_courses(batch_id, user=None):
    with session() as db:
        rows = db.scalars(select(InternshipSafetyCourse).where(
            InternshipSafetyCourse.tenant_id == _tid(),
            InternshipSafetyCourse.batch_id == _as_id(batch_id),
            InternshipSafetyCourse.is_deleted.is_(False))).all()
        return [_course_row(x) for x in rows]


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
    with session() as db:
        x = InternshipSafetyCourse(
            tenant_id=_tid(), batch_id=_as_id(b.get("batchId")) if b.get("batchId") else None,
            title=(b.get("title") or "").strip(), course_version=(b.get("courseVersion") or "v1").strip(),
            required_minutes=required_minutes, passing_score=passing_score,
            max_attempts=max_attempts, require_commitment=bool(b.get("requireCommitment", True)),
            content_snapshot=b.get("contentSnapshot"), material_file_ids=b.get("materialFileIds"),
            status=b.get("status") or "ACTIVE")
        if not x.title or not (x.content_snapshot or "").strip():
            raise AppException("VALIDATION_ERROR", "课程名称和正文快照必填")
        db.add(x)
        db.flush()
        _audit(db, x, "COURSE_CREATE", user, {"courseVersion": x.course_version})
        db.commit()
        return _course_row(x)


def _my_context(db, user):
    from app.services.mobile_student_service import _require_student, resolve_student
    from app.modules.internship.services.internship_record_resolver import resolve_student_internship_context
    stu = resolve_student(db, _require_student(user))
    if not stu:
        raise AppException("NO_PERMISSION", "无法解析当前登录学生身份")
    ctx = resolve_student_internship_context(db, student=stu, for_write=True)
    if ctx.mode != "active" or not ctx.record:
        raise AppException("DATA_CONFLICT", "当前没有唯一可操作的有效实习记录")
    return stu, ctx.record


def _my_completions(db, rec):
    return db.scalars(select(InternshipSafetyCompletion).where(
        InternshipSafetyCompletion.tenant_id == _tid(),
        InternshipSafetyCompletion.internship_id == rec.id,
        InternshipSafetyCompletion.is_deleted.is_(False),
    ).order_by(InternshipSafetyCompletion.id.asc())).all()


def _latest_completion_map(rows):
    return {row.course_id: row for row in rows}


def list_my_courses(user):
    with session() as db:
        _, rec = _my_context(db, user)
        courses = db.scalars(select(InternshipSafetyCourse).where(
            InternshipSafetyCourse.tenant_id == _tid(),
            InternshipSafetyCourse.batch_id == rec.batch_id,
            InternshipSafetyCourse.status == "ACTIVE",
            InternshipSafetyCourse.is_deleted.is_(False)).order_by(
                InternshipSafetyCourse.id.asc())).all()
        cmap = _latest_completion_map(_my_completions(db, rec))
        return [_course_row(c, cmap.get(c.id)) for c in courses]


def list_my_completions(user):
    with session() as db:
        _, rec = _my_context(db, user)
        return [_completion_row(x) for x in _my_completions(db, rec)]


def get_my_course_detail(course_id, user):
    with session() as db:
        _, rec = _my_context(db, user)
        course = db.get(InternshipSafetyCourse, _as_id(course_id))
        if (not course or course.tenant_id != _tid() or course.is_deleted or
                course.status != "ACTIVE" or course.batch_id != rec.batch_id):
            raise not_found("当前批次安全教育课程不存在")
        completion = db.scalars(_completion_query(rec.id, course.id).order_by(
            InternshipSafetyCompletion.id.desc())).first()
        return {**_course_row(course, completion), "completion": _completion_row(completion)}


def start_my_course(course_id, user):
    with session() as db:
        stu, rec = _my_context(db, user)
        course = db.get(InternshipSafetyCourse, _as_id(course_id))
        if (not course or course.tenant_id != _tid() or course.is_deleted or
                course.status != "ACTIVE" or course.batch_id != rec.batch_id):
            raise not_found("当前批次安全课程不存在")
        x = db.scalar(_completion_query(rec.id, course.id).with_for_update())
        if x and str(x.course_version or "") != str(course.course_version or ""):
            _reset_for_course_version(db, x, course, user, start=True)
            db.commit()
            return _completion_row(x)
        if x:
            if x.status == "NOT_STARTED":
                x.status = "IN_PROGRESS"
                x.started_at = datetime.utcnow()
                x.version = int(x.version or 0) + 1
                _audit(db, x, "START", user, {
                    "courseVersion": course.course_version,
                    "newVersion": int(x.version or 0),
                })
                db.commit()
            elif x.status == "FAILED":
                _restart_failed(db, x, course, user)
                db.commit()
            return _completion_row(x)
        x = InternshipSafetyCompletion(
            tenant_id=_tid(), internship_id=rec.id, batch_id=rec.batch_id,
            student_id=stu.id, course_id=course.id, course_version=course.course_version,
            course_content_snapshot=course.content_snapshot,
            course_content_hash=_hash(course.content_snapshot or ""),
            started_at=datetime.utcnow(), status="IN_PROGRESS",
            review_mode="TEACHER_REVIEW", rule_version=course.rule_version)
        db.add(x)
        db.flush()
        _audit(db, x, "START", user, {"courseVersion": course.course_version})
        db.commit()
        return _completion_row(x)


def submit_my_course(course_id, body, user):
    b = body or {}
    if "passed" in b:
        raise AppException("VALIDATION_ERROR", "学生不得提交 passed 字段")
    with session() as db:
        _, rec = _my_context(db, user)
        course = db.get(InternshipSafetyCourse, _as_id(course_id))
        x = db.scalar(_completion_query(rec.id, _as_id(course_id)).with_for_update())
        if (not course or course.tenant_id != _tid() or course.is_deleted or
                course.status != "ACTIVE" or not x or course.batch_id != rec.batch_id):
            raise not_found("请先开始当前批次安全课程")
        if str(x.course_version or "") != str(course.course_version or ""):
            raise AppException("DATA_CONFLICT", "课程版本已更新，请重新打开并开始最新课程")
        if b.get("expectedVersion") is None or int(b["expectedVersion"]) != int(x.version or 0):
            raise AppException("DATA_CONFLICT", "学习记录版本已变化")
        if x.status != "IN_PROGRESS":
            raise AppException("DATA_CONFLICT", "仅学习中的课程可提交")
        if int(x.attempt_count or 0) >= int(course.max_attempts or 0):
            raise AppException("DATA_CONFLICT", "已超过最大尝试次数")
        if course.require_commitment and not x.commitment_confirmed:
            raise AppException("DATA_CONFLICT", "请先确认安全承诺")
        now = datetime.utcnow()
        elapsed = max(0, int((now - x.started_at).total_seconds() // 60)) if x.started_at else 0
        try:
            claimed = max(0, int(b.get("studiedMinutes") if b.get("studiedMinutes") is not None else elapsed))
        except (TypeError, ValueError):
            raise AppException("VALIDATION_ERROR", "学习时长格式错误")
        trusted = min(claimed, elapsed)
        if trusted < int(course.required_minutes or 0):
            raise AppException(
                "DATA_CONFLICT",
                f"可信学习时长不足，应完成 {course.required_minutes} 分钟，当前 {trusted} 分钟")
        x.studied_minutes = trusted
        x.answer_snapshot = b.get("answers") or None
        x.submitted_at = now
        x.attempt_count = int(x.attempt_count or 0) + 1
        x.status = "PENDING_REVIEW"
        x.version = int(x.version or 0) + 1
        _audit(db, x, "SUBMIT", user, {
            "trustedMinutes": trusted, "claimedMinutes": claimed,
            "attempt": int(x.attempt_count or 0), "newVersion": int(x.version or 0)})
        db.commit()
        return _completion_row(x)


def commit_my_completion(completion_id, body, user):
    b = body or {}
    if not b.get("contentHash"):
        raise AppException("VALIDATION_ERROR", "承诺正文哈希必填")
    with session() as db:
        _, rec = _my_context(db, user)
        x = db.scalar(select(InternshipSafetyCompletion).where(
            InternshipSafetyCompletion.id == _as_id(completion_id),
            InternshipSafetyCompletion.tenant_id == _tid(),
            InternshipSafetyCompletion.internship_id == rec.id,
            InternshipSafetyCompletion.is_deleted.is_(False)).with_for_update())
        if not x:
            raise not_found("安全教育完成记录不存在")
        course = db.get(InternshipSafetyCourse, x.course_id)
        if not course or course.tenant_id != _tid() or course.is_deleted:
            raise not_found("安全教育课程不存在")
        if str(x.course_version or "") != str(course.course_version or ""):
            raise AppException("DATA_CONFLICT", "课程版本已更新，请重新打开并开始最新课程")
        if b.get("expectedVersion") is None or int(b["expectedVersion"]) != int(x.version or 0):
            raise AppException("DATA_CONFLICT", "学习记录版本已变化")
        if str(b.get("contentHash")) != str(x.course_content_hash or ""):
            raise AppException("DATA_CONFLICT", "课程正文已变化，请重新打开最新课程")
        if x.commitment_confirmed:
            return _completion_row(x)
        if x.status != "IN_PROGRESS":
            raise AppException("DATA_CONFLICT", "仅学习中的课程可确认安全承诺")
        x.commitment_confirmed = True
        x.commitment_at = datetime.utcnow()
        x.commitment_content_hash = b["contentHash"]
        x.commitment_device_digest = _hash(str(b.get("deviceDigest") or ""))
        x.version = int(x.version or 0) + 1
        _audit(db, x, "COMMITMENT_CONFIRM", user, {
            "contentHash": x.commitment_content_hash,
            "newVersion": int(x.version or 0),
        })
        db.commit()
        return _completion_row(x)


def teacher_review_completion(completion_id, score=None, action=None, comment=None,
                              expected_version=None, user=None):
    with session() as db:
        x = db.scalar(select(InternshipSafetyCompletion).where(
            InternshipSafetyCompletion.id == _as_id(completion_id),
            InternshipSafetyCompletion.tenant_id == _tid(),
            InternshipSafetyCompletion.is_deleted.is_(False)).with_for_update())
        if not x:
            raise not_found("安全教育完成记录不存在")
        from app.modules.internship.services.internship_scope import assert_internship_record_scope
        assert_internship_record_scope(db, x.internship_id, user, "安全教育审核")
        if expected_version is None or int(expected_version) != int(x.version or 0):
            raise AppException("DATA_CONFLICT", "学习记录版本已变化")
        if x.status != "PENDING_REVIEW":
            raise AppException("DATA_CONFLICT", "仅待审核记录可处理")
        course = db.get(InternshipSafetyCourse, x.course_id)
        if (not course or course.tenant_id != _tid() or course.is_deleted or
                str(x.course_version or "") != str(course.course_version or "")):
            raise AppException("DATA_CONFLICT", "课程版本已更新，旧版本完成记录不可审核通过")
        act = (action or "APPROVE").upper()
        if act == "APPROVE":
            if score is None:
                raise AppException("VALIDATION_ERROR", "审核分数必填")
            try:
                parsed_score = int(score)
            except (TypeError, ValueError):
                raise AppException("VALIDATION_ERROR", "审核分数必须为0-100的整数")
            if not 0 <= parsed_score <= 100:
                raise AppException("VALIDATION_ERROR", "审核分数必须在0-100之间")
            x.score = parsed_score
            x.passed = (
                x.score >= int(course.passing_score or 0) and
                int(x.studied_minutes or 0) >= int(course.required_minutes or 0) and
                (not course.require_commitment or x.commitment_confirmed))
            x.status = "PASSED" if x.passed else "FAILED"
        elif act == "REJECT":
            if len((comment or "").strip()) < 5:
                raise AppException("VALIDATION_ERROR", "驳回原因必填且不少于5字")
            x.passed, x.status = False, "FAILED"
        else:
            raise AppException("VALIDATION_ERROR", "action 必须为 APPROVE/REJECT")
        x.reviewed_by_name = (user or {}).get("realName") or "系统"
        x.reviewed_by_user_id = str((user or {}).get("userId") or "")
        x.reviewed_at = datetime.utcnow()
        x.completed_at = datetime.utcnow()
        x.version = int(x.version or 0) + 1
        _audit(db, x, "REVIEW", user, {
            "action": act, "result": x.status, "score": x.score,
            "comment": (comment or "").strip(), "newVersion": int(x.version or 0)})
        db.commit()
        return _completion_row(x)


def ensure_completion(body, user=None):
    """学校端分配当前课程；版本升级时复用唯一记录并重置为未开始。"""
    b = body or {}
    if not b.get("internshipId") or not b.get("courseId"):
        raise AppException("VALIDATION_ERROR", "internshipId 与 courseId 必填")
    with session() as db:
        from app.modules.internship.services.internship_scope import assert_internship_record_scope
        rec = assert_internship_record_scope(db, b["internshipId"], user, "创建安全教育记录")
        course = db.get(InternshipSafetyCourse, _as_id(b["courseId"]))
        if (not course or course.tenant_id != _tid() or course.is_deleted or
                course.status != "ACTIVE" or course.batch_id != rec.batch_id):
            raise not_found("当前批次安全教育课程不可用")
        exist = db.scalar(_completion_query(rec.id, course.id).with_for_update())
        if exist:
            if str(exist.course_version or "") != str(course.course_version or ""):
                _reset_for_course_version(db, exist, course, user, start=False)
                db.commit()
            return _completion_row(exist)
        x = InternshipSafetyCompletion(
            tenant_id=_tid(), internship_id=rec.id, batch_id=rec.batch_id,
            student_id=rec.student_id, course_id=course.id,
            course_version=course.course_version,
            course_content_snapshot=course.content_snapshot,
            course_content_hash=_hash(course.content_snapshot or ""),
            status="NOT_STARTED", review_mode="TEACHER_REVIEW",
            rule_version=course.rule_version)
        db.add(x)
        db.flush()
        _audit(db, x, "ASSIGN", user, {"courseVersion": course.course_version})
        db.commit()
        return _completion_row(x)
