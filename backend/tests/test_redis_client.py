from __future__ import annotations


class FakeRedis:
    def __init__(self, keys=()):
        self.keys = set(keys)
        self.deleted: list[str] = []

    def delete(self, *keys):
        self.deleted.extend(keys)
        count = sum(1 for key in keys if key in self.keys)
        self.keys.difference_update(keys)
        return count

    def scan_iter(self, match: str, count: int):
        prefix = match[:-1] if match.endswith("*") else match
        return iter(sorted(key for key in self.keys if key.startswith(prefix)))


def test_cache_delete_prefixes_every_key(monkeypatch):
    from app.core import redis_client

    fake = FakeRedis({
        "school-lifecycle:test:auth:subject:1:db-2",
        "school-lifecycle:test:auth:jti:abc",
    })
    monkeypatch.setattr(redis_client, "get_redis", lambda: fake)

    deleted = redis_client.cache_delete("auth:subject:1:db-2", "auth:jti:abc")

    assert deleted == 2
    assert fake.keys == set()


def test_cache_delete_pattern_scans_in_batches(monkeypatch):
    from app.core import redis_client

    fake = FakeRedis({
        "school-lifecycle:test:auth:subject:1:db-1",
        "school-lifecycle:test:auth:subject:1:db-2",
        "school-lifecycle:test:auth:subject:2:db-3",
    })
    monkeypatch.setattr(redis_client, "get_redis", lambda: fake)

    deleted = redis_client.cache_delete_pattern("auth:subject:1:*", batch_size=1)

    assert deleted == 2
    assert fake.keys == {"school-lifecycle:test:auth:subject:2:db-3"}
