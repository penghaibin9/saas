"""D9-S3 教学评价公开 Router：从 legacy academic_affairs Move Only。

学生本人任务 `/evaluation/my-student-tasks` 保持由 student_evaluation_router 正式持有。
"""
from __future__ import annotations

import io
from typing import List, Optional

from fastapi import APIRouter, Depends, Path
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.core.permissions import require_permission
from app.core.response import paginate, success
from app.core.security import get_current_user
from app.modules.academic_affairs.services import academic_affairs_evaluation_service as evaluation_svc


router = APIRouter(prefix="/academic-affairs", tags=["教务中心"])

_EVAL_MANAGE = "academicAffairs.evaluation.batch.manage"
_EVAL_VIEW = "academicAffairs.evaluation.view"
_EVAL_APPEAL = "academicAffairs.evaluation.appeal.review"
_EVAL_ROLE_MANAGE = "academicAffairs.evaluation.batch.manage"
_EVAL_EXPORT = "academicAffairs.evaluation.export"


class EvalBatchBody(BaseModel):
    batchName: str = Field(..., min_length=1)
    termId: Optional[str] = None
    scope: Optional[dict] = None
    template: Optional[dict] = None
    anonymous: Optional[bool] = True


class EvalGenTasksBody(BaseModel):
    teachingTaskIds: list[str] = Field(default_factory=list)
    evaluatorType: str = Field("STUDENT", description="STUDENT/SELF/PEER/SUPERVISOR")


class EvalSubmitBody(BaseModel):
    taskId: str = Field(..., min_length=1)
    answers: Optional[dict] = None
    objectiveScore: Optional[float] = Field(None, ge=0, le=100)
    comment: Optional[str] = Field(None, max_length=1000)


class EvalAppealBody(BaseModel):
    resultId: str = Field(..., min_length=1)
    reason: str = Field(..., min_length=5, max_length=1000)


class EvalAppealReviewBody(BaseModel):
    action: str = Field(..., description="RESOLVE/REJECT")
    reason: Optional[str] = Field("", max_length=1000)


class EvalRoleAssignment(BaseModel):
    teachingTaskId: str = Field(..., min_length=1)
    evaluatorKey: Optional[str] = Field(None, max_length=100, description="PEER/SUPERVISOR必填；SELF缺省=授课教师本人")


class EvalRoleGenBody(BaseModel):
    evaluatorType: str = Field(..., description="SELF/PEER/SUPERVISOR")
    assignments: List[EvalRoleAssignment] = Field(default_factory=list)


class EvalExportBody(BaseModel):
    domain: str = Field(..., description="results/stats")
    purpose: str = Field(..., min_length=5, max_length=200)


@router.post("/evaluation/batches", summary="建评教批次")
def eval_batch_create(body: EvalBatchBody, user=Depends(require_permission(_EVAL_MANAGE))):
    return success(evaluation_svc.create_batch(user, body), message="已创建")


@router.get("/evaluation/batches", summary="评教批次列表")
def eval_batches(status: Optional[str] = None, page: int = 1, pageSize: int = 20,
                 user=Depends(require_permission(_EVAL_VIEW))):
    items, total = evaluation_svc.list_batches(user, status, page, pageSize)
    return success(paginate(items, total, page, pageSize))


@router.get("/evaluation/batches/{bid}", summary="批次详情")
def eval_batch_detail(bid: int = Path(...), user=Depends(require_permission(_EVAL_VIEW))):
    return success(evaluation_svc.get_batch(user, bid))


@router.post("/evaluation/batches/{bid}/tasks", summary="生成应评任务（挂教学任务）")
def eval_gen_tasks(body: EvalGenTasksBody, bid: int = Path(...), user=Depends(require_permission(_EVAL_MANAGE))):
    return success(evaluation_svc.generate_tasks(user, bid, body.teachingTaskIds, body.evaluatorType), message="已生成")


@router.get("/evaluation/batches/{bid}/tasks", summary="应评任务列表")
def eval_tasks(bid: int = Path(...), evaluatorType: Optional[str] = None,
               user=Depends(require_permission(_EVAL_VIEW))):
    return success({"items": evaluation_svc.list_tasks(user, bid, evaluatorType)})


@router.post("/evaluation/batches/{bid}/publish", summary="发布批次")
def eval_publish(bid: int = Path(...), user=Depends(require_permission(_EVAL_MANAGE))):
    return success(evaluation_svc.publish_batch(user, bid), message="已发布")


@router.post("/evaluation/batches/{bid}/open", summary="开放评教窗口")
def eval_open(bid: int = Path(...), user=Depends(require_permission(_EVAL_MANAGE))):
    return success(evaluation_svc.open_batch(user, bid), message="已开放")


@router.post("/evaluation/batches/{bid}/close-score", summary="关闭核算（学生均分分级）")
def eval_close_score(bid: int = Path(...), user=Depends(require_permission(_EVAL_MANAGE))):
    return success(evaluation_svc.close_and_score(user, bid), message="已核算")


@router.post("/evaluation/batches/{bid}/publish-results", summary="发布结果（教师可见本人）")
def eval_publish_results(bid: int = Path(...), user=Depends(require_permission(_EVAL_MANAGE))):
    return success(evaluation_svc.publish_results(user, bid), message="已发布结果")


@router.post("/evaluation/batches/{bid}/archive", summary="归档批次")
def eval_archive(bid: int = Path(...), user=Depends(require_permission(_EVAL_MANAGE))):
    return success(evaluation_svc.archive_batch(user, bid), message="已归档")


@router.post("/evaluation/batches/{bid}/role-tasks", summary="生成教师自评/同行评价/督导评价应评任务")
def eval_role_tasks(body: EvalRoleGenBody, bid: int = Path(...), user=Depends(require_permission(_EVAL_ROLE_MANAGE))):
    assignments = [a.model_dump() for a in body.assignments]
    return success(evaluation_svc.generate_role_tasks(user, bid, body.evaluatorType, assignments), message="已生成")


@router.get("/evaluation/my-role-tasks", summary="我的评价任务（自评/同行/督导，按登录身份匹配 evaluatorKey）")
def eval_my_role_tasks(evaluatorType: str, batchId: Optional[str] = None,
                       user=Depends(require_permission("academicAffairs.evaluation.view"))):
    return success({"items": evaluation_svc.list_my_role_tasks(user, evaluatorType, batchId)})


@router.post("/evaluation/submit", summary="提交评价（学生匿名不存身份；自评/同行/督导校验本人）")
def eval_submit(body: EvalSubmitBody, user=Depends(get_current_user)):
    return success(
        evaluation_svc.submit_evaluation(user, int(body.taskId), body.answers, body.objectiveScore, body.comment),
        message="已提交",
    )


@router.get("/evaluation/batches/{bid}/results", summary="评价结果（教务处全量）")
def eval_results(bid: int = Path(...), page: int = 1, pageSize: int = 50,
                 user=Depends(require_permission(_EVAL_VIEW))):
    items, total = evaluation_svc.list_results(user, bid, mine=False, page=page, page_size=pageSize)
    return success(paginate(items, total, page, pageSize))


@router.get("/evaluation/batches/{bid}/my-results", summary="我的评价结果（教师本人，已发布）")
def eval_my_results(bid: int = Path(...), user=Depends(require_permission("academicAffairs.evaluation.view"))):
    items, total = evaluation_svc.list_results(user, bid, mine=True)
    return success({"items": items})


@router.post("/evaluation/appeals", summary="教师对结果申诉")
def eval_appeal_submit(body: EvalAppealBody, user=Depends(require_permission("academicAffairs.evaluation.view"))):
    return success(evaluation_svc.submit_appeal(user, int(body.resultId), body.reason), message="申诉已提交")


@router.get("/evaluation/appeals", summary="申诉列表")
def eval_appeals(status: Optional[str] = None, page: int = 1, pageSize: int = 50,
                 user=Depends(require_permission(_EVAL_APPEAL))):
    rows = evaluation_svc.list_appeals(user, status)
    total = len(rows)
    start = (max(1, page) - 1) * max(1, pageSize)
    items = rows[start:start + max(1, pageSize)]
    return success(paginate(items, total, page, pageSize))


@router.post("/evaluation/appeals/{aid}/review", summary="申诉审核")
def eval_appeal_review(body: EvalAppealReviewBody, aid: int = Path(...), user=Depends(require_permission(_EVAL_APPEAL))):
    return success(evaluation_svc.review_appeal(user, aid, body.action, body.reason), message="已处理")


@router.get("/evaluation/batches/{bid}/stats", summary="评价统计（结果分级+按评价类型参评率）")
def eval_stats(bid: int = Path(...), user=Depends(require_permission(_EVAL_VIEW))):
    return success(evaluation_svc.stats(user, bid))


@router.post("/evaluation/batches/{bid}/export", summary="导出评价结果/参评统计 xlsx（评价统计/评价归档共用）")
def eval_export(body: EvalExportBody, bid: int = Path(...), user=Depends(require_permission(_EVAL_EXPORT))):
    content = evaluation_svc.export_evaluation_xlsx(user, bid, body.domain, body.purpose)
    return StreamingResponse(
        io.BytesIO(content),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename=evaluation_{body.domain}_{bid}.xlsx"},
    )