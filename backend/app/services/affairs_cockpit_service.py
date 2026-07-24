"""13A-D 学工统计驾驶舱（统计与档案·学院/校级驾驶舱）。

复用各域已有统计口径（困难/奖助/违纪/活动二课/谈话），聚合为一屏驾驶舱 + 下钻入口。
仅聚合、按数据范围（各域统计已各自裁剪）；不落个体明细。
单域失败返回 ERROR/DEGRADED，禁止吞异常后被页面显示成假 0。
"""
from __future__ import annotations

import logging
from datetime import datetime

from app.services.db_service import _iso

logger = logging.getLogger(__name__)


def _safe_domain(key: str, label: str, route: str, fn, user, *, total_key="total",
                 highlight_from=None, highlight_label="") -> dict:
    """执行单域统计；失败不拖垮整屏，也不把失败伪装成 total=0。

    highlight_from: None | str字段名 | callable(raw)->int
    """
    updated = _iso(datetime.utcnow())
    try:
        data = fn(user) or {}
        total = int(data.get(total_key, 0) or 0)
        if callable(highlight_from):
            highlight = int(highlight_from(data) or 0)
        elif highlight_from:
            highlight = int(data.get(highlight_from, 0) or 0)
        else:
            highlight = 0
        return {
            "key": key,
            "label": label,
            "status": "OK",
            # metrics 保留各域统计的真实口径；total/highlight 是旧驾驶舱卡片的兼容字段。
            "metrics": data,
            "total": total,
            "highlight": highlight,
            "highlightLabel": highlight_label,
            "message": "",
            "updatedAt": updated,
            "route": route,
            "_raw": data,
        }
    except Exception:  # noqa: BLE001 —— 单域异常不拖垮整屏，但必须可识别
        logger.exception("student-affairs cockpit domain failed: %s", key)
        return {
            "key": key,
            "label": label,
            "status": "ERROR",
            "metrics": {},
            "total": None,
            "highlight": None,
            "highlightLabel": highlight_label,
            "message": "统计暂不可用",
            "updatedAt": updated,
            "route": route,
            "_raw": None,
        }


def _degraded_domain(key: str, label: str, route: str, message: str) -> dict:
    """没有独立聚合口径时明确降级，绝不能把缺口显示为 0。"""
    return {
        "key": key,
        "label": label,
        "status": "DEGRADED",
        "metrics": {},
        "total": None,
        "highlight": None,
        "highlightLabel": "",
        "message": message,
        "updatedAt": _iso(datetime.utcnow()),
        "route": route,
    }


def _disc_effective(data) -> int:
    for r in (data.get("byStatus") or []):
        if r.get("key") == "EFFECTIVE":
            return int(r.get("count", 0) or 0)
    return 0


def cockpit(user) -> dict:
    """各域概览卡（status + total + 关键指标 + 下钻路由）。"""
    from app.services import affairs_activity_service as activity_svc
    from app.services import affairs_aid_service as aid_svc
    from app.services import affairs_dashboard_service as dashboard_svc
    from app.services import affairs_discipline_service as disc_svc
    from app.services import affairs_dorm_service as dorm_svc
    from app.services import affairs_funding_service as funding_svc
    from app.services import affairs_leave_service as leave_svc
    from app.services import affairs_mental_service as mental_svc
    from app.services import affairs_risk_service as risk_svc
    from app.services import affairs_talk_service as talk_svc

    def _dashboard_card(card_key: str) -> dict:
        dashboard = dashboard_svc.get_dashboard(user)
        cards = {card.get("key"): card for card in dashboard.get("summaryCards") or []}
        card = cards.get(card_key)
        if card is None:
            raise RuntimeError(f"dashboard card unavailable: {card_key}")
        return {"total": card.get("value", 0), **{
            key: value for key, value in card.items() if key not in {"key", "label", "value"}
        }}

    def _leave_metrics(_user) -> dict:
        data = leave_svc.leave_stats(_user)
        metrics = {
            item.get("key"): item.get("value")
            for item in data.get("metrics") or [] if item.get("key")
        }
        return {"total": metrics.get("leaveStudentCount", 0), **metrics}

    def _risk_metrics(_user) -> dict:
        _items, _total, stats = risk_svc.list_risks(_user, page=1, page_size=1)
        return stats

    student = _safe_domain(
        "student", "学生主档", "/admin/student/list", lambda _user: _dashboard_card("studentTotal"), user,
        highlight_from=None)
    school_class = _safe_domain(
        "class", "班级管理", "/admin/campus-service/classes", lambda _user: _dashboard_card("classTotal"), user,
        highlight_from=None)
    leave = _safe_domain(
        "leave", "请假管理", "/admin/campus-service/leave-stats", _leave_metrics, user,
        highlight_from="pendingReview", highlight_label="待审批")
    dorm = _safe_domain(
        "dorm", "宿舍管理", "/admin/student-affairs/dorm/stats", dorm_svc.occupancy_stats, user,
        total_key="totalBeds", highlight_from="occupiedBeds", highlight_label="已入住床位")
    risk = _safe_domain(
        "risk", "风险预警", "/admin/student-affairs/risk", _risk_metrics, user,
        highlight_from="highCritical", highlight_label="高危/危急")

    aid = _safe_domain(
        "aid", "困难认定", "/admin/student-affairs/aid/stats",
        aid_svc.aid_stats, user, total_key="total", highlight_from="approved", highlight_label="已认定")
    funding = _safe_domain(
        "funding", "奖助勤贷补", "/admin/student-affairs/funding/stats",
        funding_svc.funding_stats, user, total_key="total", highlight_from="granted", highlight_label="已获资助")
    disc = _safe_domain(
        "discipline", "违纪处分", "/admin/student-affairs/discipline/stats",
        disc_svc.discipline_stats, user, total_key="total",
        highlight_from=_disc_effective, highlight_label="生效中")
    act = _safe_domain(
        "activity", "学生活动·二课", "/admin/student-affairs/activity/stats",
        activity_svc.activity_stats, user, total_key="totalActivities",
        highlight_from="creditStudents", highlight_label="获学分学生")
    talk = _safe_domain(
        "talk", "谈心谈话", "/admin/student-affairs/talk/stats", talk_svc.talk_stats, user,
        highlight_from="completed", highlight_label="已完成")
    mental = _safe_domain(
        "mental", "心理关注", "/admin/student-affairs/mental/stats", mental_svc.stats, user,
        highlight_from="openCrisis", highlight_label="未关闭危机")

    domains = [
        student, school_class, leave, dorm, risk, aid, funding, disc, talk,
        _degraded_domain("family", "家校联系", "/admin/student-affairs/family",
                         "暂无按数据范围的独立聚合口径"),
        mental, act,
        _degraded_domain("club", "社团管理", "/admin/student-affairs/activity/clubs",
                         "暂无独立聚合统计"),
        _degraded_domain("organization", "学生组织", "/admin/student-affairs/activity/organizations",
                         "暂无独立聚合统计"),
        _degraded_domain("partyLeague", "党团建设", "/admin/student-affairs/activity/party-league",
                         "暂无独立聚合统计"),
        _degraded_domain("archive", "学工归档", "/admin/student-affairs/archive",
                         "暂无独立聚合统计"),
    ]
    domains = [{k: v for k, v in domain.items() if k != "_raw"} for domain in domains]

    def _total_or_none(d):
        return d["total"] if d["status"] == "OK" else None

    reconcile = {}
    if disc["status"] == "OK" and disc.get("_raw"):
        reconcile = (disc["_raw"].get("reconcile") or {})

    return {
        "domains": domains,
        "domainsByKey": {domain["key"]: domain for domain in domains},
        "totals": {
            "aidApplications": _total_or_none(aid),
            "fundingApplications": _total_or_none(funding),
            "disciplineCases": _total_or_none(disc),
            "activities": _total_or_none(act),
        },
        "disciplineReconcileConsistent": bool(reconcile.get("consistent", True)) if disc["status"] == "OK" else None,
        "updatedAt": _iso(datetime.utcnow()),
    }
