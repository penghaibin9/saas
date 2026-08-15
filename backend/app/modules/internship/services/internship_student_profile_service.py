"""StudentInternshipProfile authority service.

Editable profile data is separate from school student truth. Every projection re-reads canonical
StudentProfile + College/Major/SchoolClass and returns FileBinding IDs rather than storage URLs.
"""
from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy import select

from app.core.context import get_current_user_ctx
from app.core.exceptions import AppException, no_permission, not_found
from app.db.session import get_sessionmaker
from app.models import College, Major, SchoolClass, StudentAccountLink, StudentProfile
from app.models.file import FileBinding
from app.models.internship_student_profile import (
    StudentInternshipProfile,
    StudentInternshipProfileItem,
)
from app.services import file_business_binding_service
from app.services.db_service import _as_id, _iso, _tid

_ITEM_TYPES = frozenset({"SKILL_EVIDENCE", "CERTIFICATE", "PROJECT", "PRACTICE", "AWARD", "PORTFOLIO"})
_EDITABLE_PROFILE_FIELDS = {
    "headline": "headline",
    "selfIntro": "self_intro",
    "strengths": "strengths",
    "availableFrom": "available_from",
    "availableUntil": "available_until",
    "expectedLocations": "expected_locations_json",
    "skillTags": "skill_tags_json",
}
_FORBIDDEN_SCHOOL_FIELDS = frozenset({
    "realName", "name", "studentNo", "collegeId", "collegeName", "majorId", "majorName",
    "grade", "classId", "className", "studentStatus", "currentStage",
})


def _user_db_id(user: dict | None) -> int:
    raw = str((user or {}).get("userId") or (user or {}).get("id") or "")
    if raw.startswith("db-"):
        raw = raw[3:]
    if not raw.isdigit():
        raise no_permission("当前学生账号没有可验证的数据库身份")
    return int(raw)


def resolve_my_student_id(user: dict | None = None) -> int:
    actor = user or get_current_user_ctx() or {}
    if (actor.get("userType") or "").upper() != "STUDENT":
        raise no_permission("仅学生本人可维护实习档案")
    tenant_id = _tid()
    db = get_sessionmaker()()
    try:
        link = db.scalar(
            select(StudentAccountLink).where(
                StudentAccountLink.tenant_id == tenant_id,
                StudentAccountLink.user_id == _user_db_id(actor),
                StudentAccountLink.link_status == "ACTIVE",
                StudentAccountLink.is_deleted.is_(False),
            )
        )
        if not link:
            raise no_permission("学生账号未绑定有效学生主档")
        return int(link.student_id)
    finally:
        db.close()


def _student_facts_in_tx(db, *, tenant_id: int, student_id: int) -> tuple[StudentProfile, dict[str, Any]]:
    student = db.scalar(
        select(StudentProfile).where(
            StudentProfile.id == _as_id(student_id),
            StudentProfile.tenant_id == tenant_id,
            StudentProfile.is_deleted.is_(False),
        )
    )
    if not student:
        raise not_found("学生主档不存在或不在当前租户")
    college = db.scalar(select(College).where(College.id == student.college_id, College.tenant_id == tenant_id, College.is_deleted.is_(False))) if student.college_id else None
    major = db.scalar(select(Major).where(Major.id == student.major_id, Major.tenant_id == tenant_id, Major.is_deleted.is_(False))) if student.major_id else None
    school_class = db.scalar(select(SchoolClass).where(SchoolClass.id == student.class_id, SchoolClass.tenant_id == tenant_id, SchoolClass.is_deleted.is_(False))) if student.class_id else None
    return student, {
        "studentId": str(student.id),
        "realName": student.real_name,
        "studentNo": student.student_no,
        "collegeId": str(student.college_id) if student.college_id else "",
        "collegeName": college.college_name if college else "",
        "majorId": str(student.major_id) if student.major_id else "",
        "majorName": major.major_name if major else "",
        "grade": student.grade or "",
        "classId": str(student.class_id) if student.class_id else "",
        "className": school_class.class_name if school_class else "",
        "studentStatus": student.student_status,
        "currentStage": student.current_stage,
    }


def _attachments_in_tx(db, item_ids: list[int], *, tenant_id: int) -> dict[int, list[str]]:
    if not item_ids:
        return {}
    rows = db.scalars(
        select(FileBinding).where(
            FileBinding.tenant_id == tenant_id,
            FileBinding.biz_type == "INTERNSHIP_STUDENT_PROFILE_ITEM",
            FileBinding.biz_id.in_([str(item_id) for item_id in item_ids]),
            FileBinding.status == "ACTIVE",
            FileBinding.is_current.is_(True),
            FileBinding.is_deleted.is_(False),
        ).order_by(FileBinding.id)
    ).all()
    result: dict[int, list[str]] = {item_id: [] for item_id in item_ids}
    for row in rows:
        if str(row.biz_id).isdigit():
            result.setdefault(int(row.biz_id), []).append(str(row.file_id))
    return result


def build_profile_projection_in_tx(db, *, tenant_id: int, student_id: int) -> dict[str, Any]:
    _student, school_facts = _student_facts_in_tx(db, tenant_id=tenant_id, student_id=student_id)
    profile = db.scalar(
        select(StudentInternshipProfile).where(
            StudentInternshipProfile.tenant_id == tenant_id,
            StudentInternshipProfile.student_id == _as_id(student_id),
            StudentInternshipProfile.is_deleted.is_(False),
        )
    )
    items = []
    if profile:
        items = db.scalars(
            select(StudentInternshipProfileItem).where(
                StudentInternshipProfileItem.tenant_id == tenant_id,
                StudentInternshipProfileItem.profile_id == profile.id,
                StudentInternshipProfileItem.is_deleted.is_(False),
            ).order_by(StudentInternshipProfileItem.sort_order, StudentInternshipProfileItem.id)
        ).all()
    attachments = _attachments_in_tx(db, [int(item.id) for item in items], tenant_id=tenant_id)
    return {
        "schoolFacts": school_facts,
        "profile": {
            "id": str(profile.id) if profile else "",
            "profileVersion": int(profile.profile_version or 0) if profile else 0,
            "headline": profile.headline or "" if profile else "",
            "selfIntro": profile.self_intro or "" if profile else "",
            "strengths": profile.strengths or "" if profile else "",
            "availableFrom": profile.available_from.isoformat() if profile and profile.available_from else "",
            "availableUntil": profile.available_until.isoformat() if profile and profile.available_until else "",
            "expectedLocations": list(profile.expected_locations_json or []) if profile else [],
            "skillTags": list(profile.skill_tags_json or []) if profile else [],
            "resumeTemplateCode": profile.resume_template_code if profile else "INTERNSHIP_STANDARD_V1",
        },
        "items": [
            {
                "id": str(item.id),
                "itemType": item.item_type,
                "title": item.title,
                "organization": item.organization or "",
                "description": item.description or "",
                "startDate": item.start_date.isoformat() if item.start_date else "",
                "endDate": item.end_date.isoformat() if item.end_date else "",
                "level": item.level or "",
                "sourceType": item.source_type,
                "sourceRefType": item.source_ref_type or "",
                "sourceRefId": item.source_ref_id or "",
                "verificationStatus": item.verification_status,
                "sortOrder": item.sort_order,
                "fileIds": attachments.get(int(item.id), []),
            }
            for item in items
        ],
    }


def get_profile_for_student(student_id: int) -> dict[str, Any]:
    tenant_id = _tid()
    db = get_sessionmaker()()
    try:
        return build_profile_projection_in_tx(db, tenant_id=tenant_id, student_id=_as_id(student_id))
    finally:
        db.close()


def get_my_profile(user: dict | None = None) -> dict[str, Any]:
    return get_profile_for_student(resolve_my_student_id(user))


def _parse_date(value, field: str):
    if value in (None, ""):
        return None
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value))
    except ValueError as exc:
        raise AppException("VALIDATION_ERROR", f"{field} 必须是 YYYY-MM-DD") from exc


def _clean_string_list(value, field: str, *, max_items: int = 30, item_max: int = 80) -> list[str]:
    if value in (None, ""):
        return []
    if not isinstance(value, list):
        raise AppException("VALIDATION_ERROR", f"{field} 必须是数组")
    clean: list[str] = []
    for raw in value:
        text = str(raw or "").strip()
        if not text:
            continue
        if len(text) > item_max:
            raise AppException("VALIDATION_ERROR", f"{field} 单项过长")
        if text not in clean:
            clean.append(text)
    if len(clean) > max_items:
        raise AppException("VALIDATION_ERROR", f"{field} 最多 {max_items} 项")
    return clean


def save_my_profile(body: dict | None, user: dict | None = None) -> dict[str, Any]:
    body = dict(body or {})
    forbidden = _FORBIDDEN_SCHOOL_FIELDS.intersection(body)
    if forbidden:
        raise AppException("VALIDATION_ERROR", "姓名/学号/学院/专业/年级/班级等学校主档字段不可在实习档案修改")
    student_id = resolve_my_student_id(user)
    tenant_id = _tid()
    db = get_sessionmaker()()
    try:
        _student_facts_in_tx(db, tenant_id=tenant_id, student_id=student_id)
        profile = db.scalar(
            select(StudentInternshipProfile).where(
                StudentInternshipProfile.tenant_id == tenant_id,
                StudentInternshipProfile.student_id == student_id,
                StudentInternshipProfile.is_deleted.is_(False),
            ).with_for_update()
        )
        expected = body.get("expectedProfileVersion")
        if profile:
            if expected is None or int(expected) != int(profile.profile_version or 0):
                raise AppException("DATA_CONFLICT", "实习档案已被其他请求修改，请刷新后重试")
        else:
            if expected not in (None, 0, "0"):
                raise AppException("DATA_CONFLICT", "实习档案尚未创建，版本不匹配")
            profile = StudentInternshipProfile(tenant_id=tenant_id, student_id=student_id, profile_version=0)
            db.add(profile)
            db.flush()

        values: dict[str, Any] = {}
        for source, target in _EDITABLE_PROFILE_FIELDS.items():
            if source in body:
                values[target] = body[source]
        if "availableFrom" in body:
            values["available_from"] = _parse_date(body.get("availableFrom"), "availableFrom")
        if "availableUntil" in body:
            values["available_until"] = _parse_date(body.get("availableUntil"), "availableUntil")
        if values.get("available_from") and values.get("available_until") and values["available_from"] > values["available_until"]:
            raise AppException("VALIDATION_ERROR", "availableFrom 不能晚于 availableUntil")
        if "expectedLocations" in body:
            values["expected_locations_json"] = _clean_string_list(body.get("expectedLocations"), "expectedLocations", max_items=20)
        if "skillTags" in body:
            values["skill_tags_json"] = _clean_string_list(body.get("skillTags"), "skillTags", max_items=30)
        if "headline" in values and values["headline"] is not None and len(str(values["headline"])) > 120:
            raise AppException("VALIDATION_ERROR", "headline 最多 120 字")
        for field, value in values.items():
            setattr(profile, field, value)
        profile.profile_version = int(profile.profile_version or 0) + 1
        db.commit()
        return build_profile_projection_in_tx(db, tenant_id=tenant_id, student_id=student_id)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def add_my_item(body: dict | None, user: dict | None = None) -> dict[str, Any]:
    body = dict(body or {})
    student_id = resolve_my_student_id(user)
    tenant_id = _tid()
    item_type = str(body.get("itemType") or "").upper()
    if item_type not in _ITEM_TYPES:
        raise AppException("VALIDATION_ERROR", "itemType 非法")
    title = str(body.get("title") or "").strip()
    if not title or len(title) > 200:
        raise AppException("VALIDATION_ERROR", "title 必填且最多 200 字")
    db = get_sessionmaker()()
    try:
        profile = db.scalar(
            select(StudentInternshipProfile).where(
                StudentInternshipProfile.tenant_id == tenant_id,
                StudentInternshipProfile.student_id == student_id,
                StudentInternshipProfile.is_deleted.is_(False),
            ).with_for_update()
        )
        if not profile:
            profile = StudentInternshipProfile(tenant_id=tenant_id, student_id=student_id, profile_version=1)
            db.add(profile)
            db.flush()
        item = StudentInternshipProfileItem(
            tenant_id=tenant_id,
            profile_id=profile.id,
            item_type=item_type,
            title=title,
            organization=str(body.get("organization") or "").strip() or None,
            description=str(body.get("description") or "").strip() or None,
            start_date=_parse_date(body.get("startDate"), "startDate"),
            end_date=_parse_date(body.get("endDate"), "endDate"),
            level=str(body.get("level") or "").strip() or None,
            source_type="STUDENT_ENTERED",
            source_ref_type=None,
            source_ref_id=None,
            verification_status="UNVERIFIED",
            sort_order=max(0, int(body.get("sortOrder") or 0)),
        )
        if item.start_date and item.end_date and item.start_date > item.end_date:
            raise AppException("VALIDATION_ERROR", "startDate 不能晚于 endDate")
        db.add(item)
        db.flush()
        actor = user or get_current_user_ctx() or {}
        for file_id in body.get("fileIds") or []:
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
                scope={"studentId": str(student_id), "profileId": str(profile.id), "itemType": item_type},
            )
        profile.profile_version = int(profile.profile_version or 0) + 1
        db.commit()
        return build_profile_projection_in_tx(db, tenant_id=tenant_id, student_id=student_id)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
