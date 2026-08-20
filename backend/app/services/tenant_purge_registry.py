"""Fail-closed registry for tenant-scoped physical purge.

Every table carrying a ``tenant_id`` column must be classified before a tenant
can enter PURGE_READY.  In production/staging the registry is additionally
bound to one explicitly reviewed Alembic HEAD: any later schema migration makes
physical destruction fail closed until this file is reviewed and the recorded
head/version are deliberately advanced.  This prevents a newly-added table from
silently inheriting a broad family prefix and becoming destructible by accident.
"""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import text

from app.core.config import settings

REGISTRY_VERSION = "2026-08-20.p0.3"
REVIEWED_ALEMBIC_HEAD = "20260820_ctrl_offboarding"

PURGE = "PURGE"
RETAIN = "RETAIN"
FILE_OBJECT = "FILE_OBJECT"
UNKNOWN = "UNKNOWN"

# Explicit exceptions are reviewed table-by-table.  Keep this list narrow:
# broad families live below, while control-plane evidence / oddly named tenant
# tables must be deliberately classified here so a future schema addition is
# never made destructible just because its name happens to look familiar.
_RETAIN_EXACT = {
    "t_security_audit_log",
    "t_audit_outbox",
    "t_order",  # commercial/billing evidence; actual model table is t_order
    "t_incident_tenant",  # frozen incident impact snapshot
    "t_change_impact",  # frozen change impact snapshot
    "t_sod_violation",  # security-governance evidence, user row may later be purged
    "t_emergency_access_session",  # break-glass evidence
    "t_tenant_usage_snapshot",  # usage/capacity evidence
    "t_tenant_fair_use_violation",  # fair-use enforcement evidence
    "t_tenant_offboarding_job",
    "t_tenant_tombstone",
}

_PURGE_EXACT = {
    # Current schema exceptions whose names do not belong to the reviewed
    # business/configuration prefixes below.
    "t_menu_node",
    "t_calendar_window",
    "t_calendar_transition_event",
    "t_custom_role_source",
    "t_wildcard_retirement",
    "t_sod_rule",
    "t_tenant_storage_quota",
    "t_tenant_fair_use_limit",
    "t_provisioning_job",
    "t_support_ticket",
    "t_training_record",
    "t_renewal_task",
}

_RETAIN_PREFIXES = (
    "t_access_decision_",
    "t_access_review_",
    "t_security_change_",
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


def _strict_env() -> bool:
    app_env = str(getattr(settings, "APP_ENV", "") or "").strip().lower()
    deployment_mode = str(getattr(settings, "DEPLOYMENT_MODE", "") or "").strip().lower()
    return app_env in {"production", "staging"} or deployment_mode in {"production", "staging"}


def classify_table(table_name: str) -> RegistryItem:
    name = str(table_name)
    if name == "t_file_object":
        return RegistryItem(name, FILE_OBJECT, "physical bytes are deleted by file-storage governance after references")
    if name in _RETAIN_EXACT:
        return RegistryItem(name, RETAIN, "minimum compliance/control-plane evidence retained")
    if name in _PURGE_EXACT:
        return RegistryItem(name, PURGE, "reviewed tenant business/configuration data")
    if any(name.startswith(prefix) for prefix in _RETAIN_PREFIXES):
        return RegistryItem(name, RETAIN, "security evidence retained by policy")
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
        "reviewedAlembicHead": REVIEWED_ALEMBIC_HEAD,
        "items": [item.__dict__ for item in items],
        "unknownTables": unknown,
        "complete": not unknown,
        "purgeTableCount": sum(item.classification == PURGE for item in items),
        "retainTableCount": sum(item.classification == RETAIN for item in items),
        "fileObjectTableCount": sum(item.classification == FILE_OBJECT for item in items),
    }


def assert_schema_head_reviewed(actual_heads: list[str] | tuple[str, ...] | set[str]) -> None:
    """Pure fail-closed schema review guard, kept separately testable."""
    from app.core.exceptions import AppException

    normalized = sorted({str(value).strip() for value in actual_heads if str(value).strip()})
    if normalized != [REVIEWED_ALEMBIC_HEAD]:
        raise AppException(
            "TENANT_PURGE_SCHEMA_NOT_REVIEWED",
            "数据库迁移头与租户销毁审计版本不一致，拒绝物理销毁",
            http_status=409,
            details={
                "actualHeads": normalized,
                "reviewedAlembicHead": REVIEWED_ALEMBIC_HEAD,
                "registryVersion": REGISTRY_VERSION,
            },
        )


def _database_alembic_heads() -> list[str]:
    from app.db.session import get_sessionmaker

    db = get_sessionmaker()()
    try:
        rows = db.execute(text("SELECT version_num FROM alembic_version ORDER BY version_num")).all()
        return [str(row[0]) for row in rows if row and row[0]]
    except Exception as exc:  # noqa: BLE001
        from app.core.exceptions import AppException

        raise AppException(
            "TENANT_PURGE_SCHEMA_UNVERIFIABLE",
            "无法验证数据库迁移头，拒绝物理销毁",
            http_status=503,
            details={"reviewedAlembicHead": REVIEWED_ALEMBIC_HEAD, "registryVersion": REGISTRY_VERSION},
        ) from exc
    finally:
        db.close()


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
    # Production/staging destruction is tied to a deliberately reviewed schema
    # revision.  Any future migration therefore blocks purge by default even if
    # its table name happens to match a broad historical family prefix.
    if _strict_env():
        assert_schema_head_reviewed(_database_alembic_heads())
    return result
