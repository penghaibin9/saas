"""监护人知情确认任务创建、一次性链接轮换与短信送达。

约束：
- 只使用现有 InternshipConsent / StudentParentLink 字段，不依赖未迁移列；
- 监护人通过手机号 hash 前缀与知情任务绑定，手机号只在服务端解密后用于短信；
- 生产响应不返回明文 token/链接；短信未配置或发送失败时明确记录，不伪装已送达；
- 重复下发同一正文时轮换旧 token，旧链接立即失效。
"""
from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta
from urllib.parse import quote

from sqlalchemy import select

from app.core.config import settings
from app.core.exceptions import AppException, not_found
from app.core.field_crypto import decrypt_field
from app.models import (
    InternshipConsent, InternshipRecord, StudentParentLink, StudentProfile,
)
from app.modules.internship.services import internship_consent_service as consent
from app.services.db_service import _as_id, _tid, session
from app.services.notification import sms_service


def _token_hash(token: str) -> str:
    return hashlib.sha256(str(token or "").encode("utf-8")).hexdigest()


def _portal_link(consent_id, token: str) -> str:
    base = str(settings.GUARDIAN_PORTAL_BASE_URL or "").strip().rstrip("/")
    if not base:
        return ""
    return (
        f"{base}/guardian?consentId={quote(str(consent_id))}"
        f"&token={quote(str(token))}"
    )


def _guardian_context(db, consent_row: InternshipConsent):
    record = db.get(InternshipRecord, consent_row.internship_id)
    student = db.get(StudentProfile, consent_row.student_id)
    if not record or record.tenant_id != _tid() or record.is_deleted:
        raise AppException("DATA_CONFLICT", "实习记录已失效，无法下发监护人确认")
    if not student or student.tenant_id != _tid() or student.is_deleted:
        raise AppException("DATA_CONFLICT", "学生档案已失效，无法下发监护人确认")

    identity_prefix = str(consent_row.identity_masked or "").strip()
    links = db.scalars(select(StudentParentLink).where(
        StudentParentLink.tenant_id == _tid(),
        StudentParentLink.student_id == consent_row.student_id,
        StudentParentLink.link_status == "ACTIVE",
        StudentParentLink.is_deleted.is_(False),
    ).order_by(StudentParentLink.id.desc())).all()
    link = next(
        (item for item in links
         if identity_prefix and str(item.guardian_phone_hash or "").startswith(identity_prefix)),
        None,
    )
    if not link:
        raise AppException(
            "DATA_CONFLICT", "监护人绑定关系已失效或联系方式已变化，请重新创建确认任务")
    try:
        phone = decrypt_field(link.guardian_phone_encrypted)
    except Exception as error:
        raise AppException(
            "DATA_CONFLICT", "监护人手机号无法解密，请管理员核对字段加密密钥") from error
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
        status = str((result or {}).get("status") or "FAILED").upper()
        row.delivery_channel = "SMS" if status == "SENT" else f"SMS_{status}"
        request_id = str((result or {}).get("requestId") or "").strip()
        row.message_id = int(request_id) if request_id.isdigit() else None
        row.delivered_at = datetime.utcnow() if status == "SENT" else None
        row.version = int(row.version or 0) + 1
        consent._audit(db, row, f"GUARDIAN_DELIVERY_{status}", user, {
            "status": status,
            "reason": str((result or {}).get("reason") or "")[:200],
            "requestId": request_id[:128],
            "contactMasked": row.contact_masked or "",
            "newVersion": int(row.version or 0),
        })
        db.commit()


def _send(consent_id, token: str, user=None) -> dict:
    with session() as db:
        current = db.scalar(select(InternshipConsent).where(
            InternshipConsent.id == _as_id(consent_id),
            InternshipConsent.tenant_id == _tid(),
            InternshipConsent.is_deleted.is_(False),
        ))
        if not current:
            raise not_found("监护人确认任务不存在")
        _record, student, link, phone = _guardian_context(db, current)
        confirm_link = _portal_link(current.id, token)
        contact_masked = current.contact_masked or ""
        participant_name = current.participant_name or link.guardian_name
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
                _tid(), phone, participant_name,
                params={
                    "studentName": student.real_name,
                    "confirmLink": confirm_link,
                    "expiresHours": "24",
                })
    _record_delivery(consent_id, result, user)
    response = {
        "deliveryStatus": str(result.get("status") or "FAILED").upper(),
        "deliveryReason": str(result.get("reason") or ""),
        "contactMasked": contact_masked,
    }
    if not settings.is_prod:
        response["debugConfirmLink"] = _portal_link(consent_id, token)
    return response


def create_and_deliver(body: dict, user=None) -> dict:
    payload = body or {}
    consent_type = str(payload.get("consentType") or "").upper()
    result = consent.create_pending(payload, user)
    token = result.pop("guardianConfirmToken", None)
    if consent_type != "GUARDIAN":
        return result
    if str(result.get("status") or "") != "PENDING":
        return {
            **result,
            "consentType": "GUARDIAN",
            "deliveryStatus": "NOT_REQUIRED",
            "deliveryReason": "当前任务状态无需发送",
        }
    # 相同正文会复用待确认任务，旧明文 token 不可恢复；自动轮换后重新发送。
    if not token:
        redelivered = redeliver(result["id"], result.get("version"), user)
        return {**result, "consentType": "GUARDIAN", **redelivered}
    delivery = _send(result["id"], token, user)
    result.update({"consentType": "GUARDIAN", **delivery})
    with session() as db:
        saved = db.get(InternshipConsent, _as_id(result["id"]))
        if saved:
            result["version"] = int(saved.version or 0)
            result["deliveryChannel"] = saved.delivery_channel or ""
            result["deliveredAt"] = saved.delivered_at
            result["guardianTokenExpiresAt"] = saved.guardian_token_expires_at
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
        try:
            expected = int(expected_version)
        except (TypeError, ValueError):
            raise AppException("DATA_CONFLICT", "缺少有效数据版本，请刷新后重试")
        if expected != int(row.version or 0):
            raise AppException("DATA_CONFLICT", "任务版本已变化，请刷新后重试")
        _guardian_context(db, row)
        row.guardian_token_hash = _token_hash(raw_token)
        row.guardian_token_expires_at = datetime.utcnow() + timedelta(hours=24)
        row.guardian_token_used_at = None
        row.guardian_token_revoked_at = None
        row.delivery_channel = None
        row.message_id = None
        row.delivered_at = None
        row.version = int(row.version or 0) + 1
        consent._audit(db, row, "GUARDIAN_TOKEN_ROTATE", user, {
            "expiresAt": row.guardian_token_expires_at.isoformat() + "Z",
            "newVersion": int(row.version or 0),
        })
        db.commit()
        row_id = row.id
    delivery = _send(row_id, raw_token, user)
    with session() as db:
        saved = db.get(InternshipConsent, row_id)
        return {
            "id": str(row_id),
            "status": saved.status,
            "version": int(saved.version or 0),
            "deliveryChannel": saved.delivery_channel or "",
            "deliveredAt": saved.delivered_at,
            "guardianTokenExpiresAt": saved.guardian_token_expires_at,
            **delivery,
        }
