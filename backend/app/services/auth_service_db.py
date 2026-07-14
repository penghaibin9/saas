"""
真实账号登录（POST /api/v1/auth/login）：查 t_user + pbkdf2 校验，密码仅以 hash 入库。
demo 账号绑定租户 demo-school（tenant_id=1000000000000000003），令牌携带 tenantId 实现行级隔离。
"""
from __future__ import annotations

from sqlalchemy import select

from app.core.exceptions import AppException
from app.core.security import create_access_token, verify_password
from app.core.token_store import (issue_refresh, login_locked, record_login_failure,
                                  reset_login_failures)
from app.db.session import db_enabled, get_sessionmaker

DEMO_TENANT_ID = 1000000000000000003
DEMO_TENANT_CODE = "demo-school"
DEMO_TENANT_NAME = "演示职业技术学校"
SANDBOX_TENANT_ID = 1000000000000000007
SANDBOX_TENANT_CODE = "sandbox-school"
SANDBOX_TENANT_NAME = "体验沙箱学校"

ROLE_BY_LOGIN = {
    # 正式演示租户 demo-school（真实账号，密码见登录页；仅存在于演示租户）
    "admin": ("SCHOOL_ADMIN", "学校管理员", "SCHOOL", "全校学生（正式演示）"),
    "teacher": ("COUNSELOR", "辅导员/指导教师", "COUNSELOR_CLASSES", "所带班级与指导学生（正式演示）"),
    "student": ("STUDENT", "学生", "SELF", "本人"),
    # 自由体验租户 sandbox-school（可随时重置）
    "admin2": ("SCHOOL_ADMIN", "学校管理员", "SCHOOL", "全校学生（体验沙箱）"),
    "teacher2": ("COUNSELOR", "辅导员/指导教师", "COUNSELOR_CLASSES", "所带班级与指导学生（体验沙箱）"),
    "student2": ("STUDENT", "学生", "SELF", "本人"),
    # 历史演示账号（保留兼容）
    "admin_demo": ("SCHOOL_ADMIN", "学校管理员", "SCHOOL", "全校学生（演示租户）"),
    "teacher_demo": ("GD_MENTOR", "指导教师", "GD_STUDENTS", "本人指导学生（演示租户）"),
    "counselor_demo": ("COUNSELOR", "辅导员", "COUNSELOR_CLASSES", "所带班级学生（演示租户）"),
    "student_demo": ("STUDENT", "学生", "SELF", "本人"),
}


def _tenant_meta(db, tenant_id: int) -> tuple[str, str]:
    """按 t_tenant 解析 (tenantCode, tenantName)：任意真实租户通用，不再写死 demo。"""
    from app.models import Tenant
    t = db.get(Tenant, tenant_id)
    if t is not None:
        return t.tenant_code or "demo", t.school_name or ""
    return "demo", ""


def login_with_password(login_name: str, password: str) -> dict:
    if not db_enabled():
        raise AppException("UNAUTHORIZED", "账号密码登录需启用数据库（DB_ENABLED=true）；演示可用 mock-login")
    # P5.5A：登录失败 5 次锁定 15 分钟（按登录名）
    remain = login_locked(f"pw:{login_name}")
    if remain > 0:
        from app.services import audit_log
        audit_log.record("LOGIN_LOCKED", login_name, detail={"remainSeconds": remain}, result="DENIED")
        raise AppException("UNAUTHORIZED", f"失败次数过多，账号已锁定，请 {remain // 60 + 1} 分钟后再试")
    from app.models import User
    db = get_sessionmaker()()
    try:
        user = db.scalars(select(User).where(User.login_name == login_name,
                                             User.is_deleted.is_(False),
                                             User.status == "ACTIVE")).first()
        if not user or not verify_password(password, user.password_hash):
            from app.services import audit_log
            count, locked = record_login_failure(f"pw:{login_name}")
            audit_log.record("LOGIN_FAIL", login_name,
                             detail={"failCount": count, "locked": bool(locked)}, result="FAIL")
            if locked:
                raise AppException("UNAUTHORIZED", "失败次数过多，账号已锁定 15 分钟")
            raise AppException("UNAUTHORIZED", "账号或密码不正确")
        reset_login_failures(f"pw:{login_name}")
        return build_login_result(db, user, client_type="PC")
    finally:
        db.close()


def build_login_result(db, user, client_type: str = "PC") -> dict:
    """从已认证的 User 对象构建登录响应（token + 用户 + 角色 + 数据范围）。
    账号密码登录与微信一键登录共用此函数，保证两条登录路径签发的令牌/响应完全一致。
    调用方负责已完成身份校验（密码正确 / openid 已绑定）。"""
    # P6：租户运营状态校验——停用租户全员禁止登录（平台超管除外）
    if user.user_type != "PLATFORM_SUPER_ADMIN":
        from app.services import platform_service
        if platform_service.tenant_status(user.tenant_id) == "disabled":
            from app.services import audit_log
            audit_log.record("LOGIN_TENANT_DISABLED", user.login_name,
                             detail={"tenantId": str(user.tenant_id)}, result="DENIED")
            raise AppException("NO_PERMISSION", "该学校服务已停用，无法登录，请联系平台方 13549666867")
    role_code, role_name, scope, scope_label = ROLE_BY_LOGIN.get(
        user.login_name, ("SCHOOL_ADMIN", "管理员", "SCHOOL", "全校"))
    if user.user_type == "PLATFORM_SUPER_ADMIN":
        role_code, role_name, scope, scope_label = (
            "PLATFORM_SUPER_ADMIN", "平台超级管理员", "PLATFORM", "全平台（跨租户）")
    tenant_id = str(user.tenant_id)
    t_code, t_name = _tenant_meta(db, user.tenant_id)
    claims = {
        "userId": f"db-{user.id}", "realName": user.real_name, "userType": user.user_type,
        "tid": t_code,
        "tenantId": tenant_id, "tenantName": t_name,
        "activeContextId": f"ctx_{user.login_name}", "currentRoleCode": role_code, "clientType": client_type,
    }
    # 学生账号：令牌带学号（移动端"本人数据"按学号精确解析，不依赖姓名唯一）
    if (user.user_type or "").upper() == "STUDENT":
        from app.models import StudentProfile
        sp = db.scalars(select(StudentProfile).where(
            StudentProfile.tenant_id == user.tenant_id,
            StudentProfile.real_name == user.real_name,
            StudentProfile.is_deleted.is_(False))).first()
        if sp:
            claims["studentNo"] = sp.student_no
    token = create_access_token(claims)
    refresh_token = issue_refresh(dict(claims))
    return {
        "accessToken": token, "refreshToken": refresh_token,
        "tokenType": "Bearer", "expiresIn": 7200,
        "userId": f"db-{user.id}", "username": user.login_name, "displayName": user.real_name,
        "tenantId": tenant_id, "tenantName": t_name,
        "currentRole": {"roleCode": role_code, "roleName": role_name,
                        "dataScope": scope, "scopeLabel": scope_label},
        "roles": [{"roleCode": role_code, "roleName": role_name}],
        "dataScope": {"scope": scope, "scopeLabel": scope_label},
        "permissionActions": {"viewList": True, "export": role_code != "STUDENT", "viewSensitive": False},
        "user": {"userId": f"db-{user.id}", "realName": user.real_name,
                 "userType": user.user_type, "mustChangePassword": False},
    }
