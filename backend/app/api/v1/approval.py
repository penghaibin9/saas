"""审批任务 API：正式路由只连接真实数据库服务。"""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, Header, Query
from pydantic import BaseModel

from app.api.v1.file_contract import validated_local_file_response
from app.core.exceptions import AppException
from app.core.idempotency import idempotency_guard
from app.core.response import paginate, success
from app.core.security import get_current_user, require_staff
from app.schemas.approval import (
    ApprovalActionRequest,
    ApprovalBatchRequest,
    ApprovalExportRequest,
    ApprovalExportTicketRequest,
    ApprovalRejectRequest,
    ApprovalResubmitRequest,
    ApprovalReturnRequest,
    ApprovalTemplateCreateRequest,
    ApprovalTemplateUpdateRequest,
    ApprovalTemplateVoidRequest,
    ApprovalTransferRequest,
)
from app.services import approval_attachment_preview_service as attachmentsvc
from app.services import approval_export_service as exportsvc
from app.services import approval_returned_service as returnedsvc
from app.services import approval_runtime_service as runtime
from app.services import approval_template_service as adminsvc

router = APIRouter(prefix="/approvals", tags=["approvals"])


class ApprovalAttachmentTicketRequest(BaseModel):
    action: Literal["preview", "download"]


def _require_idempotency_key(value: str | None) -> str:
    key = str(value or "").strip()
    if not key:
        raise AppException(
            "VALIDATION_ERROR",
            "Idempotency-Key 必填，关键批量/导出操作禁止无幂等保护执行",
            http_status=400,
        )
    return key


@router.get("/summary", summary="审批中心待办统计（真实服务端）")
def approval_summary(user=Depends(require_staff)):
    return success(runtime.summary(user=user))


@router.get("/tasks", summary="待我审批任务列表")
def list_tasks(
    page: int = Query(1, ge=1),
    pageSize: int = Query(20, ge=1, le=200),
    keyword: str | None = Query(None, max_length=100),
    bizType: str | None = Query(None, max_length=100),
    urgency: str | None = Query(None, max_length=30),
    submitDate: str | None = Query(None, max_length=10),
    user=Depends(require_staff),
):
    items, total = runtime.list_tasks(
        page,
        pageSize,
        user=user,
        keyword=keyword,
        biz_type=bizType,
        urgency=urgency,
        submit_date=submitDate,
    )
    return success(paginate(items, total, page, pageSize))


@router.get("/tasks/summary/by-biz-type", summary="待办按业务类型分组统计")
def tasks_by_biz_type(user=Depends(require_staff)):
    return success(runtime.summary(user=user).get("byBizType", []))


@router.get("/tasks/done", summary="已办列表（真实分页）")
def done_tasks(
    page: int = Query(1, ge=1),
    pageSize: int = Query(20, ge=1, le=200),
    keyword: str | None = Query(None, max_length=100),
    bizType: str | None = Query(None, max_length=100),
    result: str | None = Query(None, max_length=30),
    user=Depends(require_staff),
):
    items, total = runtime.list_processed(
        page, pageSize, user=user, keyword=keyword, biz_type=bizType, result=result
    )
    return success(paginate(items, total, page, pageSize))


@router.get("/tasks/returned", summary="本人退回记录（真实整改状态）")
def returned_tasks(
    page: int = Query(1, ge=1),
    pageSize: int = Query(20, ge=1, le=200),
    keyword: str | None = Query(None, max_length=100),
    rectifyStatus: str | None = Query(None, max_length=30),
    user=Depends(require_staff),
):
    items, total = returnedsvc.list_returned(
        page, pageSize, user=user, keyword=keyword, rectify_status=rectifyStatus
    )
    return success(paginate(items, total, page, pageSize))


@router.get("/tasks/{task_id}/transfer-targets", summary="当前任务可转办教职工")
def transfer_targets(task_id: str, user=Depends(require_staff)):
    return success(runtime.transfer_targets(task_id, user=user))


@router.get("/templates", summary="审批模板列表（真实流程定义）")
def templates(
    page: int = Query(1, ge=1),
    pageSize: int = Query(20, ge=1, le=100),
    keyword: str | None = Query(None, max_length=100),
    bizType: str | None = Query(None, max_length=100),
    status: str | None = Query(None, max_length=30),
    user=Depends(require_staff),
):
    items, total = adminsvc.list_templates(
        page, pageSize, user=user, keyword=keyword, biz_type=bizType, status=status
    )
    return success(paginate(items, total, page, pageSize))


@router.post("/templates", summary="新增审批模板")
def create_template(body: ApprovalTemplateCreateRequest, user=Depends(require_staff)):
    return success(adminsvc.create_template(body.model_dump(), user=user), message="模板已新增")


@router.put("/templates/{template_id}", summary="更新审批模板（乐观锁）")
def update_template(
    template_id: str,
    body: ApprovalTemplateUpdateRequest,
    user=Depends(require_staff),
):
    payload = body.model_dump(exclude={"version"})
    return success(
        adminsvc.update_template(template_id, payload, user=user, expected_version=body.version),
        message="模板已更新",
    )


@router.post("/templates/{template_id}/void", summary="作废审批模板（乐观锁）")
def void_template(
    template_id: str,
    body: ApprovalTemplateVoidRequest,
    user=Depends(require_staff),
):
    return success(
        adminsvc.void_template(
            template_id, body.reason, user=user, expected_version=body.version
        ),
        message="模板已作废",
    )


@router.get("/audit", summary="审批中心真实审计留痕")
def approval_audit(
    limit: int = Query(20, ge=1, le=50),
    user=Depends(require_staff),
):
    return success(runtime.approval_audit(user=user, limit=limit))


@router.get("/cc", summary="抄送我的（真实消息中心）")
def cc(
    page: int = Query(1, ge=1),
    pageSize: int = Query(20, ge=1, le=200),
    keyword: str | None = Query(None, max_length=100),
    readStatus: str | None = Query(None, max_length=30),
    user=Depends(require_staff),
):
    items, total = runtime.list_cc(
        page, pageSize, user=user, keyword=keyword, read_status=readStatus
    )
    return success(paginate(items, total, page, pageSize))


@router.post("/batch", summary="批量审批（逐条结果，可部分失败）")
def batch_process(
    body: ApprovalBatchRequest,
    user=Depends(require_staff),
    idempotency_key: str | None = Header(None, alias="Idempotency-Key"),
):
    idempotency_key = _require_idempotency_key(idempotency_key)
    payload = {
        "action": body.action,
        "items": [{"taskId": x.taskId, "version": x.version} for x in body.items],
        "targetUserId": body.targetUserId,
        "reason": body.reason,
        "comment": body.comment,
    }
    with idempotency_guard(
        user,
        "approval-batch",
        idempotency_key,
        payload,
        require_store=True,
    ) as guard:
        if guard.cached is not None:
            return success(guard.cached, message="批量处理完成（幂等重放）")
        result = runtime.batch_process(
            [x.model_dump() for x in body.items],
            body.action,
            user=user,
            reason=body.reason,
            target_user_id=body.targetUserId,
            comment=body.comment,
        )
        guard.success(result)
        return success(result, message="批量处理完成")


@router.post("/export", summary="创建审批中心异步 xlsx 导出任务")
def create_export(
    body: ApprovalExportRequest,
    user=Depends(require_staff),
    idempotency_key: str | None = Header(None, alias="Idempotency-Key"),
):
    idempotency_key = _require_idempotency_key(idempotency_key)
    with idempotency_guard(
        user,
        "approval-export",
        idempotency_key,
        {"scope": body.scope, "purpose": body.purpose},
        require_store=True,
    ) as guard:
        if guard.cached is not None:
            return success(guard.cached, message="导出任务已存在（幂等重放）")
        result = exportsvc.create_job(body.scope, body.purpose, user=user)
        guard.success(result)
        return success(result, message="导出任务已创建")


@router.get("/export/{task_id}", summary="查询审批中心导出任务状态")
def export_status(task_id: str, user=Depends(require_staff)):
    return success(exportsvc.get_job(task_id, user=user))


@router.post("/export/{task_id}/download-ticket", summary="创建审批导出一次性下载票据")
def export_download_ticket(
    body: ApprovalExportTicketRequest,
    task_id: str,
    user=Depends(require_staff),
):
    return success(
        exportsvc.create_download_ticket(task_id, body.expectedVersion, user=user)
    )


@router.get("/export/{task_id}/download", summary="使用一次性票据下载审批中心 xlsx")
def download_export(
    task_id: str,
    ticket: str = Query(..., min_length=20),
    user=Depends(require_staff),
):
    path, filename = exportsvc.consume_download_ticket(task_id, ticket, user=user)
    return validated_local_file_response(
        path,
        filename=filename,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        audit_action="APPROVAL_EXPORT_DOWNLOAD",
        audit_target=f"approval-export:{task_id}",
        audit_detail={"taskId": task_id},
    )


@router.get("/tasks/{task_id}/attachments", summary="审批任务附件清单（任务范围 + 文件中心安全态）")
def approval_attachments(task_id: str, user=Depends(require_staff)):
    return success({"items": attachmentsvc.list_attachments(task_id, user)})


@router.post("/tasks/{task_id}/files/{file_id}/ticket", summary="签发审批附件预览/下载短时票据")
def approval_attachment_ticket(
    task_id: str,
    file_id: int,
    body: ApprovalAttachmentTicketRequest,
    user=Depends(require_staff),
):
    return success(attachmentsvc.issue_ticket(task_id, file_id, body.action, user))


@router.get("/tasks/{task_id}/files/{file_id}/preview", summary="使用任务票据读取审批附件")
def preview_approval_attachment(
    task_id: str,
    file_id: int,
    ticket: str = Query(..., min_length=20),
    user=Depends(require_staff),
):
    path, filename, mime_type = attachmentsvc.consume_ticket(task_id, file_id, "preview", ticket, user)
    return validated_local_file_response(
        path,
        filename=filename,
        inline=True,
        media_type=mime_type,
        audit_action="APPROVAL_ATTACHMENT_PREVIEW",
        audit_target=f"approval-task:{task_id}:file:{file_id}",
        audit_detail={"taskId": task_id, "fileId": str(file_id)},
    )


@router.get("/tasks/{task_id}/files/{file_id}/download", summary="使用一次性任务票据下载审批附件")
def download_approval_attachment(
    task_id: str,
    file_id: int,
    ticket: str = Query(..., min_length=20),
    user=Depends(require_staff),
):
    path, filename, mime_type = attachmentsvc.consume_ticket(task_id, file_id, "download", ticket, user)
    return validated_local_file_response(
        path,
        filename=filename,
        media_type=mime_type,
        audit_action="APPROVAL_ATTACHMENT_DOWNLOAD",
        audit_target=f"approval-task:{task_id}:file:{file_id}",
        audit_detail={"taskId": task_id, "fileId": str(file_id)},
    )


@router.get("/tasks/{task_id}", summary="审批任务详情与真实时间线")
def get_task(task_id: str, user=Depends(require_staff)):
    return success(runtime.get_task(task_id, user=user))


@router.post("/tasks/{task_id}/approve", summary="通过（真实状态机 + 审计）")
def approve(task_id: str, body: ApprovalActionRequest, user=Depends(require_staff)):
    return success(
        runtime.approve(task_id, body.comment, user=user, version=body.version),
        message="已通过",
    )


@router.post("/tasks/{task_id}/return", summary="退回修改（可修改后重提）")
def return_for_revision(
    task_id: str,
    body: ApprovalReturnRequest,
    user=Depends(require_staff),
):
    return success(
        runtime.return_for_revision(task_id, body.reason, user=user, version=body.version),
        message="已退回修改",
    )


@router.post("/tasks/{task_id}/reject", summary="驳回终止（不可重提原流程）")
def reject(task_id: str, body: ApprovalRejectRequest, user=Depends(require_staff)):
    return success(
        runtime.reject(task_id, body.reason, user=user, version=body.version),
        message="已驳回并终止",
    )


@router.post("/tasks/{task_id}/transfer", summary="转办（旧任务留痕，新任务交目标办理人）")
def transfer(task_id: str, body: ApprovalTransferRequest, user=Depends(require_staff)):
    return success(
        runtime.transfer(
            task_id,
            body.targetUserId,
            body.comment,
            user=user,
            version=body.version,
        ),
        message="已转办",
    )


@router.post("/instances/{instance_id}/resubmit", summary="申请人修改后重新提交")
def resubmit(
    instance_id: str,
    body: ApprovalResubmitRequest,
    user=Depends(get_current_user),
):
    return success(
        runtime.resubmit(
            instance_id, user=user, version=body.version, comment=body.comment
        ),
        message="已重新提交",
    )


# 兼容旧正式路径；内部仍走同一真实查询，不再维护第二套历史台账。
@router.get("/processed", summary="已办列表（兼容路径）")
def processed(
    page: int = Query(1, ge=1),
    pageSize: int = Query(20, ge=1, le=200),
    keyword: str | None = Query(None, max_length=100),
    bizType: str | None = Query(None, max_length=100),
    result: str | None = Query(None, max_length=30),
    user=Depends(require_staff),
):
    items, total = runtime.list_processed(
        page, pageSize, user=user, keyword=keyword, biz_type=bizType, result=result
    )
    return success(paginate(items, total, page, pageSize))
