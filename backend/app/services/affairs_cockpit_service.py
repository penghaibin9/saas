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
            "total": None,
            "highlight": None,
            "highlightLabel": highlight_label,
            "message": "统计暂不可用",
            "updatedAt": updated,
            "route": route,
            "_raw": None,
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
    from app.services import affairs_discipline_service as disc_svc
    from app.services import affairs_funding_service as funding_svc

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

    domains = []
    for d in (aid, funding, disc, act):
        domains.append({k: v for k, v in d.items() if k != "_raw"})

    def _total_or_none(d):
        return d["total"] if d["status"] == "OK" else None

    reconcile = {}
    if disc["status"] == "OK" and disc.get("_raw"):
        reconcile = (disc["_raw"].get("reconcile") or {})

    return {
        "domains": domains,
        "totals": {
            "aidApplications": _total_or_none(aid),
            "fundingApplications": _total_or_none(funding),
            "disciplineCases": _total_or_none(disc),
            "activities": _total_or_none(act),
        },
        "disciplineReconcileConsistent": bool(reconcile.get("consistent", True)) if disc["status"] == "OK" else None,
        "updatedAt": _iso(datetime.utcnow()),
    }
