"""Standalone IAM recovery surface used after administrator password reset."""
from __future__ import annotations

import re
from datetime import datetime

from fastapi import APIRouter, Body, Depends
from sqlalchemy import select

from app.core.exceptions import AppException, unauthorized
from app.core.response import success
from app.core.security import get_current_user, hash_password, verify_password
from app.db.session import get_sessionmaker
from app.models import InternshipAuditTrail, User
from app.services.db_service import _tid

router = APIRouter(prefix="/auth", tags=["Standalone IAM recovery"])
_PASSWORD = re.compile(r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[^A-Za-z0-9]).{10,128}$")


def _account(db, user):
    raw = str((user or {}).get("userId") or "")
    raw_tenant = str((user or {}).get("tenantId") or (user or {}).get("tenant_id") or "")
    if not raw.startswith("db-") or not raw[3:].isdigit():
        raise unauthorized("仅真实数据库账号可执行账号安全操作")
    if not raw_tenant.isdigit() or int(raw_tenant) <= 0:
        raise unauthorized("真实账号令牌缺少学校上下文")
    row = db.scalar(select(User).where(
        User.id == int(raw[3:]),
        User.tenant_id == int(raw_tenant),
        User.is_deleted.is_(False),
        User.status == "ACTIVE",
    ).with_for_update())
    if not row:
        raise unauthorized("账号已停用或不存在")
    return row


@router.get("/me", summary="最小账号安全状态")
def me(user=Depends(get_current_user)):
    db = get_sessionmaker()()
    try:
        row = _account(db, user)
        role_code = str((user or {}).get("currentRoleCode") or (user or {}).get("roleCode") or row.user_type or "")
        role_name = str((user or {}).get("currentRoleName") or role_code)
        payload = {
            "userId": f"db-{row.id}",
            "loginName": row.login_name,
            "realName": row.real_name,
            "userType": row.user_type,
            "mustChangePassword": bool(row.must_change_password),
            "credentialVersion": int(row.credential_version or 0),
            "tenantId": str(row.tenant_id),
            "currentRole": {"roleCode": role_code, "roleName": role_name},
            "user": {
                "userId": f"db-{row.id}",
                "loginName": row.login_name,
                "realName": row.real_name,
                "userType": row.user_type,
                "studentNo": row.login_name if str(row.user_type or "").upper() == "STUDENT" else None,
                "tenantId": str(row.tenant_id),
            },
        }
        return success(payload)
    finally:
        db.close()


@router.post("/change-password", summary="首次/重置后修改临时密码")
def change_password(body: dict = Body(...), user=Depends(get_current_user)):
    payload = body or {}
    current_password = str(payload.get("currentPassword") or "")
    new_password = str(payload.get("newPassword") or "")
    if not current_password:
        raise AppException("VALIDATION_ERROR", "请输入当前临时密码")
    if not _PASSWORD.fullmatch(new_password):
        raise AppException("VALIDATION_ERROR", "新密码至少10位，并同时包含大小写字母、数字和特殊字符")
    if current_password == new_password:
        raise AppException("VALIDATION_ERROR", "新密码不能与当前密码相同")

    db = get_sessionmaker()()
    try:
        account = _account(db, user)
        if not verify_password(current_password, account.password_hash):
            raise AppException("UNAUTHORIZED", "当前临时密码不正确", http_status=401)
        before = int(account.credential_version or 0)
        account.password_hash = hash_password(new_password)
        account.must_change_password = False
        account.credential_version = before + 1
        account.version = int(account.version or 0) + 1
        db.add(InternshipAuditTrail(
            tenant_id=int(account.tenant_id),
            target_id=account.id,
            target_type="ACCOUNT_RESET",
            action="STUDENT_PASSWORD_CHANGE",
            operator_name=account.real_name or "学生",
            detail_json={
                "accountUserId": str(account.id),
                "credentialVersionBefore": before,
                "credentialVersionAfter": int(account.credential_version),
                "mustChangePassword": False,
                "summary": "首次/重置后修改密码，旧凭据版本失效",
            },
            occurred_at=datetime.utcnow(),
        ))
        db.commit()
        return success({
            "success": True,
            "mustChangePassword": False,
            "credentialVersion": int(account.credential_version),
            "reloginRequired": True,
            "notice": "密码已修改，请重新登录；改密前的访问令牌已失效",
        }, message="密码修改成功")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
