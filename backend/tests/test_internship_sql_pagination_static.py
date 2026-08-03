from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _function(path, name, next_name):
    text = (ROOT / path).read_text(encoding="utf-8")
    return text[text.index(f"def {name}"):text.index(f"def {next_name}")]


def test_management_ledgers_paginate_in_mysql():
    cases = (
        ("backend/app/modules/internship/services/internship_leave_service.py", "list_leaves", "get_leave"),
        ("backend/app/modules/internship/services/internship_makeup_service.py", "list_makeups", "get_makeup"),
        ("backend/app/modules/internship/services/internship_insurance_service.py", "list_insurances", "student_submit"),
        ("backend/app/modules/internship/services/internship_application_service.py", "list_applications", "get_application"),
    )
    for path, name, next_name in cases:
        block = _function(path, name, next_name)
        assert "apply_internship_record_scope" in block
        assert ".offset(" in block and ".limit(" in block
        assert "select(func.count())" in block
        assert "items[start:start + page_size]" not in block


def test_leave_and_makeup_page_rows_batch_prefetch_evidence():
    leave = _function(
        "backend/app/modules/internship/services/internship_leave_service.py",
        "list_leaves", "get_leave")
    makeup = _function(
        "backend/app/modules/internship/services/internship_makeup_service.py",
        "list_makeups", "get_makeup")
    assert "target_id.in_(ids)" in leave
    assert "target_id.in_(ids)" in makeup
    assert "preloaded=True" in leave and "preloaded=True" in makeup


def test_application_list_joins_position_and_company():
    block = _function(
        "backend/app/modules/internship/services/internship_application_service.py",
        "list_applications", "get_application")
    assert "outerjoin(" in block
    assert "InternshipPosition" in block and "EmpCompany" in block
    assert "preloaded=True" in block
