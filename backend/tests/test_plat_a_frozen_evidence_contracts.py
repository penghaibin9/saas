from __future__ import annotations

import hashlib
import time
import zipfile
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.context import (
    current_tenant_id,
    get_current_user_ctx,
    get_tenant,
    set_current_user,
    set_tenant,
)
from app.core.exceptions import AppException
from app.modules.graduation.materials.frozen_package_projection import (
    my_frozen_package,
    teacher_integrity_summary,
)
from app.modules.graduation.materials import frozen_package_projection
from app.modules.graduation.services.graduation_scope_service import can_access_student
from app.modules.platform_integrity.contracts import PackageArtifactRef
from app.modules.platform_integrity.deterministic_package import ArchiveEntry, write_standard_v1
from app.modules.platform_integrity.file_access_resolver import frozen_evidence_package_resolver
from app.modules.platform_integrity.file_job_service import package_job_dedupe_key
from app.modules.platform_integrity.frozen_package_service import frozen_package_artifact_biz_id
from app.models import GraduationStudent
from app.models.file import ArchiveManifest, ArchiveManifestItem, FileJob, FileObject
from app.models.platform_integrity import IntegrityException
from app.workers import frozen_package_worker
from app.modules.platform_integrity.integrity_service import (
    DetectorPage,
    IntegrityFinding,
    run_registered_probe,
    scan_frozen_manifest_page,
    stable_fingerprint,
)
from app.modules.platform_integrity.manifest_digest import (
    PLATFORM_BUSINESS_SNAPSHOT,
    PLATFORM_MANIFEST_DIGEST_V1,
    canonical_manifest_payload,
    platform_manifest_digest,
)
from app.modules.platform_integrity.package_inventory import (
    PRODUCTION_PACKAGE_PATHS,
    UNKNOWN,
    machine_ledger,
)


ROOT = Path(__file__).resolve().parents[2]


def _manifest():
    return SimpleNamespace(
        id=41,
        tenant_id=1001,
        module_code="GRADUATION",
        archive_type="STUDENT_ARCHIVE",
        target_type="GD_STUDENT",
        target_id="3001",
        revision=2,
        rule_version="GD:v7",
        status="FROZEN",
        package_file_id=None,
        updated_at=datetime(2026, 8, 29, 10, 0, 0),
        created_by=9001,
    )


def _item(*, item_id: int, code: str, sort_no: int, version_id: int, sha: str):
    return SimpleNamespace(
        id=item_id,
        material_code=code,
        asset_id=item_id + 100,
        version_id=version_id,
        file_object_id=item_id + 300,
        file_name_snapshot=f"{code}.json",
        size_snapshot=20 + item_id,
        sha256_snapshot=sha,
        review_status="APPROVED",
        scan_result="NOT_REQUIRED",
        uploader_snapshot="冻结时名称",
        submitted_at_snapshot=datetime(2026, 8, 29, 8, 0, item_id),
        sort_no=sort_no,
        updated_at=datetime(2026, 8, 29, 10, 0, 0),
    )


def test_platform_digest_uses_pinned_fields_and_stable_item_order_only():
    manifest = _manifest()
    items = [
        _item(item_id=9, code=PLATFORM_BUSINESS_SNAPSHOT, sort_no=2, version_id=29, sha="b" * 64),
        _item(item_id=8, code="FINAL_PAPER", sort_no=1, version_id=28, sha="a" * 64),
    ]
    digest = platform_manifest_digest(manifest, items)
    assert digest == platform_manifest_digest(manifest, list(reversed(items)))
    manifest.status = "PACKAGED"
    manifest.package_file_id = 777
    manifest.updated_at = datetime(2030, 1, 1)
    manifest.created_by = 42
    assert digest == platform_manifest_digest(manifest, items)
    items[0].sha256_snapshot = "c" * 64
    assert digest != platform_manifest_digest(manifest, items)


def test_platform_digest_payload_declares_schema_and_excludes_live_operational_fields():
    payload = canonical_manifest_payload(
        _manifest(),
        [_item(item_id=1, code=PLATFORM_BUSINESS_SNAPSHOT, sort_no=1, version_id=2, sha="a" * 64)],
    )
    assert payload["digestSchemaVersion"] == PLATFORM_MANIFEST_DIGEST_V1
    serialized = repr(payload)
    for forbidden in ("packageFileId", "status", "updatedAt", "createdBy", "retry"):
        assert forbidden not in serialized


def test_platform_digest_normalizes_datetime_to_mysql_persisted_precision():
    item = _item(item_id=1, code=PLATFORM_BUSINESS_SNAPSHOT, sort_no=1, version_id=2, sha="a" * 64)
    item.submitted_at_snapshot = datetime(2026, 8, 29, 8, 0, 1, 987654)
    before_commit = platform_manifest_digest(_manifest(), [item])
    item.submitted_at_snapshot = datetime(2026, 8, 29, 8, 0, 2, 0)
    assert platform_manifest_digest(_manifest(), [item]) == before_commit
    item.submitted_at_snapshot = datetime(2026, 8, 29, 8, 0, 2, 499999)
    assert platform_manifest_digest(_manifest(), [item]) == before_commit


def test_standard_v1_zip_is_byte_deterministic_and_metadata_is_pinned(tmp_path):
    first_source = tmp_path / "source-a.txt"
    second_source = tmp_path / "source-b.json"
    first_source.write_bytes("冻结材料 A\n".encode("utf-8"))
    second_source.write_bytes(b'{"value":2}\n')
    entries = [
        ArchiveEntry(
            path="evidence/0001_FINAL/final.txt",
            source_path=first_source,
            sha256=hashlib.sha256(first_source.read_bytes()).hexdigest(),
            size_bytes=first_source.stat().st_size,
        ),
        ArchiveEntry(
            path="metadata/platform_business_snapshot.json",
            source_path=second_source,
            sha256=hashlib.sha256(second_source.read_bytes()).hexdigest(),
            size_bytes=second_source.stat().st_size,
        ),
    ]
    output_a = tmp_path / "a.zip"
    output_b = tmp_path / "b.zip"
    result_a = write_standard_v1(output_a, manifest_payload={"manifestId": "41"}, entries=entries)
    result_b = write_standard_v1(output_b, manifest_payload={"manifestId": "41"}, entries=reversed(entries))
    assert result_a == result_b
    assert output_a.read_bytes() == output_b.read_bytes()
    with zipfile.ZipFile(output_a) as archive:
        assert archive.namelist() == [
            "manifest.json",
            "evidence/0001_FINAL/final.txt",
            "metadata/platform_business_snapshot.json",
            "checksums.sha256",
        ]
        for info in archive.infolist():
            assert info.date_time == (1980, 1, 1, 0, 0, 0)
            assert info.compress_type == zipfile.ZIP_DEFLATED
            assert info.flag_bits & 0x800


def test_standard_v1_is_byte_deterministic_above_one_hundred_entries(tmp_path):
    entries = []
    for index in range(120):
        source = tmp_path / f"source-{index:03d}.txt"
        source.write_bytes(f"冻结材料-{index:03d}\n".encode("utf-8"))
        body = source.read_bytes()
        entries.append(ArchiveEntry(
            path=f"evidence/{119 - index:04d}/材料-{index:03d}.txt",
            source_path=source,
            sha256=hashlib.sha256(body).hexdigest(),
            size_bytes=len(body),
        ))
    output_a = tmp_path / "many-a.zip"
    output_b = tmp_path / "many-b.zip"
    result_a = write_standard_v1(output_a, manifest_payload={"manifestId": "many"}, entries=entries)
    result_b = write_standard_v1(output_b, manifest_payload={"manifestId": "many"}, entries=reversed(entries))
    assert result_a == result_b
    assert output_a.read_bytes() == output_b.read_bytes()
    with zipfile.ZipFile(output_a) as archive:
        assert len(archive.namelist()) == 122
        assert archive.namelist()[1:-1] == sorted(archive.namelist()[1:-1])


def test_standard_v1_rejects_duplicate_and_reserved_paths(tmp_path):
    source = tmp_path / "source.txt"
    source.write_bytes(b"frozen")
    entry = ArchiveEntry(
        path="evidence/0001/source.txt",
        source_path=source,
        sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
        size_bytes=source.stat().st_size,
    )
    with pytest.raises(ValueError):
        write_standard_v1(
            tmp_path / "duplicate.zip",
            manifest_payload={"manifestId": "41"},
            entries=[entry, entry],
        )
    with pytest.raises(ValueError):
        write_standard_v1(
            tmp_path / "reserved.zip",
            manifest_payload={"manifestId": "41"},
            entries=[ArchiveEntry(
                path="MANIFEST.JSON",
                source_path=source,
                sha256=entry.sha256,
                size_bytes=entry.size_bytes,
            )],
        )


def test_deep_sha_budget_counts_unreadable_fetch_attempts(monkeypatch):
    manifest = _manifest()
    items = [
        _item(item_id=index, code=f"MATERIAL_{index}", sort_no=index, version_id=100 + index, sha="a" * 64)
        for index in range(1, 7)
    ]
    manifest.manifest_sha256 = platform_manifest_digest(manifest, items)
    versions = [SimpleNamespace(id=item.version_id, file_object_id=item.file_object_id) for item in items]
    objects = [SimpleNamespace(
        id=item.file_object_id,
        size_bytes=item.size_snapshot,
        sha256=item.sha256_snapshot,
        object_key=f"objects/{item.file_object_id}",
        file_key=f"objects/{item.file_object_id}",
    ) for item in items]

    class _Rows:
        def __init__(self, values):
            self.values = values

        def all(self):
            return self.values

    class _Db:
        def __init__(self):
            self.results = iter(([manifest], items, versions, objects, []))

        def scalars(self, _statement):
            return _Rows(next(self.results))

    class _Backend:
        def __init__(self):
            self.fetches = 0

        def exists(self, _key):
            return True

        def fetch_local(self, _key):
            self.fetches += 1
            return None

    backend = _Backend()
    monkeypatch.setattr("app.modules.platform_integrity.integrity_service._tid", lambda: 1001)
    monkeypatch.setattr("app.modules.platform_integrity.integrity_service.get_backend", lambda: backend)
    page = scan_frozen_manifest_page(
        _Db(),
        tenant_id=1001,
        deep_sha=True,
        deep_sha_limit=3,
    )
    assert backend.fetches == 3
    assert page.deep_sha_scanned == 3


def test_artifact_contract_never_exposes_storage_location_or_raw_url():
    value = PackageArtifactRef(
        tenant_id=1001,
        package_kind="FROZEN_MANIFEST_PACKAGE",
        source_type="ARCHIVE_MANIFEST",
        source_id="41",
        source_version="r2:" + "b" * 64,
        file_object_id=91,
        file_name="frozen.zip",
        size_bytes=123,
        sha256="a" * 64,
        created_at=datetime(2026, 8, 29, 10, 30),
        sensitivity_level="PERSONAL",
        resolver_code="FROZEN_EVIDENCE_PACKAGE",
        profile_code="STANDARD_V1",
    ).as_dict()
    assert value["fileId"] == "91"
    assert value["fileObjectId"] == "91"
    assert value["packageKind"] == "FROZEN_MANIFEST_PACKAGE"
    assert value["sourceType"] == "ARCHIVE_MANIFEST"
    assert value["sourceId"] == "41"
    assert value["sourceVersion"].startswith("r2:")
    assert value["resolverCode"] == "FROZEN_EVIDENCE_PACKAGE"
    assert not {"url", "downloadUrl", "fileKey", "objectKey"}.intersection(value)


def test_file_job_dedupe_binds_tenant_manifest_revision_digest_and_profile():
    base = dict(
        tenant_id=1001,
        manifest_id=41,
        revision=2,
        manifest_sha256="a" * 64,
        profile_code="STANDARD_V1",
    )
    key = package_job_dedupe_key(**base)
    assert key == package_job_dedupe_key(**base)
    assert len(key) <= 160
    for field, replacement in (
        ("tenant_id", 1002),
        ("manifest_id", 42),
        ("revision", 3),
        ("manifest_sha256", "b" * 64),
        ("profile_code", "STANDARD_V2"),
    ):
        assert key != package_job_dedupe_key(**{**base, field: replacement})


def test_common_builder_has_a_hard_source_boundary():
    source = (ROOT / "backend/app/modules/platform_integrity/frozen_package_service.py").read_text(encoding="utf-8")
    for forbidden in (
        "StudentProfile",
        "InternshipArchive",
        "GraduationStudent",
        "AcademicArchive",
        "WorkflowInstance",
        "WorkflowTask",
    ):
        assert forbidden not in source


def test_graduation_writer_adds_snapshot_before_computing_new_digest():
    source = (ROOT / "backend/app/modules/graduation/materials/manifest_service.py").read_text(encoding="utf-8")
    writer = source[source.index("def file_archive"):source.index("def batch_file")]
    assert "create_graduation_business_snapshot" in writer
    assert "material_code=PLATFORM_BUSINESS_SNAPSHOT" in writer
    assert writer.index("material_code=PLATFORM_BUSINESS_SNAPSHOT") < writer.index("platform_manifest_digest")
    assert writer.index("db.flush()", writer.index("material_code=PLATFORM_BUSINESS_SNAPSHOT")) < writer.index("platform_manifest_digest")
    assert "manifest_sha256=None" in writer


def test_legacy_active_manifest_retry_returns_before_snapshot_generation():
    source = (ROOT / "backend/app/modules/graduation/materials/manifest_service.py").read_text(encoding="utf-8")
    writer = source[source.index("def file_archive"):source.index("def batch_file")]
    first_existing_return = writer.index("return _manifest_view(db, existing)")
    snapshot_import = writer.index("from .platform_frozen_adapter import create_graduation_business_snapshot")
    assert first_existing_return < snapshot_import


def test_integrity_fingerprint_is_stable_across_volatile_evidence_and_copy_changes():
    finding = IntegrityFinding(
        exception_type="FROZEN_MANIFEST_ITEM_DRIFT",
        detector_code="FROZEN_MANIFEST_V1",
        module_code="GRADUATION",
        subject_type="ARCHIVE_MANIFEST",
        subject_id="41",
        manifest_id=41,
        file_id=91,
        title="first title",
        message="first message",
        evidence={"observedAt": "2026-08-29T01:00:00", "retry": 1},
    )
    changed_copy = IntegrityFinding(
        exception_type=finding.exception_type,
        detector_code=finding.detector_code,
        module_code=finding.module_code,
        subject_type=finding.subject_type,
        subject_id=finding.subject_id,
        manifest_id=finding.manifest_id,
        file_id=finding.file_id,
        title="new title",
        message="new message",
        evidence={"observedAt": "2030-01-01T00:00:00", "retry": 99},
    )
    assert stable_fingerprint(finding) == stable_fingerprint(changed_copy)


def test_unregistered_domain_probe_is_inconclusive_not_a_false_positive(monkeypatch):
    monkeypatch.setattr("app.modules.platform_integrity.integrity_service._tid", lambda: 1001)
    result = run_registered_probe(
        "WORKFLOW_CLOSED_TASK_PENDING",
        tenant_id=1001,
        after_id=0,
        limit=100,
        timeout_ms=500,
    )
    assert result == DetectorPage(
        detector_code="WORKFLOW_CLOSED_TASK_PENDING",
        status="INCONCLUSIVE",
        findings=(),
        next_cursor=None,
        scanned=0,
        error="PROBE_NOT_REGISTERED",
    )


def test_registered_probe_timeout_and_failure_are_isolated(monkeypatch):
    monkeypatch.setattr("app.modules.platform_integrity.integrity_service._tid", lambda: 1001)

    def slow_probe(_request):
        time.sleep(0.25)
        return DetectorPage("WORKFLOW_CLOSED_TASK_PENDING", "CONCLUSIVE", (), None, 0)

    monkeypatch.setattr(
        "app.modules.platform_integrity.integrity_service.get_integrity_probe",
        lambda _code: slow_probe,
    )
    started = time.monotonic()
    page = run_registered_probe(
        "WORKFLOW_CLOSED_TASK_PENDING",
        tenant_id=1001,
        timeout_ms=100,
    )
    assert time.monotonic() - started < 0.22
    assert page.status == "INCONCLUSIVE"
    assert page.error == "PROBE_TIMEOUT"


def test_package_taxonomy_machine_ledger_covers_every_production_writer():
    rows = machine_ledger()
    assert rows
    assert all(row["classification"] != UNKNOWN for row in rows)
    assert any(row["selected_scope"] for row in rows)
    declared_manifest_writers = {
        path for item in PRODUCTION_PACKAGE_PATHS for path in item.manifest_writers
    }
    declared_package_file_writers = {
        path for item in PRODUCTION_PACKAGE_PATHS for path in item.package_file_writers
    }
    actual_manifest_writers = set()
    actual_package_file_writers = set()
    for path in (ROOT / "backend/app").rglob("*.py"):
        relative = path.relative_to(ROOT).as_posix()
        if "/models/" in relative:
            continue
        source = path.read_text(encoding="utf-8")
        if "ArchiveManifest(" in source:
            actual_manifest_writers.add(relative)
        if "package_file_id =" in source:
            actual_package_file_writers.add(relative)
    assert actual_manifest_writers == declared_manifest_writers
    assert actual_package_file_writers == declared_package_file_writers


def test_integrity_detectors_are_bounded_read_models_without_domain_repairs():
    source = (ROOT / "backend/app/modules/platform_integrity/integrity_service.py").read_text(encoding="utf-8")
    for forbidden in (
        "StudentProfile",
        "InternshipArchive",
        "GraduationStudent",
        "AcademicArchive",
        "WorkflowInstance",
        "WorkflowTask",
        "session.delete(",
    ):
        assert forbidden not in source
    assert "MAX_PAGE_SIZE = 200" in source
    assert "MAX_DEEP_SHA_PER_PAGE = 20" in source
    assert ".id > int(after_id or 0)" in source
    assert ".limit(page_size)" in source
    assert 'page.status != "CONCLUSIVE"' in source


def test_integrity_exception_is_the_only_plat_a_table_and_migration_follows_main_head():
    model = (ROOT / "backend/app/models/platform_integrity.py").read_text(encoding="utf-8")
    migration = (ROOT / "backend/alembic/versions/20260829_plat_a_integrity_exception.py").read_text(encoding="utf-8")
    assert model.count("__tablename__") == 1
    assert '__tablename__ = "t_integrity_exception"' in model
    assert 'UniqueConstraint("tenant_id", "fingerprint"' in model
    assert 'down_revision = "20260829_pr236_main_merge"' in migration
    assert migration.count("op.create_table(") == 1


def test_four_client_routes_project_the_same_file_center_artifact_contract():
    api = (ROOT / "backend/app/api/v1/platform_integrity.py").read_text(encoding="utf-8")
    projection = (
        ROOT / "backend/app/modules/graduation/materials/frozen_package_projection.py"
    ).read_text(encoding="utf-8")
    expected_routes = (
        "/graduation/manifests/{manifest_id}/frozen-package",
        "/portal/graduation/frozen-package",
        "/mobile/student/graduation/frozen-package",
        "/mobile/teacher/platform-integrity/summary",
    )
    for route in expected_routes:
        assert route in api
    assert "frozen_manifest_artifact_ref" in projection
    assert '"artifact": artifact_view' in projection
    for forbidden in ('"url"', '"downloadUrl"', '"objectKey"', '"fileKey"'):
        assert forbidden not in projection


def test_clients_use_file_center_download_and_have_visible_entries():
    staff_api = (ROOT / "frontend/src/modules/system/api/platformIntegrity.api.js").read_text(encoding="utf-8")
    staff_view = (ROOT / "frontend/src/modules/system/views/SystemPlatformIntegrityView.vue").read_text(encoding="utf-8")
    portal_api = (ROOT / "student-portal/src/services/portalApi.js").read_text(encoding="utf-8")
    portal_view = (ROOT / "student-portal/src/views/graduation/GraduationFrozenPackageView.vue").read_text(encoding="utf-8")
    mini_api = (ROOT / "miniapp/src/services/platformIntegrityApi.js").read_text(encoding="utf-8")
    mini_pages = (ROOT / "miniapp/src/pages.json").read_text(encoding="utf-8")

    assert "/platform-integrity/exceptions" in staff_api
    assert "/graduation/manifests/${encodeURIComponent(manifestId)}/frozen-package" in staff_api
    assert "fileSdk.download" in staff_view
    for label in ("Critical", "Today New", "7d Unresolved", "进入业务", "复检"):
        assert label in staff_view
    assert "/portal/graduation/frozen-package" in portal_api
    assert "fileSdk.download" in portal_view
    assert "/mobile/student/graduation/frozen-package" in mini_api
    assert "/mobile/teacher/platform-integrity/summary" in mini_api
    assert '"root": "pages/student"' in mini_pages
    assert '"path": "graduation/evidence-package"' in mini_pages
    assert '"root": "pages/teacher"' in mini_pages
    assert '"path": "platform-integrity/index"' in mini_pages
    teacher_view = (ROOT / "miniapp/src/pages/teacher/platform-integrity/index.vue").read_text(encoding="utf-8")
    assert "data.packages" in teacher_view
    assert "pkg.artifact.fileId" in teacher_view
    assert "openTarget" in teacher_view


def test_package_file_access_is_registered_and_worker_is_tenant_bounded():
    registry = (ROOT / "backend/app/services/file_access_resolvers.py").read_text(encoding="utf-8")
    resolver = (
        ROOT / "backend/app/modules/platform_integrity/file_access_resolver.py"
    ).read_text(encoding="utf-8")
    worker = (ROOT / "backend/app/workers/frozen_package_worker.py").read_text(encoding="utf-8")

    assert "_platform_integrity_file_access_resolver" in registry
    assert "@register_file_resolver(PACKAGE_BIZ_TYPE)" in resolver
    assert "assert_student_access" in resolver
    assert "set_tenant(int(tenant_id))" in worker
    assert "batch_size = max(1, min(int(limit or 20), 100))" in worker
    assert "set_tenant(previous)" in worker


def test_platform_file_jobs_are_registered_with_the_production_scheduler():
    scheduler = (ROOT / "backend/scripts/run_scheduled_jobs.py").read_text(encoding="utf-8")
    assert "def job_file_derivatives()" in scheduler
    assert "derived_worker.process_pending_jobs(" in scheduler
    assert "process_pending_frozen_packages(" in scheduler
    assert scheduler.count("tenant_id=tenant_id") >= 2
    assert "tenant_state.BACKGROUND_BUSINESS_WRITE" in scheduler
    assert "_Ticker(INTERVAL_FILE_JOBS, now0, job_file_derivatives)" in scheduler


def test_frozen_package_scheduler_batch_can_be_pinned_to_one_tenant(monkeypatch):
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    FileJob.__table__.create(engine)
    sessions = sessionmaker(engine, expire_on_commit=False)
    with sessions() as db:
        db.add_all([
            FileJob(
                tenant_id=1001, job_type="FROZEN_EVIDENCE_PACKAGE",
                dedupe_key="package-1001", status="PENDING",
            ),
            FileJob(
                tenant_id=1002, job_type="FROZEN_EVIDENCE_PACKAGE",
                dedupe_key="package-1002", status="PENDING",
            ),
        ])
        db.commit()

    seen_tenants: list[int] = []

    def no_claim(*, worker_id):
        del worker_id
        seen_tenants.append(int(current_tenant_id()))
        return None

    monkeypatch.setattr(frozen_package_worker, "get_sessionmaker", lambda: sessions)
    monkeypatch.setattr(frozen_package_worker, "claim_next_frozen_package_job", no_claim)
    previous = get_tenant()
    try:
        result = frozen_package_worker.process_pending_frozen_packages(
            tenant_id=1002, limit=20, worker_id="scheduler-frozen:1002",
        )
    finally:
        set_tenant(previous)
    assert result == {"processed": 0, "succeeded": 0, "failed": 0}
    assert seen_tenants == [1002]
    engine.dispose()


def test_teacher_integrity_summary_applies_scope_before_limit(monkeypatch):
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    for model in (
        GraduationStudent,
        ArchiveManifest,
        ArchiveManifestItem,
        FileObject,
        FileJob,
        IntegrityException,
    ):
        model.__table__.create(engine)
    sessions = sessionmaker(engine, expire_on_commit=False)
    with sessions() as db:
        db.add_all([
            GraduationStudent(
                id=1, tenant_id=1001, student_id=101, student_no="S101",
                name="Out of scope", college_id="1", record_status="ACTIVE",
            ),
            GraduationStudent(
                id=2, tenant_id=1001, student_id=202, student_no="S202",
                name="In scope", college_id="2", record_status="ACTIVE",
            ),
            ArchiveManifest(
                id=11, tenant_id=1001, module_code="GRADUATION",
                archive_type="STUDENT_ARCHIVE", target_type="GD_STUDENT",
                target_id="1", revision=1, status="FROZEN",
            ),
            ArchiveManifest(
                id=22, tenant_id=1001, module_code="GRADUATION",
                archive_type="STUDENT_ARCHIVE", target_type="GD_STUDENT",
                target_id="2", revision=1, status="FROZEN",
            ),
            IntegrityException(
                id=200, tenant_id=1001, exception_type="NEWER_HIDDEN",
                fingerprint="hidden", status="OPEN", severity="HIGH",
                detector_code="TEST", module_code="GRADUATION",
                subject_type="MANIFEST", subject_id="11", manifest_id=11,
                title="Hidden",
            ),
            IntegrityException(
                id=100, tenant_id=1001, exception_type="OLDER_VISIBLE",
                fingerprint="visible", status="OPEN", severity="HIGH",
                detector_code="TEST", module_code="GRADUATION",
                subject_type="MANIFEST", subject_id="22", manifest_id=22,
                title="Visible",
            ),
        ])
        db.commit()

    @contextmanager
    def scoped_session():
        with sessions() as db:
            yield db

    monkeypatch.setattr(frozen_package_projection, "session", scoped_session)
    previous_user = get_current_user_ctx()
    previous_tenant = get_tenant()
    try:
        set_tenant(1001)
        teacher = {
            "currentRoleCode": "GD_COLLEGE_ADMIN",
            "collegeId": "2",
            "realName": "学院管理员",
        }
        set_current_user(teacher)
        result = teacher_integrity_summary(
            teacher,
            limit=1,
        )
    finally:
        set_current_user(previous_user)
        set_tenant(previous_tenant)
    assert result["total"] == 1
    assert [item["exceptionType"] for item in result["items"]] == ["OLDER_VISIBLE"]
    engine.dispose()


def test_student_teacher_and_file_resolver_negative_authorization_is_fail_closed(monkeypatch):
    with pytest.raises(AppException) as student_entry:
        my_frozen_package({"userType": "TEACHER", "permissions": ["graduationDesign.view"]})
    assert student_entry.value.code == "NO_PERMISSION"

    with pytest.raises(AppException) as teacher_entry:
        teacher_integrity_summary({"userType": "STUDENT", "studentId": "1"})
    assert teacher_entry.value.code == "NO_PERMISSION"

    file_obj = SimpleNamespace(tenant_id=1002, biz_id="m41:r2:digest")
    monkeypatch.setattr(
        "app.modules.platform_integrity.file_access_resolver._tid",
        lambda: 1001,
    )
    assert frozen_evidence_package_resolver(object(), file_obj, [], {}, "download") is False
    assert frozen_evidence_package_resolver(None, file_obj, [], {}, "download") is False

    manifest = SimpleNamespace(
        tenant_id=1001,
        id=41,
        module_code="GRADUATION",
        target_id="5",
        status="FROZEN",
        revision=2,
        manifest_sha256="a" * 64,
        is_deleted=False,
    )
    student = SimpleNamespace(tenant_id=1001, id=5, is_deleted=False)

    class _Scalar:
        def __init__(self, value):
            self.value = value

        def first(self):
            return self.value

    class _Db:
        def __init__(self):
            self.values = iter((manifest, student))

        def scalars(self, _statement):
            return _Scalar(next(self.values))

    same_tenant_file = SimpleNamespace(
        tenant_id=1001,
        biz_id=frozen_package_artifact_biz_id(manifest, "STANDARD_V1"),
    )
    assert frozen_evidence_package_resolver(
        _Db(), same_tenant_file, [], {"userType": "TEACHER", "permissions": []}, "download",
    ) is False
    monkeypatch.setattr(
        "app.modules.graduation.services.graduation_record_resolver.resolve_current_gd_student",
        lambda _db, _actor: SimpleNamespace(id=6),
    )
    assert frozen_evidence_package_resolver(
        _Db(), same_tenant_file, [], {"userType": "STUDENT", "studentId": "6"}, "download",
    ) is False
    monkeypatch.setattr(
        "app.modules.graduation.services.graduation_record_resolver.resolve_current_gd_student",
        lambda _db, _actor: SimpleNamespace(id=5),
    )
    assert frozen_evidence_package_resolver(
        _Db(), same_tenant_file, [], {"userType": "STUDENT", "studentId": "5"}, "download",
    ) is True
    forged_file = SimpleNamespace(tenant_id=1001, biz_id="m41:r2:forged")
    assert frozen_evidence_package_resolver(
        _Db(), forged_file, [], {"userType": "STUDENT", "studentId": "5"}, "download",
    ) is False
    manifest.status = "REVOKED"
    assert frozen_evidence_package_resolver(
        _Db(), same_tenant_file, [], {"userType": "STUDENT", "studentId": "5"}, "download",
    ) is False

    previous_user = get_current_user_ctx()
    try:
        set_current_user({
            "currentRoleCode": "GD_COLLEGE_ADMIN",
            "collegeId": "1",
            "realName": "学院管理员",
        })
        scoped_student = SimpleNamespace(
            tenant_id=1001,
            id=5,
            student_id=55,
            student_no="S55",
            college_id=2,
            major_id=3,
        )
        assert can_access_student(object(), scoped_student) is False
    finally:
        set_current_user(previous_user)


def test_http_build_request_stays_on_file_job_worker_boundary():
    api = (ROOT / "backend/app/api/v1/platform_integrity.py").read_text(encoding="utf-8")
    worker = (ROOT / "backend/app/workers/frozen_package_worker.py").read_text(encoding="utf-8")
    assert "request_frozen_package_build" in api
    assert "build_frozen_package" not in api
    assert "run_claimed_frozen_package_job" in worker
