"""Stage C1 StudentAcademicFact command and as-of resolver.

The command is intentionally transaction-neutral: callers own commit/rollback so an
academic transition, workflow state, audit/outbox and the fact switch can remain in
one database transaction.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import or_

from app.core.exceptions import AppException
from app.services.db_service import _tid

_UNSET = object()
_VALID_QUALITY = {"EXACT", "DERIVED", "INFERRED", "UNKNOWN"}


def _fact_query(db, student_id: int):
    from app.models.academic_affairs_student_fact import StudentAcademicFact

    return db.query(StudentAcademicFact).filter(
        StudentAcademicFact.tenant_id == _tid(),
        StudentAcademicFact.student_id == int(student_id),
    )


def resolve_student_academic_fact(
    db,
    student_id: int,
    as_of: datetime | None = None,
    *,
    for_update: bool = False,
    required: bool = True,
):
    """Resolve exactly one fact effective at ``as_of``.

    More than one match is a hard integrity failure; silently choosing one would make
    historical transcripts and eligibility nondeterministic.
    """
    from app.models.academic_affairs_student_fact import StudentAcademicFact

    moment = as_of or datetime.utcnow()
    q = _fact_query(db, student_id).filter(
        StudentAcademicFact.valid_from <= moment,
        or_(StudentAcademicFact.valid_to.is_(None), StudentAcademicFact.valid_to > moment),
    ).order_by(StudentAcademicFact.version_no.desc())
    if for_update:
        q = q.with_for_update()
    rows = q.limit(2).all()
    if len(rows) > 1:
        raise AppException(
            "ACADEMIC_FACT_OVERLAP",
            "学生学籍历史存在重叠有效事实，已拒绝继续使用不确定数据",
            details={"studentId": str(student_id), "asOf": moment.isoformat()},
            http_status=409,
        )
    if not rows:
        if required:
            raise AppException(
                "ACADEMIC_FACT_NOT_FOUND",
                "学生缺少该时点的学籍事实，请先完成历史事实回填/核对",
                details={"studentId": str(student_id), "asOf": moment.isoformat()},
                http_status=409,
            )
        return None
    return rows[0]


def create_baseline_student_academic_fact(
    db,
    student,
    *,
    valid_from: datetime,
    source_type: str = "BASELINE",
    source_ref_id: int | None = None,
    source_quality: str = "INFERRED",
    created_by: int | None = None,
):
    """Create the one-time version-1 baseline for a student with no fact rows."""
    from app.models.academic_affairs_student_fact import StudentAcademicFact

    quality = (source_quality or "").upper()
    if quality not in _VALID_QUALITY:
        raise AppException("VALIDATION_ERROR", f"非法事实来源质量：{source_quality}")
    existing = _fact_query(db, int(student.id)).with_for_update().first()
    if existing:
        raise AppException(
            "ACADEMIC_FACT_BASELINE_EXISTS", "学生已存在学籍事实，不允许重复创建基线", http_status=409
        )
    row = StudentAcademicFact(
        tenant_id=_tid(),
        student_id=int(student.id),
        version_no=1,
        valid_from=valid_from,
        valid_to=None,
        student_status=student.student_status or "NORMAL",
        college_id=student.college_id,
        major_id=student.major_id,
        class_id=student.class_id,
        grade=student.grade,
        source_type=(source_type or "BASELINE").upper(),
        source_ref_id=int(source_ref_id) if source_ref_id is not None else None,
        source_quality=quality,
        created_by=created_by,
    )
    db.add(row)
    db.flush()
    return row


def _projection_tuple(row) -> tuple:
    return (
        row.student_status or "NORMAL",
        row.college_id,
        row.major_id,
        row.class_id,
        row.grade,
    )


def append_student_academic_fact(
    db,
    student_id: int,
    *,
    effective_at: datetime | None = None,
    student_status=_UNSET,
    college_id=_UNSET,
    major_id=_UNSET,
    class_id=_UNSET,
    grade=_UNSET,
    source_type: str,
    source_ref_id: int | None = None,
    source_quality: str = "EXACT",
    expected_student_version: int | None = None,
    created_by: int | None = None,
):
    """Atomically switch current academic fact and StudentProfile projection.

    Future-effective approvals must *not* call this command early. They remain pending
    until their effective time and then invoke this command from the scheduled apply
    path. A missing baseline or projection/fact drift fails closed instead of silently
    laundering an earlier direct-write bypass. Major changes additionally create a
    deterministic ProgramTransitionAssessment before the fact switch, so program
    binding ambiguity is explicit evidence rather than an implicit guess.
    """
    from app.models import StudentProfile
    from app.models.academic_affairs_student_fact import StudentAcademicFact

    now = datetime.utcnow()
    at = effective_at or now
    if at > now:
        raise AppException(
            "ACADEMIC_FACT_FUTURE_NOT_DUE",
            "未来生效学籍变更尚未到生效时间，不允许提前修改当前主档",
            details={"studentId": str(student_id), "effectiveAt": at.isoformat()},
            http_status=409,
        )
    quality = (source_quality or "").upper()
    if quality not in _VALID_QUALITY:
        raise AppException("VALIDATION_ERROR", f"非法事实来源质量：{source_quality}")

    student = db.query(StudentProfile).filter(
        StudentProfile.tenant_id == _tid(),
        StudentProfile.id == int(student_id),
        StudentProfile.is_deleted.is_(False),
    ).with_for_update().first()
    if not student:
        raise AppException("DATA_NOT_FOUND", "学生不存在")
    if expected_student_version is not None and int(student.version or 0) != int(expected_student_version):
        raise AppException(
            "APPROVAL_VERSION_CONFLICT",
            "学生主档已被其他业务改写，请重新核对后再生效",
            details={"expectedVersion": int(expected_student_version), "currentVersion": int(student.version or 0)},
            http_status=409,
        )

    active = _fact_query(db, student_id).filter(StudentAcademicFact.valid_to.is_(None)).with_for_update().all()
    if len(active) != 1:
        code = "ACADEMIC_FACT_BASELINE_MISSING" if not active else "ACADEMIC_FACT_OVERLAP"
        raise AppException(
            code,
            "学生当前学籍事实底座缺失" if not active else "学生存在多个当前学籍事实",
            details={"studentId": str(student_id), "activeFacts": len(active)},
            http_status=409,
        )
    current = active[0]
    if at < current.valid_from:
        raise AppException(
            "ACADEMIC_FACT_TIME_CONFLICT",
            "生效时间早于当前事实起点，不允许倒写当前事实链",
            details={"studentId": str(student_id), "currentValidFrom": current.valid_from.isoformat()},
            http_status=409,
        )
    if _projection_tuple(current) != _projection_tuple(student):
        raise AppException(
            "ACADEMIC_FACT_PROJECTION_DRIFT",
            "当前学生主档与权威学籍事实不一致，必须先完成 reconciliation",
            details={"studentId": str(student_id), "factVersion": int(current.version_no)},
            http_status=409,
        )

    target = {
        "student_status": student.student_status if student_status is _UNSET else student_status,
        "college_id": student.college_id if college_id is _UNSET else college_id,
        "major_id": student.major_id if major_id is _UNSET else major_id,
        "class_id": student.class_id if class_id is _UNSET else class_id,
        "grade": student.grade if grade is _UNSET else grade,
    }
    if _projection_tuple(current) == (
        target["student_status"] or "NORMAL",
        target["college_id"], target["major_id"], target["class_id"], target["grade"],
    ):
        raise AppException("DATA_CONFLICT", "学籍事实没有发生变化，无需追加新版本", http_status=409)

    overlap = _fact_query(db, student_id).filter(
        StudentAcademicFact.id != current.id,
        StudentAcademicFact.valid_from <= at,
        or_(StudentAcademicFact.valid_to.is_(None), StudentAcademicFact.valid_to > at),
    ).with_for_update().first()
    if overlap:
        raise AppException(
            "ACADEMIC_FACT_OVERLAP",
            "目标生效时点已有其他学籍事实，拒绝生成重叠版本",
            details={"studentId": str(student_id), "conflictFactId": str(overlap.id)},
            http_status=409,
        )

    program_assessment = None
    if target["major_id"] is not None and int(target["major_id"] or 0) != int(current.major_id or 0):
        from app.modules.academic_affairs.services.academic_affairs_program_transition_service import (
            assess_program_transition_in_session,
        )

        program_assessment = assess_program_transition_in_session(
            db,
            student=student,
            source_fact=current,
            to_major_id=int(target["major_id"]),
            target_class_id=(int(target["class_id"]) if target["class_id"] is not None else None),
            source_type=(source_type or "").upper(),
            source_ref_id=(int(source_ref_id) if source_ref_id is not None else None),
        )

    current.valid_to = at
    next_fact = StudentAcademicFact(
        tenant_id=_tid(),
        student_id=int(student_id),
        version_no=int(current.version_no) + 1,
        valid_from=at,
        valid_to=None,
        student_status=target["student_status"] or "NORMAL",
        college_id=target["college_id"],
        major_id=target["major_id"],
        class_id=target["class_id"],
        grade=target["grade"],
        source_type=(source_type or "").upper(),
        source_ref_id=int(source_ref_id) if source_ref_id is not None else None,
        source_quality=quality,
        created_by=created_by,
    )
    db.add(next_fact)

    loaded_version = int(student.version or 0)
    changed = db.query(StudentProfile).filter(
        StudentProfile.tenant_id == _tid(),
        StudentProfile.id == int(student_id),
        StudentProfile.version == loaded_version,
        StudentProfile.is_deleted.is_(False),
    ).update(
        {
            StudentProfile.student_status: target["student_status"] or "NORMAL",
            StudentProfile.college_id: target["college_id"],
            StudentProfile.major_id: target["major_id"],
            StudentProfile.class_id: target["class_id"],
            StudentProfile.grade: target["grade"],
            StudentProfile.version: loaded_version + 1,
        },
        synchronize_session=False,
    )
    if not changed:
        raise AppException("APPROVAL_VERSION_CONFLICT", "学生主档已被并发改写，本次事实切换未生效", http_status=409)
    db.flush()
    db.refresh(student)
    db.refresh(next_fact)

    if program_assessment is not None:
        from app.modules.academic_affairs.services.academic_affairs_program_transition_service import (
            mark_program_transition_applied_in_session,
        )

        mark_program_transition_applied_in_session(db, program_assessment, next_fact)

    return next_fact, student


def current_projection_reconciliation(db, student_id: int) -> dict:
    """Machine-readable shadow-read result used by C1 reconciliation gates."""
    from app.models import StudentProfile

    student = db.query(StudentProfile).filter(
        StudentProfile.tenant_id == _tid(), StudentProfile.id == int(student_id),
        StudentProfile.is_deleted.is_(False),
    ).first()
    if not student:
        raise AppException("DATA_NOT_FOUND", "学生不存在")
    fact = resolve_student_academic_fact(db, student_id, required=False)
    if not fact:
        return {"studentId": str(student_id), "matched": False, "reason": "MISSING_FACT"}
    matched = _projection_tuple(student) == _projection_tuple(fact)
    return {
        "studentId": str(student_id),
        "matched": matched,
        "reason": "MATCHED" if matched else "PROJECTION_DRIFT",
        "factVersion": int(fact.version_no),
    }
