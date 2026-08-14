"""高危审计动作必须与真实生产调用方名称保持一致。"""
from __future__ import annotations

import pytest

from app.services.audit_log import CRITICAL_ACTIONS


@pytest.mark.parametrize("action", [
    "PLATFORM_TENANT_ENABLE",
    "PLATFORM_TENANT_DISABLE",
    "PLATFORM_TENANT_CHANGE_PACKAGE",
    "PLATFORM_TENANT_QUOTA",
    "PLATFORM_USER_RESET_PWD",
    "ROLE_PERMISSION_SAVE",
    "USER_ROLE_ASSIGN",
    "RESET_PASSWORD",
    "SENSITIVE_VIEW",
    "EXPORT",
    "ROLE_ASSIGNMENT_GRANT",
    "ROLE_ASSIGNMENT_REVOKE",
    "ROLE_ASSIGNMENT_TRANSFER",
    "ROLE_ASSIGNMENT_REVIEW",
    "ROLE_ASSIGNMENT_EXPIRE",
])
def test_real_high_risk_audit_actions_are_fail_closed(action):
    assert action in CRITICAL_ACTIONS, f"真实高危动作 {action} 必须命中 fail-closed 审计集合"
