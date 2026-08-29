from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.core.context import set_tenant
from app.core.exceptions import AppException
from app.models.file import FileAsset, FileJob, FileObject, FileVersion
from app.modules.platform.document_lifecycle import derived_worker as worker
from app.modules.platform.document_lifecycle.models import DocumentCompareResult, FileDerivedArtifact


class _Backend:
    def __init__(self, path: Path):
        self.path = path

    def fetch_local(self, _key: str):
        return self.path


def _schema(engine) -> None:
    for model in (FileObject, FileAsset, FileVersion, FileJob, FileDerivedArtifact):
        model.__table__.create(engine)


def _seed_source(db: Session, *, source: bytes = b"alpha\n\nbeta") -> dict:
    sha = hashlib.sha256(source).hexdigest()
    db.add(FileObject(
        id=10, tenant_id=101, file_key="source.txt", file_name="source.txt",
        ext="txt", mime_type="text/plain", size_bytes=len(source), sha256=sha,
        biz_type="GRADUATION_MATERIAL", biz_id="900", visibility="PRIVATE",
        security_level="SENSITIVE", status="AVAILABLE", storage_backend="local",
        storage_zone="ACTIVE", upload_source="USER", scan_required=False,
        scan_status="NOT_REQUIRED", legal_hold=True,
    ))
    db.add(FileAsset(
        id=20, tenant_id=101, asset_code="A20", title="Source",
        category_code="DOCUMENT", owner_type="BUSINESS_OBJECT",
        current_version_id=30, lifecycle_status="ACTIVE", version_count=1,
        sensitivity_level="SENSITIVE",
    ))
    db.add(FileVersion(
        id=30, tenant_id=101, asset_id=20, file_object_id=10, version_no=1,
        source_channel="TEST", status="READY", is_current=True,
    ))
    db.flush()
    return {
        "file_version_id": 30,
        "file_object_id": 10,
        "asset_id": 20,
        "source_sha256": sha,
        "mime_type": "text/plain",
        "ext": "txt",
        "size_bytes": len(source),
        "sensitivity_level": "SENSITIVE",
    }


def test_worker_rechecks_pinned_relation_sha_size_and_storage(monkeypatch, tmp_path) -> None:
    source = b"alpha\n\nbeta"
    source_path = tmp_path / "source.txt"
    source_path.write_bytes(source)
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    _schema(engine)
    with Session(engine) as db:
        payload = _seed_source(db, source=source)
        db.commit()
        monkeypatch.setattr(worker, "get_backend", lambda: _Backend(source_path))
        loaded = worker.load_pinned_source(db, tenant_id=101, payload=payload)
        assert loaded.data == source
        assert loaded.legal_hold is True
        assert loaded.sensitivity_level == "SENSITIVE"

        with pytest.raises(AppException) as exc:
            worker.load_pinned_source(
                db, tenant_id=101, payload={**payload, "source_sha256": "0" * 64},
            )
        assert exc.value.code == "DOCUMENT_SOURCE_CHANGED"
    engine.dispose()


def test_extract_worker_stores_body_in_file_object_and_only_summary_in_job(
        monkeypatch, tmp_path) -> None:
    source = b"alpha\n\nbeta"
    source_path = tmp_path / "source.txt"
    source_path.write_bytes(source)
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    _schema(engine)
    sessions = sessionmaker(engine, expire_on_commit=False)
    with sessions() as db:
        pinned = _seed_source(db, source=source)
        job = FileJob(
            id=40, tenant_id=101, job_type="DOCUMENT_EXTRACT", file_id=10,
            dedupe_key="worker-test", status="RUNNING", attempts=1, max_attempts=3,
            payload_json={
                "contract": "PLAT_C_DOCUMENT_EXTRACT_V1",
                "source": pinned,
                "derivativeKind": "EXTRACTED_TEXT",
                "extractorCode": "SAFE_TEXT_LAYER",
                "extractorVersion": "PARAGRAPH_PAGE_V1",
            },
        )
        db.add(job)
        db.commit()

    captured: dict = {}

    def artifact_writer(db, *, data, filename, sensitivity):
        captured.update({"data": data, "filename": filename, "sensitivity": sensitivity})
        row = FileObject(
            tenant_id=101, file_key="derived.txt", file_name=filename,
            ext="txt", mime_type="text/plain", size_bytes=len(data),
            sha256=hashlib.sha256(data).hexdigest(), biz_type="DOCUMENT_DERIVATIVE",
            biz_id=None, visibility="PRIVATE", security_level=sensitivity,
            status="AVAILABLE", storage_backend="local", storage_zone="ACTIVE",
            upload_source="SYSTEM", scan_required=False, scan_status="NOT_REQUIRED",
        )
        db.add(row)
        db.flush()
        return row

    monkeypatch.setattr(worker, "get_sessionmaker", lambda: sessions)
    monkeypatch.setattr(worker, "get_backend", lambda: _Backend(source_path))
    set_tenant(None)
    result = worker.complete_job(40, artifact_writer=artifact_writer)
    assert result["jobStatus"] == "SUCCEEDED"
    assert b'"document"' in captured["data"]
    assert captured["sensitivity"] == "SENSITIVE"

    with sessions() as db:
        job = db.get(FileJob, 40)
        artifact = db.scalars(select(FileDerivedArtifact)).one()
        assert job.status == "SUCCEEDED"
        assert "document" not in str(job.result_json)
        assert artifact.generated_file_object_id is not None
        assert artifact.content_sha256 == hashlib.sha256(captured["data"]).hexdigest()
        assert artifact.legal_hold is True
    engine.dispose()


def test_compare_worker_stores_diff_in_file_object_and_inherits_stricter_controls(
        monkeypatch) -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    FileObject.__table__.create(engine)
    FileJob.__table__.create(engine)
    DocumentCompareResult.__table__.create(engine)
    left_retention = datetime(2027, 1, 1)
    right_retention = left_retention + timedelta(days=30)
    sources = iter((
        worker.WorkerSource(
            tenant_id=101, asset_id=20, file_version_id=30, file_object_id=10,
            source_sha256="a" * 64, mime_type="text/plain", ext="txt",
            size_bytes=5, sensitivity_level="PERSONAL", retention_until=left_retention,
            legal_hold=False, data=b"alpha",
        ),
        worker.WorkerSource(
            tenant_id=101, asset_id=21, file_version_id=31, file_object_id=11,
            source_sha256="b" * 64, mime_type="text/plain", ext="txt",
            size_bytes=4, sensitivity_level="HIGHLY_SENSITIVE", retention_until=right_retention,
            legal_hold=True, data=b"beta",
        ),
    ))
    monkeypatch.setattr(worker, "load_pinned_source", lambda *_a, **_k: next(sources))
    captured: dict = {}

    def artifact_writer(db, *, data, filename, sensitivity):
        captured.update({"data": data, "filename": filename, "sensitivity": sensitivity})
        row = FileObject(
            tenant_id=101, file_key="compare.txt", file_name=filename,
            ext="txt", mime_type="text/plain", size_bytes=len(data),
            sha256=hashlib.sha256(data).hexdigest(), biz_type="DOCUMENT_DERIVATIVE",
            biz_id=None, visibility="PRIVATE", security_level=sensitivity,
            status="AVAILABLE", storage_backend="local", storage_zone="ACTIVE",
            upload_source="SYSTEM", scan_required=False, scan_status="NOT_REQUIRED",
        )
        db.add(row)
        db.flush()
        return row

    with Session(engine) as db:
        job = FileJob(
            id=40, tenant_id=101, job_type="DOCUMENT_COMPARE", file_id=10,
            dedupe_key="compare-worker-test", status="RUNNING", attempts=1, max_attempts=3,
        )
        db.add(job)
        db.flush()
        result = worker._execute_compare(db, job, {
            "contract": "PLAT_C_DOCUMENT_COMPARE_V1",
            "left": {}, "right": {},
            "algorithmCode": "PARAGRAPH_PAGE_V1", "algorithmVersion": "1.0.0",
        }, artifact_writer)
        row = db.scalars(select(DocumentCompareResult)).one()
        stored = json.loads(captured["data"])
        assert stored["changes"]
        assert "changes" not in str(result["summary"])
        assert row.summary_json == result["summary"]
        assert row.algorithm_code == "PARAGRAPH_PAGE_V1"
        assert row.algorithm_version == "1.0.0"
        assert row.sensitivity_level == "HIGHLY_SENSITIVE"
        assert row.retention_until == right_retention
        assert row.legal_hold is True
        assert captured["sensitivity"] == "HIGHLY_SENSITIVE"
    engine.dispose()
