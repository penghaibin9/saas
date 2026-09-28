"""Yiyang C07/G18 regulatory reporting API."""
from __future__ import annotations

from io import BytesIO

from fastapi import APIRouter, Body, Depends, Query
from fastapi.responses import StreamingResponse

from app.core.permissions import require_permission
from app.core.response import success
from app.modules.internship.services import internship_regulatory_reporting_service as svc

router = APIRouter(prefix="/internship/regulatory-reporting", tags=["岗位实习-监管上报"])

_VIEW = "internship.reporting.view"
_MANAGE = "internship.reporting.manage"
_EXPORT = "internship.reporting.export"


@router.get("/templates", summary="两套监管上报模板版本")
def templates(reportCode: str | None = Query(None), user=Depends(require_permission(_VIEW))):
    return success(svc.list_templates(reportCode))


@router.post("/templates/{report_code}/versions", summary="创建新的学校确认模板版本")
def template_version(report_code: str, body: dict = Body(...),
                     user=Depends(require_permission(_MANAGE))):
    return success(
        svc.create_template_version(report_code, body or {}, user=user),
        message="模板版本已创建",
    )


@router.get("/tasks", summary="监管上报任务")
def tasks(reportCode: str | None = Query(None), batchId: int | None = Query(None, ge=1),
          user=Depends(require_permission(_VIEW))):
    return success(svc.list_tasks(reportCode, batchId))


@router.post("/tasks", summary="按批次冻结事实并生成上报任务")
def task_create(body: dict = Body(...), user=Depends(require_permission(_MANAGE))):
    return success(svc.create_task(body or {}, user=user), message="上报任务已生成")


@router.get("/tasks/{task_id}", summary="监管上报任务详情")
def task_detail(task_id: int, user=Depends(require_permission(_VIEW))):
    return success(svc.task_detail(task_id))


@router.post("/tasks/{task_id}/validate", summary="执行必填/枚举/跨字段校验")
def task_validate(task_id: int, user=Depends(require_permission(_MANAGE))):
    return success(svc.validate_task(task_id, user=user), message="校验完成")


@router.get("/tasks/{task_id}/errors.xlsx", summary="导出错误行 Excel")
def task_errors(task_id: int, user=Depends(require_permission(_EXPORT))):
    payload, filename = svc.error_file(task_id, user=user)
    return StreamingResponse(
        BytesIO(payload),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/tasks/{task_id}/export.xlsx", summary="生成正式上报 Excel")
def task_export(task_id: int, user=Depends(require_permission(_EXPORT))):
    payload, filename = svc.export_file(task_id, user=user)
    return StreamingResponse(
        BytesIO(payload),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/tasks/{task_id}/external-submission", summary="登记真实外部提交并进入待回执")
def task_submitted(task_id: int, body: dict = Body(...),
                   user=Depends(require_permission(_MANAGE))):
    return success(
        svc.mark_submitted(task_id, body or {}, user=user),
        message="已登记外部提交，等待真实平台回执",
    )


@router.post("/tasks/{task_id}/receipt", summary="接收真实监管平台回执（未装配时硬阻断）")
def task_receipt(task_id: int, body: dict = Body(...),
                 user=Depends(require_permission(_MANAGE))):
    return success(svc.record_external_receipt(task_id, body or {}, user=user))
