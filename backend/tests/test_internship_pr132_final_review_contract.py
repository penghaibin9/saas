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


def test_major_sql_projection_trims_before_binary_collation_and_locate():
    source = inspect.getsource(eligibility_svc._major_sql_predicate)
    assert "trimmed_requirement = func.trim(requirement)" in source
    assert 'binary_requirement = trimmed_requirement.collate("utf8mb4_bin")' in source
    assert 'binary_major = literal(major).collate("utf8mb4_bin")' in source
    assert source.index("trimmed_requirement = func.trim(requirement)") < source.index("binary_requirement =")
    assert "func.locate(binary_major, binary_requirement) > 0" in source
    assert "func.locate(binary_requirement, binary_major) > 0" in source
