"""跨域真实统计聚合 API（/api/v1/stats/*）——工作台 + 数据中心 BI。

P3/A4 范围口径：
- `/stats/workbench`：按当前登录人数据范围收敛（辅导员本班 / 院级本院 / 校级全校）。
- 数据中心全校 BI（overview/lifecycle/risk/boards/rankings/drilldown）：
  仅 TENANT_ALL 角色可访问；一线角色 403002，禁止把全校数当本班数。
- A4 正式 BI DTO 附带 meta.asOf/caliber/scope/source/qualityFlags，页面可解释数字来源与质量。
"""
from __future__ import annotations

from app.core.timeutil import iso_utc, utc_now
from fastapi import APIRouter, Depends, Query

from app.core.response import success
from app.core.security import require_staff
from app.services import stats_service as svc

router = APIRouter(prefix="/stats", tags=["跨域统计"])


def _with_meta(data: dict, *, caliber: str = "REGISTERED", sources: list[str],
               quality_flags: list[dict] | None = None) -> dict:
    out = dict(data or {})
    out["meta"] = {
        "asOf": out.get("updatedAt") or iso_utc(utc_now()),
        "caliber": caliber,
        "caliberLabel": "在册口径" if caliber == "REGISTERED" else "自然口径",
        "scope": {"scopeType": "TENANT_ALL", "scopeName": "全校"},
        "source": [{"module": x, "mode": "REALTIME_MYSQL"} for x in sources],
        "qualityFlags": quality_flags or [],
    }
    return out


@router.get("/overview", summary="数据中心总览（真实聚合·校级）")
def overview(caliber: str = Query("REGISTERED"), user=Depends(require_staff)):
    svc.require_tenant_all_stats(user)
    return success(_with_meta(
        svc.get_overview(caliber), caliber=caliber,
        sources=["StudentProfile", "OrientationStudent", "AcademicWarning", "InternshipStudent",
                 "GraduationStudent", "EmpStudent", "AffairsRiskRecord", "UnifiedTodo"],
    ))


@router.get("/lifecycle", summary="生命周期漏斗（真实·校级）")
def lifecycle(caliber: str = Query("REGISTERED"), user=Depends(require_staff)):
    svc.require_tenant_all_stats(user)
    return success(_with_meta(
        svc.get_lifecycle(caliber), caliber=caliber,
        sources=["StudentProfile", "OrientationStudent", "InternshipStudent", "GraduationStudent", "EmpStudent"],
    ))


@router.get("/risk", summary="全域风险分布（真实·校级）")
def risk(user=Depends(require_staff)):
    svc.require_tenant_all_stats(user)
    return success(_with_meta(
        svc.get_risk_stats(), sources=["AffairsRiskRecord"],
        quality_flags=[{
            "code": "INTERNSHIP_RISK_NOT_UNIFIED", "severity": "INFO",
            "message": "实习域独立风险处置表尚未并入本聚合，接口不以 0 或演示数据补齐。",
        }],
    ))


@router.get("/workbench", summary="工作台首页汇总（按数据范围收敛）")
def workbench(user=Depends(require_staff)):
    return success(svc.get_workbench_summary(user))


@router.get("/lifecycle-board", summary="生命周期驾驶舱聚合（校级）")
def lifecycle_board(caliber: str = Query("REGISTERED"), user=Depends(require_staff)):
    svc.require_tenant_all_stats(user)
    data = svc.get_lifecycle_board(caliber)
    flags = []
    trends = data.get("trendCharts") if isinstance(data, dict) else None
    if not trends:
        flags.append({
            "code": "TREND_SERIES_NOT_CONFIGURED", "severity": "INFO",
            "message": "历史趋势序列尚未配置，不以 0 或演示曲线填充。",
        })
    return success(_with_meta(
        data, caliber=caliber,
        sources=["StudentProfile", "OrientationStudent", "AcademicWarning", "InternshipStudent",
                 "GraduationStudent", "EmpStudent"], quality_flags=flags,
    ))


@router.get("/risk-board", summary="风险驾驶舱聚合（校级）")
def risk_board(user=Depends(require_staff)):
    svc.require_tenant_all_stats(user)
    data = svc.get_risk_board()
    flags = [{
        "code": "RISK_STATUS_CALIBER_PARTIAL", "severity": "INFO",
        "message": "跨域风险处理进度口径尚未统一，byStatus/trend 为空时代表未配置，不代表 0。",
    }]
    return success(_with_meta(data, sources=["AffairsRiskRecord", "StudentProfile"], quality_flags=flags))


@router.get("/rankings", summary="学院/专业/班级排行（校级）")
def rankings(level: str = Query("COLLEGE"), collegeId: str | None = Query(None),
             majorId: str | None = Query(None), user=Depends(require_staff)):
    svc.require_tenant_all_stats(user)
    return success(_with_meta(
        svc.get_rankings(level=level, college_id=collegeId, major_id=majorId),
        sources=["StudentProfile"],
        quality_flags=[{
            "code": "RANKING_PROXY_CALIBER", "severity": "INFO",
            "message": "completionRate 为生命周期阶段加权推进度；employmentRate 为毕业/校友代理口径，页面必须展示该说明。",
        }],
    ))


@router.get("/drilldown", summary="下钻学生清单（校级）")
def drilldown(collegeId: str | None = Query(None), majorId: str | None = Query(None),
              classId: str | None = Query(None), stage: str | None = Query(None),
              keyword: str | None = Query(None), page: int = Query(1), pageSize: int = Query(10),
              user=Depends(require_staff)):
    svc.require_tenant_all_stats(user)
    return success(_with_meta(
        svc.get_drilldown(college_id=collegeId, major_id=majorId, class_id=classId,
                          stage=stage, keyword=keyword, page=page, page_size=pageSize),
        sources=["StudentProfile"],
    ))
