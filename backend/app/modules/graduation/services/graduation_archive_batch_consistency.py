"""批量归档预览令牌绑定最终备案批次号。"""
from __future__ import annotations

from datetime import datetime, timezone

from app.core.exceptions import AppException
from app.models import GraduationArchiveRecord, GraduationStudent
from app.services.db_service import session

def _archive_no(value) -> str:
    text = str(value or "").strip()
    if not text:
        text = f"GDARCH-{datetime.now():%Y%m%d}"
    if len(text) > 100:
        raise AppException("VALIDATION_ERROR", "归档批次号不得超过 100 字符")
    if any(ord(ch) < 32 for ch in text):
        raise AppException("VALIDATION_ERROR", "归档批次号包含非法控制字符")
    return text


def preview_batch_file(batch_id=None, archive_batch_no: str | None = None) -> dict:
    from app.modules.graduation.services import graduation_archive_consistency as consistency
    from app.modules.graduation.services import graduation_archive_service as service

    archive_no = _archive_no(archive_batch_no)
    with session() as db:
        batch = service._require_batch(db, batch_id)
        snapshot = consistency._snapshot(db, batch, "FILE")
        snapshot["archiveBatchNo"] = archive_no
        executable = sum(
            1 for row in snapshot["rows"]
            if not row["missing"] and row["openRisks"] == 0
        )
        skip_reasons: dict[str, int] = {}
        for row in snapshot["rows"]:
            if row["missing"]:
                skip_reasons["missing_materials"] = skip_reasons.get("missing_materials", 0) + 1
            if row["openRisks"] > 0:
                skip_reasons["open_risks"] = skip_reasons.get("open_risks", 0) + 1
        payload = consistency._token_payload("FILE", batch, snapshot)
        return {
            "batchId": str(batch.id), "batchName": batch.batch_name,
            "archiveBatchNo": archive_no,
            "candidateCount": len(snapshot["rows"]), "executableCount": executable,
            "skippedCount": len(snapshot["rows"]) - executable,
            "skipReasons": [{"reason": k, "count": v} for k, v in sorted(skip_reasons.items()) if v],
            "hasAbnormal": executable != len(snapshot["rows"]),
            "snapshotHash": payload["snapshotHash"],
            "previewToken": consistency._sign_token(payload),
            "expiresInSeconds": 600,
            "generatedAt": datetime.now(timezone.utc).isoformat(),
        }


def batch_file(archive_batch_no: str | None = None, batch_id=None, preview_token: str | None = None) -> dict:
    from app.modules.graduation.services import graduation_archive_consistency as consistency
    from app.modules.graduation.services import graduation_archive_service as service

    archive_no = _archive_no(archive_batch_no)
    with session() as db:
        batch = service._require_batch(db, batch_id)
        snapshot = consistency._snapshot(db, batch, "FILE", lock=True)
        snapshot["archiveBatchNo"] = archive_no
        consistency._verify_token(preview_token, consistency._token_payload("FILE", batch, snapshot))
        operator, _ = service._op()
        filed = skipped = 0
        for snap in snapshot["rows"]:
            student = db.get(GraduationStudent, int(snap["studentId"]))
            archive = db.get(GraduationArchiveRecord, int(snap["archiveId"]))
            if (
                not student or student.tenant_id != batch.tenant_id
                or not archive or archive.tenant_id != batch.tenant_id
                or archive.status != "SUBMITTED"
            ):
                skipped += 1
                continue
            checklist, missing = service._check_completeness(db, student)
            if missing or service._count_open_risks(db, student) > 0:
                skipped += 1
                continue
            archive.checklist_json, archive.missing_items = checklist, missing
            archive.status = "FILED"
            archive.verified_by = operator
            archive.filed_at = datetime.now(timezone.utc)
            archive.archive_batch_no = archive_no
            archive.manifest_hash = service._manifest_hash(db, student, archive_no)
            archive.version = int(archive.version or 0) + 1
            if student.stage != "ARCHIVED":
                student.stage = "ARCHIVED"
                student.version = int(student.version or 0) + 1
            service._audit(
                db, archive.id, "批量核验归档",
                detail=f"batchId={batch.id};archiveBatchNo={archive_no};manifest={archive.manifest_hash}",
            )
            filed += 1
        service._audit(
            db, f"batch-file-{batch.id}", "批量核验归档汇总",
            detail=(
                f"filed={filed};skipped={skipped};archiveBatchNo={archive_no};"
                f"preview={consistency._json_hash(snapshot)}"
            ),
        )
        db.commit()
        return {
            "filed": filed, "skipped": skipped, "archiveBatchNo": archive_no,
            "batchId": str(batch.id), "batchName": batch.batch_name,
        }
