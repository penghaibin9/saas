"""Compatibility import for the canonical B7 School IAM services.

Permission/template projection lives in ``school_iam_authority_projection_service``.
Access Explain is separately composed from the existing IAM, data-scope and scope-policy
authorities in ``school_iam_access_explain_service``.  This historical import path keeps
routers stable without preserving a second permission or domain truth source.
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
    school_template_impact,
    template_catalog,
    workspace_summary,
)
from app.modules.system_admin.services.school_iam_access_explain_service import (
    explain_subject_access,
)

__all__ = [
    "assignable_catalog",
    "template_catalog",
    "school_template_impact",
    "explain_subject_access",
    "workspace_summary",
]
