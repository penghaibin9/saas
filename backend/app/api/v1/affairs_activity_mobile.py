"""教师移动端活动签到辅助读接口。"""
from fastapi import APIRouter, Depends

from app.core.permissions import require_permission
from app.core.response import success

router = APIRouter(tags=["学工中心·活动签到"])


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
