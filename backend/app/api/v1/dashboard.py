"""仪表盘概览。

数据源分两档（与全后端 mock/DB 双轨一致）：
- DB 未启用（演示态）：走 mock_dashboard_service，返回演示卡片；
- DB 启用：走 stats_service 的真实跨域聚合（实时查各域表 + tenant 过滤），
  不再返回硬编码假数据（此前未读消息恒为 4、六阶段人数写死）。
身份门禁用 require_staff：学生令牌一律 403，不得访问 PC 管理端工作台概览。
"""
from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.response import success
from app.core.security import require_staff
from app.db.session import db_enabled
from app.services import mock_dashboard_service as dash_svc
from app.services import stats_service

router = APIRouter()


def _real_summary() -> dict:
    """DB 启用时的真实工作台概览（stats_service.get_workbench_summary 已实时聚合各域表）。"""
    s = stats_service.get_workbench_summary()
    return {
        "cards": [
            {"key": "students", "label": "在册学生", "value": s["studentTotal"], "unit": "人", "trend": ""},
            {"key": "todos", "label": "待办任务", "value": s["pendingTodo"], "unit": "项", "trend": ""},
            {"key": "approvals", "label": "待审批", "value": s["pendingApproval"], "unit": "件", "trend": ""},
            {"key": "messages", "label": "未读消息", "value": s["unreadMessage"], "unit": "条", "trend": ""},
            {"key": "warning", "label": "学业预警在办", "value": s["academicWarning"], "unit": "人", "trend": ""},
        ],
        "quickEntries": [
            {"key": "todo", "label": "待办中心", "path": "/todos"},
            {"key": "approval", "label": "审批处理", "path": "/approvals"},
            {"key": "students", "label": "我的学生", "path": "/students"},
        ],
        "updatedAt": s["updatedAt"],
        "notice": "数据来自各业务域实时聚合（tenant 过滤）。",
    }


@router.get("/summary", summary="工作台概览（DB 启用走真实聚合，未启用走演示）")
def summary(user=Depends(require_staff)):
    if db_enabled():
        return success(_real_summary())
    return success(dash_svc.get_summary(user))


@router.get("/lifecycle-overview", summary="生命周期总览（六阶段人数分布）")
def lifecycle_overview(user=Depends(require_staff)):
    if db_enabled():
        lc = stats_service.get_lifecycle()
        return success({
            "scope": user.get("currentRoleCode", "DEFAULT"),
            "stages": [{"stage": s["key"], "label": s["label"], "count": s["count"]} for s in lc["stages"]],
            "updatedAt": lc["updatedAt"],
        })
    return success(dash_svc.get_lifecycle_overview(user))
