"""Regression contracts for the four control-plane P0 closures.

These tests intentionally focus on safety authorities and wiring rather than
retesting every legacy control-plane screen.  They fail loudly when a future
refactor restores process-local auth safety, lets manual DR evidence turn green,
leaves a tenant table unclassified, or forgets the offboarding retry guard.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
from sqlalchemy import delete

from app.core.exceptions import AppException


ROOT = Path(__file__).resolve().parents[1]


def _load_revision(filename: str):
    path = ROOT / "alembic" / "versions" / filename
    spec = importlib.util.spec_from_file_location(f"p0_revision_{filename}", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_p0_router_installs_all_three_runtime_authorities():
    # conftest imports app.main first, but importing the router again is harmless
    # and documents the intended application-startup authority boundary.
    import app.api.v1.router  # noqa: F401
    from app.services import tenant_offboarding_service as offboarding
    from app.services import control_plane_p0_auth_guard as auth_guard
    from app.services import control_plane_p0_dr_guard as dr_guard
    from app.services import control_plane_p0_offboarding_guard as offboarding_guard

    assert auth_guard._INSTALLED is True
    assert dr_guard._INSTALLED is True
    assert offboarding_guard._INSTALLED is True
    assert {"BLOCKED", "FAILED"}.issubset(offboarding.ACTIVE_STATES)
    assert "BLOCKED" in offboarding.CANCELLABLE_STATES


def test_p0_purge_registry_classifies_every_current_tenant_table():
    from app.services.tenant_purge_registry import REVIEWED_ALEMBIC_HEAD, inventory

    registry = inventory()
    assert registry["complete"] is True, registry["unknownTables"]
    assert registry["unknownTables"] == []
    assert registry["fileObjectTableCount"] == 1
    assert registry["purgeTableCount"] > 0
    assert registry["reviewedAlembicHead"] == REVIEWED_ALEMBIC_HEAD == "20260820_ctrl_offboarding"


def test_p0_purge_registry_locks_reviewed_exception_semantics():
    from app.services.tenant_purge_registry import PURGE, RETAIN, classify_table

    retained = {
        "t_order",
        "t_incident_tenant",
        "t_change_impact",
        "t_sod_violation",
        "t_emergency_access_session",
        "t_tenant_usage_snapshot",
        "t_tenant_fair_use_violation",
    }
    purged = {
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

    assert {name for name in retained if classify_table(name).classification != RETAIN} == set()
    assert {name for name in purged if classify_table(name).classification != PURGE} == set()


def test_p0_purge_registry_blocks_any_unreviewed_schema_head():
    from app.services.tenant_purge_registry import REVIEWED_ALEMBIC_HEAD, assert_schema_head_reviewed

    assert_schema_head_reviewed([REVIEWED_ALEMBIC_HEAD])
    with pytest.raises(AppException) as exc:
        assert_schema_head_reviewed(["20991231_future_schema"])
    assert exc.value.code == "TENANT_PURGE_SCHEMA_NOT_REVIEWED"
    with pytest.raises(AppException):
        assert_schema_head_reviewed([REVIEWED_ALEMBIC_HEAD, "unexpected_second_head"])


def test_p0_auth_risk_fails_closed_without_database_in_strict_env(monkeypatch):
    from app.services import auth_risk_service as risk

    monkeypatch.setattr(risk, "db_enabled", lambda: False)
    monkeypatch.setattr(risk.settings, "APP_ENV", "production")
    monkeypatch.setattr(risk.settings, "DEPLOYMENT_MODE", "production")

    with pytest.raises(AppException) as exc:
        risk.login_locked("tenant-account-hash")
    assert exc.value.code == "AUTH_RISK_STORE_UNAVAILABLE"
    assert exc.value.http_status == 503


def test_p0_effective_policy_is_explicit_and_hard_bounded_when_storage_degraded(monkeypatch):
    from app.services import effective_security_policy_service as policy

    monkeypatch.setattr(policy, "db_enabled", lambda: False)
    out = policy.resolve_login_policy(tenant_id=123456, principal_plane=policy.TENANT)

    assert out["tenantId"] == 123456
    assert out["principalPlane"] == "TENANT"
    assert out["dataQuality"] == "DEGRADED"
    assert out["loginFailMaxTimes"] == 5
    assert out["loginFailLockMinutes"] == 15
    assert out["captchaAfterFailures"] <= out["loginFailMaxTimes"] - 1
    assert len(out["policyRevision"]) == 16


def test_p0_manual_dr_records_can_never_make_health_green(db_mode):
    # app.main/router installation makes legacy.governance_overview machine-only.
    from app.db.session import get_sessionmaker
    from app.models.disaster_recovery import BackupEvidence, RestoreDrill
    from app.models.recovery_run import RecoveryRun
    from app.services import disaster_recovery_service as dr

    db = get_sessionmaker()()
    try:
        db.execute(delete(RestoreDrill))
        db.execute(delete(BackupEvidence))
        db.execute(delete(RecoveryRun))
        db.commit()
    finally:
        db.close()

    evidence = dr.record_backup_evidence(None, {
        "backupType": "DATABASE_DUMP",
        "method": "MANUAL_CONFIRMED",
        "status": "SUCCEEDED",
        "locationRef": "manual-note-only",
    })
    dr.record_restore_drill(None, {
        "backupEvidenceId": evidence["id"],
        "drillType": "MANUAL_CONFIRMED",
        "status": "PASSED",
        "targetDescription": "manual record must not authorize green",
    })

    board = dr.governance_overview()
    assert board["machineHealth"]["authority"] == "MACHINE_ONLY"
    assert board["machineHealth"]["manualEvidenceHealthEligible"] is False
    assert board["machineHealth"]["status"] == "UNKNOWN"
    assert board["restoreDrill"]["hasPassedDrill"] is False
    assert board["restoreDrill"]["healthAuthority"] == "MACHINE_ONLY"


def test_p0_machine_restore_green_requires_complete_file_hash_verification():
    from app.services.machine_recovery_evidence_service import _passed_contract

    evidence = {
        "status": "PASSED",
        "runType": "RESTORE",
        "rpoSeconds": 10,
        "targetRpoSeconds": 20,
        "rtoSeconds": 30,
        "targetRtoSeconds": 60,
        "assertions": {
            "manifestVerified": True,
            "databaseRestoreVerified": True,
            "schemaVerified": True,
            "indexesVerified": True,
            "fileObjectsVerified": False,
        },
    }
    with pytest.raises(AppException) as exc:
        _passed_contract(evidence)
    assert exc.value.code == "VALIDATION_ERROR"
    assert "fileObjectsVerified" in str(exc.value.message)


def test_p0_machine_backup_green_requires_immutable_remote_confirmation():
    from app.services.machine_recovery_evidence_service import _passed_contract

    evidence = {
        "status": "PASSED",
        "runType": "BACKUP",
        "rpoSeconds": 10,
        "targetRpoSeconds": 20,
        "rtoSeconds": None,
        "targetRtoSeconds": None,
        "assertions": {
            "manifestVerified": True,
            "databaseShaVerified": True,
            "offsiteReadbackVerified": True,
            "immutableRemoteConfirmed": False,
        },
    }
    with pytest.raises(AppException) as exc:
        _passed_contract(evidence)
    assert exc.value.code == "VALIDATION_ERROR"
    assert "immutableRemoteConfirmed" in str(exc.value.message)


def test_p0_migrations_form_one_linear_chain_after_academic_final_head():
    auth = _load_revision("20260820_control_plane_auth_risk.py")
    recovery = _load_revision("20260820_control_plane_recovery_evidence.py")
    offboarding = _load_revision("20260820_control_plane_tenant_offboarding.py")

    assert auth.down_revision == "20260818_acad_bc_final"
    assert recovery.down_revision == auth.revision
    assert offboarding.down_revision == recovery.revision


def test_p0_machine_evidence_wrappers_use_production_virtualenv():
    backup = (ROOT.parent / "deploy" / "backup" / "machine-backup-runner.sh").read_text(encoding="utf-8")
    restore = (ROOT.parent / "deploy" / "backup" / "machine-restore-drill.sh").read_text(encoding="utf-8")
    service = (ROOT.parent / "deploy" / "systemd" / "school-lifecycle-backup.service").read_text(encoding="utf-8")

    expected_python = 'PYTHON_BIN="${RECOVERY_PYTHON_BIN:-$REPO_ROOT/backend/.venv/bin/python}"'
    assert expected_python in backup
    assert expected_python in restore
    assert "machine-backup-runner.sh" in service
    assert "backup-runner.sh" not in service.split("ExecStart=", 1)[-1].splitlines()[0]
