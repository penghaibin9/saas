"""13A 学工中心 API（/api/v1/student-affairs/*）—— P1：首页三角色视图 + 班级/班干部骨架。"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Path
from pydantic import BaseModel, Field

from app.core.response import success
from app.core.security import require_staff
from app.services import affairs_dashboard_service as svc

router = APIRouter(prefix="/student-affairs", tags=["学工中心"])


@router.get("/dashboard", summary="学工首页（三角色视图，按数据范围聚合）")
def dashboard(user=Depends(require_staff)):
    return success(svc.get_dashboard(user))


@router.get("/classes", summary="班级列表（按数据范围）")
def classes(user=Depends(require_staff)):
    return success({"items": svc.list_classes(user)})


@router.get("/classes/{classId}/cadres", summary="班干部列表")
def cadres(classId: int = Path(...), user=Depends(require_staff)):
    return success({"items": svc.list_cadres(classId, user)})


class CadreCreate(BaseModel):
    studentId: str = Field(..., min_length=1, description="学生 id")
    position: str = Field(..., min_length=1, description="职务编码：MONITOR/LEAGUE_SECRETARY/...")
    termCode: Optional[str] = Field(None, description="学年学期编码")


@router.post("/classes/{classId}/cadres", summary="任命班干部")
def add_cadre(body: CadreCreate, classId: int = Path(...), user=Depends(require_staff)):
    return success(svc.add_cadre(classId, body, user), message="已任命")


@router.delete("/classes/cadres/{cadreId}", summary="免去班干部")
def remove_cadre(cadreId: int = Path(...), user=Depends(require_staff)):
    return success(svc.remove_cadre(cadreId, user), message="已免去")
