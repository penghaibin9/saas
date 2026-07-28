"""过程指导/中期检查学校端批次安全接口。"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select

from app.core.exceptions import not_found
from app.core.response import paginate, success
from app.core.security import get_current_user
from app.models import GraduationGuidance, GraduationGuidancePlan, GraduationStudent
from app.modules.graduation.schemas.graduation_guidance import (
    GuidanceCreate, GuidancePlanCancel, GuidancePlanCheckin, GuidancePlanCreate, GuidanceVoidRequest,
)
from app.modules.graduation.schemas.graduation_midterm import MidtermCheckRequest, MidtermRectifyReview, MidtermRectifySubmit
from app.modules.graduation.services import graduation_guidance_service as guidance
from app.modules.graduation.services import graduation_midterm_service as midterm
from app.modules.graduation.services.graduation_batch_context import assert_student_batch, load_student_in_batch, require_batch_id
from app.modules.graduation.services.graduation_process_consistency import install_process_consistency
from app.modules.graduation.services.graduation_p0_service import void_guidance_scoped
from app.services.db_service import _tid, session

install_process_consistency()
router = APIRouter(tags=["毕业设计-过程批次安全"])


def _guard(student_id, batch_id, *, lock=False):
    with session() as db:
        load_student_in_batch(db, student_id, batch_id, for_update=lock)


def _related_guard(model, record_id, batch_id) -> int:
    with session() as db:
        record = db.scalars(select(model).where(
            model.id == int(record_id), model.tenant_id == _tid(), model.is_deleted.is_(False),
        )).first()
        if not record:
            raise not_found("指导记录或计划不存在")
        student = db.get(GraduationStudent, int(record.gd_student_id))
        assert_student_batch(student, batch_id)
        return int(student.id)


@router.get("/gd-guidances/stats")
def guidance_stats(
    threshold: int = Query(3, ge=1, le=50), batchId: int = Query(..., ge=1),
    user=Depends(get_current_user),
):
    return success(guidance.guidance_stats(threshold, batch_id=require_batch_id(batchId)))


@router.get("/gd-guidances")
def guidance_list(
    page: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=200),
    gdStudentId: Optional[str] = None, keyword: Optional[str] = None,
    batchId: int = Query(..., ge=1), user=Depends(get_current_user),
):
    if gdStudentId:
        _guard(gdStudentId, batchId)
    items, total = guidance.list_guidance(
        page, pageSize, gd_student_id=gdStudentId, keyword=keyword, batch_id=batchId,
    )
    return success(paginate(items, total, page, pageSize))


@router.post("/gd-guidances/{gd_student_id}")
def guidance_create(
    gd_student_id: str, body: GuidanceCreate,
    batchId: int = Query(..., ge=1), user=Depends(get_current_user),
):
    _guard(gd_student_id, batchId, lock=True)
    return success(guidance.create_guidance(gd_student_id, body.model_dump()), message="已记录")


@router.post("/gd-guidances/records/{gid}/void")
def guidance_void(
    gid: str, body: GuidanceVoidRequest, batchId: int = Query(..., ge=1),
    user=Depends(get_current_user),
):
    _related_guard(GraduationGuidance, gid, batchId)
    return success(void_guidance_scoped(gid, body.reason), message="已撤销")


@router.get("/gd-guidance-plans")
def plan_list(
    page: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=200),
    gdStudentId: Optional[str] = None, batchId: int = Query(..., ge=1),
    user=Depends(get_current_user),
):
    if gdStudentId:
        _guard(gdStudentId, batchId)
    items, total = guidance.list_plans(
        page, pageSize, gd_student_id=gdStudentId, batch_id=batchId,
    )
    return success(paginate(items, total, page, pageSize))


@router.post("/gd-guidance-plans/{gd_student_id}")
def plan_create(
    gd_student_id: str, body: GuidancePlanCreate,
    batchId: int = Query(..., ge=1), user=Depends(get_current_user),
):
    _guard(gd_student_id, batchId, lock=True)
    return success(guidance.create_plan(gd_student_id, body.model_dump()), message="已创建计划")


@router.post("/gd-guidance-plans/{plan_id}/checkin")
def plan_checkin(
    plan_id: str, body: Optional[GuidancePlanCheckin] = None,
    batchId: int = Query(..., ge=1), user=Depends(get_current_user),
):
    _related_guard(GraduationGuidancePlan, plan_id, batchId)
    return success(guidance.checkin_plan(plan_id, body.model_dump() if body else {}), message="已签到")


@router.post("/gd-guidance-plans/{plan_id}/cancel")
def plan_cancel(
    plan_id: str, body: GuidancePlanCancel,
    batchId: int = Query(..., ge=1), user=Depends(get_current_user),
):
    _related_guard(GraduationGuidancePlan, plan_id, batchId)
    return success(guidance.cancel_plan(plan_id, body.reason), message="已取消")


@router.get("/gd-midterms/stats")
def midterm_stats(batchId: int = Query(..., ge=1), user=Depends(get_current_user)):
    return success(midterm.midterm_stats(batch_id=require_batch_id(batchId)))


@router.get("/gd-midterms")
def midterm_list(
    page: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=200),
    keyword: Optional[str] = None, status: Optional[str] = None,
    batchId: int = Query(..., ge=1), user=Depends(get_current_user),
):
    items, total = midterm.list_midterms(
        page, pageSize, keyword=keyword, status=status, batch_id=batchId,
    )
    return success(paginate(items, total, page, pageSize))


@router.get("/gd-midterms/{gd_student_id}", summary="只读查看中期检查；不存在返回虚拟待检查态")
def midterm_detail(
    gd_student_id: str, batchId: int = Query(..., ge=1), user=Depends(get_current_user),
):
    _guard(gd_student_id, batchId)
    return success(midterm.get_midterm(gd_student_id))


@router.post("/gd-midterms/{gd_student_id}/check")
def midterm_check(
    gd_student_id: str, body: MidtermCheckRequest,
    batchId: int = Query(..., ge=1), user=Depends(get_current_user),
):
    _guard(gd_student_id, batchId, lock=True)
    return success(midterm.conduct_check(
        gd_student_id, body.conclusion, body.comment, body.rectifyDeadline,
    ), message="已提交检查结论")


@router.post("/gd-midterms/{gd_student_id}/rectify")
def midterm_rectify(
    gd_student_id: str, body: MidtermRectifySubmit,
    batchId: int = Query(..., ge=1), user=Depends(get_current_user),
):
    _guard(gd_student_id, batchId, lock=True)
    return success(midterm.submit_rectification(gd_student_id, body.content), message="已提交整改")


@router.post("/gd-midterms/{gd_student_id}/rectify/review")
def midterm_rectify_review(
    gd_student_id: str, body: MidtermRectifyReview,
    batchId: int = Query(..., ge=1), user=Depends(get_current_user),
):
    _guard(gd_student_id, batchId, lock=True)
    return success(midterm.review_rectification(
        gd_student_id, body.action, body.comment,
    ), message="已复核")
