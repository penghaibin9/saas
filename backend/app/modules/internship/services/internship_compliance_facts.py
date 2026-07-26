"""统一合规数量事实：所有状态、归档、统计共用，不允许前端自行推算。"""
from __future__ import annotations

from datetime import date, datetime, timedelta

from sqlalchemy import func, select

from app.models import (
    InternshipCheckin, InternshipGuidance, InternshipLeave, InternshipMakeup,
    InternshipVisit, WeeklyReport,
)
from app.services.db_service import _tid


def _date(value):
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return datetime.fromisoformat(str(value)[:10]).date()
    except ValueError:
        return None


def _expected_count(config, section, keys, default):
    node = (config or {}).get(section) or {}
    for key in keys:
        if node.get(key) is not None:
            return max(0, int(node[key]))
    return default


def material_quantity_facts(db, rec, batch) -> dict:
    cfg = (batch.rules_config or {}) if batch else {}
    start = _date(rec.intern_start_date) or _date(getattr(batch, "start_date", None))
    end = _date(rec.intern_end_date) or _date(getattr(batch, "end_date", None)) or datetime.utcnow().date()
    weekdays = 0
    if start and end and start <= end:
        cursor = start
        while cursor <= end:
            if cursor.weekday() < 5:
                weekdays += 1
            cursor += timedelta(days=1)
    leave_days = set()
    leaves = db.scalars(select(InternshipLeave).where(
        InternshipLeave.tenant_id == _tid(), InternshipLeave.internship_id == rec.id,
        InternshipLeave.status.in_(("APPROVED", "RETURNED")),
        InternshipLeave.is_deleted.is_(False))).all()
    for leave in leaves:
        left, right = _date(leave.start_date), _date(leave.end_date)
        if not left or not right:
            continue
        cursor = left
        while cursor <= right:
            if cursor.weekday() < 5 and (not start or cursor >= start) and (not end or cursor <= end):
                leave_days.add(cursor.isoformat())
            cursor += timedelta(days=1)
    checkin_cfg = cfg.get("checkin") or {}
    configured_checkin = _expected_count(
        cfg, "checkin", ("expectedDays", "requiredDays"), weekdays)
    expected_checkin = max(
        0,
        configured_checkin
        - (len(leave_days) if checkin_cfg.get("deductApprovedLeave", True) else 0),
    )
    valid_checkin_dates = set(db.scalars(select(InternshipCheckin.checkin_date).where(
        InternshipCheckin.tenant_id == _tid(), InternshipCheckin.internship_id == rec.id,
        InternshipCheckin.result.in_(("NORMAL", "RECORDED")),
        InternshipCheckin.is_deleted.is_(False))).all())
    valid_checkin_dates.update(db.scalars(select(InternshipMakeup.checkin_date).where(
        InternshipMakeup.tenant_id == _tid(), InternshipMakeup.internship_id == rec.id,
        InternshipMakeup.status == "APPROVED",
        InternshipMakeup.is_deleted.is_(False))).all())
    valid_checkin_dates = {
        value for value in valid_checkin_dates
        if value is not None
        and (not start or _date(value) >= start)
        and (not end or _date(value) <= end)
    }
    expected_weekly = _expected_count(
        cfg, "weeklyReport", ("expectedCount", "requiredCount", "minCount"),
        max(0, ((end - start).days + 7) // 7) if start and end and start <= end else 0)
    actual_weekly = int(db.scalar(select(func.count()).select_from(WeeklyReport).where(
        WeeklyReport.tenant_id == _tid(), WeeklyReport.internship_id == rec.id,
        WeeklyReport.status == "APPROVED", WeeklyReport.is_deleted.is_(False))) or 0)
    duration_days = ((end - start).days + 1) if start and end and start <= end else 0
    duration_months = max(1, (duration_days + 29) // 30) if duration_days else 0
    guidance_cfg = cfg.get("guidance") or {}
    expected_guidance = _expected_count(
        cfg, "guidance", ("expectedCount", "minCount"),
        max(0, int(guidance_cfg.get("minCommunicationsPerMonth") or 0) * duration_months),
    )
    actual_guidance = int(db.scalar(select(func.count()).select_from(InternshipGuidance).where(
        InternshipGuidance.tenant_id == _tid(), InternshipGuidance.internship_id == rec.id,
        InternshipGuidance.status == "NORMAL", InternshipGuidance.is_deleted.is_(False))) or 0)
    expected_visit = _expected_count(
        cfg, "visit", ("expectedCount", "minCount"),
        max(0, int(guidance_cfg.get("minVisitsPerTerm") or 0)),
    )
    actual_visit = int(db.scalar(select(func.count()).select_from(InternshipVisit).where(
        InternshipVisit.tenant_id == _tid(), InternshipVisit.internship_id == rec.id,
        InternshipVisit.visit_at.is_not(None), InternshipVisit.is_deleted.is_(False))) or 0)

    def row(expected, actual):
        missing = max(0, expected - actual)
        return {"expected": expected, "actual": actual,
                "status": "VALID" if missing == 0 else "MISSING", "missing": missing}

    return {
        "checkin": row(expected_checkin, len(valid_checkin_dates)),
        "weekly": row(expected_weekly, actual_weekly),
        "guidance": row(expected_guidance, actual_guidance),
        "visit": row(expected_visit, actual_visit),
        "leaveDaysDeducted": len(leave_days),
        "source": "batch.rules_config",
    }
