from app.core.affairs_security import _derive_keys


def test_affairs_security_derives_numeric_db_user_id_for_dorm_manager_binding():
    keys = _derive_keys({
        "userId": "db-10",
        "loginName": "e2e_sa009_dorm",
        "activeContextId": "role:19",
    })

    assert "db-10" in keys
    assert "10" in keys
    assert "e2e_sa009_dorm" in keys


def test_affairs_security_preserves_legacy_user_and_context_key_derivation():
    keys = _derive_keys({
        "userId": "u_counselor01",
        "loginName": "counselor_login",
        "activeContextId": "ctx_teacher001",
    })

    assert {"u_counselor01", "counselor01", "counselor_login", "teacher001"}.issubset(keys)
