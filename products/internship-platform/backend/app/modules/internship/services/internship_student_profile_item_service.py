"""Student-owned internship profile item mutations."""
from __future__ import annotations

from sqlalchemy import select

from app.core.context import get_current_user_ctx
from app.core.exceptions import AppException, not_found
from app.db.session import get_sessionmaker
from app.models.file import FileBinding
from app.models.internship_student_profile import StudentInternshipProfile, StudentInternshipProfileItem
from app.modules.internship.services import internship_student_profile_service as profile_svc
from app.services import file_business_binding_service
from app.services.db_service import _as_id, _tid


def _owned_item_in_tx(db, *, tenant_id: int, student_id: int, item_id: int, lock: bool = True):
    stmt = (
        select(StudentInternshipProfileItem, StudentInternshipProfile)
        .join(
            StudentInternshipProfile,
            (StudentInternshipProfile.id == StudentInternshipProfileItem.profile_id)
            & (StudentInternshipProfile.tenant_id == StudentInternshipProfileItem.tenant_id),
        )
        .where(
            StudentInternshipProfileItem.id == _as_id(item_id),
            StudentInternshipProfileItem.tenant_id == tenant_id,
            StudentInternshipProfileItem.is_deleted.is_(False),
            StudentInternshipProfile.student_id == student_id,
            StudentInternshipProfile.is_deleted.is_(False),
        )
    )
    if lock:
        stmt = stmt.with_for_update()
    row = db.execute(stmt).first()
    if not row:
        raise not_found("实习档案条目不存在或不属于本人")
    item, profile = row
    if item.source_type != "STUDENT_ENTERED":
        raise AppException("NO_PERMISSION", "学校事实投影条目不可由学生修改")
    return item, profile


def update_my_item(item_id: int, body: dict | None, user: dict | None = None):
    body = dict(body or {})
    student_id = profile_svc.resolve_my_student_id(user)
    tenant_id = _tid()
    db = get_sessionmaker()()
    try:
        item, profile = _owned_item_in_tx(
            db,
            tenant_id=tenant_id,
            student_id=student_id,
            item_id=item_id,
        )
        if "itemType" in body:
            item_type = str(body.get("itemType") or "").upper()
            if item_type not in profile_svc._ITEM_TYPES:
                raise AppException("VALIDATION_ERROR", "itemType 非法")
            item.item_type = item_type
        if "title" in body:
            title = str(body.get("title") or "").strip()
            if not title or len(title) > 200:
                raise AppException("VALIDATION_ERROR", "title 必填且最多 200 字")
            item.title = title
        for source, target in (("organization", "organization"), ("description", "description"), ("level", "level")):
            if source in body:
                setattr(item, target, str(body.get(source) or "").strip() or None)
        if "startDate" in body:
            item.start_date = profile_svc._parse_date(body.get("startDate"), "startDate")
        if "endDate" in body:
            item.end_date = profile_svc._parse_date(body.get("endDate"), "endDate")
        if item.start_date and item.end_date and item.start_date > item.end_date:
            raise AppException("VALIDATION_ERROR", "startDate 不能晚于 endDate")
        if "sortOrder" in body:
            item.sort_order = max(0, int(body.get("sortOrder") or 0))
        # Student edits never upgrade verification or convert the row into SCHOOL_FACT.
        item.source_type = "STUDENT_ENTERED"
        item.source_ref_type = None
        item.source_ref_id = None
        item.verification_status = "UNVERIFIED"
        actor = user or get_current_user_ctx() or {}
        for file_id in body.get("appendFileIds") or []:
            file_business_binding_service.bind_file_to_business(
                db,
                file_id=file_id,
                biz_type="INTERNSHIP_STUDENT_PROFILE_ITEM",
                biz_id=item.id,
                actor=actor,
                subject_type="STUDENT",
                subject_id=student_id,
                relation_type="PROFILE_EVIDENCE",
                module_code="INTERNSHIP",
                student_id=student_id,
                scope={"studentId": str(student_id), "profileId": str(profile.id), "itemType": item.item_type},
            )
        profile.profile_version = int(profile.profile_version or 0) + 1
        db.commit()
        return profile_svc.build_profile_projection_in_tx(db, tenant_id=tenant_id, student_id=student_id)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def delete_my_item(item_id: int, *, user: dict | None = None):
    student_id = profile_svc.resolve_my_student_id(user)
    tenant_id = _tid()
    db = get_sessionmaker()()
    try:
        item, profile = _owned_item_in_tx(
            db,
            tenant_id=tenant_id,
            student_id=student_id,
            item_id=item_id,
        )
        item.is_deleted = True
        bindings = db.scalars(
            select(FileBinding).where(
                FileBinding.tenant_id == tenant_id,
                FileBinding.biz_type == "INTERNSHIP_STUDENT_PROFILE_ITEM",
                FileBinding.biz_id == str(item.id),
                FileBinding.status == "ACTIVE",
                FileBinding.is_current.is_(True),
                FileBinding.is_deleted.is_(False),
            ).with_for_update()
        ).all()
        for binding in bindings:
            binding.status = "INACTIVE"
            binding.is_current = False
        profile.profile_version = int(profile.profile_version or 0) + 1
        db.commit()
        return profile_svc.build_profile_projection_in_tx(db, tenant_id=tenant_id, student_id=student_id)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
