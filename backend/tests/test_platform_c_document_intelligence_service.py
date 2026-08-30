from __future__ import annotations

import hashlib
import json
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.core.context import set_tenant
from app.core.exceptions import AppException
from app.models.file import FileObject
from app.modules.platform.document_lifecycle import document_intelligence_service as service
from app.modules.platform.document_lifecycle.models import DocumentCompareResult


class _Backend:
    def __init__(self, path):
        self.path = path
        self.calls = 0

    def fetch_local(self, _key):
        self.calls += 1
        return self.path


def test_extracted_body_identity_must_match_persisted_artifact() -> None:
    row = SimpleNamespace(
        source_file_version_id=21, source_sha256="d" * 64,
        extractor_code="SAFE_TEXT_LAYER", extractor_version="PARAGRAPH_PAGE_V1",
    )
    artifact = {
        "contract": "PLAT_C_EXTRACTED_ARTIFACT_V1",
        "extractorCode": "SAFE_TEXT_LAYER", "extractorVersion": "PARAGRAPH_PAGE_V1",
        "source": {"fileVersionId": "21", "sourceSha256": "d" * 64},
        "document": {"blocks": [{"paragraph": 1, "text": "alpha"}]},
    }
    assert service._validated_extracted_blocks(artifact, row)[0]["text"] == "alpha"
    with pytest.raises(AppException):
        service._validated_extracted_blocks({
            **artifact,
            "source": {"fileVersionId": "22", "sourceSha256": "e" * 64},
        }, row)


def test_compare_result_reauthorizes_both_sources_before_reading_body(monkeypatch, tmp_path) -> None:
    artifact = {
        "contract": "PLAT_C_DOCUMENT_COMPARE_ARTIFACT_V1",
        "algorithmCode": "PARAGRAPH_PAGE_V1", "algorithmVersion": "1.0.0",
        "left": {"fileVersionId": "11", "sourceSha256": "a" * 64},
        "right": {"fileVersionId": "12", "sourceSha256": "b" * 64},
        "changes": [
            {"status": "MODIFIED", "left": {"paragraph": 1}, "right": {"paragraph": 1}},
            {"status": "ADDED", "left": None, "right": {"paragraph": 2}},
        ],
    }
    body = json.dumps(artifact, separators=(",", ":")).encode()
    digest = hashlib.sha256(body).hexdigest()
    path = tmp_path / "compare.txt"
    path.write_bytes(body)
    backend = _Backend(path)
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    FileObject.__table__.create(engine)
    DocumentCompareResult.__table__.create(engine)
    with Session(engine) as db:
        generated = FileObject(
            tenant_id=101, file_key="compare.txt", file_name="compare.txt", ext="txt",
            mime_type="text/plain", size_bytes=len(body), sha256=digest,
            biz_type="DOCUMENT_DERIVATIVE", visibility="PRIVATE",
            security_level="SENSITIVE", status="AVAILABLE", storage_backend="local",
            storage_zone="ACTIVE", upload_source="SYSTEM", scan_required=False,
            scan_status="NOT_REQUIRED",
        )
        db.add(generated)
        db.flush()
        result = DocumentCompareResult(
            tenant_id=101, left_file_version_id=11, left_source_sha256="a" * 64,
            right_file_version_id=12, right_source_sha256="b" * 64,
            algorithm_code="PARAGRAPH_PAGE_V1", algorithm_version="1.0.0",
            generated_file_object_id=generated.id, diff_sha256=digest,
            summary_json={"added": 1, "modified": 1}, status="SUCCEEDED",
            sensitivity_level="SENSITIVE", legal_hold=False,
        )
        db.add(result)
        db.commit()
        result_id = int(result.id)

        auth_calls = []
        monkeypatch.setattr(service, "get_backend", lambda: backend)
        monkeypatch.setattr(
            service,
            "authorize_compare_result_read",
            lambda **kwargs: auth_calls.append(kwargs),
        )
        set_tenant(101)
        view = service.compare_result_view(
            db, result_id=result_id, user={"userId": "7"}, offset=0, limit=1,
        )
        assert view["changes"][0]["status"] == "MODIFIED"
        assert view["nextOffset"] == 1
        assert auth_calls[0]["left_file_version_id"] == 11
        assert auth_calls[0]["right_file_version_id"] == 12
        assert backend.calls == 1

        def revoked(**_kwargs):
            raise AppException("DATA_NOT_FOUND", "revoked", http_status=404)

        monkeypatch.setattr(service, "authorize_compare_result_read", revoked)
        with pytest.raises(AppException):
            service.compare_result_view(db, result_id=result_id, user={"userId": "7"})
        assert backend.calls == 1

        monkeypatch.setattr(
            service,
            "authorize_compare_result_read",
            lambda **kwargs: auth_calls.append(kwargs),
        )
        forged = json.dumps({
            **artifact,
            "left": {"fileVersionId": "999", "sourceSha256": "c" * 64},
        }, separators=(",", ":")).encode()
        forged_digest = hashlib.sha256(forged).hexdigest()
        path.write_bytes(forged)
        generated.sha256 = forged_digest
        result.diff_sha256 = forged_digest
        db.flush()
        with pytest.raises(AppException):
            service.compare_result_view(db, result_id=result_id, user={"userId": "7"})
    set_tenant(None)
    engine.dispose()
