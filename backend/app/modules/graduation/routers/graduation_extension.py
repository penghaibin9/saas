"""优秀成果认定与延期答辩学校端接口。"""
from __future__ import annotations

from fastapi import APIRouter, Body, Depends, Query

from app.core.permissions import require_permission
from app.core.response import paginate, success
from app.modules.graduation.services import graduation_extension_action_service as action_svc
from app.modules.graduation.services import graduation_extension_query_service as query_svc
from app.modules.graduation.services import graduation_extension_safety_service as safety_svc

router = APIRouter(prefix="/graduation", tags=["毕业设计-优秀成果与延期答辩"])


@router.get("/gd-excellent-outcomes/candidates", summary="优秀成果可提名候选")
def gd_excellent_outcome_candidates(
    batchId: int = Query(..., ge=1), page: int = Query(1, ge=1),
    pageSize: int = Query(20, ge=1, le=200),
    user=Depends(require_permission("graduationDesign.grade.view")),
):
    items, total = query_svc.list_candidates(batch_id=batchId, page=page, page_size=pageSize)
    return success(paginate(items, total, page, pageSize))


@router.get("/gd-excellent-outcomes", summary="优秀成果认定台账")
def gd_excellent_outcomes(
    batchId: int = Query(..., ge=1), status: str | None = None,
    page: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=200),
    user=Depends(require_permission("graduationDesign.grade.view")),
):
    items, total = safety_svc.list_excellent_outcomes(
        batch_id=batchId, status=status, page=page, page_size=pageSize,
    )
    return success(paginate(items, total, page, pageSize))


@router.post("/gd-excellent-outcomes/{gd_student_id}/nominate", summary="导师提名优秀成果")
def gd_excellent_outcome_nominate(
    gd_student_id: str, body: dict = Body(...),
    user=Depends(require_permission("graduationDesign.grade.view")),
):
    return success(action_svc.nominate_excellent(
        gd_student_id, body.get("reason"), body.get("evidence"),
    ), message="优秀成果已提名，等待专业复核")


@router.post("/gd-excellent-outcomes/{record_id}/major-review", summary="专业负责人复核优秀成果")
def gd_excellent_outcome_major_review(
    record_id: str, body: dict = Body(...),
    user=Depends(require_permission("graduationDesign.grade.review")),
):
    return success(action_svc.major_review_excellent(
        record_id, body.get("action"), body.get("comment"),
    ), message="专业复核完成")


@router.post("/gd-excellent-outcomes/{record_id}/college-review", summary="学院管理员终审并发布优秀成果")
def gd_excellent_outcome_college_review(
    record_id: str, body: dict = Body(...),
    user=Depends(require_permission("graduationDesign.grade.publish")),
):
    return success(action_svc.college_review_excellent(
        record_id, body.get("action"), body.get("comment"),
    ), message="学院终审完成")


@router.get("/gd-defense-delays", summary="延期答辩审批与排期台账")
def gd_defense_delays(
    batchId: int = Query(..., ge=1), status: str | None = None,
    page: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=200),
    user=Depends(require_permission("graduationDesign.defense.view")),
):
    items, total = safety_svc.list_delays(
        batch_id=batchId, status=status, page=page, page_size=pageSize,
    )
    return success(paginate(items, total, page, pageSize))


@router.post("/gd-defense-delays/{record_id}/advisor-review", summary="指导教师审核延期答辩")
def gd_defense_delay_advisor_review(
    record_id: str, body: dict = Body(...),
    user=Depends(require_permission("graduationDesign.defense.view")),
):
    return success(action_svc.advisor_review_delay(
        record_id, body.get("action"), body.get("comment"),
    ), message="导师审核完成")


@router.post("/gd-defense-delays/{record_id}/major-review", summary="专业负责人复核延期答辩")
def gd_defense_delay_major_review(
    record_id: str, body: dict = Body(...),
    user=Depends(require_permission("graduationDesign.defense.groupManage")),
):
    return success(action_svc.major_review_delay(
        record_id, body.get("action"), body.get("comment"),
    ), message="专业复核完成")


@router.post("/gd-defense-delays/{record_id}/college-review", summary="学院管理员审批延期答辩")
def gd_defense_delay_college_review(
    record_id: str, body: dict = Body(...),
    user=Depends(require_permission("graduationDesign.defense.groupManage")),
):
    return success(action_svc.college_review_delay(
        record_id, body.get("action"), body.get("comment"),
    ), message="学院审批完成")


@router.post("/gd-defense-delays/{record_id}/schedule", summary="学院管理员安排延期答辩")
def gd_defense_delay_schedule(
    record_id: str, body: dict = Body(...),
    user=Depends(require_permission("graduationDesign.defense.groupManage")),
):
    return success(action_svc.schedule_delay(
        record_id, body.get("defenseGroupId"), body.get("plannedDefenseDate"),
    ), message="延期答辩已重新排期，原答辩组与新答辩组均需重新发布")
