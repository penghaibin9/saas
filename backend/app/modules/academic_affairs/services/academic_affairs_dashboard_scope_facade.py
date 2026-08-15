"""AA-DASHBOARD-01 教务看板统一公开入口。

校级教务保留既有全校实时聚合；学院、课程、班级等范围不复用全校统计。
本模块显式代理旧 Service，不再通过导入副作用替换其函数对象。

A-W1：公开 ``/terms/current`` 先消费 SYS-12 CalendarResolver 的 ACTIVE 学期；尚未
纳入治理的历史学校暂走严格 legacy ``AaTerm.is_current`` 兼容，但多 current 必须
fail-closed，禁止 ``first()`` 随机挑选。
"""
from __future__ import annotations

import importlib
from datetime import datetime

from sqlalchemy import select

from app.core.affairs_security import build_affairs_context
from app.core.exceptions import AppException

_legacy = importlib.import_module(
    ".academic_affairs_service",
    package=__package__,
)


def __getattr__(name):
    return getattr(_legacy, name)


def current_term(user) -> dict:
    """A-C1 public current-term resolver: governance ACTIVE first, strict legacy fallback."""
    from app.models import AaTerm
    from app.services import academic_calendar_service as calendar

    tenant_id = int(_legacy._tid())
    resolved = calendar.resolve_current(module_code="ACADEMIC_AFFAIRS", tenant_id=tenant_id)
    with _legacy.session() as db:
        if resolved.get("hasCurrent"):
            term_id = int(resolved["termId"])
            term = db.get(AaTerm, term_id)
            if not term or term.is_deleted or int(term.tenant_id) != tenant_id:
                raise AppException(
                    "DATA_CONFLICT",
                    "全校当前学期治理记录未命中有效教务学期，禁止猜测当前学期",
                    details={"termId": str(term_id), "authoritySource": "CALENDAR_GOVERNANCE"},
                    http_status=409,
                )
            row = _legacy._term_row(term)
            row["isCurrent"] = True
            return row

        rows = db.scalars(
            select(AaTerm).where(
                AaTerm.tenant_id == tenant_id,
                AaTerm.is_current.is_(True),
                AaTerm.is_deleted.is_(False),
            )
        ).all()
        if len(rows) > 1:
            raise AppException(
                "DATA_CONFLICT",
                "学校存在多个当前学期，且尚未完成全校学期治理切换，禁止随机选择",
                details={"termIds": [str(term.id) for term in rows]},
                http_status=409,
            )
        if not rows:
            return {"termId": "", "isCurrent": False, "note": "尚未设置当前学期"}
        return _legacy._term_row(rows[0])


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
