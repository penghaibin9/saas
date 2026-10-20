"""Revocation must not reuse an earlier authorization snapshot.

Unit cases use explicit cache/session doubles. The final test uses two spawned
Python processes and the repository's isolated MySQL db_mode fixture; it is not
an HTTP or real-Redis test and never connects to a production school database.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from types import SimpleNamespace
import multiprocessing
import time
import uuid

import pytest


def _unit_store(monkeypatch, *, cached=None, row=None, error=False, available=True):
    from app.core import config, redis_client, token_store as store
    from app.db import session

    monkeypatch.setattr(config, "settings", SimpleNamespace(is_prod=True, APP_ENV="production"))
    monkeypatch.setattr(session, "db_enabled", lambda: True)
    monkeypatch.setattr(store, "_allowed_jti", {})
    monkeypatch.setattr(store, "_blocked_jti", {})
    writes, reads = [], []
    monkeypatch.setattr(redis_client, "cache_get", lambda key: reads.append(key) or cached)
    monkeypatch.setattr(redis_client, "cache_set", lambda *args: writes.append(args))

    class Session:
        calls = 0
        closed = False

        def scalars(self, statement):
            self.calls += 1
            if error:
                raise RuntimeError("injected database outage")
            return SimpleNamespace(first=lambda: row)

        def close(self):
            self.closed = True

    db = Session()
    monkeypatch.setattr(store, "_db", lambda **kwargs: db if available else None)
    return store, db, reads, writes


def test_shared_denial_wins_over_old_worker_allow(monkeypatch):
    store, db, reads, _ = _unit_store(monkeypatch, cached="1")
    store._allowed_jti["revoked"] = time.time() + 60
    assert store.jti_blocked("revoked") is True
    assert reads == ["auth:jti:revoked"] and db.calls == 0
    assert "revoked" not in store._allowed_jti


@pytest.mark.parametrize("cached", [None, "0"])
@pytest.mark.parametrize("key", ["access-jti", "auth-session:browser-session"])
def test_cache_miss_or_old_zero_cannot_hide_durable_revocation(monkeypatch, cached, key):
    row = SimpleNamespace(expires_at=datetime.utcnow() + timedelta(minutes=10))
    store, db, _, writes = _unit_store(monkeypatch, cached=cached, row=row)
    assert store.jti_blocked(key) is True
    assert db.calls == 1 and db.closed
    assert writes and all(args[1] == "1" for args in writes)


def test_expired_local_denial_does_not_short_circuit_shared_recheck(monkeypatch):
    store, _, reads, _ = _unit_store(monkeypatch, cached="1")
    store._blocked_jti["renewed-denial"] = time.time() - 1
    assert store.jti_blocked("renewed-denial") is True
    assert len(reads) == 1


def test_absence_is_never_written_as_allow_cache(monkeypatch):
    store, db, _, writes = _unit_store(monkeypatch)
    assert store.jti_blocked("not-blocked") is False
    assert store.jti_blocked("not-blocked") is False
    assert db.calls == 2 and db.closed
    assert not writes and not store._allowed_jti


@pytest.mark.parametrize("available,error", [(False, False), (True, True)])
def test_unavailable_durable_authority_fails_closed(monkeypatch, available, error):
    from app.core.exceptions import AppException
    store, db, _, _ = _unit_store(monkeypatch, available=available, error=error)
    with pytest.raises(AppException) as exc:
        store.jti_blocked("must-not-allow")
    assert exc.value.http_status == 503
    if available:
        assert db.closed


def test_security_test_reset_includes_installed_dev_limiter(monkeypatch):
    from app.core import token_store
    from app.services import control_plane_auth_service as authority
    from collections import deque

    monkeypatch.setattr(authority, "_DEV_BUCKETS", {"login:testclient": deque([time.time()] * 10)})
    monkeypatch.setattr(token_store, "_buckets", {"old-limiter": deque([time.time()])})
    token_store.reset_all_for_tests()
    assert not authority._DEV_BUCKETS
    assert not token_store._buckets


def _mysql_process(connection, database_url, key):
    """Child process with its own L1 state, no Redis and a real MySQL sessionmaker."""
    engine = None
    try:
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        from sqlalchemy.pool import NullPool
        from app.core import config, redis_client, token_store
        from app.db import session

        engine = create_engine(database_url, poolclass=NullPool)
        maker = sessionmaker(bind=engine, expire_on_commit=False)
        config.settings.APP_ENV = "production"
        session.db_enabled = lambda: True
        token_store._db = lambda **kwargs: maker()
        # Simulate a stale Redis negative entry as well as an earlier worker L1 allow.
        redis_client.cache_get = lambda value: "0"
        redis_client.cache_set = lambda *args: True
        token_store._allowed_jti[key] = time.time() + 3600
        token_store._blocked_jti.clear()
        connection.send(("ready", token_store.jti_blocked(key)))
        while True:
            command = connection.recv()
            if command == "stop":
                break
            if command == "block":
                result = token_store.block_jti(key, time.time() + 300)
            elif command == "check":
                result = token_store.jti_blocked(key)
            else:
                raise ValueError("unknown test command")
            connection.send(("ok", result))
    except BaseException as exc:
        # Never put database_url (which includes test credentials) in failures.
        connection.send(("error", type(exc).__name__))
    finally:
        if engine is not None:
            engine.dispose()
        connection.close()


def _receive(connection, expected_status):
    assert connection.poll(40), "revocation worker did not respond"
    status, value = connection.recv()
    assert status == expected_status, (status, value)
    return value


@pytest.mark.parametrize("prefix", ["access:", "auth-session:"])
def test_mysql_process_revocation_after_another_worker_acknowledges_commit(db_mode, prefix):
    from app.db.session import get_sessionmaker
    from sqlalchemy import delete
    from app.models import AuthBlockedJti

    with get_sessionmaker()() as db:
        url = db.get_bind().url
        assert url.get_backend_name() == "mysql"
        database_url = url.render_as_string(hide_password=False)
    key = prefix + "pr265-" + uuid.uuid4().hex
    context = multiprocessing.get_context("spawn")
    workers, connections = [], []
    try:
        for _ in range(2):
            parent, child = context.Pipe()
            process = context.Process(target=_mysql_process, args=(child, database_url, key))
            process.start()
            child.close()
            workers.append(process)
            connections.append(parent)
        for connection in connections:
            assert _receive(connection, "ready") is False
        connections[0].send("block")
        assert _receive(connections[0], "ok") is True
        connections[1].send("check")
        assert _receive(connections[1], "ok") is True
    finally:
        for connection in connections:
            try:
                connection.send("stop")
            except (BrokenPipeError, EOFError, OSError):
                pass
        for process in workers:
            process.join(timeout=5)
            if process.is_alive():
                process.terminate()
                process.join(timeout=5)
        for connection in connections:
            connection.close()
        with get_sessionmaker()() as db:
            db.execute(delete(AuthBlockedJti).where(AuthBlockedJti.jti == key))
            db.commit()
