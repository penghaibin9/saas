"""AA-DASHBOARD-01 旧看板聚合安全兼容层。

校级教务保留既有全校实时聚合；学院、课程、班级等范围不再复用全校统计，
避免用“已建立数据范围上下文”代替真正的SQL收敛。
"""
from __future__ import annotations

from datetime import datetime

from app.core.affairs_security import build_affairs_context

from . import academic_affairs_service as _base

_original_dashboard = _base.dashboard
_original_reminders = _base.dashboard_reminders


def dashboard(user) -> dict:
    data = dict(_original_dashboard(user) or {})
    # 正式学校页面不再输出LIVE/PENDING施工卡；能力入口由导航和readiness负责。
    data.pop("moduleCards", None)
    return data


def _empty_reminders(note: str) -> dict:
    return {
        "gradeProgress": {"totalTasks": 0, "counts": {}, "submittedRate": 0, "pendingTasks": [], "drillRoute": "aa-grade-overview", "note": note},
        "examReminders": {"count": 0, "windowDays": 14, "items": [], "drillRoute": "aa-exam", "note": note},
        "statusChangeReminders": {"count": 0, "items": [], "drillRoute": "aa-status-changes", "note": note},
        "warningReminders": {"count": 0, "items": [], "drillRoute": "aa-warnings", "note": note},
        "graduationWarnings": {"count": 0, "items": [], "drillRoute": "aa-graduation", "note": note},
        "todos": [],
        "todayTeaching": {
            "totalToday": 0, "notStarted": 0, "inProgress": 0, "ended": 0,
            "adjustedCount": 0, "examCount": 0, "teacherCount": 0,
            "classCount": 0, "roomCount": 0, "note": note, "drillRoute": "aa-schedule",
        },
        "todayCourses": {"items": [], "count": 0, "shown": 0, "note": note, "drillRoute": "aa-schedule"},
        "scheduleChangeReminders": {"count": 0, "items": [], "drillRoute": "aa-schedule-change-ledger", "note": note},
        "resourceOccupancy": {"totalRooms": 0, "occupiedToday": 0, "occupancyRate": 0, "items": [], "note": note, "drillRoute": "aa-classrooms"},
        "dataTrends": {"days": [], "series": [], "drillRoute": "aa-stats", "note": note},
        "scopeRestricted": True,
        "scopeNote": note,
        "generatedAt": datetime.utcnow().isoformat(),
    }


def dashboard_reminders(user) -> dict:
    with _base.session() as db:
        ctx = build_affairs_context(user, db)
        scope_type = str(getattr(ctx, "scope_type", None) or "NONE").upper()
    if scope_type == "TENANT_ALL":
        data = dict(_original_reminders(user) or {})
        data["scopeRestricted"] = False
        data["scopeNote"] = "按全校教务数据聚合"
        return data
    if scope_type == "COLLEGE":
        return _empty_reminders(
            "当前为学院数据范围。学校级成绩、考务、预警和资源汇总已停止展示；本院 readiness 请以上方阶段结论为准。"
        )
    return _empty_reminders(
        "当前角色仅可处理本人或本班教务事项，学校级汇总已 fail-closed。"
    )


_base.dashboard = dashboard
_base.dashboard_reminders = dashboard_reminders
