"""导入导出域白名单与权限裁决（禁止任意 domain 字符串直入 service）。"""
from __future__ import annotations

from dataclasses import dataclass

from app.core.exceptions import AppException, not_found, no_permission
from app.core.permissions import has_permission, is_super_admin


@dataclass(frozen=True)
class DomainAuth:
    domain: str
    module_key: str
    import_perm: str | None
    export_perm: str | None
    export_manage_perm: str | None
    import_namespace: str | None


# domain → 模块授权键 + 精确 permissionCode（仅此表白名单可导入/导出）
DOMAIN_AUTH: dict[str, DomainAuth] = {
    "students": DomainAuth(
        "students", "studentProfile",
        "student.import", "student.export", "student.export",
        "STUDENT_PROFILE",
    ),
    "orientation": DomainAuth(
        "orientation", "orientation",
        "orientation.import", "orientation.export", "orientation.export",
        "ORIENTATION",
    ),
    "campus-service": DomainAuth(
        "campus-service", "campusService",
        "campusService.import", "campusService.export", "campusService.export",
        "CAMPUS_SERVICE",
    ),
    "academic": DomainAuth(
        "academic", "academicAffairs",
        "academicAffairs.process.manage", "academicAffairs.process.export",
        "academicAffairs.process.export",
        "ACADEMIC_PROCESS",
    ),
    "internship": DomainAuth(
        "internship", "internship",
        None, "internship.stats.export", "internship.stats.export",
        None,
    ),
    "graduation": DomainAuth(
        "graduation", "graduation",
        None, "graduationDesign.stats.export", "graduationDesign.stats.export",
        None,
    ),
    "employment": DomainAuth(
        "employment", "employment",
        "employment.import", "employment.export", "employment.export",
        "EMPLOYMENT",
    ),
    "student-affairs": DomainAuth(
        "student-affairs", "studentAffairs",
        "studentAffairs.import", "studentAffairs.export", "studentAffairs.export",
        "STUDENT_AFFAIRS_HISTORY",
    ),
}

IMPORT_DOMAINS = {k for k, v in DOMAIN_AUTH.items() if v.import_perm}
EXPORT_DOMAINS = {k for k, v in DOMAIN_AUTH.items() if v.export_perm}


def resolve_domain(domain: str, *, for_import: bool = False, for_export: bool = False) -> DomainAuth:
    key = (domain or "").strip()
    auth = DOMAIN_AUTH.get(key)
    if not auth:
        raise AppException("VALIDATION_ERROR", f"未知导入导出域：{domain}",
                           details={"allowed": sorted(DOMAIN_AUTH)})
    if for_import and not auth.import_perm:
        raise AppException("VALIDATION_ERROR", f"域 {domain} 不支持导入")
    if for_export and not auth.export_perm:
        raise AppException("VALIDATION_ERROR", f"域 {domain} 不支持导出")
    return auth


def enforce_import_perm(user: dict, domain: str) -> DomainAuth:
    auth = resolve_domain(domain, for_import=True)
    if not has_permission(user, auth.import_perm):
        raise no_permission(f"无权限执行该操作（{auth.import_perm}）")
    return auth


def enforce_export_perm(user: dict, domain: str) -> DomainAuth:
    auth = resolve_domain(domain, for_export=True)
    if not has_permission(user, auth.export_perm):
        raise no_permission(f"无权限执行该操作（{auth.export_perm}）")
    return auth


def enforce_student_import(user: dict) -> None:
    enforce_import_perm(user, "students")


def enforce_student_export(user: dict) -> None:
    enforce_export_perm(user, "students")


def _user_key(user: dict | None) -> str:
    return str((user or {}).get("userId") or "").strip()


def assert_import_batch_owner(user: dict, operator_key: str | None, manage_perm: str) -> None:
    """确认人须为批次创建人，或具备对应域管理/导入权限（管理员代确认）。"""
    if is_super_admin(user):
        return
    me = _user_key(user)
    if operator_key and me and operator_key == me:
        return
    if has_permission(user, manage_perm):
        # 学校管理员等持有导入权限者可代确认同租户批次
        return
    raise not_found("导入批次不存在或已过期，请重新校验")


def assert_export_download(user: dict, *, task_tenant_id: int, task_created_by: int | None,
                           module_code: str | None, current_tenant_id: int) -> DomainAuth:
    """下载裁决：租户一致 + 原导出权限仍有效 +（创建人或域导出管理权限）。不满足统一 404。"""
    if int(task_tenant_id) != int(current_tenant_id):
        raise not_found("导出任务不存在或文件已清理")
    domain = module_code if module_code in DOMAIN_AUTH else (
        "students" if module_code == "student" else None)
    if not domain:
        raise not_found("导出任务不存在或文件已清理")
    auth = DOMAIN_AUTH[domain]
    if not auth.export_perm or not has_permission(user, auth.export_perm):
        raise not_found("导出任务不存在或文件已清理")
    from app.services.message_identity import resolve_message_user_id
    uid = resolve_message_user_id(user)
    is_creator = task_created_by is not None and uid and int(task_created_by) == int(uid)
    can_manage = auth.export_manage_perm and has_permission(user, auth.export_manage_perm)
    if is_creator or can_manage or is_super_admin(user):
        return auth
    raise not_found("导出任务不存在或文件已清理")
