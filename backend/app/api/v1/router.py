"""/api/v1 路由聚合。注册逻辑拆至 route_registration，路径与依赖保持兼容。"""
from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.route_registration import register_all_routes

api_router = APIRouter()
register_all_routes(api_router)
