"""A-W2 public Course service.

Legacy course CRUD remains in ``academic_affairs_course_service``.  This facade only
owns the version-creating update writer so ENABLED -> v+1 is serialized and returns a
stable business conflict instead of leaking the database unique constraint.
"""
from __future__ import annotations

from sqlalchemy import select

from app.core.exceptions import AppException, not_found
from app.services.db_service import _tid, session

from . import academic_affairs_course_service as _core


def __getattr__(name):
    return getattr(_core, name)


def update_course(course_id, user, body) -> dict:
    """Edit draft/returned in place; serialize ENABLED -> one direct DRAFT successor."""
    _core._validate(body)
    with session() as db:
        from app.models import AaCourse

        course = db.query(AaCourse).filter(
            AaCourse.id == int(course_id),
            AaCourse.tenant_id == _tid(),
            AaCourse.is_deleted.is_(False),
        ).with_for_update().first()
        if not course:
            raise not_found("课程不存在")

        _core._validate_owner_teacher(db, getattr(body, "ownerTeacherId", None))
        _core._validate_majors(db, _tid(), getattr(body, "applicableMajors", None) or [])
        _core._check_college_scope(db, user, getattr(body, "ownerCollegeId", None))

        if course.status in ("DRAFT", "RETURNED"):
            _core._apply_fields(course, body)
            _core._audit(db, course.id, "UPDATE")
            db.commit()
            db.refresh(course)
            return _core._row(course)

        if course.status != "ENABLED":
            raise AppException("DATA_CONFLICT", "审核中的课程不可编辑")

        successors = db.scalars(select(AaCourse).where(
            AaCourse.tenant_id == _tid(),
            AaCourse.prev_version_id == course.id,
            AaCourse.is_deleted.is_(False),
        ).order_by(AaCourse.id)).all()
        if successors:
            successor = successors[0]
            raise AppException(
                "DATA_CONFLICT",
                f"该课程版本已生成后继版本 v{successor.version}，请编辑后继版本，禁止从旧版本再次分叉",
                details={
                    "courseId": str(course.id),
                    "courseCode": course.course_code,
                    "sourceVersion": course.version,
                    "successorId": str(successor.id),
                    "successorVersion": successor.version,
                    "successorStatus": successor.status,
                    "successorCount": len(successors),
                },
                http_status=409,
            )

        new_version = AaCourse(
            tenant_id=_tid(),
            course_code=course.course_code,
            credit=0,
            version=course.version + 1,
            prev_version_id=course.id,
            status="DRAFT",
        )
        _core._apply_fields(new_version, body)
        db.add(new_version)
        db.flush()
        _core._audit(db, new_version.id, "NEW_VERSION", f"v{course.version}->v{new_version.version}")
        db.commit()
        db.refresh(new_version)
        return _core._row(new_version)
