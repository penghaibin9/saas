"""教师小程序岗位实习权限、批次与版本化业务上下文。"""
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
    running = [item for item in items if item.get("status") == "RUNNING"]
    pool = running or [item for item in items if item.get("status") != "VOIDED"] or items
    return str(pool[0]["id"]) if pool else ""


def _paged(items: list[dict], total: int, page: int, page_size: int, batch_id) -> dict:
    return {
        "items": items,
        "total": int(total or 0),
        "page": int(page),
        "pageSize": int(page_size),
        "hasMore": int(page) * int(page_size) < int(total or 0),
        "batchId": str(batch_id),
    }


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
        counts = Counter(int(row.batch_id) for row in records if row.batch_id)
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
                "id": str(row.id), "name": row.batch_name, "batchNo": row.batch_no,
                "status": row.status, "academicYear": row.academic_year or "",
                "term": row.term or "", "startDate": _iso(row.start_date),
                "endDate": _iso(row.end_date),
                "studentCount": int(counts.get(int(row.id), 0)),
            } for row in rows]

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
    page: int = Query(1, ge=1),
    pageSize: int = Query(20, ge=1, le=100),
    user=Depends(require_permission("internship.score.view")),
):
    from app.modules.internship.services import internship_score_service as scores
    items, total = scores.list_scores(page, pageSize, batch_id=batchId, user=user)
    return success(_paged(items, total, page, pageSize, batchId))


@router.get("/agreements", summary="教师当前批次待学校终审协议进度")
def teacher_batch_agreements(
    batchId: str = Query(..., min_length=1),
    page: int = Query(1, ge=1),
    pageSize: int = Query(20, ge=1, le=100),
    user=Depends(require_permission("internship.agreement.view")),
):
    from app.modules.internship.services import internship_agreement_service as agreements
    items, total = agreements.list_agreements(
        page, pageSize, status="PENDING_SCHOOL", batch_id=batchId, user=user)
    return success(_paged(items, total, page, pageSize, batchId))


@router.get("/enterprise-evals", summary="教师当前批次企业评价列表")
def teacher_batch_enterprise_evals(
    batchId: str = Query(..., min_length=1),
    page: int = Query(1, ge=1),
    pageSize: int = Query(20, ge=1, le=100),
    user=Depends(require_permission("internship.eval.enterprise.view")),
):
    from app.modules.internship.services import internship_enterprise_eval_service as evaluations
    items, total = evaluations.list_evals(page, pageSize, batch_id=batchId, user=user)
    return success(_paged(items, total, page, pageSize, batchId))


@router.post("/enterprise-evals", summary="教师为当前批次学生代录企业纸质评价")
def teacher_batch_enterprise_eval_create(
    batchId: int = Query(..., ge=1),
    body: dict = Body(...),
    user=Depends(require_permission("internship.eval.enterprise.manage")),
):
    from app.modules.internship.services import internship_enterprise_eval_service as evaluations
    return success(evaluations.create(
        user, body, expected_batch_id=batchId), message="企业评价已录入，等待独立审核")


@router.post("/enterprise-evals/{eval_id}/resubmit", summary="退回企业评价修改后重交")
def teacher_batch_enterprise_eval_resubmit(
    eval_id: str,
    batchId: int = Query(..., ge=1),
    body: dict = Body(...),
    user=Depends(require_permission("internship.eval.enterprise.manage")),
):
    from app.modules.internship.services import internship_enterprise_eval_service as evaluations
    return success(evaluations.resubmit(
        user, eval_id, body, expected_batch_id=batchId), message="企业评价已修改重交")


@router.post("/enterprise-evals/{eval_id}/review", summary="学校或学院授权角色独立审核企业评价")
def teacher_batch_enterprise_eval_review(
    eval_id: str,
    batchId: int = Query(..., ge=1),
    body: dict = Body(...),
    user=Depends(require_permission("internship.eval.enterprise.review")),
):
    from app.modules.internship.services import internship_enterprise_eval_service as evaluations
    payload = body or {}
    return success(evaluations.review(
        user, eval_id, str(payload.get("action") or "").upper(),
        payload.get("comment") or "", expected_version=payload.get("expectedVersion"),
        expected_batch_id=batchId),
        message="企业评价审核完成")


@router.get("/student-evals", summary="教师当前批次学生鉴定列表")
def teacher_batch_student_evals(
    batchId: str = Query(..., min_length=1),
    page: int = Query(1, ge=1),
    pageSize: int = Query(20, ge=1, le=100),
    user=Depends(require_permission("internship.eval.self.view")),
):
    from app.modules.internship.services import internship_student_eval_service as evaluations
    items, total = evaluations.list_evals(page, pageSize, batch_id=batchId, user=user)
    return success(_paged(items, total, page, pageSize, batchId))


@router.get("/student-evals/{eval_id}", summary="教师查看学生鉴定详情")
def teacher_batch_student_eval_detail(
    eval_id: str,
    user=Depends(require_permission("internship.eval.self.view")),
):
    from app.modules.internship.services import internship_student_eval_service as evaluations
    return success(evaluations.get_eval(eval_id, user=user))


@router.post("/student-evals/{eval_id}/advisor-comment", summary="指导教师按版本填写鉴定意见")
def teacher_batch_student_eval_advisor_comment(
    eval_id: str,
    batchId: int = Query(..., ge=1),
    body: dict = Body(...),
    user=Depends(require_permission("internship.eval.advisor.manage")),
):
    from app.modules.internship.services import internship_student_eval_service as evaluations
    return success(evaluations.advisor_comment(
        user, eval_id, body or {}, expected_batch_id=batchId), message="指导意见已保存")


@router.post("/student-evals/{eval_id}/review", summary="学校或学院授权角色独立审核学生鉴定")
def teacher_batch_student_eval_review(
    eval_id: str,
    batchId: int = Query(..., ge=1),
    body: dict = Body(...),
    user=Depends(require_permission("internship.eval.self.review")),
):
    from app.modules.internship.services import internship_student_eval_service as evaluations
    payload = body or {}
    return success(evaluations.review(
        user, eval_id, str(payload.get("action") or "").upper(),
        payload.get("comment") or "", expected_version=payload.get("expectedVersion"),
        expected_batch_id=batchId),
        message="学生鉴定审核完成")


@router.get("/makeups", summary="教师当前批次补卡待审核队列")
def teacher_batch_makeups(
    batchId: str = Query(..., min_length=1),
    page: int = Query(1, ge=1),
    pageSize: int = Query(20, ge=1, le=100),
    user=Depends(require_permission("internship.makeup.view")),
):
    from app.modules.internship.services import internship_makeup_service as makeups
    items, total = makeups.list_makeups(
        page, pageSize, status="PENDING", batch_id=batchId, user=user)
    return success(_paged(items, total, page, pageSize, batchId))


@router.post("/makeups/{makeup_id}/review", summary="教师按版本审批补卡")
def teacher_batch_makeup_review(
    makeup_id: str,
    batchId: int = Query(..., ge=1),
    body: dict = Body(...),
    user=Depends(require_permission("internship.makeup.review")),
):
    from app.modules.internship.services import internship_makeup_service as makeups
    payload = body or {}
    return success(makeups.review(
        user, makeup_id, str(payload.get("action") or "").upper(),
        payload.get("comment") or "", expected_version=payload.get("expectedVersion"),
        expected_batch_id=batchId),
        message="补卡审批完成")


@router.get("/leaves", summary="教师当前批次请假待审批队列")
def teacher_batch_leaves(
    batchId: str = Query(..., min_length=1),
    page: int = Query(1, ge=1),
    pageSize: int = Query(20, ge=1, le=100),
    user=Depends(require_permission("internship.leave.view")),
):
    from app.modules.internship.services import internship_leave_service as leaves
    items, total = leaves.list_leaves(
        page, pageSize, status="PENDING", batch_id=batchId, user=user)
    return success(_paged(items, total, page, pageSize, batchId))


@router.post("/leaves/{leave_id}/review", summary="教师按版本审批请假")
def teacher_batch_leave_review(
    leave_id: str,
    batchId: int = Query(..., ge=1),
    body: dict = Body(...),
    user=Depends(require_permission("internship.leave.review")),
):
    from app.modules.internship.services import internship_leave_service as leaves
    payload = body or {}
    return success(leaves.review(
        user, leave_id, str(payload.get("action") or "").upper(),
        payload.get("comment") or "", expected_version=payload.get("expectedVersion"),
        expected_batch_id=batchId),
        message="请假审批完成")


@router.get("/process-reports", summary="教师当前批次过程报告待批阅队列")
def teacher_batch_process_reports(
    batchId: str = Query(..., min_length=1),
    page: int = Query(1, ge=1),
    pageSize: int = Query(20, ge=1, le=100),
    user=Depends(require_permission("internship.report.view")),
):
    from app.modules.internship.services import internship_process_report_service as reports
    items, total = reports.list_reports(
        page, pageSize, status="PENDING_REVIEW", batch_id=batchId, user=user)
    return success(_paged(items, total, page, pageSize, batchId))


@router.get("/process-reports/{report_id}", summary="教师查看过程报告详情")
def teacher_batch_process_report_detail(
    report_id: str,
    user=Depends(require_permission("internship.report.view")),
):
    from app.modules.internship.services import internship_process_report_service as reports
    return success(reports.get_report(report_id, user=user))


@router.post("/process-reports/{report_id}/review", summary="教师按版本批阅过程报告")
def teacher_batch_process_report_review(
    report_id: str,
    batchId: int = Query(..., ge=1),
    body: dict = Body(...),
    user=Depends(require_permission("internship.report.review")),
):
    from app.modules.internship.services import internship_process_report_service as reports
    payload = body or {}
    return success(reports.review_report(
        report_id, str(payload.get("action") or "").upper(),
        payload.get("comment") or "", user=user,
        expected_version=payload.get("expectedVersion"),
        expected_batch_id=batchId),
        message="过程报告批阅完成")


@router.get("/plan-tasks", summary="教师当前批次计划任务待确认队列")
def teacher_batch_plan_tasks(
    batchId: str = Query(..., min_length=1),
    page: int = Query(1, ge=1),
    pageSize: int = Query(20, ge=1, le=100),
    user=Depends(require_permission("internship.task.view")),
):
    from app.modules.internship.services import internship_plan_task_service as tasks
    items, total = tasks.list_progress(
        page, pageSize, batch_id=batchId, status="SUBMITTED", user=user)
    return success(_paged(items, total, page, pageSize, batchId))


@router.post("/plan-tasks/{progress_id}/review", summary="教师按版本确认计划任务")
def teacher_batch_plan_task_review(
    progress_id: str,
    batchId: int = Query(..., ge=1),
    body: dict = Body(...),
    user=Depends(require_permission("internship.task.review")),
):
    from app.modules.internship.services import internship_plan_task_service as tasks
    payload = body or {}
    return success(tasks.review_progress(
        progress_id, str(payload.get("action") or "").upper(),
        payload.get("comment") or "", user=user,
        expected_version=payload.get("expectedVersion"),
        expected_batch_id=batchId),
        message="计划任务处理完成")


@router.get("/applications", summary="教师当前批次正式实习申请待审核队列")
def teacher_batch_applications(
    batchId: str = Query(..., min_length=1),
    page: int = Query(1, ge=1),
    pageSize: int = Query(20, ge=1, le=100),
    user=Depends(require_permission("internship.application.view")),
):
    from app.modules.internship.services import internship_application_service as applications
    items, total = applications.list_applications(
        page, pageSize, status="PENDING_REVIEW", batch_id=batchId, user=user)
    return success(_paged(items, total, page, pageSize, batchId))


@router.post("/applications/{application_id}/review", summary="教师按申请与学生记录版本审核正式实习申请")
def teacher_batch_application_review(
    application_id: str,
    batchId: int = Query(..., ge=1),
    body: dict = Body(...),
    user=Depends(require_permission("internship.application.review")),
):
    from app.modules.internship.services import internship_application_service as applications
    payload = body or {}
    return success(applications.review_application(
        application_id, str(payload.get("action") or "").upper(),
        payload.get("comment") or "", user=user,
        expected_version=payload.get("expectedVersion"),
        record_expected_version=payload.get("recordExpectedVersion"),
        expected_batch_id=batchId),
        message="正式实习申请审核完成")
