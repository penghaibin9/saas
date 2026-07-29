"""/api/v1 路由聚合。注册逻辑拆至 route_registration，路径与依赖保持兼容。"""
from __future__ import annotations

from fastapi import APIRouter
from fastapi.routing import APIRoute

from app.api.v1.route_registration import register_all_routes

api_router = APIRouter()
register_all_routes(api_router)

# 学工四端补充路由必须在既有路由完成注册后挂载；契约安装器随后修补已加载服务的
# version/permission/scope 绑定，不改任何其他业务域状态机。
from app.api.v1.affairs_activity_mobile import router as affairs_activity_mobile_router
from app.api.v1.affairs_appeal_mobile import router as affairs_appeal_mobile_router
from app.api.v1.affairs_appeal_repair_api import router as affairs_appeal_repair_router
from app.api.v1.affairs_four_end import router as affairs_four_end_router
from app.api.v1.affairs_leave_self_api import router as affairs_leave_self_router
from app.api.v1.affairs_operations_api import router as affairs_operations_router
from app.api.v1.affairs_student_dorm import router as affairs_student_dorm_router
from app.api.v1.affairs_student_returned import router as affairs_student_returned_router
from app.services.affairs_activity_accounting_guard import install as install_activity_accounting_guard
from app.services.affairs_activity_authority_guard import install as install_activity_authority_guard
from app.services.affairs_activity_code_service import install as install_activity_checkin_code
from app.services.affairs_activity_reconfirm_guard import install as install_activity_reconfirm_guard
from app.services.affairs_activity_reliability_service import install as install_activity_reliability
from app.services.affairs_aid_list_argument_guard import install as install_aid_list_argument_guard
from app.services.affairs_appeal_repair_scheduler import install as install_appeal_repair_scheduler
from app.services.affairs_appeal_repair_service import install as install_appeal_repair
from app.services.affairs_appeal_todo_service import install as install_appeal_todo_reconciliation
from app.services.affairs_archive_file_guard import install as install_archive_file_guard
from app.services.affairs_archive_guard import install as install_archive_guard
from app.services.affairs_batch_job_guard import install as install_batch_job_guard
from app.services.affairs_counselor_eval_guard import install as install_counselor_eval_guard
from app.services.affairs_counselor_handover_guard import install as install_counselor_handover_guard
from app.services.affairs_credit_appeal_reliability import install as install_credit_appeal_reliability
from app.services.affairs_data_integrity_guard import install as install_data_integrity_guard
from app.services.affairs_discipline_integrity_guard import install as install_discipline_integrity_guard
from app.services.affairs_dorm_checkout_guard import install as install_dorm_checkout_guard
from app.services.affairs_dorm_message_event_guard import install as install_dorm_message_event_guard
from app.services.affairs_dorm_node_guard import install as install_dorm_node_guard
from app.services.affairs_dorm_projection_service import install as install_dorm_projection
from app.services.affairs_dorm_reliability_service import install as install_dorm_reliability
from app.services.affairs_dorm_transfer_scope_guard import install as install_dorm_transfer_scope_guard
from app.services.affairs_four_end_contract import install as install_affairs_four_end_contract
from app.services.affairs_four_end_review_guard import install as install_affairs_four_end_review_guard
from app.services.affairs_four_end_terminal_guard import install as install_affairs_four_end_terminal_guard
from app.services.affairs_funding_ext_guard import install as install_funding_ext_guard
from app.services.affairs_history_dry_run_guard import install as install_history_dry_run_guard
from app.services.affairs_history_import_guard import install as install_history_import_guard
from app.services.affairs_operations_final_guard import install as install_affairs_operations_final_guard
from app.services.affairs_operations_service import install as install_affairs_operations
from app.services.affairs_publicity_guard import install as install_publicity_guard
from app.services.affairs_returned_view_service import install as install_returned_view_projection
from app.services.affairs_risk_evidence_guard import install as install_risk_evidence_guard
from app.services.affairs_risk_transfer_guard import install as install_risk_transfer_guard
from app.services.affairs_self_scope_guard import install as install_self_scope_guard
from app.services.affairs_sensitive_audit_guard import install as install_sensitive_audit_guard
from app.services.affairs_stats_integrity_guard import install as install_stats_integrity_guard
from app.services.affairs_student_application_lock import install as install_student_application_lock
from app.services.affairs_student_atomic_service import install as install_atomic_student_applications
from app.services.affairs_student_contract_security_guard import install as install_student_contract_security_guard
from app.services.affairs_student_contract_service import install as install_student_contract
from app.services.affairs_student_ledger_guard import install as install_student_ledger_guard
from app.services.affairs_talk_guard import install as install_talk_guard
from app.services.affairs_teacher_workbench_guard import install as install_teacher_workbench_guard


def _route_signature(route) -> tuple[str, frozenset[str]]:
    return str(getattr(route, "path", "")), frozenset(str(x).upper() for x in (getattr(route, "methods", None) or ()))


def _mount_supplemental_router(parent: APIRouter, child: APIRouter) -> None:
    """确定性挂载已构建好的补充 APIRoute。"""
    existing = {_route_signature(route) for route in parent.routes if isinstance(route, APIRoute)}
    for route in child.routes:
        if not isinstance(route, APIRoute):
            continue
        signature = _route_signature(route)
        if signature in existing:
            continue
        parent.routes.append(route)
        existing.add(signature)


_SUPPLEMENTAL_ROUTERS = (
    affairs_four_end_router,
    affairs_operations_router,
    affairs_student_dorm_router,
    affairs_activity_mobile_router,
    affairs_appeal_mobile_router,
    affairs_appeal_repair_router,
    affairs_student_returned_router,
    affairs_leave_self_router,
)

for supplemental_router in _SUPPLEMENTAL_ROUTERS:
    _mount_supplemental_router(api_router, supplemental_router)

install_affairs_four_end_contract()
install_aid_list_argument_guard()
install_sensitive_audit_guard()
install_returned_view_projection()
install_activity_checkin_code()
install_activity_reliability()
install_credit_appeal_reliability()
install_dorm_reliability()
install_dorm_projection()
install_dorm_checkout_guard()
install_atomic_student_applications()
install_student_application_lock()
install_appeal_todo_reconciliation()
install_appeal_repair()
install_self_scope_guard()
install_data_integrity_guard()
install_counselor_handover_guard()
install_risk_evidence_guard()
install_risk_transfer_guard()
install_counselor_eval_guard()
install_funding_ext_guard()
install_publicity_guard()
install_batch_job_guard()
install_archive_guard()
install_archive_file_guard()
install_talk_guard()
install_activity_accounting_guard()
install_activity_reconfirm_guard()
install_activity_authority_guard()
install_student_ledger_guard()
install_discipline_integrity_guard()
install_history_import_guard()
install_history_dry_run_guard()
install_stats_integrity_guard()
install_affairs_four_end_review_guard()
install_dorm_message_event_guard()
install_dorm_node_guard()
install_dorm_transfer_scope_guard()
install_student_contract()
install_student_contract_security_guard()
install_affairs_operations()
install_affairs_operations_final_guard()
install_teacher_workbench_guard()


def _finalize_route_registry_after_import_cycles() -> None:
    """所有模块完成初始化后重建父 Router，避免循环导入把半成品路由复制进 FastAPI。"""
    initial_count = len(api_router.routes)
    rebuilt = APIRouter()
    register_all_routes(rebuilt)
    for supplemental_router in _SUPPLEMENTAL_ROUTERS:
        _mount_supplemental_router(rebuilt, supplemental_router)

    # 保持 api_router 对象身份不变：循环导入期间已取得引用的模块也能看到最终路由表。
    api_router.routes[:] = rebuilt.routes

    paths = {
        str(route.path)
        for route in api_router.routes
        if isinstance(route, APIRoute)
    }
    required = {
        "/auth/login",
        "/academic-affairs/dashboard",
        "/portal/academic/transcript",
        "/mobile/academic/my",
        "/mobile/teacher/academic/tasks",
    }
    missing = sorted(required - paths)
    if missing:
        from app.api.v1 import academic as legacy_academic
        from app.api.v1 import auth as auth_api
        from app.modules.academic_affairs.routers import academic_affairs as aa_base

        sample = sorted(paths)[:20]
        raise RuntimeError(
            "API 路由最终注册不完整: "
            f"missing={missing}; initial={initial_count}; rebuilt={len(rebuilt.routes)}; "
            f"auth_child={len(auth_api.router.routes)}; legacy_child={len(legacy_academic.router.routes)}; "
            f"aa_base_child={len(aa_base.router.routes)}; sample={sample}"
        )


_finalize_route_registry_after_import_cycles()
install_affairs_four_end_terminal_guard(api_router)
install_appeal_repair_scheduler()
