"""E0: freeze the existing internship authorities before enterprise-collaboration expansion.

This suite is intentionally DB-free. It protects ownership and routing boundaries so later
E-series cards can only extend the current domain instead of creating duplicate facts.
"""
from __future__ import annotations

import inspect

from sqlalchemy import UniqueConstraint

from app.api.v1 import route_registration
from app.models import (
    EmpCompany,
    EmpJob,
    InternshipApplication,
    InternshipIntention,
    InternshipPosition,
)
from app.modules.internship.services import (
    internship_application_service,
    internship_position_service,
)


def _unique_column_sets(model) -> set[tuple[str, ...]]:
    return {
        tuple(column.name for column in constraint.columns)
        for constraint in model.__table__.constraints
        if isinstance(constraint, UniqueConstraint)
    }


def test_existing_company_and_internship_position_are_the_authorities():
    assert EmpCompany.__tablename__ == "t_emp_company"
    assert InternshipPosition.__tablename__ == "t_internship_position"

    # Employment jobs remain a different domain and must never become internship positions.
    assert EmpJob.__tablename__ == "t_emp_job"
    assert EmpJob.__table__.name != InternshipPosition.__table__.name


def test_formal_application_owns_three_slots_and_intention_stays_separate():
    assert InternshipApplication.__tablename__ == "t_internship_application"
    assert InternshipIntention.__tablename__ == "t_internship_intention"
    assert InternshipApplication.__table__.name != InternshipIntention.__table__.name
    assert ("tenant_id", "record_id", "volunteer_no") in _unique_column_sets(
        InternshipApplication
    )

    save_source = inspect.getsource(internship_application_service.save_my)
    assert 'volunteer = 0 if app_type == "SELF_ARRANGED"' in save_source
    assert "volunteer not in (1, 2, 3)" in save_source


def test_school_position_approval_must_land_through_existing_assignment_authority():
    source = inspect.getsource(internship_application_service.review_application)
    assert 'if app.application_type == "POSITION":' in source
    assert "student_svc.assign_position_in_tx(" in source


def test_position_publish_must_pass_existing_rights_gate():
    source = inspect.getsource(internship_position_service.set_status)
    assert 'elif action == "PUBLISH":' in source
    assert "evaluate_position_publishability(" in source
    assert 'p.rights_status = "COMPLIANT" if rights["passed"] else "NON_COMPLIANT"' in source
    assert 'p.status = "PUBLISHED"' in source


def test_staff_internship_bundle_remains_staff_only_and_enterprise_portal_is_not_mounted_there():
    deps_source = inspect.getsource(route_registration.build_deps)
    register_source = inspect.getsource(route_registration.register_internship_routes)

    assert "Depends(require_staff)" in deps_source
    assert 'Depends(require_module("internship"))' in deps_source
    assert 'd = deps["intern"]' in register_source
    assert "dependencies=d" in register_source

    # Future enterprise-facing routers must use their own enterprise-context guard instead of
    # piggybacking on the staff-only internship bundle.
    assert "internship_enterprise_portal" not in register_source


def test_forbidden_duplicate_authority_model_names_do_not_exist():
    import app.models as models

    for duplicate_name in (
        "EnterpriseJob",
        "InternshipRecruitmentJob",
        "StudentVolunteer",
        "PlacementResult",
    ):
        assert not hasattr(models, duplicate_name), (
            f"{duplicate_name} duplicates an already-frozen internship authority"
        )
