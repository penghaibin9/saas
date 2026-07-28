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


def build_router() -> APIRouter:
    """在注册时读取包内已完成初始化的真实子 Router，避开循环导入留下的旧模块引用。"""
    from app.modules.academic_affairs.routers import scheduling_rule_router as live_rule_router

    router = APIRouter()
    router.include_router(base_router.router)
    package = importlib.import_module(__package__)
    for module_name in _EXTENSION_ROUTER_MODULES:
        module = getattr(package, module_name, None)
        if module is None:
            module = importlib.import_module(f"{__package__}.{module_name}")
        router.include_router(module.router)
    router.include_router(live_rule_router.router)
    return router


# 主注册器会在依赖全部加载后调用 build_router()，这里不提前复制半成品路由表。
router = APIRouter()
