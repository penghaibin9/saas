"""批量归档预览令牌绑定最终备案批次号。"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import re
from datetime import datetime, timezone

from app.core.config import settings
from app.core.exceptions import AppException
from app.models import GraduationArchiveRecord, GraduationStudent
from app.services.db_service import session


def _archive_no(value) -> str:
    text = str(value or f"GDARCH-{datetime.now(timezone.utc):%Y%m%d}").strip().upper()
    if not re.fullmatch(r"[A-Z0-9][A-Z0-9_-]{2,99}", text):
        raise AppException("VALIDATION_ERROR", "archiveBatchNo 格式不正确")
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


def _token_archive_no(preview_token: str | None) -> str:
    if not preview_token or "." not in preview_token:
        raise AppException("VALIDATION_ERROR", "执行前必须先完成归档预览")
    try:
        encoded, supplied = preview_token.split(".", 1)
        expected = base64.urlsafe_b64encode(hmac.new(
            settings.jwt_secret.encode("utf-8"), encoded.encode("ascii"), hashlib.sha256,
        ).digest()).rstrip(b"=").decode()
        if not hmac.compare_digest(supplied, expected):
            raise ValueError("signature")
        payload = json.loads(base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4)))
    except (ValueError, TypeError, json.JSONDecodeError):
        raise AppException("VALIDATION_ERROR", "归档预览凭证无效，请重新预览") from None
    return _archive_no(payload.get("archiveBatchNo"))


def verify_batch_file_preview(batch_id, preview_token: str) -> dict:
    """Verify exactly the snapshot shape produced by ``preview_batch_file``."""
    from app.modules.graduation.services import graduation_archive_consistency as consistency
    from app.modules.graduation.services import graduation_archive_service as service

    archive_no = _token_archive_no(preview_token)
    with session() as db:
        batch = service._require_batch(db, batch_id)
        snapshot = consistency._snapshot(db, batch, "FILE", lock=True)
        snapshot["archiveBatchNo"] = archive_no
        consistency._verify_token(
            preview_token, consistency._token_payload("FILE", batch, snapshot)
        )
        return {**snapshot, "batchId": str(batch.id), "batchName": batch.batch_name}


def _install_consistency_bridge() -> None:
    """Keep V2 manifest execution on the same token contract as its preview."""
    from app.modules.graduation.services import graduation_archive_consistency as consistency

    original = consistency._token_payload
    if not getattr(original, "_archive_batch_no_bound", False):
        def token_payload(mode, batch, snapshot):
            payload = original(mode, batch, snapshot)
            payload["archiveBatchNo"] = str(snapshot.get("archiveBatchNo") or "")
            return payload

        token_payload._archive_batch_no_bound = True
        consistency._token_payload = token_payload
    consistency.verify_batch_file_preview = verify_batch_file_preview


_install_consistency_bridge()


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