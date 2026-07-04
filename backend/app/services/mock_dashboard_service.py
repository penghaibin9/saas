"""mock 仪表盘概览：按当前身份 + 数据范围裁剪的 KPI 卡片。"""
from __future__ import annotations

from app.services.mock_auth_service import get_active_context


def get_summary(user_ctx: dict) -> dict:
    active = get_active_context(user_ctx)
    scope = active["dataScope"]
    students = active.get("studentCount", 0)
    return {
        "activeContext": {"contextType": active["contextType"], "contextName": active["contextName"],
                          "dataScope": scope, "scopeLabel": active.get("scopeLabel")},
        "cards": [
            {"key": "students", "label": "范围内学生", "value": students, "unit": "人", "trend": "+3"},
            {"key": "todos", "label": "待办任务", "value": active.get("todoCount", 0), "unit": "项", "trend": "+1"},
            {"key": "risks", "label": "风险预警学生", "value": active.get("riskCount", 0), "unit": "人", "trend": "0"},
            {"key": "messages", "label": "未读消息", "value": 4, "unit": "条", "trend": "+2"},
        ],
        "quickEntries": [
            {"key": "todo", "label": "待办中心", "path": "/todos"},
            {"key": "approval", "label": "审批处理", "path": "/approvals"},
            {"key": "students", "label": "我的学生", "path": "/students"},
        ],
        "notice": "本数据为 mock 演示，接入数据库后按 tenant_id + dataScope 实时统计。",
    }


def get_lifecycle_overview(user_ctx: dict) -> dict:
    """生命周期总览：六阶段人数分布（mock；接库后聚合 t_student_profile.current_stage）。"""
    return {
        "scope": (user_ctx or {}).get("currentRoleCode", "DEFAULT"),
        "stages": [
            {"stage": "ADMISSION", "label": "招录", "count": 1620},
            {"stage": "ORIENTATION", "label": "迎新", "count": 1602},
            {"stage": "ON_CAMPUS", "label": "在校", "count": 6493},
            {"stage": "INTERNSHIP", "label": "实习", "count": 862},
            {"stage": "GRADUATION_DESIGN", "label": "毕设", "count": 2641},
            {"stage": "EMPLOYMENT", "label": "就业", "count": 2641},
        ],
        "updatedAt": "同步至当日 14:00（mock）",
    }
