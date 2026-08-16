from pathlib import Path


def test_data_exchange_get_detail_is_pure_read_contract():
    root = Path(__file__).resolve().parents[2]
    source = (root / "backend/app/modules/system_admin/routers/data_exchange_router.py").read_text(encoding="utf-8")
    detail_body = source.split("def import_job_detail", 1)[1].split("def process_identity_import", 1)[0]
    assert "read_identity_import_job" in detail_body
    assert "refresh_identity_import_job" not in detail_body
    assert "process_identity_import_job" not in detail_body


def test_identity_import_creation_does_not_call_parser_refresh():
    root = Path(__file__).resolve().parents[2]
    source = (root / "backend/app/modules/system_admin/services/identity_import_control_plane_service.py").read_text(encoding="utf-8")
    create_body = source.split("def create_identity_import_job", 1)[1].split("def read_identity_import_job", 1)[0]
    assert "refresh_identity_import_job" not in create_body
    assert 'status="SCANNING"' in create_body
    assert '"workerRequired": True' in create_body


def test_legacy_student_teacher_uploads_are_thin_data_exchange_adapters():
    root = Path(__file__).resolve().parents[2]
    source = (root / "backend/app/modules/system_admin/routers/identity_import_compat_router.py").read_text(encoding="utf-8")
    assert "data_exchange_router.run_identity_import_upload(" in source
    assert 'kind="students"' in source
    assert 'kind="teachers"' in source
    assert "Idempotency-Key" in source
    assert "parse_xlsx" not in source
    assert "parse_identity_xlsx_path" not in source
    assert "LEGACY_IDENTITY_IMPORT_RETIRED" in source


def test_confirm_gate_requires_validated_nonempty_zero_error_rows():
    root = Path(__file__).resolve().parents[2]
    source = (root / "backend/app/services/data_exchange_confirm_service.py").read_text(encoding="utf-8")
    assert "IMPORT_NOT_VALIDATED" in source
    assert "IMPORT_HAS_ERRORS" in source
    assert "IMPORT_EMPTY" in source
    assert "validRows" in source
    assert "invalidRows" in source


def test_identity_confirm_delegates_to_frozen_unified_dispatcher():
    root = Path(__file__).resolve().parents[2]
    source = (root / "backend/app/services/data_exchange_confirm_service.py").read_text(encoding="utf-8")
    identity_body = source.split("def confirm_identity_import_job", 1)[1].split(
        "def confirm_migration_import_job", 1
    )[0]
    assert "return _legacy.confirm_import_job(" in identity_body
    assert "_legacy.confirm_identity_import_job(" not in identity_body
