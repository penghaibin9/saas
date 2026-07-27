"""毕业设计中心 · 选题轮次/志愿 API（/api/v1/graduation/gd-topic-rounds/*）。"""
from __future__ import annotations

import hashlib
import io
from typing import Optional

from fastapi import APIRouter, Depends, File, Query, UploadFile
from fastapi.responses import StreamingResponse

from app.core.response import paginate, success
from app.core.security import get_current_user
from app.schemas.excel import ExcelErrorRows, ExcelImportRows
from app.modules.graduation.schemas.graduation_topic_round import GdTopicChoiceReview, GdTopicChoiceSubmit, GdTopicRoundCreate
from app.services import audit_log
from app.services import xlsx_util
from app.modules.graduation.services import graduation_topic_round_service as svc

router = APIRouter(prefix="/graduation", tags=["毕业设计-选题轮次"])


@router.get("/gd-topic-rounds/active", summary="当前进行中的选题轮次")
def gd_topic_round_active(batchId: Optional[str] = None, user=Depends(get_current_user)):
    data = svc.active_round(batch_id=batchId)
    return success(data)


@router.post("/gd-topic-rounds/export", summary="选题轮次台账导出 Excel（写审计）")
def gd_topic_rounds_export(batchId: Optional[str] = None, status: Optional[str] = None,
                           user=Depends(get_current_user)):
    data = svc.export_rounds_xlsx(batch_id=batchId, status=status)
    audit_log.record("导出选题轮次台账", "graduation-topic-round:export", detail={"rowCount": data["rowCount"]})
    return success(data)


@router.get("/gd-topic-rounds", summary="选题轮次列表")
def gd_topic_rounds(page: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=200),
                    batchId: Optional[str] = None, status: Optional[str] = None,
                    user=Depends(get_current_user)):
    items, total = svc.list_rounds(page, pageSize, batch_id=batchId, status=status)
    return success(paginate(items, total, page, pageSize))


@router.post("/gd-topic-rounds", summary="新建选题轮次")
def create_gd_topic_round(body: GdTopicRoundCreate, user=Depends(get_current_user)):
    result = svc.create_round(body)
    audit_log.record("新建选题轮次", f"graduation-topic-round:{result['id']}", detail={"name": result["roundName"]})
    return success(result, message="已创建")


@router.get("/gd-topic-rounds/{round_id}/choices/import/template", summary="选题志愿·下载 Excel 模板")
def gd_topic_choice_import_template(round_id: str, user=Depends(get_current_user)):
    data = svc.choice_import_template_bytes(round_id)
    return StreamingResponse(
        io.BytesIO(data),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=gd_topic_choice_import_template.xlsx"})


@router.post("/gd-topic-rounds/{round_id}/choices/import/xlsx", summary="选题志愿·上传 Excel 预校验")
async def gd_topic_choice_import_xlsx(round_id: str, file: UploadFile = File(...), user=Depends(get_current_user)):
    content = await xlsx_util.read_safe_upload(file)
    rows = svc.choice_import_read(round_id, content)
    dry = svc.choice_import_dry_run(round_id, rows, {
        "fileName": file.filename or "upload.xlsx",
        "fileSha256": hashlib.sha256(content).hexdigest(),
        "batchScope": f"round:{round_id}",
    })
    return success({"rows": rows, **dry})


@router.post("/gd-topic-rounds/{round_id}/choices/import/errors-xlsx", summary="选题志愿·下载错误行 Excel")
def gd_topic_choice_import_errors(round_id: str, body: ExcelErrorRows, user=Depends(get_current_user)):
    return success(svc.choice_import_errors_pack(round_id, body.rows, [e.model_dump() for e in body.errors]))


@router.post("/gd-topic-rounds/{round_id}/choices/import/dry-run", summary="选题志愿·预校验（粘贴行）")
def gd_topic_choice_import_dry_run(round_id: str, body: ExcelImportRows, user=Depends(get_current_user)):
    return success(svc.choice_import_dry_run(round_id, body.rows, {
        "fileName": "manual-input",
        "fileSha256": "",
        "batchScope": f"round:{round_id}",
    }))


@router.post("/gd-topic-rounds/{round_id}/choices/import/confirm", summary="选题志愿·确认导入")
def gd_topic_choice_import_confirm(round_id: str, body: ExcelImportRows, user=Depends(get_current_user)):
    result = svc.choice_import_confirm(round_id, body.rows, body.previewToken)
    audit_log.record("导入选题志愿", f"graduation-topic-round:{round_id}", detail=result)
    return success(result, message="导入完成")


@router.post("/gd-topic-rounds/{round_id}/choices/export", summary="选题志愿台账导出 Excel（写审计）")
def gd_topic_choices_export(round_id: str, matchedOnly: Optional[bool] = None, user=Depends(get_current_user)):
    data = svc.export_choices_xlsx(round_id, matched_only=bool(matchedOnly))
    audit_log.record("导出选题志愿台账", f"graduation-topic-round:{round_id}", detail={"rowCount": data["rowCount"]})
    return success(data)


@router.post("/gd-topic-rounds/{round_id}/open", summary="开启轮次")
def open_gd_topic_round(round_id: str, user=Depends(get_current_user)):
    result = svc.open_round(round_id)
    audit_log.record("开启选题轮次", f"graduation-topic-round:{round_id}")
    return success(result, message="已开启")


@router.post("/gd-topic-rounds/{round_id}/close", summary="关闭轮次")
def close_gd_topic_round(round_id: str, user=Depends(get_current_user)):
    result = svc.close_round(round_id)
    audit_log.record("关闭选题轮次", f"graduation-topic-round:{round_id}")
    return success(result, message="已关闭")


@router.get("/gd-topic-rounds/{round_id}/choices", summary="轮次志愿列表")
def gd_topic_round_choices(round_id: str, gdStudentId: Optional[str] = None, user=Depends(get_current_user)):
    return success(svc.list_choices(round_id, gd_student_id=gdStudentId))


@router.post("/gd-topic-rounds/{round_id}/choices", summary="提交选题志愿")
def submit_gd_topic_choices(round_id: str, body: GdTopicChoiceSubmit, user=Depends(get_current_user)):
    choices = [c.model_dump() for c in body.choices]
    result = svc.submit_choices(round_id, body.gdStudentId, choices)
    audit_log.record("提交选题志愿", f"graduation-topic-round:{round_id}", detail=result)
    return success(result, message="志愿已提交")


@router.post("/gd-topic-rounds/{round_id}/match", summary="执行志愿匹配（贪心分配）")
def match_gd_topic_round(round_id: str, user=Depends(get_current_user)):
    result = svc.match_round(round_id)
    audit_log.record("选题轮次匹配", f"graduation-topic-round:{round_id}", detail=result)
    return success(result, message=f"已匹配 {result.get('matched', 0)} 人")


@router.get("/gd-topic-rounds/{round_id}/choices/pending", summary="待确认志愿（教师/管理员人工复核用）")
def gd_topic_round_choices_pending(round_id: str, user=Depends(get_current_user)):
    all_choices = svc.list_choices(round_id)
    return success([c for c in all_choices if c["status"] == "PENDING"])


@router.post("/gd-topic-rounds/choices/{choice_id}/confirm",
             summary="确认志愿（人工一对一，落定分配+自动关闭该生同轮次其余待处理志愿，写审计）")
def confirm_gd_topic_choice(choice_id: str, user=Depends(get_current_user)):
    result = svc.confirm_choice(choice_id, operator_name=(user or {}).get("realName", "管理员"))
    audit_log.record("确认选题志愿", f"graduation-topic-choice:{choice_id}", detail=result)
    return success(result, message="已确认")


@router.post("/gd-topic-rounds/choices/{choice_id}/reject", summary="驳回志愿（不落定分配，写审计）")
def reject_gd_topic_choice(choice_id: str, body: GdTopicChoiceReview, user=Depends(get_current_user)):
    result = svc.reject_choice(choice_id, body.reason or "", operator_name=(user or {}).get("realName", "管理员"))
    audit_log.record("驳回选题志愿", f"graduation-topic-choice:{choice_id}", detail={"reason": body.reason})
    return success(result, message="已驳回")


@router.get("/gd-topic-rounds/{round_id}/capacity-conflicts", summary="容量冲突人工复核（过热题目+竞争学生）")
def gd_topic_round_capacity_conflicts(round_id: str, user=Depends(get_current_user)):
    return success({"items": svc.list_capacity_conflicts(round_id)})


@router.get("/gd-topic-rounds/{round_id}/stats", summary="选题统计（志愿状态分布/参与学生/过热题目）")
def gd_topic_round_stats(round_id: str, user=Depends(get_current_user)):
    return success(svc.round_stats(round_id))


@router.post("/gd-topic-rounds/{round_id}/archive", summary="选题归档（已关闭/已匹配轮次归档）")
def gd_topic_round_archive(round_id: str, user=Depends(get_current_user)):
    result = svc.archive_round(round_id)
    audit_log.record("归档选题轮次", f"graduation-topic-round:{round_id}")
    return success(result, message="已归档")


@router.post("/gd-topic-rounds/{round_id}/choices/withdraw", summary="退选（管理员代学生撤回本轮全部待处理志愿）")
def gd_topic_round_withdraw(round_id: str, gdStudentId: str, user=Depends(get_current_user)):
    result = svc.withdraw_choices(round_id, gdStudentId)
    audit_log.record("退选选题志愿", f"graduation-topic-round:{round_id}", detail={"gdStudentId": gdStudentId})
    return success(result, message="已退选")
