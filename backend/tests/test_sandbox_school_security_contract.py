"""standard-20k 合并前安全合同：凭据、原子审计、tenant fail-closed 与门禁覆盖。"""
from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def _text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_standard_20k_credentials_are_not_repository_known(monkeypatch):
    from app.services import sandbox_school_credentials as credentials

    monkeypatch.setattr(credentials, "hash_password", lambda value: f"HASH:{value}")
    monkeypatch.setenv("SANDBOX_ADMIN2_PASSWORD", "Admin-Only-Strong-2026")
    monkeypatch.setenv("SANDBOX_TEACHER2_PASSWORD", "Teacher-Only-Strong-2026")
    monkeypatch.setenv("SANDBOX_STUDENT2_PASSWORD", "Student-Only-Strong-2026")

    hashes = credentials.public_account_password_hashes()
    assert hashes == {
        "admin2": "HASH:Admin-Only-Strong-2026",
        "teacher2": "HASH:Teacher-Only-Strong-2026",
        "student2": "HASH:Student-Only-Strong-2026",
    }

    master = _text("backend/app/services/sandbox_school_master_seed.py")
    assert "Sbx@2026!" not in master
    assert 'hash_password("123456")' not in master
    assert "public_account_password_hashes()" in master
    assert master.count("opaque_background_password_hash()") == 2

    reset_script = _text("backend/scripts/reset_sandbox_school.py")
    assert reset_script.index("public_account_password_hashes()") < reset_script.index("rebuild_school_master_20k(db)")


def test_standard_20k_public_credentials_fail_closed(monkeypatch):
    from app.services import sandbox_school_credentials as credentials

    for env_name in credentials.PUBLIC_PASSWORD_ENVS.values():
        monkeypatch.delenv(env_name, raising=False)
    with pytest.raises(RuntimeError, match="缺少环境凭据"):
        credentials.public_account_password_hashes()

    monkeypatch.setenv("SANDBOX_ADMIN2_PASSWORD", "same-password-2026")
    monkeypatch.setenv("SANDBOX_TEACHER2_PASSWORD", "same-password-2026")
    monkeypatch.setenv("SANDBOX_STUDENT2_PASSWORD", "other-password-2026")
    with pytest.raises(RuntimeError, match="三份不同口令"):
        credentials.public_account_password_hashes()


def test_story_reset_is_tenant_scoped_and_transaction_owned_by_route():
    service = _text("backend/app/services/sandbox_school_story_reset.py")
    route = _text("backend/app/api/v1/sandbox_story_api.py")

    assert "chen_class = db.get(SchoolClass, chen.class_id)" not in service
    assert "SchoolClass.tenant_id == tenant_id" in service
    assert "SchoolClass.is_deleted.is_(False)" in service
    assert "db.commit()" not in service
    assert "db_service.audit_insert_in_session(" in route
    assert route.index("db_service.audit_insert_in_session(") < route.index("db.commit()")
    assert "except Exception:\n        db.rollback()\n        raise" in route


def test_standard_profile_blocks_legacy_reset(monkeypatch):
    from app.core.exceptions import AppException
    from app.services import sandbox_school_profile as profile_svc
    from app.services import sandbox_service

    class FakeDb:
        rolled_back = False

        def rollback(self):
            self.rolled_back = True

    db = FakeDb()
    monkeypatch.setattr(sandbox_service, "sandbox_row_counts", lambda _db: {"t_student_profile": 20_000})
    monkeypatch.setattr(profile_svc, "classify_sandbox_profile", lambda _db, _tid: {
        "profile": profile_svc.PROFILE_STANDARD,
        "students": 20_000,
        "colleges": 8,
        "majors": 32,
        "classes": 384,
        "backgroundStaffAccounts": 1_280,
    })

    with pytest.raises(AppException) as exc:
        sandbox_service.reset_sandbox(db, dry_run=False)
    assert exc.value.code == "DATA_CONFLICT"
    assert "standard-20k" in exc.value.message
    assert db.rolled_back is True


def test_midnight_auto_reset_feature_is_removed():
    files = {
        "config": _text("backend/app/core/config.py"),
        "web": _text("backend/app/main.py"),
        "external": _text("backend/scripts/run_scheduled_jobs.py"),
        "env": _text("backend/.env.example"),
        "systemd_env": _text("deploy/env/backend.systemd.env.example"),
        "portal_review": _text(".github/workflows/student-portal-v5-full-review.yml"),
    }
    forbidden = (
        "SANDBOX_AUTO_RESET",
        "sandbox_auto_reset",
        "sandbox-midnight-reset",
        "reset_sandbox_if_due",
        "seconds_until_next_midnight",
    )
    for name, text in files.items():
        for token in forbidden:
            assert token not in text, f"{name} still contains removed midnight auto-reset token: {token}"


def test_20k_gate_tracks_effective_grade_policy_and_security_contract():
    workflow = _text(".github/workflows/sandbox-20k-data-gate.yml")

    assert "backend/app/modules/academic_affairs/services/academic_affairs_effective_grade_policy_service.py" in workflow
    assert "backend/app/services/sandbox_school_*.py" in workflow
    assert "app/services/sandbox_school_credentials.py" in workflow
    assert "backend/tests/test_sandbox_school_security_contract.py" in workflow
    assert "tests/test_sandbox_school_security_contract.py" in workflow
