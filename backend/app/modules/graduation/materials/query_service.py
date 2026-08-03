"""Pure query side of the graduation material domain.

Every public function in this module is safe for GET handlers: it never adds,
updates, deletes, flushes or commits.  Missing catalog rows are represented from
the frozen rule with an outer join instead of being materialized on read.
"""
from __future__ import annotations

from typing import Any

from sqlalchemy import and_, case, exists, false, func, literal, or_, select, true
from sqlalchemy.orm import aliased

from app.core.exceptions import AppException, not_found
from app.core.permissions import has_permission
from app.models import (
    GraduationDefenseGroup,
    GraduationDefenseScore,
    GraduationFinal,
    GraduationMentor,
    GraduationProposal,
    GraduationReview,
    GraduationStudent,
    GraduationTemplate,
)
from app.models.data_exchange import ExportJob
from app.models.file import ArchiveManifest, ArchiveManifestItem, FileAsset, FileBinding, FileObject, FileVersion
from app.models.graduation_material import (
    GraduationMaterialItem,
    GraduationMaterialRule,
    GraduationStudentMaterial,
    GraduationTemplateAssetPolicy,
)
from app.modules.graduation.services.graduation_scope_service import assert_student_access
from app.services.db_service import _iso, _tid, session

from .definitions import (
    MANIFEST_ARCHIVE_TYPE, MANIFEST_TARGET_TYPE, MODULE_CODE, REVIEW_PERMISSION_BY_CODE, STAGE_GROUPS,
)


FULL_SCOPE_ROLES = {"PLATFORM_SUPER_ADMIN", "SCHOOL_ADMIN", "GRADUATION_ADMIN", "GD_GRADE_ADMIN"}
COLLEGE_SCOPE_ROLES = {"GD_COLLEGE_ADMIN", "COLLEGE_ADMIN"}
MAJOR_SCOPE_ROLES = {"GD_MAJOR_ADMIN"}
SAFE_SCAN = {"CLEAN", "PASSED", "NOT_REQUIRED"}


def current_student_id(user: dict) -> int:
    from app.modules.graduation.services.graduation_record_resolver import resolve_current_gd_student

    with session() as db:
        student = resolve_current_gd_student(db, user)
        if not student:
            raise not_found("毕业设计材料不存在")
        return int(student.id)


def _role(user: dict) -> str:
    return str((user or {}).get("currentRoleCode") or (user or {}).get("userType") or "").upper()


def _ids(user: dict, singular: str, plural: str) -> set[str]:
    result = {str(value) for value in ((user or {}).get(plural) or []) if str(value)}
    if (user or {}).get(singular) not in (None, ""):
        result.add(str((user or {})[singular]))
    return result


def student_scope_predicate(user: dict, student=GraduationStudent):
    """Return the SQL predicate for the actor's stable graduation relations."""
    role = _role(user)
    if role in FULL_SCOPE_ROLES:
        return true()
    if role == "STUDENT":
        student_no = str((user or {}).get("studentNo") or "").strip()
        profile_id = (user or {}).get("studentId") or (user or {}).get("studentProfileId")
        clauses = []
        if student_no:
            clauses.append(student.student_no == student_no)
        if str(profile_id or "").isdigit():
            clauses.append(student.student_id == int(profile_id))
        return or_(*clauses) if clauses else false()
    if role in COLLEGE_SCOPE_ROLES:
        values = _ids(user, "collegeId", "collegeIds")
        return student.college_id.in_(values) if values else false()
    if role in MAJOR_SCOPE_ROLES:
        values = _ids(user, "majorId", "majorIds")
        return student.major_id.in_(values) if values else false()

    login = str((user or {}).get("loginName") or "").strip()
    if not login:
        return false()
    mentor_ids = select(GraduationMentor.id).where(
        GraduationMentor.tenant_id == _tid(),
        GraduationMentor.teacher_no == login,
        GraduationMentor.is_deleted.is_(False),
    )
    if role in {"GD_MENTOR", "COUNSELOR"}:
        return student.mentor_id.in_(mentor_ids)
    if role == "GD_REVIEWER":
        return exists(select(literal(1)).where(
            GraduationReview.tenant_id == student.tenant_id,
            GraduationReview.gd_student_id == student.id,
            GraduationReview.reviewer_mentor_id.in_(mentor_ids),
            GraduationReview.is_deleted.is_(False),
        ))
    if role == "GD_DEFENSE_SECRETARY":
        return exists(select(literal(1)).where(
            GraduationDefenseGroup.tenant_id == student.tenant_id,
            GraduationDefenseGroup.id == student.defense_group_id,
            GraduationDefenseGroup.secretary_mentor_id.in_(mentor_ids),
            GraduationDefenseGroup.is_deleted.is_(False),
        ))
    if role == "GD_DEFENSE_EXPERT":
        expert_id = (user or {}).get("expertId")
        clauses = [GraduationDefenseScore.judge_mentor_id.in_(mentor_ids)]
        if str(expert_id or "").isdigit():
            clauses.append(GraduationDefenseScore.expert_id == int(expert_id))
        return exists(select(literal(1)).where(
            GraduationDefenseScore.tenant_id == student.tenant_id,
            GraduationDefenseScore.gd_student_id == student.id,
            or_(*clauses),
            GraduationDefenseScore.is_deleted.is_(False),
        ))
    return false()


def _rule_view(rule: GraduationMaterialRule, items: list[GraduationMaterialItem]) -> dict:
    return {
        "id": str(rule.id),
        "batchId": str(rule.batch_id or ""),
        "ruleCode": rule.rule_code,
        "ruleName": rule.rule_name,
        "ruleVersion": int(rule.rule_version or 1),
        "status": rule.status,
        "enabled": bool(rule.enabled),
        "ownerRole": rule.default_owner_role,
        "versionPolicy": rule.version_policy,
        "archiveRequired": bool(rule.archive_required),
        "sensitivityLevel": rule.sensitivity_level,
        "effectiveAt": _iso(rule.effective_at),
        "allowedExtensions": rule.allowed_ext_json or [],
        "maxSizeBytes": int(rule.max_size_bytes or 0),
        "maxFileCount": int(rule.max_files or 0),
        "items": [{
            "id": str(item.id),
            "materialCode": item.material_code,
            "materialName": item.material_name,
            "stage": item.biz_stage,
            "ownerRole": item.owner_role,
            "required": bool(item.required),
            "allowedExtensions": item.allowed_ext_json or [],
            "maxSizeBytes": int(item.max_size_bytes or 0),
            "maxFileCount": int(item.max_files or 1),
            "versionPolicy": item.version_policy,
            "reviewRequired": bool(item.review_required),
            "archiveRequired": bool(item.archive_required),
            "sensitivityLevel": item.sensitivity_level,
            "sortOrder": int(item.sort_no or 0),
            "enabled": bool(item.enabled),
        } for item in items],
    }


def list_rules(batch_id: int | None, user: dict) -> dict:
    del user
    with session() as db:
        stmt = select(GraduationMaterialRule).where(
            GraduationMaterialRule.tenant_id == _tid(),
            GraduationMaterialRule.is_deleted.is_(False),
        )
        if batch_id:
            stmt = stmt.where(or_(
                GraduationMaterialRule.batch_id == int(batch_id),
                GraduationMaterialRule.batch_id.is_(None),
            ))
        else:
            stmt = stmt.where(GraduationMaterialRule.batch_id.is_(None))
        rules = list(db.scalars(stmt.order_by(
            GraduationMaterialRule.batch_id,
            GraduationMaterialRule.rule_version.desc(),
            GraduationMaterialRule.id.desc(),
        )).all())
        rule_ids = {int(row.id) for row in rules}
        items = list(db.scalars(select(GraduationMaterialItem).where(
            GraduationMaterialItem.tenant_id == _tid(),
            GraduationMaterialItem.rule_id.in_(rule_ids or {-1}),
            GraduationMaterialItem.is_deleted.is_(False),
        ).order_by(GraduationMaterialItem.rule_id, GraduationMaterialItem.sort_no, GraduationMaterialItem.id)).all())
        by_rule: dict[int, list[GraduationMaterialItem]] = {}
        for item in items:
            by_rule.setdefault(int(item.rule_id), []).append(item)
        return {"items": [_rule_view(row, by_rule.get(int(row.id), [])) for row in rules], "total": len(rules)}


def _base_students(user: dict, batch_id: int, filters: dict[str, str]):
    stmt = select(GraduationStudent).where(
        GraduationStudent.tenant_id == _tid(),
        GraduationStudent.batch_id == int(batch_id),
        GraduationStudent.record_status == "ACTIVE",
        GraduationStudent.is_deleted.is_(False),
        student_scope_predicate(user),
    )
    if filters.get("college_id"):
        stmt = stmt.where(GraduationStudent.college_id == filters["college_id"])
    if filters.get("major_id"):
        stmt = stmt.where(GraduationStudent.major_id == filters["major_id"])
    if filters.get("class_id"):
        stmt = stmt.where(GraduationStudent.class_id == filters["class_id"])
    if filters.get("advisor"):
        stmt = stmt.where(GraduationStudent.advisor_name.like(f"%{filters['advisor']}%"))
    if filters.get("keyword"):
        like = f"%{filters['keyword']}%"
        stmt = stmt.where(or_(
            GraduationStudent.name.like(like),
            GraduationStudent.student_no.like(like),
            GraduationStudent.topic_title.like(like),
        ))
    return stmt


def _facts(base_students, material_filters: dict[str, str] | None = None):
    base = base_students.with_only_columns(
        GraduationStudent.id.label("gd_student_id"),
        GraduationStudent.batch_id.label("batch_id"),
        GraduationStudent.stage.label("student_stage"),
    ).subquery()
    rule = aliased(GraduationMaterialRule)
    active_rule_row = aliased(GraduationMaterialRule)
    archived_material = aliased(GraduationStudentMaterial)
    item = aliased(GraduationMaterialItem)
    material = aliased(GraduationStudentMaterial)
    version = aliased(FileVersion)
    file_obj = aliased(FileObject)
    active_rule_id = select(active_rule_row.id).where(
        active_rule_row.tenant_id == _tid(),
        active_rule_row.batch_id == base.c.batch_id,
        active_rule_row.status == "ENABLED",
        active_rule_row.enabled.is_(True),
        active_rule_row.is_deleted.is_(False),
    ).order_by(active_rule_row.rule_version.desc(), active_rule_row.id.desc()).limit(1).correlate(base).scalar_subquery()
    archived_rule_id = select(func.max(archived_material.rule_id)).where(
        archived_material.tenant_id == _tid(),
        archived_material.gd_student_id == base.c.gd_student_id,
        archived_material.archive_status.in_(("FROZEN", "ARCHIVED")),
        archived_material.is_deleted.is_(False),
    ).correlate(base).scalar_subquery()
    effective_rule_id = case(
        (func.upper(func.coalesce(base.c.student_stage, "")) == "ARCHIVED", archived_rule_id),
        else_=active_rule_id,
    )
    stmt = select(
        base.c.gd_student_id,
        item.material_code,
        item.required,
        item.archive_required,
        material.id.label("material_id"),
        material.business_status,
        material.review_status,
        material.archive_status,
        material.current_version_id,
        file_obj.scan_status,
        file_obj.status.label("file_status"),
    ).select_from(base).join(rule, and_(
        rule.tenant_id == _tid(),
        rule.id == effective_rule_id,
        rule.is_deleted.is_(False),
    )).join(item, and_(
        item.tenant_id == _tid(),
        item.rule_id == rule.id,
        item.enabled.is_(True),
        item.is_deleted.is_(False),
    )).outerjoin(material, and_(
        material.tenant_id == _tid(),
        material.batch_id == base.c.batch_id,
        material.gd_student_id == base.c.gd_student_id,
        material.rule_id == rule.id,
        material.material_code == item.material_code,
        material.is_deleted.is_(False),
    )).outerjoin(version, and_(
        version.tenant_id == _tid(),
        version.id == material.current_version_id,
        version.is_deleted.is_(False),
    )).outerjoin(file_obj, and_(
        file_obj.tenant_id == _tid(),
        file_obj.id == version.file_object_id,
        file_obj.is_deleted.is_(False),
    ))
    filters = material_filters or {}
    if filters.get("stage"):
        stmt = stmt.where(item.biz_stage == filters["stage"].upper())
    if filters.get("material_code"):
        stmt = stmt.where(item.material_code == filters["material_code"].upper())
    if filters.get("review_status"):
        stmt = stmt.where(material.review_status == filters["review_status"].upper())
    if filters.get("archive_status"):
        stmt = stmt.where(material.archive_status == filters["archive_status"].upper())
    if filters.get("scan_status"):
        wanted_scan = filters["scan_status"].upper()
        stmt = stmt.where(
            or_(file_obj.status.is_(None), file_obj.status != "AVAILABLE",
                func.upper(func.coalesce(file_obj.scan_status, "")).not_in(SAFE_SCAN))
            if wanted_scan == "ABNORMAL" else file_obj.scan_status == wanted_scan
        )
    if filters.get("missing_status", "").upper() == "MISSING":
        stmt = stmt.where(or_(material.id.is_(None), material.business_status == "MISSING"))
    return stmt


def _student_aggregate(facts):
    fact = facts.subquery()
    required_archive = and_(fact.c.required.is_(True), fact.c.archive_required.is_(True))
    missing = or_(fact.c.material_id.is_(None), fact.c.current_version_id.is_(None), fact.c.business_status == "MISSING")
    unsafe = or_(
        fact.c.file_status.is_(None),
        fact.c.file_status != "AVAILABLE",
        func.upper(func.coalesce(fact.c.scan_status, "" )).not_in(SAFE_SCAN),
    )
    return select(
        fact.c.gd_student_id,
        func.sum(case((required_archive, 1), else_=0)).label("required_count"),
        func.sum(case((and_(required_archive, missing), 1), else_=0)).label("missing_count"),
        func.sum(case((and_(fact.c.archive_required.is_(True), fact.c.current_version_id.is_not(None),
                                  fact.c.review_status == "PENDING"), 1), else_=0)).label("pending_count"),
        func.sum(case((and_(fact.c.archive_required.is_(True), fact.c.current_version_id.is_not(None),
                                  fact.c.review_status == "RETURNED"), 1), else_=0)).label("returned_count"),
        func.sum(case((and_(required_archive, fact.c.review_status.in_(("APPROVED", "NOT_REQUIRED"))), 1), else_=0)).label("approved_count"),
        func.sum(case((and_(fact.c.archive_required.is_(True), fact.c.current_version_id.is_not(None), unsafe), 1), else_=0)).label("scan_abnormal_count"),
        func.sum(case((and_(fact.c.archive_required.is_(True),
                                  fact.c.archive_status.in_(("FROZEN", "ARCHIVED"))), 1), else_=0)).label("archived_count"),
    ).group_by(fact.c.gd_student_id)


def _summary(db, aggregate) -> dict:
    agg = aggregate.subquery()
    ready = and_(
        agg.c.required_count > 0,
        agg.c.missing_count == 0,
        agg.c.pending_count == 0,
        agg.c.returned_count == 0,
        agg.c.scan_abnormal_count == 0,
        agg.c.approved_count == agg.c.required_count,
    )
    row = db.execute(select(
        func.count().label("expected_students"),
        func.coalesce(func.sum(case((agg.c.missing_count > 0, 1), else_=0)), 0).label("missing_students"),
        func.coalesce(func.sum(case((agg.c.pending_count > 0, 1), else_=0)), 0).label("pending_students"),
        func.coalesce(func.sum(case((agg.c.returned_count > 0, 1), else_=0)), 0).label("returned_students"),
        func.coalesce(func.sum(case((agg.c.scan_abnormal_count > 0, 1), else_=0)), 0).label("scan_students"),
        func.coalesce(func.sum(case((ready, 1), else_=0)), 0).label("ready_students"),
        func.coalesce(func.sum(case((agg.c.archived_count > 0, 1), else_=0)), 0).label("archived_students"),
    )).one()
    return {
        "expectedStudents": int(row.expected_students or 0),
        "completeStudents": int(row.ready_students or 0),
        "missingStudents": int(row.missing_students or 0),
        "pendingReviewStudents": int(row.pending_students or 0),
        "returnedStudents": int(row.returned_students or 0),
        "scanAbnormalStudents": int(row.scan_students or 0),
        "archiveReadyStudents": int(row.ready_students or 0),
        "archivedStudents": int(row.archived_students or 0),
    }


def students(user: dict, *, batch_id: int, page: int = 1, page_size: int = 20, **filters) -> dict:
    page = max(1, int(page or 1))
    page_size = min(100, max(1, int(page_size or 20)))
    with session() as db:
        base = _base_students(user, batch_id, filters)
        filtered_agg = _student_aggregate(_facts(base, filters))
        archive_agg = _student_aggregate(_facts(base))
        filtered_summary = _summary(db, filtered_agg)
        archive_summary = _summary(db, archive_agg)
        filtered = filtered_agg.subquery()
        archive = archive_agg.subquery()
        page_stmt = select(GraduationStudent, archive).join(
            filtered, filtered.c.gd_student_id == GraduationStudent.id,
        ).join(archive, archive.c.gd_student_id == GraduationStudent.id).where(
            GraduationStudent.tenant_id == _tid(),
            GraduationStudent.batch_id == int(batch_id),
            GraduationStudent.is_deleted.is_(False),
        ).order_by(
            GraduationStudent.college_id,
            GraduationStudent.class_id,
            GraduationStudent.student_no,
            GraduationStudent.id,
        ).offset((page - 1) * page_size).limit(page_size)
        result_rows = db.execute(page_stmt).all()
        items = []
        for result in result_rows:
            student = result[0]
            values = result._mapping
            required = int(values.get("required_count") or 0)
            missing = int(values.get("missing_count") or 0)
            pending = int(values.get("pending_count") or 0)
            returned = int(values.get("returned_count") or 0)
            abnormal = int(values.get("scan_abnormal_count") or 0)
            approved = int(values.get("approved_count") or 0)
            items.append({
                "gdStudentId": str(student.id),
                "studentId": str(student.student_id or ""),
                "studentNo": student.student_no or "",
                "studentName": student.name,
                "batchId": str(student.batch_id or ""),
                "collegeId": str(student.college_id or ""),
                "majorId": str(student.major_id or ""),
                "classId": str(student.class_id or ""),
                "className": student.class_name or "",
                "advisorName": student.advisor_name or "",
                "topicTitle": student.topic_title or "",
                "requiredCount": required,
                "missingCount": missing,
                "pendingReviewCount": pending,
                "returnedCount": returned,
                "approvedRequiredCount": approved,
                "scanAbnormalCount": abnormal,
                "archiveReady": bool(required and approved == required and missing == pending == returned == abnormal == 0),
            })
        return {
            "filteredSummary": filtered_summary,
            "archiveSummary": archive_summary,
            "summary": filtered_summary,
            "items": items,
            "total": filtered_summary["expectedStudents"],
            "page": page,
            "pageSize": page_size,
        }


def summary(user: dict, *, batch_id: int, **filters) -> dict:
    with session() as db:
        base = _base_students(user, batch_id, filters)
        return {
            "filteredSummary": _summary(db, _student_aggregate(_facts(base, filters))),
            "archiveSummary": _summary(db, _student_aggregate(_facts(base))),
        }


def files(user: dict, *, batch_id: int, page: int = 1, page_size: int = 20, **filters) -> dict:
    page = max(1, int(page or 1))
    page_size = min(100, max(1, int(page_size or 20)))
    with session() as db:
        stmt = select(
            GraduationStudent,
            GraduationStudentMaterial,
            FileAsset,
            FileVersion,
            FileObject,
        ).join(
            GraduationStudentMaterial,
            and_(
                GraduationStudentMaterial.tenant_id == GraduationStudent.tenant_id,
                GraduationStudentMaterial.gd_student_id == GraduationStudent.id,
                GraduationStudentMaterial.is_deleted.is_(False),
            ),
        ).outerjoin(
            FileAsset,
            and_(FileAsset.tenant_id == GraduationStudentMaterial.tenant_id,
                 FileAsset.id == GraduationStudentMaterial.asset_id,
                 FileAsset.is_deleted.is_(False)),
        ).outerjoin(
            FileVersion,
            and_(FileVersion.tenant_id == GraduationStudentMaterial.tenant_id,
                 FileVersion.id == GraduationStudentMaterial.current_version_id,
                 FileVersion.is_deleted.is_(False)),
        ).outerjoin(
            FileObject,
            and_(FileObject.tenant_id == GraduationStudentMaterial.tenant_id,
                 FileObject.id == FileVersion.file_object_id,
                 FileObject.is_deleted.is_(False)),
        ).where(
            GraduationStudent.tenant_id == _tid(),
            GraduationStudent.batch_id == int(batch_id),
            GraduationStudent.record_status == "ACTIVE",
            GraduationStudent.is_deleted.is_(False),
            student_scope_predicate(user),
        )
        if filters.get("college_id"):
            stmt = stmt.where(GraduationStudent.college_id == filters["college_id"])
        if filters.get("major_id"):
            stmt = stmt.where(GraduationStudent.major_id == filters["major_id"])
        if filters.get("class_id"):
            stmt = stmt.where(GraduationStudent.class_id == filters["class_id"])
        if filters.get("advisor"):
            stmt = stmt.where(GraduationStudent.advisor_name.like(f"%{filters['advisor']}%"))
        if filters.get("keyword"):
            like = f"%{filters['keyword']}%"
            stmt = stmt.where(or_(GraduationStudent.name.like(like), GraduationStudent.student_no.like(like),
                                  GraduationStudent.topic_title.like(like), FileObject.file_name.like(like)))
        if filters.get("stage"):
            stmt = stmt.where(GraduationStudentMaterial.biz_stage == filters["stage"].upper())
        if filters.get("material_code"):
            stmt = stmt.where(GraduationStudentMaterial.material_code == filters["material_code"].upper())
        if filters.get("review_status"):
            stmt = stmt.where(GraduationStudentMaterial.review_status == filters["review_status"].upper())
        if filters.get("archive_status"):
            stmt = stmt.where(GraduationStudentMaterial.archive_status == filters["archive_status"].upper())
        if filters.get("scan_status"):
            wanted_scan = filters["scan_status"].upper()
            stmt = stmt.where(
                or_(FileObject.status != "AVAILABLE",
                    func.upper(func.coalesce(FileObject.scan_status, "")).not_in(SAFE_SCAN))
                if wanted_scan == "ABNORMAL" else FileObject.scan_status == wanted_scan
            )
        count_stmt = select(func.count()).select_from(stmt.order_by(None).subquery())
        total = int(db.scalar(count_stmt) or 0)
        rows = db.execute(stmt.order_by(
            GraduationStudent.college_id,
            GraduationStudent.class_id,
            GraduationStudent.student_no,
            GraduationStudentMaterial.biz_stage,
            GraduationStudentMaterial.id,
        ).offset((page - 1) * page_size).limit(page_size)).all()
        items = []
        for student, material, asset, version, file_obj in rows:
            ready = bool(file_obj and file_obj.status == "AVAILABLE" and str(file_obj.scan_status or "").upper() in SAFE_SCAN)
            actions = ["viewMetadata"] + (["preview", "download"] if ready else [])
            review_permission = REVIEW_PERMISSION_BY_CODE.get(str(material.material_code or "").upper())
            if material.review_status == "PENDING" and review_permission and has_permission(user or {}, review_permission):
                actions.append("review")
            items.append({
                "materialId": str(material.id),
                "gdStudentId": str(student.id),
                "studentId": str(student.student_id or ""),
                "studentName": student.name,
                "studentNo": student.student_no or "",
                "collegeId": str(student.college_id or ""),
                "majorId": str(student.major_id or ""),
                "classId": str(student.class_id or ""),
                "className": student.class_name or "",
                "advisorName": student.advisor_name or "",
                "stage": material.biz_stage,
                "materialCode": material.material_code,
                "materialName": material.material_name,
                "version": int(material.version or 0),
                "fileId": str(file_obj.id if file_obj else ""),
                "fileName": file_obj.file_name if file_obj else "",
                "assetId": str(asset.id if asset else ""),
                "currentVersionId": str(version.id if version else ""),
                "currentVersion": int(version.version_no or 0) if version else 0,
                "historyVersionCount": int(asset.version_count or 0) if asset else 0,
                "uploader": version.uploader_name_snapshot if version else "",
                "uploadedAt": _iso(version.submitted_at) if version else None,
                "sizeBytes": int(file_obj.size_bytes or 0) if file_obj else 0,
                "scanStatus": file_obj.scan_status if file_obj else "MISSING",
                "reviewStatus": material.review_status,
                "archiveStatus": material.archive_status,
                "businessStatus": material.business_status,
                "readyForBusiness": ready,
                "allowedActions": actions,
            })
        return {"items": items, "total": total, "page": page, "pageSize": page_size}


def _version_dto(version: FileVersion, file_obj: FileObject, *, student_mode: bool) -> dict:
    ready = file_obj.status == "AVAILABLE" and str(file_obj.scan_status or "").upper() in SAFE_SCAN
    base = "/api/v1/mobile/graduation/material-center/files" if student_mode else "/api/v1/graduation/material-center/files"
    return {
        "assetId": str(version.asset_id),
        "versionId": str(version.id),
        "versionNo": int(version.version_no or 1),
        "isCurrent": bool(version.is_current),
        "versionStatus": version.status,
        "fileId": str(file_obj.id),
        "fileName": file_obj.file_name,
        "sizeBytes": int(file_obj.size_bytes or 0),
        "sha256": file_obj.sha256,
        "status": file_obj.status,
        "scanStatus": file_obj.scan_status,
        "readyForBusiness": ready,
        "allowedActions": ["viewMetadata"] + (["preview", "download"] if ready else []),
        "previewUrl": f"{base}/{file_obj.id}/preview" if ready else None,
        "downloadUrl": f"{base}/{file_obj.id}/download" if ready else None,
        "uploader": version.uploader_name_snapshot or "",
        "submittedAt": _iso(version.submitted_at),
    }


def _rule_for_student(db, student: GraduationStudent) -> GraduationMaterialRule:
    if str(student.stage or "").upper() == "ARCHIVED":
        rule_ids = set(db.scalars(select(GraduationStudentMaterial.rule_id).where(
            GraduationStudentMaterial.tenant_id == _tid(),
            GraduationStudentMaterial.gd_student_id == int(student.id),
            GraduationStudentMaterial.archive_status.in_(("FROZEN", "ARCHIVED")),
            GraduationStudentMaterial.rule_id.is_not(None),
            GraduationStudentMaterial.is_deleted.is_(False),
        ).distinct()).all())
        if len(rule_ids) != 1:
            raise AppException("MATERIAL_RULE_CONFLICT", "已归档材料缺少唯一冻结规则")
        rule = db.scalars(select(GraduationMaterialRule).where(
            GraduationMaterialRule.tenant_id == _tid(),
            GraduationMaterialRule.id == int(next(iter(rule_ids))),
            GraduationMaterialRule.is_deleted.is_(False),
        )).first()
    else:
        rule = db.scalars(select(GraduationMaterialRule).where(
            GraduationMaterialRule.tenant_id == _tid(),
            GraduationMaterialRule.batch_id == int(student.batch_id or 0),
            GraduationMaterialRule.status == "ENABLED",
            GraduationMaterialRule.enabled.is_(True),
            GraduationMaterialRule.is_deleted.is_(False),
        ).order_by(GraduationMaterialRule.rule_version.desc(), GraduationMaterialRule.id.desc())).first()
    if not rule:
        raise AppException("MATERIAL_RULE_NOT_INITIALIZED", "学生材料规则不存在")
    return rule


def student_library(gd_student_id: int | None, user: dict, *, include_history: bool = True) -> dict:
    with session() as db:
        if _role(user) == "STUDENT":
            stmt = select(GraduationStudent).where(
                GraduationStudent.tenant_id == _tid(),
                GraduationStudent.record_status == "ACTIVE",
                GraduationStudent.is_deleted.is_(False),
                student_scope_predicate(user),
            )
            student = db.scalars(stmt.order_by(GraduationStudent.id.desc())).first()
            if not student or (gd_student_id and int(gd_student_id) != int(student.id)):
                raise not_found("毕业设计材料库不存在")
        else:
            if not gd_student_id:
                raise AppException("VALIDATION_ERROR", "缺少毕业设计学生 ID")
            student = db.get(GraduationStudent, int(gd_student_id))
            if not student or student.tenant_id != _tid() or student.is_deleted:
                raise not_found("毕业设计材料库不存在")
            assert_student_access(db, student, "material.library")
        rule = _rule_for_student(db, student)
        rows = db.execute(select(GraduationMaterialItem, GraduationStudentMaterial).outerjoin(
            GraduationStudentMaterial,
            and_(
                GraduationStudentMaterial.tenant_id == GraduationMaterialItem.tenant_id,
                GraduationStudentMaterial.batch_id == int(student.batch_id),
                GraduationStudentMaterial.gd_student_id == int(student.id),
                GraduationStudentMaterial.material_code == GraduationMaterialItem.material_code,
                GraduationStudentMaterial.is_deleted.is_(False),
            ),
        ).where(
            GraduationMaterialItem.tenant_id == _tid(),
            GraduationMaterialItem.rule_id == int(rule.id),
            GraduationMaterialItem.enabled.is_(True),
            GraduationMaterialItem.is_deleted.is_(False),
        ).order_by(GraduationMaterialItem.sort_no, GraduationMaterialItem.id)).all()
        asset_ids = {int(material.asset_id) for _, material in rows if material and material.asset_id}
        versions = list(db.scalars(select(FileVersion).where(
            FileVersion.tenant_id == _tid(),
            FileVersion.asset_id.in_(asset_ids or {-1}),
            FileVersion.is_deleted.is_(False),
            true() if include_history else FileVersion.is_current.is_(True),
        ).order_by(FileVersion.asset_id, FileVersion.version_no.desc(), FileVersion.id.desc())).all())
        files_by_id = {int(row.id): row for row in db.scalars(select(FileObject).where(
            FileObject.tenant_id == _tid(),
            FileObject.id.in_({int(version.file_object_id) for version in versions} or {-1}),
            FileObject.is_deleted.is_(False),
        )).all()}
        versions_by_asset: dict[int, list[dict]] = {}
        for version in versions:
            file_obj = files_by_id.get(int(version.file_object_id))
            if file_obj:
                versions_by_asset.setdefault(int(version.asset_id), []).append(
                    _version_dto(version, file_obj, student_mode=_role(user) == "STUDENT")
                )
        items = []
        for definition, material in rows:
            history = versions_by_asset.get(int(material.asset_id), []) if material and material.asset_id else []
            current = next((row for row in history if row["isCurrent"]), None)
            items.append({
                "materialId": str(material.id if material else ""),
                "initialized": material is not None,
                "materialCode": definition.material_code,
                "materialName": definition.material_name,
                "stage": definition.biz_stage,
                "ownerRole": definition.owner_role,
                "required": bool(definition.required),
                "requiredStatus": material.required_status if material else ("REQUIRED" if definition.required else "OPTIONAL"),
                "businessStatus": material.business_status if material else "MISSING",
                "reviewStatus": material.review_status if material else "NOT_SUBMITTED",
                "archiveStatus": material.archive_status if material else "NOT_ARCHIVED",
                "sensitivityLevel": definition.sensitivity_level,
                "assetId": str(material.asset_id or "") if material else "",
                "currentVersionId": str(material.current_version_id or "") if material else "",
                "version": int(material.version or 0) if material else 0,
                "currentVersion": current,
                "versions": history,
                "versionCount": len(history),
                "rejectReason": material.reject_reason or "" if material else "",
                "reviewer": material.reviewer_name or "" if material else "",
                "reviewedAt": _iso(material.reviewed_at) if material else None,
                "submittedAt": _iso(material.submitted_at) if material else None,
                "archiveRequired": bool(definition.archive_required),
                "allowedActions": list((current or {}).get("allowedActions", [])),
            })
        groups = [{"name": name, "items": [row for row in items if row["stage"] in stages]} for name, stages in STAGE_GROUPS]
        return {
            "gdStudentId": str(student.id),
            "studentId": str(student.student_id or ""),
            "studentName": student.name,
            "studentNo": student.student_no or "",
            "batchId": str(student.batch_id or ""),
            "collegeId": str(student.college_id or ""),
            "majorId": str(student.major_id or ""),
            "classId": str(student.class_id or ""),
            "advisorName": student.advisor_name or "",
            "topicTitle": student.topic_title or "",
            "ruleId": str(rule.id),
            "ruleVersion": int(rule.rule_version),
            "items": items,
            "groups": groups,
            "total": len(items),
        }


def record_versions(record_type: str, record_id: int, user: dict, *, student_mode: bool = False, include_history: bool = True) -> list[dict]:
    normalized = str(record_type or "").upper()
    model = GraduationProposal if normalized == "PROPOSAL" else GraduationFinal if normalized == "FINAL" else None
    relation = "GRADUATION_PROPOSAL_MATERIAL" if normalized == "PROPOSAL" else "GRADUATION_FINAL_MATERIAL"
    if model is None:
        raise AppException("VALIDATION_ERROR", "未知毕业设计记录类型")
    with session() as db:
        record = db.scalars(select(model).where(
            model.tenant_id == _tid(), model.id == int(record_id), model.is_deleted.is_(False),
        )).first()
        if not record:
            raise not_found("毕业设计记录不存在")
        student = db.get(GraduationStudent, int(record.gd_student_id))
        assert_student_access(db, student, "material.versions")
        materials = list(db.scalars(select(GraduationStudentMaterial).where(
            GraduationStudentMaterial.tenant_id == _tid(),
            GraduationStudentMaterial.gd_student_id == int(record.gd_student_id),
            GraduationStudentMaterial.source_record_type == normalized,
            GraduationStudentMaterial.source_record_id == str(record_id),
            GraduationStudentMaterial.is_deleted.is_(False),
        )).all())
        asset_ids = {int(row.asset_id) for row in materials if row.asset_id}
        version_stmt = select(FileVersion).where(
            FileVersion.tenant_id == _tid(),
            FileVersion.asset_id.in_(asset_ids or {-1}),
            FileVersion.is_deleted.is_(False),
        )
        if not include_history:
            version_stmt = version_stmt.where(FileVersion.is_current.is_(True))
        versions = {int(row.id): row for row in db.scalars(version_stmt).all()}
        bindings = list(db.scalars(select(FileBinding).where(
            FileBinding.tenant_id == _tid(),
            FileBinding.module_code == "graduation",
            FileBinding.version_id.in_(set(versions) or {-1}),
            FileBinding.is_deleted.is_(False),
        ).order_by(FileBinding.version_no, FileBinding.id)).all())

        # Compatibility-only fallback for historical records not yet backfilled.
        if not bindings:
            legacy_stmt = select(FileBinding).where(
                FileBinding.tenant_id == _tid(),
                FileBinding.module_code == "graduation",
                FileBinding.biz_type == "GRADUATION_MATERIAL",
                FileBinding.biz_id == str(record_id),
                FileBinding.relation_type == relation,
                FileBinding.is_deleted.is_(False),
            )
            if not include_history:
                legacy_stmt = legacy_stmt.where(FileBinding.is_current.is_(True))
            bindings = list(db.scalars(legacy_stmt.order_by(FileBinding.version_no, FileBinding.id)).all())
            versions = {int(row.id): row for row in db.scalars(select(FileVersion).where(
                FileVersion.tenant_id == _tid(),
                FileVersion.id.in_({int(row.version_id) for row in bindings if row.version_id} or {-1}),
                FileVersion.is_deleted.is_(False),
            )).all()}
        file_rows = {int(row.id): row for row in db.scalars(select(FileObject).where(
            FileObject.tenant_id == _tid(),
            FileObject.id.in_({int(row.file_id) for row in bindings} or {-1}),
            FileObject.is_deleted.is_(False),
        )).all()}
        material_by_asset = {int(row.asset_id): row for row in materials if row.asset_id}
        result = []
        for binding in bindings:
            version = versions.get(int(binding.version_id or 0))
            file_obj = file_rows.get(int(binding.file_id))
            if not version or not file_obj:
                continue
            row = _version_dto(version, file_obj, student_mode=student_mode)
            material = material_by_asset.get(int(version.asset_id))
            row.update({
                "bindingId": str(binding.id),
                "isCurrent": bool(version.is_current and binding.is_current),
                "bindingStatus": binding.status,
                "materialCode": material.material_code if material else (binding.scope_json or {}).get("materialCode") or "GRADUATION_MATERIAL",
                "materialName": material.material_name if material else (binding.scope_json or {}).get("materialName") or file_obj.file_name,
                "materialId": str(material.id) if material else None,
                "materialVersion": int(material.version or 0) if material else None,
            })
            result.append(row)
        return sorted(result, key=lambda row: (row["versionNo"], row["versionId"]))


def _review_detail(record_type: str, record_id: int, user: dict) -> dict:
    from app.modules.graduation.services import graduation_service

    normalized = str(record_type).upper()
    detail = (
        graduation_service.get_proposal_detail(int(record_id))
        if normalized == "PROPOSAL"
        else graduation_service.get_final_detail(int(record_id))
    )
    versions = record_versions(normalized, int(record_id), user, include_history=False)
    attachments = [{
        "fileId": row["fileId"], "fileName": row["fileName"],
        "sizeBytes": row["sizeBytes"], "scanStatus": row["scanStatus"],
        "readyForBusiness": row["readyForBusiness"], "allowedActions": row["allowedActions"],
        "previewUrl": row["previewUrl"], "downloadUrl": row["downloadUrl"],
    } for row in versions]
    primary = next((row for row in versions if row.get("isCurrent")), None)
    detail.update({
        "currentSafeVersions": versions,
        "currentVersionCount": len({row["versionId"] for row in versions}),
        "reviewReady": bool(versions and all(row["readyForBusiness"] for row in versions)),
        "migrationRequired": not bool(versions),
        "attachments": len(attachments),
        "attachmentsList": attachments,
        "materialId": primary.get("materialId") if primary else None,
        "materialVersion": primary.get("materialVersion") if primary else None,
        "fileVersionId": primary.get("versionId") if primary else None,
    })
    return detail


def proposal_detail(proposal_id: int, user: dict) -> dict:
    return _review_detail("PROPOSAL", proposal_id, user)


def final_detail(final_id: int, user: dict) -> dict:
    return _review_detail("FINAL", final_id, user)


def template_catalog(user: dict, *, batch_id: int | None = None) -> dict:
    del user
    with session() as db:
        stmt = select(GraduationTemplateAssetPolicy).where(
            GraduationTemplateAssetPolicy.tenant_id == _tid(),
            GraduationTemplateAssetPolicy.is_deleted.is_(False),
        )
        if batch_id:
            stmt = stmt.where(or_(GraduationTemplateAssetPolicy.batch_id == int(batch_id), GraduationTemplateAssetPolicy.batch_id.is_(None)))
        policies = list(db.scalars(stmt.order_by(GraduationTemplateAssetPolicy.template_code, GraduationTemplateAssetPolicy.id)).all())
        templates = {int(row.id): row for row in db.scalars(select(GraduationTemplate).where(
            GraduationTemplate.tenant_id == _tid(), GraduationTemplate.is_deleted.is_(False),
        )).all()}
        versions = list(db.scalars(select(FileVersion).where(
            FileVersion.tenant_id == _tid(),
            FileVersion.asset_id.in_({int(row.asset_id) for row in policies if row.asset_id} or {-1}),
            FileVersion.is_deleted.is_(False),
        ).order_by(FileVersion.asset_id, FileVersion.version_no.desc(), FileVersion.id.desc())).all())
        file_rows = {int(row.id): row for row in db.scalars(select(FileObject).where(
            FileObject.tenant_id == _tid(),
            FileObject.id.in_({int(row.file_object_id) for row in versions} or {-1}),
            FileObject.is_deleted.is_(False),
        )).all()}
        by_asset: dict[int, list[dict]] = {}
        for version in versions:
            file_obj = file_rows.get(int(version.file_object_id))
            if file_obj:
                by_asset.setdefault(int(version.asset_id), []).append(_version_dto(version, file_obj, student_mode=False))
        items = []
        for policy in policies:
            template = templates.get(int(policy.template_id))
            if template:
                items.append({
                    "policyId": str(policy.id), "templateId": str(template.id),
                    "templateCode": policy.template_code, "templateName": template.name,
                    "templateType": template.template_type, "currentVersionId": str(policy.current_version_id or ""),
                    "batchId": str(policy.batch_id or ""), "collegeId": policy.college_id or "",
                    "majorId": policy.major_id or "", "enabled": bool(policy.enabled),
                    "status": policy.status, "version": int(policy.version or 0),
                    "effectiveAt": _iso(policy.effective_at), "variableSchema": policy.variable_schema_json or {},
                    "scope": policy.scope_json or {}, "versions": by_asset.get(int(policy.asset_id), []) if policy.asset_id else [],
                })
        return {"items": items, "total": len(items), "availableTemplates": [{
            "templateId": str(row.id), "templateName": row.name, "templateType": row.template_type, "status": row.status,
        } for row in templates.values()]}


def template_versions(template_id: int, user: dict | None = None) -> dict:
    del user
    with session() as db:
        asset = db.scalars(select(FileAsset).where(
            FileAsset.tenant_id == _tid(), FileAsset.owner_type == "GRADUATION_TEMPLATE",
            FileAsset.owner_id == str(template_id), FileAsset.is_deleted.is_(False),
        )).first()
        if not asset:
            return {"templateId": str(template_id), "items": [], "total": 0}
        versions = list(db.scalars(select(FileVersion).where(
            FileVersion.tenant_id == _tid(), FileVersion.asset_id == int(asset.id), FileVersion.is_deleted.is_(False),
        ).order_by(FileVersion.version_no.desc(), FileVersion.id.desc())).all())
        file_rows = {int(row.id): row for row in db.scalars(select(FileObject).where(
            FileObject.tenant_id == _tid(),
            FileObject.id.in_({int(row.file_object_id) for row in versions} or {-1}),
            FileObject.is_deleted.is_(False),
        )).all()}
        items = [_version_dto(row, file_rows[int(row.file_object_id)], student_mode=False)
                 for row in versions if int(row.file_object_id) in file_rows]
        return {"templateId": str(template_id), "items": items, "total": len(items)}


def latest_manifest(gd_student_id: int, user: dict) -> dict:
    with session() as db:
        student = db.scalars(select(GraduationStudent).where(
            GraduationStudent.tenant_id == _tid(), GraduationStudent.id == int(gd_student_id),
            GraduationStudent.is_deleted.is_(False),
        )).first()
        if not student:
            raise not_found("毕业设计归档清单不存在")
        assert_student_access(db, student, "archive.manifest.view")
        manifest = db.scalars(select(ArchiveManifest).where(
            ArchiveManifest.tenant_id == _tid(), ArchiveManifest.module_code == MODULE_CODE,
            ArchiveManifest.archive_type == MANIFEST_ARCHIVE_TYPE,
            ArchiveManifest.target_type == MANIFEST_TARGET_TYPE,
            ArchiveManifest.target_id == str(student.id), ArchiveManifest.is_deleted.is_(False),
        ).order_by(ArchiveManifest.revision.desc(), ArchiveManifest.id.desc())).first()
        if not manifest:
            raise not_found("毕业设计归档清单不存在")
        items = list(db.scalars(select(ArchiveManifestItem).where(
            ArchiveManifestItem.tenant_id == _tid(), ArchiveManifestItem.manifest_id == int(manifest.id),
            ArchiveManifestItem.is_deleted.is_(False),
        ).order_by(ArchiveManifestItem.sort_no, ArchiveManifestItem.id)).all())
        return {
            "manifestId": str(manifest.id), "revision": int(manifest.revision or 1), "status": manifest.status,
            "ruleVersion": manifest.rule_version or "", "manifestSha256": manifest.manifest_sha256 or "",
            "packageFileId": str(manifest.package_file_id or ""), "frozenAt": _iso(manifest.frozen_at),
            "revokedAt": _iso(manifest.revoked_at), "revokeReason": manifest.revoke_reason or "",
            "itemCount": len(items), "items": [{
                "materialCode": item.material_code, "assetId": str(item.asset_id),
                "fileVersionId": str(item.version_id), "versionId": str(item.version_id),
                "fileObjectId": str(item.file_object_id), "fileName": item.file_name_snapshot,
                "sizeBytes": item.size_snapshot, "sha256": item.sha256_snapshot,
                "scanResult": item.scan_result, "reviewStatus": item.review_status,
                "uploader": item.uploader_snapshot or "", "submittedAt": _iso(item.submitted_at_snapshot),
                "sortNo": int(item.sort_no or 0),
            } for item in items],
        }


def get_export_job(job_id: int, user: dict) -> dict:
    actor = (user or {}).get("userId") or (user or {}).get("sub")
    with session() as db:
        stmt = select(ExportJob).where(
            ExportJob.tenant_id == _tid(), ExportJob.id == int(job_id),
            ExportJob.module_code == MODULE_CODE, ExportJob.adapter_type == "GRADUATION_ARCHIVE",
            ExportJob.is_deleted.is_(False),
        )
        if str(actor or "").isdigit():
            stmt = stmt.where(ExportJob.operator_id == int(actor))
        row = db.scalars(stmt).first()
        if not row:
            raise not_found("毕业设计归档任务不存在")
        return {
            "id": str(row.id), "status": row.status, "progress": int(row.progress or 0),
            "rowCount": int(row.row_count or 0), "fileObjectId": str(row.file_object_id or ""),
            "expiresAt": _iso(row.expires_at), "revokedAt": _iso(row.revoked_at),
            "revokeReason": row.revoke_reason or "", "result": row.result_json or {},
            "errorMessage": row.error_message or "", "version": int(row.version or 0),
            "createdAt": _iso(row.created_at), "updatedAt": _iso(row.updated_at),
        }
