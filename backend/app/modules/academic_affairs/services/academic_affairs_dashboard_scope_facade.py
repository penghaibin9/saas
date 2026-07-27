"""AA-DASHBOARD-01 教务看板统一公开入口。

校级教务保留既有全校实时聚合；学院、课程、班级等范围不复用全校统计。
本模块显式代理旧 Service，不再通过导入副作用替换其函数对象。
"""
from __future__ import annotations

import importlib
from datetime import datetime

from app.core.affairs_security import build_affairs_context

_legacy = importlib.import_module(
    ".academic_affairs_service",
    package=__package__,
)


def __getattr__(name):
    return getattr(_legacy, name)


def dashboard(user) -> dict:
    data = dict(_legacy.dashboard(user) or {})
    # 正式学校页面不再输出 LIVE/PENDING 施工卡；能力入口由导航和 readiness 负责。
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
    with _legacy.session() as db:
        ctx = build_affairs_context(user, db)
        scope_type = str(getattr(ctx, "scope_type", None) or "NONE").upper()
    if scope_type == "TENANT_ALL":
        data = dict(_legacy.dashboard_reminders(user) or {})
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
