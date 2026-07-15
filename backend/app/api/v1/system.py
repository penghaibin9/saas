"""系统信息接口。"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import io
import re
import secrets
from urllib.parse import quote

from fastapi import APIRouter, Body, Depends, File, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select

from app.core.config import settings
from app.core.context import current_tenant_id
from app.core.response import success
from app.core.permissions import require_any_permission, require_permission
from app.db.session import db_enabled, get_sessionmaker

router = APIRouter()


def _role_scope(role) -> str:
    marker = str(role.remark or "")
    prefix = ";scope="
    return marker.split(prefix, 1)[1].split(";", 1)[0] if prefix in marker else "ASSIGNED"


def _set_role_scope(role, scope_code: str) -> None:
    scope = str(scope_code or "ASSIGNED").strip().upper()
    if not re.fullmatch(r"[A-Z_]{2,40}", scope):
        from app.core.exceptions import AppException
        raise AppException("VALIDATION_ERROR", "数据范围编码不合法")
    remark = str(role.remark or "SAAS_CUSTOM")
    role.remark = re.sub(r";scope=[^;]*", "", remark).rstrip(";") + f";scope={scope};permMode=DB"


def _role_row(role, member_count: int) -> dict:
    status = str(role.status or "").upper()
    return {
        "id": str(role.id), "name": role.role_name, "code": role.role_code,
        "type": "BUILTIN" if str(role.role_type or "").upper() == "SYSTEM" else "CUSTOM",
        "typeLabel": "预设角色" if str(role.role_type or "").upper() == "SYSTEM" else "自定义角色",
        "scopeCode": _role_scope(role), "scopeName": _role_scope(role),
        "memberCount": int(member_count or 0), "description": role.remark or "",
        "status": "ENABLED" if status in ("ACTIVE", "ENABLED") else "DISABLED",
        "statusLabel": "启用中" if status in ("ACTIVE", "ENABLED") else "已停用",
        "updatedAt": str(getattr(role, "updated_at", "") or "")[:19],
    }


def _user_row(account, roles: list) -> dict:
    status = str(account.status or "").upper()
    return {
        "id": str(account.id), "userNo": account.login_name, "name": account.real_name,
        "orgId": "", "orgName": "未设置", "roles": [r.role_code for r in roles],
        "roleNames": [r.role_name for r in roles], "phone": "", "email": "",
        "status": "ACTIVE" if status == "ACTIVE" else status,
        "statusLabel": {"ACTIVE": "启用中", "DISABLED": "已停用", "LOCKED": "已锁定"}.get(status, "待激活"),
        "source": "统一师生导入" if account.user_type in ("TEACHER", "STUDENT") else "系统创建",
        "lastLoginAt": str(account.last_login_at or "")[:19], "createdAt": str(account.created_at or "")[:10],
    }


@router.get("/system/readiness", summary="学校上线初始化检查（真实库）")
def get_system_readiness(user=Depends(require_permission("systemAdmin.dashboard.view"))):
    from app.models import College, Major, Role, SchoolClass, User
    tenant_id = current_tenant_id()
    db = get_sessionmaker()()
    try:
        def count(model):
            return int(db.scalar(select(func.count(model.id)).where(model.tenant_id == tenant_id,
                         model.is_deleted.is_(False))) or 0)
        values = {"accounts": count(User), "roles": count(Role), "colleges": count(College),
                  "majors": count(Major), "classes": count(SchoolClass)}
        checks = [
            {"key": "roles", "label": "预设角色", "passed": values["roles"] >= 26,
             "message": f"已初始化 {values['roles']} / 26 个角色"},
            {"key": "org", "label": "组织主数据", "passed": values["colleges"] > 0,
             "message": f"学院 {values['colleges']}，专业 {values['majors']}，班级 {values['classes']}"},
            {"key": "accounts", "label": "师生账号", "passed": values["accounts"] > 0,
             "message": f"已创建 {values['accounts']} 个账号（仅统一导入入口可创建）"},
        ]
        return success({"ready": all(item["passed"] for item in checks), "counts": values, "checks": checks})
    finally:
        db.close()


@router.get("/system/org-tree", summary="学院专业班级组织树（真实库）")
def get_system_org_tree(user=Depends(require_permission("systemAdmin.org.view"))):
    from app.models import College, Major, SchoolClass, StudentProfile
    tenant_id = current_tenant_id()
    db = get_sessionmaker()()
    try:
        colleges = db.scalars(select(College).where(College.tenant_id == tenant_id,
                             College.is_deleted.is_(False)).order_by(College.sort_order, College.college_name)).all()
        majors = db.scalars(select(Major).where(Major.tenant_id == tenant_id, Major.is_deleted.is_(False))).all()
        classes = db.scalars(select(SchoolClass).where(SchoolClass.tenant_id == tenant_id,
                                SchoolClass.is_deleted.is_(False))).all()
        student_counts = dict(db.execute(select(StudentProfile.class_id, func.count(StudentProfile.id)).where(
            StudentProfile.tenant_id == tenant_id, StudentProfile.is_deleted.is_(False)).group_by(StudentProfile.class_id)).all())
        by_college = {c.id: [] for c in colleges}; by_major = {m.id: [] for m in majors}
        for major in majors: by_college.setdefault(major.college_id, []).append(major)
        for school_class in classes: by_major.setdefault(school_class.major_id, []).append(school_class)
        rows = []
        for college in colleges:
            major_rows = []
            for major in by_college.get(college.id, []):
                class_rows = [{"id": str(c.id), "code": c.class_code or "", "name": c.class_name,
                               "type": "CLASS", "typeLabel": "班级", "memberCount": int(student_counts.get(c.id, 0)),
                               "status": "ENABLED" if c.status == "ACTIVE" else "DISABLED", "children": []}
                              for c in by_major.get(major.id, [])]
                major_rows.append({"id": str(major.id), "code": major.code or "", "name": major.major_name,
                                   "type": "MAJOR", "typeLabel": "专业", "memberCount": sum(x["memberCount"] for x in class_rows),
                                   "status": "ENABLED" if major.status == "ACTIVE" else "DISABLED", "children": class_rows})
            rows.append({"id": str(college.id), "code": college.code or "", "name": college.college_name,
                         "type": "COLLEGE", "typeLabel": "学院", "memberCount": sum(x["memberCount"] for x in major_rows),
                         "status": "ENABLED" if college.status == "ACTIVE" else "DISABLED", "children": major_rows})
        return success(rows)
    finally:
        db.close()


@router.post("/system/org-nodes", summary="创建学院、专业或班级主数据")
@router.put("/system/org-nodes/{node_id}", summary="更新学院、专业或班级主数据")
def save_system_org_node(body: dict = Body(...), node_id: int | None = None,
                         user=Depends(require_any_permission("systemAdmin.org.create", "systemAdmin.org.update",
                                                              "systemAdmin.org.major.manage", "systemAdmin.org.class.manage"))):
    from app.core.exceptions import AppException
    from app.models import College, Major, SchoolClass
    tenant_id = current_tenant_id(); node_type = str(body.get("type") or "").upper()
    name = str(body.get("name") or "").strip(); code = str(body.get("code") or "").strip()
    parent_id = body.get("parentId")
    if node_type not in {"COLLEGE", "MAJOR", "CLASS"} or not name or not code:
        raise AppException("VALIDATION_ERROR", "请填写名称、编码，并选择学院/专业/班级类型")
    model = {"COLLEGE": College, "MAJOR": Major, "CLASS": SchoolClass}[node_type]
    db = get_sessionmaker()()
    try:
        row = db.scalars(select(model).where(model.id == node_id, model.tenant_id == tenant_id,
                                             model.is_deleted.is_(False))).first() if node_id else None
        if node_id and row is None: raise AppException("DATA_NOT_FOUND", "组织节点不存在")
        if not row:
            if node_type == "COLLEGE": row = College(tenant_id=tenant_id, college_name=name, code=code, status="ACTIVE")
            elif node_type == "MAJOR":
                if not parent_id: raise AppException("VALIDATION_ERROR", "专业必须归属学院")
                row = Major(tenant_id=tenant_id, college_id=int(parent_id), major_name=name, code=code, status="ACTIVE")
            else:
                if not parent_id: raise AppException("VALIDATION_ERROR", "班级必须归属专业")
                row = SchoolClass(tenant_id=tenant_id, major_id=int(parent_id), class_name=name, class_code=code, status="ACTIVE")
            db.add(row)
        else:
            if node_type == "COLLEGE": row.college_name = name
            elif node_type == "MAJOR": row.major_name = name
            else: row.class_name = name
        db.commit(); db.refresh(row)
        from app.services import audit_log
        audit_log.record("ORG_NODE_SAVE", f"{node_type}:{row.id}", detail={"name": name, "code": code})
        return success({"id": str(row.id)}, message="组织主数据已保存")
    except Exception:
        db.rollback(); raise
    finally: db.close()


@router.get("/system/roles", summary="学校预设角色与成员统计（真实库）")
def list_system_roles(
        keyword: str = "", type: str = "", status: str = "", page: int = 1, page_size: int = 50,
        user=Depends(require_permission("systemAdmin.role.view"))):
    if not db_enabled():
        from app.core.exceptions import AppException
        raise AppException("UNAUTHORIZED", "角色目录需启用数据库")
    from app.models import Role, UserRole
    tenant_id = current_tenant_id()
    db = get_sessionmaker()()
    try:
        stmt = select(Role).where(Role.tenant_id == tenant_id, Role.is_deleted.is_(False))
        if keyword.strip():
            like = f"%{keyword.strip()}%"
            stmt = stmt.where(Role.role_name.like(like) | Role.role_code.like(like))
        if type.upper() == "BUILTIN":
            stmt = stmt.where(Role.role_type == "SYSTEM")
        elif type.upper() == "CUSTOM":
            stmt = stmt.where((Role.role_type != "SYSTEM") | Role.role_type.is_(None))
        if status.upper() == "ENABLED":
            stmt = stmt.where(Role.status.in_(("ACTIVE", "ENABLED")))
        elif status.upper() == "DEPRECATED":
            stmt = stmt.where(Role.status.notin_(("ACTIVE", "ENABLED")))
        roles = db.scalars(stmt.order_by(Role.role_type, Role.role_code)).all()
        counts = dict(db.execute(
            select(UserRole.role_id, func.count(UserRole.id))
            .where(UserRole.tenant_id == tenant_id, UserRole.is_deleted.is_(False), UserRole.status == "ACTIVE")
            .group_by(UserRole.role_id)
        ).all())
        page = max(1, int(page or 1)); page_size = min(100, max(1, int(page_size or 50)))
        total = len(roles); start = (page - 1) * page_size
        return success({"list": [_role_row(role, counts.get(role.id, 0)) for role in roles[start:start + page_size]],
                        "total": total, "page": page, "pageSize": page_size})
    finally:
        db.close()


@router.get("/system/users", summary="学校账号列表（真实库）")
def list_system_users(keyword: str = "", role: str = "", status: str = "", page: int = 1, page_size: int = 20,
                      user=Depends(require_permission("systemAdmin.user.view"))):
    from app.models import Role, User, UserRole
    tenant_id = current_tenant_id()
    db = get_sessionmaker()()
    try:
        stmt = select(User).where(User.tenant_id == tenant_id, User.is_deleted.is_(False))
        if keyword.strip():
            like = f"%{keyword.strip()}%"
            stmt = stmt.where(User.login_name.like(like) | User.real_name.like(like))
        if status.strip(): stmt = stmt.where(User.status == status.upper())
        if role.strip():
            stmt = stmt.where(User.id.in_(select(UserRole.user_id).join(Role, Role.id == UserRole.role_id).where(
                UserRole.tenant_id == tenant_id, UserRole.status == "ACTIVE", UserRole.is_deleted.is_(False),
                Role.role_code == role.strip().upper(), Role.is_deleted.is_(False))))
        users = db.scalars(stmt.order_by(User.created_at.desc())).all()
        user_ids = [u.id for u in users]
        by_user: dict[int, list] = {uid: [] for uid in user_ids}
        if user_ids:
            for uid, r in db.execute(select(UserRole.user_id, Role).join(Role, Role.id == UserRole.role_id).where(
                UserRole.tenant_id == tenant_id, UserRole.user_id.in_(user_ids), UserRole.status == "ACTIVE",
                UserRole.is_deleted.is_(False), Role.status.in_(("ACTIVE", "ENABLED")), Role.is_deleted.is_(False))).all():
                by_user[uid].append(r)
        page = max(1, int(page or 1)); page_size = min(100, max(1, int(page_size or 20)))
        start = (page - 1) * page_size
        return success({"list": [_user_row(account, by_user.get(account.id, [])) for account in users[start:start + page_size]],
                        "total": len(users), "page": page, "pageSize": page_size})
    finally:
        db.close()


@router.put("/system/users/{user_id}/roles", summary="分配学校账号角色")
def assign_system_user_roles(user_id: int, body: dict = Body(...),
                             user=Depends(require_permission("systemAdmin.user.assign-role"))):
    from app.core.exceptions import AppException
    from app.core.permissions import ROLE_PERMISSIONS, has_permission
    from app.models import Permission, Role, RolePermission, User, UserRole
    tenant_id = current_tenant_id()
    codes = sorted({str(code).strip().upper() for code in (body.get("roleCodes") or []) if str(code).strip()})
    if not codes:
        raise AppException("VALIDATION_ERROR", "至少保留一个角色")
    db = get_sessionmaker()()
    try:
        account = db.scalars(select(User).where(User.id == user_id, User.tenant_id == tenant_id,
                                                User.is_deleted.is_(False))).first()
        if account is None: raise AppException("DATA_NOT_FOUND", "账号不存在")
        roles = db.scalars(select(Role).where(Role.tenant_id == tenant_id, Role.role_code.in_(codes),
                                              Role.status.in_(("ACTIVE", "ENABLED")), Role.is_deleted.is_(False))).all()
        if len(roles) != len(codes): raise AppException("VALIDATION_ERROR", "包含不存在或已停用的角色")
        for role_obj in roles:
            if str(role_obj.role_type or "").upper() == "SYSTEM":
                patterns = ROLE_PERMISSIONS.get(role_obj.role_code, set())
            else:
                patterns = set(db.scalars(select(Permission.permission_code).join(RolePermission,
                    RolePermission.permission_id == Permission.id).where(RolePermission.tenant_id == tenant_id,
                    RolePermission.role_id == role_obj.id, RolePermission.status == "ACTIVE",
                    RolePermission.is_deleted.is_(False))).all())
            if any(not has_permission(user, pattern) for pattern in patterns):
                raise AppException("NO_PERMISSION", f"不能分配超出自身权限边界的角色：{role_obj.role_name}")
        existing = {link.role_id: link for link in db.scalars(select(UserRole).where(
            UserRole.tenant_id == tenant_id, UserRole.user_id == account.id)).all()}
        wanted = {role_obj.id for role_obj in roles}
        for role_id, link in existing.items():
            if role_id in wanted:
                link.status = "ACTIVE"; link.is_deleted = False
            else:
                link.status = "DISABLED"; link.is_deleted = True
            link.version = int(link.version or 0) + 1
        for role_id in wanted - set(existing):
            db.add(UserRole(tenant_id=tenant_id, user_id=account.id, role_id=role_id, status="ACTIVE"))
        account.version = int(account.version or 0) + 1
        db.commit()
        from app.services import audit_log
        audit_log.record("USER_ROLE_ASSIGN", f"user:{account.id}", detail={"loginName": account.login_name,
                         "roleCodes": codes})
        return success({"id": str(account.id), "roleCodes": codes}, message="角色已分配；该账号需重新登录")
    except Exception:
        db.rollback(); raise
    finally:
        db.close()


@router.get("/system/roles/{role_id}", summary="学校角色详情（真实库）")
def get_system_role(role_id: int, user=Depends(require_permission("systemAdmin.role.view"))):
    from app.models import Permission, Role, RolePermission, User, UserRole
    tenant_id = current_tenant_id()
    db = get_sessionmaker()()
    try:
        role = db.scalars(select(Role).where(Role.id == role_id, Role.tenant_id == tenant_id,
                                             Role.is_deleted.is_(False))).first()
        if role is None:
            from app.core.exceptions import not_found
            raise not_found("角色不存在或不属于当前学校")
        member_count = db.scalar(select(func.count(UserRole.id)).where(
            UserRole.tenant_id == tenant_id, UserRole.role_id == role.id,
            UserRole.status == "ACTIVE", UserRole.is_deleted.is_(False))) or 0
        members = db.execute(select(User.id, User.real_name).join(
            UserRole, UserRole.user_id == User.id).where(
            UserRole.tenant_id == tenant_id, UserRole.role_id == role.id,
            UserRole.status == "ACTIVE", UserRole.is_deleted.is_(False),
            User.is_deleted.is_(False)).limit(50)).all()
        permission_codes = [row[0] for row in db.execute(select(Permission.permission_code).join(
            RolePermission, RolePermission.permission_id == Permission.id).where(
            RolePermission.tenant_id == tenant_id, RolePermission.role_id == role.id,
            RolePermission.status == "ACTIVE", RolePermission.is_deleted.is_(False)).order_by(
            Permission.permission_code)).all()]
        return success({**_role_row(role, member_count), "permissionCodes": permission_codes,
                        "menuKeys": [], "buttonKeys": [],
                        "members": [{"id": str(mid), "name": name, "orgName": "—"} for mid, name in members],
                        "auditTrail": []})
    finally:
        db.close()


@router.post("/system/roles", summary="创建学校自定义角色")
def create_system_role(body: dict = Body(...), user=Depends(require_permission("systemAdmin.role.create"))):
    from app.core.exceptions import AppException
    from app.models import Role
    tenant_id = current_tenant_id()
    name = str(body.get("name") or "").strip()
    code = str(body.get("code") or "").strip().upper() or f"CUSTOM_{secrets.token_hex(4).upper()}"
    if not name or not re.fullmatch(r"[A-Z][A-Z0-9_]{2,49}", code):
        raise AppException("VALIDATION_ERROR", "角色名称必填，编码须为 3-50 位大写字母、数字或下划线")
    db = get_sessionmaker()()
    try:
        if db.scalars(select(Role).where(Role.tenant_id == tenant_id, Role.role_code == code)).first():
            raise AppException("DATA_CONFLICT", "角色编码已存在")
        role = Role(tenant_id=tenant_id, role_code=code, role_name=name, role_type="CUSTOM", status="ACTIVE",
                    remark="SAAS_CUSTOM")
        _set_role_scope(role, body.get("scopeCode") or "ASSIGNED")
        db.add(role); db.commit(); db.refresh(role)
        from app.services import audit_log
        audit_log.record("ROLE_CREATE", f"role:{role.id}", detail={"roleCode": code, "roleName": name})
        return success(_role_row(role, 0), message="自定义角色已创建；请继续配置权限")
    except Exception:
        db.rollback(); raise
    finally:
        db.close()


@router.post("/system/roles/{role_id}/copy", summary="从预设或自定义角色复制学校自定义角色")
def copy_system_role(role_id: int, user=Depends(require_permission("systemAdmin.role.create"))):
    from app.core.exceptions import AppException
    from app.core.permissions import ROLE_PERMISSIONS, has_permission
    from app.models import Permission, Role, RolePermission
    tenant_id = current_tenant_id()
    db = get_sessionmaker()()
    try:
        source = db.scalars(select(Role).where(Role.id == role_id, Role.tenant_id == tenant_id,
                                               Role.is_deleted.is_(False))).first()
        if source is None:
            raise AppException("DATA_NOT_FOUND", "源角色不存在")
        if str(source.role_type or "").upper() == "SYSTEM":
            source_codes = set(ROLE_PERMISSIONS.get(source.role_code, set()))
        else:
            source_codes = set(db.scalars(select(Permission.permission_code).join(
                RolePermission, RolePermission.permission_id == Permission.id).where(
                RolePermission.tenant_id == tenant_id, RolePermission.role_id == source.id,
                RolePermission.status == "ACTIVE", RolePermission.is_deleted.is_(False))).all())
        excess = sorted(code for code in source_codes if not has_permission(user, code))
        if excess:
            raise AppException("NO_PERMISSION", "当前操作者不能复制超出自身权限边界的角色", {"codes": excess[:10]})
        base = re.sub(r"[^A-Z0-9_]", "_", f"{source.role_code}_CUSTOM")[:44].rstrip("_") or "CUSTOM"
        existing_codes = set(db.scalars(select(Role.role_code).where(Role.tenant_id == tenant_id)).all())
        code = next((f"{base}_{i}" for i in range(1, 1000) if f"{base}_{i}" not in existing_codes), None)
        if code is None:
            raise AppException("DATA_CONFLICT", "无法生成可用的角色编码")
        role = Role(tenant_id=tenant_id, role_code=code, role_name=f"{source.role_name}（自定义）",
                    role_type="CUSTOM", status="ACTIVE", remark="SAAS_CUSTOM")
        _set_role_scope(role, _role_scope(source))
        db.add(role); db.flush()
        permissions = {p.permission_code: p for p in db.scalars(select(Permission).where(
            Permission.permission_code.in_(source_codes))).all()} if source_codes else {}
        for permission_code in source_codes:
            if permission_code not in permissions:
                module, _, action = permission_code.partition(".")
                p = Permission(permission_code=permission_code, permission_name=permission_code,
                               module_code=module, action=action or None)
                db.add(p); db.flush(); permissions[permission_code] = p
            db.add(RolePermission(tenant_id=tenant_id, role_id=role.id,
                                  permission_id=permissions[permission_code].id, status="ACTIVE"))
        db.commit(); db.refresh(role)
        from app.services import audit_log
        audit_log.record("ROLE_COPY", f"role:{role.id}", detail={"sourceRoleId": str(source.id),
                         "sourceRoleCode": source.role_code, "roleCode": role.role_code,
                         "permissionCount": len(source_codes)})
        return success(_role_row(role, 0), message="已复制为自定义角色；成员未复制")
    except Exception:
        db.rollback(); raise
    finally:
        db.close()


@router.put("/system/roles/{role_id}/permissions", summary="保存自定义角色权限与默认范围")
def save_system_role_permissions(role_id: int, body: dict = Body(...),
                                 user=Depends(require_permission("systemAdmin.role.config"))):
    from app.core.exceptions import AppException
    from app.core.permissions import has_permission
    from app.models import Permission, Role, RolePermission
    tenant_id = current_tenant_id()
    raw_codes = body.get("permissionCodes") or []
    if not isinstance(raw_codes, list):
        raise AppException("VALIDATION_ERROR", "permissionCodes 必须为数组")
    codes = sorted({str(code).strip() for code in raw_codes if str(code).strip()})
    if len(codes) > 300 or any(code == "*" or code.startswith("platform.") for code in codes):
        raise AppException("VALIDATION_ERROR", "权限点超出学校角色可配置范围")
    forbidden = [code for code in codes if not has_permission(user, code)]
    if forbidden:
        raise AppException("NO_PERMISSION", "不能向角色授予当前操作者没有的权限", {"codes": forbidden[:10]})
    db = get_sessionmaker()()
    try:
        role = db.scalars(select(Role).where(Role.id == role_id, Role.tenant_id == tenant_id,
                                             Role.is_deleted.is_(False))).first()
        if role is None:
            raise AppException("DATA_NOT_FOUND", "角色不存在")
        if str(role.role_type or "").upper() == "SYSTEM":
            raise AppException("VALIDATION_ERROR", "预设角色由平台模板维护；请复制为自定义角色后再裁剪")
        existing = {rp.permission_id: rp for rp in db.scalars(select(RolePermission).where(
            RolePermission.tenant_id == tenant_id, RolePermission.role_id == role.id)).all()}
        permissions = {p.permission_code: p for p in db.scalars(select(Permission).where(
            Permission.permission_code.in_(codes))).all()} if codes else {}
        for code in codes:
            if code not in permissions:
                module, _, action = code.partition(".")
                p = Permission(permission_code=code, permission_name=code, module_code=module, action=action or None)
                db.add(p); db.flush(); permissions[code] = p
        wanted_ids = {p.id for p in permissions.values()}
        for permission_id, link in existing.items():
            if permission_id in wanted_ids:
                link.status = "ACTIVE"; link.is_deleted = False
            else:
                link.status = "DISABLED"; link.is_deleted = True
        for permission_id in wanted_ids - set(existing):
            db.add(RolePermission(tenant_id=tenant_id, role_id=role.id, permission_id=permission_id, status="ACTIVE"))
        _set_role_scope(role, body.get("scopeCode") or _role_scope(role))
        role.version = int(role.version or 0) + 1
        db.commit()
        from app.services import audit_log
        audit_log.record("ROLE_PERMISSION_CONFIG", f"role:{role.id}",
                         detail={"roleCode": role.role_code, "permissionCount": len(codes),
                                 "scopeCode": _role_scope(role)})
        return success({"id": str(role.id), "permissionCount": len(codes), "scopeCode": _role_scope(role)},
                       message="权限配置已生效；该角色成员需重新登录")
    except Exception:
        db.rollback(); raise
    finally:
        db.close()


@router.get("/system/identity-import/role-templates", summary="师生导入可选的 SaaS 预设角色")
def identity_role_templates(user=Depends(require_permission("systemAdmin.user.view"))):
    from app.services.saas_role_templates import role_catalog
    return success(role_catalog(teacher_only=True))


@router.get("/system/identity-import/template", summary="下载师生账号导入标准模板（仅 xlsx）")
def identity_import_template(user=Depends(require_permission("systemAdmin.user.import"))):
    from app.services.identity_import_file_service import build_template
    filename = "师生账号导入模板.xlsx"
    return StreamingResponse(
        io.BytesIO(build_template()),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"})


@router.post("/system/identity-import/validate-file", summary="上传师生账号 xlsx 并预检")
async def identity_import_validate_file(
        file: UploadFile = File(...),
        user=Depends(require_permission("systemAdmin.user.import"))):
    from app.services.identity_import_file_service import MAX_FILE_BYTES, create_batch, parse_xlsx
    from app.services.identity_import_service import preview_identity_import
    chunks, size = [], 0
    while chunk := await file.read(1024 * 1024):
        size += len(chunk)
        if size > MAX_FILE_BYTES:
            from app.core.exceptions import AppException
            raise AppException("FILE_TOO_LARGE", "导入文件超过 20MB 上限，请拆分后重试")
        chunks.append(chunk)
    parsed = parse_xlsx(b"".join(chunks), file.filename or "")
    payload = {"students": parsed["students"], "teachers": parsed["teachers"], "atomic": True}
    report = preview_identity_import(user, payload, pre_errors=parsed["errors"])
    return success(create_batch(user, parsed, report), message="Excel 解析及预检完成")


@router.post("/system/identity-import/confirm-batch", summary="确认预检批次并整批创建师生账号")
def identity_import_confirm_batch(
        body: dict = Body(...),
        user=Depends(require_permission("systemAdmin.user.import"))):
    from app.services import audit_log
    from app.services.identity_import_file_service import (build_credential_receipt,
                                                            get_batch, mark_confirmed)
    from app.services.identity_import_service import run_identity_import
    batch_no = str(body.get("batchNo") or "").strip()
    entry = get_batch(user, current_tenant_id(), batch_no, require_valid=True)
    report = run_identity_import(user, entry["payload"], dry_run=False)
    credential_receipt = build_credential_receipt(entry, report)
    public_report = {key: value for key, value in report.items()
                     if key not in ("studentCredentials", "teacherCredentials")}
    public_report["credentialReceipt"] = credential_receipt
    mark_confirmed(batch_no)
    audit_log.record("IDENTITY_IMPORT", f"batch:{batch_no}", detail={
        "fileName": entry["fileName"], "fileSha256": entry["fileSha256"],
        "tenantId": entry["tenantId"], "entities": report.get("entities")})
    return success({**public_report, "batchNo": batch_no}, message="师生账号已整批创建")


@router.get("/system/identity-import/batches/{batch_no}/errors", summary="下载师生导入错误回执")
def identity_import_errors(
        batch_no: str,
        user=Depends(require_permission("systemAdmin.user.import"))):
    from app.services.identity_import_file_service import build_error_workbook, get_batch
    entry = get_batch(user, current_tenant_id(), batch_no)
    filename = f"师生账号导入错误_{batch_no}.xlsx"
    return StreamingResponse(
        io.BytesIO(build_error_workbook(entry)),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"})


@router.get("/system/info", summary="系统信息 / 能力开关")
def system_info():
    now = datetime.now(timezone(timedelta(hours=settings.TIMEZONE_OFFSET_HOURS))).isoformat(timespec="seconds")
    return success({
        "appName": settings.APP_NAME,
        "env": settings.APP_ENV,
        "version": "0.1.0-skeleton",
        "apiPrefix": settings.API_V1_PREFIX,
        "tenancyMode": settings.TENANCY_MODE,
        "databaseConnected": settings.DB_ENABLED,   # 本阶段恒 False：未连真实库
        "serverTime": now,
        "capabilities": {
            "auth": "mock", "rbac": "mock", "tenantBrand": "mock",
            "todo": "mock", "message": "mock", "audit": "reserved",
            "fileUpload": "placeholder", "import": "placeholder",
            "export": "placeholder", "database": "reserved(not-connected)",
        },
    })
