"""阶段 4 兼容收口：为纯结构化业务生成可信不可变快照。

用户上传附件仍必须通过扫描。没有原始附件的过程报告、完整性评估等结构化记录，
由系统生成 NOT_REQUIRED 文件对象，再登记为真实 FileVersion，避免空 manifest，
同时不伪造“用户上传原件”。
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime

from sqlalchemy import func, select

from app.core.exceptions import AppException, not_found
from app.models import InternshipProcessReport, StudentProfile
from app.models.file import ArchiveManifest, ArchiveManifestItem
from app.modules.internship.services import internship_material_center_facade as facade
from app.modules.internship.services import internship_material_center_service as core
from app.modules.internship.services.internship_compliance_authoritative_service import evaluate_internship_compliance
from app.services import file_service
from app.services.db_service import _as_id, _iso, _tid, session


def _generated_source(*, category: str, file_id, title: str, biz_type: str, biz_id,
                      review_status: str, label: str, business_version=None) -> dict:
    return {
        "category": category,
        "materialCode": f"{category}:{biz_id}",
        "fileId": str(file_id),
        "title": title,
        "bizType": biz_type,
        "bizId": str(biz_id),
        "reviewStatus": review_status,
        "sourceChannel": "SYSTEM_GENERATED",
        "sensitivity": "PERSONAL",
        "label": label,
        "businessVersion": business_version,
    }


def _store_snapshot(db, *, payload: dict, filename: str, record, user,
                    category: str, title: str, biz_type: str, biz_id,
                    review_status: str = "APPROVED", business_version=None) -> dict:
    content = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8")
    meta = file_service.store_bytes(
        content,
        filename,
        biz_type="INTERNSHIP",
        biz_id=str(record.id),
        mime_type="text/plain",
        user=user,
        visibility="BIZ_SCOPED",
        security_level="PERSONAL",
    )
    # store_bytes 使用独立会话提交。结束当前只读/适配事务，使 MySQL REPEATABLE READ
    # 后续查询能看到新 FileObject；此前同步出的 Asset/Version 一并安全持久化。
    db.commit()
    refreshed_record = core._assert_scope(db, record.id, user, "登记系统生成实习证据")
    student = db.get(StudentProfile, refreshed_record.student_id)
    source = _generated_source(
        category=category,
        file_id=meta["fileId"],
        title=title,
        biz_type=biz_type,
        biz_id=biz_id,
        review_status=review_status,
        label=title,
        business_version=business_version,
    )
    return core._adopt_source(db, refreshed_record, student, source, user=user)


def preflight_process_report(report_id, user=None) -> dict:
    with session() as db:
        report = db.scalar(select(InternshipProcessReport).where(
            InternshipProcessReport.id == _as_id(report_id),
            InternshipProcessReport.tenant_id == _tid(),
            InternshipProcessReport.is_deleted.is_(False),
        ).with_for_update())
        if not report:
            raise not_found("过程报告不存在")
        record = core._assert_scope(db, report.internship_id, user, "批阅过程报告")
        student = db.get(StudentProfile, record.student_id)
        payload = {
            "schemaVersion": "INTERNSHIP_PROCESS_REPORT_SNAPSHOT_V1",
            "internshipId": str(record.id),
            "studentId": str(record.student_id),
            "studentNo": getattr(student, "student_no", None),
            "studentName": getattr(student, "real_name", None),
            "reportId": str(report.id),
            "reportType": report.report_type,
            "periodKey": report.period_key,
            "content": report.content or "",
            "wordCount": int(report.word_count or 0),
            "businessVersion": int(report.version or 0),
            "submittedAt": _iso(report.submitted_at),
            "generatedAt": datetime.utcnow().isoformat() + "Z",
        }
        item = _store_snapshot(
            db,
            payload=payload,
            filename=f"过程报告_{report.report_type}_{report.period_key}_v{int(report.version or 0)}.txt",
            record=record,
            user=user,
            category="PROCESS_REPORT",
            title=f"{report.report_type} · {report.period_key}",
            biz_type="INTERNSHIP_PROCESS_REPORT",
            biz_id=report.id,
            review_status="APPROVED",
            business_version=int(report.version or 0),
        )
        if not item.get("readyForBusiness"):
            raise AppException("DATA_CONFLICT", "系统生成的过程报告版本不可用，禁止审核通过")
        db.commit()
        return item


def _ensure_archive_state_snapshot(db, record, evaluation: dict, user=None) -> dict:
    student = db.get(StudentProfile, record.student_id)
    payload = {
        "schemaVersion": "INTERNSHIP_ARCHIVE_STATE_SNAPSHOT_V1",
        "tenantId": str(_tid()),
        "internshipId": str(record.id),
        "studentId": str(record.student_id),
        "studentNo": getattr(student, "student_no", None),
        "studentName": getattr(student, "real_name", None),
        "batchId": str(record.batch_id or ""),
        "enterpriseName": record.enterprise_name or "",
        "advisorUserId": str(record.advisor_user_id or ""),
        "advisorName": record.advisor_name or "",
        "recordStatus": record.status,
        "recordVersion": int(record.version or 0),
        "ruleVersion": evaluation.get("ruleVersion"),
        "completeness": evaluation.get("completeness"),
        "blockingItems": evaluation.get("blockingItems") or [],
        "warningItems": evaluation.get("warningItems") or [],
        "generatedAt": datetime.utcnow().isoformat() + "Z",
        "generatedBy": core._op_name(user),
    }
    item = _store_snapshot(
        db,
        payload=payload,
        filename=f"实习归档状态快照_{record.id}_v{int(record.version or 0)}.txt",
        record=record,
        user=user,
        category="ARCHIVE_STATE_SNAPSHOT",
        title="实习归档状态快照",
        biz_type="INTERNSHIP_ARCHIVE_STATE",
        biz_id=f"{record.id}:{int(record.version or 0)}",
        review_status="APPROVED",
        business_version=int(record.version or 0),
    )
    if not item.get("readyForBusiness"):
        raise AppException("DATA_CONFLICT", "系统生成的归档状态快照不可用")
    return item


def prepare_archive_manifest(internship_id, user=None, force_file_ids=None) -> dict:
    with session() as db:
        record = core._assert_scope(db, internship_id, user, "准备实习归档清单")
        synced = facade.sync_record_materials(
            db, record, user=user, force_file_ids=force_file_ids,
        )
        if synced["unsafe"]:
            raise AppException(
                "DATA_CONFLICT",
                "存在扫描中、扫描失败、病毒或无法解析的材料，禁止归档",
                details={"unsafeMaterials": synced["unsafe"]},
            )
        evaluation = evaluate_internship_compliance(
            record.id, "ARCHIVE", user=user, db=db,
        )
        # 无论有无用户附件，都冻结一份系统可信的业务状态快照；它不是上传原件，
        # 但是真实 FileObject/FileVersion，保证 manifest 永不为空并可复核当时规则结论。
        _ensure_archive_state_snapshot(db, record, evaluation, user=user)
        record = core._assert_scope(db, internship_id, user, "准备实习归档清单")
        rows = core._current_rows(db, record)
        if not rows:
            raise AppException("DATA_CONFLICT", "没有可追溯的文件版本，禁止生成实习归档")

        active = db.scalars(select(ArchiveManifest).where(
            ArchiveManifest.tenant_id == _tid(),
            ArchiveManifest.module_code == core.MODULE_CODE,
            ArchiveManifest.archive_type == core.ARCHIVE_TYPE,
            ArchiveManifest.target_type == core.TARGET_TYPE,
            ArchiveManifest.target_id == str(record.id),
            ArchiveManifest.status.in_(core.ACTIVE_MANIFEST_STATUS),
            ArchiveManifest.is_deleted.is_(False),
        ).with_for_update()).all()
        for old in active:
            old.status = "SUPERSEDED"

        revision = int(db.scalar(select(func.max(ArchiveManifest.revision)).where(
            ArchiveManifest.tenant_id == _tid(),
            ArchiveManifest.module_code == core.MODULE_CODE,
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
            "moduleCode": core.MODULE_CODE,
            "archiveType": core.ARCHIVE_TYPE,
            "targetType": core.TARGET_TYPE,
            "targetId": str(record.id),
            "revision": revision,
            "ruleVersion": evaluation.get("ruleVersion"),
            "items": [{
                "materialCode": item["materialCode"],
                "assetId": item["assetId"],
                "versionId": item["versionId"],
                "fileObjectId": item["fileId"],
                "fileName": item["fileName"],
                "sizeBytes": item["sizeBytes"],
                "sha256": item["sha256"],
                "reviewStatus": item["reviewStatus"],
                "scanResult": item["scanStatus"],
                "sortNo": item["sortNo"],
            } for item in frozen],
        }
        manifest_hash = hashlib.sha256(json.dumps(
            digest_payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")).hexdigest()
        manifest = ArchiveManifest(
            tenant_id=_tid(),
            module_code=core.MODULE_CODE,
            archive_type=core.ARCHIVE_TYPE,
            target_type=core.TARGET_TYPE,
            target_id=str(record.id),
            revision=revision,
            status="PREPARED",
            rule_version=evaluation.get("ruleVersion"),
            manifest_sha256=manifest_hash,
            created_by_name=core._op_name(user),
        )
        db.add(manifest)
        db.flush()
        for item in frozen:
            db.add(ArchiveManifestItem(
                tenant_id=_tid(),
                manifest_id=manifest.id,
                material_code=item["materialCode"],
                asset_id=int(item["assetId"]),
                version_id=int(item["versionId"]),
                file_object_id=int(item["fileId"]),
                file_name_snapshot=item["fileName"],
                size_snapshot=item["sizeBytes"],
                sha256_snapshot=item["sha256"],
                review_status=item["reviewStatus"],
                scan_result=item["scanStatus"],
                sort_no=item["sortNo"],
            ))
        core._trail(db, record.id, "MANIFEST_PREPARED", {
            "manifestId": str(manifest.id),
            "revision": revision,
            "manifestSha256": manifest_hash,
            "itemCount": len(frozen),
        }, user)
        db.commit()
        return {
            "manifestId": str(manifest.id),
            "revision": revision,
            "manifestSha256": manifest_hash,
            "itemCount": len(frozen),
        }


# 其余接口继续使用已验证的阶段 4 Facade / 核心实现。
record_detail = facade.record_detail
list_center = facade.list_center
synchronize = facade.synchronize
preflight_agreement = facade.preflight_agreement
preflight_insurance = facade.preflight_insurance
finalize_manifest = facade.finalize_manifest
abort_manifest = facade.abort_manifest
get_manifest = facade.get_manifest
build_versioned_package = facade.build_versioned_package
revoke_manifests = facade.revoke_manifests
