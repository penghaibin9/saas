"""按域显式注册 /api/v1 路由。

禁止依赖包导入副作用修改 Router；所有新增路由必须在这里明确登记。
重复路径必须先合并回原 Router，不能通过运行时删除旧 APIRoute 抢占。
"""
from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.config import settings
from app.core.graduation_permissions import require_graduation_request_permission
from app.core.permissions import require_module
from app.core.security import require_staff


def _require_aa_route_user(user=Depends(require_module("academicAffairs"))):
    from app.core.exceptions import no_permission
    from app.core.security import STAFF_USER_TYPES

    user_type = (user.get("userType") or "").strip().upper()
    if user_type == "STUDENT":
        return user
    if user_type not in STAFF_USER_TYPES:
        raise no_permission("该接口仅教职工可用，请使用个人/家长门户")
    return user


def build_deps():
    """统一模块门禁依赖，禁止在注册处重复拼装。"""
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

    dependency = deps["intern"]
    for module in (
        internship,
        internship_position,
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
    ):
        api_router.include_router(module.router, dependencies=dependency)


def register_student_affairs_routes(api_router: APIRouter, deps: dict) -> None:
    from app.api.v1 import campus_service, orientation, student_affairs

    api_router.include_router(orientation.router, dependencies=deps["orientation"])
    api_router.include_router(campus_service.router, dependencies=deps["cs"])
    api_router.include_router(student_affairs.router, dependencies=deps["sa"])


def _academic_affairs_extension_routers():
    """只返回已确认独立、无重复路径、无导入副作用的教务扩展 Router。

    看板、学期详情、教学班、教学任务工作台、成绩身份、排课规则、考场异常、
    教材闭环和教师移动批量成绩仍依赖待收口包装层；合并回原 Service 前不注册，
    避免清理期暴露运行时才失败的半成品入口。
    """
    from app.modules.academic_affairs.routers import (
        dynamic_grade_router,
        program_quality_router,
        semester_pilot_router,
        stats_snapshot_router,
        student_exam_router,
    )

    return (
        dynamic_grade_router,
        program_quality_router,
        semester_pilot_router,
        stats_snapshot_router,
        student_exam_router,
    )


def register_academic_affairs_routes(api_router: APIRouter, deps: dict) -> None:
    from app.api.v1 import academic
    from app.modules.academic_affairs.routers import academic_affairs

    api_router.include_router(academic.router, dependencies=deps["academic_legacy"])
    api_router.include_router(academic_affairs.router, dependencies=deps["aa"])
    for module in _academic_affairs_extension_routers():
        api_router.include_router(module.router, dependencies=deps["aa"])


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

    dependency = deps["gd"]
    for module in (
        graduation,
        graduation_batch,
        graduation_student,
        graduation_topic,
        graduation_topic_round,
        graduation_topic_change,
        graduation_mentor,
        graduation_taskbook,
        graduation_guidance,
        graduation_midterm,
        graduation_student_eval,
        graduation_review,
        graduation_defense_score,
        graduation_grade,
        graduation_risk,
        graduation_archive,
        graduation_stats,
        graduation_template,
        graduation_more,
    ):
        api_router.include_router(module.router, dependencies=dependency)


def register_platform_routes(api_router: APIRouter) -> None:
    from app.api.v1 import (
        audit,
        dashboard,
        feedback,
        implementation,
        import_export,
        migration,
        mobile,
        mobile_export,
        mobile_orientation_teacher,
        national_standards,
        notification,
        onboarding,
        org_directory,
        platform,
        stats,
        system,
        transfer,
        user_preference,
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
    api_router.include_router(org_directory.router)


def register_all_routes(api_router: APIRouter) -> None:
    """注册顺序与拆分前 router.py 保持一致。"""
    from app.api.v1 import approval, excel, student
    from app.modules.employment.routers import employment

    deps = build_deps()
    register_core_routes(api_router)
    api_router.include_router(student.router)
    api_router.include_router(approval.router)
    register_internship_routes(api_router, deps)
    register_student_affairs_routes(api_router, deps)
    register_academic_affairs_routes(api_router, deps)
    register_graduation_routes(api_router, deps)
    api_router.include_router(excel.router)
    api_router.include_router(employment.router, dependencies=deps["employment"])
    register_platform_routes(api_router)
