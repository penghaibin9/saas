"""13A-D 学工统计驾驶舱（统计与档案·学院/校级驾驶舱）。

复用各域已有统计口径（困难/奖助/违纪/活动二课/谈话），聚合为一屏驾驶舱 + 下钻入口。
仅聚合、按数据范围（各域统计已各自裁剪）；不落个体明细。
"""
from __future__ import annotations


def _safe(fn, user):
    try:
        return fn(user) or {}
    except Exception:  # noqa: BLE001 —— 单域统计异常不拖垮整屏
        return {}


def _sum_counts(rows, key="count"):
    return sum(int(r.get(key, 0) or 0) for r in (rows or []))


def cockpit(user) -> dict:
    """各域概览卡（total + 关键指标 + 下钻路由）。"""
    from app.services import affairs_activity_service as activity_svc
    from app.services import affairs_aid_service as aid_svc
    from app.services import affairs_discipline_service as disc_svc
    from app.services import affairs_funding_service as funding_svc

    aid = _safe(aid_svc.aid_stats, user)
    funding = _safe(funding_svc.funding_stats, user)
    disc = _safe(disc_svc.discipline_stats, user)
    act = _safe(activity_svc.activity_stats, user)

    disc_effective = 0
    for r in (disc.get("byStatus") or []):
        if r.get("key") == "EFFECTIVE":
            disc_effective = int(r.get("count", 0) or 0)

    domains = [
        {"key": "aid", "label": "困难认定", "total": int(aid.get("total", 0) or 0),
         "highlight": int(aid.get("approved", 0) or 0), "highlightLabel": "已认定",
         "route": "/admin/student-affairs/aid/stats"},
        {"key": "funding", "label": "奖助勤贷补", "total": int(funding.get("total", 0) or 0),
         "highlight": int(funding.get("granted", 0) or 0), "highlightLabel": "已获资助",
         "route": "/admin/student-affairs/funding/stats"},
        {"key": "discipline", "label": "违纪处分", "total": int(disc.get("total", 0) or 0),
         "highlight": disc_effective, "highlightLabel": "生效中",
         "route": "/admin/student-affairs/discipline/stats"},
        {"key": "activity", "label": "学生活动·二课", "total": int(act.get("totalActivities", 0) or 0),
         "highlight": int(act.get("creditStudents", 0) or 0), "highlightLabel": "获学分学生",
         "route": "/admin/student-affairs/activity/stats"},
    ]
    reconcile = (disc.get("reconcile") or {})
    return {
        "domains": domains,
        "totals": {
            "aidApplications": int(aid.get("total", 0) or 0),
            "fundingApplications": int(funding.get("total", 0) or 0),
            "disciplineCases": int(disc.get("total", 0) or 0),
            "activities": int(act.get("totalActivities", 0) or 0),
        },
        "disciplineReconcileConsistent": bool(reconcile.get("consistent", True)),
    }
