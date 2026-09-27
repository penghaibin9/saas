from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.permissions import require_module, require_staff
from app.core.security import require_mobile_student
from app.core.student_portal_module_gate import enforce_student_portal_module_access
from app.api.v1 import auth_recovery, mobile_internship_context, mobile_internship_selection, mobile_internship_student
from app.student_portal.internship_router import router as student_portal_internship_router
from app.student_portal.internship_selection_router import router as student_portal_selection_router

from app.modules.internship.routers import (
    internship,
    internship_agreement_document,
    internship_agreement_template,
    internship_application,
    internship_archive,
    internship_communication,
    internship_complaint,
    internship_compliance,
    internship_enterprise_eval_versioned,
    internship_guardian_consent_delivery,
    internship_insurance,
    internship_match,
    internship_material_center,
    internship_participant,
    internship_plan,
    internship_position,
    internship_process,
    internship_recruitment_campaign,
    internship_score_appeal,
    internship_stats,
    internship_student,
    internship_visit_plan,
)

_STAFF_INTERNSHIP_DEPS = [
    Depends(require_staff),
    Depends(require_module("internship")),
]


def build_staff_internship_router() -> APIRouter:
    """Standalone school-side internship routes.

    Mirrors the canonical SaaS register_internship_routes() school/staff surface.
    Enterprise, student portal and mobile surfaces are intentionally mounted in
    later W2 cards so their identity boundaries cannot inherit staff access.
    """
    router = APIRouter()

    router.include_router(
        internship_material_center.router,
        dependencies=list(_STAFF_INTERNSHIP_DEPS),
    )

    for module in (
        internship,
        internship_position,
        internship_agreement_document,
        internship_agreement_template,
        internship_student,
        internship_match,
        internship_participant,
        internship_application,
        internship_archive,
        internship_stats,
        internship_plan,
        internship_insurance,
        internship_process,
        internship_communication,
        internship_visit_plan,
        internship_complaint,
        internship_compliance,
        internship_guardian_consent_delivery,
        internship_enterprise_eval_versioned,
        internship_recruitment_campaign,
        internship_score_appeal,
    ):
        router.include_router(
            module.router,
            dependencies=list(_STAFF_INTERNSHIP_DEPS),
        )
    return router


api_router = APIRouter()
api_router.include_router(auth_recovery.router)
api_router.include_router(build_staff_internship_router())


def build_student_mobile_router() -> APIRouter:
    router = APIRouter()
    student_dep = [Depends(require_mobile_student)]
    router.include_router(mobile_internship_student.router, dependencies=student_dep)
    router.include_router(mobile_internship_selection.router, dependencies=student_dep)
    return router


def build_student_portal_router() -> APIRouter:
    router = APIRouter()
    router.include_router(
        student_portal_internship_router,
        dependencies=[Depends(enforce_student_portal_module_access)],
    )
    # selection router already carries the same portal module gate internally.
    router.include_router(student_portal_selection_router)
    return router


def build_teacher_mobile_router() -> APIRouter:
    """Teacher mini-program surface; keep staff identity and internship module gates server-side."""
    router = APIRouter()
    router.include_router(
        mobile_internship_context.router,
        dependencies=[Depends(require_staff)],
    )
    return router


api_router.include_router(build_teacher_mobile_router())
api_router.include_router(build_student_mobile_router())
api_router.include_router(build_student_portal_router())
