from pathlib import Path
from types import SimpleNamespace

import pytest

from app.core.exceptions import AppException


ROOT = Path(__file__).resolve().parents[2]


def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_formal_approval_runtime_installs_production_guard():
    from app.services import approval_runtime_service as runtime

    assert runtime._production_guard_installed is True
    package = read("backend/app/services/__init__.py")
    assert '_APPROVAL_RUNTIME_MODULE = "approval_runtime_service"' in package
    assert "install_approval_guard(module)" in package


def test_transfer_and_reject_flags_are_persisted_policy_driven():
    from app.services.approval_production_guard import _action_flags

    enabled = SimpleNamespace(allow_transfer=True, allow_reject=False)
    active_node = SimpleNamespace(status="ACTIVE", approver_role_code="COUNSELOR")
    flags = _action_flags(enabled, active_node)
    assert flags == {"REJECT": False, "TRANSFER": True}

    assert _action_flags(enabled, None)["TRANSFER"] is False
    disabled = SimpleNamespace(allow_transfer=False, allow_reject=True)
    assert _action_flags(disabled, active_node) == {"REJECT": True, "TRANSFER": False}


def test_transfer_guard_requires_current_node_role_membership_and_atomic_write():
    guard = read("backend/app/services/approval_production_guard.py")

    assert "definition.allow_transfer" in guard
    assert "definition.allow_reject" in guard
    assert "node.approver_role_code" in guard
    assert "UserRole.user_id == target_id" in guard
    assert "Role.role_code == role_code" in guard
    assert "转办目标不属于当前节点责任角色" in guard
    assert "with_for_update()" in guard
    assert "atomic_versioned_update(" in guard
    assert 'expected_status="PENDING"' in guard
    assert '"targetRole": role_code' in guard


def test_external_scheduler_runs_approval_export_worker_for_each_tenant():
    scheduler = read("backend/scripts/run_scheduled_jobs.py")

    assert "approval_export_service as approval_export" in scheduler
    assert 'f"approval_export:{tenant_id}"' in scheduler
    assert "approval_export.run_pending(" in scheduler
    assert 'worker_id=f"scheduler-approval:{tenant_id}"' in scheduler
    assert scheduler.index("approval_export.run_pending(") < scheduler.index("def job_academic_future_effective")


def test_approval_batch_and_export_use_durable_idempotency_entrypoint():
    routes = read("backend/app/api/v1/approval.py")
    idem = read("backend/app/core/idempotency.py")

    assert "begin_required as idempotency_begin" in routes
    assert '"approval-batch"' in routes
    assert '"approval-export"' in routes
    assert "def begin_required(" in idem
    assert '"IDEMPOTENCY_STORE_UNAVAILABLE"' in idem
    assert "cached, handle = _begin_db(user, operation, key, payload)" in idem


def test_begin_required_falls_back_to_db_when_redis_is_unavailable(monkeypatch):
    from app.core import idempotency as idem
    from app.db import session as db_session

    monkeypatch.setattr(idem, "cache_get_json", lambda _key: None)
    monkeypatch.setattr(idem, "cache_set_json_if_absent", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(db_session, "db_enabled", lambda: True)
    monkeypatch.setattr(
        idem,
        "_begin_db",
        lambda *_args, **_kwargs: (None, ("db:42", "fingerprint")),
    )

    cached, handle = idem.begin_required(
        {"tenantId": "1", "userId": "9"},
        "approval-export",
        "abcdefgh",
        {"scope": "DONE"},
    )
    assert cached is None
    assert handle == ("db:42", "fingerprint")


def test_begin_required_fails_closed_when_no_store_exists(monkeypatch):
    from app.core import idempotency as idem
    from app.db import session as db_session

    monkeypatch.setattr(idem, "cache_get_json", lambda _key: None)
    monkeypatch.setattr(idem, "cache_set_json_if_absent", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(db_session, "db_enabled", lambda: False)

    with pytest.raises(AppException) as exc:
        idem.begin_required(
            {"tenantId": "1", "userId": "9"},
            "approval-batch",
            "abcdefgh",
            {"action": "APPROVE"},
        )
    assert exc.value.code == "IDEMPOTENCY_STORE_UNAVAILABLE"
    assert exc.value.http_status == 503
