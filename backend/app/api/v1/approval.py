"""审批任务 API：正式路由只连接真实数据库服务。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Header, Query

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
from app.services import approval_export_service as exportsvc
from app.services import approval_returned_service as returnedsvc
from app.services import approval_runtime_service as runtime
from app.services import approval_template_service as adminsvc

router = APIRouter(prefix="/approvals", tags=["approvals"])


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


@router.get("/biz-types", summary="审批业务类型字典（TP-A10：服务端唯一权威）")
def approval_biz_types(user=Depends(require_staff)):
    return success(runtime.biz_type_options())


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
    actedFrom: str | None = Query(None, max_length=10),
    actedTo: str | None = Query(None, max_length=10),
    user=Depends(require_staff),
):
    items, total = runtime.list_processed(
        page, pageSize, user=user, keyword=keyword, biz_type=bizType, result=result,
        acted_from=actedFrom, acted_to=actedTo,
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


@router.get("/tasks/{task_id}/next", summary="按当前筛选队列取真实下一条待办（服务端 seek）")
def next_todo(
    task_id: str,
    keyword: str | None = Query(None, max_length=100),
    bizType: str | None = Query(None, max_length=100),
    urgency: str | None = Query(None, max_length=30),
    submitDate: str | None = Query(None, max_length=10),
    user=Depends(require_staff),
):
    # P2-03：anchor 是 seek 的安全边界，不是可选提示。
    # 它此刻可以已经办结，所以只按 get_task 的“存在 + 当前调用者可见”合同校验，
    # 不要求仍是 PENDING；非法、缺失、他人任务统一 404。绝不把无效 anchor
    # 当成 None 后退化成“返回队首第一条”，否则可被构造为越权队列探测器。
    runtime.get_task(task_id, user=user)
    return success(runtime.next_task(
        task_id, user=user, keyword=keyword, biz_type=bizType,
        urgency=urgency, submit_date=submitDate,
    ))


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
    # TP-A07：sourceVersion 是批次业务语义的一部分，必须进入幂等指纹。
    # 否则同一 Idempotency-Key 在源事实版本变化后仍可能命中旧指纹/旧结果，掩盖版本冲突。
    payload = {
        "action": body.action,
        "items": [{
            "taskId": x.taskId,
            "version": x.version,
            "expectedSourceVersion": x.expectedSourceVersion,
        } for x in body.items],
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


@router.get("/tasks/{task_id}", summary="审批任务详情与真实时间线")
def get_task(task_id: str, user=Depends(require_staff)):
    return success(runtime.get_task(task_id, user=user))


@router.post("/tasks/{task_id}/approve", summary="通过（真实状态机 + 审计）")
def approve(task_id: str, body: ApprovalActionRequest, user=Depends(require_staff)):
    return success(
        runtime.approve(task_id, body.comment, user=user, version=body.version,
                        expected_source_version=body.expectedSourceVersion),
        message="已通过",
    )


@router.post("/tasks/{task_id}/return", summary="退回（按业务域策略重提或终止）")
def return_for_revision(
    task_id: str,
    body: ApprovalReturnRequest,
    user=Depends(require_staff),
):
    result = runtime.return_for_revision(
        task_id, body.reason, user=user, version=body.version,
        expected_source_version=body.expectedSourceVersion,
    )

    # W2：runtime 的基础返回值描述的是通用“可重提”策略，但领域回调可能在同一事务
    # 把实例收成真正终态（如 EMPLOYMENT_DESTINATION）。动作提交后回读权威状态，响应
    # 必须与已提交数据库事实一致；只有实例仍处于 APPLICANT_RESUBMIT 才暴露 nextTodo。
    actual = runtime.get_task(task_id, user=user)
    actual_status = str(actual.get("instanceStatus") or result.get("instanceStatus") or "")
    actual_node = str(actual.get("currentInstanceNode") or "")
    result["instanceStatus"] = actual_status
    if actual_status.upper() != "RUNNING" or actual_node.upper() != "APPLICANT_RESUBMIT":
        result["nextTodo"] = None
    return success(result, message="已退回")


@router.post("/tasks/{task_id}/reject", summary="驳回终止（不可重提原流程）")
def reject(task_id: str, body: ApprovalRejectRequest, user=Depends(require_staff)):
    return success(
        runtime.reject(task_id, body.reason, user=user, version=body.version,
                       expected_source_version=body.expectedSourceVersion),
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
    actedFrom: str | None = Query(None, max_length=10),
    actedTo: str | None = Query(None, max_length=10),
    user=Depends(require_staff),
):
    items, total = runtime.list_processed(
        page, pageSize, user=user, keyword=keyword, biz_type=bizType, result=result,
        acted_from=actedFrom, acted_to=actedTo,
    )
    return success(paginate(items, total, page, pageSize))