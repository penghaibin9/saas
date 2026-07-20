"""职业教育国家标准库查询与学校专业绑定。"""
from __future__ import annotations

import re
from datetime import datetime

from sqlalchemy import func, or_, select

from app.core.context import current_tenant_id
from app.core.exceptions import AppException
from app.db.session import get_sessionmaker
from app.models import (Major, NationalMajorCatalog, NationalStandardDocument,
                        NationalStandardSection, NationalStandardSource,
                        SchoolMajorStandardBinding)
from app.services import audit_log

LEVELS = {"SECONDARY_VOCATIONAL", "HIGHER_VOCATIONAL_SPECIALIST", "VOCATIONAL_BACHELOR"}
DOCUMENT_TYPES = {"PROFESSIONAL_TEACHING_STANDARD", "PROFESSIONAL_PROFILE"}


def _tenant_id() -> int:
    value = current_tenant_id()
    if value is None:
        raise AppException("TENANT_NOT_FOUND", "当前请求没有学校租户上下文")
    return int(value)


def _actor(user: dict) -> int | None:
    try:
        return int(user.get("userId") or user.get("id"))
    except (TypeError, ValueError):
        return None


def _snippet(text: str | None, keyword: str, size: int = 180) -> str:
    clean = re.sub(r"\s+", " ", text or "").strip()
    if not clean:
        return ""
    if not keyword:
        return clean[:size]
    pos = clean.lower().find(keyword.lower())
    if pos < 0:
        return clean[:size]
    start = max(0, pos - size // 3)
    return ("…" if start else "") + clean[start:start + size] + ("…" if start + size < len(clean) else "")


def stats() -> dict:
    db = get_sessionmaker()()
    try:
        def count(model, *conditions):
            stmt = select(func.count(model.id)).where(model.is_deleted.is_(False), *conditions)
            return int(db.scalar(stmt) or 0)
        def levels_for(document_type: str):
            return {level: count(NationalStandardDocument,
                                 NationalStandardDocument.document_type == document_type,
                                 NationalStandardDocument.education_level == level,
                                 NationalStandardDocument.status == "PUBLISHED")
                    for level in sorted(LEVELS)}
        teaching_levels = levels_for("PROFESSIONAL_TEACHING_STANDARD")
        profile_levels = levels_for("PROFESSIONAL_PROFILE")
        return {"sources": count(NationalStandardSource), "majors": count(NationalMajorCatalog),
                "documents": count(NationalStandardDocument),
                "teachingStandards": sum(teaching_levels.values()),
                "professionalProfiles": sum(profile_levels.values()),
                "fullTextDocuments": count(NationalStandardDocument,
                                           NationalStandardDocument.text_status == "EXTRACTED"),
                "metadataOnlyDocuments": count(NationalStandardDocument,
                                                NationalStandardDocument.text_status == "METADATA_ONLY"),
                "sections": count(NationalStandardSection),
                "teachingStandardLevels": teaching_levels, "professionalProfileLevels": profile_levels,
                "expected2025": {"total": 758, "SECONDARY_VOCATIONAL": 223,
                                 "HIGHER_VOCATIONAL_SPECIALIST": 471, "VOCATIONAL_BACHELOR": 64},
                "public2025": {"total": 752, "SECONDARY_VOCATIONAL": 223,
                               "HIGHER_VOCATIONAL_SPECIALIST": 465, "VOCATIONAL_BACHELOR": 64},
                "catalog2021": {"total": 1349, "SECONDARY_VOCATIONAL": 358,
                                "HIGHER_VOCATIONAL_SPECIALIST": 744, "VOCATIONAL_BACHELOR": 247},
                "copyrightPolicy": "系统内检索与实施引用；保留教育部来源链接，不提供原站文件镜像再发布。"}
    finally:
        db.close()


def search_documents(keyword: str = "", education_level: str = "", category_code: str = "",
                     text_status: str = "", document_type: str = "",
                     page: int = 1, page_size: int = 20) -> dict:
    keyword = str(keyword or "").strip()
    education_level = str(education_level or "").strip().upper()
    if education_level and education_level not in LEVELS:
        raise AppException("VALIDATION_ERROR", "教育层次筛选值无效")
    document_type = str(document_type or "").strip().upper()
    if document_type and document_type not in DOCUMENT_TYPES:
        raise AppException("VALIDATION_ERROR", "文档类型筛选值无效")
    page = max(int(page), 1); page_size = min(max(int(page_size), 1), 100)
    db = get_sessionmaker()()
    try:
        conditions = [NationalStandardDocument.is_deleted.is_(False),
                      NationalStandardDocument.status == "PUBLISHED"]
        if education_level:
            conditions.append(NationalStandardDocument.education_level == education_level)
        if text_status:
            conditions.append(NationalStandardDocument.text_status == text_status.upper())
        if document_type:
            conditions.append(NationalStandardDocument.document_type == document_type)
        if category_code:
            conditions.append(NationalMajorCatalog.category_code == str(category_code).strip())
        if keyword:
            like = f"%{keyword}%"
            conditions.append(or_(NationalStandardDocument.major_code.like(like),
                                  NationalStandardDocument.major_name.like(like),
                                  NationalStandardDocument.title.like(like),
                                  NationalStandardDocument.full_text.like(like)))
        base = (select(NationalStandardDocument, NationalMajorCatalog)
                .outerjoin(NationalMajorCatalog,
                           NationalMajorCatalog.id == NationalStandardDocument.major_catalog_id)
                .where(*conditions))
        total = int(db.scalar(select(func.count()).select_from(base.subquery())) or 0)
        rows = db.execute(base.order_by(NationalStandardDocument.education_level,
                                        NationalStandardDocument.major_code)
                          .offset((page - 1) * page_size).limit(page_size)).all()
        items = []
        for document, major in rows:
            items.append({"id": str(document.id), "standardCode": document.standard_code,
                          "documentType": document.document_type,
                          "title": document.title, "educationLevel": document.education_level,
                          "majorCode": document.major_code, "majorName": document.major_name,
                          "categoryCode": major.category_code if major else "",
                          "categoryName": major.category_name if major else "",
                          "majorClassCode": major.major_class_code if major else "",
                          "majorClassName": major.major_class_name if major else "",
                          "versionLabel": document.version_label,
                          "publishedDate": str(document.published_date or ""),
                          "textStatus": document.text_status, "pageCount": document.page_count,
                          "charCount": document.char_count, "sourceUrl": document.source_url,
                          "snippet": _snippet(document.full_text, keyword)})
        return {"list": items, "total": total, "page": page, "pageSize": page_size}
    finally:
        db.close()


def document_detail(document_id: int) -> dict:
    db = get_sessionmaker()()
    try:
        row = db.execute(select(NationalStandardDocument, NationalStandardSource, NationalMajorCatalog)
                         .join(NationalStandardSource, NationalStandardSource.id == NationalStandardDocument.source_id)
                         .outerjoin(NationalMajorCatalog,
                                    NationalMajorCatalog.id == NationalStandardDocument.major_catalog_id)
                         .where(NationalStandardDocument.id == document_id,
                                NationalStandardDocument.is_deleted.is_(False),
                                NationalStandardDocument.status == "PUBLISHED")).first()
        if not row:
            raise AppException("DATA_NOT_FOUND", "国家标准文档不存在")
        document, source, major = row
        sections = db.scalars(select(NationalStandardSection).where(
            NationalStandardSection.document_id == document.id,
            NationalStandardSection.is_deleted.is_(False)).order_by(NationalStandardSection.section_no)).all()
        return {"id": str(document.id), "standardCode": document.standard_code,
                "documentType": document.document_type,
                "title": document.title, "educationLevel": document.education_level,
                "majorCode": document.major_code, "majorName": document.major_name,
                "categoryCode": major.category_code if major else "",
                "categoryName": major.category_name if major else "",
                "majorClassCode": major.major_class_code if major else "",
                "majorClassName": major.major_class_name if major else "",
                "versionLabel": document.version_label, "publishedDate": str(document.published_date or ""),
                "pageCount": document.page_count, "charCount": document.char_count,
                "textStatus": document.text_status, "sourceUrl": document.source_url,
                "source": {"publisher": source.publisher, "title": source.title,
                           "versionLabel": source.version_label, "isOfficial": source.is_official,
                           "copyrightPolicy": source.copyright_policy},
                "sections": [{"code": item.section_code, "no": item.section_no,
                              "title": item.section_title, "content": item.content_text}
                             for item in sections],
                "extractionError": document.extraction_error or ""}
    finally:
        db.close()


def catalog(education_level: str = "", category_code: str = "", keyword: str = "",
            page: int = 1, page_size: int = 100) -> dict:
    education_level = str(education_level or "").strip().upper()
    if education_level and education_level not in LEVELS:
        raise AppException("VALIDATION_ERROR", "教育层次筛选值无效")
    page = max(int(page), 1); page_size = min(max(int(page_size), 1), 300)
    db = get_sessionmaker()()
    try:
        conditions = [NationalMajorCatalog.is_deleted.is_(False),
                      NationalMajorCatalog.directory_status == "ACTIVE"]
        if education_level: conditions.append(NationalMajorCatalog.education_level == education_level)
        if category_code: conditions.append(NationalMajorCatalog.category_code == str(category_code).strip())
        if keyword:
            like = f"%{str(keyword).strip()}%"
            conditions.append(or_(NationalMajorCatalog.major_code.like(like),
                                  NationalMajorCatalog.major_name.like(like)))
        total = int(db.scalar(select(func.count(NationalMajorCatalog.id)).where(*conditions)) or 0)
        rows = db.scalars(select(NationalMajorCatalog).where(*conditions)
                          .order_by(NationalMajorCatalog.education_level,
                                    NationalMajorCatalog.major_code)
                          .offset((page - 1) * page_size).limit(page_size)).all()
        return {"list": [{"id": str(x.id), "catalogVersion": x.catalog_version,
                          "educationLevel": x.education_level, "categoryCode": x.category_code,
                          "categoryName": x.category_name, "majorClassCode": x.major_class_code,
                          "majorClassName": x.major_class_name, "majorCode": x.major_code,
                          "majorName": x.major_name} for x in rows],
                "total": total, "page": page, "pageSize": page_size}
    finally:
        db.close()


def bind_school_major(user: dict, body: dict) -> dict:
    tenant_id = _tenant_id()
    try:
        school_major_id = int(body.get("schoolMajorId")); document_id = int(body.get("documentId"))
    except (TypeError, ValueError) as exc:
        raise AppException("VALIDATION_ERROR", "schoolMajorId 和 documentId 必填") from exc
    db = get_sessionmaker()()
    try:
        school_major = db.scalars(select(Major).where(
            Major.id == school_major_id, Major.tenant_id == tenant_id,
            Major.is_deleted.is_(False))).first()
        document = db.scalars(select(NationalStandardDocument).where(
            NationalStandardDocument.id == document_id,
            NationalStandardDocument.status == "PUBLISHED",
            NationalStandardDocument.is_deleted.is_(False))).first()
        if not school_major or not document:
            raise AppException("DATA_NOT_FOUND", "学校专业或国家标准不存在")
        exact = (str(school_major.code or "").strip() == document.major_code
                 or str(school_major.major_name).strip() == document.major_name)
        if not exact and str(body.get("confirmText") or "").strip() != "确认跨专业绑定":
            raise AppException("VALIDATION_ERROR", "学校专业与国标专业代码/名称不一致，请输入“确认跨专业绑定”")
        current = db.scalars(select(SchoolMajorStandardBinding).where(
            SchoolMajorStandardBinding.tenant_id == tenant_id,
            SchoolMajorStandardBinding.school_major_id == school_major.id,
            SchoolMajorStandardBinding.is_deleted.is_(False))).all()
        for item in current:
            item.is_primary = False; item.binding_status = "SUPERSEDED"; item.version += 1
        existing = next((x for x in current if x.document_id == document.id), None)
        if existing:
            existing.binding_status = "ACTIVE"; existing.is_primary = True
            existing.selected_at = datetime.utcnow(); existing.selected_by = _actor(user)
            existing.note = str(body.get("note") or "").strip() or None; existing.version += 1
            binding = existing
        else:
            binding = SchoolMajorStandardBinding(tenant_id=tenant_id,
                school_major_id=school_major.id, document_id=document.id,
                binding_status="ACTIVE", is_primary=True, selected_by=_actor(user),
                note=str(body.get("note") or "").strip() or None,
                created_by=_actor(user), updated_by=_actor(user))
            db.add(binding)
        db.commit(); db.refresh(binding)
        audit_log.record("NATIONAL_STANDARD_BOUND", f"school-major:{school_major.id}",
                         {"documentId": str(document.id), "majorCode": document.major_code,
                          "exact": exact})
        return {"id": str(binding.id), "schoolMajorId": str(school_major.id),
                "schoolMajorName": school_major.major_name, "documentId": str(document.id),
                "standardTitle": document.title, "bindingStatus": binding.binding_status,
                "isPrimary": binding.is_primary}
    except Exception:
        db.rollback(); raise
    finally:
        db.close()


def school_bindings() -> list[dict]:
    tenant_id = _tenant_id(); db = get_sessionmaker()()
    try:
        rows = db.execute(select(SchoolMajorStandardBinding, Major, NationalStandardDocument)
                          .join(Major, Major.id == SchoolMajorStandardBinding.school_major_id)
                          .join(NationalStandardDocument,
                                NationalStandardDocument.id == SchoolMajorStandardBinding.document_id)
                          .where(SchoolMajorStandardBinding.tenant_id == tenant_id,
                                 SchoolMajorStandardBinding.is_deleted.is_(False))
                          .order_by(SchoolMajorStandardBinding.is_primary.desc(), Major.major_name)).all()
        return [{"id": str(binding.id), "schoolMajorId": str(major.id),
                 "schoolMajorName": major.major_name, "schoolMajorCode": major.code or "",
                 "documentId": str(document.id), "standardTitle": document.title,
                 "majorCode": document.major_code, "versionLabel": document.version_label,
                 "bindingStatus": binding.binding_status, "isPrimary": binding.is_primary,
                 "selectedAt": str(binding.selected_at)[:19]} for binding, major, document in rows]
    finally:
        db.close()


def source_status() -> list[dict]:
    db = get_sessionmaker()()
    try:
        rows = db.scalars(select(NationalStandardSource).where(
            NationalStandardSource.is_deleted.is_(False)).order_by(NationalStandardSource.id.desc())).all()
        return [{"id": str(x.id), "sourceKey": x.source_key, "title": x.title,
                 "versionLabel": x.version_label, "sourceUrl": x.source_url,
                 "retrievalStatus": x.retrieval_status, "itemCount": x.item_count,
                 "lastCrawledAt": str(x.last_crawled_at or "")[:19],
                 "manifestSha256": x.manifest_sha256 or ""} for x in rows]
    finally:
        db.close()
