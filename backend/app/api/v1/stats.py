"""跨域真实统计聚合 API（/api/v1/stats/*）——工作台 + 数据中心 BI。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.core.response import success
from app.core.security import require_staff
from app.services import stats_service as svc

router = APIRouter(prefix="/stats", tags=["跨域统计"])


@router.get("/overview", summary="数据中心总览（真实聚合）")
def overview(caliber: str = Query("REGISTERED"), user=Depends(require_staff)):
    return success(svc.get_overview(caliber))


@router.get("/lifecycle", summary="生命周期漏斗（真实）")
def lifecycle(caliber: str = Query("REGISTERED"), user=Depends(require_staff)):
    return success(svc.get_lifecycle(caliber))


@router.get("/risk", summary="全域风险分布（真实）")
def risk(user=Depends(require_staff)):
    return success(svc.get_risk_stats())


@router.get("/workbench", summary="工作台首页汇总（真实）")
def workbench(user=Depends(require_staff)):
    return success(svc.get_workbench_summary())


@router.get("/lifecycle-board", summary="生命周期驾驶舱聚合（同构前端，有源真实/无源占位）")
def lifecycle_board(caliber: str = Query("REGISTERED"), user=Depends(require_staff)):
    return success(svc.get_lifecycle_board(caliber))


@router.get("/risk-board", summary="风险驾驶舱聚合（来源/等级真实，进度/趋势待接入）")
def risk_board(user=Depends(require_staff)):
    return success(svc.get_risk_board())


@router.get("/rankings", summary="学院/专业/班级排行（学生主档真实聚合）")
def rankings(level: str = Query("COLLEGE"), collegeId: str | None = Query(None),
             majorId: str | None = Query(None), user=Depends(require_staff)):
    return success(svc.get_rankings(level=level, college_id=collegeId, major_id=majorId))


@router.get("/drilldown", summary="下钻学生清单（真实 + 服务端脱敏学号）")
def drilldown(collegeId: str | None = Query(None), majorId: str | None = Query(None),
              classId: str | None = Query(None), stage: str | None = Query(None),
              keyword: str | None = Query(None), page: int = Query(1), pageSize: int = Query(10),
              user=Depends(require_staff)):
    return success(svc.get_drilldown(college_id=collegeId, major_id=majorId, class_id=classId,
                                     stage=stage, keyword=keyword, page=page, page_size=pageSize))
