"""按域注册 /api/v1 路由（路径/依赖与历史 router.py 完全一致，仅拆分维护）。"""
from __future__ import annotations

import copy
import importlib

from fastapi import APIRouter, Depends
from fastapi.routing import APIRoute

from app.core.config import settings
from app.core.graduation_permissions import require_graduation_request_permission
from app.core.mobile_graduation_permissions import require_mobile_graduation_request_permission
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
    return {
        "gd": [Depends(require_staff), Depends(require_module("graduation")), Depends(require_graduation_request_permission)],
        "intern": [Depends(require_staff), Depends(require_module("internship"))],
        "employment": [Depends(require_staff), Depends(require_module("employment"))],
        "orientation": [Depends(require_staff), Depends(require_module("orientation"))],
        "sa": [Depends(require_staff), Depends(require_module("studentAffairs"))],
        "cs": [Depends(require_staff), Depends(require_module("campusService"))],
        "aa": [Depends(_require_aa_route_user)],
        "academic_legacy": [Depends(require_staff), Depends(require_module("academicAffairs"))],
    }


def _aa_route_signature(route: APIRoute) -> tuple[str, frozenset[str]]:
    return route.path, frozenset((route.methods or set()) - {"HEAD", "OPTIONS"})


def _prepare_academic_affairs_route_overrides():
    """临时替换模块级基础 Router，让嵌套聚合器永久引用过滤后的独立副本。"""
    from app.modules.academic_affairs.routers import academic_affairs as base_router
    from app.modules.academic_affairs.routers import academic_affairs_bundle as bundle
    from app.modules.academic_affairs.routers import scheduling_rule_router

    package = importlib.import_module(bundle.__package__)
    extension_routers: list[APIRouter] = []
    for module_name in bundle._EXTENSION_ROUTER_MODULES:
        module = getattr(package, module_name, None)
        if module is None:
            module = importlib.import_module(f"{bundle.__package__}.{module_name}")
        extension_routers.append(module.router)
    extension_routers.append(scheduling_rule_router.router)

    replacement_signatures = {
        _aa_route_signature(route)
        for child in extension_routers
        for route in child.routes
        if isinstance(route, APIRoute)
    }
    # scheduling_rule_router 会在服务 Facade 循环导入期间短暂暴露空 Router；这三条是其
    # 明确声明的同 URL 契约修正，必须无条件替换旧总路由，不能依赖导入时机。
    replacement_signatures.update({
        ("/academic-affairs/scheduling/rules", frozenset({"PUT"})),
        ("/academic-affairs/scheduling/rules", frozenset({"GET"})),
        ("/academic-affairs/scheduling/rules/{rule_id}", frozenset({"DELETE"})),
    })

    original_router = base_router.router
    filtered_router = copy.copy(original_router)
    filtered_router.routes = [
        route
        for route in original_router.routes
        if not isinstance(route, APIRoute) or _aa_route_signature(route) not in replacement_signatures
    ]
    # FastAPI 0.139+ 的 include_router 保存子 Router 引用而非立即扁平复制。必须临时替换
    # 整个 Router 对象，不能修改后再恢复同一个对象的 routes，否则重复路由会重新出现。
    base_router.router = filtered_router
    return base_router, original_router


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
        internship, internship_agreement_template, internship_application, internship_archive,
        internship_communication, internship_complaint, internship_compliance,
        internship_enterprise_eval_versioned, internship_insurance,
        internship_match, internship_material_center, internship_participant,
        internship_plan, internship_position, internship_process, internship_stats,
        internship_student, internship_visit_plan,
    )
    d = deps["intern"]
    # 安全优先路由必须先于旧协议/保险/报告/归档路由注册。
    api_router.include_router(internship_material_center.router, dependencies=d)
    for r in (
        internship, internship_position, internship_agreement_template, internship_student,
        internship_match, internship_participant, internship_application, internship_archive,
        internship_stats, internship_plan, internship_insurance, internship_process,
        internship_communication, internship_visit_plan, internship_complaint, internship_compliance,
        internship_enterprise_eval_versioned,
    ):
        api_router.include_router(r.router, dependencies=d)


def register_student_affairs_routes(api_router: APIRouter, deps: dict) -> None:
    from app.api.v1 import campus_service, orientation, student_affairs
    api_router.include_router(orientation.router, dependencies=deps["orientation"])
    api_router.include_router(campus_service.router, dependencies=deps["cs"])
    api_router.include_router(student_affairs.router, dependencies=deps["sa"])


def register_academic_affairs_routes(api_router: APIRouter, deps: dict) -> None:
    from app.api.v1 import academic
    from app.modules.academic_affairs.routers import academic_affairs_bundle as academic_affairs
    base_router, original_router = _prepare_academic_affairs_route_overrides()
    try:
        academic_affairs.router = academic_affairs.build_router()
    finally:
        base_router.router = original_router
    api_router.include_router(academic.router, dependencies=deps["academic_legacy"])
    api_router.include_router(academic_affairs.router, dependencies=deps["aa"])


def register_graduation_routes(api_router: APIRouter, deps: dict) -> None:
    from app.modules.graduation.routers import (
        graduation, graduation_archive, graduation_archive_sensitive_router, graduation_batch,
        graduation_defense_score, graduation_extension, graduation_grade, graduation_guidance,
        graduation_material_center, graduation_material_sensitive_router, graduation_mentor,
        graduation_midterm, graduation_more, graduation_p0_guard, graduation_review,
        graduation_risk, graduation_sensitive_router, graduation_stats, graduation_student,
        graduation_student_eval, graduation_taskbook, graduation_template,
        graduation_topic, graduation_topic_change, graduation_topic_round,
    )
    d = deps["gd"]
    api_router.include_router(graduation_p0_guard.router, dependencies=d)
    api_router.include_router(graduation_sensitive_router.router, dependencies=d)
    api_router.include_router(graduation_archive_sensitive_router.router, dependencies=d)
    api_router.include_router(graduation_material_sensitive_router.router, dependencies=d)
    # Legacy fixed paths precede Stage-6 dynamic detail paths; legacy detail/review
    # endpoints already delegate to the authoritative public-version service.
    api_router.include_router(graduation.router, dependencies=d)
    api_router.include_router(graduation_material_center.router, dependencies=d)
    api_router.include_router(
        graduation_extension.router,
        dependencies=[Depends(require_staff), Depends(require_module("graduation"))],
    )
    # Frozen semantic order marker used by production gates:
    # graduation, graduation_batch, graduation_student
    for r in (
        graduation_batch, graduation_student, graduation_topic,
        graduation_topic_round, graduation_topic_change, graduation_mentor,
        graduation_taskbook, graduation_guidance, graduation_midterm,
        graduation_student_eval, graduation_review, graduation_defense_score,
        graduation_grade, graduation_risk, graduation_archive, graduation_stats,
        graduation_template, graduation_more,
    ):
        api_router.include_router(r.router, dependencies=d)


def register_platform_routes(api_router: APIRouter) -> None:
    from app.api.v1 import (
        audit, dashboard, data_exchange, feedback, implementation, import_export,
        migration, mobile, mobile_export, mobile_graduation_extension_teacher,
        mobile_graduation_guard, mobile_graduation_material_center,
        mobile_graduation_teacher_context, mobile_orientation_teacher,
        mobile_internship_context, mobile_internship_leave_context, mobile_internship_student,
        national_standards, notification, onboarding, org_directory, platform, stats,
        student_portal_graduation_guard, system, transfer, user_preference,
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
    api_router.include_router(data_exchange.router)
    api_router.include_router(transfer.router)
    api_router.include_router(migration.router)
    api_router.include_router(migration.platform_router)
    api_router.include_router(audit.router)
    api_router.include_router(audit.alias_router)
    api_router.include_router(platform.router)
    api_router.include_router(stats.router)
    api_router.include_router(mobile_export.router)
    api_router.include_router(mobile_orientation_teacher.router)

    teacher_mobile_deps = [Depends(require_staff), Depends(require_module("graduation"))]
    api_router.include_router(mobile_graduation_extension_teacher.router, dependencies=teacher_mobile_deps)
    api_router.include_router(
        mobile_graduation_teacher_context.router,
        dependencies=[*teacher_mobile_deps, Depends(require_mobile_graduation_request_permission)],
    )
    # 与旧移动端相同 URL，必须先于旧移动端聚合 Router 注册。
    api_router.include_router(
        mobile_graduation_material_center.router,
        dependencies=[Depends(require_mobile_graduation_request_permission)],
    )
    api_router.include_router(mobile_graduation_guard.router)
    from app.core.mobile_internship_permission_gate import enforce_teacher_internship_mobile_permission
    api_router.include_router(
        mobile.router,
        dependencies=[
            Depends(require_mobile_graduation_request_permission),
            Depends(enforce_teacher_internship_mobile_permission),
        ],
    )
    from app.core.student_portal_module_gate import enforce_student_portal_module_access
    from app.student_portal.internship_router import router as student_portal_internship_router
    api_router.include_router(mobile_internship_context.router)
    api_router.include_router(mobile_internship_leave_context.router)
    api_router.include_router(mobile_internship_student.router)
    api_router.include_router(student_portal_graduation_guard.router)
    api_router.include_router(student_portal_router)
    portal_gate = [Depends(enforce_student_portal_module_access)]
    api_router.include_router(student_portal_internship_router, dependencies=portal_gate)
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
    from app.api.v1 import academic, approval, campus_service, excel, orientation, student, student_affairs
    from app.modules.academic_affairs.routers import academic_affairs_bundle as academic_affairs
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
    base_router, original_router = _prepare_academic_affairs_route_overrides()
    try:
        academic_affairs.router = academic_affairs.build_router()
    finally:
        base_router.router = original_router
    api_router.include_router(academic_affairs.router, dependencies=deps["aa"])
    register_platform_routes(api_router)
