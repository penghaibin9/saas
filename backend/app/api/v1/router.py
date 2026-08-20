"""/api/v1 路由聚合。注册逻辑拆至 route_registration，路径与依赖保持兼容。"""
from __future__ import annotations

from fastapi import APIRouter
from fastapi.routing import APIRoute

from app.api.v1.route_registration import register_all_routes
# 必须早于 register_all_routes：sandbox_story_api 会先把 platform.router 的历史
# reset-sandbox-data 原位替换。这样即使循环导入导致应用提前复制主 Router，
# 拿到的也已经是 standard-20k/legacy-100 兼容语义。
from app.api.v1.sandbox_story_api import router as sandbox_story_router

api_router = APIRouter()
register_all_routes(api_router)

# 学工四端补充路由必须在既有路由完成注册后挂载；阶段 5 材料与归档服务通过
# 显式 Facade/正式 Service 接入，不再在启动时替换业务函数。
from app.api.v1.affairs_activity_mobile import router as affairs_activity_mobile_router
from app.api.v1.affairs_appeal_mobile import router as affairs_appeal_mobile_router
from app.api.v1.affairs_appeal_repair_api import router as affairs_appeal_repair_router
from app.api.v1.affairs_discipline_integrity_api import router as affairs_discipline_integrity_router
from app.api.v1.affairs_four_end import router as affairs_four_end_router
from app.api.v1.affairs_funding_authority_api import router as affairs_funding_authority_router
from app.api.v1.affairs_leave_self_api import router as affairs_leave_self_router
from app.api.v1.affairs_operations_api import router as affairs_operations_router
from app.api.v1.affairs_student_dorm import router as affairs_student_dorm_router
from app.api.v1.affairs_student_returned import router as affairs_student_returned_router
from app.api.v1.auth_browser import router as auth_browser_router
from app.api.v1.control_plane_auth import router as control_plane_auth_router
from app.api.v1.data_center import router as data_center_router
from app.api.v1.help_metrics import router as help_metrics_router
from app.api.v1.mobile_academic_status import router as mobile_academic_status_router
from app.api.v1.mobile_performance import router as mobile_performance_router
from app.modules.student_affairs.routers.affairs_material_center import router as affairs_material_center_router
from app.services.affairs_activity_authority_guard import install as install_activity_authority_guard
from app.services.affairs_activity_code_service import install as install_activity_checkin_code
from app.services.affairs_activity_reliability_service import install as install_activity_reliability
from app.services.affairs_batch_job_guard import install as install_batch_job_guard
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
from app.services.affairs_funding_authority_service import install as install_funding_authority
from app.services.affairs_history_dry_run_guard import install as install_history_dry_run_guard
from app.services.affairs_history_import_guard import install as install_history_import_guard
from app.services.affairs_risk_evidence_guard import install as install_risk_evidence_guard
from app.services.affairs_risk_transfer_guard import install as install_risk_transfer_guard
from app.services.affairs_stats_integrity_guard import install as install_stats_integrity_guard
from app.services.affairs_student_application_lock import install as install_student_application_lock
from app.services.affairs_student_atomic_service import install as install_atomic_student_applications
from app.services.affairs_student_contract_security_guard import install as install_student_contract_security_guard
from app.services.affairs_student_contract_service import install as install_student_contract
from app.services.affairs_student_ledger_guard import install as install_student_ledger_guard
from app.services.affairs_talk_guard import install as install_talk_guard
from app.services.control_plane_p0_auth_guard import install as install_control_plane_p0_auth_guard
from app.services.control_plane_p0_dr_guard import install as install_control_plane_p0_dr_guard


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


# standard-20k 的兼容路由已经在 register_all_routes 前注入 platform.router。
# 此处仍执行一次签名去重再挂载同一 replacement，保证历史导入时序和普通导入时序
# 最终都只有一个公开 POST 路由。
_RESET_SANDBOX_PATH = "/platform/tenants/{tenant_id}/reset-sandbox-data"
_AUTH_P0_REPLACEMENTS = {
    "/auth/captcha",
    "/auth/login",
    "/auth/refresh",
    "/auth/change-password",
    "/auth/wx-bind",
}
api_router.routes[:] = [
    route for route in api_router.routes
    if not (
        isinstance(route, APIRoute)
        and (
            (
                str(getattr(route, "path", "")) == _RESET_SANDBOX_PATH
                and "POST" in {str(x).upper() for x in (getattr(route, "methods", None) or ())}
            )
            or (
                str(getattr(route, "path", "")) in _AUTH_P0_REPLACEMENTS
                and "POST" in {str(x).upper() for x in (getattr(route, "methods", None) or ())}
            )
        )
    )
]

for supplemental_router in (
    sandbox_story_router,
    control_plane_auth_router,
    auth_browser_router,
    affairs_material_center_router,
    affairs_four_end_router,
    affairs_operations_router,
    affairs_funding_authority_router,
    affairs_discipline_integrity_router,
    affairs_student_dorm_router,
    affairs_activity_mobile_router,
    affairs_appeal_mobile_router,
    affairs_appeal_repair_router,
    affairs_student_returned_router,
    affairs_leave_self_router,
    mobile_academic_status_router,
    mobile_performance_router,
    data_center_router,
    help_metrics_router,
):
    _mount_supplemental_router(api_router, supplemental_router)

# Control-plane authorities are installed after legacy modules/routes exist but
# before the application serves requests.  This preserves public contracts while
# moving enforcement to the production authority implementations.
install_control_plane_p0_auth_guard()
install_control_plane_p0_dr_guard()

install_affairs_four_end_contract()
install_activity_checkin_code()
install_activity_reliability()
install_dorm_reliability()
install_dorm_projection()
install_dorm_checkout_guard()
install_atomic_student_applications()
install_student_application_lock()
install_data_integrity_guard()
install_risk_evidence_guard()
install_risk_transfer_guard()
install_batch_job_guard()
install_talk_guard()
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
install_funding_authority()
install_affairs_four_end_terminal_guard(api_router)
