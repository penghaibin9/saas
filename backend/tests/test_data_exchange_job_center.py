from __future__ import annotations

from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.api.v1.data_exchange import ConfirmImportRequest
from app.models.data_exchange import ExportJob, ImportJob, ImportRowError
from app.services import data_exchange_job_service as jobs


def test_confirm_request_forbids_frontend_rows_and_batch_number():
    request = ConfirmImportRequest(expectedVersion=3)
    assert request.expectedVersion == 3

    with pytest.raises(ValidationError):
        ConfirmImportRequest(expectedVersion=3, rows=[{"studentNo": "S001"}])

    with pytest.raises(ValidationError):
        ConfirmImportRequest(expectedVersion=3, batchNo="LEGACY-BATCH")


def test_stage3_models_use_frozen_table_names():
    assert ImportJob.__tablename__ == "t_import_job"
    assert ImportRowError.__tablename__ == "t_import_row_error"
    assert ExportJob.__tablename__ == "t_export_job"
    assert {column.name for column in ImportJob.__table__.columns} >= {
        "source_file_id", "adapter_type", "adapter_ref", "lease_token",
        "error_receipt_file_id", "credential_receipt_file_id", "version",
    }
    assert {column.name for column in ExportJob.__table__.columns} >= {
        "file_object_id", "expires_at", "downloaded_count", "revoked_at", "version",
    }


def test_import_projection_is_refresh_safe_and_versioned():
    row = SimpleNamespace(
        id=12,
        module_code="SYSTEM",
        import_type="IDENTITY_STUDENT",
        source_file_id=66,
        adapter_type=jobs.IMPORT_ADAPTER_IDENTITY,
        adapter_ref="IDIMP-1",
        template_version="v1",
        status="VALIDATED",
        total_rows=10,
        valid_rows=9,
        invalid_rows=1,
        confirmed_rows=0,
        error_receipt_file_id=70,
        credential_receipt_file_id=None,
        expires_at=None,
        confirmed_at=None,
        operator_name="系统管理员",
        result_json=None,
        error_message=None,
        version=4,
        created_at=None,
        updated_at=None,
    )
    data = jobs._import_row(row)
    assert data["id"] == "12"
    assert data["sourceFileId"] == "66"
    assert data["errorReceiptFileId"] == "70"
    assert data["version"] == 4
    assert data["status"] == "VALIDATED"


def test_export_projection_marks_expired_output_unavailable(monkeypatch):
    now = jobs._now()
    row = SimpleNamespace(
        id=21,
        module_code="SYSTEM",
        export_type="INITIAL_CREDENTIAL_RECEIPT",
        purpose="初始账号凭据",
        status="SUCCEEDED",
        progress=100,
        row_count=3,
        file_object_id=88,
        expires_at=now,
        downloaded_count=0,
        revoked_at=None,
        revoke_reason=None,
        error_message=None,
        version=2,
        created_at=None,
        updated_at=None,
    )
    assert jobs._export_row(row)["status"] == "EXPIRED"
