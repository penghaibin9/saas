"""Non-schema RoleTemplate plane policy used before B5 normalized migration."""
from __future__ import annotations

from enum import Enum

from app.core.exceptions import AppException


class TemplatePlane(str, Enum):
    TENANT = "TENANT"
    PLATFORM_PRODUCT = "PLATFORM_PRODUCT"


ENTERPRISE_MEMBER_ROLE_CODES = frozenset({"COMPANY_ADMIN", "HR", "MENTOR"})


def is_school_role_template_code(role_code: str) -> bool:
    code = str(role_code or "").strip().upper()
    return bool(code) and not code.startswith("PLATFORM_") and code not in ENTERPRISE_MEMBER_ROLE_CODES


def assert_school_role_template_code(role_code: str) -> str:
    code = str(role_code or "").strip().upper()
    if not is_school_role_template_code(code):
        raise AppException(
            "ROLE_TEMPLATE_PLANE_VIOLATION",
            "学校 RoleTemplate 不能承载平台主管职责或企业成员角色",
            http_status=409,
            details={"roleCode": code},
        )
    return code


def tenant_role_template_permissions(role_permissions: dict[str, set[str]]) -> dict[str, set[str]]:
    """Return only school-delivery role definitions; never silently co-mingle planes."""
    return {
        code: set(patterns)
        for code, patterns in role_permissions.items()
        if is_school_role_template_code(code)
    }
