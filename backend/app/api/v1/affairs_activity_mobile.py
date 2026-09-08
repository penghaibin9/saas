"""教师移动端活动现场办理接口。"""
from typing import Optional

from fastapi import APIRouter, Depends, Path, Query
from pydantic import BaseModel, Field

from app.core.permissions import require_permission
from app.core.response import success

router = APIRouter(tags=["学工中心·活动签到"])


class ActivityTransitionBody(BaseModel):
    action: str = Field(..., description="ENROLL_CLOSE/START/FINISH")
    version: int = Field(..., ge=0, description="页面当前乐观锁版本")


class ActivityVersionBody(BaseModel):
    version: int = Field(..., ge=0, description="页面当前乐观锁版本")


@router.get("/mobile/teacher/affairs/activities", summary="教师移动端活动办理队列")
def teacher_activities(
    status: Optional[str] = None,
    page: int = Query(1, ge=1),
    pageSize: int = Query(20, ge=1, le=100),
    user=Depends(require_permission("studentAffairs.activity.view")),
):
    from app.services import affairs_activity_service as activity
    items, total, status_counts = activity.list_activities(
        user, status=status, page=page, page_size=pageSize,
    )
    return success({
        "items": items,
        "total": total,
        "page": page,
        "pageSize": pageSize,
        "hasMore": page * pageSize < total,
        "statusCounts": status_counts,
    })


@router.get(
    "/mobile/teacher/affairs/activities/{activity_id}/participants",
    summary="教师移动端查看活动名单",
)
def teacher_activity_participants(
    activity_id: int = Path(..., ge=1),
    user=Depends(require_permission("studentAffairs.activity.view")),
):
    from app.services import affairs_activity_service as activity
    return success({"items": activity.list_participants(activity_id, user)})


@router.post(
    "/mobile/teacher/affairs/activities/{activity_id}/transition",
    summary="教师移动端推进活动现场状态",
)
def teacher_activity_transition(
    body: ActivityTransitionBody,
    activity_id: int = Path(..., ge=1),
    user=Depends(require_permission("studentAffairs.activity.publish")),
):
    from app.services import affairs_activity_service as activity
    return success(
        activity.transition_activity(activity_id, user, body.action, body.version),
        message="活动状态已更新",
    )


@router.post(
    "/mobile/teacher/affairs/activities/{activity_id}/confirm",
    summary="教师移动端确认名单并生成积分",
)
def teacher_activity_confirm(
    body: ActivityVersionBody,
    activity_id: int = Path(..., ge=1),
    user=Depends(require_permission("studentAffairs.activity.confirm")),
):
    from app.services import affairs_activity_service as activity
    return success(
        activity.confirm_activity(activity_id, user, body.version),
        message="名单已确认，积分已生成",
    )


@router.get("/mobile/teacher/affairs/activities/ongoing", summary="教师可管理的进行中活动")
def ongoing_activities(user=Depends(require_permission("studentAffairs.activity.publish"))):
    from app.services import affairs_activity_service as activity
    items, total, _counts = activity.list_activities(
        user, status="ONGOING", page=1, page_size=100,
    )
    safe = [
        {
            "activityId": x.get("activityId"),
            "activityName": x.get("activityName"),
            "location": x.get("location") or "",
            "startAt": x.get("startAt"),
            "endAt": x.get("endAt"),
            "signupCount": x.get("signupCount") or 0,
        }
        for x in items
    ]
    return success({"items": safe, "total": total})
