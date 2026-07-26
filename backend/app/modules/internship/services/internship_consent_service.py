"""知情确认：学校建任务，学生/已绑定监护人本人确认。"""
from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta

from sqlalchemy import select

from app.core.exceptions import AppException, not_found
from app.core.field_crypto import mask_phone_encrypted
from app.models import (
    InternshipAuditTrail, InternshipConsent, InternshipRecord, StudentParentLink,
    StudentProfile,
)
from app.services.db_service import _as_id, _tid, session


def _hash(value: str) -> str:
    return hashlib.sha256((value or "").encode("utf-8")).hexdigest()


def _client_digest(value: str | None) -> str | None:
    return _hash(value) if value else None


def _audit(db, consent, action, user=None, detail=None):
    db.add(InternshipAuditTrail(
        tenant_id=_tid(), target_id=consent.id, target_type="INTERNSHIP_CONSENT",
        action=action, operator_name=(user or {}).get("realName") or "系统",
        detail_json=detail or {}, occurred_at=datetime.utcnow()))


def evaluate_applicability(student, consent_type):
    if consent_type == "STUDENT":
        return True, "REQUIRED"
    birth = getattr(student, "birth_date", None)
    if not birth:
        return None, "PENDING_VERIFY"
    if isinstance(birth, str):
        try:
            birth = datetime.fromisoformat(birth[:10]).date()
        except ValueError:
            return None, "PENDING_VERIFY"
    today = datetime.utcnow().date()
    age = today.year - birth.year - ((today.month, today.day) < (birth.month, birth.day))
    return age < 18, "REQUIRED" if age < 18 else "NOT_APPLICABLE"


def create_pending(body, user=None):
    b = body or {}
    typ = (b.get("consentType") or "STUDENT").upper()
    if typ not in ("STUDENT", "GUARDIAN"):
        raise AppException("VALIDATION_ERROR", "consentType 必须为 STUDENT/GUARDIAN")
    snapshot = str(b.get("contentSnapshot") or "").strip()
    version = str(b.get("contentVersion") or "").strip()
    if not snapshot or not version:
        raise AppException("VALIDATION_ERROR", "正文快照和正文版本必填")
    digest = _hash(snapshot)
    with session() as db:
        from app.modules.internship.services.internship_scope import assert_internship_record_scope
        rec = assert_internship_record_scope(db, b.get("internshipId"), user, "创建知情确认任务")
        stu = db.get(StudentProfile, rec.student_id)
        applicable, state = evaluate_applicability(stu, typ)
        guardian = None
        if typ == "GUARDIAN" and applicable is True:
            guardian = db.scalars(select(StudentParentLink).where(
                StudentParentLink.tenant_id == _tid(),
                StudentParentLink.student_id == rec.student_id,
                StudentParentLink.link_status == "ACTIVE",
                StudentParentLink.is_deleted.is_(False),
            ).order_by(StudentParentLink.id.desc())).first()
            if not guardian:
                raise AppException("DATA_CONFLICT", "未找到学生已授权且完成手机号验证的监护人绑定")
        old_rows = db.scalars(select(InternshipConsent).where(
            InternshipConsent.tenant_id == _tid(),
            InternshipConsent.internship_id == rec.id,
            InternshipConsent.consent_type == typ,
            InternshipConsent.status.in_(("PENDING", "VALID")),
            InternshipConsent.is_deleted.is_(False),
        ).with_for_update()).all()
        for old in old_rows:
            if old.content_hash == digest and old.content_version == version:
                return _row(old, include_content=False)
            old.status = "SUPERSEDED"
            old.version = int(old.version or 0) + 1
            _audit(db, old, "SUPERSEDE", user, {"newContentHash": digest, "newContentVersion": version})
        guardian_token = secrets.token_urlsafe(32) if guardian else None
        x = InternshipConsent(
            tenant_id=_tid(), internship_id=rec.id, batch_id=rec.batch_id,
            student_id=rec.student_id, consent_type=typ, applicable=bool(applicable),
            participant_name=guardian.guardian_name if guardian else None,
            participant_relation=guardian.relation if guardian else None,
            contact_masked=mask_phone_encrypted(guardian.guardian_phone_encrypted) if guardian else None,
            identity_masked=(guardian.guardian_phone_hash[:12] if guardian else None),
            content_version=version, content_snapshot=snapshot, content_hash=digest,
            delivery_channel=b.get("deliveryChannel"), message_id=b.get("messageId"),
            delivered_at=datetime.utcnow(),
            status="PENDING" if applicable is not False else "NOT_APPLICABLE",
            guardian_token_hash=_hash(guardian_token) if guardian_token else None,
            guardian_token_expires_at=datetime.utcnow() + timedelta(hours=24) if guardian_token else None,
        )
        db.add(x)
        db.flush()
        _audit(db, x, "CREATE_TASK", user, {"type": typ, "contentHash": digest, "applicability": state})
        db.commit()
        result = {**_row(x, include_content=False), "applicability": state}
        if guardian_token:
            result["guardianConfirmToken"] = guardian_token
            result["guardianTokenExpiresAt"] = x.guardian_token_expires_at
        return result


def _my_student(db, user):
    from app.services.mobile_student_service import _require_student, resolve_student
    stu = resolve_student(db, _require_student(user))
    if not stu:
        raise AppException("NO_PERMISSION", "无法解析当前登录学生身份")
    return stu


def _my_consent(db, cid, user, *, lock=False):
    stu = _my_student(db, user)
    q = select(InternshipConsent).where(
        InternshipConsent.id == _as_id(cid),
        InternshipConsent.tenant_id == _tid(),
        InternshipConsent.student_id == stu.id,
        InternshipConsent.consent_type == "STUDENT",
        InternshipConsent.is_deleted.is_(False),
    )
    x = db.scalar(q.with_for_update() if lock else q)
    if not x:
        raise not_found("知情确认不存在")
    rec = db.get(InternshipRecord, x.internship_id)
    if not rec or rec.student_id != stu.id or rec.tenant_id != _tid():
        raise AppException("NO_PERMISSION", "该确认任务不属于当前学生本人实习记录")
    return x


def _row(x, *, include_content):
    out = {
        "id": str(x.id), "internshipId": str(x.internship_id), "consentType": x.consent_type,
        "status": x.status, "contentVersion": x.content_version, "contentHash": x.content_hash,
        "viewedAt": x.viewed_at, "confirmedAt": x.confirmed_at,
        "participantName": x.participant_name, "participantRelation": x.participant_relation,
        "contactMasked": x.contact_masked, "version": int(x.version or 0),
    }
    if include_content:
        out["contentSnapshot"] = x.content_snapshot
    return out


def list_my(user):
    with session() as db:
        stu = _my_student(db, user)
        rows = db.scalars(select(InternshipConsent).where(
            InternshipConsent.tenant_id == _tid(),
            InternshipConsent.student_id == stu.id,
            InternshipConsent.consent_type.in_(("STUDENT", "GUARDIAN")),
            InternshipConsent.is_deleted.is_(False),
        ).order_by(InternshipConsent.id.desc())).all()
        return [_row(x, include_content=False) for x in rows]


def get_my(cid, user):
    with session() as db:
        return _row(_my_consent(db, cid, user), include_content=True)


def mark_viewed(cid, user):
    with session() as db:
        x = _my_consent(db, cid, user, lock=True)
        if x.viewed_at is None:
            x.viewed_at = datetime.utcnow()
            x.version = int(x.version or 0) + 1
            _audit(db, x, "VIEW", user)
            db.commit()
        return _row(x, include_content=True)


def confirm(cid, body, user=None, client_ip=None):
    b = body or {}
    with session() as db:
        x = _my_consent(db, cid, user, lock=True)
        if x.status == "VALID":
            return _row(x, include_content=False)
        expected = b.get("expectedVersion")
        if expected is None or int(expected) != int(x.version or 0):
            raise AppException("DATA_CONFLICT", "确认任务版本已变化，请重新打开正文")
        if b.get("contentVersion") != x.content_version or b.get("contentHash") != x.content_hash:
            raise AppException("DATA_CONFLICT", "正文版本或哈希不一致，请重新阅读")
        if x.viewed_at is None:
            raise AppException("DATA_CONFLICT", "请先打开并阅读服务端保存的正文")
        if x.status != "PENDING":
            raise AppException("DATA_CONFLICT", "当前状态不可确认")
        x.confirmation_method = "STUDENT_AUTHENTICATED"
        x.device_digest = _client_digest(b.get("deviceDigest"))
        x.client_ip_digest = _client_digest(client_ip)
        x.confirmed_by_user_id = str((user or {}).get("userId") or "")
        x.confirmed_student_id = x.student_id
        x.confirmed_at = datetime.utcnow()
        x.status = "VALID"
        x.version = int(x.version or 0) + 1
        _audit(db, x, "CONFIRM", user, {"contentHash": x.content_hash})
        db.commit()
        return _row(x, include_content=False)


def reject(cid, body, user=None):
    b = body or {}
    reason = str(b.get("reason") or "").strip()
    if len(reason) < 5:
        raise AppException("VALIDATION_ERROR", "拒绝原因不少于5字")
    with session() as db:
        x = _my_consent(db, cid, user, lock=True)
        if b.get("expectedVersion") is None or int(b["expectedVersion"]) != int(x.version or 0):
            raise AppException("DATA_CONFLICT", "确认任务版本已变化")
        if x.status != "PENDING":
            raise AppException("DATA_CONFLICT", "当前状态不可拒绝")
        x.status = "REJECTED"
        x.revoke_reason = reason
        x.version = int(x.version or 0) + 1
        _audit(db, x, "REJECT", user, {"reason": reason})
        db.commit()
        return _row(x, include_content=False)


def revoke_task(cid, body, user=None):
    reason = str((body or {}).get("reason") or "").strip()
    if len(reason) < 5:
        raise AppException("VALIDATION_ERROR", "作废原因不少于5字")
    with session() as db:
        x = db.scalar(select(InternshipConsent).where(
            InternshipConsent.id == _as_id(cid),
            InternshipConsent.tenant_id == _tid(),
            InternshipConsent.is_deleted.is_(False)).with_for_update())
        if not x:
            raise not_found("知情确认任务不存在")
        from app.modules.internship.services.internship_scope import assert_internship_record_scope
        assert_internship_record_scope(db, x.internship_id, user, "作废知情确认任务")
        expected = (body or {}).get("expectedVersion")
        if expected is None or int(expected) != int(x.version or 0):
            raise AppException("DATA_CONFLICT", "确认任务版本已变化")
        if x.status not in ("PENDING", "VALID"):
            raise AppException("DATA_CONFLICT", "当前状态不可作废")
        x.status = "REVOKED"
        x.revoked_at = datetime.utcnow()
        x.revoke_reason = reason
        x.guardian_token_revoked_at = datetime.utcnow()
        x.version = int(x.version or 0) + 1
        _audit(db, x, "REVOKE_TASK", user, {"reason": reason})
        db.commit()
        return _row(x, include_content=False)


def list_guardian(user):
    ph = (user or {}).get("guardianPhoneHash")
    if (user or {}).get("userType") != "GUARDIAN" or not ph:
        raise AppException("NO_PERMISSION", "仅已验证监护人可访问")
    with session() as db:
        links = db.scalars(select(StudentParentLink).where(
            StudentParentLink.tenant_id == _tid(),
            StudentParentLink.guardian_phone_hash == ph,
            StudentParentLink.link_status == "ACTIVE",
            StudentParentLink.is_deleted.is_(False))).all()
        student_ids = [x.student_id for x in links]
        rows = db.scalars(select(InternshipConsent).where(
            InternshipConsent.tenant_id == _tid(),
            InternshipConsent.student_id.in_(student_ids or [0]),
            InternshipConsent.consent_type == "GUARDIAN",
            InternshipConsent.identity_masked == ph[:12],
            InternshipConsent.is_deleted.is_(False),
        ).order_by(InternshipConsent.id.desc())).all()
        return [_row(x, include_content=False) for x in rows]


def _assert_guardian_token(x, token):
    if not token or not secrets.compare_digest(_hash(str(token)), x.guardian_token_hash or ""):
        raise AppException("NO_PERMISSION", "监护人确认链接无效")
    if x.guardian_token_revoked_at is not None:
        raise AppException("DATA_CONFLICT", "监护人确认链接已撤销")
    if x.guardian_token_used_at is not None:
        raise AppException("DATA_CONFLICT", "监护人确认链接已使用")
    if x.guardian_token_expires_at is None or x.guardian_token_expires_at <= datetime.utcnow():
        raise AppException("DATA_CONFLICT", "监护人确认链接已过期")


def get_guardian(cid, user, token):
    ph = (user or {}).get("guardianPhoneHash")
    if (user or {}).get("userType") != "GUARDIAN" or not ph:
        raise AppException("NO_PERMISSION", "仅已验证监护人可访问")
    with session() as db:
        x = db.scalar(select(InternshipConsent).where(
            InternshipConsent.id == _as_id(cid), InternshipConsent.tenant_id == _tid(),
            InternshipConsent.consent_type == "GUARDIAN",
            InternshipConsent.identity_masked == ph[:12],
            InternshipConsent.is_deleted.is_(False)).with_for_update())
        if not x:
            raise not_found("监护人确认任务不存在")
        _assert_guardian_token(x, token)
        if x.viewed_at is None:
            x.viewed_at = datetime.utcnow()
            x.version = int(x.version or 0) + 1
            _audit(db, x, "GUARDIAN_VIEW", user)
            db.commit()
        return _row(x, include_content=True)


def guardian_confirm(cid, body, user=None, client_ip=None):
    ph = (user or {}).get("guardianPhoneHash")
    if (user or {}).get("userType") != "GUARDIAN" or not ph:
        raise AppException("NO_PERMISSION", "仅已验证监护人可确认")
    b = body or {}
    with session() as db:
        x = db.scalar(select(InternshipConsent).where(
            InternshipConsent.id == _as_id(cid), InternshipConsent.tenant_id == _tid(),
            InternshipConsent.consent_type == "GUARDIAN",
            InternshipConsent.identity_masked == ph[:12],
            InternshipConsent.is_deleted.is_(False)).with_for_update())
        if not x:
            raise not_found("监护人确认任务不存在")
        _assert_guardian_token(x, b.get("token"))
        link = db.scalars(select(StudentParentLink).where(
            StudentParentLink.tenant_id == _tid(), StudentParentLink.student_id == x.student_id,
            StudentParentLink.guardian_phone_hash == ph, StudentParentLink.link_status == "ACTIVE",
            StudentParentLink.is_deleted.is_(False))).first()
        if not link:
            raise AppException("NO_PERMISSION", "监护人授权关系无效")
        if b.get("expectedVersion") is None or int(b["expectedVersion"]) != int(x.version or 0):
            raise AppException("DATA_CONFLICT", "确认任务版本已变化")
        if b.get("contentVersion") != x.content_version or b.get("contentHash") != x.content_hash:
            raise AppException("DATA_CONFLICT", "正文版本或哈希不一致")
        if x.viewed_at is None:
            raise AppException("DATA_CONFLICT", "请先通过确认链接打开并阅读正文")
        if x.status != "PENDING":
            raise AppException("DATA_CONFLICT", "当前状态不可确认")
        x.status = "VALID"
        x.confirmation_method = "GUARDIAN_SMS_AUTHENTICATED"
        x.confirmed_at = datetime.utcnow()
        x.confirmed_by_user_id = str((user or {}).get("userId") or "")
        x.client_ip_digest = _client_digest(client_ip)
        x.device_digest = _client_digest(b.get("deviceDigest"))
        x.guardian_token_used_at = datetime.utcnow()
        x.version = int(x.version or 0) + 1
        _audit(db, x, "GUARDIAN_CONFIRM", user, {"contentHash": x.content_hash, "relation": link.relation})
        db.commit()
        return _row(x, include_content=False)


def supersede_for_major_change(db, internship_id, consent_type=None):
    q = select(InternshipConsent).where(
        InternshipConsent.tenant_id == _tid(),
        InternshipConsent.internship_id == _as_id(internship_id),
        InternshipConsent.status.in_(("PENDING", "VALID")))
    if consent_type:
        q = q.where(InternshipConsent.consent_type == consent_type)
    for x in db.scalars(q.with_for_update()).all():
        x.status = "SUPERSEDED"
        x.version = int(x.version or 0) + 1
        _audit(db, x, "SUPERSEDE_MAJOR_CHANGE", detail={"internshipId": str(internship_id)})
