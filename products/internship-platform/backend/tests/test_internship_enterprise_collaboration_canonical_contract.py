"""E0: freeze the existing internship authorities before enterprise-collaboration expansion.

This suite is intentionally DB-free. It protects ownership and routing boundaries so later
E-series cards can only extend the current domain instead of creating duplicate facts.
"""
from __future__ import annotations

import inspect

from sqlalchemy import UniqueConstraint

from app.api import router as standalone_api_router
import app.models as models
from app.models import (
    EmpCompany,
    InternshipApplication,
    InternshipIntention,
    InternshipPosition,
)
from app.modules.internship.services import (
    internship_application_service,
    internship_enterprise_collaboration_service,
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

    # Standalone must not pull the employment-domain job authority back into the extracted product.
    assert not hasattr(models, "EmpJob")


def test_formal_application_owns_three_slots_and_intention_stays_separate():
    assert InternshipApplication.__tablename__ == "t_internship_application"
    assert InternshipIntention.__tablename__ == "t_internship_intention"
    assert InternshipApplication.__table__.name != InternshipIntention.__table__.name
    uniques = _unique_column_sets(InternshipApplication)
    # N-1 legacy writers keep their physical record_id uniqueness unchanged while V3 rows use
    # the additive campaign_record_id namespace for per-round history.
    assert ("tenant_id", "record_id", "volunteer_no") in uniques
    assert (
        "tenant_id",
        "campaign_record_id",
        "campaign_id",
        "volunteer_no",
    ) in uniques

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
    publish_block = source.split('elif action == "PUBLISH":', 1)[1].split('elif action == "OFFLINE":', 1)[0]
    assert "evaluate_position_publishability(" in publish_block
    assert 'p.rights_status = "COMPLIANT" if rights["passed"] else "NON_COMPLIANT"' in publish_block
    gate_at = publish_block.index('if not rights["passed"]:')
    rejection_at = publish_block.index('raise AppException("DATA_CONFLICT"', gate_at)
    publish_at = publish_block.index('p.status = "PUBLISHED"')
    assert gate_at < rejection_at < publish_at, (
        "failed rights evaluation must reject before the position can become PUBLISHED"
    )


def test_staff_internship_bundle_remains_staff_only_and_enterprise_portal_is_separately_guarded():
    source = inspect.getsource(standalone_api_router)

    # Standalone school/staff routes inherit the same two server-side gates.
    assert "_STAFF_INTERNSHIP_DEPS" in source
    assert "Depends(require_staff)" in source
    assert 'Depends(require_module("internship"))' in source
    assert "dependencies=list(_STAFF_INTERNSHIP_DEPS)" in source

    # Enterprise portal/collaboration routers are mounted outside that bundle and keep
    # their signed EnterprisePrincipal/grant boundaries.
    assert "api_router.include_router(internship_enterprise_portal.router)" in source
    assert "api_router.include_router(internship_enterprise_collaboration.router)" in source
    assert "internship_enterprise_portal.router, dependencies=list(_STAFF_INTERNSHIP_DEPS)" not in source
    assert "internship_enterprise_collaboration.router, dependencies=list(_STAFF_INTERNSHIP_DEPS)" not in source


def test_forbidden_duplicate_authority_model_names_do_not_exist():
    for duplicate_name in (
        "EnterpriseCompany",
        "EnterpriseJob",
        "EnterpriseUser",
        "InternshipRecruitmentJob",
        "StudentVolunteer",
        "PlacementResult",
        "RecruitmentApplication",
    ):
        assert not hasattr(models, duplicate_name), (
            f"{duplicate_name} duplicates an already-frozen internship authority"
        )



def test_enterprise_collaboration_filters_keep_status_and_deeplink_scopes_separate():
    status_source = inspect.getsource(internship_enterprise_collaboration_service._filter_record_status)
    evaluation_source = inspect.getsource(internship_enterprise_collaboration_service.list_evaluation_tasks_in_tx)

    # Status filtering must be a pure transformation of q; a previous regression referenced
    # free variables named internship_id/base and crashed every real enterprise student list.
    assert "internship_id" not in status_source
    assert "base =" not in status_source
    assert "return q" in status_source

    # Deep-link evaluation lookup is a different concern and must narrow the evaluation query.
    assert "if internship_id is not None:" in evaluation_source
    assert "InternshipRecord.id == int(internship_id)" in evaluation_source
