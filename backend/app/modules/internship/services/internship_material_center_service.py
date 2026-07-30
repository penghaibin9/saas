"""岗位实习材料与证据中心：旧 file_id → Asset/Version/Binding → ArchiveManifest。

本服务只接管文件证据与版本，不复制协议、保险、报告、风险和归档业务状态机。
旧字段继续双写，阶段 4 先完成回填、审核安全门和真实版本归档。
"""
from __future__ import annotations

import hashlib
import io
import json
import re
import zipfile
from datetime import datetime

from sqlalchemy import func, select

from app.core.exceptions import AppException, not_found
from app.models import (
    AttendanceException, InternshipAgreement, InternshipArchive, InternshipAuditTrail,
    InternshipComplaint, InternshipEnterpriseEval, InternshipEvidencePackage,
    InternshipGuidance, InternshipInsurance, InternshipLeave, InternshipPlanTaskProgress,
    InternshipProcessReport, InternshipRecord, InternshipSafetyCompletion,
    InternshipSpecialFiling, InternshipStudentEval, InternshipVisit, StudentProfile,
)
from app.models.file import (
    ArchiveManifest, ArchiveManifestItem, FileAsset, FileBinding, FileObject, FileVersion,
)
from app.services import file_service
from app.services.db_service import _as_id, _iso, _tid, session
from app.services.storage import get_backend

MODULE_CODE = "INTERNSHIP"
ARCHIVE_TYPE = "STUDENT_INTERNSHIP"
TARGET_TYPE = "INTERNSHIP_RECORD"
READY_SCAN = {"CLEAN", "NOT_REQUIRED"}
READY_FILE_STATUS = {"AVAILABLE", "STORED"}
READY_VERSION_STATUS = {"READY", "SUBMITTED", "APPROVED", "ARCHIVED"}
ACTIVE_MANIFEST_STATUS = {"PREPARED", "FROZEN", "PACKAGED"}

MATERIAL_RULES = {
    "AGREEMENT": {"label": "三方协议", "sensitivity": "SENSITIVE"},
    "INSURANCE": {"label": "保险凭证", "sensitivity": "SENSITIVE"},
    "PROCESS_REPORT": {"label": "过程报告", "sensitivity": "PERSONAL"},
    "GUIDANCE": {"label": "指导记录附件", "sensitivity": "PERSONAL"},
    "VISIT": {"label": "巡访证据", "sensitivity": "PERSONAL"},
    "ENTERPRISE_EVAL": {"label": "企业评价证明", "sensitivity": "SENSITIVE"},
    "STUDENT_EVAL": {"label": "学生鉴定证明", "sensitivity": "PERSONAL"},
    "LEAVE_EVIDENCE": {"label": "请假证明", "sensitivity": "SENSITIVE"},
    "ATTENDANCE_APPEAL": {"label": "打卡申诉证明", "sensitivity": "PERSONAL"},
    "COMPLAINT_EVIDENCE": {"label": "投诉证据", "sensitivity": "CONFIDENTIAL"},
    "PLAN_TASK_EVIDENCE": {"label": "计划任务证据", "sensitivity": "PERSONAL"},
    "SAFETY_EVIDENCE": {"label": "安全教育证据", "sensitivity": "SENSITIVE"},
    "SPECIAL_FILING": {"label": "特殊实习备案", "sensitivity": "SENSITIVE"},
    "FORCE_ARCHIVE_EVIDENCE": {"label": "强制归档依据", "sensitivity": "HIGHLY_SENSITIVE"},
}


def _op_name(user=None) -> str:
    return (user or {}).get("realName") or "系统"


def _user_id(user=None) -> str | None:
    value = (user or {}).get("userId") or (user or {}).get("id")
    return str(value).strip() if value not in (None, "") else None


def _trail(db, target_id: int, action: str, detail: dict | None, user=None) -> None:
    db.add(InternshipAuditTrail(
        tenant_id=_tid(), target_id=target_id, target_type="MATERIAL_CENTER",
        action=action, operator_name=_op_name(user), detail_json=detail or {},
        occurred_at=datetime.utcnow(),
    ))


def _assert_scope(db, internship_id, user, action: str = "查看材料") -> InternshipRecord:
    from app.modules.internship.services.internship_scope import assert_internship_record_scope
    return assert_internship_record_scope(db, _as_id(internship_id), user, action)


def _file_ready(row: FileObject | None) -> bool:
    if not row or row.is_deleted:
        return False
    scan = str(row.scan_status or "NOT_REQUIRED").upper()
    status = str(row.status or "").upper()
    return status in READY_FILE_STATUS and scan in READY_SCAN


def _version_state(row: FileObject, review_status: str | None = None) -> str:
    scan = str(row.scan_status or "NOT_REQUIRED").upper()
    status = str(row.status or "").upper()
    if status not in READY_FILE_STATUS:
        return "REJECTED" if status in {"REJECTED", "DELETED"} else "SCANNING"
    if scan in {"PENDING", "RUNNING", "QUEUED"}:
        return "SCANNING"
    if scan in {"INFECTED", "ERROR", "FAILED"}:
        return "REJECTED"
    reviewed = str(review_status or "").upper()
    if reviewed in {"APPROVED", "VERIFIED", "EFFECTIVE", "ARCHIVED", "PASSED", "RESOLVED", "CLOSED", "CONFIRMED"}:
        return "APPROVED"
    return "SUBMITTED"


def _asset_code(record_id: int, category: str, biz_type: str, biz_id: str) -> str:
    raw = f"INTERNSHIP:{record_id}:{category}:{biz_type}:{biz_id}"
    if len(raw) <= 180:
        return raw
    return f"INTERNSHIP:{record_id}:{category}:{hashlib.sha256(raw.encode()).hexdigest()[:32]}"


def _source(category: str, file_id, *, title: str, biz_type: str, biz_id,
            review_status: str | None = None, source_channel: str = "LEGACY_ADAPTER",
            business_version: int | None = None) -> dict:
    rule = MATERIAL_RULES[category]
    return {
        "category": category, "materialCode": f"{category}:{biz_id}",
        "fileId": str(file_id or "").strip(), "title": title,
        "bizType": str(biz_type), "bizId": str(biz_id),
        "reviewStatus": str(review_status or ""), "sourceChannel": source_channel,
        "sensitivity": rule["sensitivity"], "label": rule["label"],
        "businessVersion": business_version,
    }


def _report_snapshot(db, report: InternshipProcessReport, record: InternshipRecord, student, user) -> str:
    code = _asset_code(record.id, "PROCESS_REPORT", "INTERNSHIP_PROCESS_REPORT", str(report.id))
    asset = db.scalar(select(FileAsset).where(
        FileAsset.tenant_id == _tid(), FileAsset.asset_code == code,
        FileAsset.is_deleted.is_(False)))
    if asset and asset.current_version_id:
        version = db.get(FileVersion, asset.current_version_id)
        binding = db.scalar(select(FileBinding).where(
            FileBinding.tenant_id == _tid(), FileBinding.version_id == asset.current_version_id,
            FileBinding.is_current.is_(True), FileBinding.is_deleted.is_(False)))
        scope = (binding.data_scope_snapshot_json or binding.scope_json or {}) if binding else {}
        if version and version.is_current and str(scope.get("sourceBusinessVersion") or "") == str(int(report.version or 0)):
            return str(version.file_object_id)
    payload = {
        "schemaVersion": "INTERNSHIP_PROCESS_REPORT_SNAPSHOT_V1",
        "internshipId": str(record.id), "studentId": str(record.student_id),
        "studentNo": getattr(student, "student_no", None),
        "studentName": getattr(student, "real_name", None), "reportId": str(report.id),
        "reportType": report.report_type, "periodKey": report.period_key,
        "content": report.content or "", "wordCount": int(report.word_count or 0),
        "businessVersion": int(report.version or 0), "submittedAt": _iso(report.submitted_at),
        "generatedAt": datetime.utcnow().isoformat() + "Z",
    }
    content = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8")
    name = f"过程报告_{report.report_type}_{report.period_key}_v{int(report.version or 0)}.txt"
    meta = file_service.store_bytes(
        content, name, biz_type="INTERNSHIP", biz_id=str(record.id), mime_type="text/plain",
        user=user, visibility="BIZ_SCOPED", security_level="PERSONAL")
    return str(meta["fileId"])


def _model_file_sources(db, record, model, category, biz_type, file_field, title_fn, status_fn):
    rows = db.scalars(select(model).where(
        model.tenant_id == _tid(), model.internship_id == record.id,
        model.is_deleted.is_(False), getattr(model, file_field).is_not(None),
    ).order_by(model.id)).all()
    return [_source(category, getattr(row, file_field), title=title_fn(row),
                    biz_type=biz_type, biz_id=row.id, review_status=status_fn(row)) for row in rows]


def _legacy_sources(db, record: InternshipRecord, user=None, force_file_ids=None) -> list[dict]:
    student = db.get(StudentProfile, record.student_id)
    values: list[dict] = []
    for row in db.scalars(select(InternshipAgreement).where(
        InternshipAgreement.tenant_id == _tid(), InternshipAgreement.internship_id == record.id,
        InternshipAgreement.is_deleted.is_(False), InternshipAgreement.file_id.is_not(None),
    ).order_by(InternshipAgreement.id)).all():
        values.append(_source("AGREEMENT", row.file_id,
            title=f"三方协议 · {getattr(student, 'real_name', '') or row.id}",
            biz_type="INTERNSHIP_AGREEMENT", biz_id=row.id, review_status=row.status))
    for row in db.scalars(select(InternshipInsurance).where(
        InternshipInsurance.tenant_id == _tid(), InternshipInsurance.internship_id == record.id,
        InternshipInsurance.is_deleted.is_(False), InternshipInsurance.file_id.is_not(None),
    ).order_by(InternshipInsurance.id)).all():
        values.append(_source("INSURANCE", row.file_id,
            title=f"实习保险 · {row.policy_no or row.id}", biz_type="INTERNSHIP_INSURANCE",
            biz_id=row.id, review_status=row.status))
    for row in db.scalars(select(InternshipProcessReport).where(
        InternshipProcessReport.tenant_id == _tid(), InternshipProcessReport.internship_id == record.id,
        InternshipProcessReport.is_deleted.is_(False),
    ).order_by(InternshipProcessReport.id)).all():
        values.append(_source("PROCESS_REPORT", _report_snapshot(db, row, record, student, user),
            title=f"{row.report_type} · {row.period_key}", biz_type="INTERNSHIP_PROCESS_REPORT",
            biz_id=row.id, review_status=row.status, source_channel="SYSTEM_GENERATED",
            business_version=int(row.version or 0)))
    specs = (
        (InternshipGuidance, "GUIDANCE", "INTERNSHIP_GUIDANCE", "file_id", lambda x: f"指导记录 · {x.topic or x.id}", lambda x: x.status),
        (InternshipVisit, "VISIT", "INTERNSHIP_VISIT", "file_id", lambda x: f"巡访记录 · {x.id}", lambda x: x.rectify_status),
        (InternshipEnterpriseEval, "ENTERPRISE_EVAL", "INTERNSHIP_ENTERPRISE_EVAL", "file_id", lambda x: f"企业评价 · {x.id}", lambda x: x.school_review_status),
        (InternshipStudentEval, "STUDENT_EVAL", "INTERNSHIP_STUDENT_EVAL", "file_id", lambda x: f"学生鉴定 · {x.id}", lambda x: x.school_review_status),
        (InternshipLeave, "LEAVE_EVIDENCE", "INTERNSHIP_LEAVE", "file_id", lambda x: f"请假证明 · {x.id}", lambda x: x.status),
        (AttendanceException, "ATTENDANCE_APPEAL", "INTERNSHIP_ATTENDANCE_APPEAL", "appeal_file_id", lambda x: f"打卡申诉 · {x.id}", lambda x: x.appeal_status),
        (InternshipComplaint, "COMPLAINT_EVIDENCE", "INTERNSHIP_COMPLAINT", "evidence_file_id", lambda x: f"投诉证据 · {x.id}", lambda x: x.status),
        (InternshipPlanTaskProgress, "PLAN_TASK_EVIDENCE", "INTERNSHIP_PLAN_TASK", "evidence_file_id", lambda x: f"计划任务证据 · {x.task_name}", lambda x: x.status),
        (InternshipSafetyCompletion, "SAFETY_EVIDENCE", "INTERNSHIP_SAFETY", "evidence_file_id", lambda x: f"安全教育证据 · {x.id}", lambda x: x.status),
    )
    for spec in specs:
        values.extend(_model_file_sources(db, record, *spec))
    for filing in db.scalars(select(InternshipSpecialFiling).where(
        InternshipSpecialFiling.tenant_id == _tid(), InternshipSpecialFiling.internship_id == record.id,
        InternshipSpecialFiling.is_deleted.is_(False),
    ).order_by(InternshipSpecialFiling.id)).all():
        for index, file_id in enumerate(filing.file_ids or [], start=1):
            values.append(_source("SPECIAL_FILING", file_id,
                title=f"特殊实习备案 · {filing.filing_type} · {index}",
                biz_type="INTERNSHIP_SPECIAL_FILING", biz_id=f"{filing.id}:{index}",
                review_status=filing.status))
    for index, file_id in enumerate(force_file_ids or [], start=1):
        values.append(_source("FORCE_ARCHIVE_EVIDENCE", file_id,
            title=f"强制归档依据 · {index}", biz_type="INTERNSHIP_ARCHIVE_FORCE",
            biz_id=f"{record.id}:{index}", review_status="APPROVED"))
    return [item for item in values if item["fileId"]]


def _adopt_source(db, record: InternshipRecord, student, source: dict, user=None) -> dict:
    fid = source["fileId"]
    if not str(fid).isdigit():
        return {**source, "readyForBusiness": False, "issue": "LEGACY_FILE_ID_NOT_NUMERIC"}
    file_row = db.scalar(select(FileObject).where(
        FileObject.id == int(fid), FileObject.tenant_id == _tid(), FileObject.is_deleted.is_(False)))
    if not file_row:
        return {**source, "readyForBusiness": False, "issue": "FILE_NOT_FOUND"}
    code = _asset_code(record.id, source["category"], source["bizType"], source["bizId"])
    asset = db.scalar(select(FileAsset).where(
        FileAsset.tenant_id == _tid(), FileAsset.asset_code == code,
        FileAsset.is_deleted.is_(False)).with_for_update())
    if not asset:
        asset = FileAsset(
            tenant_id=_tid(), asset_code=code, title=source["title"],
            category_code=source["category"], owner_type="INTERNSHIP_RECORD",
            owner_id=str(record.id), lifecycle_status="ACTIVE",
            sensitivity_level=source["sensitivity"])
        db.add(asset); db.flush()
    state = _version_state(file_row, source.get("reviewStatus"))
    current = db.scalar(select(FileVersion).where(
        FileVersion.tenant_id == _tid(), FileVersion.asset_id == asset.id,
        FileVersion.is_current.is_(True), FileVersion.is_deleted.is_(False)).with_for_update())
    if current and current.file_object_id == file_row.id:
        current.status = state
        version = current
    else:
        if current:
            current.is_current = False
            if current.status not in {"ARCHIVED", "INVALIDATED"}:
                current.status = "INVALIDATED"
            current.invalidated_at = datetime.utcnow(); current.invalidated_by = _op_name(user)
            current.invalid_reason = "SUPERSEDED_BY_NEW_FILE"
            db.query(FileBinding).filter(
                FileBinding.tenant_id == _tid(), FileBinding.version_id == current.id,
                FileBinding.is_current.is_(True)).update({
                    FileBinding.is_current: False, FileBinding.status: "SUPERSEDED",
                    FileBinding.invalidated_at: datetime.utcnow()}, synchronize_session=False)
        next_no = int(db.scalar(select(func.max(FileVersion.version_no)).where(
            FileVersion.tenant_id == _tid(), FileVersion.asset_id == asset.id)) or 0) + 1
        version = FileVersion(
            tenant_id=_tid(), asset_id=asset.id, file_object_id=file_row.id,
            version_no=next_no, source_channel=source["sourceChannel"],
            uploader_user_id=_user_id(user), uploader_name_snapshot=_op_name(user),
            submit_comment=f"由岗位实习阶段4适配器登记：{source['label']}",
            status=state, is_current=True, submitted_at=datetime.utcnow())
        db.add(version); db.flush()
        asset.current_version_id = version.id; asset.version_count = next_no
        asset.version = int(asset.version or 0) + 1
    binding = db.scalar(select(FileBinding).where(
        FileBinding.tenant_id == _tid(), FileBinding.version_id == version.id,
        FileBinding.module_code == MODULE_CODE, FileBinding.biz_type == source["bizType"],
        FileBinding.biz_id == source["bizId"], FileBinding.relation_type == "MATERIAL",
        FileBinding.is_deleted.is_(False)))
    scope = {
        "internshipId": str(record.id), "studentId": str(record.student_id),
        "batchId": str(record.batch_id or ""), "advisorUserId": str(record.advisor_user_id or ""),
        "advisorName": record.advisor_name or "", "reviewStatus": source.get("reviewStatus") or "",
        "sourceBusinessVersion": source.get("businessVersion"),
    }
    if not binding:
        binding = FileBinding(
            tenant_id=_tid(), file_id=file_row.id, asset_id=asset.id, version_id=version.id,
            module_code=MODULE_CODE, biz_type=source["bizType"], biz_id=source["bizId"],
            relation_type="MATERIAL", subject_type="STUDENT", subject_id=str(record.student_id),
            student_id=record.student_id, batch_id=str(record.batch_id or ""),
            college_id=getattr(student, "college_id", None), class_id=getattr(student, "class_id", None),
            version_no=version.version_no, is_current=True, status="ACTIVE",
            scope_json=scope, data_scope_snapshot_json=scope)
        db.add(binding)
    else:
        binding.file_id = file_row.id; binding.asset_id = asset.id
        binding.is_current = True; binding.status = "ACTIVE"
        binding.scope_json = scope; binding.data_scope_snapshot_json = scope
    ready = _file_ready(file_row) and version.status in READY_VERSION_STATUS
    return {
        **source, "assetId": str(asset.id), "versionId": str(version.id),
        "versionNo": version.version_no, "fileName": file_row.file_name,
        "sizeBytes": file_row.size_bytes, "sha256": file_row.sha256,
        "fileStatus": file_row.status, "scanStatus": file_row.scan_status,
        "versionStatus": version.status, "readyForBusiness": ready,
        "issue": "" if ready else f"FILE_NOT_READY:{file_row.scan_status or file_row.status}",
    }


def sync_record_materials(db, record: InternshipRecord, user=None, force_file_ids=None) -> dict:
    student = db.get(StudentProfile, record.student_id)
    items = [_adopt_source(db, record, student, source, user=user)
             for source in _legacy_sources(db, record, user=user, force_file_ids=force_file_ids)]
    return {"internshipId": str(record.id), "studentId": str(record.student_id),
            "items": items, "unsafe": [item for item in items if not item.get("readyForBusiness")]}


def synchronize(internship_id, user=None) -> dict:
    with session() as db:
        record = _assert_scope(db, internship_id, user, "同步实习材料")
        result = sync_record_materials(db, record, user=user)
        _trail(db, record.id, "MATERIAL_SYNC", {"itemCount": len(result["items"]), "unsafeCount": len(result["unsafe"])}, user)
        db.commit()
        return result


def assert_business_file_ready(db, record: InternshipRecord, *, file_id, category: str,
                               biz_type: str, biz_id, title: str, review_status: str,
                               user=None) -> dict:
    source = _source(category, file_id, title=title, biz_type=biz_type,
                     biz_id=biz_id, review_status=review_status)
    item = _adopt_source(db, record, db.get(StudentProfile, record.student_id), source, user=user)
    if not item.get("readyForBusiness"):
        raise AppException("DATA_CONFLICT", "材料仍在安全扫描、扫描失败或已检出风险，不能核验通过",
            details={"fileId": str(file_id or ""), "scanStatus": item.get("scanStatus"),
                     "versionStatus": item.get("versionStatus"), "issue": item.get("issue")})
    return item


def ensure_report_file_ready(db, report: InternshipProcessReport, record: InternshipRecord, user=None) -> dict:
    file_id = _report_snapshot(db, report, record, db.get(StudentProfile, record.student_id), user)
    return assert_business_file_ready(db, record, file_id=file_id, category="PROCESS_REPORT",
        biz_type="INTERNSHIP_PROCESS_REPORT", biz_id=report.id,
        title=f"{report.report_type} · {report.period_key}", review_status="APPROVED", user=user)


def preflight_agreement(agreement_id, user=None) -> dict:
    with session() as db:
        row = db.scalar(select(InternshipAgreement).where(
            InternshipAgreement.id == _as_id(agreement_id), InternshipAgreement.tenant_id == _tid(),
            InternshipAgreement.is_deleted.is_(False)).with_for_update())
        if not row:
            raise not_found("协议不存在")
        record = _assert_scope(db, row.internship_id, user, "确认协议材料")
        item = assert_business_file_ready(db, record, file_id=row.file_id, category="AGREEMENT",
            biz_type="INTERNSHIP_AGREEMENT", biz_id=row.id, title=f"三方协议 · {row.id}",
            review_status="EFFECTIVE", user=user)
        db.commit(); return item


def preflight_insurance(insurance_id, user=None) -> dict:
    with session() as db:
        row = db.scalar(select(InternshipInsurance).where(
            InternshipInsurance.id == _as_id(insurance_id), InternshipInsurance.tenant_id == _tid(),
            InternshipInsurance.is_deleted.is_(False)).with_for_update())
        if not row:
            raise not_found("保险记录不存在")
        record = _assert_scope(db, row.internship_id, user, "核验保险材料")
        item = assert_business_file_ready(db, record, file_id=row.file_id, category="INSURANCE",
            biz_type="INTERNSHIP_INSURANCE", biz_id=row.id,
            title=f"实习保险 · {row.policy_no or row.id}", review_status="VERIFIED", user=user)
        db.commit(); return item


def preflight_process_report(report_id, user=None) -> dict:
    with session() as db:
        report = db.scalar(select(InternshipProcessReport).where(
            InternshipProcessReport.id == _as_id(report_id), InternshipProcessReport.tenant_id == _tid(),
            InternshipProcessReport.is_deleted.is_(False)).with_for_update())
        if not report:
            raise not_found("过程报告不存在")
        record = _assert_scope(db, report.internship_id, user, "批阅过程报告")
        item = ensure_report_file_ready(db, report, record, user=user)
        db.commit(); return item


def _current_rows(db, record: InternshipRecord) -> list[tuple]:
    return db.execute(select(FileBinding, FileAsset, FileVersion, FileObject)
        .join(FileAsset, FileAsset.id == FileBinding.asset_id)
        .join(FileVersion, FileVersion.id == FileBinding.version_id)
        .join(FileObject, FileObject.id == FileBinding.file_id)
        .where(
            FileBinding.tenant_id == _tid(), FileBinding.module_code == MODULE_CODE,
            FileBinding.student_id == record.student_id,
            FileBinding.batch_id == str(record.batch_id or ""), FileBinding.is_current.is_(True),
            FileBinding.status == "ACTIVE", FileBinding.is_deleted.is_(False),
            FileAsset.lifecycle_status == "ACTIVE", FileAsset.is_deleted.is_(False),
            FileVersion.is_current.is_(True), FileVersion.is_deleted.is_(False),
            FileObject.is_deleted.is_(False))
        .order_by(FileAsset.category_code, FileBinding.id)).all()


def _item(binding, asset, version, file_row) -> dict:
    ready = _file_ready(file_row) and version.status in READY_VERSION_STATUS
    scope = binding.data_scope_snapshot_json or binding.scope_json or {}
    return {
        "bindingId": str(binding.id), "assetId": str(asset.id), "versionId": str(version.id),
        "versionNo": version.version_no, "materialCode": f"{asset.category_code}:{binding.biz_id}",
        "category": asset.category_code,
        "categoryLabel": MATERIAL_RULES.get(asset.category_code, {}).get("label", asset.category_code),
        "title": asset.title, "fileId": str(file_row.id), "fileName": file_row.file_name,
        "sizeBytes": file_row.size_bytes, "sha256": file_row.sha256,
        "scanStatus": file_row.scan_status, "fileStatus": file_row.status,
        "versionStatus": version.status, "reviewStatus": scope.get("reviewStatus") or "",
        "readyForBusiness": ready,
        "statusText": "安全可用" if ready else ("检测到风险，已拒绝" if str(file_row.scan_status).upper() == "INFECTED" else "等待安全扫描/处理"),
        "allowedActions": ["preview", "download"] if ready else [],
        "canPreview": ready, "canDownload": ready,
    }


def _manifest_row(db, manifest: ArchiveManifest) -> dict:
    items = db.scalars(select(ArchiveManifestItem).where(
        ArchiveManifestItem.tenant_id == _tid(), ArchiveManifestItem.manifest_id == manifest.id,
        ArchiveManifestItem.is_deleted.is_(False)).order_by(
            ArchiveManifestItem.sort_no, ArchiveManifestItem.id)).all()
    return {
        "id": str(manifest.id), "moduleCode": manifest.module_code,
        "archiveType": manifest.archive_type, "targetId": manifest.target_id,
        "revision": manifest.revision, "status": manifest.status,
        "ruleVersion": manifest.rule_version, "manifestSha256": manifest.manifest_sha256,
        "packageFileId": str(manifest.package_file_id) if manifest.package_file_id else "",
        "frozenAt": _iso(manifest.frozen_at), "revokedAt": _iso(manifest.revoked_at),
        "revokeReason": manifest.revoke_reason or "",
        "items": [{"materialCode": item.material_code, "assetId": str(item.asset_id),
                   "versionId": str(item.version_id), "fileObjectId": str(item.file_object_id),
                   "fileName": item.file_name_snapshot, "sizeBytes": item.size_snapshot,
                   "sha256": item.sha256_snapshot, "reviewStatus": item.review_status,
                   "scanResult": item.scan_result, "sortNo": item.sort_no} for item in items],
    }


def record_detail(internship_id, user=None, *, auto_sync: bool = False) -> dict:
    if auto_sync:
        synchronize(internship_id, user)
    with session() as db:
        record = _assert_scope(db, internship_id, user, "查看材料与证据中心")
        student = db.get(StudentProfile, record.student_id)
        items = [_item(*row) for row in _current_rows(db, record)]
        manifest = db.scalar(select(ArchiveManifest).where(
            ArchiveManifest.tenant_id == _tid(), ArchiveManifest.module_code == MODULE_CODE,
            ArchiveManifest.target_type == TARGET_TYPE, ArchiveManifest.target_id == str(record.id),
            ArchiveManifest.is_deleted.is_(False)).order_by(ArchiveManifest.revision.desc()))
        return {"internshipId": str(record.id), "studentId": str(record.student_id),
            "studentName": getattr(student, "real_name", "") or "",
            "studentNo": getattr(student, "student_no", "") or "",
            "enterpriseName": record.enterprise_name or "", "advisorName": record.advisor_name or "",
            "batchId": str(record.batch_id or ""), "items": items,
            "summary": {"total": len(items), "ready": sum(1 for x in items if x["readyForBusiness"]),
                        "unsafe": sum(1 for x in items if not x["readyForBusiness"]),
                        "versionCount": sum(int(x["versionNo"] or 0) for x in items)},
            "manifest": _manifest_row(db, manifest) if manifest else None}


def list_center(page=1, page_size=20, *, batch_id=None, keyword=None, safety_status=None, user=None):
    from app.modules.internship.services.internship_batch_context import batch_record_ids
    from app.modules.internship.services.internship_scope import apply_internship_record_scope
    with session() as db:
        batch, record_ids = batch_record_ids(db, batch_id)
        if not record_ids:
            return [], 0
        query = select(InternshipRecord, StudentProfile).join(
            StudentProfile, StudentProfile.id == InternshipRecord.student_id).where(
            InternshipRecord.tenant_id == _tid(), InternshipRecord.id.in_(record_ids),
            InternshipRecord.is_deleted.is_(False), StudentProfile.is_deleted.is_(False))
        query = apply_internship_record_scope(query, user)
        if keyword:
            value = f"%{keyword.strip()}%"
            query = query.where((StudentProfile.real_name.like(value)) | (StudentProfile.student_no.like(value)))
        rows = []
        for record, student in db.execute(query.order_by(InternshipRecord.id.desc())).all():
            items = [_item(*row) for row in _current_rows(db, record)]
            unsafe = sum(1 for x in items if not x["readyForBusiness"])
            if safety_status == "READY" and unsafe: continue
            if safety_status == "UNSAFE" and not unsafe: continue
            rows.append({"internshipId": str(record.id), "studentId": str(record.student_id),
                "studentName": student.real_name or "", "studentNo": student.student_no or "",
                "enterpriseName": record.enterprise_name or "", "advisorName": record.advisor_name or "",
                "batchId": str(batch.id), "materialCount": len(items),
                "readyCount": len(items) - unsafe, "unsafeCount": unsafe,
                "safetyStatus": "READY" if items and not unsafe else ("UNSAFE" if unsafe else "NOT_SYNCED")})
        total = len(rows); start = (max(1, int(page)) - 1) * int(page_size)
        return rows[start:start + int(page_size)], total


def prepare_archive_manifest(internship_id, user=None, force_file_ids=None) -> dict:
    from app.modules.internship.services.internship_compliance_authoritative_service import evaluate_internship_compliance
    with session() as db:
        record = _assert_scope(db, internship_id, user, "准备实习归档清单")
        sync = sync_record_materials(db, record, user=user, force_file_ids=force_file_ids)
        if sync["unsafe"]:
            raise AppException("DATA_CONFLICT", "存在扫描中、扫描失败、病毒或无法解析的材料，禁止归档",
                               details={"unsafeMaterials": sync["unsafe"]})
        rows = _current_rows(db, record)
        if not rows:
            raise AppException("DATA_CONFLICT", "没有可追溯的文件版本，禁止生成实习归档")
        evaluation = evaluate_internship_compliance(record.id, "ARCHIVE", user=user, db=db)
        for old in db.scalars(select(ArchiveManifest).where(
            ArchiveManifest.tenant_id == _tid(), ArchiveManifest.module_code == MODULE_CODE,
            ArchiveManifest.archive_type == ARCHIVE_TYPE, ArchiveManifest.target_type == TARGET_TYPE,
            ArchiveManifest.target_id == str(record.id), ArchiveManifest.status.in_(ACTIVE_MANIFEST_STATUS),
            ArchiveManifest.is_deleted.is_(False)).with_for_update()).all():
            old.status = "SUPERSEDED"
        revision = int(db.scalar(select(func.max(ArchiveManifest.revision)).where(
            ArchiveManifest.tenant_id == _tid(), ArchiveManifest.module_code == MODULE_CODE,
            ArchiveManifest.archive_type == ARCHIVE_TYPE, ArchiveManifest.target_type == TARGET_TYPE,
            ArchiveManifest.target_id == str(record.id))) or 0) + 1
        frozen_items = []
        for order, row in enumerate(rows, start=1):
            binding, asset, version, file_row = row
            if not (_file_ready(file_row) and version.status in READY_VERSION_STATUS):
                raise AppException("DATA_CONFLICT", "归档材料安全状态已变化，请刷新后重试")
            data = _item(binding, asset, version, file_row); data["sortNo"] = order
            frozen_items.append(data)
        digest_payload = {"moduleCode": MODULE_CODE, "archiveType": ARCHIVE_TYPE,
            "targetType": TARGET_TYPE, "targetId": str(record.id), "revision": revision,
            "ruleVersion": evaluation.get("ruleVersion"),
            "items": [{"materialCode": x["materialCode"], "assetId": x["assetId"],
                       "versionId": x["versionId"], "fileObjectId": x["fileId"],
                       "fileName": x["fileName"], "sizeBytes": x["sizeBytes"],
                       "sha256": x["sha256"], "reviewStatus": x["reviewStatus"],
                       "scanResult": x["scanStatus"], "sortNo": x["sortNo"]} for x in frozen_items]}
        manifest_hash = hashlib.sha256(json.dumps(digest_payload, ensure_ascii=False,
            sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
        manifest = ArchiveManifest(
            tenant_id=_tid(), module_code=MODULE_CODE, archive_type=ARCHIVE_TYPE,
            target_type=TARGET_TYPE, target_id=str(record.id), revision=revision,
            status="PREPARED", rule_version=evaluation.get("ruleVersion"),
            manifest_sha256=manifest_hash, created_by_name=_op_name(user))
        db.add(manifest); db.flush()
        for item in frozen_items:
            db.add(ArchiveManifestItem(
                tenant_id=_tid(), manifest_id=manifest.id, material_code=item["materialCode"],
                asset_id=int(item["assetId"]), version_id=int(item["versionId"]),
                file_object_id=int(item["fileId"]), file_name_snapshot=item["fileName"],
                size_snapshot=item["sizeBytes"], sha256_snapshot=item["sha256"],
                review_status=item["reviewStatus"], scan_result=item["scanStatus"],
                sort_no=item["sortNo"]))
        _trail(db, record.id, "MANIFEST_PREPARED", {"manifestId": str(manifest.id),
            "revision": revision, "manifestSha256": manifest_hash,
            "itemCount": len(frozen_items)}, user)
        db.commit()
        return {"manifestId": str(manifest.id), "revision": revision,
                "manifestSha256": manifest_hash, "itemCount": len(frozen_items)}


def abort_manifest(manifest_id, reason: str, user=None) -> None:
    with session() as db:
        row = db.get(ArchiveManifest, _as_id(manifest_id))
        if row and row.tenant_id == _tid() and row.status == "PREPARED":
            row.status = "ABORTED"; row.revoke_reason = str(reason or "")[:500]
            row.revoked_by = _op_name(user); row.revoked_at = datetime.utcnow(); db.commit()


def finalize_manifest(manifest_id, internship_id, user=None) -> dict:
    with session() as db:
        manifest = db.scalar(select(ArchiveManifest).where(
            ArchiveManifest.id == _as_id(manifest_id), ArchiveManifest.tenant_id == _tid(),
            ArchiveManifest.target_id == str(_as_id(internship_id)), ArchiveManifest.status == "PREPARED",
            ArchiveManifest.is_deleted.is_(False)).with_for_update())
        if not manifest:
            raise AppException("DATA_CONFLICT", "归档文件版本清单不存在或状态已变化")
        manifest.status = "FROZEN"; manifest.frozen_at = datetime.utcnow()
        archive = db.scalar(select(InternshipArchive).where(
            InternshipArchive.tenant_id == _tid(), InternshipArchive.internship_id == _as_id(internship_id),
            InternshipArchive.status == "ARCHIVED", InternshipArchive.is_deleted.is_(False)).with_for_update())
        if not archive:
            raise AppException("DATA_CONFLICT", "业务归档未成功，不能冻结文件版本清单")
        items = db.scalars(select(ArchiveManifestItem).where(
            ArchiveManifestItem.tenant_id == _tid(), ArchiveManifestItem.manifest_id == manifest.id,
            ArchiveManifestItem.is_deleted.is_(False)).order_by(
            ArchiveManifestItem.sort_no, ArchiveManifestItem.id)).all()
        snapshot = dict(archive.material_snapshot or {})
        snapshot["fileVersionManifest"] = {
            "schemaVersion": "INTERNSHIP_FILE_VERSION_MANIFEST_V1", "manifestId": str(manifest.id),
            "revision": manifest.revision, "manifestSha256": manifest.manifest_sha256,
            "frozenAt": manifest.frozen_at.isoformat() + "Z",
            "items": [{"materialCode": x.material_code, "assetId": str(x.asset_id),
                       "versionId": str(x.version_id), "fileObjectId": str(x.file_object_id),
                       "fileName": x.file_name_snapshot, "sizeBytes": x.size_snapshot,
                       "sha256": x.sha256_snapshot, "reviewStatus": x.review_status,
                       "scanResult": x.scan_result} for x in items]}
        archive.material_snapshot = snapshot; archive.snapshot_version = int(archive.snapshot_version or 0) + 1
        archive.version = int(archive.version or 0) + 1
        _trail(db, _as_id(internship_id), "MANIFEST_FROZEN",
               {"manifestId": str(manifest.id), "manifestSha256": manifest.manifest_sha256}, user)
        db.commit(); return _manifest_row(db, manifest)


def get_manifest(internship_id, user=None) -> dict | None:
    with session() as db:
        record = _assert_scope(db, internship_id, user, "查看实习归档文件版本清单")
        row = db.scalar(select(ArchiveManifest).where(
            ArchiveManifest.tenant_id == _tid(), ArchiveManifest.module_code == MODULE_CODE,
            ArchiveManifest.target_type == TARGET_TYPE, ArchiveManifest.target_id == str(record.id),
            ArchiveManifest.is_deleted.is_(False)).order_by(ArchiveManifest.revision.desc()))
        return _manifest_row(db, row) if row else None


def build_versioned_package(internship_id, user=None) -> dict:
    from sqlalchemy.exc import IntegrityError
    with session() as db:
        record = _assert_scope(db, internship_id, user, "生成真实版本实习归档包")
        archive = db.scalar(select(InternshipArchive).where(
            InternshipArchive.tenant_id == _tid(), InternshipArchive.internship_id == record.id,
            InternshipArchive.status == "ARCHIVED", InternshipArchive.is_deleted.is_(False)))
        if not archive:
            raise AppException("DATA_CONFLICT", "仅已归档学生可生成归档包")
        manifest = db.scalar(select(ArchiveManifest).where(
            ArchiveManifest.tenant_id == _tid(), ArchiveManifest.module_code == MODULE_CODE,
            ArchiveManifest.target_id == str(record.id), ArchiveManifest.status.in_(("FROZEN", "PACKAGED")),
            ArchiveManifest.is_deleted.is_(False)).order_by(ArchiveManifest.revision.desc()).with_for_update())
        if not manifest:
            raise AppException("DATA_CONFLICT", "缺少已冻结的 file_version 归档清单")
        items = db.scalars(select(ArchiveManifestItem).where(
            ArchiveManifestItem.tenant_id == _tid(), ArchiveManifestItem.manifest_id == manifest.id,
            ArchiveManifestItem.is_deleted.is_(False)).order_by(
            ArchiveManifestItem.sort_no, ArchiveManifestItem.id)).all()
        if not items:
            raise AppException("DATA_CONFLICT", "归档清单没有真实文件版本")
        payload_items = []; entries: dict[str, bytes] = {}
        for item in items:
            version = db.scalar(select(FileVersion).where(
                FileVersion.id == item.version_id, FileVersion.tenant_id == _tid(),
                FileVersion.is_deleted.is_(False)))
            file_row = db.scalar(select(FileObject).where(
                FileObject.id == item.file_object_id, FileObject.tenant_id == _tid(),
                FileObject.is_deleted.is_(False)))
            if not version or not file_row or version.file_object_id != file_row.id:
                raise AppException("DATA_CONFLICT", "归档清单引用的文件版本已损坏")
            if not (_file_ready(file_row) and version.status in READY_VERSION_STATUS):
                raise AppException("DATA_CONFLICT", "归档材料安全状态已变化，禁止打包")
            if file_row.sha256 != item.sha256_snapshot:
                raise AppException("DATA_CONFLICT", "归档材料哈希与冻结清单不一致")
            path = get_backend().fetch_local(file_row.file_key)
            if not path or not path.exists():
                raise AppException("DATA_CONFLICT", "归档材料字节不存在，禁止生成不完整归档包")
            data = path.read_bytes(); digest = hashlib.sha256(data).hexdigest()
            if digest != item.sha256_snapshot:
                raise AppException("DATA_CONFLICT", "归档材料字节哈希校验失败")
            safe_name = re.sub(r"[\\/:*?\"<>|]+", "_", item.file_name_snapshot or f"file-{file_row.id}")
            archive_path = f"materials/{item.sort_no:03d}_{item.material_code.replace(':', '_')}_{safe_name}"
            entries[archive_path] = data
            payload_items.append({"materialCode": item.material_code, "assetId": str(item.asset_id),
                "versionId": str(item.version_id), "fileObjectId": str(item.file_object_id),
                "fileName": safe_name, "archivePath": archive_path, "sizeBytes": len(data),
                "sha256": digest, "reviewStatus": item.review_status, "scanResult": item.scan_result})
        package_manifest = {"schemaVersion": "INTERNSHIP_ARCHIVE_PACKAGE_FILE_VERSION_V1",
            "manifestId": str(manifest.id), "manifestRevision": manifest.revision,
            "manifestSha256": manifest.manifest_sha256, "tenantId": str(_tid()),
            "internshipId": str(record.id), "studentId": str(record.student_id),
            "batchId": str(record.batch_id or ""), "generatedAt": datetime.utcnow().isoformat() + "Z",
            "generatedBy": _op_name(user), "items": payload_items}
        entries["manifest.json"] = json.dumps(package_manifest, ensure_ascii=False,
                                               indent=2, sort_keys=True).encode("utf-8")
        output = io.BytesIO()
        with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive_zip:
            for name in sorted(entries): archive_zip.writestr(name, entries[name])
        zip_bytes = output.getvalue()
        latest = int(db.scalar(select(func.max(InternshipEvidencePackage.package_version)).where(
            InternshipEvidencePackage.tenant_id == _tid(),
            InternshipEvidencePackage.package_type == "ARCHIVE",
            InternshipEvidencePackage.target_id == record.id)) or 0)
        package = InternshipEvidencePackage(
            tenant_id=_tid(), package_type="ARCHIVE", batch_id=record.batch_id,
            target_id=record.id, package_version=latest + 1, status="FAILED",
            generated_by_name=_op_name(user), generated_at=datetime.utcnow(), row_count=1)
        db.add(package)
        try: db.flush()
        except IntegrityError as exc:
            raise AppException("DATA_CONFLICT", "归档包正在生成，请稍后重试") from exc
        student = db.get(StudentProfile, record.student_id)
        safe_student = re.sub(r"[\\/:*?\"<>|]+", "_", getattr(student, "real_name", "") or "学生")
        meta = file_service.store_bytes(
            zip_bytes, f"实习归档_{safe_student}_manifest{manifest.revision}_v{package.package_version}.zip",
            biz_type="ARCHIVE_PACKAGE", biz_id=f"ARCHIVE:{record.id}", mime_type="application/zip",
            user=user, visibility="BIZ_SCOPED", security_level="SENSITIVE")
        package_manifest.update({"packageFileId": str(meta["fileId"]),
            "packageSha256": meta["sha256"], "packageSizeBytes": meta["sizeBytes"]})
        package.package_file_id = meta["fileId"]; package.package_sha256 = meta["sha256"]
        package.package_size_bytes = meta["sizeBytes"]; package.manifest_json = package_manifest
        package.included_items = payload_items; package.missing_items = []
        package.rule_version = manifest.rule_version; package.metric_version = "file-version-manifest-v1"
        package.status = "READY"; package.file_count = len(payload_items)
        manifest.package_file_id = int(meta["fileId"]); manifest.status = "PACKAGED"
        archive.package_file_id = str(meta["fileId"])
        _trail(db, record.id, "VERSIONED_PACKAGE", {"manifestId": str(manifest.id),
            "packageId": str(package.id), "packageVersion": package.package_version,
            "fileId": str(meta["fileId"]), "sha256": meta["sha256"],
            "fileVersionCount": len(payload_items)}, user)
        db.commit()
        return {"fileId": str(meta["fileId"]), "fileName": meta["fileName"],
            "sizeBytes": meta["sizeBytes"], "sha256": meta["sha256"],
            "packageId": str(package.id), "packageVersion": package.package_version,
            "manifestId": str(manifest.id), "manifestRevision": manifest.revision,
            "status": "READY", "packageReady": True}


def revoke_manifests(internship_id, reason: str, user=None) -> dict:
    with session() as db:
        record = _assert_scope(db, internship_id, user, "撤销实习归档文件版本清单")
        rows = db.scalars(select(ArchiveManifest).where(
            ArchiveManifest.tenant_id == _tid(), ArchiveManifest.module_code == MODULE_CODE,
            ArchiveManifest.target_id == str(record.id), ArchiveManifest.status.in_(ACTIVE_MANIFEST_STATUS),
            ArchiveManifest.is_deleted.is_(False)).with_for_update()).all()
        for row in rows:
            row.status = "REVOKED"; row.revoked_at = datetime.utcnow()
            row.revoked_by = _op_name(user); row.revoke_reason = (reason or "").strip()
        _trail(db, record.id, "MANIFEST_REVOKED",
               {"reason": (reason or "").strip(), "manifestCount": len(rows)}, user)
        db.commit(); return {"revokedManifestCount": len(rows)}
