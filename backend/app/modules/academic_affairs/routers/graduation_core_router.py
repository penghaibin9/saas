"""D9-S1a 毕业资格审核公开 Router：从 legacy academic_affairs Move Only。"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Path
from pydantic import BaseModel, Field

from app.core.permissions import require_any_permission, require_permission
from app.core.response import paginate, success
from app.modules.academic_affairs.services import academic_affairs_graduation_scope_guard as _grad_scope_guard
from app.modules.academic_affairs.services import academic_affairs_graduation_service as grad_svc


# The public Graduation router installs a read-side scope projection that consumes the
# shared affairs security context. Permission grants never imply tenant-wide data scope.
_grad_scope_guard.install(grad_svc)

router = APIRouter(prefix="/academic-affairs", tags=["教务中心"])

_GRAD_MANAGE = "academicAffairs.graduation.manage"
_GRAD_VIEW = "academicAffairs.graduation.view"
_GRAD_COLLEGE_REVIEW = "academicAffairs.graduation.collegeReview"
_GRAD_FINAL = "academicAffairs.graduation.final"


class GradAuditBatchCreate(BaseModel):
    batchName: str = Field(..., min_length=1)
    gradeYear: Optional[str] = None
    majorId: Optional[str] = None


class GenerateStudentsBody(BaseModel):
    studentIds: Optional[list[str]] = None


class GradReviewBody(BaseModel):
    action: str = Field(..., description="APPROVE/REJECT")
    note: Optional[str] = Field("", max_length=500)


class GradFinalBody(BaseModel):
    conclusion: str = Field(..., description="GRADUATED/COMPLETED/DELAYED")
    confirm: bool = Field(False, description="二次确认(涉学籍终态)")


class GradFeeClearanceBody(BaseModel):
    rows: list[dict] = Field(..., description="[{studentNo,status:CLEARED|OWED,evidence?}]")


class GradFeeMarkOneBody(BaseModel):
    studentNo: Optional[str] = Field(None, description="学号")
    studentId: Optional[str] = Field(None, description="学生ID（与学号二选一）")
    status: str = Field(..., description="CLEARED 已结清 / OWED 仍欠费")
    evidence: Optional[str] = Field(None, max_length=200, description="依据说明，缺省=人工勾选过渡")


@router.get("/graduation-audit-batches", summary="审核批次列表（附应审/通过/异常/已终审/已归档统计）")
def grad_batches(status: Optional[str] = None, page: int = 1, pageSize: int = 50,
                 user=Depends(require_any_permission(_GRAD_VIEW, _GRAD_MANAGE))):
    items, total = grad_svc.list_batches(user, status, page, pageSize)
    return success(paginate(items, total, page, pageSize))


@router.post("/graduation-audit-batches", summary="新建毕业资格审核批次")
def grad_batch_create(body: GradAuditBatchCreate, user=Depends(require_permission(_GRAD_MANAGE))):
    return success(grad_svc.create_batch(body, user), message="已创建")


@router.post("/graduation-audit-batches/{batchId}/generate", summary="圈定应届生生成预审行（幂等）")
def grad_generate(body: GenerateStudentsBody = GenerateStudentsBody(), batchId: int = Path(...),
                  user=Depends(require_permission(_GRAD_MANAGE))):
    return success(grad_svc.generate(batchId, user, body.studentIds), message="已生成")


@router.post("/graduation-audit-batches/{batchId}/precheck", summary="十项供数三态预审（幂等，覆盖）")
def grad_precheck(batchId: int = Path(...), user=Depends(require_permission(_GRAD_MANAGE))):
    return success(grad_svc.precheck(batchId, user), message="预审完成")


@router.post("/graduation-audit-batches/{batchId}/fee-clearance", summary="财务回填费用结清（CLEARED/OWED）")
def grad_fee_clearance(body: GradFeeClearanceBody, batchId: int = Path(...),
                       user=Depends(require_permission(_GRAD_MANAGE))):
    return success(grad_svc.import_fee_clearance(batchId, user, body.rows), message="费用结清已回填")


@router.post("/graduation-audit-batches/{batchId}/fee-clearance/mark",
             summary="人工勾选费用结清（过渡；CLEARED/OWED，不得默认 PASS）")
def grad_fee_mark_one(body: GradFeeMarkOneBody, batchId: int = Path(...),
                      user=Depends(require_permission(_GRAD_MANAGE))):
    return success(grad_svc.mark_fee_clearance_one(
        batchId, user, student_no=body.studentNo, student_id=body.studentId,
        status=body.status, evidence=body.evidence or ""), message="费用结清已勾选")


@router.post("/graduation-audit-batches/{batchId}/archive", summary="审核归档（收敛已终审毕业/结业结果）")
def grad_archive(batchId: int = Path(...), user=Depends(require_permission(_GRAD_MANAGE))):
    return success(grad_svc.archive_batch(batchId, user), message="已归档")


@router.get("/graduation-audit-batches/{batchId}/results", summary="预审结果列表（支持按单项透视过滤）")
def grad_results(batchId: int = Path(...), status: Optional[str] = None, overall: Optional[str] = None,
                 item: Optional[str] = None, itemResult: Optional[str] = None,
                 page: int = 1, pageSize: int = 50, user=Depends(require_permission(_GRAD_VIEW))):
    items, total = grad_svc.list_results(batchId, user, status, overall, item, itemResult, page, pageSize)
    return success(paginate(items, total, page, pageSize))


@router.get("/graduation-audit-batches/{batchId}/rosters", summary="三名单（毕业/结业/延毕）")
def grad_rosters(batchId: int = Path(...), user=Depends(require_permission(_GRAD_VIEW))):
    return success(grad_svc.rosters(batchId, user))


@router.get("/graduation-results/{resultId}", summary="预审结果详情（十项证据）")
def grad_result_detail(resultId: int = Path(...), user=Depends(require_permission(_GRAD_VIEW))):
    return success(grad_svc.get_result(resultId, user))


@router.post("/graduation-results/{resultId}/college-review", summary="学院初审")
def grad_college_review(body: GradReviewBody, resultId: int = Path(...),
                        user=Depends(require_permission(_GRAD_COLLEGE_REVIEW))):
    return success(grad_svc.college_review(resultId, user, body.action, body.note or ""), message="已处理")


@router.post("/graduation-results/{resultId}/final", summary="毕业资格终审（结论→经单一入口写学籍，强制二次确认）")
def grad_final(body: GradFinalBody, resultId: int = Path(...), user=Depends(require_permission(_GRAD_FINAL))):
    return success(grad_svc.academic_final(resultId, user, body.conclusion, body.confirm), message="已终审")
