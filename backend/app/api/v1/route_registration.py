"""按域注册 /api/v1 路由（路径/依赖与历史 router.py 完全一致，仅拆分维护）。"""
from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.config import settings
from app.core.graduation_permissions import require_graduation_request_permission
from app.core.permissions import require_module
from app.core.security import require_staff


def _require_aa_route_user(user=Depends(require_module("academicAffairs"))):
    from app.core.exceptions import no_permission
    from app.core.security import STAFF_USER_TYPES
    ut = (user.get("userType") or "").strip().upper()
    if ut == "STUDENT":
        return user
    if ut not in STAFF_USER_TYPES:
        raise no_permission("该接口仅教职工可用，请使用个人/家长门户")
    return user


def build_deps():
    """统一模块门禁依赖；禁止在注册处再手工拼装导致漂移。"""
    return {
        "gd": [
            Depends(require_staff),
            Depends(require_module("graduation")),
            Depends(require_graduation_request_permission),
        ],
        "intern": [Depends(require_staff), Depends(require_module("internship"))],
        "employment": [Depends(require_staff), Depends(require_module("employment"))],
        "orientation": [Depends(require_staff), Depends(require_module("orientation"))],
        "sa": [Depends(require_staff), Depends(require_module("studentAffairs"))],
        "cs": [Depends(require_staff), Depends(require_module("campusService"))],
        "aa": [Depends(_require_aa_route_user)],
        "academic_legacy": [Depends(require_staff), Depends(require_module("academicAffairs"))],
    }


def register_core_routes(api_router: APIRouter) -> None:
    from app.api.v1 import auth, authz, files, rbac, tenant
    from app.api.v1 import file as file_simple

    api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
    api_router.include_router(authz.router)
    api_router.include_router(tenant.router, prefix="/tenant", tags=["tenant"])
    api_router.include_router(rbac.router, prefix="/rbac", tags=["rbac"])
    api_router.include_router(files.router)
    api_router.include_router(file_simple.router, prefix="/files", tags=["files"])
    if not settings.is_prod:
        api_router.include_router(file_simple.placeholder_router, prefix="/files", tags=["files-placeholder"])


def register_internship_routes(api_router: APIRouter, deps: dict) -> None:
    from app.modules.internship.routers import (
        internship,
        internship_agreement_template,
        internship_application,
        internship_archive,
        internship_communication,
        internship_complaint,
        internship_compliance,
        internship_insurance,
        internship_match,
        internship_participant,
        internship_plan,
        internship_position,
        internship_process,
        internship_stats,
        internship_student,
        internship_visit_plan,
    )

    d = deps["intern"]
    api_router.include_router(internship.router, dependencies=d)
    api_router.include_router(internship_position.router, dependencies=d)
    api_router.include_router(internship_agreement_template.router, dependencies=d)
    api_router.include_router(internship_student.router, dependencies=d)
    api_router.include_router(internship_match.router, dependencies=d)
    # 批次参与人（组织范围选人，替代反复导 Excel 名单）
    api_router.include_router(internship_participant.router, dependencies=d)
    api_router.include_router(internship_application.router, dependencies=d)
    api_router.include_router(internship_archive.router, dependencies=d)
    api_router.include_router(internship_stats.router, dependencies=d)
    api_router.include_router(internship_plan.router, dependencies=d)
    api_router.include_router(internship_insurance.router, dependencies=d)
    api_router.include_router(internship_process.router, dependencies=d)
    api_router.include_router(internship_communication.router, dependencies=d)
    api_router.include_router(internship_visit_plan.router, dependencies=d)
    api_router.include_router(internship_complaint.router, dependencies=d)
    api_router.include_router(internship_compliance.router, dependencies=d)


def register_student_affairs_routes(api_router: APIRouter, deps: dict) -> None:
    from app.api.v1 import campus_service, orientation, student_affairs

    api_router.include_router(orientation.router, dependencies=deps["orientation"])
    api_router.include_router(campus_service.router, dependencies=deps["cs"])
    api_router.include_router(student_affairs.router, dependencies=deps["sa"])


def register_academic_affairs_routes(api_router: APIRouter, deps: dict) -> None:
    from app.api.v1 import academic
    from app.modules.academic_affairs.routers import academic_affairs

    api_router.include_router(academic.router, dependencies=deps["academic_legacy"])
    api_router.include_router(academic_affairs.router, dependencies=deps["aa"])


def register_graduation_routes(api_router: APIRouter, deps: dict) -> None:
    from app.modules.graduation.routers import (
        graduation,
        graduation_archive,
        graduation_batch,
        graduation_defense_score,
        graduation_grade,
        graduation_guidance,
        graduation_mentor,
        graduation_midterm,
        graduation_more,
        graduation_review,
        graduation_risk,
        graduation_stats,
        graduation_student,
        graduation_student_eval,
        graduation_taskbook,
        graduation_template,
        graduation_topic,
        graduation_topic_change,
        graduation_topic_round,
    )

    d = deps["gd"]
    for r in (
        graduation, graduation_batch, graduation_student, graduation_topic,
        graduation_topic_round, graduation_topic_change, graduation_mentor,
        graduation_taskbook, graduation_guidance, graduation_midterm,
        graduation_student_eval, graduation_review, graduation_defense_score,
        graduation_grade, graduation_risk, graduation_archive, graduation_stats,
        graduation_template, graduation_more,
    ):
        api_router.include_router(r.router, dependencies=d)


def register_platform_routes(api_router: APIRouter) -> None:
    from app.api.v1 import (
        audit, dashboard, feedback, implementation, import_export,
        migration, mobile, mobile_export, mobile_orientation_teacher,
        national_standards, notification, onboarding, org_directory, platform, stats, system,
        transfer, user_preference,
    )
    from app.api.v1 import message as message_simple
    from app.api.v1 import message_center as message_center_api
    from app.api.v1 import todo as todo_simple
    from app.api.v1.todos import make_router as make_todos_router
    from app.student_portal.router import router as student_portal_router

    api_router.include_router(dashboard.router, prefix="/dashboard", tags=["dashboard"])
    api_router.include_router(todo_simple.router, prefix="/todos", tags=["todos"])
    api_router.include_router(message_simple.router, prefix="/messages", tags=["messages"])
    api_router.include_router(make_todos_router("admin"))
    api_router.include_router(make_todos_router("student-mini"))
    api_router.include_router(make_todos_router("teacher-mobile"))
    api_router.include_router(message_center_api.router)
    api_router.include_router(import_export.import_router, prefix="/import", tags=["import-export"])
    api_router.include_router(import_export.export_router, prefix="/export", tags=["import-export"])
    api_router.include_router(transfer.router)
    api_router.include_router(migration.router)
    api_router.include_router(migration.platform_router)
    api_router.include_router(audit.router)
    api_router.include_router(audit.alias_router)
    api_router.include_router(platform.router)
    api_router.include_router(stats.router)
    api_router.include_router(mobile_export.router)
    api_router.include_router(mobile_orientation_teacher.router)
    api_router.include_router(mobile.router)
    api_router.include_router(student_portal_router)
    from app.api.v1 import student_portal_admin
    api_router.include_router(student_portal_admin.router)
    api_router.include_router(onboarding.router)
    api_router.include_router(implementation.router)
    api_router.include_router(national_standards.router)
    api_router.include_router(national_standards.platform_router)
    api_router.include_router(notification.router)
    api_router.include_router(user_preference.router)
    api_router.include_router(feedback.router)
    api_router.include_router(system.router, tags=["system"])
    # 组织目录：选人场景（实习/毕设批次、评奖）共用的组织树与年级源，按本人数据范围裁剪
    api_router.include_router(org_directory.router)


def register_all_routes(api_router: APIRouter) -> None:
    """注册顺序与拆分前 router.py 一致。"""
    from app.api.v1 import academic, approval, campus_service, excel, orientation, student, student_affairs
    from app.modules.academic_affairs.routers import academic_affairs
    from app.modules.employment.routers import employment

    deps = build_deps()
    register_core_routes(api_router)
    api_router.include_router(student.router)
    api_router.include_router(approval.router)
    register_internship_routes(api_router, deps)
    api_router.include_router(orientation.router, dependencies=deps["orientation"])
    api_router.include_router(campus_service.router, dependencies=deps["cs"])
    api_router.include_router(academic.router, dependencies=deps["academic_legacy"])
    register_graduation_routes(api_router, deps)
    api_router.include_router(excel.router)
    api_router.include_router(employment.router, dependencies=deps["employment"])
    api_router.include_router(student_affairs.router, dependencies=deps["sa"])
    api_router.include_router(academic_affairs.router, dependencies=deps["aa"])
    register_platform_routes(api_router)
