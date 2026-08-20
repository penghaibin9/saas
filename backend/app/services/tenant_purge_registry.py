"""Fail-closed registry for tenant-scoped physical purge.

Every table carrying a ``tenant_id`` column must be classified before a tenant
can enter PURGE_READY.  The registry uses reviewed domain prefixes plus explicit
retention/special cases; an unfamiliar prefix is UNKNOWN and blocks destruction.
"""
from __future__ import annotations

from dataclasses import dataclass

REGISTRY_VERSION = "2026-08-20.p0.1"

PURGE = "PURGE"
RETAIN = "RETAIN"
FILE_OBJECT = "FILE_OBJECT"
UNKNOWN = "UNKNOWN"

_RETAIN_EXACT = {
    "t_security_audit_log",
    "t_audit_outbox",
    "t_platform_order",
    "t_tenant_offboarding_job",
    "t_tenant_tombstone",
}
_RETAIN_PREFIXES = (
    "t_access_decision_",
    "t_access_review_",
    "t_security_change_",
    "t_tenant_meter",
    "t_fair_use_",
)
_PURGE_PREFIXES = (
    "t_tenant_brand_", "t_tenant_capability_", "t_tenant_portal_",
    "t_org", "t_college", "t_major", "t_school_class", "t_staff_",
    "t_user", "t_role", "t_permission", "t_wx_", "t_password_", "t_auth_",
    "t_student", "t_teacher_", "t_scope_", "t_config_", "t_sys_", "t_system_",
    "t_workflow", "t_approval", "t_unified_", "t_todo", "t_message", "t_notification",
    "t_file_", "t_archive_", "t_export", "t_import", "t_excel_", "t_identity_", "t_shared_",
    "t_platform_config", "t_platform_notice",
    "t_orientation", "t_campus", "t_cs_",
    "t_academic", "t_aa_",
    "t_affairs", "t_dorm", "t_aid_", "t_funding_", "t_psy_", "t_discipline_",
    "t_internship", "t_risk_", "t_weekly_",
    "t_graduation", "t_gd_",
    "t_emp_", "t_employment",
    "t_data_", "t_master_", "t_service_", "t_sandbox_", "t_feedback",
    "t_idempotency", "t_portal_", "t_role_assignment_", "t_national_", "t_school_major_",
)


@dataclass(frozen=True)
class RegistryItem:
    table_name: str
    classification: str
    reason: str


def classify_table(table_name: str) -> RegistryItem:
    name = str(table_name)
    if name == "t_file_object":
        return RegistryItem(name, FILE_OBJECT, "physical bytes are deleted by file-storage governance after references")
    if name in _RETAIN_EXACT:
        return RegistryItem(name, RETAIN, "minimum compliance/control-plane evidence retained")
    if any(name.startswith(prefix) for prefix in _RETAIN_PREFIXES):
        return RegistryItem(name, RETAIN, "security/usage evidence retained by policy")
    if any(name.startswith(prefix) for prefix in _PURGE_PREFIXES):
        return RegistryItem(name, PURGE, "tenant business/configuration data")
    return RegistryItem(name, UNKNOWN, "unreviewed tenant-scoped table")


def inventory() -> dict:
    from app.db.base import metadata

    items: list[RegistryItem] = []
    for table in metadata.sorted_tables:
        if "tenant_id" not in table.c:
            continue
        items.append(classify_table(table.name))
    unknown = [item.table_name for item in items if item.classification == UNKNOWN]
    return {
        "registryVersion": REGISTRY_VERSION,
        "items": [item.__dict__ for item in items],
        "unknownTables": unknown,
        "complete": not unknown,
        "purgeTableCount": sum(item.classification == PURGE for item in items),
        "retainTableCount": sum(item.classification == RETAIN for item in items),
        "fileObjectTableCount": sum(item.classification == FILE_OBJECT for item in items),
    }


def assert_registry_complete() -> dict:
    from app.core.exceptions import AppException

    result = inventory()
    if result["unknownTables"]:
        raise AppException(
            "TENANT_PURGE_REGISTRY_INCOMPLETE",
            "存在未分类的租户数据表，拒绝进入物理销毁",
            http_status=409,
            details={"unknownTables": result["unknownTables"], "registryVersion": REGISTRY_VERSION},
        )
    return result
