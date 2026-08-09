"""教务中心公开 Router 聚合入口。

主线 ``app.api.v1.route_registration`` 只注册一个 ``academic_affairs.router``。
本长期分支把新增教务 Router 聚合在模块内部，避免继续改动主线共享注册文件，
从而降低与毕业设计、岗位实习后续路由安全修复的合并冲突风险。
"""
from __future__ import annotations

import importlib

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
    parent.routes.extend(list(child.routes))


def build_router() -> APIRouter:
    """在注册时读取包内已完成初始化的真实子 Router，避开循环导入留下的旧模块引用。"""
    from app.modules.academic_affairs.routers import scheduling_rule_router as live_rule_router

    router = APIRouter()
    # 阶段 7：精确同路径适配器必须先于历史同步 StreamingResponse Router 注册。
    # 旧页面合同不变，但实际生成先进入 FileObject + ExportJob + 一次性票据。
    compat_module = importlib.import_module(f"{__package__}.academic_export_compat_router")
    _mount_routes(router, compat_module.router)
    _mount_routes(router, base_router.router)
    package = importlib.import_module(__package__)
    for module_name in _EXTENSION_ROUTER_MODULES:
        module = getattr(package, module_name, None)
        if module is None:
            module = importlib.import_module(f"{__package__}.{module_name}")
        _mount_routes(router, module.router)

    # 该独立路由会在服务 Facade 初始化期间经历循环导入；注册阶段读取当前真实 Router。
    _mount_routes(router, live_rule_router.router)
    return router


# 主注册器会在依赖全部加载后调用 build_router()，这里不提前复制半成品路由表。
router = APIRouter()
