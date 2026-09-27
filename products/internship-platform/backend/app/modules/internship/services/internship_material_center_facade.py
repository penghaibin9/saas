"""阶段 4 岗位实习材料中心兼容 Facade。

核心服务负责 Asset/Version/Binding/Manifest；本层只处理不同旧表的真实关联差异。
尤其投诉记录没有 internship_id，必须按 student_id + batch_id 收敛，禁止伪造关系。
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime

from sqlalchemy import func, select

from app.core.exceptions import AppException
from app.models import (
    AttendanceException, InternshipAgreement, InternshipComplaint, InternshipEnterpriseEval,
    InternshipGuidance, InternshipInsurance, InternshipLeave, InternshipPlanTaskProgress,
    InternshipProcessReport, InternshipSafetyCompletion, InternshipSpecialFiling,
    InternshipStudentEval, InternshipVisit, StudentProfile,
)
from app.models.file import ArchiveManifest, ArchiveManifestItem, FileAsset, FileBinding, FileObject, FileVersion
from app.modules.internship.services import internship_material_center_service as core
from app.modules.internship.services.internship_compliance_authoritative_service import evaluate_internship_compliance
from app.services.db_service import _tid, session


def _model_sources(db, record, model, category, biz_type, file_field, title_fn, status_fn):
    rows = db.scalars(select(model).where(
        model.tenant_id == _tid(), model.internship_id == record.id,
        model.is_deleted.is_(False), getattr(model, file_field).is_not(None),
    ).order_by(model.id)).all()
    return [core._source(category, getattr(row, file_field), title=title_fn(row),
                         biz_type=biz_type, biz_id=row.id,
                         review_status=status_fn(row)) for row in rows]


def _sources(db, record, user=None, force_file_ids=None):
    student = db.get(StudentProfile, record.student_id)
    values = []
    agreements = db.scalars(select(InternshipAgreement).where(
        InternshipAgreement.tenant_id == _tid(), InternshipAgreement.internship_id == record.id,
        InternshipAgreement.is_deleted.is_(False), InternshipAgreement.file_id.is_not(None),
    ).order_by(InternshipAgreement.id)).all()
    for row in agreements:
        values.append(core._source(
            "AGREEMENT", row.file_id,
            title=f"三方协议 · {getattr(student, 'real_name', '') or row.id}",
            biz_type="INTERNSHIP_AGREEMENT", biz_id=row.id, review_status=row.status,
        ))
    insurances = db.scalars(select(InternshipInsurance).where(
        InternshipInsurance.tenant_id == _tid(), InternshipInsurance.internship_id == record.id,
        InternshipInsurance.is_deleted.is_(False), InternshipInsurance.file_id.is_not(None),
    ).order_by(InternshipInsurance.id)).all()
    for row in insurances:
        values.append(core._source(
            "INSURANCE", row.file_id, title=f"实习保险 · {row.policy_no or row.id}",
            biz_type="INTERNSHIP_INSURANCE", biz_id=row.id, review_status=row.status,
        ))
    reports = db.scalars(select(InternshipProcessReport).where(
        InternshipProcessReport.tenant_id == _tid(),
        InternshipProcessReport.internship_id == record.id,
        InternshipProcessReport.is_deleted.is_(False),
    ).order_by(InternshipProcessReport.id)).all()
    for row in reports:
        values.append(core._source(
            "PROCESS_REPORT", core._report_snapshot(db, row, record, student, user),
            title=f"{row.report_type} · {row.period_key}",
            biz_type="INTERNSHIP_PROCESS_REPORT", biz_id=row.id,
            review_status=row.status, source_channel="SYSTEM_GENERATED",
            business_version=int(row.version or 0),
        ))
    specs = (
        (InternshipGuidance, "GUIDANCE", "INTERNSHIP_GUIDANCE", "file_id", lambda x: f"指导记录 · {x.topic or x.id}", lambda x: x.status),
        (InternshipVisit, "VISIT", "INTERNSHIP_VISIT", "file_id", lambda x: f"巡访记录 · {x.id}", lambda x: x.rectify_status),
        (InternshipEnterpriseEval, "ENTERPRISE_EVAL", "INTERNSHIP_ENTERPRISE_EVAL", "file_id", lambda x: f"企业评价 · {x.id}", lambda x: x.school_review_status),
        (InternshipStudentEval, "STUDENT_EVAL", "INTERNSHIP_STUDENT_EVAL", "file_id", lambda x: f"学生鉴定 · {x.id}", lambda x: x.school_review_status),
        (InternshipLeave, "LEAVE_EVIDENCE", "INTERNSHIP_LEAVE", "file_id", lambda x: f"请假证明 · {x.id}", lambda x: x.status),
        (AttendanceException, "ATTENDANCE_APPEAL", "INTERNSHIP_ATTENDANCE_APPEAL", "appeal_file_id", lambda x: f"打卡申诉 · {x.id}", lambda x: x.appeal_status),
        (InternshipPlanTaskProgress, "PLAN_TASK_EVIDENCE", "INTERNSHIP_PLAN_TASK", "evidence_file_id", lambda x: f"计划任务证据 · {x.task_name}", lambda x: x.status),
        (InternshipSafetyCompletion, "SAFETY_EVIDENCE", "INTERNSHIP_SAFETY", "evidence_file_id", lambda x: f"安全教育证据 · {x.id}", lambda x: x.status),
    )
    for spec in specs:
        values.extend(_model_sources(db, record, *spec))

    # 投诉记录没有 internship_id；只接入当前学生且批次明确一致的证据。
    complaint_conditions = [
        InternshipComplaint.tenant_id == _tid(),
        InternshipComplaint.student_id == record.student_id,
        InternshipComplaint.is_deleted.is_(False),
        InternshipComplaint.evidence_file_id.is_not(None),
    ]
    if record.batch_id:
        complaint_conditions.append(InternshipComplaint.batch_id == record.batch_id)
    complaints = db.scalars(select(InternshipComplaint).where(
        *complaint_conditions).order_by(InternshipComplaint.id)).all()
    for row in complaints:
        values.append(core._source(
            "COMPLAINT_EVIDENCE", row.evidence_file_id,
            title=f"投诉证据 · {row.complaint_no or row.id}",
            biz_type="INTERNSHIP_COMPLAINT", biz_id=row.id, review_status=row.status,
        ))

    filings = db.scalars(select(InternshipSpecialFiling).where(
        InternshipSpecialFiling.tenant_id == _tid(),
        InternshipSpecialFiling.internship_id == record.id,
        InternshipSpecialFiling.is_deleted.is_(False),
    ).order_by(InternshipSpecialFiling.id)).all()
    for filing in filings:
        for index, file_id in enumerate(filing.file_ids or [], start=1):
            values.append(core._source(
                "SPECIAL_FILING", file_id,
                title=f"特殊实习备案 · {filing.filing_type} · {index}",
                biz_type="INTERNSHIP_SPECIAL_FILING", biz_id=f"{filing.id}:{index}",
                review_status=filing.status,
            ))
    for index, file_id in enumerate(force_file_ids or [], start=1):
        values.append(core._source(
            "FORCE_ARCHIVE_EVIDENCE", file_id, title=f"强制归档依据 · {index}",
            biz_type="INTERNSHIP_ARCHIVE_FORCE", biz_id=f"{record.id}:{index}",
            review_status="APPROVED",
        ))
    return [item for item in values if item["fileId"]]


def sync_record_materials(db, record, user=None, force_file_ids=None):
    student = db.get(StudentProfile, record.student_id)
    items = [core._adopt_source(db, record, student, source, user=user)
             for source in _sources(db, record, user=user, force_file_ids=force_file_ids)]
    return {
        "internshipId": str(record.id), "studentId": str(record.student_id),
        "items": items, "unsafe": [item for item in items if not item.get("readyForBusiness")],
    }


def synchronize(internship_id, user=None):
    with session() as db:
        record = core._assert_scope(db, internship_id, user, "同步实习材料")
        result = sync_record_materials(db, record, user=user)
        core._trail(db, record.id, "MATERIAL_SYNC", {
            "itemCount": len(result["items"]), "unsafeCount": len(result["unsafe"]),
        }, user)
        db.commit()
        return result


def prepare_archive_manifest(internship_id, user=None, force_file_ids=None):
    with session() as db:
        record = core._assert_scope(db, internship_id, user, "准备实习归档清单")
        synced = sync_record_materials(db, record, user=user, force_file_ids=force_file_ids)
        if synced["unsafe"]:
            raise AppException(
                "DATA_CONFLICT", "存在扫描中、扫描失败、病毒或无法解析的材料，禁止归档",
                details={"unsafeMaterials": synced["unsafe"]},
            )
        rows = core._current_rows(db, record)
        if not rows:
            raise AppException("DATA_CONFLICT", "没有可追溯的文件版本，禁止生成实习归档")
        evaluation = evaluate_internship_compliance(record.id, "ARCHIVE", user=user, db=db)
        active = db.scalars(select(ArchiveManifest).where(
            ArchiveManifest.tenant_id == _tid(), ArchiveManifest.module_code == core.MODULE_CODE,
            ArchiveManifest.archive_type == core.ARCHIVE_TYPE,
            ArchiveManifest.target_type == core.TARGET_TYPE,
            ArchiveManifest.target_id == str(record.id),
            ArchiveManifest.status.in_(core.ACTIVE_MANIFEST_STATUS),
            ArchiveManifest.is_deleted.is_(False),
        ).with_for_update()).all()
        for old in active:
            old.status = "SUPERSEDED"
        revision = int(db.scalar(select(func.max(ArchiveManifest.revision)).where(
            ArchiveManifest.tenant_id == _tid(), ArchiveManifest.module_code == core.MODULE_CODE,
            ArchiveManifest.archive_type == core.ARCHIVE_TYPE,
            ArchiveManifest.target_type == core.TARGET_TYPE,
            ArchiveManifest.target_id == str(record.id),
        )) or 0) + 1
        frozen = []
        for order, row in enumerate(rows, start=1):
            binding, asset, version, file_row = row
            if not (core._file_ready(file_row) and version.status in core.READY_VERSION_STATUS):
                raise AppException("DATA_CONFLICT", "归档材料安全状态已变化，请刷新后重试")
            item = core._item(binding, asset, version, file_row)
            item["sortNo"] = order
            frozen.append(item)
        digest_payload = {
            "moduleCode": core.MODULE_CODE, "archiveType": core.ARCHIVE_TYPE,
            "targetType": core.TARGET_TYPE, "targetId": str(record.id),
            "revision": revision, "ruleVersion": evaluation.get("ruleVersion"),
            "items": [{
                "materialCode": item["materialCode"], "assetId": item["assetId"],
                "versionId": item["versionId"], "fileObjectId": item["fileId"],
                "fileName": item["fileName"], "sizeBytes": item["sizeBytes"],
                "sha256": item["sha256"], "reviewStatus": item["reviewStatus"],
                "scanResult": item["scanStatus"], "sortNo": item["sortNo"],
            } for item in frozen],
        }
        manifest_hash = hashlib.sha256(json.dumps(
            digest_payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
        ).encode("utf-8")).hexdigest()
        manifest = ArchiveManifest(
            tenant_id=_tid(), module_code=core.MODULE_CODE, archive_type=core.ARCHIVE_TYPE,
            target_type=core.TARGET_TYPE, target_id=str(record.id), revision=revision,
            status="PREPARED", rule_version=evaluation.get("ruleVersion"),
            manifest_sha256=manifest_hash, created_by_name=core._op_name(user),
        )
        db.add(manifest)
        db.flush()
        for item in frozen:
            db.add(ArchiveManifestItem(
                tenant_id=_tid(), manifest_id=manifest.id,
                material_code=item["materialCode"], asset_id=int(item["assetId"]),
                version_id=int(item["versionId"]), file_object_id=int(item["fileId"]),
                file_name_snapshot=item["fileName"], size_snapshot=item["sizeBytes"],
                sha256_snapshot=item["sha256"], review_status=item["reviewStatus"],
                scan_result=item["scanStatus"], sort_no=item["sortNo"],
            ))
        core._trail(db, record.id, "MANIFEST_PREPARED", {
            "manifestId": str(manifest.id), "revision": revision,
            "manifestSha256": manifest_hash, "itemCount": len(frozen),
        }, user)
        db.commit()
        return {
            "manifestId": str(manifest.id), "revision": revision,
            "manifestSha256": manifest_hash, "itemCount": len(frozen),
        }


# 其余能力只读取已经登记的权威资产/版本，直接复用核心服务。
record_detail = core.record_detail
list_center = core.list_center
preflight_agreement = core.preflight_agreement
preflight_insurance = core.preflight_insurance
preflight_process_report = core.preflight_process_report
finalize_manifest = core.finalize_manifest
abort_manifest = core.abort_manifest
get_manifest = core.get_manifest
build_versioned_package = core.build_versioned_package
revoke_manifests = core.revoke_manifests
