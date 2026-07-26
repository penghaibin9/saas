"""教务中心 API 路由聚合。"""
from __future__ import annotations

from . import academic_affairs as academic_affairs
from .teaching_class_router import router as teaching_class_router

# route_registration 继续只注册 academic_affairs.router；V2独立小路由在包内聚合，避免反复改千行总路由。
_existing_paths = {getattr(route, "path", "") for route in academic_affairs.router.routes}
if "/academic-affairs/teaching-classes" not in _existing_paths:
    academic_affairs.router.include_router(teaching_class_router)
