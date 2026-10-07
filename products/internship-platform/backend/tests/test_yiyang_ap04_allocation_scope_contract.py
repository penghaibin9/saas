"""Yiyang AP04 allocation/college-scope contracts.

This suite locks the standalone authority surface without starting full CI:
- enterprise applicability is an internship-domain relation, not a new company master;
- enterprise and position APIs accept the authenticated principal for scope enforcement;
- direct placement invokes the same enterprise-scope guard;
- removed additional-plan tasks are filtered from teacher projections.
"""
from __future__ import annotations

import inspect

from app.models import InternshipEnterpriseCollegeScope, InternshipPlanAssignment
from app.modules.internship.routers.internship import router as internship_router
from app.modules.internship.routers.internship_position import router as position_router
from app.modules.internship.routers.internship_student import router as student_router
from app.modules.internship.services import internship_enterprise_service as enterprise_svc
from app.modules.internship.services import internship_plan_task_service as plan_task_svc
from app.modules.internship.services import internship_position_service as position_svc
from app.modules.internship.services import internship_student_service as student_svc


def _methods(router):
    return {
        (route.path, method)
        for route in router.routes
        for method in (getattr(route, "methods", set()) or set())
    }


def test_enterprise_college_scope_is_separate_internship_fact():
    table = InternshipEnterpriseCollegeScope.__table__
    assert table.name == "t_internship_enterprise_college_scope"
    columns = set(table.c.keys())
    assert {"tenant_id", "company_id", "college_id", "scope_source", "is_deleted", "version"} <= columns
    assert any(
        set(constraint.columns.keys()) == {"tenant_id", "company_id", "college_id"}
        for constraint in table.constraints
        if constraint.__class__.__name__ == "UniqueConstraint"
    )


def test_ap04_scope_routes_and_principal_contracts_are_exposed():
    methods = _methods(internship_router) | _methods(position_router) | _methods(student_router)
    assert ("/internship/enterprises/scope-colleges", "GET") in methods
    assert ("/internship/intern-students/{record_id}/plan-assignments", "GET") in methods
    assert ("/internship/intern-students/{record_id}/plan-assignments", "POST") in methods
    assert (
        "/internship/intern-students/{record_id}/plan-assignments/{assignment_id}/remove",
        "POST",
    ) in methods

    for fn in (
        enterprise_svc.list_enterprises,
        enterprise_svc.get_enterprise,
        enterprise_svc.create_enterprise,
        enterprise_svc.update_enterprise,
        position_svc.list_positions,
        position_svc.create_position,
        position_svc.update_position,
        position_svc.position_stats,
        position_svc.export_positions,
    ):
        assert "user" in inspect.signature(fn).parameters, fn.__name__


def test_direct_position_assignment_rechecks_enterprise_college_scope():
    source = inspect.getsource(student_svc._assign_position_core_in_tx)
    assert "assert_company_visible" in source
    assert "enterprise_scope" in source

    list_source = inspect.getsource(position_svc.list_positions)
    export_source = inspect.getsource(position_svc.export_positions)
    assert "apply_company_scope" in list_source
    assert "apply_company_scope" in export_source


def test_removed_additional_plan_is_not_teacher_task_truth():
    assignment_table = InternshipPlanAssignment.__table__
    columns = set(assignment_table.c.keys())
    assert {"internship_id", "plan_id", "status", "is_primary"} <= columns

    source = inspect.getsource(plan_task_svc.list_progress)
    assert "InternshipPlanAssignment.status == \"ACTIVE\"" in source
    assert "active_assignment" in source
    assert "legacy_primary" in source
