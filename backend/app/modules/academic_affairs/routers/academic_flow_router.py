"""教务第五版只读责任与进度入口。"""
from fastapi import APIRouter, Depends, Query

from app.core.permissions import require_permission
from app.core.response import success
from app.modules.academic_affairs.services import academic_affairs_flow_service as service

router = APIRouter(prefix="/academic-affairs", tags=["教务责任接力"])


@router.get("/flow", summary="按当前角色与真实范围查看学期责任接力")
def flow(termId: int | None = Query(None, gt=0), collegeId: int | None = Query(None, gt=0),
         user=Depends(require_permission("academicAffairs.dashboard.view"))):
    return success(service.flow(user, termId, collegeId))
