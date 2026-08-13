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


def _mount_routes(parent: APIRouter, child: APIRouter, *,
                  skip_existing_shapes: frozenset[str] = frozenset()) -> None:
    """Flatten an already-built child router into the public aggregate.

    FastAPI 0.141 can preserve nested ``include_router`` calls as internal
    ``_IncludedRouter`` nodes until a later expansion step.  The academic-affairs
    bundle is itself included by the application registry, so leaving another nested
    layer can make formal extension routes disappear from the final public route table.
    Copy the concrete child route objects instead; the application-level academic
    dependencies are still attached once by ``route_registration``.

    Exact method/path shapes are unique at the final public surface.  Adapter/final
    routers are mounted before the historical large router, so the first registered
    shape is authoritative and later duplicates are dropped deterministically.  The
    legacy ``skip_existing_shapes`` argument remains accepted for old callers but the
    safety rule now applies to every duplicate shape, not only scheduling rules.
    """
    del skip_existing_shapes

    def route_key(route):
        path = re.sub(r"\{[^/{}]+\}", "{}", getattr(route, "path", ""))
        return path, tuple(sorted(getattr(route, "methods", set()) or set()))

    existing = {route_key(route) for route in parent.routes}
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
    # 成绩任务特殊补录必须把稳定 courseId 真实传进生产 Service，再由 canonical term guard
    # 对 ARCHIVED 学期 fail-closed；精确 V2 入口必须先于历史大 Router 的旧 Pydantic 模型。
    grade_task_create_module = importlib.import_module(f"{__package__}.grade_task_create_v2_router")
    _mount_routes(router, grade_task_create_module.router)
    # 正式规则 Router 必须先于历史大 Router；相同 method/path 由上面的确定性去重保留新版。
    _mount_routes(router, live_rule_router.router)
    # D1-S：学期/校历/作息节次/time-bands 已从历史大 Router 纯结构迁出。
    # 必须在 legacy 之前挂载，确保公开 owner 真正切换到 term_calendar_router；
    # legacy 中同 method/path 继续保留为兼容来源并由确定性去重跳过。
    term_calendar_module = importlib.import_module(f"{__package__}.term_calendar_router")
    _mount_routes(router, term_calendar_module.router)
    # D1-U：便利性只读 preview。它不替代 canonical 写链，只把系统能计算的
    # 校历复制/标准作息候选提前算给用户看，确认后仍走原正式写端点。
    convenience_module = importlib.import_module(f"{__package__}.term_calendar_convenience_router")
    _mount_routes(router, convenience_module.router)
    # D2-S：学籍名册 + 注册管理 Move Only。三条正式导出由上方 compat 继续先占 owner；
    # 其余 legacy 同路径由 normalized method/path 去重切换到 roster_registration_router。
    roster_registration_module = importlib.import_module(f"{__package__}.roster_registration_router")
    _mount_routes(router, roster_registration_module.router)
    # D2-U：候选 enrich / 批量注册 preview+confirm 只做便利性编排；最终写入仍逐项
    # 调用原 register_student canonical，且新路径不覆盖任何 legacy/compat shape。
    roster_registration_convenience_module = importlib.import_module(
        f"{__package__}.roster_registration_convenience_router"
    )
    _mount_routes(router, roster_registration_convenience_module.router)
    # D3-S：只迁 legacy base 仍持有的 status-change 主入口。future-effective /scheduled
    # 继续由下方 status_change_temporal_router extension 持有，禁止复制 temporal 逻辑。
    status_change_module = importlib.import_module(f"{__package__}.status_change_router")
    _mount_routes(router, status_change_module.router)
    # D3-U：统一立即/计划生效 + 正式材料便利性。新路径只编排上面的 canonical submit，
    # 不覆盖 D3-S 五入口，也不覆盖 temporal /scheduled；材料在同一事务通过 FileBinding 落地。
    status_change_convenience_module = importlib.import_module(f"{__package__}.status_change_convenience_router")
    _mount_routes(router, status_change_convenience_module.router)
    # D4-S：课程库 / 培养方案 / 教学任务从 legacy 大 Router Move Only 迁出。
    # 已独立的 program_quality_router / teaching_class_router 继续保持 extension owner，
    # 本批不复制其路径、不改 canonical service / permission / DTO / schema。
    course_program_task_module = importlib.import_module(f"{__package__}.course_program_task_router")
    _mount_routes(router, course_program_task_module.router)
    # D5-S1：课表批次主链与课表只读主入口 Move Only。
    # /schedule/export 继续由上方 compat owner 持有；scheduling rules 继续由 live_rule_router 持有。
    schedule_core_module = importlib.import_module(f"{__package__}.schedule_core_router")
    _mount_routes(router, schedule_core_module.router)
    # D5-S2：教师可用时间、冲突报告、排课增强、Excel 结果导入、异议、归档与自动排课 Move Only。
    # 不复制 scheduling rules，不接管 D5-S1 主链，也不改 canonical service / permission / DTO。
    scheduling_operations_module = importlib.import_module(f"{__package__}.scheduling_operations_router")
    _mount_routes(router, scheduling_operations_module.router)
    # D5-S3：教室、实训室、设备、预约、占用、冲突、维修与资源统计 Move Only。
    # 保持 bookings/options 字面量路径在动态详情之前，不改 resource_svc 规则或权限。
    teaching_resource_module = importlib.import_module(f"{__package__}.teaching_resource_router")
    _mount_routes(router, teaching_resource_module.router)
    # D5-S4：调课/停课/补课申请、预检、统计、终态归档、审批与撤销 Move Only。
    # 静态 stats/archive 必须先于动态详情，状态机与课表改写继续唯一由 sched_change_svc 持有。
    schedule_change_module = importlib.import_module(f"{__package__}.schedule_change_router")
    _mount_routes(router, schedule_change_module.router)
    # D7-S：考试批次/排考/考场座位/监巡考/发布归档/缓考审批从 legacy Move Only 迁出。
    # mobile exam-v2 与 incident resolve 仍由既有 extension owner 持有；成绩域留给 D8。
    exam_core_module = importlib.import_module(f"{__package__}.exam_core_router")
    _mount_routes(router, exam_core_module.router)
    _mount_routes(
        router,
        base_router.router,
        skip_existing_shapes=frozenset({
            "/academic-affairs/scheduling/rules",
            "/academic-affairs/scheduling/rules/{}",
        }),
    )
    package = importlib.import_module(__package__)
    for module_name in _EXTENSION_ROUTER_MODULES:
        module = getattr(package, module_name, None)
        if module is None:
            module = importlib.import_module(f"{__package__}.{module_name}")
        _mount_routes(router, module.router)

    return router


# 主注册器会在依赖全部加载后调用 build_router()，这里不提前复制半成品路由表。
router = APIRouter()
