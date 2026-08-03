"""Repository-wide pytest safety fixtures.

DB-backed tests use an isolated MySQL schema and the canonical demo tenant id.
The production tenant guard is fail-closed, so the test harness must seed the
same authoritative ``t_tenant`` row that real requests require instead of
relying on orphaned tenant ids in business tables.
"""
from __future__ import annotations

import pytest

TEST_TENANT_ID = 1000000000000000001


@pytest.fixture(autouse=True)
def _seed_authoritative_tenant_for_db_tests(request):
    """Seed the canonical active tenant after ``db_mode`` resets the schema.

    Unit tests that do not request ``db_mode`` remain database-free. Tests may
    still create their own tenant lifecycle metadata; this fixture only supplies
    the relational hard-safety row required by the production tenant guard.
    """
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
