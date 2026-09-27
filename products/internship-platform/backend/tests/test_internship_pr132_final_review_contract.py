from __future__ import annotations

import inspect

from app.modules.internship.services import internship_application_service as legacy_app_svc
from app.modules.internship.services import internship_student_catalog_facade_service as catalog_svc
from app.modules.internship.services import internship_student_position_eligibility_service as eligibility_svc


def test_legacy_staff_approval_revalidates_position_before_shared_assignment_authority():
    source = inspect.getsource(legacy_app_svc.review_application)
    legacy_guard = source.index("_legacy_position(db, app.position_id)")
    assignment = source.index("student_svc.assign_position_in_tx(")
    assert legacy_guard < assignment
    assert "招聘季岗位必须通过三志愿原子接口" in inspect.getsource(legacy_app_svc._legacy_position)


def test_major_sql_projection_normalizes_python_strip_whitespace_before_binary_locate():
    source = inspect.getsource(eligibility_svc._major_sql_predicate)
    strip_source = inspect.getsource(eligibility_svc._python_strip_sql)
    assert "normalized_requirement = _python_strip_sql(requirement)" in source
    assert "func.regexp_replace(value, _PYTHON_STRIP_EDGE_WS_REGEX, \"\")" in strip_source
    assert 'binary_requirement = normalized_requirement.collate("utf8mb4_bin")' in source
    assert 'binary_major = literal(major).collate("utf8mb4_bin")' in source
    assert source.index("normalized_requirement =") < source.index("binary_requirement =")
    assert "func.locate(binary_major, binary_requirement) > 0" in source
    assert "func.locate(binary_requirement, binary_major) > 0" in source

    pattern = eligibility_svc._PYTHON_STRIP_EDGE_WS_REGEX
    # Python str.strip() includes C0 separators, NBSP, OGHAM, the U+2000 block and ideographic space.
    for token in (r"\x{001C}-\x{001F}", r"\x{0085}", r"\x{00A0}", r"\x{1680}", r"\x{2000}-\x{200A}", r"\x{3000}"):
        assert token in pattern


def test_catalog_sql_projection_matches_python_string_truthiness_and_strip_semantics():
    source = inspect.getsource(eligibility_svc.apply_catalog_query_eligibility_filters_in_tx)
    assert "normalized_work_content = _python_strip_sql(InternshipPosition.work_content)" in source
    assert "normalized_remuneration_type = _python_strip_sql(InternshipPosition.remuneration_type)" in source
    assert "func.length(normalized_work_content) > 0" in source
    assert "func.length(normalized_remuneration_type) > 0" in source
    assert "func.char_length(InternshipPosition.prohibited_reason) == 0" in source
    assert "func.char_length(InternshipPosition.remuneration_cycle) > 0" in source
    assert "func.char_length(InternshipPosition.remuneration_type) == len(\"UNPAID\")" in source
    assert 'literal("UNPAID").collate("utf8mb4_bin")' in source
    assert "func.trim(InternshipPosition.work_content)" not in source
    assert "InternshipPosition.prohibited_reason == \"\"" not in source
    assert "InternshipPosition.remuneration_cycle != \"\"" not in source


def test_catalog_lifecycle_projection_is_pad_safe_and_matches_python_case_rules():
    source = inspect.getsource(catalog_svc._base_query)
    helper = inspect.getsource(catalog_svc._exact_ascii_sql)
    assert "func.char_length(column) == len(value)" in helper
    assert 'literal(expected_value).collate("utf8mb4_bin")' in helper
    assert '_exact_ascii_sql(InternshipPosition.status, "PUBLISHED")' in source
    assert '_exact_ascii_sql(EmpCompany.status, "ACTIVE", case_insensitive=True)' in source
    assert '_exact_ascii_sql(EmpCompany.coop_status, "ACTIVE")' in source
    assert '_exact_ascii_sql(EmpCompany.qualification_status, "PASSED")' in source
    assert '_exact_ascii_sql(InternshipCampaignEnterprise.status, "ACCEPTED")' in source
    assert 'InternshipPosition.status == "PUBLISHED"' not in source
    assert 'EmpCompany.coop_status == "ACTIVE"' not in source
    assert 'EmpCompany.qualification_status == "PASSED"' not in source
