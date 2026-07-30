"""阶段 5：学工材料与真实档案公共版本中心。

权威关系：
AffairsMaterialRequirement -> FileAsset -> FileVersion -> FileObject
                                      -> FileBinding
AffairsMaterialSubmission / AffairsAttachment 仅保留旧接口兼容引用。

心理与困难认定材料默认 HIGHLY_SENSITIVE。任何列表、计数、详情、版本时间线与
Manifest 查询都先做角色和学生范围过滤，禁止通过数量、文件名或 403 差异枚举。
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from typing import Any, Iterable

from sqlalchemy import func, or_, select

from app.core.exceptions import AppException, check_version, no_permission, not_found
from app.core.permissions import has_permission
from app.models.file import (
    ArchiveManifest,
    ArchiveManifestItem,
    FileAsset,
    FileBinding,
    FileObject,
    FileVersion,
)
from app.services.db_service import _iso, _tid, session
from app.services.file_content_security import is_downloadable_status
from app.services.file_scan_constants import READY_SCAN_STATES, SCAN_NOT_REQUIRED

MODULE_CODE = "student-affairs"
ARCHIVE_TYPE = "AFFAIRS_STUDENT_RECORD"
TARGET_TYPE = "ARCHIVE_PACKAGE"
READY_VERSION_STATUS = {"READY", "SUBMITTED", "APPROVED", "ARCHIVED"}
ACTIVE_MANIFEST_STATUS = {"PREPARED", "FROZEN", "PACKAGED"}

MATERIAL_STATUS_LABELS = {
    "MISSING": "待补交",
    "PENDING_REVIEW": "待审核",
    "ACCEPTED": "已验收",
    "RETURNED": "已退回补交",
    "WAIVED": "已免交",
}
SUBMISSION_STATUS_LABELS = {
    "SUBMITTED": "已提交待审核",
    "ACCEPTED": "已验收",
    "RETURNED": "已退回",
    "SUPERSEDED": "历史版本",
}

BIZ_PERMISSIONS: dict[str, tuple[str, ...]] = {
    "LEAVE": ("studentAffairs.leave.approve",),
    "AID": ("studentAffairs.aid.approve", "studentAffairs.aid.counselorReview", "studentAffairs.aid.view"),
    "FUNDING": ("studentAffairs.funding.approve", "studentAffairs.funding.view"),
    "DISCIPLINE": ("studentAffairs.discipline.approve", "studentAffairs.discipline.view"),
    "DISCIPLINE_APPEAL": ("studentAffairs.discipline.appeal.review", "studentAffairs.discipline.view"),
    "DORM_TRANSFER": ("studentAffairs.dorm.transfer.approve", "studentAffairs.dorm.view"),
    "CREDIT_APPEAL": ("studentAffairs.activity.confirm", "studentAffairs.activity.view"),
    "SECOND_CLASS_APPEAL": ("studentAffairs.activity.confirm", "studentAffairs.activity.view"),
    "MENTAL": ("studentAffairs.risk.psyDetail.view",),
}

HIGHLY_SENSITIVE_BIZ = {"AID", "MENTAL"}
HIGHLY_SENSITIVE_HINTS = {
    "FAMILY", "ECONOMY", "INCOME", "DEBT", "LOW_INCOME", "DIFFICULTY",
    "PSY", "MENTAL", "COUNSEL", "DIAGNOSIS", "MEDICAL", "DISABILITY",
    "家庭", "经济", "收入", "负债", "低保", "困难", "心理", "咨询", "诊断", "残疾",
}


def _biz(value: Any) -> str:
    return str(value or "").strip().upper().replace("-", "_")


def _actor_id(user: dict | None) -> int:
    from app.services.message_identity import resolve_message_user_id

    value = resolve_message_user_id(user or {})
    return int(value or 0)


def _actor_name(user: dict | None) -> str:
    return str((user or {}).get("realName") or (user or {}).get("name") or "系统")[:100]


def classify_sensitivity(biz_type: str, item_code: str = "", item_name: str = "") -> tuple[str, str]:
    bt = _biz(biz_type)
    haystack = f"{item_code} {item_name}".upper()
    if bt in HIGHLY_SENSITIVE_BIZ or any(token.upper() in haystack for token in HIGHLY_SENSITIVE_HINTS):
        if bt == "MENTAL" or any(token in haystack for token in ("PSY", "MENTAL", "心理", "咨询", "诊断")):
            return "HIGHLY_SENSITIVE", "PSY_STUDENT"
        return "HIGHLY_SENSITIVE", "AID_RESTRICTED"
    if bt in {"DISCIPLINE", "DISCIPLINE_APPEAL", "FUNDING", "LEAVE"}:
        return "SENSITIVE", "BUSINESS_SCOPE"
    return "PERSONAL", "STUDENT_SELF"


def _require_supported_biz(value: str) -> str:
    bt = _biz(value)
    if bt not in BIZ_PERMISSIONS:
        raise AppException("VALIDATION_ERROR", f"暂不支持该材料业务类型：{bt or '-'}")
    return bt


def _has_biz_permission(user: dict, biz_type: str) -> bool:
    return any(has_permission(user or {}, code) for code in BIZ_PERMISSIONS.get(_biz(biz_type), ()))


def _require_biz_permission(user: dict, biz_type: str) -> None:
    if not _has_biz_permission(user, biz_type):
        raise no_permission("当前身份无权维护该业务的补交材料")


def _resolve_biz_student(db, biz_type: str, biz_id: int) -> int:
    bt = _require_supported_biz(biz_type)
    if bt == "MENTAL":
        from app.models import PsyReferral

        row = db.get(PsyReferral, int(biz_id))
        if not row or row.is_deleted or row.tenant_id != _tid():
            raise not_found("业务申请不存在")
        return int(row.student_id)

    from app.services import affairs_operations_service as legacy

    return int(legacy._resolve_biz_student(db, bt, int(biz_id)))


def _require_student_scope(db, student_id: int, user: dict, *, hide: bool = False) -> None:
    try:
        from app.core.affairs_security import build_affairs_context

        build_affairs_context(user or {}, db).require_student(db, int(student_id))
    except Exception as exc:
        if hide:
            raise not_found("材料记录不存在") from exc
        raise


def _psy_scope_allows(db, student_id: int, user: dict) -> bool:
    try:
        from app.services.affairs_mental_service import psy_scope_ids

        scope = psy_scope_ids(db, user or {})
        return scope is None or int(student_id) in scope
    except Exception:
        return False


def _staff_can_enumerate(db, requirement, user: dict) -> bool:
    if not _has_biz_permission(user, requirement.biz_type):
        return False
    if requirement.material_scope == "PSY_STUDENT":
        return _psy_scope_allows(db, requirement.student_id, user)
    try:
        _require_student_scope(db, requirement.student_id, user, hide=True)
        return True
    except Exception:
        return False


def _student_profile(db, student_id: int):
    from app.models import StudentProfile

    row = db.get(StudentProfile, int(student_id))
    if not row or row.is_deleted or row.tenant_id != _tid():
        raise not_found("学生档案不存在")
    return row


def _file_ready(file_obj: FileObject) -> bool:
    scan = str(file_obj.scan_status or SCAN_NOT_REQUIRED).upper()
    return bool(is_downloadable_status(file_obj.status) and scan in READY_SCAN_STATES)


def _require_file_ready(file_obj: FileObject) -> None:
    if not _file_ready(file_obj):
        raise AppException(
            "DATA_CONFLICT",
            "材料仍在安全扫描、扫描失败或已被隔离，不能提交或审核",
            details={"scanStatus": str(file_obj.scan_status or ""), "fileStatus": str(file_obj.status or "")},
        )
    if not file_obj.sha256:
        raise AppException("DATA_CONFLICT", "材料缺少 SHA-256，不能进入公共版本链")


def _asset_code(requirement_id: int) -> str:
    return f"AFFAIRS_MATERIAL:{_tid()}:{int(requirement_id)}"


def _ensure_asset(db, requirement) -> FileAsset:
    asset = db.get(FileAsset, int(requirement.asset_id)) if requirement.asset_id else None
    if asset and not asset.is_deleted and asset.tenant_id == _tid():
        return asset
    code = _asset_code(requirement.id)
    asset = db.scalars(select(FileAsset).where(
        FileAsset.tenant_id == _tid(),
        FileAsset.asset_code == code,
        FileAsset.is_deleted.is_(False),
    ).with_for_update()).first()
    if asset is None:
        asset = FileAsset(
            tenant_id=_tid(),
            asset_code=code,
            title=requirement.item_name,
            category_code=f"AFFAIRS_{_biz(requirement.biz_type)}",
            owner_type="MATERIAL_REQUIREMENT",
            owner_id=str(requirement.id),
            lifecycle_status="ACTIVE",
            version_count=0,
            sensitivity_level=requirement.sensitivity_level or "SENSITIVE",
        )
        db.add(asset)
        db.flush()
    requirement.asset_id = int(asset.id)
    asset.title = requirement.item_name
    asset.sensitivity_level = requirement.sensitivity_level or asset.sensitivity_level
    return asset


def _invalidate_current(db, asset: FileAsset, *, reason: str, actor: str) -> None:
    now = datetime.utcnow()
    versions = db.scalars(select(FileVersion).where(
        FileVersion.tenant_id == _tid(),
        FileVersion.asset_id == int(asset.id),
        FileVersion.is_current.is_(True),
        FileVersion.is_deleted.is_(False),
    ).with_for_update()).all()
    version_ids = []
    for version in versions:
        version.is_current = False
        if version.status not in {"APPROVED", "ARCHIVED"}:
            version.status = "INVALIDATED"
        version.invalidated_at = now
        version.invalidated_by = actor
        version.invalid_reason = reason[:500]
        version_ids.append(int(version.id))
    if version_ids:
        bindings = db.scalars(select(FileBinding).where(
            FileBinding.tenant_id == _tid(),
            FileBinding.version_id.in_(version_ids),
            FileBinding.is_current.is_(True),
            FileBinding.is_deleted.is_(False),
        ).with_for_update()).all()
        for binding in bindings:
            binding.is_current = False
            binding.status = "SUPERSEDED"
            binding.invalidated_at = now


def _adopt_file(
    db,
    requirement,
    file_obj: FileObject,
    *,
    source_channel: str,
    submit_comment: str,
    user: dict,
    requested_version_no: int | None = None,
) -> tuple[FileAsset, FileVersion, FileBinding]:
    _require_file_ready(file_obj)
    asset = _ensure_asset(db, requirement)
    actor_name = _actor_name(user)
    _invalidate_current(db, asset, reason="学生提交新版本", actor=actor_name)

    latest_no = int(db.scalar(select(func.max(FileVersion.version_no)).where(
        FileVersion.tenant_id == _tid(),
        FileVersion.asset_id == int(asset.id),
        FileVersion.is_deleted.is_(False),
    )) or 0)
    version_no = max(latest_no + 1, int(requested_version_no or 0))
    student = _student_profile(db, requirement.student_id)
    actor = _actor_id(user)
    version = FileVersion(
        tenant_id=_tid(),
        asset_id=int(asset.id),
        file_object_id=int(file_obj.id),
        version_no=version_no,
        source_channel=source_channel,
        uploader_user_id=str(actor or file_obj.owner_user_id or file_obj.created_by or "") or None,
        uploader_name_snapshot=actor_name,
        submit_comment=(submit_comment or "")[:500] or None,
        status="SUBMITTED",
        is_current=True,
        submitted_at=datetime.utcnow(),
        created_by=actor or None,
    )
    db.add(version)
    db.flush()
    binding = FileBinding(
        tenant_id=_tid(),
        file_id=int(file_obj.id),
        biz_type="MATERIAL_REQUIREMENT",
        biz_id=str(requirement.id),
        relation_type="MATERIAL_SUBMISSION",
        subject_type="STUDENT",
        subject_id=str(requirement.student_id),
        batch_id=None,
        version_no=version_no,
        is_current=True,
        status="ACTIVE",
        scope_json={
            "studentId": str(requirement.student_id),
            "businessType": requirement.biz_type,
            "businessId": str(requirement.biz_id),
            "materialScope": requirement.material_scope,
            "sensitivityLevel": requirement.sensitivity_level,
        },
        asset_id=int(asset.id),
        version_id=int(version.id),
        module_code=MODULE_CODE,
        student_id=int(requirement.student_id),
        college_id=getattr(student, "college_id", None),
        class_id=getattr(student, "class_id", None),
        data_scope_snapshot_json={
            "studentId": str(requirement.student_id),
            "collegeId": str(getattr(student, "college_id", None) or ""),
            "classId": str(getattr(student, "class_id", None) or ""),
            "materialScope": requirement.material_scope,
        },
        created_by=actor or None,
    )
    db.add(binding)
    db.flush()
    asset.current_version_id = int(version.id)
    asset.version_count = max(int(asset.version_count or 0), version_no)
    file_obj.biz_type = "MATERIAL_REQUIREMENT"
    file_obj.biz_id = str(requirement.id)
    file_obj.visibility = "STUDENT_SELF"
    file_obj.security_level = requirement.sensitivity_level or "SENSITIVE"
    return asset, version, binding


def _submission_dict(row, current_id: int | None = None) -> dict:
    return {
        "submissionId": str(row.id),
        "versionNo": int(row.version_no or 0),
        "assetId": str(row.asset_id or ""),
        "fileVersionId": str(row.file_version_id or ""),
        "bindingId": str(row.binding_id or ""),
        "fileId": str(row.file_id),
        "fileName": row.file_name or "补交材料",
        "sensitivityLevel": row.sensitivity_level or "SENSITIVE",
        "status": row.status,
        "statusLabel": SUBMISSION_STATUS_LABELS.get(row.status, row.status),
        "submittedAt": _iso(row.submitted_at or row.created_at),
        "reviewedAt": _iso(row.reviewed_at),
        "reviewNote": row.review_note or "",
        "current": int(current_id or 0) == int(row.id),
        "downloadable": not bool(row.is_deleted),
        "supersedesId": str(row.supersedes_id or ""),
    }


def _submission_rows(db, requirement_ids: Iterable[int]) -> dict[int, list[Any]]:
    from app.models.affairs_operations import AffairsMaterialSubmission

    ids = {int(value) for value in requirement_ids}
    result = {value: [] for value in ids}
    if not ids:
        return result
    rows = db.scalars(select(AffairsMaterialSubmission).where(
        AffairsMaterialSubmission.tenant_id == _tid(),
        AffairsMaterialSubmission.requirement_id.in_(ids),
        AffairsMaterialSubmission.is_deleted.is_(False),
    ).order_by(
        AffairsMaterialSubmission.requirement_id,
        AffairsMaterialSubmission.version_no.desc(),
    )).all()
    for row in rows:
        result.setdefault(int(row.requirement_id), []).append(row)
    return result


def _requirement_dict(row, submissions: list[Any], *, student_view: bool, owner_name: str = "") -> dict:
    current = next((item for item in submissions if int(item.id) == int(row.current_submission_id or 0)), None)
    overdue = bool(row.due_at and row.due_at < datetime.utcnow() and row.status in {"MISSING", "RETURNED"})
    actions: list[str] = []
    if student_view and row.status in {"MISSING", "RETURNED"}:
        actions.append("SUBMIT_MATERIAL")
    if not student_view and row.status == "PENDING_REVIEW":
        actions.extend(["ACCEPT_MATERIAL", "RETURN_MATERIAL"])
    if not student_view and row.status in {"MISSING", "RETURNED", "PENDING_REVIEW"}:
        actions.append("WAIVE_MATERIAL")
    versions = [_submission_dict(item, row.current_submission_id) for item in submissions]
    return {
        "requirementId": str(row.id),
        "studentId": str(row.student_id),
        "bizType": row.biz_type,
        "bizId": str(row.biz_id),
        "itemCode": row.item_code,
        "itemName": row.item_name,
        "requirementReason": row.requirement_reason or "",
        "assetId": str(row.asset_id or ""),
        "sensitivityLevel": row.sensitivity_level or "SENSITIVE",
        "materialScope": row.material_scope or "STUDENT_SELF",
        "status": row.status,
        "statusLabel": MATERIAL_STATUS_LABELS.get(row.status, row.status),
        "returnRound": int(row.return_round or 1),
        "dueAt": _iso(row.due_at),
        "overdue": overdue,
        "reviewOwnerId": str(row.review_owner_id or ""),
        "reviewOwner": owner_name or "",
        "currentSubmissionId": str(row.current_submission_id or ""),
        "currentSubmission": _submission_dict(current, row.current_submission_id) if current else None,
        "versions": versions,
        "versionCount": len(versions),
        "version": int(row.version or 0),
        "allowedActions": actions,
        "exceptionProjection": {
            "type": "MATERIAL_MISSING",
            "responsibleUserId": str(row.review_owner_id or ""),
            "responsibleUser": owner_name or "",
            "dueAt": _iso(row.due_at),
            "overdue": overdue,
            "status": row.status,
            "canEscalate": overdue and row.status in {"MISSING", "RETURNED"},
        },
    }


def create_material_requirement(user: dict, payload: dict) -> dict:
    from app.models import User
    from app.models.affairs_operations import AffairsMaterialRequirement
    from app.services import affairs_operations_service as legacy

    bt = _require_supported_biz(payload.get("bizType"))
    _require_biz_permission(user, bt)
    biz_id = int(payload.get("bizId") or 0)
    if biz_id <= 0:
        raise AppException("VALIDATION_ERROR", "业务记录ID无效")
    item_code = str(payload.get("itemCode") or "").strip().upper()
    if not re.fullmatch(r"[A-Z0-9][A-Z0-9_-]{0,99}", item_code):
        raise AppException("VALIDATION_ERROR", "材料项编码需为1-100位大写字母、数字、下划线或短横线")
    item_name = str(payload.get("itemName") or "").strip()
    if not 2 <= len(item_name) <= 200:
        raise AppException("VALIDATION_ERROR", "材料项名称需2-200字")
    reason = str(payload.get("requirementReason") or "").strip()
    if reason and not 5 <= len(reason) <= 500:
        raise AppException("VALIDATION_ERROR", "缺项说明需5-500字")
    owner = _actor_id(user)
    if owner <= 0:
        raise AppException("ASSIGNEE_NOT_CONFIGURED", "当前教师账号未绑定可用用户ID")
    sensitivity, material_scope = classify_sensitivity(bt, item_code, item_name)

    created = False
    with session() as db:
        student_id = _resolve_biz_student(db, bt, biz_id)
        if material_scope == "PSY_STUDENT":
            if not _psy_scope_allows(db, student_id, user):
                raise not_found("业务申请不存在")
        else:
            _require_student_scope(db, student_id, user)
        row = db.scalars(select(AffairsMaterialRequirement).where(
            AffairsMaterialRequirement.tenant_id == _tid(),
            AffairsMaterialRequirement.biz_type == bt,
            AffairsMaterialRequirement.biz_id == biz_id,
            AffairsMaterialRequirement.item_code == item_code,
            AffairsMaterialRequirement.is_deleted.is_(False),
        ).with_for_update()).first()
        if row:
            if row.status in {"MISSING", "RETURNED", "PENDING_REVIEW"}:
                raise AppException("DATA_CONFLICT", "该材料缺项仍在处理中，请勿重复登记")
            row.status = "MISSING"
            row.return_round = int(row.return_round or 0) + 1
            row.requirement_reason = reason or row.requirement_reason
            row.item_name = item_name
            row.due_at = payload.get("dueAt")
            row.review_owner_id = owner
            row.accepted_at = None
            # 新一轮不把历史验收版本冒充当前件。
            row.current_submission_id = None
            row.version = int(row.version or 0) + 1
            action = "REOPEN_REQUIREMENT"
        else:
            row = AffairsMaterialRequirement(
                tenant_id=_tid(), student_id=student_id, biz_type=bt, biz_id=biz_id,
                item_code=item_code, item_name=item_name, requirement_reason=reason or None,
                status="MISSING", return_round=1, due_at=payload.get("dueAt"),
                review_owner_id=owner, sensitivity_level=sensitivity,
                material_scope=material_scope, created_by=owner, updated_by=owner,
            )
            db.add(row)
            db.flush()
            created = True
            action = "CREATE_REQUIREMENT"
        row.sensitivity_level = sensitivity
        row.material_scope = material_scope
        asset = _ensure_asset(db, row)
        asset.lifecycle_status = "ACTIVE"
        legacy._audit(db, row.id, action, f"{bt}:{biz_id}:{item_code}:{item_name}")
        legacy._emit_student_notice(
            db, row, "MATERIAL.REQUIRED", "材料待补交",
            f"{item_name}需要补交，请在学工申请中查看要求并上传材料。",
            extra=str(row.return_round),
        )
        db.commit()
        db.refresh(row)
        owner_row = db.get(User, owner)
        result = _requirement_dict(row, [], student_view=False, owner_name=(owner_row.real_name if owner_row else ""))
        result["created"] = created
    legacy._drain_messages()
    return result


def list_teacher_requirements(
    user: dict,
    *,
    status: str | None = None,
    page: int = 1,
    page_size: int = 50,
) -> tuple[list[dict], int]:
    """先权限/强敏感/数据范围过滤，再计数和分页。"""
    from app.models import StudentProfile, User
    from app.models.affairs_operations import AffairsMaterialRequirement
    from app.services.affairs_dashboard_service import _allowed_class_ids

    visible_biz = {bt for bt in BIZ_PERMISSIONS if _has_biz_permission(user, bt)}
    if not visible_biz:
        return [], 0
    page, page_size = max(1, int(page)), min(100, max(1, int(page_size)))
    with session() as db:
        allowed, _ = _allowed_class_ids(db, user)
        conds = [
            AffairsMaterialRequirement.tenant_id == _tid(),
            AffairsMaterialRequirement.biz_type.in_(visible_biz),
            AffairsMaterialRequirement.is_deleted.is_(False),
            StudentProfile.tenant_id == _tid(),
            StudentProfile.id == AffairsMaterialRequirement.student_id,
            StudentProfile.is_deleted.is_(False),
        ]
        if status:
            conds.append(AffairsMaterialRequirement.status == str(status).upper())
        if allowed is not None:
            conds.append(StudentProfile.class_id.in_(allowed or {-1}))
        if "MENTAL" in visible_biz:
            from app.services.affairs_mental_service import psy_scope_ids

            psy_scope = psy_scope_ids(db, user or {})
            if psy_scope is not None:
                conds.append(or_(
                    AffairsMaterialRequirement.biz_type != "MENTAL",
                    AffairsMaterialRequirement.student_id.in_(psy_scope or {-1}),
                ))
        total = int(db.scalar(select(func.count()).select_from(AffairsMaterialRequirement).join(
            StudentProfile, StudentProfile.id == AffairsMaterialRequirement.student_id,
        ).where(*conds)) or 0)
        rows = db.scalars(select(AffairsMaterialRequirement).join(
            StudentProfile, StudentProfile.id == AffairsMaterialRequirement.student_id,
        ).where(*conds).order_by(AffairsMaterialRequirement.id.desc())
            .offset((page - 1) * page_size).limit(page_size)).all()
        submissions = _submission_rows(db, [row.id for row in rows])
        owner_ids = {int(row.review_owner_id) for row in rows if row.review_owner_id}
        owners = {
            int(owner.id): owner.real_name
            for owner in db.scalars(select(User).where(
                User.tenant_id == _tid(), User.id.in_(owner_ids or {-1}), User.is_deleted.is_(False),
            )).all()
        }
        return [
            _requirement_dict(
                row, submissions.get(int(row.id), []), student_view=False,
                owner_name=owners.get(int(row.review_owner_id or 0), ""),
            )
            for row in rows
        ], total


def list_my_requirements(user: dict, *, biz_type: str | None = None, biz_id: int | None = None) -> list[dict]:
    from app.models import User
    from app.models.affairs_operations import AffairsMaterialRequirement
    from app.services.mobile_student_service import _require_student, resolve_student

    _require_student(user)
    with session() as db:
        student = resolve_student(db, user)
        if not student:
            raise no_permission("尚未建立你的学生档案")
        conds = [
            AffairsMaterialRequirement.tenant_id == _tid(),
            AffairsMaterialRequirement.student_id == int(student.id),
            AffairsMaterialRequirement.is_deleted.is_(False),
        ]
        if biz_type:
            conds.append(AffairsMaterialRequirement.biz_type == _biz(biz_type))
        if biz_id:
            conds.append(AffairsMaterialRequirement.biz_id == int(biz_id))
        rows = db.scalars(select(AffairsMaterialRequirement).where(*conds)
                          .order_by(AffairsMaterialRequirement.id.desc())).all()
        submissions = _submission_rows(db, [row.id for row in rows])
        owner_ids = {int(row.review_owner_id) for row in rows if row.review_owner_id}
        owners = {
            int(owner.id): owner.real_name
            for owner in db.scalars(select(User).where(
                User.tenant_id == _tid(), User.id.in_(owner_ids or {-1}), User.is_deleted.is_(False),
            )).all()
        }
        return [
            _requirement_dict(
                row, submissions.get(int(row.id), []), student_view=True,
                owner_name=owners.get(int(row.review_owner_id or 0), ""),
            )
            for row in rows
        ]


def submit_material(
    user: dict,
    requirement_id: int,
    *,
    file_id: int,
    note: str = "",
    expected_version: int | None,
) -> dict:
    from app.models import AffairsAttachment
    from app.models.affairs_operations import AffairsMaterialRequirement, AffairsMaterialSubmission
    from app.services import affairs_operations_service as legacy
    from app.services.mobile_student_service import _require_student, resolve_student

    _require_student(user)
    actor = _actor_id(user)
    if actor <= 0:
        raise AppException("UNAUTHORIZED", "学生账号未建立稳定用户绑定")
    with session() as db:
        student = resolve_student(db, user)
        if not student:
            raise no_permission("尚未建立你的学生档案")
        requirement = db.scalars(select(AffairsMaterialRequirement).where(
            AffairsMaterialRequirement.tenant_id == _tid(),
            AffairsMaterialRequirement.id == int(requirement_id),
            AffairsMaterialRequirement.student_id == int(student.id),
            AffairsMaterialRequirement.is_deleted.is_(False),
        ).with_for_update()).first()
        if not requirement:
            raise not_found("材料缺项不存在或不属于本人")
        if requirement.status not in {"MISSING", "RETURNED"}:
            raise AppException("APPROVAL_VERSION_CONFLICT", "当前材料状态不可补交，请刷新")
        check_version(requirement.version, expected_version)
        file_obj = db.scalars(select(FileObject).where(
            FileObject.tenant_id == _tid(),
            FileObject.id == int(file_id),
            FileObject.is_deleted.is_(False),
        ).with_for_update()).first()
        if not file_obj:
            raise not_found("上传文件不存在或不可用")
        owner = int(file_obj.owner_user_id or file_obj.created_by or 0)
        if owner != actor:
            raise no_permission("只能提交本人上传的文件")
        _require_file_ready(file_obj)

        previous = db.scalars(select(AffairsMaterialSubmission).where(
            AffairsMaterialSubmission.tenant_id == _tid(),
            AffairsMaterialSubmission.requirement_id == int(requirement.id),
            AffairsMaterialSubmission.is_deleted.is_(False),
        ).order_by(AffairsMaterialSubmission.version_no.desc()).with_for_update()).first()
        if previous and previous.status not in {"ACCEPTED", "SUPERSEDED"}:
            previous.status = "SUPERSEDED"
            previous.version = int(previous.version or 0) + 1

        asset, file_version, binding = _adopt_file(
            db, requirement, file_obj,
            source_channel="STUDENT_SUBMISSION",
            submit_comment=note or f"补交项：{requirement.item_name}",
            user=user,
        )
        attachment = AffairsAttachment(
            tenant_id=_tid(), biz_type="MATERIAL_SUPPLEMENT", biz_id=int(requirement.id),
            file_id=int(file_obj.id), file_name=file_obj.file_name,
            note=(note or f"补交项：{requirement.item_name}")[:500],
            asset_id=int(asset.id), file_version_id=int(file_version.id), binding_id=int(binding.id),
            sensitivity_level=requirement.sensitivity_level,
            source_channel="MATERIAL_SUBMISSION", created_by=actor,
        )
        db.add(attachment)
        db.flush()
        submission = AffairsMaterialSubmission(
            tenant_id=_tid(), requirement_id=int(requirement.id), student_id=int(student.id),
            version_no=int(file_version.version_no), affairs_attachment_id=int(attachment.id),
            file_id=int(file_obj.id), file_name=file_obj.file_name, status="SUBMITTED",
            submitted_by=str(actor), submitted_at=datetime.utcnow(),
            supersedes_id=int(previous.id) if previous else None,
            asset_id=int(asset.id), file_version_id=int(file_version.id), binding_id=int(binding.id),
            sensitivity_level=requirement.sensitivity_level,
            created_by=actor, updated_by=actor,
        )
        db.add(submission)
        db.flush()
        requirement.current_submission_id = int(submission.id)
        requirement.status = "PENDING_REVIEW"
        requirement.version = int(requirement.version or 0) + 1
        requirement.updated_by = actor
        legacy._todo_upsert(db, requirement)
        legacy._audit(
            db, requirement.id, "SUBMIT_MATERIAL",
            f"submission={submission.id};asset={asset.id};version={file_version.id};file={file_obj.id}",
        )
        db.commit()
        db.refresh(requirement)
        versions = _submission_rows(db, [requirement.id]).get(int(requirement.id), [])
        return _requirement_dict(requirement, versions, student_view=True)


def _load_current_version(db, requirement, submission):
    version = db.get(FileVersion, int(submission.file_version_id)) if submission and submission.file_version_id else None
    file_obj = db.get(FileObject, int(submission.file_id)) if submission else None
    binding = db.get(FileBinding, int(submission.binding_id)) if submission and submission.binding_id else None
    if not version or version.is_deleted or version.tenant_id != _tid():
        raise AppException("DATA_CONFLICT", "补交材料尚未完成公共版本回填，不能审核")
    if not file_obj or file_obj.is_deleted or file_obj.tenant_id != _tid():
        raise AppException("DATA_CONFLICT", "补交材料文件不存在，不能审核")
    if int(version.file_object_id) != int(file_obj.id) or int(version.asset_id) != int(requirement.asset_id or 0):
        raise AppException("DATA_CONFLICT", "补交材料版本关系不一致，不能审核")
    if binding and (int(binding.version_id or 0) != int(version.id) or int(binding.file_id) != int(file_obj.id)):
        raise AppException("DATA_CONFLICT", "补交材料授权绑定不一致，不能审核")
    _require_file_ready(file_obj)
    return version, file_obj, binding


def review_material(
    user: dict,
    requirement_id: int,
    *,
    action: str,
    reason: str = "",
    expected_version: int | None,
) -> dict:
    from app.models import User
    from app.models.affairs_operations import AffairsMaterialRequirement, AffairsMaterialSubmission
    from app.services import affairs_operations_service as legacy

    act = str(action or "").strip().upper()
    if act not in {"ACCEPT", "RETURN", "WAIVE"}:
        raise AppException("VALIDATION_ERROR", "材料审核动作仅支持 ACCEPT/RETURN/WAIVE")
    text = str(reason or "").strip()
    if act == "RETURN" and not 5 <= len(text) <= 500:
        raise AppException("VALIDATION_ERROR", "退回原因需5-500字")
    actor = _actor_id(user)
    with session() as db:
        requirement = db.scalars(select(AffairsMaterialRequirement).where(
            AffairsMaterialRequirement.tenant_id == _tid(),
            AffairsMaterialRequirement.id == int(requirement_id),
            AffairsMaterialRequirement.is_deleted.is_(False),
        ).with_for_update()).first()
        if not requirement or not _staff_can_enumerate(db, requirement, user):
            raise not_found("材料缺项不存在")
        if int(requirement.review_owner_id or 0) != actor:
            from app.core.affairs_security import build_affairs_context

            if build_affairs_context(user or {}, db).scope_type != "TENANT_ALL":
                raise no_permission("仅材料审核责任人或学校级学工管理员可处理")
        check_version(requirement.version, expected_version)
        current = db.get(AffairsMaterialSubmission, int(requirement.current_submission_id)) if requirement.current_submission_id else None
        if act in {"ACCEPT", "RETURN"}:
            if requirement.status != "PENDING_REVIEW" or not current or current.status != "SUBMITTED":
                raise AppException("APPROVAL_VERSION_CONFLICT", "当前没有可审核的最新补交版本")
            public_version, _file, binding = _load_current_version(db, requirement, current)
        else:
            public_version = None
            binding = None
        now = datetime.utcnow()
        if act == "ACCEPT":
            current.status = "ACCEPTED"
            current.reviewed_by = str(actor)
            current.reviewed_at = now
            current.review_note = text or "材料验收通过"
            current.version = int(current.version or 0) + 1
            public_version.status = "APPROVED"
            requirement.status = "ACCEPTED"
            requirement.accepted_at = now
            event, title, content = "MATERIAL.ACCEPTED", "材料已验收", f"{requirement.item_name}已验收通过。"
        elif act == "RETURN":
            current.status = "RETURNED"
            current.reviewed_by = str(actor)
            current.reviewed_at = now
            current.review_note = text
            current.version = int(current.version or 0) + 1
            public_version.status = "REJECTED"
            if binding:
                binding.status = "REJECTED"
            requirement.status = "RETURNED"
            requirement.return_round = int(requirement.return_round or 0) + 1
            event, title, content = "MATERIAL.RETURNED", "补交材料被退回", f"{requirement.item_name}需重新补交：{text}"
        else:
            if requirement.status not in {"MISSING", "RETURNED", "PENDING_REVIEW"}:
                raise AppException("APPROVAL_VERSION_CONFLICT", "当前材料状态不可免交")
            if current and current.status == "SUBMITTED":
                current.status = "SUPERSEDED"
                current.reviewed_by = str(actor)
                current.reviewed_at = now
                current.review_note = text or "学校免交"
                current.version = int(current.version or 0) + 1
                if current.file_version_id:
                    version = db.get(FileVersion, int(current.file_version_id))
                    if version:
                        version.status = "INVALIDATED"
                        version.is_current = False
                        version.invalidated_at = now
                        version.invalidated_by = _actor_name(user)
                        version.invalid_reason = "学校免交"
            requirement.status = "WAIVED"
            requirement.accepted_at = now
            event, title, content = "MATERIAL.WAIVED", "材料已免交", f"{requirement.item_name}已由学校确认免交。"
        requirement.version = int(requirement.version or 0) + 1
        requirement.updated_by = actor or None
        legacy._todo_done(db, requirement.id)
        legacy._audit(db, requirement.id, f"MATERIAL_{act}", text)
        legacy._emit_student_notice(db, requirement, event, title, content, extra=str(requirement.version))
        db.commit()
        db.refresh(requirement)
        versions = _submission_rows(db, [requirement.id]).get(int(requirement.id), [])
        owner = db.get(User, int(requirement.review_owner_id)) if requirement.review_owner_id else None
        result = _requirement_dict(
            requirement, versions, student_view=False,
            owner_name=(owner.real_name if owner else ""),
        )
    legacy._drain_messages()
    return result


def link_legacy_attachment(
    db,
    attachment,
    file_obj: FileObject,
    *,
    student_id: int,
    user: dict,
    sensitivity_level: str,
    material_scope: str = "BUSINESS_SCOPE",
) -> dict:
    """把 AffairsAttachment 变为公共绑定 adapter；不会覆盖已有版本。"""
    _require_file_ready(file_obj)
    asset_code = f"AFFAIRS_ATTACHMENT:{_tid()}:{attachment.biz_type}:{attachment.biz_id}:{attachment.id}"
    asset = db.scalars(select(FileAsset).where(
        FileAsset.tenant_id == _tid(), FileAsset.asset_code == asset_code,
        FileAsset.is_deleted.is_(False),
    ).with_for_update()).first()
    if asset is None:
        asset = FileAsset(
            tenant_id=_tid(), asset_code=asset_code,
            title=attachment.file_name or file_obj.file_name,
            category_code=f"AFFAIRS_{_biz(attachment.biz_type)}",
            owner_type="AFFAIRS_ATTACHMENT", owner_id=str(attachment.id),
            lifecycle_status="ACTIVE", version_count=0,
            sensitivity_level=sensitivity_level,
        )
        db.add(asset)
        db.flush()
    existing = db.scalars(select(FileVersion).where(
        FileVersion.tenant_id == _tid(), FileVersion.asset_id == int(asset.id),
        FileVersion.file_object_id == int(file_obj.id), FileVersion.is_deleted.is_(False),
    )).first()
    if existing is None:
        existing = FileVersion(
            tenant_id=_tid(), asset_id=int(asset.id), file_object_id=int(file_obj.id),
            version_no=max(1, int(asset.version_count or 0) + 1),
            source_channel=attachment.source_channel or "LEGACY_ADAPTER",
            uploader_user_id=str(_actor_id(user) or file_obj.owner_user_id or "") or None,
            uploader_name_snapshot=_actor_name(user), submit_comment=attachment.note,
            status="READY", is_current=True, submitted_at=attachment.created_at or datetime.utcnow(),
            created_by=_actor_id(user) or None,
        )
        db.add(existing)
        db.flush()
    student = _student_profile(db, student_id)
    binding = db.scalars(select(FileBinding).where(
        FileBinding.tenant_id == _tid(), FileBinding.file_id == int(file_obj.id),
        FileBinding.biz_type == _biz(attachment.biz_type),
        FileBinding.biz_id == str(attachment.biz_id),
        FileBinding.relation_type == "AFFAIRS_ATTACHMENT",
        FileBinding.is_deleted.is_(False),
    )).first()
    if binding is None:
        binding = FileBinding(
            tenant_id=_tid(), file_id=int(file_obj.id),
            biz_type=_biz(attachment.biz_type), biz_id=str(attachment.biz_id),
            relation_type="AFFAIRS_ATTACHMENT", subject_type="STUDENT",
            subject_id=str(student_id), version_no=int(existing.version_no),
            is_current=True, status="ACTIVE",
            scope_json={"studentId": str(student_id), "materialScope": material_scope},
            asset_id=int(asset.id), version_id=int(existing.id), module_code=MODULE_CODE,
            student_id=int(student_id), college_id=getattr(student, "college_id", None),
            class_id=getattr(student, "class_id", None),
            data_scope_snapshot_json={
                "studentId": str(student_id), "materialScope": material_scope,
                "sensitivityLevel": sensitivity_level,
            },
            created_by=_actor_id(user) or None,
        )
        db.add(binding)
        db.flush()
    asset.current_version_id = int(existing.id)
    asset.version_count = max(int(asset.version_count or 0), int(existing.version_no))
    attachment.asset_id = int(asset.id)
    attachment.file_version_id = int(existing.id)
    attachment.binding_id = int(binding.id)
    attachment.sensitivity_level = sensitivity_level
    file_obj.security_level = sensitivity_level
    return {
        "assetId": str(asset.id), "fileVersionId": str(existing.id),
        "bindingId": str(binding.id), "versionNo": int(existing.version_no),
    }


def backfill_legacy(user: dict, *, limit: int = 500) -> dict:
    """幂等回填旧 Submission 与 AffairsAttachment；失败即回滚，不伪装完成。"""
    from app.models import AffairsAttachment
    from app.models.affairs_operations import AffairsMaterialRequirement, AffairsMaterialSubmission

    if not (
        has_permission(user or {}, "studentAffairs.archive.batch.manage")
        or has_permission(user or {}, "systemAdmin.file.manage")
        or has_permission(user or {}, "*")
    ):
        raise no_permission("无权执行学工材料回填")
    converted_submissions = 0
    converted_attachments = 0
    with session() as db:
        submissions = db.scalars(select(AffairsMaterialSubmission).where(
            AffairsMaterialSubmission.tenant_id == _tid(),
            AffairsMaterialSubmission.file_version_id.is_(None),
            AffairsMaterialSubmission.is_deleted.is_(False),
        ).order_by(AffairsMaterialSubmission.requirement_id, AffairsMaterialSubmission.version_no)
            .limit(max(1, min(5000, int(limit))))).all()
        for submission in submissions:
            requirement = db.get(AffairsMaterialRequirement, int(submission.requirement_id))
            attachment = db.get(AffairsAttachment, int(submission.affairs_attachment_id))
            file_obj = db.get(FileObject, int(submission.file_id))
            if not requirement or not attachment or not file_obj or file_obj.is_deleted:
                raise AppException("DATA_CONFLICT", f"旧补交记录{submission.id}缺少关联文件，停止回填")
            sensitivity, material_scope = classify_sensitivity(
                requirement.biz_type, requirement.item_code, requirement.item_name,
            )
            requirement.sensitivity_level = sensitivity
            requirement.material_scope = material_scope
            asset = _ensure_asset(db, requirement)
            existing = db.scalars(select(FileVersion).where(
                FileVersion.tenant_id == _tid(), FileVersion.asset_id == int(asset.id),
                FileVersion.file_object_id == int(file_obj.id), FileVersion.is_deleted.is_(False),
            )).first()
            if existing is None:
                existing = FileVersion(
                    tenant_id=_tid(), asset_id=int(asset.id), file_object_id=int(file_obj.id),
                    version_no=int(submission.version_no), source_channel="BACKFILL",
                    uploader_user_id=submission.submitted_by,
                    uploader_name_snapshot="历史回填", submit_comment=attachment.note,
                    status={
                        "ACCEPTED": "APPROVED", "RETURNED": "REJECTED",
                        "SUPERSEDED": "INVALIDATED",
                    }.get(submission.status, "SUBMITTED"),
                    is_current=int(requirement.current_submission_id or 0) == int(submission.id),
                    submitted_at=submission.submitted_at,
                )
                db.add(existing)
                db.flush()
            student = _student_profile(db, requirement.student_id)
            binding = db.scalars(select(FileBinding).where(
                FileBinding.tenant_id == _tid(), FileBinding.version_id == int(existing.id),
                FileBinding.module_code == MODULE_CODE,
                FileBinding.biz_type == "MATERIAL_REQUIREMENT",
                FileBinding.biz_id == str(requirement.id),
                FileBinding.relation_type == "MATERIAL_SUBMISSION",
                FileBinding.is_deleted.is_(False),
            )).first()
            if binding is None:
                binding = FileBinding(
                    tenant_id=_tid(), file_id=int(file_obj.id),
                    biz_type="MATERIAL_REQUIREMENT", biz_id=str(requirement.id),
                    relation_type="MATERIAL_SUBMISSION", subject_type="STUDENT",
                    subject_id=str(requirement.student_id), version_no=int(existing.version_no),
                    is_current=bool(existing.is_current),
                    status="ACTIVE" if existing.is_current else "SUPERSEDED",
                    scope_json={
                        "studentId": str(requirement.student_id),
                        "materialScope": material_scope, "backfilled": True,
                    },
                    asset_id=int(asset.id), version_id=int(existing.id), module_code=MODULE_CODE,
                    student_id=int(requirement.student_id), college_id=getattr(student, "college_id", None),
                    class_id=getattr(student, "class_id", None),
                    data_scope_snapshot_json={
                        "studentId": str(requirement.student_id),
                        "materialScope": material_scope,
                        "sensitivityLevel": sensitivity,
                    },
                )
                db.add(binding)
                db.flush()
            submission.asset_id = int(asset.id)
            submission.file_version_id = int(existing.id)
            submission.binding_id = int(binding.id)
            submission.sensitivity_level = sensitivity
            attachment.asset_id = int(asset.id)
            attachment.file_version_id = int(existing.id)
            attachment.binding_id = int(binding.id)
            attachment.sensitivity_level = sensitivity
            attachment.source_channel = "BACKFILL"
            file_obj.biz_type = "MATERIAL_REQUIREMENT"
            file_obj.biz_id = str(requirement.id)
            file_obj.security_level = sensitivity
            if existing.is_current:
                asset.current_version_id = int(existing.id)
            asset.version_count = max(int(asset.version_count or 0), int(existing.version_no))
            converted_submissions += 1

        attachments = db.scalars(select(AffairsAttachment).where(
            AffairsAttachment.tenant_id == _tid(),
            AffairsAttachment.file_version_id.is_(None),
            AffairsAttachment.biz_type != "MATERIAL_SUPPLEMENT",
            AffairsAttachment.is_deleted.is_(False),
        ).order_by(AffairsAttachment.id).limit(max(1, min(5000, int(limit))))).all()
        for attachment in attachments:
            file_obj = db.get(FileObject, int(attachment.file_id))
            if not file_obj or file_obj.is_deleted:
                raise AppException("DATA_CONFLICT", f"旧附件{attachment.id}缺少文件对象，停止回填")
            try:
                from app.services.affairs_attachment_service import resolve_attachment_student

                student_id = resolve_attachment_student(db, attachment.biz_type, attachment.biz_id)
            except Exception as exc:
                raise AppException("DATA_CONFLICT", f"旧附件{attachment.id}无法解析学生，停止回填") from exc
            sensitivity, material_scope = classify_sensitivity(attachment.biz_type, "", attachment.file_name or "")
            attachment.source_channel = "BACKFILL"
            link_legacy_attachment(
                db, attachment, file_obj, student_id=student_id, user=user,
                sensitivity_level=sensitivity, material_scope=material_scope,
            )
            converted_attachments += 1
        db.commit()
    return {
        "convertedSubmissions": converted_submissions,
        "convertedAttachments": converted_attachments,
        "completed": converted_submissions == 0 and converted_attachments == 0,
    }


def material_overview(
    user: dict,
    *,
    status: str | None = None,
    sensitivity_level: str | None = None,
    page: int = 1,
    page_size: int = 50,
) -> dict:
    items, total = list_teacher_requirements(user, status=status, page=page, page_size=page_size)
    if sensitivity_level:
        level = str(sensitivity_level).upper()
        items = [item for item in items if item.get("sensitivityLevel") == level]
        # 过滤发生在已授权集合内，不能返回未授权全局总数。
        total = len(items)
    summary = {
        "total": total,
        "missing": sum(item["status"] in {"MISSING", "RETURNED"} for item in items),
        "pendingReview": sum(item["status"] == "PENDING_REVIEW" for item in items),
        "accepted": sum(item["status"] == "ACCEPTED" for item in items),
        "highlySensitive": sum(item.get("sensitivityLevel") == "HIGHLY_SENSITIVE" for item in items),
    }
    return {"items": items, "total": total, "summary": summary, "page": page, "pageSize": page_size}


def _manifest_item_dict(item: ArchiveManifestItem) -> dict:
    return {
        "materialCode": item.material_code,
        "assetId": str(item.asset_id),
        "versionId": str(item.version_id),
        "fileObjectId": str(item.file_object_id),
        "fileName": item.file_name_snapshot,
        "sizeBytes": item.size_snapshot,
        "sha256": item.sha256_snapshot,
        "reviewStatus": item.review_status,
        "scanResult": item.scan_result,
        "sortNo": int(item.sort_no or 0),
    }


def _manifest_row(db, manifest: ArchiveManifest) -> dict:
    items = db.scalars(select(ArchiveManifestItem).where(
        ArchiveManifestItem.tenant_id == _tid(),
        ArchiveManifestItem.manifest_id == int(manifest.id),
        ArchiveManifestItem.is_deleted.is_(False),
    ).order_by(ArchiveManifestItem.sort_no, ArchiveManifestItem.id)).all()
    return {
        "manifestId": str(manifest.id), "revision": int(manifest.revision or 1),
        "status": manifest.status, "manifestSha256": manifest.manifest_sha256 or "",
        "frozenAt": _iso(manifest.frozen_at), "packageFileId": str(manifest.package_file_id or ""),
        "items": [_manifest_item_dict(item) for item in items],
        "itemCount": len(items),
    }


def freeze_archive_manifest(db, package, user: dict) -> dict:
    """冻结某学生档案包的真实版本清单。调用方已校验 archive 权限与学生范围。"""
    from app.models.affairs_operations import AffairsMaterialRequirement, AffairsMaterialSubmission

    requirements = db.scalars(select(AffairsMaterialRequirement).where(
        AffairsMaterialRequirement.tenant_id == _tid(),
        AffairsMaterialRequirement.student_id == int(package.student_id),
        AffairsMaterialRequirement.status.in_(("ACCEPTED", "WAIVED")),
        AffairsMaterialRequirement.is_deleted.is_(False),
    ).order_by(AffairsMaterialRequirement.id)).all()
    version_ids: list[tuple[str, int, str]] = []
    for requirement in requirements:
        if requirement.status == "WAIVED" or not requirement.current_submission_id:
            continue
        submission = db.get(AffairsMaterialSubmission, int(requirement.current_submission_id))
        if not submission or submission.status != "ACCEPTED" or not submission.file_version_id:
            raise AppException("DATA_CONFLICT", f"材料{requirement.item_name}未形成已验收公共版本")
        version_ids.append((requirement.item_code, int(submission.file_version_id), "ACCEPTED"))
    if package.package_version_id:
        version_ids.append(("AFFAIRS_PROFILE_PACKAGE", int(package.package_version_id), "APPROVED"))
    if not version_ids:
        raise AppException("DATA_CONFLICT", "学生档案没有可冻结的真实文件版本")

    active = db.scalars(select(ArchiveManifest).where(
        ArchiveManifest.tenant_id == _tid(), ArchiveManifest.module_code == MODULE_CODE,
        ArchiveManifest.archive_type == ARCHIVE_TYPE, ArchiveManifest.target_type == TARGET_TYPE,
        ArchiveManifest.target_id == str(package.id),
        ArchiveManifest.status.in_(ACTIVE_MANIFEST_STATUS),
        ArchiveManifest.is_deleted.is_(False),
    ).with_for_update()).all()
    for old in active:
        old.status = "SUPERSEDED"
    revision = int(db.scalar(select(func.max(ArchiveManifest.revision)).where(
        ArchiveManifest.tenant_id == _tid(), ArchiveManifest.module_code == MODULE_CODE,
        ArchiveManifest.archive_type == ARCHIVE_TYPE, ArchiveManifest.target_type == TARGET_TYPE,
        ArchiveManifest.target_id == str(package.id),
    )) or 0) + 1

    frozen = []
    for order, (material_code, version_id, review_status) in enumerate(version_ids, start=1):
        version = db.get(FileVersion, int(version_id))
        file_obj = db.get(FileObject, int(version.file_object_id)) if version else None
        if not version or version.is_deleted or version.status not in READY_VERSION_STATUS:
            raise AppException("DATA_CONFLICT", "档案材料版本状态不可归档")
        if not file_obj or file_obj.is_deleted:
            raise AppException("DATA_CONFLICT", "档案材料文件不存在")
        _require_file_ready(file_obj)
        frozen.append({
            "materialCode": material_code, "assetId": int(version.asset_id),
            "versionId": int(version.id), "fileObjectId": int(file_obj.id),
            "fileName": file_obj.file_name, "sizeBytes": file_obj.size_bytes,
            "sha256": file_obj.sha256, "reviewStatus": review_status,
            "scanResult": str(file_obj.scan_status or SCAN_NOT_REQUIRED).upper(), "sortNo": order,
        })
    digest_payload = {
        "moduleCode": MODULE_CODE, "archiveType": ARCHIVE_TYPE,
        "targetType": TARGET_TYPE, "targetId": str(package.id),
        "studentId": str(package.student_id), "revision": revision,
        "items": frozen,
    }
    digest = hashlib.sha256(json.dumps(
        digest_payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")).hexdigest()
    manifest = ArchiveManifest(
        tenant_id=_tid(), module_code=MODULE_CODE, archive_type=ARCHIVE_TYPE,
        target_type=TARGET_TYPE, target_id=str(package.id), revision=revision,
        status="FROZEN", rule_version="AFFAIRS_MATERIAL_CENTER_V1",
        manifest_sha256=digest, created_by_name=_actor_name(user),
        frozen_at=datetime.utcnow(), created_by=_actor_id(user) or None,
    )
    db.add(manifest)
    db.flush()
    for item in frozen:
        db.add(ArchiveManifestItem(
            tenant_id=_tid(), manifest_id=int(manifest.id),
            material_code=item["materialCode"], asset_id=item["assetId"],
            version_id=item["versionId"], file_object_id=item["fileObjectId"],
            file_name_snapshot=item["fileName"], size_snapshot=item["sizeBytes"],
            sha256_snapshot=item["sha256"], review_status=item["reviewStatus"],
            scan_result=item["scanResult"], sort_no=item["sortNo"],
            created_by=_actor_id(user) or None,
        ))
    package.manifest_id = int(manifest.id)
    package.manifest_revision = revision
    package.manifest_sha256 = digest
    return _manifest_row(db, manifest)


def get_archive_manifest(package_id: int, user: dict) -> dict:
    from app.models import ArchivePackage

    with session() as db:
        package = db.get(ArchivePackage, int(package_id))
        if not package or package.is_deleted or package.tenant_id != _tid() or not package.manifest_id:
            raise not_found("档案清单不存在")
        if not has_permission(user or {}, "studentAffairs.archive.view"):
            raise not_found("档案清单不存在")
        _require_student_scope(db, package.student_id, user, hide=True)
        manifest = db.get(ArchiveManifest, int(package.manifest_id))
        if not manifest or manifest.is_deleted or manifest.tenant_id != _tid():
            raise not_found("档案清单不存在")
        return _manifest_row(db, manifest)


# 低风险批次保持原数据库实现；正式材料路径不再依赖运行时函数替换。
def create_batch_job(user: dict, payload: dict) -> dict:
    from app.services import affairs_operations_service as legacy
    return legacy.create_batch_job(user, payload)


def run_batch_job(job_id: int, user: dict, failed_only: bool = False) -> dict:
    from app.services import affairs_operations_service as legacy
    return legacy.run_batch_job(job_id, user, failed_only=failed_only)


def list_batch_jobs(user: dict, *, page: int = 1, page_size: int = 50):
    from app.services import affairs_operations_service as legacy
    return legacy.list_batch_jobs(user, page=page, page_size=page_size)


def get_batch_job(user: dict, job_id: int) -> dict:
    from app.services import affairs_operations_service as legacy
    return legacy.get_batch_job(user, job_id)
