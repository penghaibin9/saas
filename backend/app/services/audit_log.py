"""Canonical audit facade with Control Plane critical-action extensions."""
from __future__ import annotations

from app.services import audit_log_legacy as _legacy

_legacy.CRITICAL_ACTIONS = frozenset(set(_legacy.CRITICAL_ACTIONS) | {
    "SECURITY_CHANGE_ACTIVATE",
    "SECURITY_CHANGE_ROLLBACK",
    "PLATFORM_DUTY_CHANGE",
    "PLATFORM_ELEVATION_CHANGE",
    "PLATFORM_SUPPORT_SESSION_CHANGE",
    "PLATFORM_ACCESS_REVIEW_CHANGE",
    "ROLE_TEMPLATE_PUBLISH",
    "PLATFORM_PRODUCT_IAM_PUBLISH",
    "CUSTOM_ROLE_BINDING_RECONCILE",
    # Seven P1 closure writes that are deliberately committed in the same DB transaction
    # as their audit row. Keeping them in the canonical critical registry prevents a
    # deployment from accepting the business fact when its evidence cannot be persisted.
    "CONFIG_OVERRIDE_RESTORE_INHERITANCE",
    "ORG_NODE_DISABLE",
    "ORG_NODE_ENABLE",
    "PLATFORM_TENANT_PROFILE_UPDATE",
    "ACCOUNT_BINDING_REPAIR",
    "ACCOUNT_BINDING_REVOKE",
    "PLATFORM_SUPPORT_TICKET_CREATE",
    "PLATFORM_SUPPORT_TICKET_TRANSITION",
    "PLATFORM_TRAINING_CREATE",
    "PLATFORM_TRAINING_COMPLETE",
    "PLATFORM_RENEWAL_TASK_CREATE",
    "PLATFORM_RENEWAL_TASK_TRANSITION",
})

from app.services.audit_log_legacy import *  # noqa: F401,F403,E402

CRITICAL_ACTIONS = _legacy.CRITICAL_ACTIONS


def __getattr__(name: str):
    return getattr(_legacy, name)


def __dir__():
    return sorted(set(globals()) | set(dir(_legacy)))