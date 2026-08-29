from __future__ import annotations

import threading
import time
from datetime import datetime, timedelta

import pytest
from sqlalchemy import func, select

from app.core.context import get_tenant, set_tenant
from app.core.exceptions import AppException
from app.models.file import ArchiveManifest, ArchiveManifestItem, FileBinding, FileJob, FileObject
from app.models.platform_integrity import IntegrityException
from app.modules.platform_integrity.file_job_service import (
    FROZEN_PACKAGE_JOB_TYPE,
    claim_next_frozen_package_job,
    enqueue_frozen_package,
    run_claimed_frozen_package_job,
)
from app.modules.graduation.materials.frozen_package_projection import _artifact_view
from app.modules.platform_integrity.frozen_package_service import build_frozen_package
from app.modules.platform_integrity.integrity_service import (
    DetectorPage,
    IntegrityFinding,
    record_detector_page,
    recheck_integrity_exception,
    scan_file_binding_page,
    stable_fingerprint,
)
from app.modules.platform_integrity.manifest_digest import (
    PLATFORM_BUSINESS_SNAPSHOT,
    platform_manifest_digest,
)
from app.modules.platform_integrity.snapshot_service import create_business_snapshot
from app.services.db_service import session


TENANT_A = 970001
TENANT_B = 970002


def _tenant(value: int) -> None:
    set_tenant({"tenantId": str(value), "tenantCode": f"plat-a-{value}"})


def _seed_manifest() -> int:
    with session() as db:
        manifest = ArchiveManifest(
            tenant_id=TENANT_A,
            module_code="GRADUATION",
            archive_type="STUDENT_ARCHIVE",
            target_type="GD_STUDENT",
            target_id="88001",
            revision=1,
            status="FROZEN",
            rule_version="GD:V1",
            manifest_sha256=None,
            frozen_at=datetime.utcnow(),
        )
        db.add(manifest)
        db.flush()
        snapshot = create_business_snapshot(
            db,
            module_code="GRADUATION",
            target_type="GD_STUDENT",
            target_id="88001",
            revision=1,
            payload={
                "schemaVersion": "PLATFORM_BUSINESS_SNAPSHOT_V1",
                "moduleCode": "GRADUATION",
                "targetType": "GD_STUDENT",
                "targetId": "88001",
                "identity": {"studentId": "99001", "studentNo": "S99001", "displayName": "冻结测试"},
                "scope": {"batchId": "1", "collegeId": "2", "classId": "3"},
                "display": {"archiveLabel": "毕业设计归档", "safePackageBaseName": "S99001-r1"},
                "frozenFacts": {"topicTitle": "冻结题目"},
                "sourceVersions": {"graduationStudent": 1},
                "sensitivityLevel": "PERSONAL",
                "frozenAt": "2026-08-29T00:00:00.000000Z",
            },
            user={"userId": "7001", "realName": "PLAT-A MySQL"},
            subject_type="STUDENT",
            subject_id="99001",
            student_id=99001,
            college_id=2,
            class_id=3,
        )
        item = ArchiveManifestItem(
            tenant_id=TENANT_A,
            manifest_id=int(manifest.id),
            material_code=PLATFORM_BUSINESS_SNAPSHOT,
            asset_id=snapshot.asset_id,
            version_id=snapshot.version_id,
            file_object_id=snapshot.file_object_id,
            file_name_snapshot=snapshot.file_name,
            size_snapshot=snapshot.size_bytes,
            sha256_snapshot=snapshot.sha256,
            review_status="APPROVED",
            scan_result="NOT_REQUIRED",
            uploader_snapshot="PLAT-A MySQL",
            submitted_at_snapshot=manifest.frozen_at,
            sort_no=1,
        )
        db.add(item)
        db.flush()
        manifest.manifest_sha256 = platform_manifest_digest(manifest, [item])
        db.commit()
        return int(manifest.id)


def test_mysql_file_job_lease_artifact_idempotency_and_tenant_fail_closed(db_mode, tmp_path, monkeypatch):
    from app.core.config import settings
    from app.services.storage import get_backend, reset_backend

    previous = get_tenant()
    previous_upload_dir = settings.UPLOAD_DIR
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(tmp_path / "plat-a-uploads"))
    reset_backend()
    try:
        _tenant(TENANT_A)
        manifest_id = _seed_manifest()
        with session() as db:
            source_item = db.scalars(select(ArchiveManifestItem).where(
                ArchiveManifestItem.tenant_id == TENANT_A,
                ArchiveManifestItem.manifest_id == manifest_id,
            )).one()
            source_object = db.get(FileObject, int(source_item.file_object_id))
            source_path = get_backend().fetch_local(str(source_object.object_key or source_object.file_key))
            assert source_path is not None
            original_source_bytes = source_path.read_bytes()
            original_source_size = int(source_object.size_bytes or 0)
            source_object.size_bytes = original_source_size + 1
            db.commit()
        with pytest.raises(AppException) as size_drift:
            build_frozen_package(manifest_id=manifest_id, profile_code="STANDARD_V1")
        assert size_drift.value.code == "FROZEN_MANIFEST_ITEM_DRIFT"
        with session() as db:
            source_object = db.get(FileObject, int(source_item.file_object_id))
            source_object.size_bytes = original_source_size
            db.commit()
        source_path.write_bytes(original_source_bytes + b"drift")
        with pytest.raises(AppException) as sha_drift:
            build_frozen_package(manifest_id=manifest_id, profile_code="STANDARD_V1")
        assert sha_drift.value.code == "FROZEN_MANIFEST_ITEM_DRIFT"
        source_path.write_bytes(original_source_bytes)

        build_barrier = threading.Barrier(2)
        build_results: list[dict] = []
        build_errors: list[Exception] = []

        def build_once() -> None:
            try:
                _tenant(TENANT_A)
                build_barrier.wait(timeout=5)
                build_results.append(build_frozen_package(
                    manifest_id=manifest_id,
                    profile_code="STANDARD_V1",
                ).as_dict())
            except Exception as exc:
                build_errors.append(exc)
            finally:
                set_tenant(None)

        build_threads = [threading.Thread(target=build_once) for _ in range(2)]
        for thread in build_threads:
            thread.start()
        for thread in build_threads:
            thread.join(timeout=15)
        assert not any(thread.is_alive() for thread in build_threads)
        assert build_errors == []
        assert len(build_results) == 2
        assert sorted(result["reused"] for result in build_results) == [False, True]
        assert len({result["artifact"]["fileId"] for result in build_results}) == 1
        prebuilt_file_id = build_results[0]["artifact"]["fileId"]

        request_barrier = threading.Barrier(2)
        request_ids: list[int] = []
        request_errors: list[Exception] = []

        def request_once() -> None:
            try:
                _tenant(TENANT_A)
                request_barrier.wait(timeout=5)
                with session() as request_db:
                    requested = enqueue_frozen_package(request_db, manifest_id=manifest_id)
                    request_id = int(requested.id)
                    request_db.commit()
                    request_ids.append(request_id)
            except Exception as exc:
                request_errors.append(exc)
            finally:
                set_tenant(None)

        request_threads = [threading.Thread(target=request_once) for _ in range(2)]
        for thread in request_threads:
            thread.start()
        for thread in request_threads:
            thread.join(timeout=10)
        assert not any(thread.is_alive() for thread in request_threads)
        assert request_errors == []
        assert len(request_ids) == 2
        assert len(set(request_ids)) == 1
        _tenant(TENANT_A)
        with session() as db:
            first = enqueue_frozen_package(db, manifest_id=manifest_id)
            second = enqueue_frozen_package(db, manifest_id=manifest_id)
            assert int(first.id) == int(second.id)
            assert int(first.id) == request_ids[0]
            first.status = "RUNNING"
            first.attempts = 1
            first.available_at = datetime.utcnow() - timedelta(minutes=20)
            first.locked_at = datetime.utcnow() - timedelta(minutes=20)
            first.locked_by = "dead-worker"
            db.commit()
            job_id = int(first.id)

        _tenant(TENANT_B)
        assert claim_next_frozen_package_job(worker_id="tenant-b-worker") is None
        with pytest.raises(AppException) as cross_tenant:
            build_frozen_package(manifest_id=manifest_id, profile_code="STANDARD_V1")
        assert cross_tenant.value.code == "DATA_NOT_FOUND"

        _tenant(TENANT_A)
        claimed = claim_next_frozen_package_job(worker_id="plat-a-worker", stale_after_seconds=600)
        assert claimed == job_id
        result = run_claimed_frozen_package_job(job_id=job_id, worker_id="plat-a-worker")
        artifact = result["artifact"]
        assert artifact["tenantId"] == str(TENANT_A)
        assert artifact["packageKind"] == "FROZEN_MANIFEST_PACKAGE"
        assert artifact["sourceType"] == "ARCHIVE_MANIFEST"
        assert artifact["sourceId"] == str(manifest_id)
        assert artifact["fileId"] == artifact["fileObjectId"]
        assert artifact["fileId"] == prebuilt_file_id
        assert not {"url", "downloadUrl", "fileKey", "objectKey"}.intersection(artifact)
        with session() as db:
            manifest = db.get(ArchiveManifest, manifest_id)
            artifact_object = db.get(FileObject, int(artifact["fileId"]))
            client_projection = _artifact_view(manifest, artifact_object, can_download=True)
        for field in (
            "tenantId", "packageKind", "sourceType", "sourceId", "sourceVersion",
            "fileId", "fileObjectId", "sha256", "resolverCode", "profileCode",
        ):
            assert client_projection[field] == artifact[field]

        rebuilt = build_frozen_package(manifest_id=manifest_id, profile_code="STANDARD_V1").as_dict()
        assert rebuilt["reused"] is True
        assert rebuilt["artifact"]["fileId"] == artifact["fileId"]
        assert rebuilt["artifact"]["sha256"] == artifact["sha256"]
        with session() as db:
            job = db.get(FileJob, job_id)
            assert job.status == "SUCCEEDED"
            assert int(job.attempts) == 2
            assert db.scalar(select(func.count()).select_from(FileJob).where(
                FileJob.tenant_id == TENANT_A,
                FileJob.job_type == FROZEN_PACKAGE_JOB_TYPE,
            )) == 1
            file_obj = db.get(FileObject, int(artifact["fileId"]))
            original_artifact_path = get_backend().fetch_local(str(file_obj.object_key or file_obj.file_key))
            assert original_artifact_path is not None
            original_artifact_bytes = original_artifact_path.read_bytes()
            file_obj.is_deleted = True
            db.commit()
        forced = build_frozen_package(manifest_id=manifest_id, profile_code="STANDARD_V1").as_dict()
        assert forced["reused"] is False
        assert forced["artifact"]["fileId"] != artifact["fileId"]
        assert forced["artifact"]["sha256"] == artifact["sha256"]
        with session() as db:
            forced_object = db.get(FileObject, int(forced["artifact"]["fileId"]))
            forced_path = get_backend().fetch_local(str(forced_object.object_key or forced_object.file_key))
            assert forced_path is not None
            assert forced_path.read_bytes() == original_artifact_bytes
            storage_key = str(forced_object.object_key or forced_object.file_key)
        get_backend().delete(storage_key)
        with pytest.raises(AppException) as missing:
            build_frozen_package(manifest_id=manifest_id, profile_code="STANDARD_V1")
        assert missing.value.code == "PACKAGED_FILE_MISSING"
    finally:
        set_tenant(previous)
        settings.UPLOAD_DIR = previous_upload_dir
        reset_backend()


def test_mysql_exception_fingerprint_concurrent_upsert_is_single_row(db_mode):
    previous = get_tenant()
    finding = IntegrityFinding(
        exception_type="FILE_BINDING_BROKEN_REFERENCE",
        detector_code="FILE_BINDING_REFERENCE_V1",
        module_code="GRADUATION",
        subject_type="FILE_BINDING",
        subject_id="771",
        file_id=991,
        title="broken binding",
        message="missing object",
        severity="MEDIUM",
    )
    page = DetectorPage(
        detector_code="FILE_BINDING_REFERENCE_V1",
        status="CONCLUSIVE",
        findings=(finding,),
        next_cursor=None,
        scanned=1,
    )
    barrier = threading.Barrier(2)
    errors: list[Exception] = []

    def write_once() -> None:
        try:
            _tenant(TENANT_A)
            barrier.wait(timeout=5)
            with session() as db:
                record_detector_page(db, page)
                db.commit()
        except Exception as exc:  # surfaced below; never masked
            errors.append(exc)
        finally:
            set_tenant(None)

    try:
        threads = [threading.Thread(target=write_once) for _ in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=10)
        assert not any(thread.is_alive() for thread in threads)
        assert errors == []
        _tenant(TENANT_A)
        with session() as db:
            rows = list(db.scalars(select(IntegrityException).where(
                IntegrityException.tenant_id == TENANT_A,
                IntegrityException.fingerprint == stable_fingerprint(finding),
            )).all())
            assert len(rows) == 1
            assert int(rows[0].occurrence_count) == 2
            assert int(rows[0].version) == 1

        outcomes: list[str] = []
        recheck_barrier = threading.Barrier(2)

        def recheck_once() -> None:
            try:
                _tenant(TENANT_A)
                recheck_barrier.wait(timeout=5)
                recheck_integrity_exception(
                    int(rows[0].id),
                    expected_version=1,
                    actor_id=7001,
                    timeout_ms=500,
                )
                outcomes.append("SUCCESS")
            except AppException as exc:
                outcomes.append(exc.code)
            finally:
                set_tenant(None)

        recheck_threads = [threading.Thread(target=recheck_once) for _ in range(2)]
        for thread in recheck_threads:
            thread.start()
        for thread in recheck_threads:
            thread.join(timeout=10)
        assert not any(thread.is_alive() for thread in recheck_threads)
        assert sorted(outcomes) == ["SUCCESS", "VERSION_CONFLICT"]
    finally:
        set_tenant(previous)


def test_mysql_file_binding_detector_pages_twenty_thousand_rows_without_unbounded_read(db_mode):
    previous = get_tenant()
    try:
        _tenant(TENANT_A)
        with session() as db:
            statement = FileBinding.__table__.insert()
            for offset in range(0, 20_000, 1_000):
                db.execute(statement, [{
                    "tenant_id": TENANT_A,
                    "file_id": 1_000_000 + index,
                    "biz_type": "FROZEN_EVIDENCE_PACKAGE",
                    "biz_id": str(index),
                    "relation_type": "ATTACHMENT",
                    "subject_type": "BUSINESS_OBJECT",
                    "version_no": 1,
                    "is_current": True,
                    "status": "ACTIVE",
                    "module_code": "GRADUATION",
                    "student_id": 2_000_000 + index,
                } for index in range(offset, offset + 1_000)])
            db.commit()

        started = time.monotonic()
        cursor = 0
        scanned = 0
        findings = 0
        pages = 0
        with session() as db:
            while True:
                page = scan_file_binding_page(
                    db,
                    tenant_id=TENANT_A,
                    after_id=cursor,
                    limit=200,
                )
                assert page.status == "CONCLUSIVE"
                assert page.scanned <= 200
                scanned += page.scanned
                findings += len(page.findings)
                pages += 1
                if page.next_cursor is None:
                    break
                cursor = int(page.next_cursor)
        elapsed = time.monotonic() - started
        assert scanned == 20_000
        assert findings == 20_000
        assert pages == 101
        assert elapsed < 60
    finally:
        set_tenant(previous)
