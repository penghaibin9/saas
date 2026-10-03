"""岗位实习监护人知情确认创建与重新送达。"""
from fastapi import APIRouter, Body, Depends

from app.core.permissions import require_permission
from app.core.response import success
from app.modules.internship.services import (
    internship_guardian_consent_delivery_service as delivery,
)

router = APIRouter(
    prefix="/internship/compliance/consents",
    tags=["岗位实习·监护人知情送达"],
)


@router.post("/deliver")
def create_and_deliver(
    body: dict = Body(...),
    user=Depends(require_permission("internship.consent.manage")),
):
    result = delivery.create_and_deliver(body or {}, user)
    message = "知情确认任务已创建"
    if result.get("consentType") == "GUARDIAN":
        status = result.get("deliveryStatus")
        message = "监护人确认链接已发送" if status == "SENT" else "监护人任务已创建，但短信未送达"
    return success(result, message=message)


@router.post("/{consent_id}/redeliver")
def redeliver(
    consent_id: str,
    body: dict = Body(...),
    user=Depends(require_permission("internship.consent.manage")),
):
    result = delivery.redeliver(
        consent_id, (body or {}).get("expectedVersion"), user)
    return success(
        result,
        message="监护人确认链接已重新发送"
        if result.get("deliveryStatus") == "SENT"
        else "已轮换确认链接，但短信未送达",
    )
