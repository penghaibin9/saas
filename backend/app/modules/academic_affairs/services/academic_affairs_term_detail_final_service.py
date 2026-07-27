"""AA-TERM-01 学期详情最终语义层。

修正第一轮实现与当前模型/前端路由的偏差：
- AffairsAuditTrail 是 append-only，不存在 is_deleted；
- 关联业务跳转必须命中现有正式路由；
- 只有 PUBLISHED 学期可设为当前；
- PUBLISHED/FROZEN 允许仅修改显示名称，禁止直接修改时间轴；
- ARCHIVED 全字段只读。
"""
from __future__ import annotations

from sqlalchemy import select

from app.services.db_service import _iso, _tid

from . import academic_affairs_service as _legacy
from . import academic_affairs_term_detail_facade as _impl


_DOMAIN_ROUTES = {
    "CALENDAR": "/admin/academic-affairs/calendar",
    "SCHEDULE": "/admin/academic-affairs/schedule",
    "EXAM": "/admin/academic-affairs/exam",
    "SELECTION": "/admin/academic-affairs/selection",
    "GRADE": "/admin/academic-affairs/grade-overview",
}


def _route(path: str, term_id) -> str:
    return f"{path}?termId={term_id}"


def _timeline(db, term_id) -> list[dict]:
    """审计表是 append-only；禁止查询不存在的 is_deleted 字段。"""
    from app.models import AffairsAuditTrail

    rows = db.scalars(select(AffairsAuditTrail).where(
        AffairsAuditTrail.tenant_id == _tid(),
        AffairsAuditTrail.biz_type == "AA_TERM",
        AffairsAuditTrail.biz_id == int(term_id),
    ).order_by(AffairsAuditTrail.occurred_at.desc(), AffairsAuditTrail.id.desc())).all()
    return [{
        "auditId": str(row.id),
        "action": row.action,
        "actionLabel": _impl._ACTION_LABELS.get(row.action, row.action),
        "operator": row.operator or "系统",
        "roleName": row.role_name or "",
        "detail": row.detail or "",
        "occurredAt": _iso(row.occurred_at),
    } for row in rows]


_original_linked_data = _impl._linked_data
_original_allowed_actions = _impl._allowed_actions


def _linked_data(db, term) -> dict:
    data = _original_linked_data(db, term)
    term_id = term.id
    data["calendar"]["route"] = _route(_DOMAIN_ROUTES["CALENDAR"], term_id)
    data["teachingTasks"]["route"] = _route("/admin/academic-affairs/teaching-tasks", term_id)
    data["schedules"]["route"] = _route(_DOMAIN_ROUTES["SCHEDULE"], term_id)
    data["exams"]["route"] = _route(_DOMAIN_ROUTES["EXAM"], term_id)
    data["selections"]["route"] = _route(_DOMAIN_ROUTES["SELECTION"], term_id)
    data["grades"]["route"] = _route(_DOMAIN_ROUTES["GRADE"], term_id)
    return data


def _allowed_actions(term, linked) -> dict:
    data = _original_allowed_actions(term, linked)
    status = str(term.status or "").upper()
    data.update({
        "editBasic": status == "DRAFT",
        "editNameOnly": status in {"PUBLISHED", "FROZEN"},
        "publish": status == "DRAFT",
        "setCurrent": status == "PUBLISHED" and not bool(term.is_current),
        "freeze": status == "PUBLISHED",
        "archive": status == "FROZEN",
    })
    if status == "ARCHIVED":
        data.update({
            "editBasic": False,
            "editNameOnly": False,
            "publish": False,
            "setCurrent": False,
            "freeze": False,
            "archive": False,
        })
    return data


def _normalize_preview(data: dict) -> dict:
    """按真实状态机重算保存结论，避免仅改名称被结构影响误拦截。"""
    output = dict(data or {})
    status = str(output.get("termStatus") or "").upper()
    changes = list(output.get("changes") or [])
    structural = bool(output.get("structuralChange"))

    impacts = []
    for source in output.get("impacts") or []:
        row = dict(source)
        domain = str(row.get("domain") or "").upper()
        if domain in _DOMAIN_ROUTES:
            row["route"] = _route(_DOMAIN_ROUTES[domain], output.get("termId"))
        impacts.append(row)
    output["impacts"] = impacts

    if not changes:
        output.update({
            "directChangeAllowed": False,
            "canSave": False,
            "conclusion": "未检测到字段变化。",
        })
        return output

    if status == "ARCHIVED":
        output.update({
            "directChangeAllowed": False,
            "canSave": False,
            "blockers": [{
                "code": "TERM_ARCHIVED_READ_ONLY",
                "message": "已归档学期只读，不可修改。",
            }],
            "blockerCount": 1,
            "conclusion": "已归档学期只读，不可保存修改。",
        })
        return output

    if not structural and status in {"DRAFT", "PUBLISHED", "FROZEN"}:
        output.update({
            "directChangeAllowed": True,
            "canSave": True,
            "conflictCount": 0,
            "blockers": [],
            "blockerCount": 0,
            "conclusion": "本次仅修改学期显示名称，可以直接保存。",
        })
        return output

    if structural and status != "DRAFT":
        blockers = [row for row in (output.get("blockers") or [])
                    if row.get("code") != "TERM_CHANGE_LINKED_CONFLICTS"]
        if not any(row.get("code") == "TERM_PUBLISHED_DIRECT_CHANGE_FORBIDDEN" for row in blockers):
            blockers.insert(0, {
                "code": "TERM_PUBLISHED_DIRECT_CHANGE_FORBIDDEN",
                "message": "已发布或冻结学期禁止直接修改时间轴，请保留原时间轴或走正式变更流程。",
            })
        output.update({
            "directChangeAllowed": False,
            "canSave": False,
            "blockers": blockers,
            "blockerCount": len(blockers),
            "conclusion": "当前状态禁止直接修改学期时间轴。",
        })
        return output

    conflict_count = int(output.get("conflictCount") or 0)
    output.update({
        "directChangeAllowed": True,
        "canSave": conflict_count == 0,
        "conclusion": (
            "草稿学期可以保存本次修改。"
            if conflict_count == 0 else
            f"拟调整时间轴与 {conflict_count} 条现有业务事实冲突，请先处理。"
        ),
    })
    return output


# 安装到第一轮实现内部，确保详情、预览、更新三条链使用同一口径。
_impl._timeline = _timeline
_impl._linked_data = _linked_data
_impl._allowed_actions = _allowed_actions


def term_detail(term_id, user) -> dict:
    return _impl.term_detail(term_id, user)


def impact_preview(term_id, user, body=None) -> dict:
    return _normalize_preview(_impl.impact_preview(term_id, user, body or {}))


def update_term(term_id, user, body: dict) -> dict:
    return _impl.update_term(term_id, user, body)


# 现有 GET /terms/{termId} 继续走原路由，但运行最终详情实现。
_legacy.term_detail = term_detail
