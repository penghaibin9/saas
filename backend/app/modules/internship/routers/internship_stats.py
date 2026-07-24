"""岗位实习中心 · 实习统计 API（/api/v1/internship/stats/*）。

指标口径（落实率/协议签署率/打卡合规率/成绩分布/就业率/归档率）+ 维度筛选（学院/专业/班级）+
数据范围隔离（service 内处理）+ 导出。PC 管理端（学生 403 由注册处 require_staff 统一门禁）。

权限（P3）：查询 internship.stats.view（含指导教师本人范围聚合、领导只读、督导审计）；
导出 internship.stats.export（仅管理员/学院负责人）。
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query

from app.core.permissions import require_permission
from app.core.response import success
from app.modules.internship.services import internship_stats_service as svc

router = APIRouter(prefix="/internship", tags=["岗位实习-实习统计"])

_P_VIEW = "internship.stats.view"
_P_EXPORT = "internship.stats.export"


@router.get("/stats/overview", summary="实习总览统计（指标/计数/成绩分布，按数据范围+维度筛选）")
def stats_overview(college: Optional[str] = None, major: Optional[str] = None,
                   className: Optional[str] = None, batchId: Optional[str] = None,
                   user=Depends(require_permission(_P_VIEW))):
    return success(svc.overview(user, college=college, major=major, class_name=className,
                                batch_id=batchId))


@router.get("/stats/dimensions", summary="统计维度选项（学院/专业/班级）")
def stats_dimensions(batchId: Optional[str] = None, user=Depends(require_permission(_P_VIEW))):
    return success(svc.dimension_options(user, batch_id=batchId))


@router.get("/stats/trends", summary="实习业务月度趋势（建档、报告、指导、巡访）")
def stats_trends(college: Optional[str] = None, major: Optional[str] = None,
                 className: Optional[str] = None, months: int = Query(6, ge=3, le=12),
                 batchId: Optional[str] = None,
                 user=Depends(require_permission(_P_VIEW))):
    return success(svc.trends(user, college=college, major=major, class_name=className,
                              months=months, batch_id=batchId))


@router.post("/stats/export", summary="导出实习统计台账（xlsx）")
def stats_export(college: Optional[str] = None, major: Optional[str] = None,
                 className: Optional[str] = None, batchId: Optional[str] = None,
                 user=Depends(require_permission(_P_EXPORT))):
    return success(svc.export_stats(user, college=college, major=major, class_name=className,
                                    batch_id=batchId))
