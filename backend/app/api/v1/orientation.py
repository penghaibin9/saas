"""数字迎新域 API（/api/v1/orientation/*）。真实走库；写操作落域审计。"""
from __future__ import annotations

import io
from typing import Optional

from fastapi import APIRouter, Body, Depends, File, Query, UploadFile
from fastapi.responses import StreamingResponse

from app.core.response import paginate, success
from app.core.security import get_current_user
from app.schemas.internship import ImportErrorsExport
from app.schemas.orientation import (ArchiveCreate, AssignCounselorBody, BatchCreate, BatchRemindBody, BatchUpdate, BlockedBody,
                                      CommentBody, DormBody, FlowUpdate, FollowUpBody, IdsBody,
                                      NoteBody, NoticeCreate, PointCreate, PointUpdate, ReasonBody,
                                      RemarkBody, StudentCreate, StudentExportRequest, StudentImport,
                                      StudentUpdate, VerifyBody)
from app.services import audit_log
from app.services import orientation_service as svc
from app.services import xlsx_util

_ORI_STU_HEADERS = ["录取编号", "姓名", "身份证号", "录取专业", "联系电话", "班级"]
_ORI_STU_MAP = {"录取编号": "admissionNo", "姓名": "name", "身份证号": "idCard",
                "录取专业": "majorName", "联系电话": "phone", "班级": "className"}


def _ori_stu_row_values(r: dict) -> list:
    return [r.get("admissionNo", ""), r.get("name", ""), r.get("idCard", ""),
            r.get("majorName", ""), r.get("phone", ""), r.get("className", "")]

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


@router.get("/students/import/template", summary="新生导入·下载 Excel 模板(.xlsx)")
def student_import_template(user=Depends(get_current_user)):
    data = xlsx_util.build_template_xlsx(
        _ORI_STU_HEADERS,
        required=["录取编号", "姓名", "录取专业"],
        samples=[["LQ2026010001", "李明", "330102200801011234", "软件技术", "13800001111", "软件2401"]],
        notes=[
            "1. 只导入「导入模板」页；录取编号租户内唯一。",
            "2. 身份证号、联系电话为敏感字段，导入后列表默认脱敏。",
            "3. 保存为 .xlsx 后上传，系统预校验通过方可确认导入。",
        ])
    return StreamingResponse(
        io.BytesIO(data),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=orientation_student_import_template.xlsx"})


@router.post("/students/import/xlsx", summary="新生导入·上传 Excel 解析+预校验")
async def student_import_xlsx(file: UploadFile = File(...), user=Depends(get_current_user)):
    content = await file.read()
    rows = xlsx_util.read_xlsx(content, _ORI_STU_MAP)
    dry = svc.import_students_dry_run(rows)
    return success({"rows": rows, **dry})


@router.post("/students/import/dry-run", summary="新生导入·高级粘贴预校验")
def student_import_dry_run(body: StudentImport, user=Depends(get_current_user)):
    return success(svc.import_students_dry_run(body.rows))


@router.post("/students/import/errors-xlsx", summary="新生导入·下载错误行 Excel")
def student_import_errors_xlsx(body: ImportErrorsExport, user=Depends(get_current_user)):
    content = xlsx_util.build_error_rows_xlsx(
        _ORI_STU_HEADERS, body.rows, body.errors, _ori_stu_row_values)
    packed = xlsx_util.pack_xlsx_result(content, "新生导入错误行.xlsx", len(body.errors))
    return success(packed)


@router.post("/students/import/confirm", summary="新生导入·确认（整批事务）")
def student_import_confirm(body: StudentImport, user=Depends(get_current_user)):
    result = svc.import_students_confirm(body.rows)
    audit_log.record("导入新生台账", "orientation-student:import", detail=result)
    return success(result, message="导入完成")


@router.post("/students/export", summary="新生台账导出 Excel（脱敏+水印+审计）")
def student_export(body: StudentExportRequest, user=Depends(get_current_user)):
    data = svc.export_students_xlsx(
        keyword=body.keyword, class_id=body.classId, stage=body.stage,
        report_status=body.reportStatus, payment_status=body.paymentStatus,
        risk_level=body.riskLevel, purpose=body.purpose, mask=body.mask)
    audit_log.record("导出新生台账", "orientation-student:export",
                     detail={"rowCount": data["rowCount"], "purpose": body.purpose})
    return success(data)


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


@router.post("/students/{sid}/verify", summary="新生信息核验（通过/不通过；不通过原因≥5字）")
def student_verify(sid: str, body: VerifyBody, user=Depends(get_current_user)):
    return success(svc.verify_student(sid, body.passed, body.reason), message="已核验")


@router.post("/students/batch-remind", summary="批量提醒新生")
def student_batch_remind(body: BatchRemindBody, user=Depends(get_current_user)):
    return success(svc.batch_remind_students(body.ids, body.message), message="已记录提醒")


@router.post("/students/batch-assign-counselor", summary="批量分配辅导员")
def student_batch_assign_counselor(body: AssignCounselorBody, user=Depends(get_current_user)):
    return success(svc.batch_assign_counselor(body.ids, body.counselor), message="已分配辅导员")


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


# ═══ 迎新批次 ═══

@router.get("/batches", summary="迎新批次列表")
def batches(page: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=200),
            keyword: Optional[str] = None, status: Optional[str] = None,
            user=Depends(get_current_user)):
    items, total = svc.list_batches(page, pageSize, keyword=keyword, status=status)
    return success(paginate(items, total, page, pageSize))


@router.get("/batches/{bid}", summary="批次详情")
def batch_detail(bid: str, user=Depends(get_current_user)):
    return success(svc.get_batch(bid))


@router.post("/batches", summary="新建批次")
def batch_create(body: BatchCreate, user=Depends(get_current_user)):
    return success(svc.create_batch(body.model_dump()), message="已新建")


@router.put("/batches/{bid}", summary="编辑批次")
def batch_update(bid: str, body: BatchUpdate, user=Depends(get_current_user)):
    return success(svc.update_batch(bid, body.model_dump()), message="已保存")


@router.post("/batches/{bid}/activate", summary="启用批次（草稿→进行中）")
def batch_activate(bid: str, user=Depends(get_current_user)):
    return success(svc.activate_batch(bid), message="已启用")


@router.post("/batches/{bid}/close", summary="结束批次（进行中→已结束）")
def batch_close(bid: str, user=Depends(get_current_user)):
    return success(svc.close_batch(bid), message="已结束")


@router.post("/batches/{bid}/void", summary="作废批次（原因≥5字）")
def batch_void(bid: str, body: ReasonBody, user=Depends(get_current_user)):
    return success(svc.delete_batch(bid, body.reason), message="已作废")


# ═══ 现场报到点 ═══

@router.get("/checkin-points", summary="现场报到点列表")
def checkin_points(page: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=200),
                   keyword: Optional[str] = None, status: Optional[str] = None,
                   user=Depends(get_current_user)):
    items, total = svc.list_checkin_points(page, pageSize, keyword=keyword, status=status)
    return success(paginate(items, total, page, pageSize))


@router.post("/checkin-points", summary="新增报到点")
def checkin_point_create(body: PointCreate, user=Depends(get_current_user)):
    return success(svc.create_checkin_point(body.model_dump()), message="已新增")


@router.put("/checkin-points/{pid}", summary="编辑报到点")
def checkin_point_update(pid: str, body: PointUpdate, user=Depends(get_current_user)):
    return success(svc.update_checkin_point(pid, body.model_dump()), message="已保存")


@router.post("/checkin-points/{pid}/toggle", summary="启用/停用报到点")
def checkin_point_toggle(pid: str, user=Depends(get_current_user)):
    return success(svc.toggle_checkin_point(pid), message="已切换")


@router.post("/checkin-points/{pid}/delete", summary="删除报到点")
def checkin_point_delete(pid: str, user=Depends(get_current_user)):
    return success(svc.delete_checkin_point(pid), message="已删除")


# ═══ 报到流程配置 ═══

@router.get("/flow-config", summary="报到流程配置")
def flow_config(user=Depends(get_current_user)):
    return success(svc.list_flow_config())


@router.put("/flow-config/{fid}", summary="调整流程环节（启用/必办）")
def flow_config_update(fid: str, body: FlowUpdate, user=Depends(get_current_user)):
    return success(svc.update_flow_config(fid, body.model_dump()), message="已更新")


# ═══ 迎新通知 ═══

@router.get("/notices", summary="迎新通知列表")
def notices(page: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=200),
            keyword: Optional[str] = None, status: Optional[str] = None, channel: Optional[str] = None,
            user=Depends(get_current_user)):
    items, total = svc.list_notice_tasks(page, pageSize, keyword=keyword, status=status, channel=channel)
    return success(paginate(items, total, page, pageSize))


@router.post("/notices", summary="新建通知")
def notice_create(body: NoticeCreate, user=Depends(get_current_user)):
    return success(svc.create_notice_task(body.model_dump()), message="已新建")


@router.post("/notices/{nid}/send", summary="发送通知（仅站内已配置，短信/邮件显示未配置）")
def notice_send(nid: str, user=Depends(get_current_user)):
    return success(svc.send_notice_task(nid), message="已提交发送")


# ═══ 迎新归档 ═══

@router.get("/archives", summary="迎新归档列表")
def archives(page: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=200),
             keyword: Optional[str] = None, status: Optional[str] = None,
             user=Depends(get_current_user)):
    items, total = svc.list_archives(page, pageSize, keyword=keyword, status=status)
    return success(paginate(items, total, page, pageSize))


@router.post("/archives", summary="新建归档任务")
def archive_create(body: ArchiveCreate, user=Depends(get_current_user)):
    return success(svc.create_archive(body.model_dump()), message="已新建")


@router.post("/archives/{aid}/run", summary="执行归档")
def archive_run(aid: str, user=Depends(get_current_user)):
    return success(svc.run_archive(aid), message="已归档")
