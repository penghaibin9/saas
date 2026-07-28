"""教务中心公开 Router 聚合入口。

主线 ``app.api.v1.route_registration`` 只注册一个 ``academic_affairs.router``。
本长期分支把新增教务 Router 聚合在模块内部，避免继续改动主线共享注册文件，
从而降低与毕业设计、岗位实习后续路由安全修复的合并冲突风险。
"""
from __future__ import annotations

from fastapi import APIRouter

from . import academic_affairs as base_router
from . import (
    dashboard_readiness_router,
    dynamic_grade_router,
    exam_incident_closure_router,
    grade_task_identity_router,
    mobile_grade_entry_router,
    program_quality_router,
    scheduling_rule_router,
    semester_pilot_router,
    stats_snapshot_router,
    student_evaluation_router,
    student_exam_router,
    teaching_class_router,
    teaching_task_workbench_router,
    term_detail_router,
    textbook_closure_router,
)


_EXTENSION_ROUTERS = (
    dashboard_readiness_router,
    dynamic_grade_router,
    exam_incident_closure_router,
    grade_task_identity_router,
    mobile_grade_entry_router,
    program_quality_router,
    scheduling_rule_router,
    semester_pilot_router,
    stats_snapshot_router,
    student_evaluation_router,
    student_exam_router,
    teaching_class_router,
    teaching_task_workbench_router,
    term_detail_router,
    textbook_closure_router,
)


def build_router() -> APIRouter:
    """按当前已完成初始化的子 Router 重建聚合器，避免循环导入阶段复制到空路由表。"""
    router = APIRouter()
    router.include_router(base_router.router)
    for module in _EXTENSION_ROUTERS:
        router.include_router(module.router)
    return router


router = build_router()
