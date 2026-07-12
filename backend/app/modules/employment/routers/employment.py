"""就业服务域 API（/api/v1/employment/*）。真实走库；写操作落域审计。"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query

from app.core.response import paginate, success
from app.core.security import get_current_user
from app.modules.employment.schemas.employment import (AssignTeacherBody, CommentBody, CompanyCreate, FollowUpCreate,
                                     IdsBody, JobCreate, MarkDestBody, ReasonBody, StudentCreate,
                                     StudentUpdate)
from app.modules.employment.services import employment_service as svc

router = APIRouter(prefix="/employment", tags=["就业服务"])


def _p(i, t, page, ps):
    return success(paginate(i, t, page, ps))


@router.get("/dashboard", summary="就业看板")
def dashboard(user=Depends(get_current_user)):
    return success(svc.get_dashboard())


# 学生
@router.get("/students", summary="就业台账列表")
def students(page: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=200),
             keyword: Optional[str] = None, classId: Optional[str] = None,
             destinationType: Optional[str] = None, verifyStatus: Optional[str] = None,
             helpLevel: Optional[str] = None, user=Depends(get_current_user)):
    i, t = svc.list_students(page, pageSize, keyword=keyword, class_id=classId,
                             destination_type=destinationType, verify_status=verifyStatus,
                             help_level=helpLevel)
    return _p(i, t, page, pageSize)


@router.get("/students/{sid}", summary="就业学生详情")
def student_detail(sid: str, user=Depends(get_current_user)):
    return success(svc.get_student_detail(sid))


@router.post("/students", summary="新增就业记录")
def student_create(body: StudentCreate, user=Depends(get_current_user)):
    return success(svc.create_student(body.model_dump()), message="已新增")


@router.put("/students/{sid}", summary="编辑就业记录")
def student_update(sid: str, body: StudentUpdate, user=Depends(get_current_user)):
    return success(svc.update_student(sid, body.model_dump()), message="已保存")


@router.post("/students/{sid}/void", summary="作废就业记录（原因≥5字）")
def student_void(sid: str, body: ReasonBody, user=Depends(get_current_user)):
    return success(svc.void_student(sid, body.reason), message="已作废")


@router.post("/students/mark-destination", summary="批量标记去向")
def mark_destination(body: MarkDestBody, user=Depends(get_current_user)):
    return success(svc.batch_mark_destination(body.ids, body.destinationType), message="已标记")


# 材料
@router.get("/materials", summary="就业材料列表")
def materials(page: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=200),
              keyword: Optional[str] = None, status: Optional[str] = None,
              materialType: Optional[str] = None, user=Depends(get_current_user)):
    i, t = svc.list_materials(page, pageSize, keyword=keyword, status=status, material_type=materialType)
    return _p(i, t, page, pageSize)


@router.post("/materials/{mid}/approve", summary="材料审核通过")
def material_approve(mid: str, body: CommentBody = CommentBody(), user=Depends(get_current_user)):
    return success(svc.approve_material(mid, body.comment), message="已通过")


@router.post("/materials/{mid}/return", summary="材料退回（原因≥5字）")
def material_return(mid: str, body: ReasonBody, user=Depends(get_current_user)):
    return success(svc.return_material(mid, body.reason), message="已退回")


# 未就业帮扶
@router.get("/unemployed", summary="未就业学生列表")
def unemployed(page: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=200),
               keyword: Optional[str] = None, helpLevel: Optional[str] = None,
               riskLevel: Optional[str] = None, user=Depends(get_current_user)):
    i, t = svc.list_unemployed(page, pageSize, keyword=keyword, help_level=helpLevel, risk_level=riskLevel)
    return _p(i, t, page, pageSize)


@router.post("/unemployed/mark-employed", summary="标记已就业")
def unemployed_employed(body: IdsBody, user=Depends(get_current_user)):
    return success(svc.mark_employed(body.ids), message="已标记")


@router.post("/unemployed/mark-key-help", summary="标记重点帮扶")
def unemployed_key_help(body: IdsBody, user=Depends(get_current_user)):
    return success(svc.mark_key_help(body.ids), message="已标记")


@router.post("/unemployed/assign-teacher", summary="分配就业老师")
def unemployed_assign(body: AssignTeacherBody, user=Depends(get_current_user)):
    return success(svc.assign_teacher(body.ids, body.teacher), message="已分配")


# 跟进
@router.get("/followups", summary="就业跟进列表")
def followups(page: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=200),
              keyword: Optional[str] = None, status: Optional[str] = None,
              user=Depends(get_current_user)):
    i, t = svc.list_followups(page, pageSize, keyword=keyword, status=status)
    return _p(i, t, page, pageSize)


@router.post("/followups", summary="新增就业跟进")
def followup_create(body: FollowUpCreate, user=Depends(get_current_user)):
    return success(svc.create_followup(body.model_dump()), message="已记录")


@router.post("/followups/{fid}/void", summary="作废跟进（原因≥5字）")
def followup_void(fid: str, body: ReasonBody, user=Depends(get_current_user)):
    return success(svc.void_followup(fid, body.reason), message="已作废")


# 企业 / 岗位
@router.get("/companies", summary="企业列表")
def companies(page: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=200),
              keyword: Optional[str] = None, status: Optional[str] = None,
              user=Depends(get_current_user)):
    i, t = svc.list_companies(page, pageSize, keyword=keyword, status=status)
    return _p(i, t, page, pageSize)


@router.post("/companies", summary="新增企业（信用代码必填）")
def company_create(body: CompanyCreate, user=Depends(get_current_user)):
    return success(svc.create_company(body.model_dump()), message="已新增")


@router.post("/companies/{cid}/disable", summary="停用企业（原因≥5字，级联关闭岗位）")
def company_disable(cid: str, body: ReasonBody, user=Depends(get_current_user)):
    return success(svc.disable_company(cid, body.reason), message="已停用")


@router.get("/jobs", summary="岗位列表")
def jobs(page: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=200),
         keyword: Optional[str] = None, status: Optional[str] = None,
         companyId: Optional[str] = None, user=Depends(get_current_user)):
    i, t = svc.list_jobs(page, pageSize, keyword=keyword, status=status, company_id=companyId)
    return _p(i, t, page, pageSize)


@router.post("/jobs", summary="新增岗位")
def job_create(body: JobCreate, user=Depends(get_current_user)):
    return success(svc.create_job(body.model_dump()), message="已新增")


@router.post("/jobs/{jid}/disable", summary="停用岗位（原因≥5字）")
def job_disable(jid: str, body: ReasonBody, user=Depends(get_current_user)):
    return success(svc.disable_job(jid, body.reason), message="已停用")


@router.get("/audit-logs", summary="就业域审计")
def audit_logs(page: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=200),
               bizType: Optional[str] = None, keyword: Optional[str] = None,
               user=Depends(get_current_user)):
    i, t = svc.list_audit(page, pageSize, biz_type=bizType, keyword=keyword)
    return _p(i, t, page, pageSize)
