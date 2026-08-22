"""PLAT-05 production mutation endpoints.

Mounted before the broader Platform P1 router so these exact write signatures win. Reads
and health-score computation stay in platform_p1_closure/customer_health_service.
"""
from __future__ import annotations

from fastapi import APIRouter, Body, Depends

from app.api.v1.platform_p1_closure import _ensure_tenant, _utc_naive, require_platform_capability
from app.core.exceptions import AppException
from app.core.response import success

router = APIRouter(prefix="/platform", tags=["平台总控·客户成功生产写入"])


@router.post("/support-tickets", summary="创建客户成功工单（事务审计）")
def support_ticket_create(
    body: dict = Body(...),
    user=Depends(require_platform_capability("customerSuccess.manage")),
):
    from app.services import customer_success_p1_guard_service as guard

    try:
        tenant_id = int((body or {}).get("tenantId") or 0)
    except (TypeError, ValueError):
        raise AppException("VALIDATION_ERROR", "tenantId 必须是正整数") from None
    if tenant_id <= 0:
        raise AppException("VALIDATION_ERROR", "必须指定 tenantId")
    _ensure_tenant(tenant_id)
    return success(guard.create_ticket(
        tenant_id=tenant_id,
        title=(body or {}).get("title") or "",
        description=(body or {}).get("description") or "",
        severity=str((body or {}).get("severity") or "P2").upper(),
        reporter_name=(body or {}).get("reporterName") or "",
        user=user,
    ), message="工单已创建")


@router.post("/support-tickets/{ticket_id}/transition", summary="流转客户工单（行锁+状态机+事务审计）")
def support_ticket_transition(
    ticket_id: int,
    body: dict = Body(...),
    user=Depends(require_platform_capability("customerSuccess.manage")),
):
    from app.services import customer_success_p1_guard_service as guard

    return success(guard.transition_ticket(
        ticket_id,
        status=str((body or {}).get("status") or "").upper(),
        resolution_note=(body or {}).get("resolutionNote") or "",
        expected_version=(body or {}).get("expectedVersion"),
        user=user,
    ), message="工单状态已更新")


@router.post("/trainings", summary="登记客户培训计划（UTC+事务审计）")
def training_create(
    body: dict = Body(...),
    user=Depends(require_platform_capability("customerSuccess.manage")),
):
    from app.services import customer_success_p1_guard_service as guard

    try:
        tenant_id = int((body or {}).get("tenantId") or 0)
    except (TypeError, ValueError):
        raise AppException("VALIDATION_ERROR", "tenantId 必须是正整数") from None
    if tenant_id <= 0:
        raise AppException("VALIDATION_ERROR", "必须指定 tenantId")
    _ensure_tenant(tenant_id)
    return success(guard.create_training(
        tenant_id=tenant_id,
        topic=(body or {}).get("topic") or "",
        scheduled_at=_utc_naive((body or {}).get("scheduledAt"), "scheduledAt"),
        trainer_name=(body or {}).get("trainerName") or "",
        user=user,
    ), message="培训计划已登记")


@router.post("/trainings/{training_id}/complete", summary="完成客户培训（行锁+事务审计）")
def training_complete(
    training_id: int,
    body: dict = Body(...),
    user=Depends(require_platform_capability("customerSuccess.manage")),
):
    from app.services import customer_success_p1_guard_service as guard

    return success(guard.complete_training(
        training_id,
        attendee_count=(body or {}).get("attendeeCount"),
        note=(body or {}).get("note") or "",
        expected_version=(body or {}).get("expectedVersion"),
        user=user,
    ), message="培训已标记完成")


@router.post("/renewal-tasks", summary="创建续费跟进（UTC+事务审计）")
def renewal_create(
    body: dict = Body(...),
    user=Depends(require_platform_capability("customerSuccess.manage")),
):
    from app.services import customer_success_p1_guard_service as guard

    try:
        tenant_id = int((body or {}).get("tenantId") or 0)
    except (TypeError, ValueError):
        raise AppException("VALIDATION_ERROR", "tenantId 必须是正整数") from None
    if tenant_id <= 0:
        raise AppException("VALIDATION_ERROR", "必须指定 tenantId")
    _ensure_tenant(tenant_id)
    return success(guard.create_renewal_task(
        tenant_id=tenant_id,
        due_at=_utc_naive((body or {}).get("dueAt"), "dueAt"),
        owner_name=(body or {}).get("ownerName") or "",
        note=(body or {}).get("note") or "",
        user=user,
    ), message="续费任务已创建")


@router.post("/renewal-tasks/{task_id}/transition", summary="流转续费任务（行锁+终态不可逆+事务审计）")
def renewal_transition(
    task_id: int,
    body: dict = Body(...),
    user=Depends(require_platform_capability("customerSuccess.manage")),
):
    from app.services import customer_success_p1_guard_service as guard

    return success(guard.transition_renewal_task(
        task_id,
        status=str((body or {}).get("status") or "").upper(),
        note=(body or {}).get("note") or "",
        expected_version=(body or {}).get("expectedVersion"),
        user=user,
    ), message="续费任务状态已更新")
