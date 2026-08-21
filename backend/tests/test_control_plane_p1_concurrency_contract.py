"""Source-level locks for P1 production concurrency/audit boundaries.

The behavior is also exercised by broader MySQL gates. These assertions prevent future
refactors from silently removing the locks, route precedence or critical audit registry.
"""
from pathlib import Path


def _read(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def test_customer_success_mutations_use_locked_guard_before_broad_router():
    router = _read("app/api/v1/router.py")
    guard = _read("app/services/customer_success_p1_guard_service.py")
    api = _read("app/api/v1/customer_success_p1_closure.py")

    assert "customer_success_p1_closure_router" in router
    assert router.index("customer_success_p1_closure_router,") < router.index("platform_p1_closure_router,")
    # All three state-changing operations share one canonical row-lock helper.
    # Count helper call sites rather than duplicated with_for_update() syntax so
    # extracting the lock into a common function cannot create a false red gate.
    assert "def _lock_row(" in guard
    assert ".with_for_update()" in guard
    assert guard.count("_lock_row(db,") >= 3
    assert guard.count("record_critical_in_session") >= 6
    assert '"CLOSED": set()' in guard
    assert '"RENEWED": set()' in guard
    assert '"CHURNED": set()' in guard
    assert "expected_version" in api
    assert "customerSuccess.manage" in api


def test_identity_mutations_are_serializable_atomically_audited_and_timeline_complete():
    guard = _read("app/services/identity_binding_p1_guard_service.py")
    router = _read("app/api/v1/router.py")

    assert guard.count("with_for_update()") >= 3
    assert guard.count("record_critical_in_session") >= 2
    assert "bound_at=now" in guard
    assert "before.unbound_at = now" in guard
    assert "link.unbound_at = now" in guard
    assert "remark=reason[:500]" in guard
    assert '_sig("/system/accounts/{user_id}/repair-binding", "POST")' in router
    assert '_sig("/system/accounts/{user_id}/unbind", "POST")' in router


def test_first_tenant_profile_write_locks_tenant_authority_row():
    source = _read("app/api/v1/platform_p1_closure.py")
    assert "tenant_stmt = tenant_stmt.with_for_update()" in source
    assert "stmt = stmt.with_for_update()" in source
    assert "expectedVersion" in source
    assert "PLATFORM_TENANT_PROFILE_UPDATE" in source


def test_all_new_in_session_audit_actions_are_registered_critical():
    audit = _read("app/services/audit_log.py")
    required = {
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
    }
    for action in required:
        assert f'"{action}"' in audit, action
