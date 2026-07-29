"""学生本人评教任务路由。

只返回当前账号稳定学生身份在正式教学班名单中的任务，不暴露其他学生、答卷或匿名去重凭证。
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.core.response import success
from app.core.security import get_current_user
from app.modules.academic_affairs.services import academic_affairs_evaluation_service as service

router = APIRouter(
    prefix="/academic-affairs/evaluation",
    tags=["academic-affairs-student-evaluation"],
)


@router.get("/my-student-tasks", summary="学生本人评教任务")
def my_student_tasks(
    batch_id: int | None = Query(None, alias="batchId"),
    include_closed: bool = Query(True, alias="includeClosed"),
    user=Depends(get_current_user),
):
    return success(
        service.my_student_tasks(
            user,
            batch_id=batch_id,
            include_closed=include_closed,
        )
    )
