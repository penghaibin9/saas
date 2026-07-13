"""岗位实习中心 · 实习统计 API（/api/v1/internship/stats/*）。

指标口径（落实率/协议签署率/打卡合规率/成绩分布/就业率/归档率）+ 维度筛选（学院/专业/班级）+
数据范围隔离（service 内处理）+ 导出。PC 管理端（学生 403 由注册处 require_staff 统一门禁）。
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends

from app.core.response import success
from app.core.security import get_current_user
from app.modules.internship.services import internship_stats_service as svc

router = APIRouter(prefix="/internship", tags=["岗位实习-实习统计"])


@router.get("/stats/overview", summary="实习总览统计（指标/计数/成绩分布，按数据范围+维度筛选）")
def stats_overview(college: Optional[str] = None, major: Optional[str] = None,
                   className: Optional[str] = None, user=Depends(get_current_user)):
    return success(svc.overview(user, college=college, major=major, class_name=className))


@router.get("/stats/dimensions", summary="统计维度选项（学院/专业/班级）")
def stats_dimensions(user=Depends(get_current_user)):
    return success(svc.dimension_options(user))


@router.post("/stats/export", summary="导出实习统计台账（xlsx）")
def stats_export(college: Optional[str] = None, major: Optional[str] = None,
                 className: Optional[str] = None, user=Depends(get_current_user)):
    return success(svc.export_stats(user, college=college, major=major, class_name=className))
