"""安全教育：课程管理、学生真实学习、教师范围内审核。"""
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


def _audit(db, x, action, user=None, detail=None):
    db.add(InternshipAuditTrail(
        tenant_id=_tid(), target_id=x.id, target_type="INTERNSHIP_SAFETY",
        action=action, operator_name=(user or {}).get("realName") or "系统",
        detail_json=detail or {}, occurred_at=datetime.utcnow()))


def _course_row(x, completion=None):
    return {
        "id": str(x.id), "title": x.title, "status": x.status,
        "courseVersion": x.course_version, "requiredMinutes": x.required_minutes,
        "passingScore": x.passing_score, "maxAttempts": x.max_attempts,
        "requireCommitment": bool(x.require_commitment),
        "contentSnapshot": x.content_snapshot,
        "completionStatus": completion.status if completion else "NOT_STARTED",
        "studiedMinutes": completion.studied_minutes if completion else 0,
        "remainingAttempts": max(0, x.max_attempts - (completion.attempt_count if completion else 0)),
        "blocksOnboard": not completion or completion.status != "PASSED",
    }


def list_courses(batch_id, user=None):
    with session() as db:
        rows = db.scalars(select(InternshipSafetyCourse).where(
            InternshipSafetyCourse.tenant_id == _tid(),
            InternshipSafetyCourse.batch_id == _as_id(batch_id),
            InternshipSafetyCourse.is_deleted.is_(False))).all()
        return [_course_row(x) for x in rows]


def create_course(body, user=None):
    b = body or {}
    with session() as db:
        x = InternshipSafetyCourse(
            tenant_id=_tid(), batch_id=_as_id(b.get("batchId")) if b.get("batchId") else None,
            title=b.get("title") or "", course_version=b.get("courseVersion") or "v1",
            required_minutes=int(b.get("requiredMinutes", 60)),
            passing_score=int(b.get("passingScore", 80)),
            max_attempts=int(b.get("maxAttempts", 3)),
            require_commitment=bool(b.get("requireCommitment", True)),
            content_snapshot=b.get("contentSnapshot"),
            material_file_ids=b.get("materialFileIds"), status=b.get("status") or "ACTIVE")
        if not x.title or not x.content_snapshot:
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
        raise AppException("DATA_CONFLICT", "当前没有可操作的有效实习记录")
    return stu, ctx.record


def list_my_courses(user):
    with session() as db:
        _, rec = _my_context(db, user)
        courses = db.scalars(select(InternshipSafetyCourse).where(
            InternshipSafetyCourse.tenant_id == _tid(),
            InternshipSafetyCourse.batch_id == rec.batch_id,
            InternshipSafetyCourse.status == "ACTIVE",
            InternshipSafetyCourse.is_deleted.is_(False))).all()
        completions = db.scalars(select(InternshipSafetyCompletion).where(
            InternshipSafetyCompletion.tenant_id == _tid(),
            InternshipSafetyCompletion.internship_id == rec.id,
            InternshipSafetyCompletion.is_deleted.is_(False))).all()
        cmap = {x.course_id: x for x in completions}
        return [_course_row(c, cmap.get(c.id)) for c in courses]


def list_my_completions(user):
    with session() as db:
        _, rec = _my_context(db, user)
        rows = db.scalars(select(InternshipSafetyCompletion).where(
            InternshipSafetyCompletion.tenant_id == _tid(),
            InternshipSafetyCompletion.internship_id == rec.id,
            InternshipSafetyCompletion.is_deleted.is_(False))).all()
        return [{
            "id": str(x.id), "courseId": str(x.course_id), "status": x.status,
            "studiedMinutes": x.studied_minutes, "attemptCount": x.attempt_count,
            "score": x.score, "passed": bool(x.passed),
            "commitmentConfirmed": bool(x.commitment_confirmed),
            "version": int(x.version or 0),
        } for x in rows]


def start_my_course(course_id, user):
    with session() as db:
        stu, rec = _my_context(db, user)
        course = db.get(InternshipSafetyCourse, _as_id(course_id))
        if (not course or course.tenant_id != _tid() or course.is_deleted or
                course.status != "ACTIVE" or course.batch_id != rec.batch_id):
            raise not_found("当前批次安全课程不存在")
        x = db.scalars(select(InternshipSafetyCompletion).where(
            InternshipSafetyCompletion.tenant_id == _tid(),
            InternshipSafetyCompletion.internship_id == rec.id,
            InternshipSafetyCompletion.course_id == course.id,
            InternshipSafetyCompletion.is_deleted.is_(False)).with_for_update()).first()
        if x:
            return {"id": str(x.id), "status": x.status, "startedAt": x.started_at,
                    "version": int(x.version or 0)}
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
        return {"id": str(x.id), "status": x.status, "startedAt": x.started_at,
                "version": int(x.version or 0)}


def submit_my_course(course_id, body, user):
    b = body or {}
    if "passed" in b:
        raise AppException("VALIDATION_ERROR", "学生不得提交 passed 字段")
    with session() as db:
        _, rec = _my_context(db, user)
        course = db.get(InternshipSafetyCourse, _as_id(course_id))
        x = db.scalars(select(InternshipSafetyCompletion).where(
            InternshipSafetyCompletion.tenant_id == _tid(),
            InternshipSafetyCompletion.internship_id == rec.id,
            InternshipSafetyCompletion.course_id == _as_id(course_id),
            InternshipSafetyCompletion.is_deleted.is_(False)).with_for_update()).first()
        if not course or not x or course.batch_id != rec.batch_id:
            raise not_found("请先开始当前批次安全课程")
        if b.get("expectedVersion") is None or int(b["expectedVersion"]) != int(x.version or 0):
            raise AppException("DATA_CONFLICT", "学习记录版本已变化")
        if x.attempt_count >= course.max_attempts:
            raise AppException("DATA_CONFLICT", "已超过最大尝试次数")
        now = datetime.utcnow()
        elapsed = max(0, int((now - x.started_at).total_seconds() // 60)) if x.started_at else 0
        claimed = max(0, int(b.get("studiedMinutes") or elapsed))
        x.studied_minutes = min(claimed, elapsed)
        x.answer_snapshot = b.get("answers") or None
        x.submitted_at = now
        x.attempt_count += 1
        x.status = "PENDING_REVIEW"
        x.version = int(x.version or 0) + 1
        _audit(db, x, "SUBMIT", user, {
            "trustedMinutes": x.studied_minutes, "claimedMinutes": claimed,
            "attempt": x.attempt_count})
        db.commit()
        return {"id": str(x.id), "status": x.status,
                "studiedMinutes": x.studied_minutes, "version": x.version}


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
        if b.get("expectedVersion") is None or int(b["expectedVersion"]) != int(x.version or 0):
            raise AppException("DATA_CONFLICT", "学习记录版本已变化")
        if x.commitment_confirmed:
            return {"id": str(x.id), "status": x.status, "version": x.version}
        x.commitment_confirmed = True
        x.commitment_at = datetime.utcnow()
        x.commitment_content_hash = b["contentHash"]
        x.commitment_device_digest = _hash(str(b.get("deviceDigest") or ""))
        x.version = int(x.version or 0) + 1
        _audit(db, x, "COMMITMENT_CONFIRM", user, {"contentHash": x.commitment_content_hash})
        db.commit()
        return {"id": str(x.id), "status": x.status, "version": x.version}


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
        act = (action or "APPROVE").upper()
        if act == "APPROVE":
            if score is None:
                raise AppException("VALIDATION_ERROR", "审核分数必填")
            x.score = int(score)
            x.passed = (
                x.score >= course.passing_score and
                x.studied_minutes >= course.required_minutes and
                (not course.require_commitment or x.commitment_confirmed))
            x.status = "PASSED" if x.passed else "FAILED"
        elif act == "REJECT":
            x.passed, x.status = False, "FAILED"
        else:
            raise AppException("VALIDATION_ERROR", "action 必须为 APPROVE/REJECT")
        x.reviewed_by_name = (user or {}).get("realName") or "系统"
        x.reviewed_by_user_id = str((user or {}).get("userId") or "")
        x.reviewed_at = datetime.utcnow()
        x.completed_at = datetime.utcnow()
        x.version = int(x.version or 0) + 1
        _audit(db, x, "REVIEW", user, {"action": act, "result": x.status, "comment": comment})
        db.commit()
        return {"id": str(x.id), "status": x.status, "passed": x.passed,
                "courseVersion": x.course_version, "version": x.version}


def ensure_completion(body, user=None):
    """兼容学校端：仅创建待学习记录，不允许直接通过。"""
    b = body or {}
    if not b.get("internshipId") or not b.get("courseId"):
        raise AppException("VALIDATION_ERROR", "internshipId 与 courseId 必填")
    with session() as db:
        from app.modules.internship.services.internship_scope import assert_internship_record_scope
        rec = assert_internship_record_scope(db, b["internshipId"], user, "创建安全教育记录")
        course = db.get(InternshipSafetyCourse, _as_id(b["courseId"]))
        if not course or course.tenant_id != _tid() or course.batch_id != rec.batch_id:
            raise not_found("当前批次安全教育课程不可用")
        exist = db.scalars(select(InternshipSafetyCompletion).where(
            InternshipSafetyCompletion.tenant_id == _tid(),
            InternshipSafetyCompletion.internship_id == rec.id,
            InternshipSafetyCompletion.course_id == course.id,
            InternshipSafetyCompletion.is_deleted.is_(False))).first()
        if exist:
            return {"id": str(exist.id), "status": exist.status, "passed": exist.passed}
        x = InternshipSafetyCompletion(
            tenant_id=_tid(), internship_id=rec.id, batch_id=rec.batch_id,
            student_id=rec.student_id, course_id=course.id,
            course_version=course.course_version,
            course_content_snapshot=course.content_snapshot,
            course_content_hash=_hash(course.content_snapshot or ""),
            status="NOT_STARTED", review_mode="TEACHER_REVIEW")
        db.add(x)
        db.flush()
        _audit(db, x, "ASSIGN", user)
        db.commit()
        return {"id": str(x.id), "status": x.status, "passed": False}
