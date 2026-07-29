"""教学任务批次工作台独立路由。

返回批次首屏结论、阻断项、确认率和当前身份允许动作，不把复杂聚合继续塞入历史大路由。
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Path

from app.core.permissions import require_permission
from app.core.response import success
from app.modules.academic_affairs.services import academic_affairs_task_service as service

router = APIRouter(prefix="/academic-affairs", tags=["教务中心-教学任务工作台"])


@router.get("/teaching-task-batches/{batchId}/workbench", summary="教学任务批次工作台（指标/阻断项/下一步）")
def teaching_task_batch_workbench(
    batchId: int = Path(...),
    user=Depends(require_permission("academicAffairs.teachingTask.view")),
):
    return success(service.get_batch_workbench(batchId, user))
