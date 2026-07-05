"""通知中心 API（/api/v1/notification/*）。教职工可用；短信默认关闭（记录 SKIPPED）。"""
from __future__ import annotations

from fastapi import APIRouter, Body, Depends

from app.core.response import success
from app.core.security import require_staff
from app.db.session import db_enabled, get_sessionmaker
from app.services.db_service import _iso, _tid
from app.services.notification import send_sms

router = APIRouter(prefix="/notification", tags=["通知中心"])


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
