"""/api/v1 路由聚合。注册逻辑拆至 route_registration，路径与依赖保持兼容。"""
from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.route_registration import register_all_routes

api_router = APIRouter()
register_all_routes(api_router)

# 学工四端补充路由必须在既有路由完成注册后挂载；契约安装器随后修补已加载服务的
# version/permission/scope 绑定，不改任何其他业务域状态机。
from app.api.v1.affairs_four_end import router as affairs_four_end_router
from app.services.affairs_four_end_contract import install as install_affairs_four_end_contract

api_router.include_router(affairs_four_end_router)
install_affairs_four_end_contract()
