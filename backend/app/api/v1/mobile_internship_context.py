"""教师小程序岗位实习权限、批次与批次化查询上下文。"""
from __future__ import annotations

from collections import Counter

from fastapi import APIRouter, Body, Depends, Query
from sqlalchemy import select

from app.core.permissions import (
    get_effective_access_context,
    require_module,
    require_permission,
)
from app.core.response import success
from app.models import InternshipBatch, InternshipRecord
from app.modules.internship.services.internship_scope import apply_internship_record_scope
from app.services.db_service import _iso, _tid, session

router = APIRouter(
    prefix="/mobile/teacher/internship/context",
    tags=["教师移动端-岗位实习上下文"],
    dependencies=[Depends(require_module("internship"))],
)


def _choose_default_batch(items: list[dict]) -> str:
    running = [x for x in items if x.get("status") == "RUNNING"]
    pool = running or [x for x in items if x.get("status") != "VOIDED"] or items
    return str(pool[0]["id"]) if pool else ""


@router.get("", summary="教师岗位实习权限与批次上下文")
def teacher_internship_context(
    user=Depends(require_permission("internship.dashboard.view")),
):
    with session() as db:
        query = select(InternshipRecord).where(
            InternshipRecord.tenant_id == _tid(),
            InternshipRecord.is_deleted.is_(False),
            InternshipRecord.batch_id.is_not(None),
        )
        records = db.scalars(
            apply_internship_record_scope(query, user).order_by(InternshipRecord.id.desc())
        ).all()
        counts = Counter(int(x.batch_id) for x in records if x.batch_id)
        batch_ids = list(counts)
        batches = []
        if batch_ids:
            rows = db.scalars(select(InternshipBatch).where(
                InternshipBatch.tenant_id == _tid(),
                InternshipBatch.id.in_(batch_ids),
                InternshipBatch.is_deleted.is_(False),
            ).order_by(
                InternshipBatch.start_date.desc(), InternshipBatch.id.desc()
            )).all()
            batches = [{
                "id": str(x.id), "name": x.batch_name, "batchNo": x.batch_no,
                "status": x.status, "academicYear": x.academic_year or "",
                "term": x.term or "", "startDate": _iso(x.start_date),
                "endDate": _iso(x.end_date),
                "studentCount": int(counts.get(int(x.id), 0)),
            } for x in rows]

    access = get_effective_access_context(user)
    healthy = bool(access.get("moduleAccessHealthy", True))
    return success({
        "roleCode": access.get("roleCode"),
        "permissionPatterns": (access.get("permissionPatterns") or []) if healthy else [],
        "permissionVersion": access.get("permissionVersion"),
        "moduleAccessHealthy": healthy,
        "moduleAccessError": access.get("moduleAccessError") or "",
        "batches": batches if healthy else [],
        "defaultBatchId": _choose_default_batch(batches) if healthy else "",
    })


@router.get("/scores", summary="教师当前批次实习成绩列表")
def teacher_batch_scores(
    batchId: str = Query(..., min_length=1),
    user=Depends(require_permission("internship.score.view")),
):
    from app.modules.internship.services import internship_score_service as scores
    items, total = scores.list_scores(1, 200, batch_id=batchId, user=user)
    return success({"list": items, "total": total, "batchId": str(batchId)})


@router.get("/enterprise-evals", summary="教师当前批次企业评价列表")
def teacher_batch_enterprise_evals(
    batchId: str = Query(..., min_length=1),
    user=Depends(require_permission("internship.eval.enterprise.view")),
):
    from app.modules.internship.services import internship_enterprise_eval_service as evaluations
    items, total = evaluations.list_evals(
        1, 200, batch_id=batchId, user=user)
    return success({"list": items, "total": total, "batchId": str(batchId)})


@router.post("/enterprise-evals", summary="教师为当前批次学生代录企业纸质评价")
def teacher_batch_enterprise_eval_create(
    body: dict = Body(...),
    user=Depends(require_permission("internship.eval.enterprise.manage")),
):
    from app.modules.internship.services import internship_enterprise_eval_service as evaluations
    return success(evaluations.create(user, body), message="企业评价已录入，等待独立审核")


@router.post("/enterprise-evals/{eval_id}/review", summary="学校或学院授权角色独立审核企业评价")
def teacher_batch_enterprise_eval_review(
    eval_id: str,
    body: dict = Body(...),
    user=Depends(require_permission("internship.eval.enterprise.review")),
):
    from app.modules.internship.services import internship_enterprise_eval_service as evaluations
    payload = body or {}
    return success(evaluations.review(
        user, eval_id, str(payload.get("action") or "").upper(),
        payload.get("comment") or "", expected_version=payload.get("expectedVersion")),
        message="企业评价审核完成")
