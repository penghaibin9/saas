"""数字迎新域 API（/api/v1/orientation/*）。真实走库；写操作落域审计。"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Body, Depends, Query

from app.core.response import paginate, success
from app.core.security import get_current_user
from app.schemas.orientation import (BlockedBody, CommentBody, DormBody, FollowUpBody, IdsBody,
                                      NoteBody, ReasonBody, RemarkBody, StudentCreate, StudentUpdate)
from app.services import orientation_service as svc

router = APIRouter(prefix="/orientation", tags=["数字迎新"])


@router.get("/dashboard", summary="迎新看板")
def dashboard(user=Depends(get_current_user)):
    return success(svc.get_dashboard())


@router.get("/students", summary="新生台账列表")
def students(page: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=200),
             keyword: Optional[str] = None, classId: Optional[str] = None, stage: Optional[str] = None,
             reportStatus: Optional[str] = None, paymentStatus: Optional[str] = None,
             riskLevel: Optional[str] = None, user=Depends(get_current_user)):
    items, total = svc.list_students(page, pageSize, keyword=keyword, class_id=classId, stage=stage,
                                     report_status=reportStatus, payment_status=paymentStatus,
                                     risk_level=riskLevel)
    return success(paginate(items, total, page, pageSize))


@router.get("/students/{sid}", summary="新生详情")
def student_detail(sid: str, user=Depends(get_current_user)):
    return success(svc.get_student_detail(sid))


@router.post("/students", summary="新增新生")
def student_create(body: StudentCreate, user=Depends(get_current_user)):
    return success(svc.create_student(body.model_dump()), message="已新增")


@router.put("/students/{sid}", summary="编辑新生")
def student_update(sid: str, body: StudentUpdate, user=Depends(get_current_user)):
    return success(svc.update_student(sid, body.model_dump()), message="已保存")


@router.post("/students/{sid}/void", summary="作废新生（原因≥5字）")
def student_void(sid: str, body: ReasonBody, user=Depends(get_current_user)):
    return success(svc.void_student(sid, body.reason), message="已作废")


@router.get("/progress", summary="报到进度")
def progress(page: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=200),
             keyword: Optional[str] = None, blockedOnly: str = "NO", user=Depends(get_current_user)):
    items, total = svc.list_progress(page, pageSize, keyword=keyword, blocked_only=blockedOnly)
    return success(paginate(items, total, page, pageSize))


@router.put("/progress/{sid}/blocked", summary="编辑卡点")
def progress_blocked(sid: str, body: BlockedBody, user=Depends(get_current_user)):
    return success(svc.update_blocked(sid, body.blockedStep, body.blockedReason), message="已更新")


@router.post("/progress/{sid}/resolve", summary="标记卡点人工已处理")
def progress_resolve(sid: str, body: NoteBody = Body(default=NoteBody()), user=Depends(get_current_user)):
    return success(svc.resolve_blocked(sid, body.note), message="已处理")


@router.get("/payments", summary="缴费列表")
def payments(page: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=200),
             keyword: Optional[str] = None, paymentStatus: Optional[str] = None,
             user=Depends(get_current_user)):
    items, total = svc.list_payments(page, pageSize, keyword=keyword, payment_status=paymentStatus)
    return success(paginate(items, total, page, pageSize))


@router.get("/green-channels", summary="绿色通道列表")
def green_channels(page: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=200),
                   keyword: Optional[str] = None, status: Optional[str] = None,
                   user=Depends(get_current_user)):
    items, total = svc.list_green_channels(page, pageSize, keyword=keyword, status=status)
    return success(paginate(items, total, page, pageSize))


@router.post("/green-channels/{gid}/approve", summary="绿色通道通过")
def gc_approve(gid: str, body: RemarkBody = Body(default=RemarkBody()), user=Depends(get_current_user)):
    return success(svc.approve_green_channel(gid, body.remark), message="已通过")


@router.post("/green-channels/{gid}/reject", summary="绿色通道驳回（原因≥5字）")
def gc_reject(gid: str, body: ReasonBody, user=Depends(get_current_user)):
    return success(svc.reject_green_channel(gid, body.reason), message="已驳回")


@router.post("/green-channels/{gid}/return", summary="绿色通道退回（原因≥5字）")
def gc_return(gid: str, body: ReasonBody, user=Depends(get_current_user)):
    return success(svc.return_green_channel(gid, body.reason), message="已退回")


@router.get("/materials", summary="材料审核列表")
def materials(page: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=200),
              keyword: Optional[str] = None, status: Optional[str] = None,
              materialType: Optional[str] = None, user=Depends(get_current_user)):
    items, total = svc.list_materials(page, pageSize, keyword=keyword, status=status,
                                      material_type=materialType)
    return success(paginate(items, total, page, pageSize))


@router.post("/materials/{mid}/approve", summary="材料通过")
def mat_approve(mid: str, body: CommentBody = Body(default=CommentBody()), user=Depends(get_current_user)):
    return success(svc.approve_material(mid, body.comment), message="已通过")


@router.post("/materials/{mid}/return", summary="材料退回（原因≥5字）")
def mat_return(mid: str, body: ReasonBody, user=Depends(get_current_user)):
    return success(svc.return_material(mid, body.reason), message="已退回")


@router.get("/dorms", summary="宿舍入住列表")
def dorms(page: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=200),
          keyword: Optional[str] = None, dormStatus: Optional[str] = None,
          building: Optional[str] = None, user=Depends(get_current_user)):
    items, total = svc.list_dorms(page, pageSize, keyword=keyword, dorm_status=dormStatus,
                                  building=building)
    return success(paginate(items, total, page, pageSize))


@router.put("/dorms/{sid}", summary="编辑宿舍")
def dorm_update(sid: str, body: DormBody, user=Depends(get_current_user)):
    return success(svc.update_dorm(sid, body.model_dump(exclude_unset=True)), message="已保存")


@router.post("/dorms/confirm", summary="批量确认入住")
def dorm_confirm(body: IdsBody, user=Depends(get_current_user)):
    return success(svc.batch_confirm_checkin(body.ids), message="已确认")


@router.post("/dorms/{sid}/exception", summary="标记入住异常（说明≥5字）")
def dorm_exception(sid: str, body: NoteBody, user=Depends(get_current_user)):
    return success(svc.mark_dorm_exception(sid, body.note), message="已标记")


@router.get("/exceptions", summary="迎新异常列表")
def exceptions(page: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=200),
               keyword: Optional[str] = None, exceptionType: Optional[str] = None,
               status: Optional[str] = None, riskLevel: Optional[str] = None,
               user=Depends(get_current_user)):
    items, total = svc.list_exceptions(page, pageSize, keyword=keyword, exception_type=exceptionType,
                                       status=status, risk_level=riskLevel)
    return success(paginate(items, total, page, pageSize))


@router.get("/exceptions/{eid}", summary="异常详情")
def exception_detail(eid: str, user=Depends(get_current_user)):
    return success(svc.get_exception_detail(eid))


@router.post("/exceptions/{eid}/followup", summary="新增异常跟进")
def exception_followup(eid: str, body: FollowUpBody, user=Depends(get_current_user)):
    return success(svc.add_followup(eid, body.content, body.way), message="已记录")


@router.post("/exceptions/{eid}/resolve", summary="标记异常已处理")
def exception_resolve(eid: str, body: NoteBody = Body(default=NoteBody()), user=Depends(get_current_user)):
    return success(svc.resolve_exception(eid, body.note), message="已处理")


@router.post("/exceptions/{eid}/escalate", summary="升级异常风险（原因≥5字）")
def exception_escalate(eid: str, body: ReasonBody, user=Depends(get_current_user)):
    return success(svc.escalate_exception(eid, body.reason), message="已升级")


@router.get("/audit-logs", summary="迎新域审计")
def audit_logs(page: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=200),
               bizType: Optional[str] = None, keyword: Optional[str] = None,
               user=Depends(get_current_user)):
    items, total = svc.list_audit(page, pageSize, biz_type=bizType, keyword=keyword)
    return success(paginate(items, total, page, pageSize))
