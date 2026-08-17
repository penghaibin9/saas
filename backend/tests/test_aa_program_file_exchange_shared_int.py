"""INT shared-owner wiring contracts for Program through Academic File Exchange."""
from __future__ import annotations

import inspect
from pathlib import Path
from types import SimpleNamespace

import pytest


def test_program_parse_branch_reuses_six_sheet_adapter_and_read_only_preview(tmp_path, monkeypatch):
    from app.modules.academic_affairs.services import academic_file_exchange_service as exchange
    from app.modules.academic_affairs.services import academic_affairs_school_setup_program_preview_service as preview_service
    from app.modules.academic_affairs.services import academic_affairs_school_setup_program_workbook_adapter as workbook

    source_path = tmp_path / "program.xlsx"
    source_path.write_bytes(b"program-xlsx-placeholder")
    expected_grouped = {"MAIN": [{"programSeriesKey": "SER-A"}]}
    expected_rows = [{
        "rowNo": 2,
        "logicalGroup": "MAIN",
        "programKey": "SERIES:SER-A:v1",
        "definitionKey": "SERIES:SER-A:v1",
        "payload": {"programSeriesKey": "SER-A"},
    }]
    expected_preview = {
        "totalRows": 1,
        "validRows": 1,
        "invalidRows": 0,
        "phase": "DEFINITION",
        "stage": "READY",
        "programPreflightSafe": True,
    }
    calls = []

    def fake_parse(file_bytes, *, max_bytes):
        calls.append((file_bytes, max_bytes))
        return expected_grouped, expected_rows

    def fake_preview(rows, *, phase, user):
        assert rows == expected_rows
        assert phase == "DEFINITION"
        assert user == {"userId": "7"}
        return dict(expected_preview)

    monkeypatch.setattr(workbook, "parse_and_normalize_program_workbook", fake_parse)
    monkeypatch.setattr(preview_service, "preview_program_normalized_rows", fake_preview)
    row = SimpleNamespace(
        import_type=exchange.ACADEMIC_PROGRAM_IMPORT,
        source_snapshot_json={"context": {"phase": "DEFINITION"}},
    )

    rows, preview = exchange._parse_and_validate(row, Path(source_path), {"userId": "7"})

    assert rows == expected_rows
    assert preview["stage"] == "READY"
    assert preview["sheetRowCounts"] == {"MAIN": 1}
    assert preview["normalizedRowCount"] == 1
    assert calls == [(b"program-xlsx-placeholder", exchange.MAX_IMPORT_BYTES)]


def test_program_phase_permissions_are_server_side_and_fail_closed(monkeypatch):
    from app.core.exceptions import AppException
    from app.modules.academic_affairs.services import academic_file_exchange_service as exchange

    calls = []
    monkeypatch.setattr(exchange, "enforce_permission", lambda user, code: calls.append((user, code)))
    user = {"userId": "7"}

    assert exchange._enforce_program_job_permission(
        exchange.ACADEMIC_PROGRAM_IMPORT,
        {"phase": "DEFINITION", "ignored": "client-value"},
        user,
    ) == "DEFINITION"
    assert exchange._enforce_program_job_permission(
        exchange.ACADEMIC_PROGRAM_IMPORT,
        {"phase": "BINDING"},
        user,
    ) == "BINDING"
    assert calls == [
        (user, "academicAffairs.program.manage"),
        (user, "academicAffairs.program.publish"),
    ]

    with pytest.raises(AppException, match="服务端冻结"):
        exchange._enforce_program_job_permission(
            exchange.ACADEMIC_PROGRAM_IMPORT,
            {"phase": "MIGRATION"},
            user,
        )


def test_legacy_confirm_rechecks_program_phase_permission_before_any_fast_path_or_lease(monkeypatch):
    from app.core.exceptions import AppException
    from app.modules.academic_affairs.services import academic_file_exchange_service as exchange
    from app.services import data_exchange_confirm_legacy as legacy

    class FakeDb:
        def close(self):
            pass

    monkeypatch.setattr(legacy, "get_sessionmaker", lambda: lambda: FakeDb())
    calls = []

    def denied(import_type, context, user):
        calls.append((import_type, dict(context), user))
        raise AppException("NO_PERMISSION", "permission revoked", http_status=403)

    monkeypatch.setattr(exchange, "_enforce_program_job_permission", denied)
    monkeypatch.setattr(
        legacy,
        "_begin_adapter_confirm",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("lease must not start")),
    )
    user = {"userId": "7"}

    for status in ("VALIDATED", "SUCCEEDED"):
        row = SimpleNamespace(
            adapter_type=legacy.jobs.IMPORT_ADAPTER_EXCEL,
            import_type="ACADEMIC_PROGRAM",
            source_snapshot_json={"context": {"phase": "BINDING"}},
            status=status,
        )
        monkeypatch.setattr(legacy.jobs, "_owned_import", lambda db, job_id, actor, _row=row: _row)
        with pytest.raises(AppException, match="permission revoked"):
            legacy.confirm_import_job("55", expected_version=3, user=user)

    assert calls == [
        ("ACADEMIC_PROGRAM", {"phase": "BINDING"}, user),
        ("ACADEMIC_PROGRAM", {"phase": "BINDING"}, user),
    ]


def _confirm_row(exchange, phase: str, rows: list[dict]):
    return SimpleNamespace(
        adapter_type=exchange.jobs.IMPORT_ADAPTER_EXCEL,
        lease_token="lease-1",
        source_snapshot_json={
            "rowDigest": exchange._row_digest(rows),
            "context": {"phase": phase},
        },
        import_type=exchange.ACADEMIC_PROGRAM_IMPORT,
    )


@pytest.mark.parametrize("phase", ["DEFINITION", "BINDING"])
def test_program_confirm_reparses_same_digest_and_dispatches_exact_atomic_owner(phase, monkeypatch):
    from app.modules.academic_affairs.services import academic_file_exchange_service as exchange
    from app.modules.academic_affairs.services import academic_affairs_school_setup_program_binding_confirm_service as binding
    from app.modules.academic_affairs.services import academic_affairs_school_setup_program_definition_authority_service as definition

    rows = [{"programKey": "SERIES:SER-A:v1", "logicalGroup": "MAIN", "rowNo": 2}]
    import_row = _confirm_row(exchange, phase, rows)

    class FakeDb:
        def close(self):
            pass

    monkeypatch.setattr(exchange, "get_sessionmaker", lambda: lambda: FakeDb())
    monkeypatch.setattr(exchange.jobs, "_owned_import", lambda db, job_id, user: import_row)
    monkeypatch.setattr(exchange, "_source_file_path", lambda row, user: Path("/tmp/program.xlsx"))
    monkeypatch.setattr(
        exchange,
        "_parse_and_validate",
        lambda row, source_path, user: (
            rows,
            {"totalRows": 1, "validRows": 1, "invalidRows": 0},
        ),
    )
    permission_calls = []
    monkeypatch.setattr(
        exchange,
        "_enforce_program_job_permission",
        lambda import_type, context, user: permission_calls.append((import_type, dict(context))) or phase,
    )
    definition_calls = []
    binding_calls = []
    monkeypatch.setattr(
        definition,
        "confirm_program_definition_import",
        lambda source_rows, *, user: definition_calls.append((source_rows, user)) or {"phase": "DEFINITION"},
    )
    monkeypatch.setattr(
        binding,
        "confirm_program_binding_import",
        lambda source_rows, *, user: binding_calls.append((source_rows, user)) or {"phase": "BINDING"},
    )

    user = {"userId": "7"}
    result = exchange.confirm_academic_import("55", lease="lease-1", user=user)

    assert result["confirmedRows"] == 1
    assert permission_calls == [(exchange.ACADEMIC_PROGRAM_IMPORT, {"phase": phase})]
    if phase == "DEFINITION":
        assert definition_calls == [(rows, user)]
        assert binding_calls == []
    else:
        assert binding_calls == [(rows, user)]
        assert definition_calls == []


def test_program_preview_errors_keep_real_sheet_and_normalized_raw_snapshot():
    from app.modules.academic_affairs.services.academic_affairs_school_setup_program_preview_adapter import (
        program_preflight_to_file_exchange_preview,
    )

    rows = [{
        "rowNo": 2,
        "logicalGroup": "COURSE",
        "programKey": "SERIES:SER-A:v1",
        "definitionKey": "SERIES:SER-A:v1|COURSE|CS101@v1",
        "payload": {
            "courseKey": "CS101@v1",
            "module": "MAJOR_CORE",
            "formationMode": "ADMIN_FIXED",
        },
    }]
    result = program_preflight_to_file_exchange_preview(rows, {
        "stage": "REFERENCE",
        "programPreflightSafe": False,
        "actions": [],
        "binding": {"phase": "DEFINITION"},
        "errors": [{
            "row": 2,
            "logicalGroup": "COURSE",
            "programKey": "SERIES:SER-A:v1",
            "businessCode": "PROGRAM_COURSE_NOT_FOUND",
            "message": "课程版本不存在",
            "evidence": {"courseKey": "CS101@v1"},
            "howToResolve": "先创建课程版本",
        }],
    })
    error = result["errors"][0]
    assert error["sheetName"] == "方案课程"
    assert error["raw"]["courseKey"] == "CS101@v1"
    assert error["raw"]["programKey"] == "SERIES:SER-A:v1"
    assert error["evidence"] == {
        "courseKey": "CS101@v1",
        "programKey": "SERIES:SER-A:v1",
    }


def test_program_workbook_shared_parser_accepts_caller_owned_20mb_ceiling():
    from app.modules.academic_affairs.services import academic_affairs_school_setup_program_workbook_adapter as workbook

    read_params = inspect.signature(workbook.read_program_workbook).parameters
    parse_params = inspect.signature(workbook.parse_and_normalize_program_workbook).parameters
    assert "max_bytes" in read_params
    assert "max_bytes" in parse_params


def test_canonical_and_frozen_dispatchers_both_include_program():
    from app.services import data_exchange_confirm_legacy as legacy
    from app.services import data_exchange_confirm_service as canonical

    canonical_source = inspect.getsource(canonical.confirm_import_job)
    legacy_source = inspect.getsource(legacy.confirm_import_job)
    assert '"ACADEMIC_PROGRAM"' in canonical_source
    assert '"ACADEMIC_PROGRAM"' in legacy_source
    assert "confirm_academic_import_job" in canonical_source
    assert "academic.confirm_academic_import" in legacy_source


def test_public_router_exposes_program_template_and_two_server_owned_phase_routes():
    from app.modules.academic_affairs.routers import academic_file_exchange_router as router_module

    paths = {route.path for route in router_module.router.routes}
    assert "/academic-affairs/file-exchange/programs/import-template" in paths
    assert "/academic-affairs/file-exchange/programs/definition/import-jobs" in paths
    assert "/academic-affairs/file-exchange/programs/binding/import-jobs" in paths
    source = inspect.getsource(router_module)
    assert '_PROGRAM_MANAGE_PERMISSION = "academicAffairs.program.manage"' in source
    assert '_PROGRAM_PUBLISH_PERMISSION = "academicAffairs.program.publish"' in source
    assert 'context={"phase": "DEFINITION"}' in source
    assert 'context={"phase": "BINDING"}' in source
    assert "exchange.ACADEMIC_PROGRAM_IMPORT" in source


def test_program_file_exchange_contract_is_public_only_with_shared_owner():
    from app.modules.academic_affairs.services.academic_affairs_school_setup_program_file_exchange_spec import (
        program_file_exchange_contract,
    )

    contract = program_file_exchange_contract()
    assert contract["publicImportEnabled"] is True
    assert contract["confirmOwner"] == "ACADEMIC_FILE_EXCHANGE"
    assert contract["confirmPhases"] == ["DEFINITION", "BINDING"]


def test_shared_service_uses_canonical_definition_authority_not_lower_level_writer():
    from app.modules.academic_affairs.services import academic_file_exchange_service as exchange

    source = inspect.getsource(exchange.confirm_academic_import)
    assert "academic_affairs_school_setup_program_definition_authority_service" in source
    assert "academic_affairs_school_setup_program_binding_confirm_service" in source
    assert "academic_affairs_school_setup_program_definition_confirm_service" not in source
