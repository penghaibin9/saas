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
from app.api.v1.affairs_student_dorm import router as affairs_student_dorm_router
from app.api.v1.affairs_student_returned import router as affairs_student_returned_router
from app.services.affairs_activity_accounting_guard import install as install_activity_accounting_guard
from app.services.affairs_activity_authority_guard import install as install_activity_authority_guard
from app.services.affairs_activity_code_service import install as install_activity_checkin_code
from app.services.affairs_activity_reliability_service import install as install_activity_reliability
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
from app.services.affairs_dorm_node_guard import install as install_dorm_node_guard
from app.services.affairs_dorm_projection_service import install as install_dorm_projection
from app.services.affairs_dorm_reliability_service import install as install_dorm_reliability
from app.services.affairs_four_end_contract import install as install_affairs_four_end_contract
from app.services.affairs_four_end_review_guard import install as install_affairs_four_end_review_guard
from app.services.affairs_four_end_terminal_guard import install as install_affairs_four_end_terminal_guard
from app.services.affairs_funding_ext_guard import install as install_funding_ext_guard
from app.services.affairs_history_dry_run_guard import install as install_history_dry_run_guard
from app.services.affairs_history_import_guard import install as install_history_import_guard
from app.services.affairs_publicity_guard import install as install_publicity_guard
from app.services.affairs_returned_view_service import install as install_returned_view_projection
from app.services.affairs_risk_evidence_guard import install as install_risk_evidence_guard
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
    """确定性挂载已构建好的补充 APIRoute。

    当前 FastAPI 依赖范围内，项目运行环境出现 ``include_router`` 未复制这些后置构建路由的情况；
    子路由没有额外 prefix 或 include 级 dependencies，APIRoute 已包含端点依赖、响应模型、标签与方法，
    因此按 path+method 去重后直接加入聚合器。随后终态安全门仍会逐条验证权限登记，禁止静默漏挂。
    """
    existing = {_route_signature(route) for route in parent.routes if isinstance(route, APIRoute)}
    for route in child.routes:
        if not isinstance(route, APIRoute):
            continue
        signature = _route_signature(route)
        if signature in existing:
            continue
        parent.routes.append(route)
        existing.add(signature)


for supplemental_router in (
    affairs_four_end_router,
    affairs_student_dorm_router,
    affairs_activity_mobile_router,
    affairs_appeal_mobile_router,
    affairs_appeal_repair_router,
    affairs_student_returned_router,
):
    _mount_supplemental_router(api_router, supplemental_router)

install_affairs_four_end_contract()
install_sensitive_audit_guard()
install_returned_view_projection()
install_activity_checkin_code()
install_activity_reliability()
install_credit_appeal_reliability()
install_dorm_reliability()
install_dorm_projection()
install_atomic_student_applications()
# 原子申请入口安装后，再把本人解析收紧为同学生行锁，序列化并发重复提交。
install_student_application_lock()
# 必须在核心申诉实现完成后安装，包装具体受理人待办和结果消息。
install_appeal_todo_reconciliation()
install_appeal_repair()
# 将补偿队列接入现有学工周期扫描，避免一次孤立失败长期等待人工或下一次写请求。
install_appeal_repair_scheduler()
# SELF 必须先由服务端账号关系解析，后续画像、二课和申诉只能访问本人。
install_self_scope_guard()
# 核心审计安全门必须在既有兼容层之后安装，避免后续补丁再次放宽数据口径。
install_data_integrity_guard()
install_counselor_handover_guard()
install_risk_evidence_guard()
install_counselor_eval_guard()
install_funding_ext_guard()
# 公示和批处理扫描统一在归档/统计之前使用正式期限、数据范围和MySQL行锁。
install_publicity_guard()
install_batch_job_guard()
install_archive_guard()
install_archive_file_guard()
install_talk_guard()
install_activity_accounting_guard()
install_activity_authority_guard()
install_student_ledger_guard()
install_discipline_integrity_guard()
# 历史导入先安装共享存储/完整副作用，再安装“错行整批失败”修正层。
install_history_import_guard()
install_history_dry_run_guard()
install_stats_integrity_guard()
# 先安装通用版本/移动权限门，再以节点级调宿授权覆盖旧的楼栋一刀切。
install_affairs_four_end_review_guard()
install_dorm_node_guard()
# 学生四端合同必须在所有业务兼容层后安装，确保动作、申请、时间线、材料和消息读取最终同源。
install_student_contract()
# 最终安全门收紧学生时间线、附件可见性、稳定标识和可执行动作。
install_student_contract_security_guard()
# 教师学工首页复用通用待办可见性，并返回真实逐条跨业务待办。
install_teacher_workbench_guard()
# 终态安全门在所有兼容层之后执行：强制学生本人身份，并机械检查教师移动读写权限登记。
install_affairs_four_end_terminal_guard(api_router)
