"""INT contract for the six-sheet Program File Exchange workbook spec."""
from __future__ import annotations

import inspect


def _spec():
    from app.modules.academic_affairs.services import academic_affairs_school_setup_program_file_exchange_spec as spec
    return spec


def test_program_workbook_freezes_all_six_logical_groups_in_exact_order():
    spec = _spec()
    contract = spec.program_file_exchange_contract()
    assert contract["templateVersion"] == "program-v2"
    assert contract["workbookMode"] == "MULTI_SHEET_EXACT_NAMES"
    assert contract["sheetCount"] == 6
    assert [item["sheetName"] for item in contract["sheets"]] == [
        "培养方案", "方案课程", "学分要求", "实践环节", "毕业要求", "适用范围",
    ]
    assert [item["logicalGroup"] for item in contract["sheets"]] == [
        "MAIN", "COURSE", "CREDIT_REQUIREMENT", "PRACTICE", "GRADUATION", "BINDING",
    ]
    assert contract["confirmPhases"] == ["DEFINITION", "BINDING"]
    assert contract["publicImportEnabled"] is True
    assert contract["confirmOwner"] == "ACADEMIC_FILE_EXCHANGE"


def test_every_required_program_field_has_a_workbook_header():
    spec = _spec()
    from app.modules.academic_affairs.services import academic_affairs_school_setup_import_contract as domain

    for group, required_fields in domain.PROGRAM_REQUIRED_FIELDS_BY_GROUP.items():
        mapped_fields = set(spec.PROGRAM_HEADER_MAP_BY_GROUP[group].values())
        assert required_fields <= mapped_fields, (group, sorted(required_fields - mapped_fields))


def test_program_course_sheet_requires_module_and_explicit_formation_but_credit_is_assertion_only():
    spec = _spec()
    course = next(
        item for item in spec.program_file_exchange_contract()["sheets"]
        if item["logicalGroup"] == "COURSE"
    )
    assert course["headerMap"]["课程模块"] == "module"
    assert course["headerMap"]["编班方式"] == "formationMode"
    assert "课程模块" in course["requiredHeaders"]
    assert "编班方式" in course["requiredHeaders"]
    assert course["headerMap"]["学分快照(断言)"] == "creditSnapshot"
    assert "学分快照(断言)" not in course["requiredHeaders"]


def test_binding_sheet_keeps_class_id_conditional_and_never_redefines_program_identity():
    spec = _spec()
    binding = next(
        item for item in spec.program_file_exchange_contract()["sheets"]
        if item["logicalGroup"] == "BINDING"
    )
    assert binding["headerMap"]["培养方案系列键"] == "programSeriesKey"
    assert binding["headerMap"]["版本"] == "programVersion"
    assert binding["headerMap"]["绑定范围"] == "bindingScope"
    assert binding["headerMap"]["班级ID"] == "classId"
    assert "班级ID" not in binding["requiredHeaders"]
    notes = "\n".join(spec.PROGRAM_FILLING_NOTES)
    assert "不得由专业、年级、方案名称或绑定范围自动生成" in notes
    assert "第二轮 BINDING phase" in notes


def test_spec_does_not_own_parser_job_session_or_shared_dispatcher():
    source = inspect.getsource(_spec())
    assert "openpyxl" not in source
    assert "xlsx_util" not in source
    assert "ImportJob(" not in source
    assert "FileObject(" not in source
    assert "session()" not in source
    assert "data_exchange_confirm_service" not in source
    assert "data_exchange_confirm_legacy" not in source
