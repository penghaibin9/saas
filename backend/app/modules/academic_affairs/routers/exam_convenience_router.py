from fastapi import APIRouter, Depends, Path, Query
from pydantic import BaseModel
from app.core.permissions import require_permission
from app.core.response import paginate, success
from app.modules.academic_affairs.routers import academic_affairs as legacy
from app.modules.academic_affairs.services import exam_convenience_service as convenience

router = APIRouter(prefix="/academic-affairs", tags=["教务中心-考务便利性"])

class BulkCourseBody(BaseModel):
    teachingTaskIds: list[int | str]

class PreviewConfirmBody(BaseModel):
    previewToken: str

@router.get("/exam/batches/{bid}/courses", summary="批次考试课程列表")
def exam_courses(bid: int = Path(...), page: int = Query(1, ge=1), pageSize: int = Query(100, ge=1, le=200), user=Depends(require_permission(legacy._EXAM_VIEW))):
    items, total = convenience.list_courses(user, bid, page, pageSize)
    return success(paginate(items, total, page, pageSize))

@router.get("/exam/batches/{bid}/course-candidates", summary="批量圈定应考课程候选")
def course_candidates(bid: int = Path(...), keyword: str | None = Query(None, max_length=100), page: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=200), user=Depends(require_permission(legacy._EXAM_MANAGE))):
    items, total = convenience.list_course_candidates(bid, user, keyword=keyword, page=page, page_size=pageSize)
    return success(paginate(items, total, page, pageSize))

@router.post("/exam/batches/{bid}/course-candidates/preview", summary="批量圈课预览")
def course_preview(body: BulkCourseBody, bid: int = Path(...), user=Depends(require_permission(legacy._EXAM_MANAGE))):
    return success(convenience.bulk_course_preview(bid, user, body.teachingTaskIds))

@router.post("/exam/batches/{bid}/course-candidates/confirm", summary="批量圈课确认")
def course_confirm(body: PreviewConfirmBody, bid: int = Path(...), user=Depends(require_permission(legacy._EXAM_MANAGE))):
    return success(convenience.bulk_course_confirm(bid, user, body.previewToken))

@router.get("/exam/batches/{bid}/readiness", summary="考务批次发布就绪摘要")
def batch_readiness(bid: int = Path(...), user=Depends(require_permission(legacy._EXAM_VIEW))):
    return success(convenience.batch_readiness(bid, user))
