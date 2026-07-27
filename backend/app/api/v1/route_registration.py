"""按域显式注册 /api/v1 路由。

保持主线既有路径、依赖、注册顺序与安全守卫；教务扩展 Router 必须在这里显式登记，
禁止依赖包导入副作用、运行时替换 Router 或通过注册顺序抢占重复路径。

当前长期分支早于主线部分毕业设计/实习安全扩展。为使分支可独立验证，又不在最终合并时
覆盖主线守卫，本文件仅在对应主线模块真实存在时启用扩展；模块存在但导入失败仍直接报错，
绝不吞掉实现错误。
"""
from __future__ import annotations

from importlib.util import find_spec

from fastapi import APIRouter, Depends

from app.core.config import settings
from app.core.graduation_permissions import require_graduation_request_permission
from app.core.permissions import require_module
from app.core.security import require_staff


def _module_exists(module_name: str) -> bool:
    return find_spec(module_name) is not None


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


def _academic_affairs_extension_routers():
    """返回使用独立 URL、无重复路径和无导入副作用的教务扩展 Router。"""
    from app.modules.academic_affairs.routers import (
        dashboard_readiness_router,
        dynamic_grade_router,
        exam_incident_closure_router,
        grade_task_identity_router,
        mobile_grade_entry_router,
        program_quality_router,
        semester_pilot_router,
        stats_snapshot_router,
        student_evaluation_router,
        student_exam_router,
        teaching_class_router,
        teaching_task_workbench_router,
        term_detail_router,
        textbook_closure_router,
    )

    return (
        dashboard_readiness_router,
        dynamic_grade_router,
        exam_incident_closure_router,
        grade_task_identity_router,
        mobile_grade_entry_router,
        program_quality_router,
        semester_pilot_router,
        stats_snapshot_router,
        student_evaluation_router,
        student_exam_router,
        teaching_class_router,
        teaching_task_workbench_router,
        term_detail_router,
        textbook_closure_router,
    )


def register_academic_affairs_extensions(api_router: APIRouter, deps: dict) -> None:
    for module in _academic_affairs_extension_routers():
        api_router.include_router(module.router, dependencies=deps["aa"])


def register_graduation_routes(api_router: APIRouter, deps: dict) -> None:
    if _module_exists("app.modules.graduation.services.graduation_consistency_install"):
        from app.modules.graduation.services.graduation_consistency_install import install_consistency_guards

        install_consistency_guards()

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
    sensitive_modules = (
        "app.modules.graduation.routers.graduation_p0_guard",
        "app.modules.graduation.routers.graduation_sensitive_router",
        "app.modules.graduation.routers.graduation_archive_sensitive_router",
        "app.modules.graduation.routers.graduation_material_sensitive_router",
        "app.modules.graduation.routers.graduation_extension",
    )
    if all(_module_exists(name) for name in sensitive_modules):
        from app.modules.graduation.routers import (
            graduation_archive_sensitive_router,
            graduation_extension,
            graduation_material_sensitive_router,
            graduation_p0_guard,
            graduation_sensitive_router,
        )

        api_router.include_router(graduation_p0_guard.router, dependencies=dependency)
        api_router.include_router(graduation_sensitive_router.router, dependencies=dependency)
        api_router.include_router(graduation_archive_sensitive_router.router, dependencies=dependency)
        api_router.include_router(graduation_material_sensitive_router.router, dependencies=dependency)
        api_router.include_router(
            graduation_extension.router,
            dependencies=[Depends(require_staff), Depends(require_module("graduation"))],
        )

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

    mobile_security_modules = (
        "app.core.mobile_graduation_permissions",
        "app.api.v1.mobile_graduation_extension_teacher",
        "app.api.v1.mobile_graduation_guard",
        "app.api.v1.mobile_graduation_teacher_context",
        "app.modules.graduation.services.graduation_record_resolver",
        "app.modules.graduation.services.graduation_mobile_stable_bridge",
        "app.modules.graduation.services.graduation_mobile_taskbook_bridge",
    )
    if all(_module_exists(name) for name in mobile_security_modules):
        from app.api.v1 import (
            mobile_graduation_extension_teacher,
            mobile_graduation_guard,
            mobile_graduation_teacher_context,
        )
        from app.core.mobile_graduation_permissions import require_mobile_graduation_request_permission
        from app.modules.graduation.services.graduation_mobile_stable_bridge import install_mobile_stable_bridge
        from app.modules.graduation.services.graduation_mobile_taskbook_bridge import install_mobile_taskbook_list_bridge
        from app.modules.graduation.services.graduation_record_resolver import install_mobile_resolver

        install_mobile_resolver()
        install_mobile_stable_bridge()
        install_mobile_taskbook_list_bridge()
        teacher_mobile_deps = [Depends(require_staff), Depends(require_module("graduation"))]
        api_router.include_router(mobile_graduation_extension_teacher.router, dependencies=teacher_mobile_deps)
        api_router.include_router(
            mobile_graduation_teacher_context.router,
            dependencies=[*teacher_mobile_deps, Depends(require_mobile_graduation_request_permission)],
        )
        api_router.include_router(mobile_graduation_guard.router)
        api_router.include_router(mobile.router, dependencies=[Depends(require_mobile_graduation_request_permission)])
    else:
        api_router.include_router(mobile.router)

    student_portal_security_modules = (
        "app.api.v1.mobile_internship_context",
        "app.api.v1.mobile_internship_leave_context",
        "app.api.v1.mobile_internship_student",
        "app.api.v1.student_portal_graduation_guard",
        "app.core.student_portal_module_gate",
        "app.student_portal.internship_router",
    )
    if all(_module_exists(name) for name in student_portal_security_modules):
        from app.api.v1 import (
            mobile_internship_context,
            mobile_internship_leave_context,
            mobile_internship_student,
            student_portal_graduation_guard,
        )
        from app.core.student_portal_module_gate import enforce_student_portal_module_access
        from app.student_portal.internship_router import router as student_portal_internship_router

        api_router.include_router(mobile_internship_context.router)
        api_router.include_router(mobile_internship_leave_context.router)
        api_router.include_router(mobile_internship_student.router)
        api_router.include_router(student_portal_graduation_guard.router)
        api_router.include_router(student_portal_router)
        api_router.include_router(
            student_portal_internship_router,
            dependencies=[Depends(enforce_student_portal_module_access)],
        )
    else:
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
    """保持主线注册顺序，并在主教务 Router 后追加独立扩展 Router。"""
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
    register_academic_affairs_extensions(api_router, deps)
    register_platform_routes(api_router)
