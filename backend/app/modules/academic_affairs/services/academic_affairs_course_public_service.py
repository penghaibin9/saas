"""A-W2 public Course service.

Legacy course CRUD remains in ``academic_affairs_course_service``. This facade owns
the version-creating update writer and node-authorized review writer that must be
serialized and fail closed.
"""
from __future__ import annotations

from sqlalchemy import select

from app.core.affairs_security import build_affairs_context, no_data_scope
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


def _assert_course_review_scope(db, user, course) -> None:
    """Authorize the locked review node without letting school scope impersonate college review."""
    ctx = build_affairs_context(user, db)
    scope_type = str(getattr(ctx, "scope_type", None) or "NONE").upper()
    if course.status == "ACADEMIC_REVIEW":
        if scope_type != "TENANT_ALL":
            raise no_data_scope("仅校级教务可执行课程终审")
        return
    if course.status != "COLLEGE_REVIEW":
        raise AppException("APPROVAL_VERSION_CONFLICT", "该课程当前状态不可审核")
    if scope_type == "TENANT_ALL":
        raise no_data_scope("学院审核必须由课程开课单位审批人执行")
    if not course.owner_college_id:
        raise no_data_scope("课程缺少开课单位，无法证明学院审核权限")
    college_ids = {int(value) for value in getattr(ctx, "college_ids", set()) if value is not None}
    if int(course.owner_college_id) not in college_ids:
        raise no_data_scope("该课程不在您的学院审核范围内")


def review_course(course_id, user, action, reason="") -> dict:
    """P1-04: serialize one review decision and enforce node-specific Authority."""
    from app.models import AaCourse

    action = str(action or "").upper()
    with session() as db:
        course = db.query(AaCourse).filter(
            AaCourse.id == int(course_id),
            AaCourse.tenant_id == _tid(),
            AaCourse.is_deleted.is_(False),
        ).with_for_update().first()
        if not course:
            raise not_found("课程不存在")
        if course.status not in ("COLLEGE_REVIEW", "ACADEMIC_REVIEW"):
            raise AppException("APPROVAL_VERSION_CONFLICT", "该课程当前状态不可审核")

        _assert_course_review_scope(db, user, course)
        before_status = course.status
        if action == "APPROVE":
            course.status = "ACADEMIC_REVIEW" if before_status == "COLLEGE_REVIEW" else "ENABLED"
            _core._audit(db, course.id, "APPROVE", f"{before_status}->{course.status}")
        elif action in ("RETURN", "REJECT"):
            clean_reason = str(reason or "").strip()
            if len(clean_reason) < 5:
                raise AppException("VALIDATION_ERROR", "退回原因必填且不少于 5 字")
            course.status = "RETURNED"
            _core._audit(db, course.id, "RETURNED", clean_reason)
        else:
            raise AppException("VALIDATION_ERROR", "无效操作")

        db.commit()
        db.refresh(course)
        return _core._row(course)
