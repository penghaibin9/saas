from datetime import datetime, timedelta

import pytest

from app.core.exceptions import AppException
from app.services.entitlement_reconciliation_service import reconcile_snapshot
from app.services.file_storage_cleanup_service import _candidate_snapshot


def test_governance_output_contract_never_exposes_object_key_or_filename(monkeypatch):
    # Static contract protects against accidental return of the private internal
    # delete key from the new bound preview path.
    source = open("app/services/file_storage_cleanup_service.py", encoding="utf-8").read()
    block = source.split("def _candidate_snapshot", 1)[1].split("def create_cleanup_preview", 1)[0]
    assert '"objectKey"' not in block
    assert '"fileName"' not in block


def test_cleanup_api_requires_server_bound_preview_for_execution():
    source = open("app/api/v1/file_governance.py", encoding="utf-8").read()
    assert "CLEANUP_PREVIEW_REQUIRED" in source
    assert "execute_cleanup_preview" in source
    assert "candidateHash" in source
    assert "previewId" in source


def test_school_quota_over_commercial_limit_is_p1_reconciliation_error():
    result = reconcile_snapshot({
        "commercialStorageLimitBytes": 20,
        "schoolGovernanceQuotaBytes": 30,
        "fileObjectBytes": 1,
        "heldReservationBytes": 1,
    })
    assert result["healthy"] is False
    assert result["violations"][0]["code"] == "SCHOOL_QUOTA_EXCEEDS_COMMERCIAL"
