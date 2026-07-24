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


def _real_summary(user: dict) -> dict:
    """DB 启用时的真实工作台概览（按当前登录人数据范围收敛，见 stats_service.get_workbench_summary）。"""
    s = stats_service.get_workbench_summary(user)
    cards_by_key = {
        "students": {"key": "students", "label": "在册学生", "value": s["studentTotal"], "unit": "人", "trend": ""},
        "todos": {"key": "todos", "label": "待办任务", "value": s["pendingTodo"], "unit": "项", "trend": ""},
        "approvals": {"key": "approvals", "label": "待审批", "value": s["pendingApproval"], "unit": "件", "trend": ""},
        "messages": {"key": "messages", "label": "未读消息", "value": s["unreadMessage"], "unit": "条", "trend": ""},
        "warning": {"key": "warning", "label": "学业预警在办", "value": s["academicWarning"], "unit": "人", "trend": ""},
    }
    quick_entries = [
        {"key": "todo", "label": "待办中心", "path": "/admin/approval"},
        {"key": "students", "label": "我的学生", "path": "/admin/students"},
    ]
    card_keys = list(cards_by_key); workbench = None
    try:
        from sqlalchemy import select
        from app.core.context import current_tenant_id
        from app.core.permissions import has_permission
        from app.db.session import get_sessionmaker
        from app.models import RoleWorkbenchConfig
        role_code = str(user.get("currentRoleCode") or "").upper()
        db = get_sessionmaker()()
        try:
            workbench = db.scalars(select(RoleWorkbenchConfig).where(
                RoleWorkbenchConfig.tenant_id == current_tenant_id(),
                RoleWorkbenchConfig.role_code == role_code,
                RoleWorkbenchConfig.status == "ENABLED",
                RoleWorkbenchConfig.is_deleted.is_(False))).first()
            if workbench:
                card_keys = workbench.card_keys_json or card_keys
                quick_entries = [{"key": x.get("key"), "label": x.get("label"), "path": x.get("path")}
                                 for x in workbench.quick_entries_json or []
                                 if not x.get("permissionCode") or has_permission(user, x["permissionCode"])]
        finally:
            db.close()
    except Exception:  # 配置读取失败不影响真实统计主链路
        workbench = None
    return {
        "cards": [cards_by_key[key] for key in card_keys if key in cards_by_key],
        "quickEntries": quick_entries,
        "workbench": {"title": workbench.title, "subtitle": workbench.subtitle,
                      "roleCode": workbench.role_code, "alerts": workbench.alert_keys_json}
                     if workbench else None,
        "updatedAt": s["updatedAt"],
        "scopeType": s.get("scopeType"),
        "scopeLabel": s.get("scopeLabel"),
        "notice": f"数据按当前身份范围聚合（{s.get('scopeLabel') or '已收敛'}）。",
    }


@router.get("/summary", summary="工作台概览（DB 启用走真实聚合，未启用走演示）")
def summary(user=Depends(require_staff)):
    if db_enabled():
        return success(_real_summary(user))
    return success(dash_svc.get_summary(user))


@router.get("/lifecycle-overview", summary="生命周期总览（六阶段人数分布·校级）")
def lifecycle_overview(user=Depends(require_staff)):
    if db_enabled():
        # 与 /stats/lifecycle 同口径：全校漏斗仅校级授权角色可见，一线禁止看全校数。
        stats_service.require_tenant_all_stats(user)
        lc = stats_service.get_lifecycle()
        return success({
            "scope": user.get("currentRoleCode", "DEFAULT"),
            "stages": [{"stage": s["key"], "label": s["label"], "count": s["count"]} for s in lc["stages"]],
            "updatedAt": lc["updatedAt"],
        })
    return success(dash_svc.get_lifecycle_overview(user))
