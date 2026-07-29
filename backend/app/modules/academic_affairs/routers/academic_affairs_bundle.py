"""教务中心公开 Router 聚合入口。

主线 ``app.api.v1.route_registration`` 只注册一个 ``academic_affairs.router``。
本长期分支把新增教务 Router 聚合在模块内部，避免继续改动主线共享注册文件，
从而降低与毕业设计、岗位实习后续路由安全修复的合并冲突风险。
"""
from __future__ import annotations

import importlib

from fastapi import APIRouter
from fastapi.routing import APIRoute

from . import academic_affairs as base_router


_EXTENSION_ROUTER_MODULES = (
    "dashboard_readiness_router",
    "dynamic_grade_router",
    "exam_incident_closure_router",
    "grade_task_identity_router",
    "mobile_grade_entry_router",
    "program_quality_router",
    "semester_pilot_router",
    "stats_snapshot_router",
    "student_evaluation_router",
    "student_exam_router",
    "teaching_class_router",
    "teaching_task_workbench_router",
    "term_detail_router",
    "textbook_closure_router",
)


def _route_signature(route: APIRoute) -> tuple[str, frozenset[str]]:
    return route.path, frozenset((route.methods or set()) - {"HEAD", "OPTIONS"})


def _append_route(router: APIRouter, route, seen: set[tuple[str, frozenset[str]]]) -> None:
    """复制已完成初始化的路由；扩展路由之间禁止继续产生同方法同路径冲突。"""
    if not isinstance(route, APIRoute):
        router.routes.append(route)
        return
    signature = _route_signature(route)
    if signature in seen:
        raise RuntimeError(f"教务扩展路由重复注册: methods={sorted(signature[1])} path={signature[0]}")
    router.routes.append(route)
    seen.add(signature)


def build_router() -> APIRouter:
    """构建单一教务 Router；同路径扩展明确替换旧实现，不依赖注册顺序抢占。"""
    from app.modules.academic_affairs.routers import scheduling_rule_router as live_rule_router

    package = importlib.import_module(__package__)
    extension_routers: list[APIRouter] = []
    for module_name in _EXTENSION_ROUTER_MODULES:
        module = getattr(package, module_name, None)
        if module is None:
            module = importlib.import_module(f"{__package__}.{module_name}")
        extension_routers.append(module.router)

    # 该独立路由会在服务 Facade 初始化期间经历循环导入，因此必须在注册阶段读取当前真实 Router。
    extension_routers.append(live_rule_router.router)

    # 新增 Router 中存在少量“保持原 URL、修正请求契约”的替代实现（例如排课规则
    # ruleValue 从 dict 放宽为 Any）。先收集这些精确方法+路径，再从旧总 Router 中移除同签名路由，
    # 避免生产进程同时挂载两份端点并依赖声明顺序决定实际命中谁。
    replacement_signatures = {
        _route_signature(route)
        for child in extension_routers
        for route in child.routes
        if isinstance(route, APIRoute)
    }

    router = APIRouter()
    seen: set[tuple[str, frozenset[str]]] = set()
    for route in base_router.router.routes:
        if isinstance(route, APIRoute) and _route_signature(route) in replacement_signatures:
            continue
        _append_route(router, route, seen)

    for child in extension_routers:
        for route in child.routes:
            _append_route(router, route, seen)

    return router


# 主注册器会在依赖全部加载后调用 build_router()，这里不提前复制半成品路由表。
router = APIRouter()
