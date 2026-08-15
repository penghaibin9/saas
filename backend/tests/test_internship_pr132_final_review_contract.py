from __future__ import annotations

import inspect

from app.modules.internship.services import internship_application_service as legacy_app_svc
from app.modules.internship.services import internship_student_position_eligibility_service as eligibility_svc


def test_legacy_staff_approval_revalidates_position_before_shared_assignment_authority():
    source = inspect.getsource(legacy_app_svc.review_application)
    legacy_guard = source.index("_legacy_position(db, app.position_id)")
    assignment = source.index("student_svc.assign_position_in_tx(")
    assert legacy_guard < assignment
    assert "招聘季岗位必须通过三志愿原子接口" in inspect.getsource(legacy_app_svc._legacy_position)


def test_major_sql_projection_normalizes_python_strip_whitespace_before_binary_locate():
    source = inspect.getsource(eligibility_svc._major_sql_predicate)
    assert "normalized_requirement = func.regexp_replace(requirement, _PYTHON_STRIP_EDGE_WS_REGEX, \"\")" in source
    assert 'binary_requirement = normalized_requirement.collate("utf8mb4_bin")' in source
    assert 'binary_major = literal(major).collate("utf8mb4_bin")' in source
    assert source.index("normalized_requirement =") < source.index("binary_requirement =")
    assert "func.locate(binary_major, binary_requirement) > 0" in source
    assert "func.locate(binary_requirement, binary_major) > 0" in source

    pattern = eligibility_svc._PYTHON_STRIP_EDGE_WS_REGEX
    # Python str.strip() includes C0 separators, NBSP, OGHAM, the U+2000 block and ideographic space.
    for token in (r"\x{001C}-\x{001F}", r"\x{0085}", r"\x{00A0}", r"\x{1680}", r"\x{2000}-\x{200A}", r"\x{3000}"):
        assert token in pattern
