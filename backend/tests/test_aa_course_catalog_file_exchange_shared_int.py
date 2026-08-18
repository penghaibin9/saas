"""INT shared-owner wiring for Course Catalog through Academic File Exchange."""
from __future__ import annotations

import inspect
from pathlib import Path
from types import SimpleNamespace

import pytest


def test_course_catalog_parse_branch_delegates_frozen_file_exchange_spec(monkeypatch):
    from app.modules.academic_affairs.services import academic_file_exchange_service as exchange
    from app.modules.academic_affairs.services import academic_affairs_school_setup_file_exchange_spec as spec

    expected_rows = [{"courseCode": "CS101", "version": "1"}]
    expected_preview = {"totalRows": 1, "validRows": 1, "invalidRows": 0}
    calls = []

    def fake_parse(source_path, *, user, reader):
        calls.append((source_path, user, reader))
        return expected_rows, expected_preview

    monkeypatch.setattr(spec, "parse_and_validate_course_catalog", fake_parse)
    row = SimpleNamespace(
        import_type=exchange.ACADEMIC_COURSE_CATALOG_IMPORT,
        source_snapshot_json={"context": {}},
    )
    source_path = Path("/tmp/course.xlsx")
    user = {"userId": "7"}

    rows, preview = exchange._parse_and_validate(row, source_path, user)

    assert rows == expected_rows
    assert preview == expected_preview
    assert calls == [(source_path, user, exchange._read_xlsx_path)]


def test_course_catalog_confirm_branch_reuses_same_file_digest_and_atomic_writer(monkeypatch):
    from app.modules.academic_affairs.services import academic_file_exchange_service as exchange
    from app.modules.academic_affairs.services import academic_affairs_school_setup_course_confirm_service as course_confirm

    rows = [{"courseCode": "CS101", "version": "1"}]
    digest = exchange._row_digest(rows)
    import_row = SimpleNamespace(
        adapter_type=exchange.jobs.IMPORT_ADAPTER_EXCEL,
        lease_token="lease-1",
        source_snapshot_json={"rowDigest": digest, "context": {}},
        import_type=exchange.ACADEMIC_COURSE_CATALOG_IMPORT,
    )

    class FakeDb:
        def close(self):
            pass

    monkeypatch.setattr(exchange, "get_sessionmaker", lambda: lambda: FakeDb())
    monkeypatch.setattr(exchange.jobs, "_owned_import", lambda db, job_id, user: import_row)
    monkeypatch.setattr(exchange, "_source_file_path", lambda row, user: Path("/tmp/course.xlsx"))
    monkeypatch.setattr(
        exchange,
        "_parse_and_validate",
        lambda row, source_path, user: (rows, {"totalRows": 1, "validRows": 1, "invalidRows": 0}),
    )
    calls = []

    def fake_confirm(source_rows, user):
        calls.append((source_rows, user))
        return {"confirmedRows": 1, "createdCount": 1, "reusedCount": 0}

    monkeypatch.setattr(course_confirm, "confirm_course_catalog_import", fake_confirm)
    user = {"userId": "7"}
    result = exchange.confirm_academic_import("55", lease="lease-1", user=user)

    assert result["confirmedRows"] == 1
    assert calls == [(rows, user)]


def test_course_catalog_is_accepted_by_job_creator_but_unknown_type_fails_before_db(monkeypatch):
    from app.core.exceptions import AppException
    from app.modules.academic_affairs.services import academic_file_exchange_service as exchange

    def db_reached():
        raise RuntimeError("DB_REACHED")

    monkeypatch.setattr(exchange, "get_sessionmaker", db_reached)
    with pytest.raises(RuntimeError, match="DB_REACHED"):
        exchange.create_academic_import_job(
            filename="courses.xlsx",
            source_file_id=1,
            import_type=exchange.ACADEMIC_COURSE_CATALOG_IMPORT,
            context={},
            user={"userId": "7"},
        )

    with pytest.raises(AppException, match="不支持的教务导入类型"):
        exchange.create_academic_import_job(
            filename="unknown.xlsx",
            source_file_id=1,
            import_type="ACADEMIC_UNKNOWN",
            context={},
            user={"userId": "7"},
        )


def test_canonical_and_frozen_dispatchers_both_include_course_catalog():
    from app.services import data_exchange_confirm_legacy as legacy
    from app.services import data_exchange_confirm_service as canonical

    canonical_source = inspect.getsource(canonical.confirm_import_job)
    legacy_source = inspect.getsource(legacy.confirm_import_job)
    assert '"ACADEMIC_COURSE_CATALOG"' in canonical_source
    assert '"ACADEMIC_COURSE_CATALOG"' in legacy_source
    assert "confirm_academic_import_job" in canonical_source
    assert "academic.confirm_academic_import" in legacy_source


def test_public_router_exposes_course_template_and_import_job_with_existing_course_manage_permission():
    from app.modules.academic_affairs.routers import academic_file_exchange_router as router_module

    paths = {route.path for route in router_module.router.routes}
    assert "/academic-affairs/file-exchange/course-catalog/import-template" in paths
    assert "/academic-affairs/file-exchange/course-catalog/import-jobs" in paths
    source = inspect.getsource(router_module)
    assert '_COURSE_MANAGE_PERMISSION = "academicAffairs.course.manage"' in source
    assert "ACADEMIC_COURSE_CATALOG_IMPORT_SOURCE" in source
    assert "exchange.ACADEMIC_COURSE_CATALOG_IMPORT" in source


def test_file_exchange_contract_is_public_only_after_shared_wiring():
    from app.modules.academic_affairs.services.academic_affairs_school_setup_file_exchange_spec import (
        course_catalog_file_exchange_contract,
    )

    contract = course_catalog_file_exchange_contract()
    assert contract["publicImportEnabled"] is True
    assert contract["confirmOwner"] == "ACADEMIC_FILE_EXCHANGE"


def test_shared_finish_prefers_confirmed_rows_over_created_count(monkeypatch):
    from app.services import data_exchange_confirm_legacy as legacy

    row = SimpleNamespace(
        status="CONFIRMING",
        lease_token="lease-1",
        valid_rows=2,
        confirmed_rows=0,
        result_json=None,
        lease_started_at=object(),
        error_message="",
        version=3,
        confirmed_at=None,
    )

    class FakeDb:
        def commit(self):
            pass

        def refresh(self, value):
            assert value is row

        def close(self):
            pass

    monkeypatch.setattr(legacy, "get_sessionmaker", lambda: lambda: FakeDb())
    monkeypatch.setattr(legacy.jobs, "_owned_import", lambda db, job_id, user, lock=False: row)
    monkeypatch.setattr(legacy.jobs, "_now", lambda: "NOW")
    monkeypatch.setattr(legacy.jobs, "_import_row", lambda value: {"confirmedRows": value.confirmed_rows})

    result = legacy._finish(
        "55",
        "lease-1",
        {"confirmedRows": 2, "createdCount": 1, "reusedCount": 1},
        {"userId": "7"},
    )

    assert row.confirmed_rows == 2
    assert result == {"confirmedRows": 2}
