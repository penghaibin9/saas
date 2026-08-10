"""教务中心公开 Router 聚合入口。

主线 ``app.api.v1.route_registration`` 只注册一个 ``academic_affairs.router``。
本长期分支把新增教务 Router 聚合在模块内部，避免继续改动主线共享注册文件，
从而降低与毕业设计、岗位实习后续路由安全修复的合并冲突风险。
"""
from __future__ import annotations

import importlib
import re

from fastapi import APIRouter

from . import academic_affairs as base_router


_EXTENSION_ROUTER_MODULES = (
    "academic_file_exchange_router",
    "archive_correction_router",
    "dashboard_readiness_router",
    "dynamic_grade_router",
    "exam_incident_closure_router",
    "grade_task_identity_router",
    "mobile_grade_entry_router",
    "program_quality_router",
    "semester_pilot_router",
    "stats_snapshot_router",
    "status_change_temporal_router",
    "student_evaluation_router",
    "student_exam_router",
    "teaching_class_router",
    "teaching_task_workbench_router",
    "term_detail_router",
    "textbook_closure_router",
)


def _mount_routes(parent: APIRouter, child: APIRouter) -> None:
    """Flatten an already-built child router into the public aggregate.

    FastAPI 0.141 can preserve nested ``include_router`` calls as internal
    ``_IncludedRouter`` nodes until a later expansion step.  The academic-affairs
    bundle is itself included by the application registry, so leaving another nested
    layer can make formal extension routes disappear from the final public route table.
    Copy the concrete child route objects instead; the application-level academic
    dependencies are still attached once by ``route_registration``.
    """
    def route_key(route):
        path = re.sub(r"\{[^/{}]+\}", "{}", getattr(route, "path", ""))
        return path, tuple(sorted(getattr(route, "methods", set()) or set()))

    existing = {
        route_key(route)
        for route in parent.routes
    }
    for route in child.routes:
        key = route_key(route)
        if key in existing:
            continue
        parent.routes.append(route)
        existing.add(key)


def build_router() -> APIRouter:
    """在注册时读取包内已完成初始化的真实子 Router，避开循环导入留下的旧模块引用。"""
    from app.modules.academic_affairs.routers import scheduling_rule_router as live_rule_router

    router = APIRouter()
    # 阶段 7：精确同路径适配器必须先于历史同步 StreamingResponse Router 注册。
    # 旧页面合同不变，但实际生成先进入 FileObject + ExportJob + 一次性票据。
    compat_module = importlib.import_module(f"{__package__}.academic_export_compat_router")
    _mount_routes(router, compat_module.router)
    # Stage D：选课 final service 已完成行锁/学籍事实/DecisionTrace 收口，必须让精确
    # HTTP 路径先命中 final adapter；历史大 Router 继续保留以降低长期分支冲突。
    selection_final_module = importlib.import_module(f"{__package__}.academic_selection_final_router")
    _mount_routes(router, selection_final_module.router)
    # 正式规则 Router 必须先于历史大 Router；相同 method/path 由上面的确定性去重保留新版。
    _mount_routes(router, live_rule_router.router)
    _mount_routes(router, base_router.router)
    package = importlib.import_module(__package__)
    for module_name in _EXTENSION_ROUTER_MODULES:
        module = getattr(package, module_name, None)
        if module is None:
            module = importlib.import_module(f"{__package__}.{module_name}")
        _mount_routes(router, module.router)

    return router


# 主注册器会在依赖全部加载后调用 build_router()，这里不提前复制半成品路由表。
router = APIRouter()
