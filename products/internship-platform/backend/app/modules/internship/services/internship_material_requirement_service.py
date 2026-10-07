"""Yiyang C03/G09 configurable internship material collection workflow.

Business configuration lives here; file bytes, scan state, immutable versions and archive
manifests continue to use the shared FileObject/FileAsset/FileVersion/FileBinding foundation.
"""
from __future__ import annotations

import re
from datetime import datetime

from sqlalchemy import func, or_, select

from app.core.exceptions import AppException, not_found
from app.models import (
    InternshipAuditTrail,
    InternshipBatch,
    InternshipMaterialRequirement,
    InternshipMaterialSubmission,
    InternshipMaterialSubmissionFile,
    InternshipMaterialTemplateVersion,
    InternshipRecord,
    StudentProfile,
)
from app.models.file import FileAsset, FileBinding, FileObject, FileVersion
from app.modules.internship.services.internship_student_context_guard import require_explicit_context
from app.services import file_access_service, file_business_binding_service, file_service
from app.services.db_service import _as_id, _iso, _tid, session

_CODE = re.compile(r"^[A-Z0-9][A-Z0-9_-]{1,79}$")
_SUBMITTED = {"SUBMITTED", "APPROVED"}
_REVIEWED = {"APPROVED", "RETURNED"}


def _op_name(user=None):
    return str((user or {}).get("realName") or "系统")


def _trail(db, target_id, action, detail, user=None):
    db.add(InternshipAuditTrail(
        tenant_id=_tid(),
        target_id=int(target_id),
        target_type="MATERIAL_REQUIREMENT",
        action=action,
        operator_name=_op_name(user),
        detail_json=detail or {},
        occurred_at=datetime.utcnow(),
    ))


def _extensions(value) -> list[str]:
    if value in (None, ""):
        return ["pdf", "doc", "docx", "jpg", "jpeg", "png"]
    raw = value if isinstance(value, list) else str(value).split(",")
    out = []
    for item in raw:
        ext = str(item or "").strip().lower().lstrip(".")
        if not ext or not re.fullmatch(r"[a-z0-9]{1,12}", ext):
            raise AppException("VALIDATION_ERROR", "材料格式只允许扩展名，如 pdf、docx、jpg")
        if ext not in out:
            out.append(ext)
    if not out:
        raise AppException("VALIDATION_ERROR", "至少配置一种允许上传格式")
    return out


def _ids(value):
    if not isinstance(value, list):
        return []
    out = []
    for item in value:
        try:
            number = int(item)
        except (TypeError, ValueError):
            continue
        if number > 0 and number not in out:
            out.append(number)
    return out


def _requirement(db, requirement_id, *, lock=False):
    query = select(InternshipMaterialRequirement).where(
        InternshipMaterialRequirement.id == _as_id(requirement_id),
        InternshipMaterialRequirement.tenant_id == _tid(),
        InternshipMaterialRequirement.is_deleted.is_(False),
    )
    row = db.scalar(query.with_for_update() if lock else query)
    if not row:
        raise not_found("材料收件要求不存在")
    return row


def _template(db, requirement):
    if not requirement.current_template_version_id:
        return None
    row = db.get(InternshipMaterialTemplateVersion, requirement.current_template_version_id)
    if not row or row.is_deleted or row.tenant_id != _tid() or not row.is_current:
        return None
    return row


def _applies(requirement, student: StudentProfile) -> bool:
    kind = str(requirement.audience_type or "ALL").upper()
    rules = requirement.audience_filter_json or {}
    if kind == "ALL":
        return True
    if kind == "SELECTED_STUDENTS":
        return int(student.id) in _ids(rules.get("studentIds"))
    if kind != "FILTERED":
        return False
    dimensions = (
        ("studentIds", student.id),
        ("collegeIds", student.college_id),
        ("majorIds", student.major_id),
        ("classIds", student.class_id),
    )
    constrained = False
    for key, actual in dimensions:
        allowed = _ids(rules.get(key))
        if allowed:
            constrained = True
            if actual is None or int(actual) not in allowed:
                return False
    return constrained


def _requirement_view(db, row, *, student=None, submission=None):
    template = _template(db, row)
    result = {
        "id": str(row.id),
        "batchId": str(row.batch_id),
        "materialCode": row.material_code,
        "materialName": row.material_name,
        "description": row.description or "",
        "isRequired": bool(row.is_required),
        "audienceType": row.audience_type,
        "audienceFilter": row.audience_filter_json or {},
        "allowedExtensions": list(row.allowed_extensions_json or []),
        "minFiles": int(row.min_files or 0),
        "maxFiles": int(row.max_files or 0),
        "dueAt": _iso(row.due_at) or "",
        "reviewerPermission": row.reviewer_permission,
        "archiveCategory": row.archive_category,
        "sortOrder": int(row.sort_order or 0),
        "status": row.status,
        "version": int(row.version or 0),
        "template": {
            "versionId": str(template.id),
            "versionNo": int(template.version_no),
            "fileId": str(template.file_id),
            "fileName": template.file_name_snapshot or "",
            "sha256": template.sha256_snapshot or "",
        } if template else None,
    }
    if student is not None:
        result["appliesToStudent"] = _applies(row, student)
    if submission is not None:
        result["submission"] = _submission_view(db, submission)
    return result


def create_requirement(body: dict, user=None):
    payload = body or {}
    code = str(payload.get("materialCode") or "").strip().upper()
    name = str(payload.get("materialName") or "").strip()
    if not _CODE.fullmatch(code):
        raise AppException("VALIDATION_ERROR", "材料编码需为2-80位大写字母、数字、下划线或短横线")
    if len(name) < 2 or len(name) > 200:
        raise AppException("VALIDATION_ERROR", "材料名称需为2-200个字符")
    try:
        batch_id = int(payload.get("batchId"))
    except (TypeError, ValueError):
        raise AppException("VALIDATION_ERROR", "请选择实习批次") from None
    min_files = int(payload.get("minFiles", 1) or 0)
    max_files = int(payload.get("maxFiles", 1) or 0)
    if min_files < 0 or max_files < 1 or min_files > max_files or max_files > 20:
        raise AppException("VALIDATION_ERROR", "材料数量配置不合法（最多20份）")
    audience_type = str(payload.get("audienceType") or "ALL").upper()
    if audience_type not in {"ALL", "SELECTED_STUDENTS", "FILTERED"}:
        raise AppException("VALIDATION_ERROR", "必交人群类型不合法")
    due_at = None
    if payload.get("dueAt"):
        try:
            due_at = datetime.fromisoformat(str(payload["dueAt"]).replace("Z", "+00:00")).replace(tzinfo=None)
        except ValueError:
            raise AppException("VALIDATION_ERROR", "截止时间格式不合法") from None

    with session() as db:
        batch = db.scalar(select(InternshipBatch).where(
            InternshipBatch.id == batch_id,
            InternshipBatch.tenant_id == _tid(),
            InternshipBatch.is_deleted.is_(False),
        ))
        if not batch:
            raise not_found("实习批次不存在")
        exists = db.scalar(select(InternshipMaterialRequirement.id).where(
            InternshipMaterialRequirement.tenant_id == _tid(),
            InternshipMaterialRequirement.batch_id == batch_id,
            InternshipMaterialRequirement.material_code == code,
            InternshipMaterialRequirement.is_deleted.is_(False),
        ))
        if exists:
            raise AppException("DATA_CONFLICT", "当前批次已存在相同材料编码")
        row = InternshipMaterialRequirement(
            tenant_id=_tid(),
            batch_id=batch_id,
            material_code=code,
            material_name=name,
            description=str(payload.get("description") or "").strip()[:1000] or None,
            is_required=bool(payload.get("isRequired", True)),
            audience_type=audience_type,
            audience_filter_json=dict(payload.get("audienceFilter") or {}),
            allowed_extensions_json=_extensions(payload.get("allowedExtensions")),
            min_files=min_files,
            max_files=max_files,
            due_at=due_at,
            reviewer_permission=str(payload.get("reviewerPermission") or "internship.material.review")[:120],
            archive_category=str(payload.get("archiveCategory") or "CUSTOM_MATERIAL")[:80],
            sort_order=int(payload.get("sortOrder") or 0),
            status="DRAFT",
        )
        db.add(row)
        db.flush()
        _trail(db, row.id, "REQUIREMENT_CREATE", {
            "batchId": str(batch_id), "materialCode": code,
            "audienceType": audience_type, "minFiles": min_files, "maxFiles": max_files,
        }, user)
        db.commit()
        return _requirement_view(db, row)


def list_requirements(*, batch_id, status=None, user=None):
    with session() as db:
        query = select(InternshipMaterialRequirement).where(
            InternshipMaterialRequirement.tenant_id == _tid(),
            InternshipMaterialRequirement.batch_id == int(batch_id),
            InternshipMaterialRequirement.is_deleted.is_(False),
        )
        value = str(status or "").strip().upper()
        if value and value != "ALL":
            query = query.where(InternshipMaterialRequirement.status == value)
        rows = db.scalars(query.order_by(
            InternshipMaterialRequirement.sort_order,
            InternshipMaterialRequirement.id,
        )).all()
        return [_requirement_view(db, row) for row in rows]


def attach_template(requirement_id, file_id, user=None):
    file_obj = file_access_service.require_file_access(str(file_id), user=user, action="bind")
    with session() as db:
        row = _requirement(db, requirement_id, lock=True)
        current = db.scalars(select(InternshipMaterialTemplateVersion).where(
            InternshipMaterialTemplateVersion.tenant_id == _tid(),
            InternshipMaterialTemplateVersion.requirement_id == row.id,
            InternshipMaterialTemplateVersion.is_current.is_(True),
            InternshipMaterialTemplateVersion.is_deleted.is_(False),
        ).with_for_update()).all()
        for old in current:
            old.is_current = False
            old.status = "SUPERSEDED"
            old.version = int(old.version or 0) + 1
        version_no = int(db.scalar(select(func.max(InternshipMaterialTemplateVersion.version_no)).where(
            InternshipMaterialTemplateVersion.tenant_id == _tid(),
            InternshipMaterialTemplateVersion.requirement_id == row.id,
        )) or 0) + 1
        item = InternshipMaterialTemplateVersion(
            tenant_id=_tid(),
            requirement_id=row.id,
            version_no=version_no,
            file_id=int(file_obj.id),
            file_name_snapshot=file_obj.file_name,
            sha256_snapshot=file_obj.sha256,
            is_current=True,
            status="ACTIVE",
            uploaded_by_name=_op_name(user),
        )
        db.add(item)
        db.flush()
        file_business_binding_service.bind_file_to_business(
            db,
            file_id=file_obj.id,
            biz_type="INTERNSHIP_MATERIAL_TEMPLATE",
            biz_id=row.id,
            actor=user or {},
            subject_type="ROLE",
            subject_id="SCHOOL_ADMIN",
            relation_type="TEMPLATE",
            module_code="INTERNSHIP",
            batch_id=str(row.batch_id),
            scope={"batchId": str(row.batch_id), "requirementId": str(row.id)},
        )
        row.current_template_version_id = item.id
        row.version = int(row.version or 0) + 1
        _trail(db, row.id, "TEMPLATE_VERSION_ADD", {
            "templateVersionId": str(item.id),
            "templateVersionNo": version_no,
            "fileId": str(file_obj.id),
            "sha256": file_obj.sha256 or "",
        }, user)
        db.commit()
        return _requirement_view(db, row)


def publish_requirement(requirement_id, user=None):
    with session() as db:
        row = _requirement(db, requirement_id, lock=True)
        if row.status == "CLOSED":
            raise AppException("DATA_CONFLICT", "已关闭收件要求不可重新发布")
        if not _template(db, row):
            raise AppException("DATA_CONFLICT", "发布前必须上传至少一个材料模板版本")
        row.status = "PUBLISHED"
        row.version = int(row.version or 0) + 1
        _trail(db, row.id, "REQUIREMENT_PUBLISH", {
            "batchId": str(row.batch_id), "materialCode": row.material_code,
        }, user)
        db.commit()
        return _requirement_view(db, row)


def _submission(db, requirement_id, record_id, *, lock=False):
    query = select(InternshipMaterialSubmission).where(
        InternshipMaterialSubmission.tenant_id == _tid(),
        InternshipMaterialSubmission.requirement_id == int(requirement_id),
        InternshipMaterialSubmission.internship_id == int(record_id),
        InternshipMaterialSubmission.is_deleted.is_(False),
    )
    return db.scalar(query.with_for_update() if lock else query)


def _submission_files(db, submission_id):
    return db.scalars(select(InternshipMaterialSubmissionFile).where(
        InternshipMaterialSubmissionFile.tenant_id == _tid(),
        InternshipMaterialSubmissionFile.submission_id == int(submission_id),
        InternshipMaterialSubmissionFile.is_deleted.is_(False),
    ).order_by(InternshipMaterialSubmissionFile.slot_no)).all()


def _submission_view(db, row):
    files = []
    for item in _submission_files(db, row.id):
        version = db.get(FileVersion, item.current_version_id)
        file_obj = db.get(FileObject, item.file_id)
        files.append({
            "slotNo": int(item.slot_no),
            "assetId": str(item.asset_id),
            "fileVersionId": str(item.current_version_id),
            "versionNo": int(version.version_no) if version else 0,
            "versionStatus": version.status if version else "",
            "fileId": str(item.file_id),
            "fileName": file_obj.file_name if file_obj else "",
            "sha256": file_obj.sha256 if file_obj else "",
            "scanStatus": file_obj.scan_status if file_obj else "",
        })
    return {
        "id": str(row.id),
        "requirementId": str(row.requirement_id),
        "internshipId": str(row.internship_id),
        "studentId": str(row.student_id),
        "batchId": str(row.batch_id),
        "status": row.status,
        "statusLabel": {
            "DRAFT": "草稿", "SUBMITTED": "待审核", "APPROVED": "已通过",
            "RETURNED": "已退回", "WITHDRAWN": "已撤回",
        }.get(row.status, row.status),
        "submitComment": row.submit_comment or "",
        "submittedAt": _iso(row.submitted_at) or "",
        "reviewedBy": row.reviewed_by_name or "",
        "reviewComment": row.review_comment or "",
        "reviewedAt": _iso(row.reviewed_at) or "",
        "version": int(row.version or 0),
        "files": files,
    }


def list_my_requirements(user: dict, *, batch_id, internship_id):
    payload = {"batchId": batch_id, "internshipId": internship_id}
    with session() as db:
        record, student, _batch = require_explicit_context(db, user, payload, for_write=False)
        rows = db.scalars(select(InternshipMaterialRequirement).where(
            InternshipMaterialRequirement.tenant_id == _tid(),
            InternshipMaterialRequirement.batch_id == record.batch_id,
            InternshipMaterialRequirement.status == "PUBLISHED",
            InternshipMaterialRequirement.is_deleted.is_(False),
        ).order_by(
            InternshipMaterialRequirement.sort_order,
            InternshipMaterialRequirement.id,
        )).all()
        out = []
        for row in rows:
            if not _applies(row, student):
                continue
            submission = _submission(db, row.id, record.id)
            item = _requirement_view(db, row, student=student, submission=submission)
            item["isLate"] = bool(row.due_at and datetime.utcnow() > row.due_at and (
                not submission or submission.status not in _SUBMITTED))
            out.append(item)
        return out


def _assert_extension(file_obj: FileObject, requirement):
    allowed = set(requirement.allowed_extensions_json or [])
    ext = str(file_obj.ext or "").lower().lstrip(".")
    if allowed and ext not in allowed:
        raise AppException(
            "VALIDATION_ERROR",
            f"文件格式 .{ext or '未知'} 不在允许范围：{', '.join(sorted(allowed))}",
        )


def _asset(db, requirement, record, slot_no):
    code = f"INTERNSHIP:CUSTOM:{requirement.id}:{record.id}:{slot_no}"
    row = db.scalar(select(FileAsset).where(
        FileAsset.tenant_id == _tid(),
        FileAsset.asset_code == code,
        FileAsset.is_deleted.is_(False),
    ).with_for_update())
    if not row:
        row = FileAsset(
            tenant_id=_tid(),
            asset_code=code,
            title=f"{requirement.material_name} · 第{slot_no}份",
            category_code=requirement.material_code,
            owner_type="INTERNSHIP_RECORD",
            owner_id=str(record.id),
            lifecycle_status="ACTIVE",
            sensitivity_level="PERSONAL",
        )
        db.add(row)
        db.flush()
    return row


def submit_material(user: dict, requirement_id, body: dict):
    payload = body or {}
    file_ids = [str(item).strip() for item in (payload.get("fileIds") or []) if str(item).strip()]
    with session() as db:
        record, student, _batch = require_explicit_context(db, user, payload, for_write=True)
        requirement = _requirement(db, requirement_id, lock=True)
        if requirement.batch_id != record.batch_id or requirement.status != "PUBLISHED":
            raise AppException("DATA_CONFLICT", "当前批次没有可提交的该材料要求")
        if not _applies(requirement, student):
            raise AppException("NO_PERMISSION", "该材料要求不适用于当前学生", http_status=403)
        if len(file_ids) < int(requirement.min_files or 0) or len(file_ids) > int(requirement.max_files or 0):
            raise AppException(
                "VALIDATION_ERROR",
                f"本材料要求上传 {requirement.min_files}-{requirement.max_files} 份文件",
            )
        if len(set(file_ids)) != len(file_ids):
            raise AppException("VALIDATION_ERROR", "同一文件不能在一次提交中重复使用")

        validated = []
        for file_id in file_ids:
            file_obj = file_access_service.require_file_access(file_id, user=user, action="bind")
            _assert_extension(file_obj, requirement)
            validated.append(file_obj)

        submission = _submission(db, requirement.id, record.id, lock=True)
        if submission and submission.status in {"SUBMITTED", "APPROVED"}:
            raise AppException("DATA_CONFLICT", "当前材料正在审核或已通过，不可覆盖")
        if not submission:
            submission = InternshipMaterialSubmission(
                tenant_id=_tid(),
                requirement_id=requirement.id,
                internship_id=record.id,
                student_id=student.id,
                batch_id=record.batch_id,
                status="DRAFT",
            )
            db.add(submission)
            db.flush()

        existing = {int(item.slot_no): item for item in _submission_files(db, submission.id)}
        touched = set()
        for slot_no, file_obj in enumerate(validated, start=1):
            touched.add(slot_no)
            asset = _asset(db, requirement, record, slot_no)
            old = existing.get(slot_no)
            old_version = db.get(FileVersion, old.current_version_id) if old else None
            if old_version:
                old_version.is_current = False
                old_version.status = "REJECTED" if submission.status == "RETURNED" else "INVALIDATED"
                old_version.invalidated_at = datetime.utcnow()
                old_version.invalidated_by = _op_name(user)
                old_version.invalid_reason = "RESUBMITTED"
                for binding in db.scalars(select(FileBinding).where(
                    FileBinding.tenant_id == _tid(),
                    FileBinding.asset_id == asset.id,
                    FileBinding.is_current.is_(True),
                    FileBinding.is_deleted.is_(False),
                ).with_for_update()).all():
                    binding.is_current = False
                    binding.status = "SUPERSEDED"
                    binding.invalidated_at = datetime.utcnow()

            next_no = int(db.scalar(select(func.max(FileVersion.version_no)).where(
                FileVersion.tenant_id == _tid(),
                FileVersion.asset_id == asset.id,
            )) or 0) + 1
            version = FileVersion(
                tenant_id=_tid(),
                asset_id=asset.id,
                file_object_id=file_obj.id,
                version_no=next_no,
                source_channel="STUDENT_SUBMISSION",
                uploader_user_id=str((user or {}).get("userId") or ""),
                uploader_name_snapshot=student.real_name,
                submit_comment=str(payload.get("comment") or "").strip()[:500] or None,
                status="SUBMITTED",
                is_current=True,
                submitted_at=datetime.utcnow(),
            )
            db.add(version)
            db.flush()
            asset.current_version_id = version.id
            asset.version_count = next_no
            asset.version = int(asset.version or 0) + 1

            binding = file_business_binding_service.bind_file_to_business(
                db,
                file_id=file_obj.id,
                biz_type="INTERNSHIP_CUSTOM_MATERIAL",
                biz_id=f"{submission.id}:{slot_no}",
                actor=user or {},
                subject_type="STUDENT",
                subject_id=student.id,
                relation_type="MATERIAL",
                module_code="INTERNSHIP",
                student_id=student.id,
                batch_id=str(record.batch_id),
                college_id=student.college_id,
                class_id=student.class_id,
                scope={
                    "internshipId": str(record.id),
                    "studentId": str(student.id),
                    "batchId": str(record.batch_id),
                    "requirementId": str(requirement.id),
                    "materialCode": requirement.material_code,
                    "slotNo": slot_no,
                },
            )
            binding.asset_id = asset.id
            binding.version_id = version.id
            binding.version_no = version.version_no

            if old:
                old.asset_id = asset.id
                old.current_version_id = version.id
                old.file_id = file_obj.id
                old.version = int(old.version or 0) + 1
            else:
                db.add(InternshipMaterialSubmissionFile(
                    tenant_id=_tid(),
                    submission_id=submission.id,
                    slot_no=slot_no,
                    asset_id=asset.id,
                    current_version_id=version.id,
                    file_id=file_obj.id,
                ))

        for slot_no, old in existing.items():
            if slot_no not in touched:
                old.is_deleted = True
                old.version = int(old.version or 0) + 1

        submission.status = "SUBMITTED"
        submission.submit_comment = str(payload.get("comment") or "").strip()[:500] or None
        submission.submitted_at = datetime.utcnow()
        submission.reviewed_by_name = None
        submission.review_comment = None
        submission.reviewed_at = None
        submission.version = int(submission.version or 0) + 1
        db.flush()
        _trail(db, requirement.id, "MATERIAL_SUBMIT", {
            "submissionId": str(submission.id),
            "internshipId": str(record.id),
            "studentId": str(student.id),
            "fileIds": file_ids,
            "version": int(submission.version or 0),
        }, user)
        db.commit()
        return _submission_view(db, submission)


def _scoped_students(db, requirement, user=None):
    from app.modules.internship.services.internship_scope import apply_internship_record_scope
    scoped = apply_internship_record_scope(
        select(InternshipRecord.id).where(
            InternshipRecord.tenant_id == _tid(),
            InternshipRecord.batch_id == requirement.batch_id,
            InternshipRecord.is_deleted.is_(False),
        ),
        user,
    ).subquery()
    rows = db.execute(select(InternshipRecord, StudentProfile).join(
        StudentProfile, StudentProfile.id == InternshipRecord.student_id,
    ).where(
        InternshipRecord.id.in_(select(scoped.c.id)),
        StudentProfile.tenant_id == _tid(),
        StudentProfile.is_deleted.is_(False),
    )).all()
    return [(record, student) for record, student in rows if _applies(requirement, student)]


def coverage(requirement_id, user=None):
    with session() as db:
        requirement = _requirement(db, requirement_id)
        targets = _scoped_students(db, requirement, user)
        record_ids = [record.id for record, _student in targets]
        submissions = db.scalars(select(InternshipMaterialSubmission).where(
            InternshipMaterialSubmission.tenant_id == _tid(),
            InternshipMaterialSubmission.requirement_id == requirement.id,
            InternshipMaterialSubmission.internship_id.in_(record_ids or [-1]),
            InternshipMaterialSubmission.is_deleted.is_(False),
        )).all()
        by_record = {item.internship_id: item for item in submissions}
        counts = {"SUBMITTED": 0, "APPROVED": 0, "RETURNED": 0, "MISSING": 0}
        for record, _student in targets:
            status = by_record.get(record.id).status if by_record.get(record.id) else "MISSING"
            counts[status if status in counts else "MISSING"] += 1
        effective = counts["SUBMITTED"] + counts["APPROVED"]
        return {
            "requirementId": str(requirement.id),
            "batchId": str(requirement.batch_id),
            "materialCode": requirement.material_code,
            "materialName": requirement.material_name,
            "requiredStudents": len(targets),
            "effectiveSubmittedStudents": effective,
            "missingStudents": len(targets) - effective,
            "pendingReviewStudents": counts["SUBMITTED"],
            "approvedStudents": counts["APPROVED"],
            "returnedStudents": counts["RETURNED"],
            "completionRate": round(effective * 100.0 / len(targets), 1) if targets else 0.0,
        }


def list_students(requirement_id, *, state="ALL", page=1, page_size=20, keyword="", user=None):
    with session() as db:
        requirement = _requirement(db, requirement_id)
        targets = _scoped_students(db, requirement, user)
        submissions = {
            row.internship_id: row
            for row in db.scalars(select(InternshipMaterialSubmission).where(
                InternshipMaterialSubmission.tenant_id == _tid(),
                InternshipMaterialSubmission.requirement_id == requirement.id,
                InternshipMaterialSubmission.is_deleted.is_(False),
            )).all()
        }
        state_value = str(state or "ALL").upper()
        term = str(keyword or "").strip().lower()
        rows = []
        for record, student in targets:
            submission = submissions.get(record.id)
            status = submission.status if submission else "MISSING"
            effective_state = "SUBMITTED" if status in _SUBMITTED else status
            if state_value != "ALL":
                if state_value == "MISSING" and effective_state not in {"MISSING", "RETURNED"}:
                    continue
                elif state_value != "MISSING" and state_value != effective_state:
                    continue
            if term and term not in f"{student.real_name} {student.student_no} {record.enterprise_name or ''}".lower():
                continue
            rows.append({
                "internshipId": str(record.id),
                "studentId": str(student.id),
                "studentName": student.real_name,
                "studentNo": student.student_no,
                "enterpriseName": record.enterprise_name or "",
                "status": status,
                "submission": _submission_view(db, submission) if submission else None,
            })
        total = len(rows)
        start = (max(1, int(page)) - 1) * int(page_size)
        return rows[start:start + int(page_size)], total


def review_submission(submission_id, body: dict, user=None):
    payload = body or {}
    action = str(payload.get("action") or "").strip().upper()
    if action not in {"APPROVE", "RETURN"}:
        raise AppException("VALIDATION_ERROR", "action 必须是 APPROVE 或 RETURN")
    comment = str(payload.get("comment") or "").strip()
    if action == "RETURN" and len(comment) < 5:
        raise AppException("VALIDATION_ERROR", "退回原因不少于5个字")
    with session() as db:
        row = db.scalar(select(InternshipMaterialSubmission).where(
            InternshipMaterialSubmission.id == _as_id(submission_id),
            InternshipMaterialSubmission.tenant_id == _tid(),
            InternshipMaterialSubmission.is_deleted.is_(False),
        ).with_for_update())
        if not row:
            raise not_found("材料提交记录不存在")
        from app.modules.internship.services.internship_scope import assert_internship_record_scope
        assert_internship_record_scope(db, row.internship_id, user, "审核学生材料", lock=True)
        expected = payload.get("expectedVersion")
        if expected is None or int(expected) != int(row.version or 0):
            raise AppException("DATA_CONFLICT", "材料提交已变化，请刷新后重试")
        if row.status != "SUBMITTED":
            raise AppException("DATA_CONFLICT", "仅待审核材料可处理")
        files = _submission_files(db, row.id)
        if not files:
            raise AppException("DATA_CONFLICT", "材料提交没有有效文件")
        for item in files:
            version = db.get(FileVersion, item.current_version_id)
            file_obj = db.get(FileObject, item.file_id)
            if not version or not file_obj:
                raise AppException("DATA_CONFLICT", "材料文件版本不存在")
            if not file_service.get_file_meta(str(file_obj.id), user, require_ready=True):
                raise AppException("FILE_NOT_READY", "材料文件尚未安全就绪", http_status=409)
            version.status = "APPROVED" if action == "APPROVE" else "REJECTED"
            version.version = int(version.version or 0) + 1

        row.status = "APPROVED" if action == "APPROVE" else "RETURNED"
        row.reviewed_by_name = _op_name(user)
        row.review_comment = comment or None
        row.reviewed_at = datetime.utcnow()
        row.version = int(row.version or 0) + 1
        _trail(db, row.requirement_id, f"MATERIAL_{action}", {
            "submissionId": str(row.id),
            "internshipId": str(row.internship_id),
            "reason": comment,
        }, user)
        db.commit()
        return _submission_view(db, row)


def template_download(requirement_id, user: dict, *, batch_id=None, internship_id=None):
    with session() as db:
        requirement = _requirement(db, requirement_id)
        if str((user or {}).get("userType") or "").upper() == "STUDENT":
            record, student, _batch = require_explicit_context(
                db, user, {"batchId": batch_id, "internshipId": internship_id}, for_write=False)
            if record.batch_id != requirement.batch_id or not _applies(requirement, student):
                raise AppException("NO_PERMISSION", "该模板不适用于当前学生", http_status=403)
            if requirement.status != "PUBLISHED":
                raise not_found("材料模板不存在")
        template = _template(db, requirement)
        if not template:
            raise not_found("材料模板尚未上传")
        resolved = file_service.resolve_download(str(template.file_id), user=user)
        if not resolved:
            raise not_found("材料模板文件不存在或尚未安全就绪")
        return resolved[0], template.file_name_snapshot or resolved[1]


def approved_custom_sources(db, record: InternshipRecord) -> list[dict]:
    """Return final custom-material file facts for the existing archive adapter."""
    rows = db.scalars(select(InternshipMaterialSubmission).where(
        InternshipMaterialSubmission.tenant_id == _tid(),
        InternshipMaterialSubmission.internship_id == record.id,
        InternshipMaterialSubmission.status == "APPROVED",
        InternshipMaterialSubmission.is_deleted.is_(False),
    )).all()
    out = []
    for submission in rows:
        requirement = db.get(InternshipMaterialRequirement, submission.requirement_id)
        if not requirement or requirement.is_deleted:
            continue
        for item in _submission_files(db, submission.id):
            version = db.get(FileVersion, item.current_version_id)
            if not version or version.status != "APPROVED":
                continue
            out.append({
                "category": "CUSTOM_MATERIAL",
                "materialCode": f"CUSTOM:{requirement.material_code}:{item.slot_no}",
                "fileId": str(item.file_id),
                "title": f"{requirement.material_name} · 第{item.slot_no}份",
                "bizType": "INTERNSHIP_CUSTOM_MATERIAL",
                "bizId": f"{submission.id}:{item.slot_no}",
                "reviewStatus": "APPROVED",
                "sourceChannel": "STUDENT_SUBMISSION",
                "sensitivity": "PERSONAL",
                "label": requirement.material_name,
                "businessVersion": int(submission.version or 0),
            })
    return out
