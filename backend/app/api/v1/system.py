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
from app.core.permissions import require_permission
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
