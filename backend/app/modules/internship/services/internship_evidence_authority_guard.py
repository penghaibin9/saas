"""包 8：豁免与强制归档统一证据验证器。

所有依据文件必须通过文件中心安全状态和对象关系裁决，并冻结
fileId/version/hash/bindingId。豁免评估与归档详情读取会重新验证；文件、扫描
状态或绑定发生变化时，证据立即 INVALIDATED，不再作为有效豁免依据。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import select

from app.core.exceptions import AppException, no_permission, not_found
from app.core.permissions import enforce_permission, is_super_admin
from app.models import (
    InternshipArchive,
    InternshipAuditTrail,
    InternshipComplianceExemption,
    InternshipRecord,
    StudentProfile,
)
from app.models.file import FileBinding, FileObject
from app.modules.internship.services import internship_archive_service as archive_service
from app.modules.internship.services import internship_compliance_authoritative_service as authoritative
from app.modules.internship.services import internship_compliance_service as compliance_service
from app.modules.internship.services import internship_evidence_package_service as package_service
from app.modules.internship.services import internship_score_archive_guard as score_archive_guard
from app.services.db_service import _as_id, _tid, session
from app.services.file_business_binding_service import bind_file_to_business

_INSTALLED = False
_ORIGINAL_EVALUATE = authoritative.evaluate_internship_compliance
_ORIGINAL_CAPTURE = package_service.capture_archive_snapshot
_ORIGINAL_GET_ARCHIVE = archive_service.get_archive


def _operator(user) -> str:
    return (user or {}).get("realName") or "系统"


def _file_ids(raw) -> list[str]:
    if raw in (None, ""):
        return []
    if not isinstance(raw, list):
        raise AppException("VALIDATION_ERROR", "依据文件必须为数组")
    result = []
    for value in raw:
        if isinstance(value, dict):
            value = value.get("fileId")
        text = str(value or "").strip()
        if not text.isdigit():
            raise AppException("VALIDATION_ERROR", "依据文件 ID 无效")
        if text not in result:
            result.append(text)
    return result


def _is_snapshot_list(raw) -> bool:
    return bool(raw) and isinstance(raw, list) and all(
        isinstance(item, dict)
        and str(item.get("fileId") or "").isdigit()
        and str(item.get("bindingId") or "").isdigit()
        for item in raw
    )


def bind_evidence(
    db,
    *,
    file_ids,
    biz_type: str,
    biz_id,
    relation_type: str,
    actor,
    record: InternshipRecord,
    student: StudentProfile,
) -> list[dict]:
    snapshots = []
    for file_id in _file_ids(file_ids):
        binding = bind_file_to_business(
            db,
            file_id=file_id,
            biz_type=biz_type,
            biz_id=str(biz_id),
            actor=actor or {},
            subject_type="STUDENT",
            subject_id=str(student.id),
            relation_type=relation_type,
            module_code="INTERNSHIP",
            student_id=student.id,
            batch_id=str(record.batch_id or "") or None,
            college_id=getattr(student, "college_id", None),
            class_id=getattr(student, "class_id", None),
            scope={
                "internshipId": str(record.id),
                "studentId": str(student.id),
                "batchId": str(record.batch_id or ""),
                "businessType": biz_type,
                "businessId": str(biz_id),
            },
        )
        db.flush()
        file_obj = db.get(FileObject, int(file_id))
        if not file_obj or not binding.id:
            raise AppException("DATA_CONFLICT", "依据文件未形成有效业务绑定")
        snapshots.append({
            "fileId": str(file_obj.id),
            "fileVersion": int(file_obj.version or 0),
            "fileSha256": file_obj.sha256 or "",
            "scanStatus": file_obj.scan_status,
            "fileStatus": file_obj.status,
            "bindingId": str(binding.id),
            "bindingVersion": int(binding.version or 0),
            "bindingStatus": binding.status,
            "bizType": biz_type,
            "bizId": str(biz_id),
            "relationType": relation_type,
        })
    return snapshots


def validate_evidence(db, snapshots, *, biz_type: str, biz_id) -> tuple[bool, str]:
    if not _is_snapshot_list(snapshots):
        return False, "依据文件缺少正式版本/hash/binding 快照"
    for item in snapshots:
        file_obj = db.scalar(select(FileObject).where(
            FileObject.id == int(item["fileId"]),
            FileObject.tenant_id == _tid(),
            FileObject.is_deleted.is_(False),
        ))
        binding = db.scalar(select(FileBinding).where(
            FileBinding.id == int(item["bindingId"]),
            FileBinding.tenant_id == _tid(),
            FileBinding.file_id == int(item["fileId"]),
            FileBinding.biz_type == biz_type,
            FileBinding.biz_id == str(biz_id),
            FileBinding.status == "ACTIVE",
            FileBinding.is_current.is_(True),
            FileBinding.is_deleted.is_(False),
        ))
        if not file_obj or not binding:
            return False, f"文件 {item['fileId']} 或业务绑定已失效"
        if str(file_obj.status or "").upper() not in {"AVAILABLE", "STORED"}:
            return False, f"文件 {item['fileId']} 当前不可用"
        if str(file_obj.scan_status or "NOT_REQUIRED").upper() not in {"CLEAN", "NOT_REQUIRED"}:
            return False, f"文件 {item['fileId']} 安全扫描状态无效"
        if int(file_obj.version or 0) != int(item.get("fileVersion") or 0):
            return False, f"文件 {item['fileId']} 版本已变化"
        if str(file_obj.sha256 or "") != str(item.get("fileSha256") or ""):
            return False, f"文件 {item['fileId']} hash 已变化"
        if int(binding.version or 0) != int(item.get("bindingVersion") or 0):
            return False, f"文件 {item['fileId']} 绑定版本已变化"
    return True, ""


def _trail(db, target_id, target_type, action, user, detail=None):
    db.add(InternshipAuditTrail(
        tenant_id=_tid(),
        target_id=int(target_id),
        target_type=target_type,
        action=action,
        operator_name=_operator(user),
        detail_json=detail or {},
        occurred_at=datetime.utcnow(),
    ))


def _record_student(db, internship_id, user, action):
    from app.modules.internship.services.internship_scope import assert_internship_record_scope

    record = assert_internship_record_scope(db, internship_id, user, action)
    student = db.scalar(select(StudentProfile).where(
        StudentProfile.id == record.student_id,
        StudentProfile.tenant_id == _tid(),
        StudentProfile.is_deleted.is_(False),
    ))
    if not student:
        raise not_found("实习学生主档不存在")
    return record, student


def grant_exemption(body, user=None):
    payload = body or {}
    reason = str(payload.get("reason") or "").strip()
    if len(reason) < 5:
        raise AppException("VALIDATION_ERROR", "豁免原因不少于 5 字")
    if not payload.get("checkCode") or not payload.get("internshipId"):
        raise AppException("VALIDATION_ERROR", "缺少 internshipId/checkCode")
    if not payload.get("validUntil"):
        raise AppException("VALIDATION_ERROR", "豁免必须设置有效期")
    ids = _file_ids(payload.get("evidenceFileIds") or payload.get("fileIds"))
    if not ids:
        raise AppException("VALIDATION_ERROR", "豁免申请必须绑定依据文件")
    raw_until = payload["validUntil"]
    valid_until = (
        datetime.fromisoformat(str(raw_until).replace("Z", ""))
        if isinstance(raw_until, str) else raw_until
    )
    if not valid_until or valid_until <= datetime.utcnow():
        raise AppException("VALIDATION_ERROR", "豁免有效期必须晚于当前时间")

    with session() as db:
        record, student = _record_student(db, payload["internshipId"], user, "合规豁免申请")
        exemption = InternshipComplianceExemption(
            tenant_id=_tid(),
            internship_id=record.id,
            batch_id=record.batch_id,
            check_code=str(payload["checkCode"]),
            reason=reason,
            valid_from=datetime.utcnow(),
            valid_until=valid_until,
            status="PENDING_REVIEW",
            requested_by_name=_operator(user),
            requested_by_user_id=str((user or {}).get("userId") or ""),
            rule_version=payload.get("ruleVersion"),
        )
        db.add(exemption)
        db.flush()
        exemption.evidence_file_ids = bind_evidence(
            db,
            file_ids=ids,
            biz_type="INTERNSHIP_COMPLIANCE_EXEMPTION",
            biz_id=exemption.id,
            relation_type="EXEMPTION_EVIDENCE",
            actor=user,
            record=record,
            student=student,
        )
        _trail(db, record.id, "COMPLIANCE_EXEMPT", "REQUEST", user, {
            "exemptionId": str(exemption.id),
            "checkCode": exemption.check_code,
            "evidence": exemption.evidence_file_ids,
        })
        db.commit()
        return {
            "id": str(exemption.id),
            "status": exemption.status,
            "checkCode": exemption.check_code,
            "version": int(exemption.version or 0),
        }


def review_exemption(exemption_id, body, user=None):
    enforce_permission(user or {}, "internship.compliance.exempt.approve")
    role = str((user or {}).get("currentRoleCode") or "").upper()
    if role != "SCHOOL_ADMIN" and not is_super_admin(user or {}):
        raise no_permission("仅学校管理员可批准合规豁免")
    payload = body or {}
    action = str(payload.get("action") or "").upper()
    if action not in {"APPROVE", "REJECT"}:
        raise AppException("VALIDATION_ERROR", "action 必须为 APPROVE/REJECT")

    with session() as db:
        exemption = db.scalar(select(InternshipComplianceExemption).where(
            InternshipComplianceExemption.id == _as_id(exemption_id),
            InternshipComplianceExemption.tenant_id == _tid(),
            InternshipComplianceExemption.is_deleted.is_(False),
        ).with_for_update())
        if not exemption:
            raise not_found("合规豁免不存在")
        if payload.get("expectedVersion") is None or int(payload["expectedVersion"]) != int(exemption.version or 0):
            raise AppException("DATA_CONFLICT", "豁免申请版本已变化")
        if exemption.status != "PENDING_REVIEW":
            raise AppException("DATA_CONFLICT", "仅待审核豁免可处理")

        if action == "APPROVE":
            ok, invalid_reason = validate_evidence(
                db,
                exemption.evidence_file_ids,
                biz_type="INTERNSHIP_COMPLIANCE_EXEMPTION",
                biz_id=exemption.id,
            )
            if not ok:
                exemption.status = "INVALIDATED"
                exemption.reviewed_by_name = _operator(user)
                exemption.reviewed_at = datetime.utcnow()
                exemption.version = int(exemption.version or 0) + 1
                _trail(db, exemption.internship_id, "COMPLIANCE_EXEMPT", "INVALIDATE", user, {
                    "exemptionId": str(exemption.id),
                    "reason": invalid_reason,
                })
                db.commit()
                return {
                    "id": str(exemption.id),
                    "status": "INVALIDATED",
                    "version": exemption.version,
                    "invalidationReason": invalid_reason,
                }
            if not exemption.valid_until or exemption.valid_until <= datetime.utcnow():
                raise AppException("DATA_CONFLICT", "豁免有效期无效")
            exemption.status = "APPROVED"
            exemption.approved_by_name = _operator(user)
            exemption.approved_at = datetime.utcnow()
        else:
            exemption.status = "REJECTED"
        exemption.reviewed_by_name = _operator(user)
        exemption.reviewed_at = datetime.utcnow()
        exemption.version = int(exemption.version or 0) + 1
        _trail(db, exemption.internship_id, "COMPLIANCE_EXEMPT", action, user, {
            "exemptionId": str(exemption.id),
            "checkCode": exemption.check_code,
            "comment": payload.get("comment") or "",
        })
        db.commit()
        return {
            "id": str(exemption.id),
            "status": exemption.status,
            "version": exemption.version,
        }


def _invalidate_exemptions(db, internship_id, user=None) -> bool:
    changed = False
    rows = db.scalars(select(InternshipComplianceExemption).where(
        InternshipComplianceExemption.tenant_id == _tid(),
        InternshipComplianceExemption.internship_id == _as_id(internship_id),
        InternshipComplianceExemption.status == "APPROVED",
        InternshipComplianceExemption.is_deleted.is_(False),
    ).with_for_update()).all()
    for exemption in rows:
        ok, reason = validate_evidence(
            db,
            exemption.evidence_file_ids,
            biz_type="INTERNSHIP_COMPLIANCE_EXEMPTION",
            biz_id=exemption.id,
        )
        if ok:
            continue
        exemption.status = "INVALIDATED"
        exemption.version = int(exemption.version or 0) + 1
        _trail(db, exemption.internship_id, "COMPLIANCE_EXEMPT", "INVALIDATE", user, {
            "exemptionId": str(exemption.id),
            "reason": reason,
        })
        changed = True
    return changed


def evaluate_internship_compliance(internship_id, operation="ONBOARD", user=None, db=None):
    if db is not None:
        _invalidate_exemptions(db, internship_id, user)
        db.flush()
        return _ORIGINAL_EVALUATE(
            internship_id, operation=operation, user=user, db=db,
        )
    with session() as active_db:
        changed = _invalidate_exemptions(active_db, internship_id, user)
        if changed:
            active_db.commit()
        return _ORIGINAL_EVALUATE(
            internship_id, operation=operation, user=user, db=active_db,
        )


def capture_archive_snapshot(db, record, evaluation, user):
    snapshot = _ORIGINAL_CAPTURE(db, record, evaluation, user)
    archive = db.scalar(select(InternshipArchive).where(
        InternshipArchive.tenant_id == _tid(),
        InternshipArchive.internship_id == record.id,
        InternshipArchive.is_deleted.is_(False),
    ).order_by(InternshipArchive.id.desc()).with_for_update())
    if not archive or not archive.force_reason or not archive.force_evidence_file_ids:
        return snapshot
    if _is_snapshot_list(archive.force_evidence_file_ids):
        evidence = archive.force_evidence_file_ids
    else:
        student = db.get(StudentProfile, record.student_id)
        evidence = bind_evidence(
            db,
            file_ids=archive.force_evidence_file_ids,
            biz_type="INTERNSHIP_FORCE_ARCHIVE",
            biz_id=archive.id,
            relation_type="FORCE_ARCHIVE_EVIDENCE",
            actor=user,
            record=record,
            student=student,
        )
        archive.force_evidence_file_ids = evidence
    snapshot["forceEvidence"] = evidence
    snapshot["forceEvidenceStatus"] = "VALID"
    return snapshot


def _invalidate_force_archive(internship_id, user=None):
    with session() as db:
        archive = db.scalar(select(InternshipArchive).where(
            InternshipArchive.tenant_id == _tid(),
            InternshipArchive.internship_id == _as_id(internship_id),
            InternshipArchive.status == "ARCHIVED",
            InternshipArchive.is_deleted.is_(False),
        ).order_by(InternshipArchive.id.desc()).with_for_update())
        if not archive or not archive.force_reason:
            return
        ok, reason = validate_evidence(
            db,
            archive.force_evidence_file_ids,
            biz_type="INTERNSHIP_FORCE_ARCHIVE",
            biz_id=archive.id,
        )
        material = dict(archive.material_snapshot or {})
        target = "VALID" if ok else "INVALIDATED"
        if material.get("forceEvidenceStatus") == target:
            return
        material["forceEvidenceStatus"] = target
        if not ok:
            material["forceEvidenceInvalidationReason"] = reason
            _trail(db, archive.internship_id, "ARCHIVE", "FORCE_EVIDENCE_INVALIDATE", user, {
                "archiveId": str(archive.id),
                "reason": reason,
            })
        archive.material_snapshot = material
        archive.snapshot_version = int(archive.snapshot_version or 0) + 1
        db.commit()


def get_archive(internship_id, user=None):
    _invalidate_force_archive(internship_id, user)
    result = _ORIGINAL_GET_ARCHIVE(internship_id, user)
    with session() as db:
        archive = db.scalar(select(InternshipArchive).where(
            InternshipArchive.tenant_id == _tid(),
            InternshipArchive.internship_id == _as_id(internship_id),
            InternshipArchive.is_deleted.is_(False),
        ).order_by(InternshipArchive.id.desc()))
        if archive:
            material = archive.material_snapshot or {}
            result["forceEvidenceStatus"] = material.get("forceEvidenceStatus") or (
                "NOT_APPLICABLE" if not archive.force_reason else "LEGACY_MISSING"
            )
            result["forceEvidenceInvalidationReason"] = material.get(
                "forceEvidenceInvalidationReason", "",
            )
    return result


def install() -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    compliance_service.grant_exemption = grant_exemption
    compliance_service.review_exemption = review_exemption
    compliance_service.evaluate_internship_compliance = evaluate_internship_compliance
    authoritative.evaluate_internship_compliance = evaluate_internship_compliance
    score_archive_guard.evaluate_internship_compliance = evaluate_internship_compliance
    archive_service.evaluate_internship_compliance = evaluate_internship_compliance
    archive_service.get_archive = get_archive
    package_service.capture_archive_snapshot = capture_archive_snapshot
    _INSTALLED = True
