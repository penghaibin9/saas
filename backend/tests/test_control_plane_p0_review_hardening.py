"""Regression contracts for findings from the final PR #189 pre-merge review."""
from __future__ import annotations

import hashlib
import importlib.util
import time
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import delete, select

from app.core.exceptions import AppException

ROOT = Path(__file__).resolve().parents[1]


def _load_script(filename: str):
    path = ROOT / "scripts" / filename
    spec = importlib.util.spec_from_file_location(f"review_script_{filename}", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def _write_restore_evidence(path: Path, *, explicit_file_verification: bool) -> None:
    lines = [
        "backup_set_id=review-backup-1",
        f"manifest_sha256={'a' * 64}",
        "backup_age_seconds=10",
        "max_backup_age_seconds=20",
        "restore_seconds=12",
        "max_restore_seconds=30",
        "table_count=10",
        "index_count=20",
        "foreign_key_count=0",
        "active_tenant_count=1",
        "upload_entry_count=0",
        "local_file_object_count=0",
        "local_file_object_hashed_count=0",
        "workflow_run_id=review",
        "completed_at_utc=2026-08-21T00:00:00Z",
    ]
    if explicit_file_verification:
        lines.append("file_object_verification_executed=true")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    Path(str(path) + ".sha256").write_text(f"{digest}  {path.name}\n", encoding="utf-8")


def test_review_dr_zero_file_count_is_not_vacuously_verified(tmp_path):
    recorder = _load_script("record_recovery_evidence.py")
    from app.services.machine_recovery_evidence_service import _passed_contract

    evidence = tmp_path / "restore.env"
    _write_restore_evidence(evidence, explicit_file_verification=False)
    payload = recorder._restore_payload(evidence)
    assert payload["detail"]["localFileObjectCount"] == 0
    assert payload["detail"]["fileObjectVerificationExecuted"] is False
    assert payload["assertions"]["fileObjectsVerified"] is False
    with pytest.raises(AppException):
        _passed_contract(payload)

    # Zero FileObjects may be GREEN only when the machine wrapper explicitly
    # queried the restored DB and certified that zero is the real row count.
    _write_restore_evidence(evidence, explicit_file_verification=True)
    payload = recorder._restore_payload(evidence)
    assert payload["detail"]["fileObjectVerificationExecuted"] is True
    assert payload["assertions"]["fileObjectsVerified"] is True
    _passed_contract(payload)


def test_review_machine_restore_wrapper_forces_complete_file_hash_check():
    wrapper = (ROOT.parent / "deploy" / "backup" / "machine-restore-drill.sh").read_text(encoding="utf-8")
    assert 'MIN_RESTORED_LOCAL_FILE_OBJECTS="$local_file_object_count"' in wrapper
    assert 'MIN_RESTORED_HASHED_FILE_OBJECTS="$local_file_object_count"' in wrapper
    assert "file_object_verification_executed=true" in wrapper
    assert "t_file_object" in wrapper


def test_review_global_ip_risk_bucket_is_not_owned_by_last_tenant(db_mode):
    # Importing the aggregate router installs the production P0 authority guard.
    import app.api.v1.router  # noqa: F401
    from app.db.session import get_sessionmaker
    from app.models.auth_risk import AuthRiskState
    from app.services import auth_risk_service as risk

    db = get_sessionmaker()()
    try:
        db.execute(delete(AuthRiskState).where(AuthRiskState.risk_type == risk.LOGIN_IP))
        db.commit()
    finally:
        db.close()

    result = risk.record_failure(
        "203.0.113.88",
        threshold=20,
        lock_seconds=900,
        risk_type=risk.LOGIN_IP,
        tenant_id=987654321,
    )
    assert result is not None

    db = get_sessionmaker()()
    try:
        row = db.scalars(select(AuthRiskState).where(
            AuthRiskState.risk_type == risk.LOGIN_IP,
            AuthRiskState.is_deleted.is_(False),
        )).first()
        assert row is not None
        assert row.tenant_id is None
    finally:
        db.close()


def test_review_tenant_freeze_revokes_refresh_for_soft_deleted_users(db_mode):
    from app.core.security import hash_password
    from app.db.session import get_sessionmaker
    from app.models import AuthRefreshToken, User
    from app.services import tenant_offboarding_service as offboarding

    tenant_id = 987654322
    db = get_sessionmaker()()
    try:
        user = User(
            tenant_id=tenant_id,
            login_name="review-soft-deleted-platform-user",
            real_name="Review Soft Deleted",
            password_hash=hash_password("Review-Password-123!"),
            user_type="TEACHER",
            status="DISABLED",
            is_deleted=True,
        )
        db.add(user)
        db.flush()
        refresh = AuthRefreshToken(
            token_hash="b" * 64,
            user_id=f"db-{int(user.id)}",
            claims_json={"userId": f"db-{int(user.id)}", "tenantId": str(tenant_id)},
            expires_at=datetime.utcnow() + timedelta(days=1),
        )
        db.add(refresh)
        db.commit()

        removed = offboarding._revoke_refresh_by_tenant(db, tenant_id)
        assert removed == 1
        assert db.scalar(select(AuthRefreshToken.id).where(AuthRefreshToken.user_id == f"db-{int(user.id)}")) is None
    finally:
        db.rollback()
        db.close()


def test_review_native_platform_totp_reaches_signed_mfa_assurance(db_mode):
    import app.api.v1.router  # noqa: F401
    from app.core.platform_assurance import assert_recent_platform_auth
    from app.core.security import decode_token, hash_password
    from app.db.session import get_sessionmaker
    from app.models import PlatformConfig, User
    from app.services import platform_mfa_service as mfa

    db = get_sessionmaker()()
    try:
        user = User(
            tenant_id=0,
            login_name="review-platform-mfa-admin",
            real_name="Review Platform Admin",
            password_hash=hash_password("Review-Platform-Password-123!"),
            user_type="PLATFORM_SUPER_ADMIN",
            status="ACTIVE",
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        user_pk = int(user.id)
    finally:
        db.close()

    now = int(time.time())
    principal = {
        "userId": f"db-{user_pk}",
        "loginName": "review-platform-mfa-admin",
        "realName": "Review Platform Admin",
        "userType": "PLATFORM_SUPER_ADMIN",
        "tenantCode": "platform",
        "tenantId": "0",
        "activeContextId": "legacy:PLATFORM_SUPER_ADMIN",
        "currentRoleCode": "PLATFORM_SUPER_ADMIN",
        "permissionVersion": None,
        "authTime": now,
        "tokenIat": now,
        "amr": [],
        "acr": None,
    }

    started = mfa.start_enrollment(principal, password="Review-Platform-Password-123!")
    assert started["status"] == "PENDING"
    assert started["provisioningUri"].startswith("otpauth://totp/")
    secret = started["secret"]

    db = get_sessionmaker()()
    try:
        row = db.scalars(select(PlatformConfig).where(
            PlatformConfig.tenant_id == 0,
            PlatformConfig.config_type == "PLATFORM_MFA_TOTP",
            PlatformConfig.config_key == f"user:{user_pk}",
        )).first()
        assert row is not None
        assert row.config_json["secretEncrypted"] != secret
        assert str(row.config_json["secretEncrypted"]).startswith("k")
    finally:
        db.close()

    counter = int(time.time() // 30)
    code = mfa._totp_for_counter(secret, counter)
    confirmed = mfa.confirm_enrollment(principal, code=code)
    claims = decode_token(confirmed["accessToken"])
    assert "totp" in claims["amr"]
    assert "mfa" in claims["acr"]
    assert int(claims["exp"]) - int(claims["iat"]) == 600
    assert_recent_platform_auth(
        {"authTime": claims["auth_time"], "amr": claims["amr"], "acr": claims["acr"]},
        require_mfa=True,
    )

    # The same TOTP time-step may not be replayed for a second elevation token.
    with pytest.raises(AppException):
        mfa.step_up(principal, code=code)


def test_review_machine_passed_evidence_requires_sha_and_measured_objectives():
    from app.services.machine_recovery_evidence_service import canonical_evidence, _passed_contract

    backup = {
        "runId": "review-backup-metrics",
        "runType": "BACKUP",
        "source": "MACHINE",
        "status": "PASSED",
        "manifestSha256": "a" * 64,
        "finishedAt": "2026-08-21T00:00:00Z",
        "assertions": {
            "manifestVerified": True,
            "databaseShaVerified": True,
            "offsiteReadbackVerified": True,
            "immutableRemoteConfirmed": True,
        },
    }
    with pytest.raises(AppException):
        _passed_contract(canonical_evidence(backup))

    with pytest.raises(AppException):
        canonical_evidence({**backup, "manifestSha256": "not-a-sha256"})

    restore = {
        "runId": "review-restore-metrics",
        "runType": "RESTORE",
        "source": "MACHINE",
        "status": "PASSED",
        "manifestSha256": "b" * 64,
        "finishedAt": "2026-08-21T00:00:00Z",
        "rpoSeconds": 10,
        "targetRpoSeconds": 20,
        "assertions": {
            "manifestVerified": True,
            "databaseRestoreVerified": True,
            "schemaVerified": True,
            "indexesVerified": True,
            "fileObjectsVerified": True,
        },
    }
    with pytest.raises(AppException):
        _passed_contract(canonical_evidence(restore))


def test_review_machine_health_red_dominates_unknown(db_mode):
    from app.db.session import get_sessionmaker
    from app.models.recovery_run import RecoveryRun
    from app.services.machine_recovery_evidence_service import machine_health, record_machine_evidence

    db = get_sessionmaker()()
    try:
        db.execute(delete(RecoveryRun))
        db.commit()
    finally:
        db.close()

    record_machine_evidence({
        "runId": "review-known-failed-backup",
        "runType": "BACKUP",
        "source": "MACHINE",
        "status": "FAILED",
        "assertions": {},
        "detail": {"error": "review failure"},
        "finishedAt": datetime.utcnow().isoformat(),
    })
    health = machine_health()
    assert health["backup"]["status"] == "RED"
    assert health["restore"]["status"] == "UNKNOWN"
    assert health["status"] == "RED"


def test_review_purge_finalize_failure_is_retryable_but_irreversible(db_mode):
    from app.db.session import get_sessionmaker
    from app.models.tenant_offboarding import TenantOffboardingJob
    from app.services import tenant_offboarding_service as offboarding

    tenant_id = 987654323
    db = get_sessionmaker()()
    try:
        job = TenantOffboardingJob(
            tenant_id=tenant_id,
            state="PURGING",
            reason="review finalization retry contract",
            expected_tenant_version=0,
            preview_json={},
            result_json={},
        )
        db.add(job)
        db.commit()
        db.refresh(job)
        job_id = int(job.id)
    finally:
        db.close()

    evidence = {"evidenceSha256": "c" * 64, "deletedRowCount": 7}
    offboarding._mark_purge_failed(
        job_id,
        tenant_id,
        RuntimeError("final tombstone transaction failed"),
        evidence=evidence,
    )

    out = offboarding.get_job(job_id)
    assert out["state"] == "FAILED"
    assert out["cancellable"] is False
    assert out["irreversible"] is True
    assert out["result"]["purgeEvidence"] == evidence
    assert "final tombstone transaction failed" in out["lastError"]


def test_review_purge_runtime_mutex_survives_worker_crash_contract():
    source = (ROOT / "app" / "services" / "control_plane_p0_offboarding_guard.py").read_text(encoding="utf-8")
    assert "SELECT GET_LOCK(:lock_name, 0)" in source
    assert "SELECT RELEASE_LOCK(:lock_name)" in source
    assert "TENANT_PURGE_ALREADY_RUNNING" in source
    assert 'job.state == "PURGING"' in source
    assert 'job.state = "FAILED"' in source
    assert "resuming idempotently" in source
