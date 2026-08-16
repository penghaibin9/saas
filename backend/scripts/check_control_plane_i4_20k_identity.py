#!/usr/bin/env python3
"""I4 real MySQL 20K single-job identity import proof.

No fake fast path is allowed here: the proof uses the production PBKDF2 password
hasher, normalized I3 staging, canonical validation, ImportJob/IdentityImportBatch
leases, canonical onboarding transaction, credential receipt generation, and an
idempotent confirmation replay.
"""
from __future__ import annotations

import hashlib
import json
import os
import resource
import tempfile
import time
from datetime import datetime, timedelta
from pathlib import Path

from openpyxl import Workbook
from sqlalchemy import func, select

from app.core.context import set_current_user, set_tenant
from app.db.session import get_sessionmaker
from app.models import Role, User, UserRole
from app.models.data_exchange import IdentityImportStagingRow, ImportJob, ImportRowError
from app.models.file import FileObject
from app.models.identity_import_batch import IdentityImportBatch
from app.services import data_exchange_job_service as jobs
from app.services.identity_import_file_service import TEACHER_HEADERS
from app.services.identity_import_staging_service import (
    MAX_STAGING_ROWS,
    STAGING_CHUNK_SIZE,
    create_staging_batch,
    stage_identity_xlsx,
    validate_staging,
)

ROWS = 20_000
TENANT_ID = 99420
OPERATOR_ID = 9942001
LOGIN_PREFIX = "I4T"
ROLE_CODE = "ACADEMIC_TEACHER"
IDEMPOTENCY_KEY = "control-plane-i4-20k-confirm-v1"
USER = {
    "tenantId": str(TENANT_ID),
    "userId": str(OPERATOR_ID),
    "realName": "I4 20K Gate",
    "userType": "ADMIN",
    "currentRoleCode": "SCHOOL_ADMIN",
    "permissions": ["*"],
}


def _rss_mb() -> float:
    # Linux ru_maxrss is KiB.
    return round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0, 2)


def _timed(metrics: dict, name: str, fn):
    started = time.monotonic()
    value = fn()
    metrics[f"{name}Seconds"] = round(time.monotonic() - started, 3)
    metrics[f"{name}MaxRssMb"] = _rss_mb()
    return value


def _generate_workbook(path: Path) -> None:
    wb = Workbook(write_only=True)
    ws = wb.create_sheet("教师导入")
    ws.append(list(TEACHER_HEADERS))
    for index in range(1, ROWS + 1):
        values = {
            "工号": f"{LOGIN_PREFIX}{index:06d}",
            "姓名": f"I4教师{index:06d}",
            "所属部门": "",
            "岗位名称": "",
            "预设角色编码": ROLE_CODE,
            "数据范围类型": "",
            "数据范围引用": "",
        }
        ws.append([values.get(header, "") for header in TEACHER_HEADERS])
    wb.save(path)
    wb.close()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _prepare_job_and_file(path: Path) -> tuple[int, int]:
    db = get_sessionmaker()()
    try:
        now = datetime.utcnow()
        file_row = FileObject(
            tenant_id=TENANT_ID,
            file_key="i4-proof/teachers-20000.xlsx",
            file_name="teachers-20000.xlsx",
            ext="xlsx",
            mime_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            size_bytes=path.stat().st_size,
            sha256=_sha256(path),
            biz_type="SYSTEM_IDENTITY_IMPORT",
            biz_id="I4-20K",
            owner_user_id=OPERATOR_ID,
            visibility="PRIVATE",
            security_level="SENSITIVE",
            status="AVAILABLE",
            storage_backend="local",
            storage_zone="ACTIVE",
            upload_source="USER",
            scan_required=False,
            scan_status="NOT_REQUIRED",
            scan_attempts=0,
            available_at=now,
            created_by=OPERATOR_ID,
            updated_by=OPERATOR_ID,
        )
        db.add(file_row)
        db.flush()
        job = ImportJob(
            tenant_id=TENANT_ID,
            module_code="SYSTEM",
            import_type="IDENTITY_TEACHER",
            source_file_id=int(file_row.id),
            adapter_type="IDENTITY_IMPORT_FILE",
            adapter_ref="I4-20K-PENDING",
            template_version="v1",
            status="PARSING",
            total_rows=0,
            valid_rows=0,
            invalid_rows=0,
            confirmed_rows=0,
            operator_id=OPERATOR_ID,
            operator_name=USER["realName"],
            expires_at=now + timedelta(hours=8),
            source_snapshot_json={"kind": "TEACHER", "proof": "I4_20K"},
            result_json={},
            created_by=OPERATOR_ID,
            updated_by=OPERATOR_ID,
        )
        db.add(job)
        db.commit()
        db.refresh(file_row)
        db.refresh(job)
        return int(job.id), int(file_row.id)
    finally:
        db.close()


def _promote_job(job_id: int, file_id: int, staged: dict, batch: dict) -> int:
    db = get_sessionmaker()()
    try:
        row = db.get(ImportJob, job_id)
        assert row is not None
        row.source_file_id = file_id
        row.adapter_type = jobs.IMPORT_ADAPTER_IDENTITY
        row.adapter_ref = str(batch["batchNo"])
        row.status = "VALIDATED"
        row.total_rows = ROWS
        row.valid_rows = ROWS
        row.invalid_rows = 0
        row.source_snapshot_json = {
            "fileName": staged["fileName"],
            "fileSha256": staged["fileSha256"],
            "kind": "TEACHER",
            "parseMode": "NORMALIZED_STAGING",
            "stagingAuthority": True,
            "stagingChunkSize": STAGING_CHUNK_SIZE,
            "stagingRows": ROWS,
            "stagingDigest": staged["stagingDigest"],
        }
        row.result_json = {"batchNo": batch["batchNo"], "stagingAuthority": True}
        row.version = int(row.version or 0) + 1
        db.commit()
        db.refresh(row)
        return int(row.version or 0)
    finally:
        db.close()


def _assert_marker(batch_no: str) -> dict:
    db = get_sessionmaker()()
    try:
        row = db.scalar(select(IdentityImportBatch).where(
            IdentityImportBatch.tenant_id == TENANT_ID,
            IdentityImportBatch.batch_no == batch_no,
            IdentityImportBatch.is_deleted.is_(False),
        ))
        assert row is not None
        payload = dict(row.payload_json or {})
        marker = dict(payload.get("_staging") or {})
        assert payload.get("students") == []
        assert payload.get("teachers") == []
        assert int(marker.get("rows") or 0) == ROWS
        assert int(marker.get("tenantId") or 0) == TENANT_ID
        encoded_size = len(json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
        assert encoded_size < 4096, encoded_size
        return {"payloadBytes": encoded_size, "batchStatus": row.status}
    finally:
        db.close()


def _counts(job_id: int) -> dict:
    db = get_sessionmaker()()
    try:
        user_count = int(db.scalar(select(func.count(User.id)).where(
            User.tenant_id == TENANT_ID,
            User.user_type == "TEACHER",
            User.login_name.like(f"{LOGIN_PREFIX}%"),
            User.is_deleted.is_(False),
        )) or 0)
        role = db.scalar(select(Role).where(
            Role.tenant_id == TENANT_ID,
            Role.role_code == ROLE_CODE,
            Role.is_deleted.is_(False),
        ))
        role_link_count = 0
        if role is not None:
            role_link_count = int(db.scalar(select(func.count(UserRole.id)).join(
                User, User.id == UserRole.user_id,
            ).where(
                UserRole.tenant_id == TENANT_ID,
                UserRole.role_id == int(role.id),
                UserRole.status == "ACTIVE",
                UserRole.is_deleted.is_(False),
                User.tenant_id == TENANT_ID,
                User.user_type == "TEACHER",
                User.login_name.like(f"{LOGIN_PREFIX}%"),
                User.is_deleted.is_(False),
            )) or 0)
        staging_count = int(db.scalar(select(func.count(IdentityImportStagingRow.id)).where(
            IdentityImportStagingRow.tenant_id == TENANT_ID,
            IdentityImportStagingRow.import_job_id == job_id,
            IdentityImportStagingRow.is_deleted.is_(False),
        )) or 0)
        valid_staging_count = int(db.scalar(select(func.count(IdentityImportStagingRow.id)).where(
            IdentityImportStagingRow.tenant_id == TENANT_ID,
            IdentityImportStagingRow.import_job_id == job_id,
            IdentityImportStagingRow.validation_status == "VALID",
            IdentityImportStagingRow.is_deleted.is_(False),
        )) or 0)
        error_count = int(db.scalar(select(func.count(ImportRowError.id)).where(
            ImportRowError.tenant_id == TENANT_ID,
            ImportRowError.import_job_id == job_id,
            ImportRowError.is_deleted.is_(False),
        )) or 0)
        return {
            "runtimeTeachers": user_count,
            "runtimeRoleLinks": role_link_count,
            "stagingRows": staging_count,
            "validStagingRows": valid_staging_count,
            "rowErrors": error_count,
        }
    finally:
        db.close()


def main() -> None:
    assert MAX_STAGING_ROWS == ROWS
    set_tenant({"tenantId": str(TENANT_ID)})
    set_current_user(USER)
    metrics: dict = {
        "schemaVersion": 1,
        "card": "I4",
        "headSha": os.getenv("I4_EXPECTED_SHA") or os.getenv("GITHUB_SHA") or "",
        "rows": ROWS,
        "stagingChunkSize": STAGING_CHUNK_SIZE,
        "startedAt": datetime.utcnow().isoformat(timespec="seconds") + "Z",
    }
    try:
        with tempfile.TemporaryDirectory(prefix="i4-20k-") as tmp:
            workbook = Path(tmp) / "teachers-20000.xlsx"
            _timed(metrics, "xlsxBuild", lambda: _generate_workbook(workbook))
            job_id, file_id = _prepare_job_and_file(workbook)
            metrics["jobId"] = str(job_id)
            metrics["sourceFileId"] = str(file_id)

            staged = _timed(metrics, "stage", lambda: stage_identity_xlsx(
                path=workbook,
                filename=workbook.name,
                kind="TEACHER",
                tenant_id=TENANT_ID,
                job_id=job_id,
                actor_id=OPERATOR_ID,
            ))
            assert int(staged["totalRows"]) == ROWS

            report = _timed(metrics, "validate", lambda: validate_staging(
                user=USER,
                tenant_id=TENANT_ID,
                job_id=job_id,
                parser_errors=list(staged.get("parserErrors") or []),
            ))
            assert list(report.get("errors") or []) == [], report.get("errors")

            batch = create_staging_batch(
                user=USER,
                tenant_id=TENANT_ID,
                job_id=job_id,
                filename=workbook.name,
                file_sha256=staged["fileSha256"],
                total_rows=ROWS,
                staging_digest=staged["stagingDigest"],
                report=report,
            )
            assert int(batch["total"]) == ROWS
            assert int(batch["valid"]) == ROWS
            assert int(batch["invalid"]) == 0
            metrics["batchNoHash"] = hashlib.sha256(str(batch["batchNo"]).encode()).hexdigest()
            metrics.update(_assert_marker(str(batch["batchNo"])))

            expected_version = _promote_job(job_id, file_id, staged, batch)
            result = _timed(metrics, "confirm", lambda: jobs.confirm_identity_import_job(
                str(job_id),
                expected_version=expected_version,
                user=USER,
                idempotency_key=IDEMPOTENCY_KEY,
            ))
            assert result["status"] == "SUCCEEDED", result
            assert int(result.get("confirmedRows") or 0) == ROWS, result
            assert str(result.get("credentialReceiptFileId") or ""), result

            first_counts = _counts(job_id)
            assert first_counts == {
                "runtimeTeachers": ROWS,
                "runtimeRoleLinks": ROWS,
                "stagingRows": ROWS,
                "validStagingRows": ROWS,
                "rowErrors": 0,
            }, first_counts
            metrics.update(first_counts)

            replay = _timed(metrics, "replay", lambda: jobs.confirm_identity_import_job(
                str(job_id),
                expected_version=int(result.get("version") or 0),
                user=USER,
                idempotency_key=IDEMPOTENCY_KEY,
            ))
            assert replay["status"] == "SUCCEEDED"
            assert _counts(job_id) == first_counts
            metrics.update(_assert_marker(str(batch["batchNo"])))
            metrics["idempotentReplay"] = True
            metrics["goldCandidate"] = True
            metrics["finishedAt"] = datetime.utcnow().isoformat(timespec="seconds") + "Z"
            metrics["totalSeconds"] = round(sum(
                float(value) for key, value in metrics.items() if key.endswith("Seconds") and key != "totalSeconds"
            ), 3)
            metrics["maxRssMb"] = _rss_mb()
    finally:
        set_current_user(None)
        set_tenant(None)

    target = Path(os.getenv("I4_EVIDENCE_PATH", "../artifacts/control-plane/i4-20k.json"))
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(metrics, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(metrics, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
