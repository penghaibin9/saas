"""/api/v1 路由聚合。注册逻辑拆至 route_registration，路径与依赖保持兼容。"""
from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.route_registration import register_all_routes

api_router = APIRouter()
register_all_routes(api_router)

# 学工四端补充路由必须在既有路由完成注册后挂载；契约安装器随后修补已加载服务的
# version/permission/scope 绑定，不改任何其他业务域状态机。
from app.api.v1.affairs_activity_mobile import router as affairs_activity_mobile_router
from app.api.v1.affairs_appeal_mobile import router as affairs_appeal_mobile_router
from app.api.v1.affairs_four_end import router as affairs_four_end_router
from app.api.v1.affairs_student_dorm import router as affairs_student_dorm_router
from app.api.v1.affairs_student_returned import router as affairs_student_returned_router
from app.services.affairs_activity_code_service import install as install_activity_checkin_code
from app.services.affairs_activity_reliability_service import install as install_activity_reliability
from app.services.affairs_appeal_todo_service import install as install_appeal_todo_reconciliation
from app.services.affairs_four_end_contract import install as install_affairs_four_end_contract
from app.services.affairs_four_end_review_guard import install as install_affairs_four_end_review_guard
from app.services.affairs_returned_view_service import install as install_returned_view_projection
from app.services.affairs_sensitive_audit_guard import install as install_sensitive_audit_guard
from app.services.affairs_student_atomic_service import install as install_atomic_student_applications

api_router.include_router(affairs_four_end_router)
api_router.include_router(affairs_student_dorm_router)
api_router.include_router(affairs_activity_mobile_router)
api_router.include_router(affairs_appeal_mobile_router)
api_router.include_router(affairs_student_returned_router)
install_affairs_four_end_contract()
install_sensitive_audit_guard()
install_returned_view_projection()
install_activity_checkin_code()
install_activity_reliability()
install_atomic_student_applications()
install_appeal_todo_reconciliation()
# 必须最后安装：收紧前述兼容层的 fail-closed、显式 version 与学生宿舍范围边界。
install_affairs_four_end_review_guard()
