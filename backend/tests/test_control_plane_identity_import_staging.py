from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import delete, select

from app.core.context import set_current_user, set_tenant
from app.core.exceptions import AppException
from app.db.session import get_sessionmaker
from app.models.data_exchange import IdentityImportStagingRow, ImportRowError
from app.models.identity_import_batch import IdentityImportBatch
from app.services import identity_import_staging_service as staging

TENANT_ID = 95531
USER_ID = 955
USER = {
    "tenantId": str(TENANT_ID),
    "userId": str(USER_ID),
    "realName": "I3 staging test",
    "userType": "ADMIN",
    "currentRoleCode": "SCHOOL_ADMIN",
    "permissions": ["*"],
}


@pytest.fixture(autouse=True)
def _context_and_cleanup(db_mode):
    set_tenant({"tenantId": str(TENANT_ID)})
    set_current_user(USER)
    db = get_sessionmaker()()
    try:
        db.execute(delete(ImportRowError).where(ImportRowError.tenant_id == TENANT_ID))
        db.execute(delete(IdentityImportStagingRow).where(IdentityImportStagingRow.tenant_id == TENANT_ID))
        db.execute(delete(IdentityImportBatch).where(IdentityImportBatch.tenant_id == TENANT_ID))
        db.commit()
    finally:
        db.close()
    yield
    db = get_sessionmaker()()
    try:
        db.execute(delete(ImportRowError).where(ImportRowError.tenant_id == TENANT_ID))
        db.execute(delete(IdentityImportStagingRow).where(IdentityImportStagingRow.tenant_id == TENANT_ID))
        db.execute(delete(IdentityImportBatch).where(IdentityImportBatch.tenant_id == TENANT_ID))
        db.commit()
    finally:
        db.close()
    set_current_user(None)
    set_tenant(None)


def _stage_rows(job_id: int, count: int = 5):
    db = get_sessionmaker()()
    try:
        for index in range(1, count + 1):
            payload = {
                "_rowNo": index + 1,
                "studentNo": f"S{index:04d}",
                "name": f"学生{index}",
                "collegeName": "信息工程学院",
                "majorName": "软件技术",
                "className": "软件2601",
                "grade": "2026",
                "gender": "",
                "idCard": "",
            }
            db.add(IdentityImportStagingRow(
                tenant_id=TENANT_ID,
                import_job_id=job_id,
                row_no=index + 1,
                entity_type="STUDENT",
                natural_key=payload["studentNo"],
                payload_json=payload,
                validation_status="VALID",
                error_count=0,
                row_digest=staging._row_digest(payload),
            ))
        db.commit()
    finally:
        db.close()


def test_i3_schema_and_source_contracts():
    root = Path(__file__).resolve().parents[2]
    migration = (root / "backend/alembic/versions/20260815_control_plane_identity_staging.py").read_text(encoding="utf-8")
    orchestrator = (root / "backend/app/services/identity_import_scan_orchestrator.py").read_text(encoding="utf-8")
    service = (root / "backend/app/services/identity_import_staging_service.py").read_text(encoding="utf-8")
    identity = (root / "backend/app/services/identity_import_service.py").read_text(encoding="utf-8")

    assert 'revision = "20260815_ctrl_identity_staging"' in migration
    assert 'down_revision = "20260815_ctrl_role_gov"' in migration
    assert '"t_identity_import_staging_row"' in migration
    assert staging.MAX_STAGING_ROWS == 20_000
    assert staging.STAGING_CHUNK_SIZE <= 1000
    assert "parse_identity_xlsx_path" not in orchestrator
    assert "create_batch(" not in orchestrator
    assert "stage_identity_xlsx(" in orchestrator
    assert '"parseMode": "NORMALIZED_STAGING"' in orchestrator
    assert "StagingRowSequence" in service
    assert ".limit(self.chunk_size)" in service
    assert "expand_staging_marker" in identity


def test_staging_sequence_is_repeatable_and_keyset_paged():
    job_id = 71001
    _stage_rows(job_id, 5)
    sequence = staging.StagingRowSequence(TENANT_ID, job_id, "STUDENT", chunk_size=2)
    first = [row["studentNo"] for row in sequence]
    second = [row["studentNo"] for row in sequence]
    assert first == ["S0001", "S0002", "S0003", "S0004", "S0005"]
    assert second == first
    assert bool(sequence) is True


def test_staging_digest_detects_payload_tamper():
    job_id = 71002
    _stage_rows(job_id, 3)
    count, digest = staging.staging_fingerprint(TENANT_ID, job_id)
    assert count == 3
    staging.assert_staging_integrity(
        tenant_id=TENANT_ID, job_id=job_id, expected_rows=count, expected_digest=digest
    )

    db = get_sessionmaker()()
    try:
        row = db.scalar(select(IdentityImportStagingRow).where(
            IdentityImportStagingRow.tenant_id == TENANT_ID,
            IdentityImportStagingRow.import_job_id == job_id,
        ).order_by(IdentityImportStagingRow.row_no).limit(1))
        payload = dict(row.payload_json or {})
        payload["name"] = "被篡改"
        row.payload_json = payload
        db.commit()
    finally:
        db.close()

    with pytest.raises(AppException) as exc:
        staging.assert_staging_integrity(
            tenant_id=TENANT_ID, job_id=job_id, expected_rows=count, expected_digest=digest
        )
    assert exc.value.code == "STAGING_INTEGRITY_DRIFT"


def test_staging_marker_expands_in_place_without_row_list():
    job_id = 71003
    _stage_rows(job_id, 4)
    count, digest = staging.staging_fingerprint(TENANT_ID, job_id)
    source = {
        "tenantId": str(TENANT_ID),
        "students": [],
        "teachers": [],
        "atomic": True,
        "_staging": {
            "tenantId": TENANT_ID,
            "jobId": job_id,
            "rows": count,
            "digest": digest,
        },
    }
    expanded = staging.expand_staging_marker(source)
    assert expanded is source
    assert "_staging" not in expanded
    assert isinstance(expanded["students"], staging.StagingRowSequence)
    assert not isinstance(expanded["students"], list)
    assert [row["studentNo"] for row in expanded["students"]] == [
        "S0001", "S0002", "S0003", "S0004"
    ]
