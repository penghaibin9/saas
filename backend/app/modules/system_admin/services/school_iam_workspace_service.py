"""Compatibility import for the canonical B7 School IAM Authority projection.

The runtime implementation lives in ``school_iam_authority_projection_service``.
This module keeps the historical import path stable without preserving a second
permission truth source.
"""
from app.modules.system_admin.services.school_iam_authority_projection_service import (
    PLATFORM_TENANT,
    _custom_role_governance,
    _json_items,
    _latest_template,
    _role_governance,
    _role_permissions,
    _system_role_governance,
    _template_permissions,
    _template_version,
    _tenant_id,
    assignable_catalog,
    explain_subject_access,
    school_template_impact,
    template_catalog,
    workspace_summary,
)

__all__ = [
    "assignable_catalog",
    "template_catalog",
    "school_template_impact",
    "explain_subject_access",
    "workspace_summary",
]
