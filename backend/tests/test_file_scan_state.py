from __future__ import annotations

import pytest

from app.core.exceptions import AppException
from app.models.base import Base
from app.services import file_scan_service, file_service
from app.services.file_content_security import is_scan_required_for_upload
from app.services.file_scan_constants import SCAN_NOT_REQUIRED, SCAN_PENDING


def test_file_security_models_are_registered() -> None:
    assert {
        "t_file_object",
        "t_file_scan_record",
        "t_file_upload_session",
        "t_file_job",
    }.issubset(Base.metadata.tables)


def test_high_risk_upload_classification() -> None:
    for ext in ("doc", "docx", "xls", "xlsx", "ppt", "pptx", "zip", "txt", "csv"):
        assert is_scan_required_for_upload(ext) is True
    for ext in ("pdf", "png", "jpg", "jpeg", "gif"):
        assert is_scan_required_for_upload(ext) is False


def test_business_gate_fails_closed_for_memory_quarantine(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(file_scan_service, "db_enabled", lambda: False)
    file_id = "mem-stage1-pending"
    file_service._MEM_REGISTRY[file_id] = {
        "fileId": file_id,
        "status": "QUARANTINED",
        "scanStatus": SCAN_PENDING,
    }
    try:
        with pytest.raises(AppException) as caught:
            file_scan_service.assert_file_ready_for_business(file_id)
        assert caught.value.code == "FILE_NOT_READY"
        assert caught.value.http_status == 409
    finally:
        file_service._MEM_REGISTRY.pop(file_id, None)


def test_business_gate_allows_memory_ready_file(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(file_scan_service, "db_enabled", lambda: False)
    file_id = "mem-stage1-ready"
    file_service._MEM_REGISTRY[file_id] = {
        "fileId": file_id,
        "status": "AVAILABLE",
        "scanStatus": SCAN_NOT_REQUIRED,
    }
    try:
        result = file_scan_service.assert_file_ready_for_business(file_id)
        assert result["fileId"] == file_id
    finally:
        file_service._MEM_REGISTRY.pop(file_id, None)
