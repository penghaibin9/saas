from app.services import mobile_read_cache as cache


def _user(**overrides):
    value = {
        "tenantId": "1001",
        "userType": "TEACHER",
        "currentRoleCode": "SCHOOL_ADMIN",
        "userId": "u-1",
        "loginName": "teacher01",
        "activeContextId": "ctx-1",
    }
    value.update(overrides)
    return value


def test_cache_key_isolated_by_tenant_user_role_and_endpoint():
    base = _user()
    key = cache.mobile_read_cache_key(base, "teacher-overview")
    assert key != cache.mobile_read_cache_key(_user(tenantId="1002"), "teacher-overview")
    assert key != cache.mobile_read_cache_key(_user(userId="u-2"), "teacher-overview")
    assert key != cache.mobile_read_cache_key(_user(currentRoleCode="COUNSELOR"), "teacher-overview")
    assert key != cache.mobile_read_cache_key(base, "teacher-todos")


def test_cache_hit_skips_loader(monkeypatch):
    monkeypatch.setattr(cache, "cache_get_json", lambda _key: {"value": 7})
    calls = []
    result = cache.cached_mobile_read(_user(), "teacher-overview", lambda: calls.append(1))
    assert result == {"value": 7}
    assert calls == []


def test_cache_miss_stores_success_dict(monkeypatch):
    stored = {}
    monkeypatch.setattr(cache, "cache_get_json", lambda _key: None)
    monkeypatch.setattr(
        cache,
        "cache_set_json",
        lambda key, value, ttl: stored.update(key=key, value=value, ttl=ttl) or True,
    )
    result = cache.cached_mobile_read(_user(), "teacher-overview", lambda: {"value": 9})
    assert result == {"value": 9}
    assert stored["value"] == {"value": 9}
    assert stored["ttl"] == 8


def test_non_dict_result_is_not_cached(monkeypatch):
    writes = []
    monkeypatch.setattr(cache, "cache_get_json", lambda _key: None)
    monkeypatch.setattr(cache, "cache_set_json", lambda *args: writes.append(args))
    assert cache.cached_mobile_read(_user(), "x", lambda: [1, 2]) == [1, 2]
    assert writes == []
