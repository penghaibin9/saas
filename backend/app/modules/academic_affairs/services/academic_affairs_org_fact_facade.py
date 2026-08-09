"""Stage C1 formal organization service facade.

Read/config operations delegate to the mature organization service. Student class
adjustment is overridden so class/major/college changes append StudentAcademicFact.
"""
from __future__ import annotations

import importlib

from app.core.exceptions import AppException, not_found

_legacy = importlib.import_module(".academic_affairs_org_service", package=__package__)


def __getattr__(name):
    return getattr(_legacy, name)


def adjust_student_class(user, body) -> dict:
    from app.models import StudentProfile
    from app.modules.academic_affairs.services.academic_affairs_student_fact_service import (
        append_student_academic_fact,
    )

    student_id = getattr(body, "studentId", None)
    target_class_id = getattr(body, "targetClassId", None)
    if not student_id or not target_class_id:
        raise AppException("VALIDATION_ERROR", "学生与目标班级必填")

    with _legacy.session() as db:
        ctx = _legacy._ctx(user, db)
        target = _legacy._get_class(db, target_class_id)
        target_college_id = _legacy._class_college_id(db, target.id)
        _legacy._require_college_write(ctx, db, target_college_id)
        student = db.query(StudentProfile).filter(
            StudentProfile.id == int(student_id),
            StudentProfile.tenant_id == _legacy._tid(),
            StudentProfile.is_deleted.is_(False),
        ).with_for_update().first()
        if not student:
            raise not_found("学生不存在")
        old_class = student.class_id
        if old_class:
            _legacy._require_college_write(ctx, db, _legacy._class_college_id(db, old_class))
        if old_class == target.id:
            raise AppException("DATA_CONFLICT", "学生已在目标班级")

        fact, projected = append_student_academic_fact(
            db,
            int(student.id),
            college_id=target_college_id,
            major_id=target.major_id,
            class_id=target.id,
            source_type="CLASS_ADJUST",
            source_ref_id=int(target.id),
            expected_student_version=int(student.version or 0),
        )
        _legacy._audit(
            db,
            "AA_ORG_CLASS_ADJUST",
            projected.id,
            "ADJUST_CLASS",
            f"{projected.real_name} → {target.class_name}（academicFactVersion={fact.version_no}）",
            before=str(old_class or ""),
            after=str(target.id),
        )
        db.commit()
        return {
            "studentId": str(student_id),
            "fromClassId": str(old_class) if old_class else None,
            "toClassId": str(target.id),
            "academicFactVersion": int(fact.version_no),
        }
