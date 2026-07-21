"""真实账号认证与数据库角色上下文。

生产链路以 ``t_user -> t_user_role -> t_role`` 为唯一角色来源。仓库历史演示账号
尚未全部补齐 UserRole，因此仅对明确登记在 ``LEGACY_DEMO_ROLE_BY_LOGIN`` 的账号保留
兼容上下文；任意其他真实账号没有有效角色时默认拒绝登录。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import and_, select

from app.core.exceptions import AppException
from app.core.config import settings
from app.core.redis_client import cache_delete, cache_get_json, cache_set_json
from app.core.security import create_access_token, hash_password, verify_password
from app.core.token_store import (block_jti, issue_refresh, login_locked,
                                  record_login_failure, reset_login_failures,
                                  revoke_refresh_by_user)
from app.db.session import db_enabled, get_sessionmaker


# 只用于迁移期演示账号兼容，禁止把新学校账号继续写入此表。
LEGACY_DEMO_ROLE_BY_LOGIN = {
    "admin": ("SCHOOL_ADMIN", "学校管理员", "SCHOOL", "全校学生（正式演示）"),
    "teacher": ("COUNSELOR", "辅导员/指导教师", "COUNSELOR_CLASSES", "所带班级与指导学生（正式演示）"),
    "student": ("STUDENT", "学生", "SELF", "本人"),
    "admin2": ("SCHOOL_ADMIN", "学校管理员", "SCHOOL", "全校学生（体验沙箱）"),
    "teacher2": ("COUNSELOR", "辅导员/指导教师", "COUNSELOR_CLASSES", "所带班级与指导学生（体验沙箱）"),
    "student2": ("STUDENT", "学生", "SELF", "本人"),
    "admin_demo": ("SCHOOL_ADMIN", "学校管理员", "SCHOOL", "全校学生（演示租户）"),
    "teacher_demo": ("GD_MENTOR", "指导教师", "GD_STUDENTS", "本人指导学生（演示租户）"),
    "counselor_demo": ("COUNSELOR", "辅导员", "COUNSELOR_CLASSES", "所带班级学生（演示租户）"),
    "student_demo": ("STUDENT", "学生", "SELF", "本人"),
}


def _subject_cache_key(user_ctx: dict) -> str:
    return (f"auth:subject:{user_ctx.get('tenantId') or '0'}:"
            f"{user_ctx.get('userId') or '-'}")


def invalidate_subject_cache(user_id: str | int, tenant_id: str | int,
                             context_id: str | None = None) -> None:
    """Invalidate a known subject cache entry after security-sensitive writes."""
    cache_delete(f"auth:subject:{tenant_id}:{user_id}")


def invalidate_tenant_subject_caches(tenant_id: str | int) -> int:
    """Invalidate every cached account/role/status decision for one school."""
    from app.core.redis_client import cache_delete_pattern
    return cache_delete_pattern(f"auth:subject:{tenant_id}:*")


def _subject_cache_matches(user_ctx: dict) -> bool:
    cached = cache_get_json(_subject_cache_key(user_ctx))
    if not isinstance(cached, dict):
        return False
    return (
        cached.get("active") is True
        and cached.get("roleCode") == user_ctx.get("currentRoleCode")
        and cached.get("permissionVersion") == user_ctx.get("permissionVersion")
    )

# 这里只描述角色的默认范围策略；最终可见数据仍由各业务域真实关系解析器收敛。
ROLE_DEFAULT_SCOPE: dict[str, tuple[str, str]] = {
    "PLATFORM_SUPER_ADMIN": ("PLATFORM", "平台配置面（不含学校业务敏感明细）"),
    "SCHOOL_ADMIN": ("SCHOOL", "本校配置与授权范围"),
    "SYS_ADMIN": ("SCHOOL", "本校系统配置面"),
    "SECURITY_AUDITOR": ("SCHOOL", "本校审计日志（只读）"),
    "LEADER": ("SCHOOL", "全校汇总（只读、脱敏）"),
    "COLLEGE_ADMIN": ("COLLEGE", "所属学院"),
    "ACADEMIC_ADMIN": ("SCHOOL", "全校教务域"),
    "ACADEMIC_TEACHER": ("ASSIGNED", "本人教学任务"),
    "STUDENT_AFFAIRS_ADMIN": ("SCHOOL", "全校学工域"),
    "STUDENT_AFFAIRS": ("COLLEGE", "授权学工范围"),
    "COUNSELOR": ("COUNSELOR_CLASSES", "本人所带班级学生"),
    "PSYCHOLOGY_TEACHER": ("PSY_STUDENT", "专项授权心理关注学生"),
    "FUNDING_TEACHER": ("FUNDING_BIZ", "资助业务学生"),
    "DORM_MANAGER": ("DORM_BUILDING", "负责楼栋学生"),
    "YOUTH_LEAGUE": ("SCHOOL", "授权团学范围"),
    "GD_MENTOR": ("GD_STUDENTS", "本人指导毕设学生"),
    "INTERN_MENTOR": ("INTERN_STUDENTS", "本人指导实习学生"),
    "EMPLOYMENT_TEACHER": ("ASSIGNED", "授权就业业务范围"),
    "STUDENT": ("SELF", "本人"),
}


def _tenant_meta(db, tenant_id: int) -> tuple[str, str]:
    from app.models import Tenant
    tenant = db.get(Tenant, tenant_id)
    if tenant is not None:
        return tenant.tenant_code or "", tenant.school_name or ""
    return "", ""


def _scope_for(role_code: str) -> tuple[str, str]:
    return ROLE_DEFAULT_SCOPE.get(role_code, ("ASSIGNED", "按岗位业务关系授权"))


def _scope_from_role(role) -> str | None:
    marker = str(getattr(role, "remark", "") or "")
    prefix = ";scope="
    return marker.split(prefix, 1)[1].split(";", 1)[0] if prefix in marker else None


def _public_context(role_id: int | None, role_code: str, role_name: str,
                    scope: str | None = None, scope_label: str | None = None,
                    version: int = 0, legacy: bool = False) -> dict:
    default_scope, default_label = _scope_for(role_code)
    return {
        "contextId": f"legacy:{role_code}" if legacy else f"role:{role_id}",
        "contextType": role_code,
        "contextName": role_name,
        "roleCode": role_code,
        "roleName": role_name,
        "roleId": str(role_id) if role_id is not None else None,
        "orgName": "",
        "dataScope": scope or default_scope,
        "scopeLabel": scope_label or default_label,
        "todoCount": 0,
        "riskCount": 0,
        "enabled": True,
        "version": int(version or 0),
    }


def _role_contexts(db, user) -> list[dict]:
    """读取用户在本租户内的有效角色，任何一层租户/状态/软删不合法均不返回。"""
    from app.models import Role, UserRole
    # 平台超管只使用控制面内建身份，不与任意学校租户角色混用。
    if (user.user_type or "").upper() == "PLATFORM_SUPER_ADMIN":
        return [_public_context(None, "PLATFORM_SUPER_ADMIN", "平台超级管理员", legacy=True)]
    stmt = (
        select(UserRole, Role)
        .join(Role, and_(Role.id == UserRole.role_id,
                         Role.tenant_id == UserRole.tenant_id))
        .where(UserRole.tenant_id == user.tenant_id,
               UserRole.user_id == user.id,
               UserRole.status == "ACTIVE",
               UserRole.is_deleted.is_(False),
               Role.tenant_id == user.tenant_id,
               Role.role_code != "PLATFORM_SUPER_ADMIN",
               Role.status.in_(("ACTIVE", "ENABLED")),
               Role.is_deleted.is_(False))
        .order_by(UserRole.id)
    )
    contexts = [
        _public_context(role.id, role.role_code, role.role_name,
                        scope=_scope_from_role(role),
                        version=max(int(role.version or 0), int(link.version or 0)))
        for link, role in db.execute(stmt).all()
    ]
    if contexts:
        return contexts

    # 迁移期只兼容仓库登记的演示账号。新账号无角色必须 fail-closed。
    legacy = LEGACY_DEMO_ROLE_BY_LOGIN.get(user.login_name)
    if legacy:
        return [_public_context(None, legacy[0], legacy[1], legacy[2], legacy[3], legacy=True)]
    return []


def _pick_context(contexts: list[dict], *, context_id: str | None = None,
                  role_code: str | None = None) -> dict | None:
    if context_id:
        return next((c for c in contexts if c["contextId"] == context_id), None)
    if role_code:
        return next((c for c in contexts if c["roleCode"] == role_code), None)
    return contexts[0] if contexts else None


def _tenant_operating_status(db, tenant_id: int) -> str:
    """使用当前会话读取控制面状态，避免每个鉴权请求额外打开数据库会话。"""
    from app.models import PlatformConfig
    row = db.scalars(select(PlatformConfig).where(
        PlatformConfig.tenant_id == tenant_id,
        PlatformConfig.config_type == "TENANT_META",
        PlatformConfig.config_key == "-",
        PlatformConfig.is_deleted.is_(False))).first()
    meta = dict(row.config_json or {}) if row else {}
    status = str(meta.get("status") or "active").lower()
    expire_at = meta.get("expireAt")
    if status in ("active", "trial") and expire_at:
        try:
            expire_time = datetime.fromisoformat(str(expire_at))
            now = datetime.now(expire_time.tzinfo) if expire_time.tzinfo else datetime.now()
            if expire_time < now:
                return "expired"
        except (TypeError, ValueError):
            return "invalid"
    return status


def _ensure_tenant_login_allowed(db, user) -> None:
    """所有登录/刷新/访问通道共用的租户状态门禁。"""
    if (user.user_type or "").upper() == "PLATFORM_SUPER_ADMIN":
        return
    from app.models import Tenant
    tenant = db.get(Tenant, user.tenant_id)
    if tenant is None or (tenant.status or "").upper() not in ("ACTIVE", "TRIAL"):
        raise AppException("NO_PERMISSION", "该学校服务未启用或已停用，请联系平台方")
    if _tenant_operating_status(db, user.tenant_id) not in ("active", "trial"):
        raise AppException("NO_PERMISSION", "该学校服务已停用或到期，请联系平台方")


def _permission_version(user, contexts: list[dict]) -> str:
    role_part = ",".join(f"{c['roleCode']}:{c['version']}" for c in contexts)
    return f"u{int(user.version or 0)}|{role_part}"


def _student_no(db, user) -> str | None:
    if (user.user_type or "").upper() != "STUDENT":
        return None
    from app.models import StudentProfile
    # 正式账号优先以登录名=学号精确绑定；姓名查询只保留给历史演示账号。
    student = db.scalars(select(StudentProfile).where(
        StudentProfile.tenant_id == user.tenant_id,
        StudentProfile.student_no == user.login_name,
        StudentProfile.is_deleted.is_(False))).first()
    if student is None and user.login_name in LEGACY_DEMO_ROLE_BY_LOGIN:
        student = db.scalars(select(StudentProfile).where(
            StudentProfile.tenant_id == user.tenant_id,
            StudentProfile.real_name == user.real_name,
            StudentProfile.is_deleted.is_(False))).first()
    return student.student_no if student else None


def _claims(db, user, context: dict, contexts: list[dict], client_type: str) -> dict:
    tenant_code, tenant_name = _tenant_meta(db, user.tenant_id)
    claims = {
        "userId": f"db-{user.id}",
        "loginName": user.login_name,
        "realName": user.real_name,
        "userType": user.user_type,
        "tid": tenant_code,
        "tenantId": str(user.tenant_id),
        "tenantName": tenant_name,
        "activeContextId": context["contextId"],
        "currentRoleCode": context["roleCode"],
        "permissionVersion": _permission_version(user, contexts),
        "clientType": client_type,
    }
    student_no = _student_no(db, user)
    if student_no:
        claims["studentNo"] = student_no
    return claims


def _login_result(db, user, context: dict, contexts: list[dict], client_type: str) -> dict:
    claims = _claims(db, user, context, contexts, client_type)
    access_token = create_access_token(claims)
    refresh_token = issue_refresh(dict(claims))
    return {
        "accessToken": access_token,
        "refreshToken": refresh_token,
        "tokenType": "Bearer",
        "expiresIn": settings.JWT_EXPIRES_IN,
        "userId": f"db-{user.id}",
        "username": user.login_name,
        "displayName": user.real_name,
        "tenantId": str(user.tenant_id),
        "tenantName": claims["tenantName"],
        "activeContextId": context["contextId"],
        "currentRole": {
            "roleCode": context["roleCode"],
            "roleName": context["roleName"],
            "contextType": context["roleCode"],
            "contextName": context["roleName"],
            "dataScope": context["dataScope"],
            "scopeLabel": context["scopeLabel"],
        },
        "roles": [{"roleCode": c["roleCode"], "roleName": c["roleName"],
                   "contextId": c["contextId"]} for c in contexts],
        "contexts": [{k: v for k, v in c.items() if k != "version"} for c in contexts],
        "dataScope": {"scope": context["dataScope"], "scopeLabel": context["scopeLabel"]},
        "permissionActions": {
            "viewList": True,
            "export": context["roleCode"] not in ("STUDENT", "PLATFORM_SUPER_ADMIN"),
            "viewSensitive": False,
        },
        "user": {
            "userId": f"db-{user.id}",
            "realName": user.real_name,
            "userType": user.user_type,
            "mustChangePassword": bool(user.must_change_password),
        },
    }


def _find_login_user(db, login_name: str, tenant_code: str | None):
    from app.models import Tenant, User
    stmt = select(User).where(User.login_name == login_name,
                              User.is_deleted.is_(False),
                              User.status == "ACTIVE")
    if tenant_code:
        tenant = db.scalars(select(Tenant).where(
            Tenant.tenant_code == tenant_code,
            Tenant.status.in_(("ACTIVE", "TRIAL", "active", "trial")))).first()
        if tenant is None:
            return None
        return db.scalars(stmt.where(User.tenant_id == tenant.id)).first()
    users = db.scalars(stmt.order_by(User.id).limit(2)).all()
    if len(users) > 1:
        raise AppException("VALIDATION_ERROR", "该账号存在于多所学校，请填写学校编码后登录")
    return users[0] if users else None


def login_with_password(login_name: str, password: str, tenant_code: str | None = None,
                        client_type: str = "PC") -> dict:
    if not db_enabled():
        raise AppException("UNAUTHORIZED", "账号密码登录需启用数据库（DB_ENABLED=true）；演示可用 mock-login")
    login_name = (login_name or "").strip()
    tenant_code = (tenant_code or "").strip() or None
    lock_key = f"pw:{tenant_code or '*'}:{login_name}"
    remain = login_locked(lock_key)
    if remain > 0:
        from app.services import audit_log
        audit_log.record("LOGIN_LOCKED", login_name,
                         detail={"remainSeconds": remain, "tenantCode": tenant_code}, result="DENIED")
        raise AppException("UNAUTHORIZED", f"失败次数过多，账号已锁定，请 {remain // 60 + 1} 分钟后再试")

    db = get_sessionmaker()()
    try:
        user = _find_login_user(db, login_name, tenant_code)
        if not user or not verify_password(password, user.password_hash):
            from app.services import audit_log
            from app.services.system_config_service import get_int
            lock_minutes = get_int("SEC_LOCK_MINUTES", 15)
            count, locked = record_login_failure(lock_key, threshold=get_int("SEC_LOCK_MAX_FAIL", 5),
                                                 lock_seconds=lock_minutes * 60)
            audit_log.record("LOGIN_FAIL", login_name,
                             detail={"failCount": count, "locked": bool(locked),
                                     "tenantCode": tenant_code}, result="FAIL")
            if locked:
                raise AppException("UNAUTHORIZED", f"失败次数过多，账号已锁定 {lock_minutes} 分钟")
            raise AppException("UNAUTHORIZED", "账号、学校编码或密码不正确")

        contexts = _role_contexts(db, user)
        if not contexts:
            from app.services import audit_log
            audit_log.record("LOGIN_NO_ACTIVE_ROLE", login_name,
                             detail={"tenantId": str(user.tenant_id)}, result="DENIED")
            raise AppException("NO_PERMISSION", "账号尚未分配有效岗位，请联系学校管理员")

        _ensure_tenant_login_allowed(db, user)
        reset_login_failures(lock_key)
        return _login_result(db, user, contexts[0], contexts, client_type)
    finally:
        db.close()


def build_login_result(db, user, client_type: str = "PC") -> dict:
    """微信登录等已认证通道共用的登录响应。"""
    _ensure_tenant_login_allowed(db, user)
    contexts = _role_contexts(db, user)
    if not contexts:
        raise AppException("NO_PERMISSION", "账号尚未分配有效岗位，请联系学校管理员")
    return _login_result(db, user, contexts[0], contexts, client_type)


def _load_token_user(db, user_ctx: dict):
    from app.models import User
    raw_id = str((user_ctx or {}).get("userId") or "")
    tenant_id = str((user_ctx or {}).get("tenantId") or "")
    if not raw_id.startswith("db-") or not raw_id[3:].isdigit() or not tenant_id.isdigit():
        raise AppException("UNAUTHORIZED", "真实账号令牌无效，请重新登录")
    user = db.scalars(select(User).where(
        User.id == int(raw_id[3:]), User.tenant_id == int(tenant_id),
        User.is_deleted.is_(False), User.status == "ACTIVE")).first()
    if user is None:
        raise AppException("UNAUTHORIZED", "账号已停用或令牌已失效，请重新登录")
    return user


def validate_token_subject(user_ctx: dict) -> dict:
    """对真实账号逐请求复核账号、租户、当前角色和权限版本，角色回收立即生效。"""
    if not db_enabled() or not str((user_ctx or {}).get("userId") or "").startswith("db-"):
        return user_ctx
    if _subject_cache_matches(user_ctx):
        return user_ctx
    db = get_sessionmaker()()
    try:
        user = _load_token_user(db, user_ctx)
        _ensure_tenant_login_allowed(db, user)
        contexts = _role_contexts(db, user)
        current = _pick_context(contexts,
                                context_id=user_ctx.get("activeContextId"),
                                role_code=user_ctx.get("currentRoleCode"))
        if current is None or current["roleCode"] != user_ctx.get("currentRoleCode"):
            raise AppException("UNAUTHORIZED", "当前岗位已被回收，请重新登录")
        token_version = user_ctx.get("permissionVersion")
        if token_version and token_version != _permission_version(user, contexts):
            raise AppException("UNAUTHORIZED", "权限配置已更新，请重新登录")
        cache_set_json(_subject_cache_key(user_ctx), {
            "active": True,
            "roleCode": current["roleCode"],
            "permissionVersion": _permission_version(user, contexts),
        }, settings.AUTH_SUBJECT_CACHE_TTL)
        return user_ctx
    finally:
        db.close()


def get_me(user_ctx: dict) -> dict:
    db = get_sessionmaker()()
    try:
        user = _load_token_user(db, user_ctx)
        contexts = _role_contexts(db, user)
        active = _pick_context(contexts, context_id=user_ctx.get("activeContextId"),
                               role_code=user_ctx.get("currentRoleCode"))
        if active is None:
            raise AppException("UNAUTHORIZED", "当前岗位已被回收，请重新登录")
        return {
            "userId": f"db-{user.id}",
            "loginName": user.login_name,
            "realName": user.real_name,
            "userType": user.user_type,
            "avatarFileId": None,
            "phoneMasked": None,
            "activeContextId": active["contextId"],
            "currentRole": {
                "contextType": active["roleCode"], "contextName": active["roleName"],
                "roleCode": active["roleCode"], "roleName": active["roleName"],
                "dataScope": active["dataScope"], "scopeLabel": active["scopeLabel"],
            },
            "contexts": [{k: v for k, v in c.items() if k != "version"} for c in contexts],
        }
    finally:
        db.close()


def switch_role(user_ctx: dict, context_id: str, client_type: str) -> dict:
    db = get_sessionmaker()()
    try:
        user = _load_token_user(db, user_ctx)
        contexts = _role_contexts(db, user)
        target = _pick_context(contexts, context_id=context_id)
        if target is None or target["contextId"] != context_id:
            raise AppException("ROLE_NOT_FOUND", "身份不存在、已停用或不属于当前用户")

        # 身份切换后旧 access/refresh 不得继续恢复旧上下文。
        block_jti(str(user_ctx.get("tokenJti") or ""), user_ctx.get("tokenExp"))
        revoke_refresh_by_user(f"db-{user.id}")
        result = _login_result(db, user, target, contexts, client_type)
        result.update({
            "contextType": target["roleCode"],
            "contextName": target["roleName"],
            "dataScope": target["dataScope"],
            "menusChanged": True,
        })
        return result
    finally:
        db.close()


def get_active_context(user_ctx: dict) -> dict:
    """RBAC/menu 服务使用的统一当前上下文；mock 用户继续由 mock 服务解析。"""
    me = get_me(user_ctx)
    role = me["currentRole"]
    return {
        "contextId": me["activeContextId"],
        "contextType": role["roleCode"],
        "contextName": role["roleName"],
        "roleCode": role["roleCode"],
        "roleName": role["roleName"],
        "dataScope": role["dataScope"],
        "scopeLabel": role.get("scopeLabel", ""),
        "studentCount": 0,
        "todoCount": 0,
        "riskCount": 0,
        "enabled": True,
    }


def change_own_password(user_ctx: dict, old_password: str, new_password: str) -> dict:
    if not db_enabled():
        raise AppException("UNAUTHORIZED", "需启用数据库")
    raw_id = str((user_ctx or {}).get("userId") or "")
    if not raw_id.startswith("db-") or not raw_id[3:].isdigit():
        raise AppException("VALIDATION_ERROR", "演示账号不支持修改密码，请使用正式账号登录后再试")
    from app.services.system_config_service import get_int
    min_len = get_int("SEC_PASSWORD_MIN_LEN", 8)
    if len(new_password or "") < min_len:
        raise AppException("VALIDATION_ERROR", f"新密码长度至少 {min_len} 位")
    if old_password == new_password:
        raise AppException("VALIDATION_ERROR", "新密码不能与原密码相同")
    lock_key = f"pwchange:{raw_id[3:]}"
    remain = login_locked(lock_key)
    if remain > 0:
        raise AppException("UNAUTHORIZED", f"失败次数过多，请 {remain // 60 + 1} 分钟后再试")
    db = get_sessionmaker()()
    try:
        user = _load_token_user(db, user_ctx)
        if not verify_password(old_password or "", user.password_hash):
            count, locked = record_login_failure(lock_key)
            if locked:
                raise AppException("UNAUTHORIZED", "失败次数过多，账号已锁定 15 分钟")
            raise AppException("UNAUTHORIZED", "原密码不正确")
        reset_login_failures(lock_key)
        user.password_hash = hash_password(new_password)
        user.must_change_password = False
        user.version = int(user.version or 0) + 1
        db.commit()
        invalidate_subject_cache(f"db-{user.id}", user.tenant_id,
                                 user_ctx.get("activeContextId"))
        revoke_refresh_by_user(f"db-{user.id}")
        from app.services import audit_log
        audit_log.record("PASSWORD_CHANGE", user.login_name, detail={}, result="SUCCESS")
        return {"success": True, "reloginRequired": True}
    finally:
        db.close()
