"""Explicit compatibility adapter for legacy graduation tests only.

The shared ``client`` fixture remains a plain TestClient.  This plugin only
augments tests that explicitly request ``graduation_client`` so old scenarios
can exercise the current optimistic-lock and archive-preview contracts without
silently changing requests in unrelated domains.
"""
from __future__ import annotations

import re
from urllib.parse import parse_qsl, urlsplit

import pytest
from sqlalchemy import select

MAIN_TENANT_ID = 1000000000000000001
_BATCH_ARCHIVE_ACTIONS = {
    "/api/v1/graduation/gd-archives/batch-generate",
    "/api/v1/graduation/gd-archives/batch-file",
}
_REVIEW_RE = re.compile(r"^/api/v1/graduation/(proposals|finals)/(\d+)/review$")
_PLAGIARISM_RESULT_RE = re.compile(r"^/api/v1/graduation/gd-plagiarism/(\d+)/result$")


def _body(kwargs: dict) -> dict | None:
    value = kwargs.get("json")
    return value if isinstance(value, dict) else None


def _path_query(url) -> tuple[str, dict[str, str]]:
    parsed = urlsplit(str(url))
    return parsed.path or str(url), dict(parse_qsl(parsed.query, keep_blank_values=True))


def _batch_id(client, kwargs: dict, query: dict[str, str]) -> int | None:
    params = kwargs.get("params") or {}
    raw = params.get("batchId") if isinstance(params, dict) else None
    raw = raw or query.get("batchId") or getattr(client, "_active_batch_id", None)
    try:
        return int(raw) if raw not in (None, "") else None
    except (TypeError, ValueError):
        return None


def _claims(kwargs: dict) -> dict:
    headers = kwargs.get("headers") or {}
    auth = headers.get("Authorization") or headers.get("authorization") or ""
    if not str(auth).startswith("Bearer "):
        return {}
    try:
        from app.core.security import decode_token

        return decode_token(str(auth)[7:]) or {}
    except Exception:
        return {}


def _current_student(db, kwargs: dict, batch_id: int | None):
    from app.models import GraduationStudent

    claims = _claims(kwargs)
    query = select(GraduationStudent).where(
        GraduationStudent.tenant_id == MAIN_TENANT_ID,
        GraduationStudent.record_status == "ACTIVE",
        GraduationStudent.is_deleted.is_(False),
    )
    student_no = str(claims.get("studentNo") or "").strip()
    real_name = str(claims.get("realName") or "").strip()
    if student_no:
        query = query.where(GraduationStudent.student_no == student_no)
    elif real_name:
        query = query.where(GraduationStudent.name == real_name)
    else:
        return None
    if batch_id:
        query = query.where(GraduationStudent.batch_id == int(batch_id))
    return db.scalars(query.order_by(GraduationStudent.id.desc()).limit(1)).first()


def _material(db, gd_student_id: int, material_code: str, *, record_type: str | None = None,
              record_id: int | None = None):
    from app.models.graduation_material import GraduationStudentMaterial

    query = select(GraduationStudentMaterial).where(
        GraduationStudentMaterial.tenant_id == MAIN_TENANT_ID,
        GraduationStudentMaterial.gd_student_id == int(gd_student_id),
        GraduationStudentMaterial.material_code == material_code,
        GraduationStudentMaterial.is_deleted.is_(False),
    )
    if record_type and record_id is not None:
        query = query.where(
            GraduationStudentMaterial.source_record_type == record_type,
            GraduationStudentMaterial.source_record_id == str(record_id),
        )
    return db.scalars(query.order_by(GraduationStudentMaterial.id.desc()).limit(1)).first()


def _inject_mobile_material_version(client, path: str, kwargs: dict, body: dict) -> None:
    if path not in {"/api/v1/mobile/graduation/proposal", "/api/v1/mobile/graduation/final"}:
        return
    if body.get("expectedVersion") not in (None, ""):
        return
    from app.db.session import get_sessionmaker

    _path, query = _path_query(path)
    bid = _batch_id(client, kwargs, query)
    db = get_sessionmaker()()
    try:
        student = _current_student(db, kwargs, bid)
        if not student:
            return
        if path.endswith("/proposal"):
            code = "PROPOSAL_REPORT"
        else:
            code = "THESIS_FINAL" if str(body.get("finalType") or "初稿") == "定稿" else "THESIS_DRAFT"
        row = _material(db, int(student.id), code)
        body["expectedVersion"] = int(getattr(row, "version", 0) or 0)
    finally:
        db.close()


def _inject_review_versions(path: str, body: dict) -> None:
    match = _REVIEW_RE.match(path)
    if not match:
        return
    kind, raw_id = match.groups()
    from app.db.session import get_sessionmaker
    from app.models import GraduationFinal, GraduationProposal

    record_id = int(raw_id)
    model = GraduationProposal if kind == "proposals" else GraduationFinal
    record_type = "PROPOSAL" if kind == "proposals" else "FINAL"
    material_code = "PROPOSAL_REPORT"
    db = get_sessionmaker()()
    try:
        record = db.get(model, record_id)
        if not record:
            return
        if kind == "finals":
            material_code = "THESIS_FINAL" if str(record.final_type or "") == "定稿" else "THESIS_DRAFT"
        row = _material(
            db, int(record.gd_student_id), material_code,
            record_type=record_type, record_id=record_id,
        ) or _material(db, int(record.gd_student_id), material_code)
        if body.get("expectedVersion") in (None, ""):
            body["expectedVersion"] = int(getattr(row, "version", 0) or 0)
        if body.get("fileVersionId") in (None, ""):
            body["fileVersionId"] = int(getattr(row, "current_version_id", 0) or 0)
    finally:
        db.close()


def _inject_plagiarism_version(path: str, body: dict) -> None:
    match = _PLAGIARISM_RESULT_RE.match(path)
    if not match or body.get("expectedVersion") not in (None, ""):
        return
    from app.db.session import get_sessionmaker
    from app.models import GraduationPlagiarismCheck

    db = get_sessionmaker()()
    try:
        row = db.get(GraduationPlagiarismCheck, int(match.group(1)))
        if row and row.tenant_id == MAIN_TENANT_ID and not row.is_deleted:
            body["expectedVersion"] = int(getattr(row, "version", 0) or 0)
    finally:
        db.close()


def _refresh_batch_archive_preview(client, path: str, kwargs: dict, query: dict[str, str]) -> None:
    if path not in _BATCH_ARCHIVE_ACTIONS:
        return
    bid = _batch_id(client, kwargs, query)
    if not bid:
        return
    params = dict(kwargs.get("params") or {})
    params["batchId"] = str(bid)
    response = client._wrapped.post(
        f"{path}/preview",
        headers=kwargs.get("headers") or {},
        params=params,
    )
    payload = response.json() or {}
    if payload.get("code") != 0:
        return
    preview = payload.get("data") or {}
    token = preview.get("previewToken")
    if not token:
        return
    current = dict(_body(kwargs) or {})
    current["previewToken"] = token
    if preview.get("archiveBatchNo"):
        current["archiveBatchNo"] = preview["archiveBatchNo"]
    kwargs["json"] = current


def _prepare_contract(client, original_prepare, method: str, url, kwargs: dict) -> None:
    method = str(method).upper()
    path, query = _path_query(url)
    if method == "POST" and path in _BATCH_ARCHIVE_ACTIONS:
        client._archive_previews.clear()
    original_prepare(method, url, kwargs)
    if method != "POST":
        return
    body = _body(kwargs)
    if body is not None:
        _inject_mobile_material_version(client, path, kwargs, body)
        _inject_review_versions(path, body)
        _inject_plagiarism_version(path, body)
    _refresh_batch_archive_preview(client, path, kwargs, query)


@pytest.fixture(autouse=True)
def _explicit_graduation_legacy_contract(request):
    """Patch only a test that explicitly asks for ``graduation_client``."""
    if "graduation_client" not in request.fixturenames:
        yield
        return
    client = request.getfixturevalue("graduation_client")
    original_prepare = client._prepare_batch

    def prepared(method, url, kwargs):
        return _prepare_contract(client, original_prepare, method, url, kwargs)

    client._prepare_batch = prepared
    yield
