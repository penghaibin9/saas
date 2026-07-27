"""公示、历史导入和xlsx安全静态回归合同。"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_publicity_has_formal_duration_and_serialized_scans():
    text = read("backend/app/services/affairs_publicity_guard.py")
    assert "正式公示天数应为1-30天" in text
    assert "学年格式应为YYYY-YYYY" in text
    assert text.count("with_for_update(skip_locked=True)") == 2
    assert text.count("timedelta(days=max(1") == 2
    assert "_pending_objection_ids" in text
    assert "_pending_appeal_ids" in text


def test_history_import_is_shared_locked_and_full_side_effect():
    history = read("backend/app/services/affairs_history_import_guard.py")
    dry = read("backend/app/services/affairs_history_dry_run_guard.py")
    assert "cache_set_json_if_absent" in history
    assert "IMPORT_STORE_UNAVAILABLE" in history
    assert "AffairsStudentOrg" in history
    assert "discipline._make_effective" in history
    assert "dorm._writeback_dorm_record" in history
    assert "StudentStageEvent" in history
    assert 'memory["status"] = "DRY_RUN_FAILED"' in dry
    assert 'memory["rows"] = []' in dry


def test_xlsx_import_export_prevents_formula_and_path_injection():
    domain_export = read("backend/app/services/domain_export_service.py")
    common = read("backend/app/services/import_export_service.py")
    assert "_excel_safe" in domain_export
    assert "_excel_safe" in common
    assert '("=", "+", "-", "@")' in common
    assert 'ext != "xlsx"' in common
    assert "危险表达式" in common
    assert "candidate.relative_to(root)" in common
    assert 'candidate.suffix.lower() == ".xlsx"' in common
    assert "target.unlink(missing_ok=True)" in domain_export


def test_router_installs_publicity_before_archive_and_stats():
    source = read("backend/app/api/v1/router.py")
    publicity = source.index("install_publicity_guard()")
    archive = source.index("install_archive_guard()")
    stats = source.index("install_stats_integrity_guard()")
    assert publicity < archive < stats
