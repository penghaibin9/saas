"""在校服务域 API（/api/v1/campus-service/*）。真实走库；写操作落域审计。"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query

from app.core.response import paginate, success
from app.core.permissions import require_permission
from app.schemas.campus_service import (AssignBody, CommentBody, DisciplineCreate, DisciplineUpdate,
                                        DormExcHandle, DormExcMark, HandleBody, IdsBody, NoteBody,
                                        ReasonBody, StudentCreate, StudentUpdate, VersionedIdsBody,
                                        WorkOrderCreate)
from app.services import campus_service_service as svc

router = APIRouter(prefix="/campus-service", tags=["在校服务"])


def _p(items, total, page, ps):
    return success(paginate(items, total, page, ps))


@router.get("/dashboard", summary="在校服务看板")
def dashboard(user=Depends(require_permission("campusService.dashboard.view"))):
    return success(svc.get_dashboard())


# 学生台账
@router.get("/students", summary="服务台账列表")
def students(page: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=200),
             keyword: Optional[str] = None, classId: Optional[str] = None,
             careLevel: Optional[str] = None, riskLevel: Optional[str] = None,
             user=Depends(require_permission("campusService.student.view"))):
    i, t = svc.list_students(page, pageSize, keyword=keyword, class_id=classId, care_level=careLevel,
                             risk_level=riskLevel)
    return _p(i, t, page, pageSize)


@router.get("/students/{sid}", summary="服务台账详情")
def student_detail(sid: str, user=Depends(require_permission("campusService.student.view"))):
    return success(svc.get_student_detail(sid))


@router.post("/students", summary="新增服务记录")
def student_create(body: StudentCreate, user=Depends(require_permission("campusService.student.create"))):
    return success(svc.create_student(body.model_dump()), message="已新增")


@router.put("/students/{sid}", summary="编辑服务记录")
def student_update(sid: str, body: StudentUpdate, user=Depends(require_permission("campusService.student.edit"))):
    return success(svc.update_student(sid, body.model_dump()), message="已保存")


@router.post("/students/{sid}/void", summary="作废服务记录（原因≥5字）")
def student_void(sid: str, body: ReasonBody, user=Depends(require_permission("campusService.student.void"))):
    return success(svc.void_student(sid, body.reason), message="已作废")


# 请假旧接口已退出；正式接口统一为 /student-affairs/leave/*。

# 资助
@router.get("/grants", summary="资助列表（金额脱敏）")
def grants(page: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=200),
           keyword: Optional[str] = None, type: Optional[str] = None, status: Optional[str] = None,
           user=Depends(require_permission("campusService.grant.view"))):
    i, t = svc.list_grants(page, pageSize, keyword=keyword, type=type, status=status)
    return _p(i, t, page, pageSize)


@router.get("/grants/{gid}", summary="资助详情")
def grant_detail(gid: str, user=Depends(require_permission("campusService.grant.view"))):
    return success(svc.get_grant_detail(gid))


@router.post("/grants/{gid}/approve", summary="资助通过")
def grant_approve(gid: str, body: CommentBody, user=Depends(require_permission("campusService.grant.approve"))):
    return success(svc.approve_grant(gid, body.comment, body.version), message="已通过")


@router.post("/grants/{gid}/return", summary="资助退回（原因≥5字）")
def grant_return(gid: str, body: ReasonBody, user=Depends(require_permission("campusService.grant.approve"))):
    return success(svc.return_grant(gid, body.reason, body.version), message="已退回")


@router.post("/grants/batch-approve", summary="批量通过资助")
def grant_batch(body: VersionedIdsBody, user=Depends(require_permission("campusService.grant.approve"))):
    items = [{"id": x.id, "version": x.version} for x in (body.items or [])]
    return success(svc.batch_approve_grants(items), message="已批量通过")


# 宿舍
@router.get("/dorm-records", summary="住宿记录列表")
def dorm_records(page: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=200),
                 keyword: Optional[str] = None, status: Optional[str] = None,
                 user=Depends(require_permission("campusService.dorm.view"))):
    i, t = svc.list_dorm_records(page, pageSize, keyword=keyword, status=status)
    return _p(i, t, page, pageSize)


@router.get("/dorm-exceptions", summary="宿舍异常列表")
def dorm_exceptions(page: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=200),
                    keyword: Optional[str] = None, type: Optional[str] = None,
                    status: Optional[str] = None, user=Depends(require_permission("campusService.dorm.view"))):
    i, t = svc.list_dorm_exceptions(page, pageSize, keyword=keyword, type=type, status=status)
    return _p(i, t, page, pageSize)


@router.post("/dorm-exceptions", summary="标记宿舍异常（说明≥5字）")
def dorm_exc_mark(body: DormExcMark, user=Depends(require_permission("campusService.dorm.handle"))):
    return success(svc.mark_dorm_exception(body.model_dump()), message="已标记")


@router.post("/dorm-exceptions/{eid}/handle", summary="处理宿舍异常（说明≥5字）")
def dorm_exc_handle(eid: str, body: DormExcHandle, user=Depends(require_permission("campusService.dorm.handle"))):
    return success(svc.handle_dorm_exception(eid, body.note, body.complete, body.version), message="已处理")


# 违纪
@router.get("/disciplines", summary="违纪处分列表")
def disciplines(page: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=200),
                keyword: Optional[str] = None, type: Optional[str] = None, status: Optional[str] = None,
                user=Depends(require_permission("campusService.discipline.view"))):
    i, t = svc.list_disciplines(page, pageSize, keyword=keyword, type=type, status=status)
    return _p(i, t, page, pageSize)


@router.post("/disciplines", summary="新增处分（事由≥5字）")
def discipline_create(body: DisciplineCreate, user=Depends(require_permission("campusService.discipline.create"))):
    return success(svc.create_discipline(body.model_dump()), message="已新增")


@router.put("/disciplines/{did}", summary="更新处分")
def discipline_update(did: str, body: DisciplineUpdate, user=Depends(require_permission("campusService.discipline.edit"))):
    return success(svc.update_discipline(did, body.model_dump()), message="已更新")


@router.post("/disciplines/{did}/void", summary="作废处分（原因≥5字）")
def discipline_void(did: str, body: ReasonBody, user=Depends(require_permission("campusService.discipline.void"))):
    return success(svc.void_discipline(did, body.reason), message="已作废")


# 工单
@router.get("/work-orders", summary="服务工单列表")
def work_orders(page: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=200),
                keyword: Optional[str] = None, type: Optional[str] = None, status: Optional[str] = None,
                priority: Optional[str] = None, user=Depends(require_permission("campusService.workOrder.view"))):
    i, t = svc.list_work_orders(page, pageSize, keyword=keyword, type=type, status=status,
                                priority=priority)
    return _p(i, t, page, pageSize)


@router.get("/work-orders/{wid}", summary="工单详情")
def work_order_detail(wid: str, user=Depends(require_permission("campusService.workOrder.view"))):
    return success(svc.get_work_order_detail(wid))


@router.post("/work-orders", summary="新增工单")
def work_order_create(body: WorkOrderCreate, user=Depends(require_permission("campusService.workOrder.create"))):
    return success(svc.create_work_order(body.model_dump()), message="已创建")


@router.post("/work-orders/assign", summary="批量分派工单")
def work_order_assign(body: AssignBody, user=Depends(require_permission("campusService.workOrder.assign"))):
    return success(svc.assign_work_orders(body.ids, body.handler), message="已分派")


@router.post("/work-orders/{wid}/handle", summary="处理工单（说明≥5字）")
def work_order_handle(wid: str, body: HandleBody, user=Depends(require_permission("campusService.workOrder.handle"))):
    return success(svc.handle_work_order(wid, body.note, body.close, body.version), message="已处理")


@router.post("/work-orders/{wid}/close", summary="关闭工单（原因≥5字）")
def work_order_close(wid: str, body: ReasonBody, user=Depends(require_permission("campusService.workOrder.handle"))):
    return success(svc.close_work_order(wid, body.reason, body.version), message="已关闭")


# 心理关怀 + 审计
@router.get("/mental-records", summary="心理关怀记录（涉密：细粒度权限+明细遮蔽+原因审计）")
def mental_records(page: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=200),
                   keyword: Optional[str] = None, reason: Optional[str] = None,
                   user=Depends(require_permission("studentAffairs.risk.psyDetail.view"))):
    # SEC-1：由零门禁 get_current_user 改为 psyDetail.view 细粒度权限；counselorNote 明细默认遮蔽，
    # 仅授权角色 + 原因(≥5字) 方返回明文并写 SENSITIVE_VIEW（见 svc.list_mental）。
    i, t = svc.list_mental(page, pageSize, keyword=keyword, user=user, reason=reason)
    return _p(i, t, page, pageSize)


@router.get("/audit-logs", summary="在校服务域审计")
def audit_logs(page: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=200),
               bizType: Optional[str] = None, keyword: Optional[str] = None,
               user=Depends(require_permission("campusService.audit.view"))):
    i, t = svc.list_audit(page, pageSize, biz_type=bizType, keyword=keyword)
    return _p(i, t, page, pageSize)
