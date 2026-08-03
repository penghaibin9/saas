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
    "test_graduation.py",
    "test_graduation_batch9.py",
    "test_graduation_batch_risk_archive_scope.py",
    "test_graduation_e2e_acceptance_gates.py",
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

_ARCHIVE_PREVIEW_PATHS = {
    "/api/v1/graduation/gd-archives/batch-generate/preview",
    "/api/v1/graduation/gd-archives/batch-file/preview",
}
_ARCHIVE_WRITE_PATHS = {
    "/api/v1/graduation/gd-archives/batch-generate",
    "/api/v1/graduation/gd-archives/batch-file",
}


def _json_data(response) -> dict:
    try:
        payload = response.json() or {}
    except Exception:
        return {}
    data = payload.get("data")
    return data if isinstance(data, dict) else {}


def _request_batch_id(original_request, kwargs) -> int | None:
    params = kwargs.get("params") or {}
    candidate = params.get("batchId") if isinstance(params, dict) else None
    if candidate in (None, ""):
        owner = getattr(original_request, "__self__", None)
        candidate = getattr(owner, "_active_batch_id", None)
    try:
        return int(candidate) if candidate not in (None, "") else None
    except (TypeError, ValueError):
        return None


def _ensure_student_material_catalog(headers: dict, batch_id: int | None = None) -> None:
    """Run the real rule/catalog initializers for a legacy test student.

    Old suites create ad-hoc graduation batches directly or through the legacy
    batch helper.  The production clients initialize a frozen material rule and
    student catalog before opening the library.  Reproduce that prerequisite in
    the harness instead of inventing lock tokens or bypassing validation.
    """
    auth = str((headers or {}).get("Authorization") or (headers or {}).get("authorization") or "")
    if not auth.startswith("Bearer "):
        return

    from sqlalchemy import or_, select

    from app.core.context import get_current_user_ctx, get_tenant, set_current_user, set_tenant
    from app.core.security import decode_token
    from app.db.session import get_sessionmaker
    from app.models import GraduationBatch, GraduationStudent
    from app.modules.graduation.materials.command_service import initialize_student_materials_in_session
    from app.modules.graduation.materials.rule_service import initialize_default_rule_in_session

    try:
        claims = decode_token(auth[7:]) or {}
    except Exception:
        return
    if str(claims.get("userType") or claims.get("currentRoleCode") or "").upper() != "STUDENT":
        return

    student_no = str(claims.get("studentNo") or "").strip()
    profile_id = str(claims.get("studentId") or claims.get("studentProfileId") or "").strip()
    real_name = str(claims.get("realName") or "").strip()
    clauses = []
    if student_no:
        clauses.append(GraduationStudent.student_no == student_no)
    if profile_id.isdigit():
        clauses.append(GraduationStudent.student_id == int(profile_id))
    if real_name:
        clauses.append(GraduationStudent.name == real_name)
    if not clauses:
        return

    previous_tenant = get_tenant()
    previous_user = get_current_user_ctx()
    db = get_sessionmaker()()
    try:
        set_tenant({"tenantId": str(TEST_TENANT_ID), "tenantCode": "demo"})
        set_current_user(claims)
        query = select(GraduationStudent).where(
            GraduationStudent.tenant_id == TEST_TENANT_ID,
            GraduationStudent.record_status == "ACTIVE",
            GraduationStudent.is_deleted.is_(False),
            or_(*clauses),
        )
        if batch_id is not None:
            query = query.where(GraduationStudent.batch_id == int(batch_id))
        student = db.scalars(query.order_by(GraduationStudent.id.desc()).limit(1)).first()
        if not student or not student.batch_id:
            return
        batch = db.get(GraduationBatch, int(student.batch_id))
        if batch and str(batch.status or "").upper() in {"ACTIVE", "DRAFT", "NOT_STARTED"}:
            batch.status = "IN_PROGRESS"
        initialize_default_rule_in_session(db, int(student.batch_id), claims)
        initialize_student_materials_in_session(db, int(student.id), claims)
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
        set_current_user(previous_user)
        set_tenant(previous_tenant)


def _student_material_snapshot(original_request, kwargs, material_code: str) -> dict:
    headers = kwargs.get("headers") or {}
    batch_id = _request_batch_id(original_request, kwargs)
    _ensure_student_material_catalog(headers, batch_id)
    params = dict(kwargs.get("params") or {})
    if batch_id is not None:
        params.setdefault("batchId", str(batch_id))
    response = original_request(
        "GET",
        "/api/v1/mobile/graduation/material-center/library",
        headers=headers,
        params=params,
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


def _bind_archive_preview_metadata(path: str, kwargs, archive_previews: dict[str, dict]) -> None:
    if path not in _ARCHIVE_WRITE_PATHS:
        return
    body = kwargs.get("json")
    if not isinstance(body, dict):
        return
    token = str(body.get("previewToken") or "")
    preview = archive_previews.get(token)
    if not preview or not preview.get("archiveBatchNo") or body.get("archiveBatchNo"):
        return
    patched = dict(body)
    patched["archiveBatchNo"] = preview["archiveBatchNo"]
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
    archive_previews: dict[str, dict] = {}

    def request_with_snapshot(method, url, **kwargs):
        normalized = str(method).upper()
        path = urlsplit(str(url)).path or str(url)
        _inject_graduation_snapshot(original_request, normalized, url, kwargs)
        _bind_archive_preview_metadata(path, kwargs, archive_previews)
        response = original_request(normalized, url, **kwargs)
        if normalized == "POST" and path in _ARCHIVE_PREVIEW_PATHS:
            data = _json_data(response)
            token = str(data.get("previewToken") or "")
            if token:
                archive_previews[token] = data
        return response

    client.request = request_with_snapshot
    try:
        yield
    finally:
        client.request = original_request
