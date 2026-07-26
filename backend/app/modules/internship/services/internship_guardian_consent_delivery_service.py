"""监护人知情确认任务创建、token轮换与短信送达。

生产环境不向管理端返回明文token。确认链接只发往已绑定、已验证的监护人手机号；
门户地址、短信开关或模板未配置时明确返回 SKIPPED，不伪装成已送达。
"""
from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta
from urllib.parse import quote

from sqlalchemy import select

from app.core.config import settings
from app.core.exceptions import AppException, no_permission, not_found
from app.core.field_crypto import decrypt_field
from app.models import (
    InternshipConsent, InternshipRecord, StudentParentLink, StudentProfile,
)
from app.modules.internship.services import internship_consent_service as consent
from app.services.db_service import _as_id, _tid, session
from app.services.notification import sms_service


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _portal_link(consent_id, token: str) -> str:
    base = str(settings.GUARDIAN_PORTAL_BASE_URL or "").strip().rstrip("/")
    if not base:
        return ""
    return (
        f"{base}/guardian?consentId={quote(str(consent_id))}"
        f"&token={quote(token)}"
    )


def _guardian_context(db, consent_row: InternshipConsent):
    record = db.get(InternshipRecord, consent_row.internship_id)
    student = db.get(StudentProfile, consent_row.student_id)
    link = db.scalar(select(StudentParentLink).where(
        StudentParentLink.id == consent_row.guardian_link_id,
        StudentParentLink.tenant_id == _tid(),
        StudentParentLink.student_id == consent_row.student_id,
        StudentParentLink.status == "ACTIVE",
    ))
    if not record or not student or not link:
        raise AppException(
            "DATA_CONFLICT", "监护人绑定关系已失效，请重新绑定后下发")
    try:
        phone = decrypt_field(link.phone_encrypted)
    except Exception as error:
        raise AppException(
            "DATA_CONFLICT", "监护人手机号无法解密，请管理员核对加密密钥") from error
    if not phone:
        raise AppException("DATA_CONFLICT", "监护人手机号缺失")
    return record, student, link, phone


def _record_delivery(consent_id, result: dict, user=None):
    with session() as db:
        row = db.scalar(select(InternshipConsent).where(
            InternshipConsent.id == _as_id(consent_id),
            InternshipConsent.tenant_id == _tid(),
            InternshipConsent.is_deleted.is_(False),
        ).with_for_update())
        if not row:
            return
        status = str(result.get("status") or "FAILED").upper()
        row.delivery_channel = "SMS" if status == "SENT" else f"SMS_{status}"
        row.delivery_message_id = str(
            result.get("requestId") or result.get("reason") or status)[:128]
        row.delivered_at = datetime.utcnow() if status == "SENT" else None
        row.version = int(row.version or 0) + 1
        consent._audit(db, row, f"GUARDIAN_DELIVERY_{status}", user, {
            "status": status,
            "reason": result.get("reason") or "",
            "requestId": result.get("requestId") or "",
            "contactMasked": row.contact_masked or "",
            "newVersion": int(row.version or 0),
        })
        db.commit()


def _send(row: InternshipConsent, token: str, user=None) -> dict:
    with session() as db:
        current = db.get(InternshipConsent, row.id)
        if not current or current.tenant_id != _tid() or current.is_deleted:
            raise not_found("监护人确认任务不存在")
        _record, student, link, phone = _guardian_context(db, current)
        confirm_link = _portal_link(current.id, token)
        if not confirm_link:
            result = {
                "status": "SKIPPED",
                "reason": "GUARDIAN_PORTAL_BASE_URL 未配置",
            }
        elif not str(settings.SMS_TEMPLATE_GUARDIAN_CONSENT or "").strip():
            result = {
                "status": "SKIPPED",
                "reason": "SMS_TEMPLATE_GUARDIAN_CONSENT 未配置",
            }
        else:
            result = sms_service.notify_guardian_consent(
                _tid(), phone, current.participant_name or link.parent_name,
                params={
                    "studentName": student.real_name,
                    "confirmLink": confirm_link,
                    "expiresHours": "24",
                })
    _record_delivery(row.id, result, user)
    response = {
        "deliveryStatus": result.get("status") or "FAILED",
        "deliveryReason": result.get("reason") or "",
        "contactMasked": row.contact_masked or "",
    }
    if not settings.is_prod:
        response["debugConfirmLink"] = _portal_link(row.id, token)
    return response


def create_and_deliver(body: dict, user=None) -> dict:
    result = consent.create_pending(body, user)
    token = result.pop("guardianConfirmToken", None)
    if str(result.get("consentType") or "").upper() != "GUARDIAN":
        return result
    if not token:
        raise AppException("SYSTEM_ERROR", "监护人确认token生成失败")
    row = InternshipConsent(id=_as_id(result["id"]))
    delivery = _send(row, token, user)
    result.update(delivery)
    # delivery写回会增加版本，返回最终版本而不是创建时旧版本。
    with session() as db:
        saved = db.get(InternshipConsent, _as_id(result["id"]))
        result["version"] = int(saved.version or 0) if saved else result.get("version", 0)
        result["deliveryChannel"] = saved.delivery_channel if saved else ""
        result["deliveredAt"] = saved.delivered_at if saved else None
    return result


def redeliver(consent_id, expected_version, user=None) -> dict:
    raw_token = secrets.token_urlsafe(32)
    with session() as db:
        row = db.scalar(select(InternshipConsent).where(
            InternshipConsent.id == _as_id(consent_id),
            InternshipConsent.tenant_id == _tid(),
            InternshipConsent.is_deleted.is_(False),
        ).with_for_update())
        if not row:
            raise not_found("监护人确认任务不存在")
        if row.consent_type != "GUARDIAN":
            raise AppException("VALIDATION_ERROR", "仅监护人确认任务可重新发送")
        if row.status != "PENDING":
            raise AppException("DATA_CONFLICT", "仅待确认任务可重新发送")
        if expected_version is None or int(expected_version) != int(row.version or 0):
            raise AppException("DATA_CONFLICT", "任务版本已变化，请刷新后重试")
        _guardian_context(db, row)
        row.guardian_token_hash = _token_hash(raw_token)
        row.guardian_token_nonce = secrets.token_hex(12)
        row.guardian_token_expires_at = datetime.utcnow() + timedelta(hours=24)
        row.guardian_token_used_at = None
        row.delivery_channel = None
        row.delivery_message_id = None
        row.delivered_at = None
        row.version = int(row.version or 0) + 1
        consent._audit(db, row, "GUARDIAN_TOKEN_ROTATE", user, {
            "expiresAt": row.guardian_token_expires_at.isoformat() + "Z",
            "newVersion": int(row.version or 0),
        })
        db.commit()
        row_id = row.id
    delivery = _send(InternshipConsent(id=row_id), raw_token, user)
    with session() as db:
        saved = db.get(InternshipConsent, row_id)
        return {
            "id": str(row_id), "status": saved.status,
            "version": int(saved.version or 0),
            "deliveryChannel": saved.delivery_channel or "",
            "deliveredAt": saved.delivered_at,
            **delivery,
        }
