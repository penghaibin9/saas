"""AA-DASHBOARD-01 readiness 最终数据范围层。"""
from __future__ import annotations

from datetime import datetime

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


def _recalculate(data: dict, items: list[dict], *, scope_type: str, scope_note: str) -> dict:
    items = sorted(items, key=lambda row: (
        _base._SEVERITY_ORDER.get(row.get("severity"), 9),
        row.get("deadline") or "9999-12-31",
        row.get("key") or "",
    ))
    blocker_count = sum(int(row.get("count") or 0) for row in items if row.get("severity") == "BLOCKER")
    risk_count = sum(int(row.get("count") or 0) for row in items if row.get("severity") == "RISK")
    status = "BLOCKED" if blocker_count else ("RISK" if risk_count else "NORMAL")
    if data.get("stage") == "ARCHIVED":
        status = "NORMAL"
        items = []
        blocker_count = risk_count = 0
    conclusion = {
        "BLOCKED": "本学期当前阶段不可继续，请先处理阻断项",
        "RISK": "本学期可以继续，但存在需要尽快处理的风险",
        "NORMAL": "本学期当前阶段运行正常，可以继续",
    }[status]
    if data.get("stage") == "ARCHIVED":
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


def _restricted(user, scope_type: str, message: str) -> dict:
    with session() as db:
        term = _base._load_term(db, None)
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
        data = _base.readiness(user, term_id)
        return _recalculate(data, data.get("items") or [], scope_type=scope_type,
                            scope_note="按全校教务数据判断当前阶段 readiness")

    if scope_type == "COLLEGE":
        if not college_ids:
            return _restricted(user, scope_type, "当前学院角色未取得任何学院数据范围，已停止加载教务汇总。")
        data = _base.readiness(user, term_id)
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
