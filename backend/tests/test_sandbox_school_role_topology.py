"""20K 演示校正式角色拓扑合同；纯单元测试，不连接数据库。"""
from pathlib import Path
from types import SimpleNamespace

from app.services.saas_role_templates import ROLE_TEMPLATE_BY_CODE
from app.services.sandbox_school_role_reconcile import (
    EXPECTED_ORG_SCOPES,
    EXPECTED_ORG_SCOPE_TYPES,
    REQUIRED_ROLE_CODES,
    SECONDARY_ROLE_ASSIGNMENT_COUNTS,
    _assignment_plan,
)


def test_20k_role_topology_uses_only_frozen_builtin_roles():
    assert set(REQUIRED_ROLE_CODES) <= set(ROLE_TEMPLATE_BY_CODE)
    assert len(REQUIRED_ROLE_CODES) == 24


def test_secondary_roles_enrich_existing_staff_without_new_accounts():
    assert sum(SECONDARY_ROLE_ASSIGNMENT_COUNTS.values()) == 493
    assert SECONDARY_ROLE_ASSIGNMENT_COUNTS["LEADER"] == 1
    assert SECONDARY_ROLE_ASSIGNMENT_COUNTS["COLLEGE_ADMIN"] == 24
    assert SECONDARY_ROLE_ASSIGNMENT_COUNTS["STUDENT_AFFAIRS"] == 32
    assert SECONDARY_ROLE_ASSIGNMENT_COUNTS["DORM_MANAGER"] == 12
    assert SECONDARY_ROLE_ASSIGNMENT_COUNTS["GD_MAJOR_ADMIN"] == 32
    assert SECONDARY_ROLE_ASSIGNMENT_COUNTS["GD_DEFENSE_EXPERT"] == 160
    assert SECONDARY_ROLE_ASSIGNMENT_COUNTS["EMPLOYMENT_TEACHER"] == 32


def test_assignment_plan_does_not_promote_college_leaders_to_school_leader():
    pools = {
        name: [SimpleNamespace(login_name=f"{name}_{index:04d}") for index in range(count)]
        for name, count in {
            "academic_admin": 48,
            "student_affairs": 32,
            "academic": 912,
            "graduation_mentor": 96,
        }.items()
    }

    plan = _assignment_plan(pools)
    school_leaders = {user.login_name for user in plan["LEADER"]}
    college_admins = {user.login_name for user in plan["COLLEGE_ADMIN"]}

    assert school_leaders == {pools["academic_admin"][0].login_name}
    assert len(college_admins) == 24
    for user in pools["academic_admin"][1:9]:
        assert user.login_name in college_admins
        assert user.login_name not in school_leaders
    assert {code: len(users) for code, users in plan.items()} == SECONDARY_ROLE_ASSIGNMENT_COUNTS


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


def test_org_scope_validation_does_not_count_sensitive_student_grants_twice():
    assert set(EXPECTED_ORG_SCOPE_TYPES) == set(EXPECTED_ORG_SCOPES)
    assert EXPECTED_ORG_SCOPE_TYPES["PSYCHOLOGY_TEACHER"] == "COLLEGE"
    assert EXPECTED_ORG_SCOPE_TYPES["GD_MAJOR_ADMIN"] == "MAJOR"
    assert EXPECTED_ORG_SCOPE_TYPES["GD_MENTOR"] == "ADVISOR"


def test_b8_final_topology_uses_the_same_canonical_org_scope_types():
    source = (Path(__file__).resolve().parents[1]
              / "scripts" / "check_control_plane_b8_topology.py").read_text(encoding="utf-8")
    assert "EXPECTED_ORG_SCOPE_TYPES" in source
    assert "TeacherStudentScope.scope_type == EXPECTED_ORG_SCOPE_TYPES[code]" in source
