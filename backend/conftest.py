"""Repository-wide pytest safety and compatibility fixtures.

DB-backed tests use an isolated MySQL schema and the canonical demo tenant id.
Package 8 also removed runtime authorization by advisor display name. Older
integration fixtures are explicitly migrated to stable advisor ids here before
an internship request; production code remains fail-closed.
"""
from __future__ import annotations

import hashlib
import sys
from urllib.parse import urlsplit

import pytest

TEST_TENANT_ID = 1000000000000000001
_REQUEST_WRAPPER_PATCHED = False


@pytest.fixture(autouse=True)
def _seed_authoritative_tenant_for_db_tests(request):
    """Seed the canonical active tenant after ``db_mode`` resets the schema."""
    if "db_mode" not in request.fixturenames:
        yield
        return

    request.getfixturevalue("db_mode")

    from app.db.session import get_sessionmaker
    from app.models import Tenant

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


def _stable_test_user_id(claims: dict) -> int | None:
    raw = claims.get("userId")
    try:
        parsed = int(raw)
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
    """Perform an explicit test-data backfill; never enable name authorization."""
    if "internship" not in path:
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

        patched = {key: value for key, value in claims.items() if key not in {"exp", "iat", "jti"}}
        patched["userId"] = str(stable_id)
        new_headers = dict(headers)
        new_headers["Authorization"] = "Bearer " + create_access_token(patched)
        kwargs["headers"] = new_headers
    except Exception:
        # Failed fixture migration leaves the request to exercise fail-closed behavior.
        return


def _install_request_wrapper() -> None:
    global _REQUEST_WRAPPER_PATCHED
    if _REQUEST_WRAPPER_PATCHED:
        return
    for module in tuple(sys.modules.values()):
        client_type = getattr(module, "GraduationBatchAwareClient", None)
        if client_type is None:
            continue
        original = client_type.request
        if getattr(original, "_internship_stable_fixture_wrapper", False):
            _REQUEST_WRAPPER_PATCHED = True
            return

        def request(self, method, url, _original=original, **kwargs):
            path = urlsplit(str(url)).path or str(url)
            _upgrade_internship_fixture_identity(path, kwargs)
            return _original(self, method, url, **kwargs)

        request._internship_stable_fixture_wrapper = True
        client_type.request = request
        _REQUEST_WRAPPER_PATCHED = True
        return


def pytest_runtest_setup(item) -> None:
    _install_request_wrapper()
