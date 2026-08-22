"""通知中心 API（/api/v1/notification/*）。

教职工通知仍使用既有持久化短信编排；官网 website-lead 是匿名公开入口，
只做校验/防滥用并把本次表单直接短信转发给商务联系人，不写销售线索或通知日志表。
"""
from __future__ import annotations

from fastapi import APIRouter, Body, Depends, HTTPException, Request

from app.core.context import get_request_meta
from app.core.response import success
from app.core.security import require_staff
from app.db.session import db_enabled, get_sessionmaker
from app.services.db_service import _iso, _tid
from app.services.notification import send_sms
from app.services.notification.website_lead import (
    WebsiteLeadRequest,
    allow_website_lead,
    send_website_lead_sms,
)

router = APIRouter(prefix="/notification", tags=["通知中心"])


@router.post("/website-lead", summary="官网商务咨询：短信通知跃科，不落业务数据库")
def website_lead(body: WebsiteLeadRequest, request: Request):
    # 蜜罐命中时对机器人仍返回通用成功，避免暴露反滥用策略；不会发送短信。
    if body.website:
        return success({"accepted": True})

    request_meta = get_request_meta()
    client_ip = str(request_meta.get("ip") or (request.client.host if request.client else "") or "unknown")
    allowed, reason = allow_website_lead(client_ip)
    if not allowed:
        if reason == "RATE_LIMITED":
            raise HTTPException(status_code=429, detail="提交过于频繁，请稍后再试或直接电话联系")
        raise HTTPException(status_code=503, detail="在线咨询暂时不可用，请直接电话联系 135 4966 6867")

    result = send_website_lead_sms(body)
    if result.get("status") == "SENT":
        return success({"accepted": True})
    if result.get("status") == "IGNORED_BOT":
        return success({"accepted": True})
    raise HTTPException(status_code=503, detail="在线咨询暂时不可用，请直接电话联系 135 4966 6867")


@router.post("/send-test", summary="发送测试短信（受 SMS_ENABLED 控制，默认只记录不发）")
def send_test(body: dict = Body(...), user=Depends(require_staff)):
    r = send_sms(_tid(), body.get("phone"), body.get("templateCode", "TODO"),
                 body.get("params") or {}, body.get("bizType", "TODO"), body.get("name"))
    return success(r)


@router.get("/logs", summary="通知发送日志（本租户，手机号脱敏）")
def logs(user=Depends(require_staff)):
    if not db_enabled():
        return success({"list": [], "note": "演示模式"})
    from sqlalchemy import select

    from app.models import NotificationLog
    db = get_sessionmaker()()
    try:
        rows = db.scalars(select(NotificationLog).where(
            NotificationLog.tenant_id == _tid()).order_by(NotificationLog.id.desc()).limit(100)).all()
        return success({"list": [{"id": str(r.id), "bizType": r.biz_type, "provider": r.provider,
                                  "phoneMasked": r.phone_masked, "result": r.result,
                                  "reason": r.reason, "sentAt": _iso(r.sent_at)} for r in rows]})
    finally:
        db.close()
