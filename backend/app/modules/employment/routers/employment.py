"""就业服务域 API（/api/v1/employment/*）。

A3 / P0-05：正式 PC 页面统一走 scoped runtime；学生相关读写均继承当前 dataScope，
未配置范围 fail-closed。企业/岗位未注册在当前就业正式路由树，暂保留既有真实 service。
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Header, Query

from app.core.idempotency import idempotency_guard
from app.core.permissions import require_permission
from app.core.response import paginate, success
from app.modules.employment.schemas.employment import (
    AssignTeacherBody, CommentBody, CompanyCreate, FollowUpCreate, IdsBody,
    JobCreate, MarkDestBody, ReasonBody, StudentCreate, StudentUpdate,
)
from app.modules.employment.services import employment_runtime_audit_service as audit_runtime
from app.modules.employment.services import employment_runtime_service as svc
from app.modules.employment.services import employment_service as raw_svc

router = APIRouter(prefix="/employment", tags=["就业服务"])


def _p(items, total, page, ps):
    return success(paginate(items, total, page, ps))


def _idem(user, operation: str, key: str | None, payload: dict):
    return idempotency_guard(user, operation, key, payload, require_store=True)


@router.get("/dashboard", summary="就业看板（按当前数据范围）")
def dashboard(user=Depends(require_permission("employment.dashboard.view"))):
    return success(svc.get_dashboard(user=user))


@router.get("/options", summary="就业中心真实筛选选项（按当前数据范围）")
def employment_options(user=Depends(require_permission("employment.student.view"))):
    return success(svc.get_filter_options(user=user))


# 学生
@router.get("/students", summary="就业台账列表")
def students(page: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=200),
             keyword: Optional[str] = None, classId: Optional[str] = None,
             destinationType: Optional[str] = None, verifyStatus: Optional[str] = None,
             helpLevel: Optional[str] = None, user=Depends(require_permission("employment.student.view"))):
    items, total = svc.list_students(
        page, pageSize, user=user, keyword=keyword, class_id=classId,
        destination_type=destinationType, verify_status=verifyStatus, help_level=helpLevel,
    )
    return _p(items, total, page, pageSize)


@router.get("/students/{sid}", summary="就业学生详情")
def student_detail(sid: str, user=Depends(require_permission("employment.student.view"))):
    return success(svc.get_student_detail(sid, user=user))


@router.post("/students", summary="新增就业记录")
def student_create(body: StudentCreate,
                   user=Depends(require_permission("employment.student.manage")),
                   idempotency_key: str | None = Header(None, alias="Idempotency-Key")):
    payload = body.model_dump()
    with _idem(user, "employment-student-create", idempotency_key, payload) as guard:
        if guard.cached is not None:
            return success(guard.cached, message="已新增（幂等重放）")
        result = svc.create_student(payload, user=user)
        guard.success(result)
        return success(result, message="已新增")


@router.put("/students/{sid}", summary="编辑就业记录")
def student_update(sid: str, body: StudentUpdate,
                   user=Depends(require_permission("employment.student.manage")),
                   idempotency_key: str | None = Header(None, alias="Idempotency-Key")):
    payload = {"sid": sid, **body.model_dump()}
    with _idem(user, "employment-student-update", idempotency_key, payload) as guard:
        if guard.cached is not None:
            return success(guard.cached, message="已保存（幂等重放）")
        result = svc.update_student(sid, body.model_dump(), user=user)
        guard.success(result)
        return success(result, message="已保存")


@router.post("/students/{sid}/void", summary="作废就业记录（原因≥5字）")
def student_void(sid: str, body: ReasonBody,
                 user=Depends(require_permission("employment.student.manage")),
                 idempotency_key: str | None = Header(None, alias="Idempotency-Key")):
    payload = {"sid": sid, "reason": body.reason}
    with _idem(user, "employment-student-void", idempotency_key, payload) as guard:
        if guard.cached is not None:
            return success(guard.cached, message="已作废（幂等重放）")
        result = svc.void_student(sid, body.reason, user=user)
        guard.success(result)
        return success(result, message="已作废")


@router.post("/students/mark-destination", summary="批量标记去向")
def mark_destination(body: MarkDestBody,
                     user=Depends(require_permission("employment.student.manage")),
                     idempotency_key: str | None = Header(None, alias="Idempotency-Key")):
    payload = body.model_dump()
    with _idem(user, "employment-mark-destination", idempotency_key, payload) as guard:
        if guard.cached is not None:
            return success(guard.cached, message="已标记（幂等重放）")
        result = svc.batch_mark_destination(body.ids, body.destinationType, user=user)
        guard.success(result)
        return success(result, message="已标记")


# 材料
@router.get("/materials", summary="就业材料列表")
def materials(page: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=200),
              keyword: Optional[str] = None, status: Optional[str] = None,
              materialType: Optional[str] = None, user=Depends(require_permission("employment.material.view"))):
    items, total = svc.list_materials(
        page, pageSize, user=user, keyword=keyword, status=status, material_type=materialType,
    )
    return _p(items, total, page, pageSize)


@router.get("/materials/{mid}", summary="就业材料审核详情")
def material_detail(mid: str, user=Depends(require_permission("employment.material.view"))):
    return success(svc.get_material_detail(mid, user=user))


@router.post("/materials/{mid}/approve", summary="材料审核通过")
def material_approve(mid: str, body: CommentBody = CommentBody(),
                     user=Depends(require_permission("employment.material.approve")),
                     idempotency_key: str | None = Header(None, alias="Idempotency-Key")):
    payload = {"mid": mid, "comment": body.comment or ""}
    with _idem(user, "employment-material-approve", idempotency_key, payload) as guard:
        if guard.cached is not None:
            return success(guard.cached, message="已通过（幂等重放）")
        result = svc.approve_material(mid, body.comment, user=user)
        guard.success(result)
        return success(result, message="已通过")


@router.post("/materials/{mid}/return", summary="材料退回（原因≥5字）")
def material_return(mid: str, body: ReasonBody,
                    user=Depends(require_permission("employment.material.approve")),
                    idempotency_key: str | None = Header(None, alias="Idempotency-Key")):
    payload = {"mid": mid, "reason": body.reason}
    with _idem(user, "employment-material-return", idempotency_key, payload) as guard:
        if guard.cached is not None:
            return success(guard.cached, message="已退回（幂等重放）")
        result = svc.return_material(mid, body.reason, user=user)
        guard.success(result)
        return success(result, message="已退回")


# 未就业帮扶
@router.get("/unemployed", summary="未就业学生列表")
def unemployed(page: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=200),
               keyword: Optional[str] = None, helpLevel: Optional[str] = None,
               riskLevel: Optional[str] = None, user=Depends(require_permission("employment.unemployed.view"))):
    items, total = svc.list_unemployed(
        page, pageSize, user=user, keyword=keyword, help_level=helpLevel, risk_level=riskLevel,
    )
    return _p(items, total, page, pageSize)


@router.post("/unemployed/mark-employed", summary="标记已就业")
def unemployed_employed(body: IdsBody,
                        user=Depends(require_permission("employment.unemployed.manage")),
                        idempotency_key: str | None = Header(None, alias="Idempotency-Key")):
    payload = body.model_dump()
    with _idem(user, "employment-mark-employed", idempotency_key, payload) as guard:
        if guard.cached is not None:
            return success(guard.cached, message="已标记（幂等重放）")
        result = svc.mark_employed(body.ids, user=user)
        guard.success(result)
        return success(result, message="已标记")


@router.post("/unemployed/mark-key-help", summary="标记重点帮扶")
def unemployed_key_help(body: IdsBody,
                        user=Depends(require_permission("employment.unemployed.manage")),
                        idempotency_key: str | None = Header(None, alias="Idempotency-Key")):
    payload = body.model_dump()
    with _idem(user, "employment-mark-key-help", idempotency_key, payload) as guard:
        if guard.cached is not None:
            return success(guard.cached, message="已标记（幂等重放）")
        result = svc.mark_key_help(body.ids, user=user)
        guard.success(result)
        return success(result, message="已标记")


@router.post("/unemployed/assign-teacher", summary="分配就业老师")
def unemployed_assign(body: AssignTeacherBody,
                      user=Depends(require_permission("employment.unemployed.assign")),
                      idempotency_key: str | None = Header(None, alias="Idempotency-Key")):
    payload = body.model_dump()
    with _idem(user, "employment-assign-teacher", idempotency_key, payload) as guard:
        if guard.cached is not None:
            return success(guard.cached, message="已分配（幂等重放）")
        result = svc.assign_teacher(body.ids, body.teacher, user=user)
        guard.success(result)
        return success(result, message="已分配")


# 跟进
@router.get("/followups", summary="就业跟进列表")
def followups(page: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=200),
              keyword: Optional[str] = None, status: Optional[str] = None,
              user=Depends(require_permission("employment.followup.view"))):
    items, total = svc.list_followups(page, pageSize, user=user, keyword=keyword, status=status)
    return _p(items, total, page, pageSize)


@router.post("/followups", summary="新增就业跟进")
def followup_create(body: FollowUpCreate,
                    user=Depends(require_permission("employment.followup.manage")),
                    idempotency_key: str | None = Header(None, alias="Idempotency-Key")):
    payload = body.model_dump()
    with _idem(user, "employment-followup-create", idempotency_key, payload) as guard:
        if guard.cached is not None:
            return success(guard.cached, message="已记录（幂等重放）")
        result = svc.create_followup(payload, user=user)
        guard.success(result)
        return success(result, message="已记录")


@router.post("/followups/{fid}/void", summary="作废跟进（原因≥5字）")
def followup_void(fid: str, body: ReasonBody,
                  user=Depends(require_permission("employment.followup.manage")),
                  idempotency_key: str | None = Header(None, alias="Idempotency-Key")):
    payload = {"fid": fid, "reason": body.reason}
    with _idem(user, "employment-followup-void", idempotency_key, payload) as guard:
        if guard.cached is not None:
            return success(guard.cached, message="已作废（幂等重放）")
        result = svc.void_followup(fid, body.reason, user=user)
        guard.success(result)
        return success(result, message="已作废")


# 企业 / 岗位：当前就业正式 PC 路由树未注册，保留既有真实 API，不回退 mock。
@router.get("/companies", summary="企业列表")
def companies(page: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=200),
              keyword: Optional[str] = None, status: Optional[str] = None,
              user=Depends(require_permission("employment.company.view"))):
    items, total = raw_svc.list_companies(page, pageSize, keyword=keyword, status=status)
    return _p(items, total, page, pageSize)


@router.post("/companies", summary="新增企业（信用代码必填）")
def company_create(body: CompanyCreate, user=Depends(require_permission("employment.company.manage"))):
    return success(raw_svc.create_company(body.model_dump()), message="已新增")


@router.post("/companies/{cid}/disable", summary="停用企业（原因≥5字，级联关闭岗位）")
def company_disable(cid: str, body: ReasonBody, user=Depends(require_permission("employment.company.manage"))):
    return success(raw_svc.disable_company(cid, body.reason), message="已停用")


@router.get("/jobs", summary="岗位列表")
def jobs(page: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=200),
         keyword: Optional[str] = None, status: Optional[str] = None,
         companyId: Optional[str] = None, user=Depends(require_permission("employment.job.view"))):
    items, total = raw_svc.list_jobs(page, pageSize, keyword=keyword, status=status, company_id=companyId)
    return _p(items, total, page, pageSize)


@router.post("/jobs", summary="新增岗位")
def job_create(body: JobCreate, user=Depends(require_permission("employment.job.manage"))):
    return success(raw_svc.create_job(body.model_dump()), message="已新增")


@router.post("/jobs/{jid}/disable", summary="停用岗位（原因≥5字）")
def job_disable(jid: str, body: ReasonBody, user=Depends(require_permission("employment.job.manage"))):
    return success(raw_svc.disable_job(jid, body.reason), message="已停用")


@router.get("/audit-logs", summary="就业域审计（按当前数据范围）")
def audit_logs(page: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=200),
               bizType: Optional[str] = None, keyword: Optional[str] = None,
               user=Depends(require_permission("employment.audit.view"))):
    items, total = audit_runtime.list_audit(
        page, pageSize, user=user, biz_type=bizType, keyword=keyword)
    return _p(items, total, page, pageSize)
