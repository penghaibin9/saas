"""AA-DASHBOARD-01 readiness 最终数据范围层。

统一在本模块完成真实模型兼容、范围收敛、截止时间归一和导出，禁止通过导入副作用
替换基础 readiness Service 的函数。
"""
from __future__ import annotations

from datetime import date, datetime, timedelta

from app.core.affairs_security import build_affairs_context
from app.services.db_service import session

from . import academic_affairs_dashboard_readiness_service as _base


_COLLEGE_SAFE_KEYS = {
    "CURRENT_TERM_MISSING",
    "TERM_FIELDS_INCOMPLETE",
    "TIME_SLOT_MISSING",
    "PROGRAM_BINDING_UNRESOLVED",
    "TEACHING_TASK_MISSING",
    "TEACHING_TASK_NOT_READY",
    "SCHEDULE_NOT_PUBLISHED",
    "SCHEDULE_HARD_CONFLICT",
}


def _operation_risks(db, term):
    """按当前真实模型统计在途风险；调停课模型没有 term_id，禁止虚构字段。"""
    from app.models import AaScheduleChange, AaStatusChange, AcademicWarning

    risks = []
    pending_changes = db.query(AaScheduleChange).filter(
        AaScheduleChange.tenant_id == _base._tid(),
        AaScheduleChange.status.in_(["SUBMITTED", "COLLEGE_REVIEW", "ACADEMIC_REVIEW"]),
        AaScheduleChange.is_deleted.is_(False),
    ).count()
    if pending_changes:
        risks.append(_base._item(
            key="SCHEDULE_CHANGE_PENDING",
            severity="RISK",
            title="存在在途调停课申请",
            summary=f"{pending_changes} 条调课、停课或补课申请尚未生效。",
            rule_code="DASHBOARD_SCHEDULE_CHANGE_PENDING",
            count=pending_changes,
            route="/admin/academic-affairs/schedule-changes",
            owner_role="学院教务员 / 教务处",
        ))

    pending_status = db.query(AaStatusChange).filter(
        AaStatusChange.tenant_id == _base._tid(),
        AaStatusChange.status.in_(["SUBMITTED", "IN_REVIEW"]),
        AaStatusChange.is_deleted.is_(False),
    ).count()
    if pending_status:
        risks.append(_base._item(
            key="STATUS_CHANGE_PENDING",
            severity="RISK",
            title="存在在途学籍异动",
            summary=f"{pending_status} 条学籍异动尚未完成审批或生效。",
            rule_code="DASHBOARD_STATUS_CHANGE_PENDING",
            count=pending_status,
            route="/admin/academic-affairs/status-changes",
            owner_role="学院教务员 / 教务处",
        ))

    high_warnings = db.query(AcademicWarning).filter(
        AcademicWarning.tenant_id == _base._tid(),
        AcademicWarning.level == "HIGH",
        AcademicWarning.status == "PENDING_HANDLE",
        AcademicWarning.record_status == "ACTIVE",
        AcademicWarning.is_deleted.is_(False),
    ).count()
    if high_warnings:
        risks.append(_base._item(
            key="HIGH_WARNING_PENDING",
            severity="RISK",
            title="高等级学业预警待处置",
            summary=f"{high_warnings} 条高等级学业预警尚未形成闭环。",
            rule_code="DASHBOARD_HIGH_WARNING_PENDING",
            count=high_warnings,
            route="/admin/academic-affairs/warnings",
            owner_role="辅导员 / 学院教务员",
        ))
    return risks


def _raw_readiness(user, term_id=None) -> dict:
    """复用基础域规则，但以真实模型兼容实现聚合运行风险。"""
    with session() as db:
        ctx = build_affairs_context(user, db)
        term = _base._load_term(db, term_id)
        today = _base._local_today(db)
        stage, week = _base._stage(term, today)
        college_ids = _base._scope_college_ids(ctx)

        items = _base._term_setup_items(db, term)
        if term and stage not in {"TERM_SETUP", "ARCHIVED"}:
            items.extend(_base._program_items(db, term, college_ids))
            items.extend(_base._task_items(db, term, college_ids))
            items.extend(_base._schedule_items(db, term, college_ids))
            items.extend(_base._exam_items(db, term, stage))
            items.extend(_base._grade_items(db, term, stage))
            items.extend(_operation_risks(db, term))

        items.sort(key=lambda row: (
            _base._SEVERITY_ORDER.get(row["severity"], 9),
            row["deadline"] or "9999-12-31",
            row["key"],
        ))
        blocker_count = sum(row["count"] for row in items if row["severity"] == "BLOCKER")
        risk_count = sum(row["count"] for row in items if row["severity"] == "RISK")
        status = "BLOCKED" if blocker_count else ("RISK" if risk_count else "NORMAL")
        conclusion = {
            "BLOCKED": "本学期当前阶段不可继续，请先处理阻断项",
            "RISK": "本学期可以继续，但存在需要尽快处理的风险",
            "NORMAL": "本学期当前阶段运行正常，可以继续",
        }[status]
        if stage == "ARCHIVED":
            status = "NORMAL"
            conclusion = "本学期已经完成正式归档，业务数据保持只读"

        return {
            "term": {
                "termId": str(term.id) if term else None,
                "termCode": _base._term_code(term),
                "termLabel": _base._term_label(term),
                "status": term.status if term else None,
                "startDate": _base._iso(term.start_date) if term else None,
                "endDate": _base._iso(term.end_date) if term else None,
                "teachingWeeks": term.teaching_weeks if term else None,
                "examWeekStart": term.exam_week_start if term else None,
            },
            "stage": stage,
            "stageLabel": _base._STAGE_LABELS[stage],
            "currentWeek": week,
            "today": today.isoformat(),
            "status": status,
            "conclusion": conclusion,
            "blockerCount": blocker_count,
            "riskCount": risk_count,
            "itemCount": len(items),
            "topItems": items[:3],
            "items": items,
            "scopeType": getattr(ctx, "scope_type", None),
            "generatedAt": datetime.utcnow().isoformat(),
        }


def _exam_deadline(data: dict) -> str | None:
    term = data.get("term") or {}
    raw_start = str(term.get("startDate") or "")[:10]
    exam_week = term.get("examWeekStart")
    if not raw_start or not exam_week:
        return None
    try:
        start = date.fromisoformat(raw_start)
        return (start + timedelta(days=(int(exam_week) - 1) * 7)).isoformat()
    except (TypeError, ValueError):
        return None


def _normalize_deadlines(data: dict, items: list[dict]) -> list[dict]:
    exam_deadline = _exam_deadline(data)
    output = []
    for source in items:
        row = dict(source)
        if row.get("key") in {"EXAM_NOT_PUBLISHED", "EXAM_COURSE_INCOMPLETE"} and exam_deadline:
            row["deadline"] = exam_deadline
            row["deadlineLabel"] = exam_deadline
        output.append(row)
    return output


def _mark_current(data: dict) -> dict:
    enriched = dict(data or {})
    term = dict(enriched.get("term") or {})
    selected_id = str(term.get("termId") or "")
    with session() as db:
        current = _base._load_term(db, None)
    current_id = str(current.id) if current else ""
    term["isCurrent"] = bool(selected_id and selected_id == current_id)
    term["currentTermId"] = current_id or None
    term["currentTermLabel"] = _base._term_label(current) if current else None
    enriched["term"] = term
    return enriched


def _recalculate(data: dict, items: list[dict], *, scope_type: str, scope_note: str) -> dict:
    data = _mark_current(data)
    items = _normalize_deadlines(data, items)
    if data.get("stage") == "ARCHIVED":
        items = []
    items = sorted(items, key=lambda row: (
        _base._SEVERITY_ORDER.get(row.get("severity"), 9),
        row.get("deadline") or "9999-12-31",
        row.get("key") or "",
    ))
    blocker_count = sum(int(row.get("count") or 0) for row in items if row.get("severity") == "BLOCKER")
    risk_count = sum(int(row.get("count") or 0) for row in items if row.get("severity") == "RISK")
    status = "BLOCKED" if blocker_count else ("RISK" if risk_count else "NORMAL")
    conclusion = {
        "BLOCKED": "本学期当前阶段不可继续，请先处理阻断项",
        "RISK": "本学期可以继续，但存在需要尽快处理的风险",
        "NORMAL": "本学期当前阶段运行正常，可以继续",
    }[status]
    if data.get("stage") == "ARCHIVED":
        status = "NORMAL"
        conclusion = "本学期已经完成正式归档，业务数据保持只读"
    return {
        **data,
        "status": status,
        "conclusion": conclusion,
        "blockerCount": blocker_count,
        "riskCount": risk_count,
        "itemCount": len(items),
        "topItems": items[:3],
        "items": items,
        "scopeType": scope_type,
        "scopeNote": scope_note,
        "generatedAt": datetime.utcnow().isoformat(),
    }


def _restricted(user, scope_type: str, message: str, term_id=None) -> dict:
    with session() as db:
        term = _base._load_term(db, term_id)
        today = _base._local_today(db)
        stage, week = _base._stage(term, today)
    item = _base._item(
        key="DASHBOARD_SCOPE_RESTRICTED",
        severity="RISK",
        title="当前角色不展示学校级教务运行汇总",
        summary=message,
        rule_code="DASHBOARD_SCOPE_FAIL_CLOSED",
        route="/",
        owner_role="学校教务管理员",
        count=1,
    )
    data = {
        "term": {
            "termId": str(term.id) if term else None,
            "termCode": _base._term_code(term),
            "termLabel": _base._term_label(term),
            "status": term.status if term else None,
            "startDate": _base._iso(term.start_date) if term else None,
            "endDate": _base._iso(term.end_date) if term else None,
            "teachingWeeks": term.teaching_weeks if term else None,
            "examWeekStart": term.exam_week_start if term else None,
        },
        "stage": stage,
        "stageLabel": _base._STAGE_LABELS[stage],
        "currentWeek": week,
        "today": today.isoformat(),
    }
    return _recalculate(data, [item], scope_type=scope_type, scope_note=message)


def readiness(user, term_id=None) -> dict:
    with session() as db:
        ctx = build_affairs_context(user, db)
        scope_type = str(getattr(ctx, "scope_type", None) or "NONE").upper()
        college_ids = {
            int(value) for value in (getattr(ctx, "college_ids", None) or [])
            if str(value).isdigit()
        }

    if scope_type == "TENANT_ALL":
        data = _raw_readiness(user, term_id)
        return _recalculate(data, data.get("items") or [], scope_type=scope_type,
                            scope_note="按全校教务数据判断当前阶段 readiness")

    if scope_type == "COLLEGE":
        if not college_ids:
            return _restricted(
                user, scope_type,
                "当前学院角色未取得任何学院数据范围，已停止加载教务汇总。",
                term_id,
            )
        data = _raw_readiness(user, term_id)
        safe_items = [row for row in (data.get("items") or []) if row.get("key") in _COLLEGE_SAFE_KEYS]
        return _recalculate(
            data,
            safe_items,
            scope_type=scope_type,
            scope_note="当前仅按本院培养方案、教学任务和课表判断；全校考务、成绩与预警汇总不向学院范围放大。",
        )

    return _restricted(
        user,
        scope_type,
        "当前角色仅可处理本人或本班业务；学校级 readiness、全校成绩、考务和预警数量已 fail-closed。",
        term_id,
    )


def export_readiness_xlsx(user, term_id=None, purpose=""):
    purpose = str(purpose or "").strip()
    if len(purpose) < 5:
        from app.core.exceptions import AppException
        raise AppException("VALIDATION_ERROR", "导出用途必填且不少于5个字")
    data = readiness(user, term_id)
    from app.services.xlsx_util import build_ledger_xlsx

    headers = ["级别", "阻断/风险项", "规则编号", "数量", "责任角色", "截止时间", "处理入口", "说明"]
    rows = [[
        "阻断" if row["severity"] == "BLOCKER" else "风险",
        row["title"], row["ruleCode"], row["count"], row["ownerRole"],
        row["deadlineLabel"], row["route"], row["summary"],
    ] for row in data["items"]]
    if not rows:
        rows = [["正常", "当前阶段无阻断或风险", "DASHBOARD_READY", 0, "—", "—", "—", data["conclusion"]]]
    watermark = (
        f"学期：{data['term']['termLabel']}  范围：{data.get('scopeType') or '-'}  "
        f"导出时间：{datetime.utcnow().strftime('%Y-%m-%d %H:%M')}  用途：{purpose}"
    )
    content = build_ledger_xlsx("开学与学期运行准备清单", headers, rows, watermark=watermark)
    return content, f"{data['term']['termCode'] or '未设置学期'}-教务运行准备清单.xlsx"
