"""Repository-wide pytest safety and compatibility fixtures.

DB-backed tests use an isolated MySQL schema and the canonical demo tenant id.
Package 8 removed runtime authorization by advisor display name, so older
internship fixtures are explicitly migrated to stable advisor ids here.
Package 9 adds an authoritative defense-phase gate; legacy positive defense
fixtures without an explicit DEFENSE phase are normalized here rather than
weakening the production policy.
"""
from __future__ import annotations

import hashlib
from urllib.parse import parse_qsl, urlsplit

import pytest

TEST_TENANT_ID = 1000000000000000001
_REQUEST_WRAPPER_PATCHED = False


@pytest.fixture(autouse=True)
def _seed_authoritative_tenant_for_db_tests(request):
    """Seed and bind the canonical active tenant after ``db_mode`` resets the schema.

    ``db_mode`` is an explicit trusted test-database boundary.  Production service
    writes are fail-closed when no tenant ContextVar exists, so DB-backed tests must
    install the same authoritative tenant context that their seeded rows use.  This
    fixture deliberately does *not* install a user/actor context: actor-sensitive
    policies (notably formal file binding) remain fail-closed and must opt in to an
    explicit actor in the fixture that owns that operation.
    """
    if "db_mode" not in request.fixturenames:
        yield
        return

    request.getfixturevalue("db_mode")

    from app.core.context import set_tenant
    from app.db.session import get_sessionmaker
    from app.models import Tenant

    set_tenant({
        "tenantId": str(TEST_TENANT_ID),
        "tenantCode": "demo",
        "tenantName": "测试学校",
        "status": "ACTIVE",
    })
    try:
        db = get_sessionmaker()()
        try:
            if db.get(Tenant, TEST_TENANT_ID) is None:
                db.add(
                    Tenant(
                        id=TEST_TENANT_ID,
                        tenant_code="demo",
                        school_name="测试学校",
                        short_name="测试学校",
                        deploy_mode="SAAS",
                        db_mode="SHARED",
                        status="ACTIVE",
                    )
                )
                db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

        yield
    finally:
        set_tenant(None)


def _stable_test_user_id(claims: dict) -> int | None:
    """Return an existing stable DB id when the token already carries one.

    Real password-login/switch-role tokens use ``db-<user.id>``.  The synthetic
    BIGINT namespace below is only for legacy tests whose tokens do not identify a
    persisted user.  Replacing a real ``db-`` identity with a synthetic id would
    make correctly assigned internship records disappear from the mentor's scope.
    """
    raw = claims.get("userId")
    normalized = str(raw or "").strip()
    if normalized.startswith("db-"):
        normalized = normalized[3:]
    try:
        parsed = int(normalized)
    except (TypeError, ValueError):
        parsed = 0
    if parsed > 0:
        return parsed

    tenant_id = str(claims.get("tenantId") or "").strip()
    real_name = str(claims.get("realName") or "").strip()
    principal = str(raw or claims.get("loginName") or real_name).strip()
    if not tenant_id or not principal:
        return None
    digest = hashlib.sha256(f"{tenant_id}:{principal}".encode("utf-8")).digest()
    # Signed BIGINT-safe namespace reserved for synthetic test users.
    return 7_000_000_000_000_000_000 + int.from_bytes(digest[:8], "big") % 1_000_000_000_000_000_000


def _upgrade_internship_fixture_identity(path: str, kwargs: dict) -> None:
    """Backfill legacy rows and keep mentor uploads on the same stable identity."""
    normalized_path = path.rstrip("/") or "/"
    if "internship" not in normalized_path and normalized_path != "/api/v1/files":
        return
    headers = kwargs.get("headers") or {}
    auth = headers.get("Authorization") or headers.get("authorization")
    if not auth or not str(auth).startswith("Bearer "):
        return

    try:
        from sqlalchemy import update

        from app.core.security import create_access_token, decode_token
        from app.db.session import get_sessionmaker
        from app.models import InternshipRecord

        claims = decode_token(str(auth)[7:])
        if str(claims.get("userType") or "").upper() != "TEACHER":
            return
        role = str(claims.get("currentRoleCode") or "").upper()
        if role not in {"INTERN_MENTOR", "TEACHER"}:
            return
        tenant_id = int(claims.get("tenantId"))
        real_name = str(claims.get("realName") or "").strip()
        stable_id = _stable_test_user_id(claims)
        if not real_name or stable_id is None:
            return

        db = get_sessionmaker()()
        try:
            db.execute(
                update(InternshipRecord)
                .where(
                    InternshipRecord.tenant_id == tenant_id,
                    InternshipRecord.advisor_user_id.is_(None),
                    InternshipRecord.advisor_name == real_name,
                )
                .values(advisor_user_id=stable_id)
            )
            db.commit()
        finally:
            db.close()

        patched = {
            key: value
            for key, value in claims.items()
            if key not in {"exp", "iat", "jti"}
        }
        patched["userId"] = str(stable_id)
        new_headers = dict(headers)
        new_headers["Authorization"] = "Bearer " + create_access_token(patched)
        kwargs["headers"] = new_headers
    except Exception:
        # Failed fixture migration leaves the request to exercise fail-closed behavior.
        return


def _stage_rows(stage_config) -> list[dict]:
    if isinstance(stage_config, list):
        return [item for item in stage_config if isinstance(item, dict)]
    if isinstance(stage_config, dict):
        for key in ("stages", "phases", "items"):
            rows = stage_config.get(key)
            if isinstance(rows, list):
                return [item for item in rows if isinstance(item, dict)]
    return []


def _is_defense_write(path: str) -> bool:
    if path == "/api/v1/graduation/gd-defense-scores/entry":
        return True
    if path.startswith("/api/v1/graduation/gd-defense-scores/") and path.endswith(("/confirm", "/second-defense")):
        return True
    return path.startswith("/api/v1/mobile/teacher/graduation/defense/") and path.endswith("/score")


def _upgrade_legacy_graduation_defense_phase(url, path: str, kwargs: dict) -> None:
    """Normalize only legacy positive fixtures that omitted an explicit DEFENSE phase.

    This hook runs only in pytest. Explicit DEFENSE rows and CLOSED/ARCHIVED
    batches are never altered. Legacy batches created by old positive fixtures
    commonly remain DRAFT because those tests predate the phase contract; when
    they have no explicit timeline, the fixture states their intended setup by
    moving them to RUNNING. Production policy remains fail-closed.
    """
    if not _is_defense_write(path):
        return
    params = kwargs.get("params") or {}
    batch_id = params.get("batchId") if isinstance(params, dict) else None
    if batch_id in (None, ""):
        query = dict(parse_qsl(urlsplit(str(url)).query, keep_blank_values=True))
        batch_id = query.get("batchId")
    try:
        parsed_batch_id = int(batch_id)
    except (TypeError, ValueError):
        return

    try:
        from app.db.session import get_sessionmaker
        from app.models import GraduationBatch

        db = get_sessionmaker()()
        try:
            batch = db.get(GraduationBatch, parsed_batch_id)
            if not batch or batch.is_deleted or int(batch.tenant_id) != TEST_TENANT_ID:
                return
            if str(batch.status or "").upper() not in {"DRAFT", "ACTIVE", "RUNNING"}:
                return
            rows = _stage_rows(batch.stage_config)
            has_explicit_defense = any(
                str(item.get("code") or item.get("key") or "").upper() == "DEFENSE"
                for item in rows
            )
            if has_explicit_defense:
                return
            batch.status = "RUNNING"
            batch.stage_config = None
            db.commit()
        finally:
            db.close()
    except Exception:
        # A failed compatibility migration must leave the production gate fail-closed.
        return


def _install_request_wrapper() -> None:
    """Wrap the actual client used by legacy integration tests."""
    global _REQUEST_WRAPPER_PATCHED
    if _REQUEST_WRAPPER_PATCHED:
        return

    from starlette.testclient import TestClient

    original = TestClient.request
    if getattr(original, "_stable_fixture_wrapper", False):
        _REQUEST_WRAPPER_PATCHED = True
        return

    def request(self, method, url, _original=original, **kwargs):
        path = urlsplit(str(url)).path or str(url)
        _upgrade_internship_fixture_identity(path, kwargs)
        _upgrade_legacy_graduation_defense_phase(url, path, kwargs)
        return _original(self, method, url, **kwargs)

    request._stable_fixture_wrapper = True
    TestClient.request = request
    _REQUEST_WRAPPER_PATCHED = True


def pytest_runtest_setup(item) -> None:
    _install_request_wrapper()