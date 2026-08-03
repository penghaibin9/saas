"""Immutable, scope-checked internship regulatory evidence packages."""
from __future__ import annotations

import hashlib
import io
import json
import zipfile
from datetime import date, datetime
from decimal import Decimal

from openpyxl import Workbook
from sqlalchemy import func, inspect, select
from sqlalchemy.exc import IntegrityError

import app.models as models
from app.core.exceptions import AppException, not_found
from app.models import (
    FileObject, InternshipAuditTrail, InternshipBatch, InternshipEvidencePackage,
    InternshipRecord, StudentProfile,
)
from app.modules.internship.services.internship_compliance_service import (
    evaluate_internship_compliance,
)
from app.services import file_service
from app.services.db_service import _as_id, _tid, session

MAX_STUDENTS = 500
PACKAGE_VERSION = "INTERNSHIP_EVIDENCE_V2"
METRIC_VERSION = "internship-compliance-v2"
DOWNLOADABLE_STATUSES = {"AVAILABLE", "STORED"}
SENSITIVE_KEYS = ("phone", "mobile", "id_card", "idcard", "token", "client_ip", "guardian_phone")

EVIDENCE_MODELS = (
    ("agreements", "InternshipAgreement"),
    ("insurance", "InternshipInsurance"),
    ("consents", "InternshipConsent"),
    ("safety", "InternshipSafetyCompletion"),
    ("special-filings", "InternshipSpecialFiling"),
    ("attendance", "InternshipCheckin"),
    ("makeups", "InternshipMakeup"),
    ("leaves", "InternshipLeave"),
    ("reports", "WeeklyReport"),
    ("guidance", "InternshipGuidance"),
    ("visits", "InternshipVisit"),
    ("risks", "RiskRecord"),
    ("incidents", "InternshipIncident"),
    ("enterprise-evaluations", "InternshipEnterpriseEval"),
    ("student-evaluations", "InternshipStudentEval"),
    ("scores", "InternshipFinalScore"),
    ("archive", "InternshipArchive"),
    ("exemptions", "InternshipComplianceExemption"),
)


def _json_value(value):
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    return value


def _safe_row(row) -> dict:
    result = {}
    for col in inspect(row).mapper.column_attrs:
        key = col.key
        value = getattr(row, key)
        lowered = key.lower()
        if any(part in lowered for part in SENSITIVE_KEYS) and value:
            result[key] = hashlib.sha256(str(value).encode()).hexdigest()[:16]
        else:
            result[key] = _json_value(value)
    return result


def _json_bytes(value) -> bytes:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8")


def _add_json(entries: dict[str, bytes], path: str, value) -> None:
    entries[path] = _json_bytes(value)


def _query_evidence(db, model_name: str, internship_id: int):
    model = getattr(models, model_name, None)
    if model is None or not hasattr(model, "internship_id"):
        return []
    conditions = [
        model.tenant_id == _tid(),
        model.internship_id == internship_id,
    ]
    if hasattr(model, "is_deleted"):
        conditions.append(model.is_deleted.is_(False))
    return db.scalars(select(model).where(*conditions).order_by(model.id)).all()


def _file_ids(value) -> list[str]:
    found = []
    for key, item in value.items():
        lowered = key.lower()
        if lowered.endswith("file_id") and item:
            found.append(str(item))
        elif lowered.endswith("file_ids") and isinstance(item, list):
            found.extend(str(x) for x in item if x)
    return found


def _attachment(db, file_id: str, user, prefix: str, entries, file_manifest, missing):
    row = db.scalar(select(FileObject).where(
        FileObject.id == _as_id(file_id), FileObject.tenant_id == _tid(),
        FileObject.is_deleted.is_(False)))
    item = {
        "path": None, "sourceType": "FILE_OBJECT", "sourceId": str(file_id),
        "sourceVersion": int(row.version or 0) if row else None, "fileId": str(file_id),
        "fileName": row.file_name if row else None, "sizeBytes": row.size_bytes if row else None,
        "sha256": row.sha256 if row else None, "included": False, "reason": "",
    }
    if not row:
        item["reason"] = "FILE_NOT_FOUND"
    elif row.status not in DOWNLOADABLE_STATUSES:
        item["reason"] = f"FILE_NOT_DOWNLOADABLE:{row.status}"
    else:
        resolved = file_service.resolve_download(str(file_id), user=user)
        if not resolved:
            item["reason"] = "FILE_NOT_FOUND_OR_NOT_AUTHORIZED"
        else:
            path, filename = resolved
            data = path.read_bytes()
            digest = hashlib.sha256(data).hexdigest()
            safe_name = (filename or row.file_name or f"file-{file_id}").replace("/", "_").replace("\\", "_")
            archive_path = f"{prefix}/{file_id}-{safe_name}"
            entries[archive_path] = data
            item.update({
                "path": archive_path, "fileName": safe_name, "sizeBytes": len(data),
                "sha256": digest, "included": True,
            })
    if not item["included"]:
        missing.append({"code": "ATTACHMENT_MISSING", "fileId": str(file_id),
                        "reason": item["reason"]})
    file_manifest.append(item)


def _record_entries(db, rec, user, base: str, entries, files, missing):
    student = db.get(StudentProfile, rec.student_id)
    _add_json(entries, f"{base}evidence/student-profile.json",
              _safe_row(student) if student else None)
    _add_json(entries, f"{base}evidence/internship-record.json", _safe_row(rec))
    company = db.get(getattr(models, "EmpCompany"), rec.enterprise_id) if rec.enterprise_id else None
    position = db.get(getattr(models, "InternshipPosition"), rec.position_id) if rec.position_id else None
    _add_json(entries, f"{base}evidence/company-position.json", {
        "company": _safe_row(company) if company else None,
        "position": _safe_row(position) if position else None,
    })
    evaluation = evaluate_internship_compliance(rec.id, "ARCHIVE", user=user, db=db)
    _add_json(entries, f"{base}evidence/compliance-result.json", evaluation)
    for folder, model_name in EVIDENCE_MODELS:
        rows = [_safe_row(x) for x in _query_evidence(db, model_name, rec.id)]
        _add_json(entries, f"{base}evidence/{folder}.json", rows)
        for row in rows:
            for file_id in _file_ids(row):
                _attachment(db, file_id, user, f"{base}attachments", entries, files, missing)
    audits = db.scalars(select(InternshipAuditTrail).where(
        InternshipAuditTrail.tenant_id == _tid(),
        InternshipAuditTrail.target_id == rec.id).order_by(InternshipAuditTrail.id)).all()
    _add_json(entries, f"{base}audit/internship-audit.json", [_safe_row(x) for x in audits])
    return evaluation


def capture_archive_snapshot(db, rec, evaluation, user=None) -> dict:
    """Freeze business object ids/versions and file hashes at archive time."""
    student = db.get(StudentProfile, rec.student_id)
    datasets = {}
    file_refs = []
    for folder, model_name in EVIDENCE_MODELS:
        rows = [_safe_row(x) for x in _query_evidence(db, model_name, rec.id)]
        datasets[folder] = rows
        for row in rows:
            for file_id in _file_ids(row):
                file_row = db.scalar(select(FileObject).where(
                    FileObject.id == _as_id(file_id), FileObject.tenant_id == _tid(),
                    FileObject.is_deleted.is_(False)))
                file_refs.append({
                    "fileId": str(file_id), "fileName": file_row.file_name if file_row else None,
                    "sizeBytes": file_row.size_bytes if file_row else None,
                    "sha256": file_row.sha256 if file_row else None,
                    "status": file_row.status if file_row else "MISSING",
                    "sourceVersion": int(file_row.version or 0) if file_row else None,
                })
    audits = db.scalars(select(InternshipAuditTrail).where(
        InternshipAuditTrail.tenant_id == _tid(),
        InternshipAuditTrail.target_id == rec.id).order_by(InternshipAuditTrail.id)).all()
    return {
        "snapshotSchemaVersion": "INTERNSHIP_ARCHIVE_SNAPSHOT_V2",
        "capturedAt": datetime.utcnow().isoformat() + "Z",
        "capturedByUserId": str((user or {}).get("userId") or ""),
        "ruleVersion": evaluation["ruleVersion"],
        "compliance": evaluation,
        "quantityFacts": evaluation.get("quantityFacts"),
        "student": _safe_row(student) if student else None,
        "internshipRecord": _safe_row(rec),
        "datasets": datasets,
        "fileRefs": file_refs,
        "audit": [_safe_row(x) for x in audits],
        "sourceObjectVersions": [
            {"type": "INTERNSHIP_RECORD", "id": str(rec.id), "version": int(rec.version or 0)}
        ],
    }


def archive_zip_from_snapshot(snapshot: dict, user=None, db=None,
                              manifest_extra=None) -> tuple[bytes, dict]:
    """Build an archive package only from its frozen snapshot and frozen file ids."""
    entries = {
        "归档合规结果.json": _json_bytes(snapshot.get("compliance")),
        "规则快照.json": _json_bytes({
            "ruleVersion": snapshot.get("ruleVersion"),
            "capturedAt": snapshot.get("capturedAt"),
        }),
        "审计.json": _json_bytes(snapshot.get("audit") or []),
    }
    datasets = snapshot.get("datasets") or {}
    for name, rows in datasets.items():
        entries[f"evidence/{name}.json"] = _json_bytes(rows)
    wb = Workbook()
    ws = wb.active
    ws.title = "材料清单"
    ws.append(["材料类型", "对象数量"])
    for name, rows in datasets.items():
        ws.append([name, len(rows or [])])
    ws.append(["附件应有数", len(snapshot.get("fileRefs") or [])])
    out = io.BytesIO()
    wb.save(out)
    entries["材料清单.xlsx"] = out.getvalue()
    files, missing = [], []
    def collect(active_db):
        for ref in snapshot.get("fileRefs") or []:
            _attachment(active_db, ref["fileId"], user, "attachments", entries, files, missing)
            if files[-1].get("sha256") != ref.get("sha256"):
                files[-1]["included"] = False
                files[-1]["reason"] = "FILE_HASH_CHANGED_SINCE_ARCHIVE"
                entries.pop(files[-1].get("path"), None)
                missing.append({
                    "code": "ARCHIVED_FILE_CHANGED", "fileId": ref["fileId"],
                    "reason": "FILE_HASH_CHANGED_SINCE_ARCHIVE",
                })
    if not snapshot.get("fileRefs"):
        pass
    elif db is None:
        with session() as owned_db:
            collect(owned_db)
    else:
        collect(db)
    manifest = {
        "packageSchemaVersion": "INTERNSHIP_ARCHIVE_PACKAGE_V2",
        "packageStatus": "READY" if not missing else "READY_WITH_MISSING",
        "snapshotVersion": snapshot.get("snapshotSchemaVersion"),
        "capturedAt": snapshot.get("capturedAt"),
        "ruleVersion": snapshot.get("ruleVersion"),
        "includedItems": ["manifest.json", *sorted(entries)], "missingItems": missing,
        "attachmentCount": sum(1 for x in files if x["included"]), "files": files,
        "packageSha256": None, "totalSizeBytes": None,
    }
    manifest.update(manifest_extra or {})
    return _build_zip(entries, manifest), manifest


def _resolve_records(db, typ, target_id, user):
    from app.modules.internship.services.internship_scope import (
        apply_internship_record_scope, assert_internship_record_scope,
    )
    target = _as_id(target_id)
    if typ == "STUDENT":
        rec = assert_internship_record_scope(db, target, user, "生成学生监管证据包")
        return [rec], rec.batch_id
    if typ == "BATCH":
        query = select(InternshipRecord).where(
            InternshipRecord.tenant_id == _tid(), InternshipRecord.batch_id == target,
            InternshipRecord.is_deleted.is_(False))
        batch_id = target
    elif typ == "ENTERPRISE":
        query = select(InternshipRecord).where(
            InternshipRecord.tenant_id == _tid(), InternshipRecord.enterprise_id == target,
            InternshipRecord.is_deleted.is_(False))
        batch_id = None
    else:
        raise AppException("VALIDATION_ERROR", "packageType 必须为 STUDENT/BATCH/ENTERPRISE")
    scoped = apply_internship_record_scope(query, user)
    total = int(db.scalar(select(func.count()).select_from(scoped.subquery())) or 0)
    if total > MAX_STUDENTS:
        raise AppException("VALIDATION_ERROR",
                           f"证据包包含 {total} 名学生，超过单次上限 {MAX_STUDENTS}，请缩小范围")
    return db.scalars(scoped.order_by(InternshipRecord.id)).all(), batch_id


def _summary_xlsx(records, results) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "合规汇总"
    ws.append(["实习记录ID", "学生ID", "是否通过", "完整度", "阻断项", "规则版本"])
    for rec, result in zip(records, results):
        ws.append([
            rec.id, rec.student_id, "是" if result["passed"] else "否",
            result["completeness"]["ratio"],
            "、".join(item["code"] for item in result["blockers"]),
            result["ruleVersion"],
        ])
    output = io.BytesIO()
    wb.save(output)
    return output.getvalue()


def _build_zip(entries: dict[str, bytes], manifest: dict) -> bytes:
    payload = dict(entries)
    payload["manifest.json"] = _json_bytes(manifest)
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(payload):
            archive.writestr(path, payload[path])
    return output.getvalue()


def generate(package_type, target_id, user=None):
    typ = (package_type or "").upper()
    with session() as db:
        records, batch_id = _resolve_records(db, typ, target_id, user)
        if not records:
            raise not_found("当前数据范围内没有可生成证据包的实习记录")
        latest = int(db.scalar(select(func.max(InternshipEvidencePackage.package_version)).where(
            InternshipEvidencePackage.tenant_id == _tid(),
            InternshipEvidencePackage.package_type == typ,
            InternshipEvidencePackage.target_id == _as_id(target_id))) or 0)
        package = InternshipEvidencePackage(
            tenant_id=_tid(), package_type=typ, batch_id=batch_id,
            target_id=_as_id(target_id), package_version=latest + 1,
            status="FAILED", generated_by_name=(user or {}).get("realName") or "系统",
            generated_at=datetime.utcnow(), row_count=len(records), file_count=0,
        )
        db.add(package)
        try:
            db.flush()
        except IntegrityError as exc:
            raise AppException("DATA_CONFLICT", "同一目标正在生成证据包，请稍后重试") from exc

        entries: dict[str, bytes] = {}
        files, missing, results = [], [], []
        batch = db.get(InternshipBatch, batch_id) if batch_id else None
        rule_snapshot = {
            "batchId": str(batch_id or ""), "rulesConfig": batch.rules_config if batch else None,
            "rulesVersion": batch.rules_version if batch else None,
        }
        _add_json(entries, "rules/compliance-rule-snapshot.json", rule_snapshot)
        if typ == "ENTERPRISE":
            company_model = getattr(models, "EmpCompany")
            company = db.get(company_model, _as_id(target_id))
            positions = db.scalars(select(getattr(models, "InternshipPosition")).where(
                getattr(models, "InternshipPosition").tenant_id == _tid(),
                getattr(models, "InternshipPosition").company_id == _as_id(target_id),
                getattr(models, "InternshipPosition").is_deleted.is_(False))).all()
            inspections = db.scalars(select(getattr(models, "InternshipEnterpriseInspection")).where(
                getattr(models, "InternshipEnterpriseInspection").tenant_id == _tid(),
                getattr(models, "InternshipEnterpriseInspection").company_id == _as_id(target_id),
                getattr(models, "InternshipEnterpriseInspection").is_deleted.is_(False))).all()
            complaints = db.scalars(select(getattr(models, "InternshipComplaint")).where(
                getattr(models, "InternshipComplaint").tenant_id == _tid(),
                getattr(models, "InternshipComplaint").enterprise_id == _as_id(target_id),
                getattr(models, "InternshipComplaint").is_deleted.is_(False))).all()
            _add_json(entries, "evidence/enterprise-master.json",
                      _safe_row(company) if company else None)
            _add_json(entries, "evidence/enterprise-positions.json",
                      [_safe_row(x) for x in positions])
            _add_json(entries, "evidence/enterprise-access-inspections.json",
                      [_safe_row(x) for x in inspections])
            _add_json(entries, "evidence/enterprise-complaints-rectification.json",
                      [_safe_row(x) for x in complaints])
        for rec in records:
            base = "" if typ == "STUDENT" else f"students/{rec.id}/"
            results.append(_record_entries(db, rec, user, base, entries, files, missing))
        entries["summary.xlsx"] = _summary_xlsx(records, results)

        included = ["manifest.json", *sorted(entries)]
        status = "READY" if not missing and all(x["passed"] for x in results) else "READY_WITH_MISSING"
        manifest = {
            "packageId": str(package.id), "packageType": typ,
            "packageVersion": package.package_version, "packageSchemaVersion": PACKAGE_VERSION,
            "packageStatus": status, "tenantId": str(_tid()), "batchId": str(batch_id or ""),
            "targetId": str(target_id),
            "generatedByUserId": str((user or {}).get("userId") or ""),
            "generatedByName": (user or {}).get("realName") or "系统",
            "generatedAt": datetime.utcnow().isoformat() + "Z",
            "ruleVersion": results[0]["ruleVersion"] if results else None,
            "metricVersion": METRIC_VERSION,
            "sourceObjectVersions": [
                {"type": "INTERNSHIP_RECORD", "id": str(x.id), "version": int(x.version or 0)}
                for x in records
            ],
            "includedItems": included, "missingItems": missing, "skippedItems": [],
            "invalidItems": [], "attachmentCount": sum(1 for x in files if x["included"]),
            "totalSizeBytes": None, "packageSha256": None, "files": files,
        }
        zip_bytes = _build_zip(entries, manifest)
        meta = file_service.store_bytes(
            zip_bytes, f"internship-evidence-{typ.lower()}-{target_id}-v{package.package_version}.zip",
            biz_type="COMPLIANCE_EVIDENCE", biz_id=f"{typ}:{target_id}",
            mime_type="application/zip", user=user, visibility="BIZ_SCOPED",
            security_level="SENSITIVE",
        )
        manifest["totalSizeBytes"] = meta["sizeBytes"]
        manifest["packageSha256"] = meta["sha256"]
        package.package_file_id = meta["fileId"]
        package.package_sha256 = meta["sha256"]
        package.package_size_bytes = meta["sizeBytes"]
        package.manifest_json = manifest
        package.included_items = included
        package.missing_items = missing
        package.rule_version = manifest["ruleVersion"]
        package.metric_version = METRIC_VERSION
        package.status = status
        package.file_count = len(entries) + 1
        db.add(InternshipAuditTrail(
            tenant_id=_tid(), target_id=package.id, target_type="EVIDENCE_PACKAGE",
            action="GENERATE", operator_name=(user or {}).get("realName") or "系统",
            detail_json={
                "packageType": typ, "targetId": str(target_id),
                "packageVersion": package.package_version, "status": status,
                "fileId": meta["fileId"], "sha256": meta["sha256"],
            }, occurred_at=datetime.utcnow()))
        db.commit()
        return {
            "id": str(package.id), "fileId": package.package_file_id,
            "version": package.package_version, "status": status,
            "sha256": package.package_sha256, "sizeBytes": package.package_size_bytes,
            "missingItems": missing, "manifest": manifest,
        }


def resolve_package_download(package_id, user=None):
    """Object-scoped package download; missing and denied deliberately look identical."""
    with session() as db:
        package = db.scalar(select(InternshipEvidencePackage).where(
            InternshipEvidencePackage.id == _as_id(package_id),
            InternshipEvidencePackage.tenant_id == _tid(),
            InternshipEvidencePackage.is_deleted.is_(False)))
        if not package or package.status == "INVALIDATED" or not package.package_file_id:
            raise not_found("证据包不存在或不可下载")
        _resolve_records(db, package.package_type, package.target_id, user)
        resolved = file_service.resolve_download(package.package_file_id, user=user)
        if not resolved:
            raise not_found("证据包不存在或不可下载")
        db.add(InternshipAuditTrail(
            tenant_id=_tid(), target_id=package.id, target_type="EVIDENCE_PACKAGE",
            action="DOWNLOAD", operator_name=(user or {}).get("realName") or "系统",
            detail_json={"version": package.package_version,
                         "sha256": package.package_sha256},
            occurred_at=datetime.utcnow()))
        db.commit()
        return resolved
