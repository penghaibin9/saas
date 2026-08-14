"""20K 演示校正式角色拓扑合同；纯单元测试，不连接数据库。"""
from app.services.saas_role_templates import ROLE_TEMPLATE_BY_CODE
from app.services.sandbox_school_role_reconcile import (
    EXPECTED_ORG_SCOPES,
    REQUIRED_ROLE_CODES,
    SECONDARY_ROLE_ASSIGNMENT_COUNTS,
)


def test_20k_role_topology_uses_only_frozen_builtin_roles():
    assert set(REQUIRED_ROLE_CODES) <= set(ROLE_TEMPLATE_BY_CODE)
    assert len(REQUIRED_ROLE_CODES) == 24


def test_secondary_roles_enrich_existing_staff_without_new_accounts():
    assert sum(SECONDARY_ROLE_ASSIGNMENT_COUNTS.values()) == 501
    assert SECONDARY_ROLE_ASSIGNMENT_COUNTS["LEADER"] == 9
    assert SECONDARY_ROLE_ASSIGNMENT_COUNTS["COLLEGE_ADMIN"] == 24
    assert SECONDARY_ROLE_ASSIGNMENT_COUNTS["STUDENT_AFFAIRS"] == 32
    assert SECONDARY_ROLE_ASSIGNMENT_COUNTS["DORM_MANAGER"] == 12
    assert SECONDARY_ROLE_ASSIGNMENT_COUNTS["GD_MAJOR_ADMIN"] == 32
    assert SECONDARY_ROLE_ASSIGNMENT_COUNTS["GD_DEFENSE_EXPERT"] == 160
    assert SECONDARY_ROLE_ASSIGNMENT_COUNTS["EMPLOYMENT_TEACHER"] == 32


def test_org_scope_plan_matches_eight_colleges_and_thirty_two_majors():
    assert sum(EXPECTED_ORG_SCOPES.values()) == 368
    assert EXPECTED_ORG_SCOPES["COLLEGE_ADMIN"] == 8 * 3
    assert EXPECTED_ORG_SCOPES["STUDENT_AFFAIRS"] == 8 * 4
    assert EXPECTED_ORG_SCOPES["PSYCHOLOGY_TEACHER"] == 8 * 2
    assert EXPECTED_ORG_SCOPES["FUNDING_TEACHER"] == 8 * 2
    assert EXPECTED_ORG_SCOPES["YOUTH_LEAGUE"] == 8
    assert EXPECTED_ORG_SCOPES["GD_COLLEGE_ADMIN"] == 8 * 2
    assert EXPECTED_ORG_SCOPES["GD_MAJOR_ADMIN"] == 32
    assert EXPECTED_ORG_SCOPES["EMPLOYMENT_TEACHER"] == 8 * 4
    assert EXPECTED_ORG_SCOPES["GD_MENTOR"] == 96
    assert EXPECTED_ORG_SCOPES["INTERN_MENTOR"] == 96
