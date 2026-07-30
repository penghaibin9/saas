from __future__ import annotations

import inspect

import pytest
from pydantic import ValidationError

from app.modules.academic_affairs.routers.academic_file_exchange_router import ConfirmRequest, router
from app.modules.academic_affairs.services import academic_file_exchange_service as exchange
from app.services import data_exchange_confirm_service as confirm_service


def test_academic_confirm_contract_forbids_frontend_rows():
    assert ConfirmRequest(expectedVersion=2).expectedVersion == 2
    with pytest.raises(ValidationError):
        ConfirmRequest(expectedVersion=2, rows=[{"studentNo": "S001"}])
    with pytest.raises(ValidationError):
        ConfirmRequest(expectedVersion=2, batchNo="legacy")


def test_academic_exchange_routes_are_registered_as_job_contracts():
    signatures = {
        (route.path, frozenset((route.methods or set()) - {"HEAD", "OPTIONS"}))
        for route in router.routes
    }
    assert ("/academic-affairs/file-exchange/roster/import-jobs", frozenset({"POST"})) in signatures
    assert ("/academic-affairs/file-exchange/imports/{job_id}/confirm", frozenset({"POST"})) in signatures
    assert ("/academic-affairs/file-exchange/roster/export-jobs", frozenset({"POST"})) in signatures
    assert ("/academic-affairs/file-exchange/exports/{job_id}/download-ticket", frozenset({"POST"})) in signatures
    assert ("/academic-affairs/file-exchange/exports/{job_id}/revoke", frozenset({"POST"})) in signatures


def test_authoritative_import_does_not_persist_frontend_rows_snapshot():
    source = inspect.getsource(exchange.create_roster_import_job)
    assert '"authority": "SOURCE_FILE_OBJECT"' in source
    assert '"rows": rows' not in source
    assert "rowDigest" in source
    confirm_source = inspect.getsource(exchange.confirm_roster_import)
    assert "_source_file_bytes" in confirm_source
    assert "roster_import_read(content)" in confirm_source


def test_excel_dispatch_has_explicit_academic_roster_adapter():
    source = inspect.getsource(confirm_service.confirm_import_job)
    assert 'import_type == "ACADEMIC_ROSTER"' in source
    assert "confirm_roster_import" in source
    assert "assert_file_ready_for_business" in source


def test_academic_export_is_file_object_and_job_not_blob_contract():
    source = inspect.getsource(exchange.create_roster_export_job)
    assert "jobs._write_generated_file" in source
    assert "ExportJob(" in source
    assert 'status="SUCCEEDED"' in source
    assert "expires_at=" in source
