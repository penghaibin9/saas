"""Stage B 教师小程序审批队列 API。"""
from fastapi import APIRouter, Depends, Query

from app.core.response import paginate, success
from app.core.security import require_staff
from app.services import approval_mobile_query_service as mobileq

router = APIRouter(prefix="/approvals/mobile", tags=["approvals-mobile"])


@router.get("/queue", summary="教师小程序审批 pending/done/mine 真分页")
def list_mobile_queue(
    mode: str = Query("pending", pattern="^(pending|done|mine)$"),
    page: int = Query(1, ge=1),
    pageSize: int = Query(20, ge=1, le=100),
    keyword: str | None = Query(None, max_length=100),
    bizType: str | None = Query(None, max_length=100),
    user=Depends(require_staff),
):
    items, total = mobileq.list_queue(
        mode,
        page,
        pageSize,
        user=user,
        keyword=keyword,
        biz_type=bizType,
    )
    return success(paginate(items, total, page, pageSize))
