"""Repository-wide pytest safety fixtures.

DB-backed tests use an isolated MySQL schema and the canonical demo tenant id.
The production tenant guard is fail-closed, so the test harness must seed the
same authoritative ``t_tenant`` row that real requests require instead of
relying on orphaned tenant ids in business tables.
"""
from __future__ import annotations

from pathlib import Path
from urllib.parse import urlsplit

import pytest

TEST_TENANT_ID = 1000000000000000001

# These suites pre-date the graduation material P0 contract.  The adapter does
# not weaken production validation: it performs the same read-before-write as
# the four real clients and copies the returned optimistic-lock/file snapshot
# tokens into legacy test requests.  Dedicated material-contract tests are
# intentionally excluded so missing/stale-token assertions remain effective.
_LEGACY_GRADUATION_SUITES = {
    "test_graduation_final.py",
    "test_graduation_mobile_final.py",
    "test_graduation_mobile_review.py",
    "test_graduation_more.py",
    "test_graduation_p1_audit_fixes.py",
    "test_graduation_proposal.py",
    "test_graduation_reaudit_gates.py",
    "test_graduation_review.py",
    "test_graduation_risk_archive_stats.py",
    "test_graduation_student_channel_reaudit.py",
}


def _json_data(response) -> dict:
    try:
        payload = response.json() or {}
    except Exception:
        return {}
    data = payload.get("data")
    return data if isinstance(data, dict) else {}


def _student_material_snapshot(original_request, kwargs, material_code: str) -> dict:
    response = original_request(
        "GET",
        "/api/v1/mobile/graduation/material-center/library",
        headers=kwargs.get("headers") or {},
    )
    data = _json_data(response)
    for item in data.get("items") or []:
        if str(item.get("materialCode") or "").upper() != material_code:
            continue
        current = item.get("currentVersion") or {}
        return {
            "expectedVersion": int(item.get("version") or 0),
            "fileVersionId": int(current.get("versionId") or 0),
        }
    return {}


def _review_material_snapshot(original_request, path: str, kwargs) -> dict:
    response = original_request(
        "GET",
        path.removesuffix("/review"),
        headers=kwargs.get("headers") or {},
        params=kwargs.get("params") or {},
    )
    data = _json_data(response)
    return {
        "expectedVersion": data.get("materialVersion"),
        "fileVersionId": data.get("fileVersionId"),
    }


def _inject_graduation_snapshot(original_request, method: str, url, kwargs) -> None:
    if method not in {"POST", "PUT", "PATCH"}:
        return
    body = kwargs.get("json")
    if not isinstance(body, dict):
        return
    path = urlsplit(str(url)).path or str(url)
    patched = dict(body)

    material_code = None
    if path == "/api/v1/mobile/graduation/proposal":
        material_code = "PROPOSAL_REPORT"
    elif path == "/api/v1/mobile/graduation/final":
        material_code = "THESIS_FINAL" if patched.get("finalType") == "定稿" else "THESIS_DRAFT"
    if material_code and "expectedVersion" not in patched:
        snapshot = _student_material_snapshot(original_request, kwargs, material_code)
        if "expectedVersion" in snapshot:
            patched["expectedVersion"] = snapshot["expectedVersion"]

    is_material_review = (
        path.endswith("/review")
        and (
            path.startswith("/api/v1/graduation/proposals/")
            or path.startswith("/api/v1/graduation/finals/")
            or path.startswith("/api/v1/mobile/teacher/graduation/proposal/")
            or path.startswith("/api/v1/mobile/teacher/graduation/final/")
        )
    )
    if is_material_review and ("expectedVersion" not in patched or "fileVersionId" not in patched):
        snapshot = _review_material_snapshot(original_request, path, kwargs)
        if "expectedVersion" not in patched and snapshot.get("expectedVersion") is not None:
            patched["expectedVersion"] = int(snapshot["expectedVersion"])
        if "fileVersionId" not in patched and snapshot.get("fileVersionId") not in (None, "", 0, "0"):
            patched["fileVersionId"] = int(snapshot["fileVersionId"])

    if patched != body:
        kwargs["json"] = patched


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


@pytest.fixture(autouse=True)
def _adapt_legacy_graduation_snapshot_contract(request):
    """Make legacy HTTP tests exercise the current read-before-write contract."""
    file_name = Path(str(getattr(request.node, "fspath", ""))).name
    if file_name not in _LEGACY_GRADUATION_SUITES or "client" not in request.fixturenames:
        yield
        return

    client = request.getfixturevalue("client")
    original_request = client.request

    def request_with_snapshot(method, url, **kwargs):
        normalized = str(method).upper()
        _inject_graduation_snapshot(original_request, normalized, url, kwargs)
        return original_request(normalized, url, **kwargs)

    client.request = request_with_snapshot
    try:
        yield
    finally:
        client.request = original_request
