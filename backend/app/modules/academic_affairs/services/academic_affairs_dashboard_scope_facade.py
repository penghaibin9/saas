"""AA-DASHBOARD-01 教务看板统一公开入口。

校级教务保留既有全校实时聚合；学院、课程、班级等范围不复用全校统计。
本模块显式代理旧 Service，不再通过导入副作用替换其函数对象。

A-W1：公开 ``/terms/current`` 消费 A-C1 ``Term Context Resolver``。Resolver 优先
SYS-12 ACTIVE 治理学期；尚未纳入治理的历史学校暂走严格 ``AaTerm.is_current``
兼容，多 current 必须 fail-closed。返回值同时解释当前 Authority 与允许的切换入口，
让管理 PC 不再展示一个必定被后端拒绝的旁路按钮。
"""
from __future__ import annotations

import importlib
from datetime import datetime

from sqlalchemy import select

from app.core.affairs_security import build_affairs_context, no_data_scope
from app.core.exceptions import AppException, not_found

_legacy = importlib.import_module(
    ".academic_affairs_service",
    package=__package__,
)


def __getattr__(name):
    return getattr(_legacy, name)


def register_student(batch_id, user, student_id) -> dict:
    from .academic_affairs_registration_scope import register_student as scoped_register_student

    return scoped_register_student(batch_id, user, student_id)


def list_registrations(batch_id, user, page=1, page_size=50):
    from .academic_affairs_registration_scope import list_registrations as scoped_list_registrations

    return scoped_list_registrations(batch_id, user, page, page_size)


def _assert_term_command_scope(user, db) -> None:
    ctx = build_affairs_context(user, db)
    if str(getattr(ctx, "scope_type", None) or "NONE").upper() != "TENANT_ALL":
        raise no_data_scope("仅校级教务可发布或切换学期")


def _lock_target_term(db, term_id):
    from app.models import AaTerm

    term = db.scalars(
        select(AaTerm).where(
            AaTerm.tenant_id == int(_legacy._tid()),
            AaTerm.id == int(term_id),
            AaTerm.is_deleted.is_(False),
        ).with_for_update()
    ).first()
    if not term:
        raise not_found("学期不存在")
    return term


def _lock_tenant_terms(db, term_id):
    from app.models import AaTerm

    rows = db.scalars(
        select(AaTerm).where(
            AaTerm.tenant_id == int(_legacy._tid()),
            AaTerm.is_deleted.is_(False),
        ).order_by(AaTerm.id).with_for_update()
    ).all()
    target = next((row for row in rows if int(row.id) == int(term_id)), None)
    if not target:
        raise not_found("学期不存在")
    return target, rows


def _governance_switch_conflict(resolved) -> AppException:
    return AppException(
        "DATA_CONFLICT",
        "当前学期由全校学期治理统一管理，教务侧不可直接切换",
        details={
            "currentAuthority": resolved.authority,
            "switchRoute": resolved.switch_route,
        },
        http_status=409,
    )


def publish_term(term_id, user) -> dict:
    """Publish a term definition without bypassing the current-term Authority."""
    from .academic_affairs_term_context_service import resolve_current_term
    from .academic_affairs_archive_service import guard_term_writable

    with _legacy.session() as db:
        _assert_term_command_scope(user, db)
        resolved = resolve_current_term(db, tenant_id=int(_legacy._tid()))

        if resolved.authority == "CALENDAR_GOVERNANCE":
            term = _lock_target_term(db, term_id)
            guard_term_writable(db, term.id)
            if term.status not in ("DRAFT", "PUBLISHED"):
                raise AppException(
                    "DATA_CONFLICT",
                    "仅草稿学期可发布",
                    details={"termId": str(term.id), "status": term.status},
                    http_status=409,
                )
            if term.status == "DRAFT":
                term.status = "PUBLISHED"
                _legacy._audit(db, "AA_TERM", term.id, "PUBLISH")
            db.commit()
            db.refresh(term)
            return _legacy._term_row(term)

        if resolved.authority != "AA_TERM_COMPAT" or not resolved.can_direct_switch:
            raise _governance_switch_conflict(resolved)

        term, rows = _lock_tenant_terms(db, term_id)
        guard_term_writable(db, term.id)
        if term.status in ("DRAFT", "PUBLISHED"):
            for other in rows:
                if int(other.id) != int(term.id):
                    other.is_current = False
            term.status = "PUBLISHED"
            term.is_current = True
            _legacy._audit(db, "AA_TERM", term.id, "PUBLISH")
        db.commit()
        db.refresh(term)
        return _legacy._term_row(term)


def set_current_term(term_id, user) -> dict:
    """Switch the legacy compatible current term; SYS-12 Authority always rejects."""
    from .academic_affairs_term_context_service import resolve_current_term

    with _legacy.session() as db:
        _assert_term_command_scope(user, db)
        resolved = resolve_current_term(db, tenant_id=int(_legacy._tid()))
        if resolved.authority != "AA_TERM_COMPAT" or not resolved.can_direct_switch:
            raise _governance_switch_conflict(resolved)

        term, rows = _lock_tenant_terms(db, term_id)
        if term.status != "PUBLISHED":
            raise AppException("DATA_CONFLICT", "仅进行中（PUBLISHED）学期可设为当前学期")
        if not term.is_current:
            for other in rows:
                if int(other.id) != int(term.id):
                    other.is_current = False
            term.is_current = True
            _legacy._audit(
                db,
                "AA_TERM",
                term.id,
                "SET_CURRENT",
                f"{term.year_code}-{term.term_no}",
            )
        db.commit()
        db.refresh(term)
        return _legacy._term_row(term)


def current_term(user) -> dict:
    """A-C1 public current-term contract: one resolver, no duplicate interpretation."""
    from .academic_affairs_term_context_service import resolve_current_term

    with _legacy.session() as db:
        resolved = resolve_current_term(db, tenant_id=int(_legacy._tid()))
        if resolved.term is None:
            row = {"termId": "", "isCurrent": False, "note": "尚未设置当前学期"}
        else:
            row = _legacy._term_row(resolved.term)
            if resolved.authority == "CALENDAR_GOVERNANCE":
                # governance ACTIVE 是当前学期的公开 Authority；即便历史 AaTerm 标志
                # 尚未完成 reconciliation，公开 DTO 也不能把已解析的当前学期显示为 false。
                row["isCurrent"] = True
        row.update({
            "currentAuthority": resolved.authority,
            "canDirectSwitch": resolved.can_direct_switch,
            "switchRoute": resolved.switch_route,
            "switchHint": resolved.switch_hint,
        })
        return row


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
