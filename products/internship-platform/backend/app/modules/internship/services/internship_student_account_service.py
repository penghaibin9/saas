"""Yiyang C04/G11 controlled student password reset inside internship data scope."""
from __future__ import annotations

import secrets
import string
from datetime import datetime

from sqlalchemy import select

from app.core.exceptions import AppException, not_found
from app.core.security import hash_password
from app.models import InternshipAuditTrail, StudentAccountLink, StudentProfile, User
from app.modules.internship.services.internship_scope import assert_internship_record_scope
from app.services.db_service import _as_id, _tid, session

_ACTIVE_LINK = "ACTIVE"


def _account_for_record(db, record):
    link = db.scalar(select(StudentAccountLink).where(
        StudentAccountLink.tenant_id == _tid(),
        StudentAccountLink.student_id == record.student_id,
        StudentAccountLink.link_status == _ACTIVE_LINK,
        StudentAccountLink.is_deleted.is_(False),
    ))
    if not link:
        raise AppException("DATA_CONFLICT", "该学生尚未绑定可登录账号，不能重置密码")
    account = db.scalar(select(User).where(
        User.id == link.user_id,
        User.tenant_id == _tid(),
        User.is_deleted.is_(False),
    ).with_for_update())
    if not account or str(account.user_type or "").upper() != "STUDENT":
        raise AppException("DATA_CONFLICT", "学生绑定账号不存在或账号类型不正确")
    if str(account.status or "").upper() != "ACTIVE":
        raise AppException("DATA_CONFLICT", "学生账号当前未启用，不能执行密码重置")
    return link, account


def _mask_login(value: str) -> str:
    text = str(value or "")
    if len(text) <= 4:
        return text[:1] + "***"
    return text[:2] + "***" + text[-2:]


def account_state(record_id, user: dict, *, batch_id=None) -> dict:
    with session() as db:
        record = assert_internship_record_scope(
            db, record_id, user, "查看学生账号状态", lock=False)
        if batch_id not in (None, "") and int(record.batch_id or 0) != int(batch_id):
            raise AppException("DATA_CONFLICT", "学生记录不属于当前实习批次，请刷新后重试")
        student = db.get(StudentProfile, record.student_id)
        link = db.scalar(select(StudentAccountLink).where(
            StudentAccountLink.tenant_id == _tid(),
            StudentAccountLink.student_id == record.student_id,
            StudentAccountLink.link_status == _ACTIVE_LINK,
            StudentAccountLink.is_deleted.is_(False),
        ))
        account = db.get(User, link.user_id) if link else None
        valid = bool(
            account and not account.is_deleted and account.tenant_id == _tid()
            and str(account.user_type or "").upper() == "STUDENT"
        )
        return {
            "recordId": str(record.id),
            "studentId": str(record.student_id),
            "studentName": student.real_name if student else "",
            "studentNo": student.student_no if student else "",
            "bound": valid,
            "accountId": str(account.id) if valid else "",
            "loginNameMasked": _mask_login(account.login_name) if valid else "",
            "accountStatus": account.status if valid else "",
            "mustChangePassword": bool(account.must_change_password) if valid else False,
            "accountVersion": int(account.version or 0) if valid else None,
            "credentialVersion": int(account.credential_version or 0) if valid else None,
            "canReset": bool(valid and str(account.status or "").upper() == "ACTIVE"),
        }


def _temporary_password() -> str:
    alphabet = string.ascii_letters + string.digits
    random_part = "".join(secrets.choice(alphabet) for _ in range(10))
    # Deterministically satisfies upper/lower/digit/symbol without logging or persistence.
    return f"Yk!A1{random_part}"


def reset_password(record_id, body: dict, user: dict) -> dict:
    payload = body or {}
    reason = str(payload.get("reason") or "").strip()
    if len(reason) < 5:
        raise AppException("VALIDATION_ERROR", "重置原因必填且不少于5个字")
    with session() as db:
        record = assert_internship_record_scope(
            db, record_id, user, "重置学生密码", lock=True)
        batch_id = payload.get("batchId")
        if batch_id in (None, ""):
            raise AppException("VALIDATION_ERROR", "缺少当前实习批次 batchId")
        try:
            if int(record.batch_id or 0) != int(batch_id):
                raise AppException("DATA_CONFLICT", "学生记录不属于当前实习批次，请刷新后重试")
        except (TypeError, ValueError):
            raise AppException("VALIDATION_ERROR", "batchId 格式不正确") from None

        link, account = _account_for_record(db, record)
        expected = payload.get("expectedAccountVersion")
        if expected is None:
            raise AppException("DATA_CONFLICT", "缺少学生账号版本，请刷新详情后重试")
        try:
            expected_value = int(expected)
        except (TypeError, ValueError):
            raise AppException("VALIDATION_ERROR", "expectedAccountVersion 必须是整数") from None
        if expected_value != int(account.version or 0):
            raise AppException("DATA_CONFLICT", "学生账号状态已变化，请刷新后重试")

        old_credential = int(account.credential_version or 0)
        temp_password = _temporary_password()
        account.password_hash = hash_password(temp_password)
        account.must_change_password = True
        account.credential_version = old_credential + 1
        account.version = int(account.version or 0) + 1

        db.add(InternshipAuditTrail(
            tenant_id=_tid(),
            target_id=account.id,
            target_type="ACCOUNT_RESET",
            action="STUDENT_PASSWORD_RESET",
            operator_name=str((user or {}).get("realName") or "教师"),
            detail_json={
                "recordId": str(record.id),
                "studentId": str(record.student_id),
                "accountUserId": str(account.id),
                "batchId": str(record.batch_id or ""),
                "linkId": str(link.id),
                "credentialVersionBefore": old_credential,
                "credentialVersionAfter": int(account.credential_version),
                "mustChangePassword": True,
                "reason": reason,
                # Never include old/new password or password hash in audit detail.
            },
            occurred_at=datetime.utcnow(),
        ))
        db.commit()
        return {
            "recordId": str(record.id),
            "studentId": str(record.student_id),
            "accountId": str(account.id),
            "tempPassword": temp_password,
            "mustChangePassword": True,
            "accountVersion": int(account.version or 0),
            "credentialVersion": int(account.credential_version or 0),
            "reloginRequired": True,
            "notice": "临时密码仅本次显示，请立即转交学生；旧会话已因凭据版本变化失效，学生首次登录须修改密码",
        }
