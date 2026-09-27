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
from app.modules.internship.schemas.internship_recruitment_campaign import VolunteerLockRelease, VolunteerSchoolConfirm
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


@router.get("/volunteer-campaigns", summary="教师指导批次的正式志愿招聘季")
def teacher_volunteer_campaigns(
    batchId: int = Query(..., ge=1),
    user=Depends(require_permission("internship.application.view")),
):
    from app.modules.internship.services import internship_school_volunteer_service as volunteers
    return success(volunteers.review_context(batch_id=batchId, user=user))


@router.post("/volunteer-groups/{group_id}/confirm", summary="教师按版本确认正式志愿岗位")
def teacher_volunteer_confirm(
    group_id: int, body: VolunteerSchoolConfirm,
    campaignId: int = Query(..., ge=1), batchId: int = Query(..., ge=1),
    user=Depends(require_permission("internship.application.review")),
):
    from app.modules.internship.services import internship_school_volunteer_service as volunteers
    return success(volunteers.confirm_group(
        campaign_id=campaignId, group_id=group_id, expected_batch_id=batchId, user=user,
        application_id=body.applicationId, expected_group_version=body.expectedGroupVersion,
        expected_record_version=body.expectedRecordVersion,
        expected_application_version=body.expectedApplicationVersion,
    ), message="岗位已确认，协议、保险与上岗条件需继续核验")


@router.post("/volunteer-groups/{group_id}/return", summary="教师按版本退回正式志愿补正")
def teacher_volunteer_return(
    group_id: int, body: VolunteerLockRelease,
    campaignId: int = Query(..., ge=1), batchId: int = Query(..., ge=1),
    user=Depends(require_permission("internship.application.review")),
):
    from app.modules.internship.services import internship_school_volunteer_service as volunteers
    return success(volunteers.return_group(
        campaign_id=campaignId, group_id=group_id, expected_batch_id=batchId, user=user,
        reason=body.reason, expected_group_version=body.expectedGroupVersion,
        expected_record_version=body.expectedRecordVersion,
    ), message="志愿已退回，等待学生补正后重提")


@router.get("/volunteer-groups", summary="教师当前招聘季正式志愿队列")
def teacher_volunteer_groups(
    campaignId: int = Query(..., ge=1), batchId: int = Query(..., ge=1),
    page: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=100),
    status: str = Query("PENDING"), keyword: str = Query("", max_length=100),
    user=Depends(require_permission("internship.application.view")),
):
    from app.modules.internship.services import internship_school_volunteer_service as volunteers
    result = volunteers.list_groups(campaign_id=campaignId, expected_batch_id=batchId, user=user,
        status=status, keyword=keyword, page=page, page_size=pageSize)
    return success(_paged(result["items"], result["total"], page, pageSize, batchId))


@router.get("/volunteer-groups/{group_id}", summary="教师正式志愿、冻结材料及企业处理详情")
def teacher_volunteer_group_detail(
    group_id: int, campaignId: int = Query(..., ge=1), batchId: int = Query(..., ge=1),
    user=Depends(require_permission("internship.application.view")),
):
    from app.modules.internship.services import internship_school_volunteer_service as volunteers
    return success(volunteers.get_group(campaign_id=campaignId, group_id=group_id,
        expected_batch_id=batchId, user=user))


@router.get("/positions", summary="教师指导批次岗位核对（只读）")
def teacher_batch_positions(
    batchId: str = Query(..., min_length=1),
    page: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=50),
    keyword: str = Query('', max_length=100), status: str = Query(''),
    user=Depends(require_permission("internship.position.view")),
):
    from app.modules.internship.services import internship_teacher_position_service as positions
    items, total = positions.list_positions(user, batch_id=batchId, page=page, page_size=pageSize, keyword=keyword, status=status)
    return success(_paged(items, total, page, pageSize, batchId))


@router.get("/positions/{position_id}", summary="教师指导批次岗位详情（只读）")
def teacher_batch_position_detail(
    position_id: int, batchId: str = Query(..., min_length=1),
    user=Depends(require_permission("internship.position.view")),
):
    from app.modules.internship.services import internship_teacher_position_service as positions
    return success(positions.get_position(user, batch_id=batchId, position_id=position_id))


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
    status: str = Query("PENDING_REVIEW", min_length=1),
    user=Depends(require_permission("internship.application.view")),
):
    from app.modules.internship.services import internship_application_service as applications
    items, total = applications.list_applications(
        page, pageSize, status=status, batch_id=batchId, user=user)
    return success(_paged(items, total, page, pageSize, batchId))


@router.get("/students/{record_id}/account", summary="教师查看本人数据范围学生账号重置状态")
def teacher_student_account_state(
    record_id: str,
    batchId: str = Query(..., min_length=1),
    user=Depends(require_permission("internship.student.password.reset")),
):
    from app.modules.internship.services import internship_student_account_service as accounts
    return success(accounts.account_state(record_id, user, batch_id=batchId))


@router.post("/students/{record_id}/reset-password", summary="教师受控重置本人数据范围学生密码")
def teacher_student_reset_password(
    record_id: str,
    body: dict = Body(...),
    user=Depends(require_permission("internship.student.password.reset")),
):
    from app.modules.internship.services import internship_student_account_service as accounts
    return success(accounts.reset_password(record_id, body or {}, user), message="学生密码已重置")


@router.get("/material-requirements", summary="教师当前批次材料收件要求")
def teacher_material_requirements(
    batchId: str = Query(..., min_length=1),
    user=Depends(require_permission("internship.report.review")),
):
    from app.modules.internship.services import internship_material_requirement_service as materials
    return success(materials.list_requirements(
        batch_id=batchId, status="PUBLISHED", user=user))


@router.get("/material-requirements/{requirement_id}/coverage", summary="教师材料已交/缺交统计")
def teacher_material_requirement_coverage(
    requirement_id: int,
    user=Depends(require_permission("internship.report.review")),
):
    from app.modules.internship.services import internship_material_requirement_service as materials
    return success(materials.coverage(requirement_id, user=user))


@router.get("/material-requirements/{requirement_id}/students", summary="教师材料已交/缺交学生名单")
def teacher_material_requirement_students(
    requirement_id: int,
    state: str = Query("ALL"),
    page: int = Query(1, ge=1),
    pageSize: int = Query(20, ge=1, le=100),
    keyword: str = Query(""),
    user=Depends(require_permission("internship.report.review")),
):
    from app.modules.internship.services import internship_material_requirement_service as materials
    items, total = materials.list_students(
        requirement_id, state=state, page=page, page_size=pageSize,
        keyword=keyword, user=user)
    return success(_paged(items, total, page, pageSize, None))


@router.post("/material-submissions/{submission_id}/review", summary="教师审核学生材料")
def teacher_material_submission_review(
    submission_id: int,
    body: dict = Body(...),
    user=Depends(require_permission("internship.report.review")),
):
    from app.modules.internship.services import internship_material_requirement_service as materials
    return success(materials.review_submission(
        submission_id, body or {}, user=user), message="材料审核完成")


@router.get("/checkin-exemptions", summary="教师当前批次免签申请")
def teacher_checkin_exemptions(
    batchId: str = Query(..., min_length=1),
    page: int = Query(1, ge=1),
    pageSize: int = Query(20, ge=1, le=100),
    status: str = Query("PENDING"),
    user=Depends(require_permission("internship.attendance.review")),
):
    from app.modules.internship.services import internship_checkin_exemption_service as exemptions
    items, total = exemptions.list_for_teacher(
        page, pageSize, batch_id=batchId, status=status, user=user)
    return success(_paged(items, total, page, pageSize, batchId))


@router.post("/checkin-exemptions/{exemption_id}/review", summary="教师审批免签申请")
def teacher_checkin_exemption_review(
    exemption_id: str,
    body: dict = Body(...),
    user=Depends(require_permission("internship.attendance.review")),
):
    from app.modules.internship.services import internship_checkin_exemption_service as exemptions
    return success(exemptions.review(exemption_id, body or {}, user), message="免签申请已处理")


@router.get("/applications/summary", summary="教师当前批次实习岗位填报与审核全量统计")
def teacher_batch_application_summary(
    batchId: str = Query(..., min_length=1),
    user=Depends(require_permission("internship.application.view")),
):
    from app.modules.internship.services import internship_application_service as applications
    return success(applications.application_summary(batch_id=batchId, user=user))


@router.get("/applications/students", summary="教师当前批次已填报/未填报学生名单")
def teacher_batch_application_students(
    batchId: str = Query(..., min_length=1),
    state: str = Query(..., min_length=1),
    page: int = Query(1, ge=1),
    pageSize: int = Query(20, ge=1, le=100),
    keyword: str | None = Query(None),
    user=Depends(require_permission("internship.application.view")),
):
    from app.modules.internship.services import internship_application_service as applications
    items, total = applications.list_application_students(
        page, pageSize, state, batch_id=batchId, keyword=keyword, user=user)
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


@router.get("/changes", summary="教师当前批次实习变更待审核队列")
def teacher_batch_changes(
    batchId: str = Query(..., min_length=1),
    page: int = Query(1, ge=1),
    pageSize: int = Query(20, ge=1, le=100),
    user=Depends(require_permission("internship.change.view")),
):
    from app.modules.internship.services import internship_change_service as changes
    items, total = changes.list_changes(
        page, pageSize, status="PENDING", batch_id=batchId, user=user)
    return success(_paged(items, total, page, pageSize, batchId))


@router.post("/changes/{change_id}/review", summary="教师按申请与学生记录版本审核实习变更")
def teacher_batch_change_review(
    change_id: str,
    batchId: int = Query(..., ge=1),
    body: dict = Body(...),
    user=Depends(require_permission("internship.change.review")),
):
    from app.modules.internship.services import internship_change_service as changes
    payload = body or {}
    return success(changes.review_change(
        change_id, str(payload.get("action") or "").upper(),
        payload.get("comment") or "", user=user,
        expected_version=payload.get("expectedVersion"),
        record_expected_version=payload.get("recordExpectedVersion"),
        expected_batch_id=batchId), message="实习变更审核完成")
