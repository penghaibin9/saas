"""P0-NEW：学生目录 fail-closed、审批 assignee、乐观锁强制 version、加密与令牌存储。"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.core.affairs_security import student_directory_scope
from app.core.exceptions import AppException, check_version
from app.core.field_crypto import decrypt_field, encrypt_field, looks_like_fernet
from app.core.optimistic_lock import require_expected_version
from app.core.token_store import consume_refresh, issue_refresh


def test_unknown_role_directory_scope_empty_when_db_off(monkeypatch):
    monkeypatch.setattr("app.db.session.db_enabled", lambda: False)
    class_ids, student_ids = student_directory_scope(
        {"currentRoleCode": "ACADEMIC_TEACHER", "userId": "u1"})
    assert class_ids == set()
    assert student_ids is None


def test_tenant_all_role_unrestricted_when_db_off(monkeypatch):
    monkeypatch.setattr("app.db.session.db_enabled", lambda: False)
    class_ids, student_ids = student_directory_scope(
        {"currentRoleCode": "SCHOOL_ADMIN", "userId": "u1", "userType": "ADMIN"})
    assert class_ids is None and student_ids is None


def test_check_version_requires_value():
    with pytest.raises(AppException) as ei:
        check_version(3, None)
    assert ei.value.code == "VALIDATION_ERROR"
    with pytest.raises(AppException):
        require_expected_version(None)
    check_version(3, 3)


def test_encrypt_decrypt_roundtrip():
    enc = encrypt_field("13800138000")
    assert enc and looks_like_fernet(enc)
    assert decrypt_field(enc) == "13800138000"
    # 历史明文兼容
    assert decrypt_field("13800138000") == "13800138000"


def test_decrypt_rejects_corrupt_ciphertext_in_prod(monkeypatch):
    monkeypatch.setattr("app.core.config.settings.APP_ENV", "production")
    with pytest.raises(AppException) as ei:
        decrypt_field("gAAAA" + ("A" * 80))
    assert ei.value.code == "SENSITIVE_DECRYPT_FAILED"


def test_issue_refresh_fails_closed_when_db_write_fails(monkeypatch):
    monkeypatch.setattr("app.db.session.db_enabled", lambda: True)

    class _BadDb:
        def add(self, *_a, **_k):
            raise RuntimeError("db down")

        def commit(self):
            pass

        def rollback(self):
            pass

        def close(self):
            pass

    monkeypatch.setattr("app.core.token_store._db", lambda required=False: _BadDb())
    with pytest.raises(AppException) as ei:
        issue_refresh({"userId": "db-1"})
    assert ei.value.code == "AUTH_STORE_UNAVAILABLE"


def test_consume_refresh_fails_closed_on_db_error(monkeypatch):
    monkeypatch.setattr("app.db.session.db_enabled", lambda: True)

    class _BadDb:
        def scalars(self, *_a, **_k):
            raise RuntimeError("db down")

        def rollback(self):
            pass

        def close(self):
            pass

    monkeypatch.setattr("app.core.token_store._db", lambda required=False: _BadDb())
    with pytest.raises(AppException) as ei:
        consume_refresh("any-token")
    assert ei.value.code == "AUTH_STORE_UNAVAILABLE"


def test_assert_task_assignee_denies_other_user():
    from app.services.db_service import _assert_task_assignee

    t = MagicMock()
    t.assignee_id = 100
    with pytest.raises(AppException) as ei:
        _assert_task_assignee(t, {"userId": "200", "permissions": []})
    assert ei.value.code == "DATA_NOT_FOUND"
