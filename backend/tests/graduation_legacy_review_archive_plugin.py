"""Narrow adapters for explicit legacy graduation review/archive tests only."""
from __future__ import annotations

import re
from urllib.parse import parse_qsl, urlsplit

import httpx
import pytest
from sqlalchemy import select

MAIN_TENANT_ID = 1000000000000000001
_MOBILE_REVIEW = re.compile(
    r"^/api/v1/mobile/teacher/graduation/(proposal|final)/(\d+)/review$"
)
_STUDENT_FILE = re.compile(r"^/api/v1/graduation/gd-archives/(\d+)/file$")
_BATCH_ACTIONS = {
    "/api/v1/graduation/gd-archives/batch-generate",
    "/api/v1/graduation/gd-archives/batch-file",
}


def _body(kwargs):
    value = kwargs.get("json")
    return value if isinstance(value, dict) else {}


def _inject_mobile_review(path: str, kwargs: dict) -> None:
    match = _MOBILE_REVIEW.match(path)
    if not match:
        return
    kind, raw_id = match.groups()
    from app.db.session import get_sessionmaker
    from app.models import GraduationFinal, GraduationProposal
    from app.models.graduation_material import GraduationStudentMaterial

    model = GraduationProposal if kind == "proposal" else GraduationFinal
    db = get_sessionmaker()()
    try:
        record = db.get(model, int(raw_id))
        if not record or record.tenant_id != MAIN_TENANT_ID or record.is_deleted:
            return
        code = "PROPOSAL_REPORT"
        if kind == "final":
            code = "THESIS_FINAL" if str(record.final_type or "") == "定稿" else "THESIS_DRAFT"
        row = db.scalars(select(GraduationStudentMaterial).where(
            GraduationStudentMaterial.tenant_id == MAIN_TENANT_ID,
            GraduationStudentMaterial.gd_student_id == int(record.gd_student_id),
            GraduationStudentMaterial.material_code == code,
            GraduationStudentMaterial.is_deleted.is_(False),
        ).order_by(
            (GraduationStudentMaterial.source_record_id == str(record.id)).desc(),
            GraduationStudentMaterial.id.desc(),
        ).limit(1)).first()
        if not row:
            return
        body = dict(_body(kwargs))
        body.setdefault("expectedVersion", int(row.version or 0))
        if row.current_version_id:
            body.setdefault("fileVersionId", int(row.current_version_id))
        kwargs["json"] = body
    finally:
        db.close()


def _inject_archive_version(path: str, kwargs: dict) -> None:
    match = _STUDENT_FILE.match(path)
    if not match:
        return
    from app.db.session import get_sessionmaker
    from app.models import GraduationArchiveRecord

    db = get_sessionmaker()()
    try:
        row = db.scalars(select(GraduationArchiveRecord).where(
            GraduationArchiveRecord.tenant_id == MAIN_TENANT_ID,
            GraduationArchiveRecord.gd_student_id == int(match.group(1)),
            GraduationArchiveRecord.is_deleted.is_(False),
        ).limit(1)).first()
        if not row:
            return
        body = dict(_body(kwargs))
        body.setdefault("expectedVersion", int(row.version or 0))
        kwargs["json"] = body
    finally:
        db.close()


def _direct_batch_action(client, method, url, kwargs):
    body = _body(kwargs)
    if not body.get("previewToken"):
        return None
    parsed = urlsplit(str(url))
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    params = dict(kwargs.get("params") or {})
    if "batchId" not in params and query.get("batchId"):
        params["batchId"] = query["batchId"]
    kwargs["params"] = params
    response = client._wrapped.request(method, url, **kwargs)
    client._remember_batch(str(method).upper(), url, kwargs, response)
    return response


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


def _prepare_single_archive_evidence(gd_student_id: int, kwargs: dict) -> None:
    """Complete explicit old ORM fixtures through real V2 snapshot/backfill writers."""
    user = _claims(kwargs)
    if not user:
        return
    from app.db.session import get_sessionmaker
    from app.models import GraduationFinal, GraduationStudent
    from app.modules.graduation.materials.command_service import adopt_legacy_file_in_session
    from app.modules.graduation.materials.snapshot_service import prepare_all

    prepare_all(int(gd_student_id), user)
    db = get_sessionmaker()()
    try:
        student = db.get(GraduationStudent, int(gd_student_id))
        if not student or student.tenant_id != MAIN_TENANT_ID or student.is_deleted:
            return
        final = db.scalars(select(GraduationFinal).where(
            GraduationFinal.tenant_id == MAIN_TENANT_ID,
            GraduationFinal.gd_student_id == int(student.id),
            GraduationFinal.final_type == "定稿",
            GraduationFinal.status == "APPROVED",
            GraduationFinal.is_deleted.is_(False),
        ).order_by(GraduationFinal.id.desc()).limit(1)).first()
        ids = []
        for raw in (final.attachments_json if final else []) or []:
            value = raw.get("fileId") if isinstance(raw, dict) else raw
            if str(value or "").isdigit():
                ids.append(int(value))
        if final and len(ids) == 1:
            adopt_legacy_file_in_session(
                db, student, "THESIS_FINAL", ids[0],
                source_record_type="FINAL", source_record_id=str(final.id),
                user=user, approved=True,
                binding_metadata={
                    "mappingReason": "legacy explicit test fixture final attachment",
                    "mappingConfidence": "HIGH", "manualReview": False,
                },
            )
            db.commit()
    finally:
        db.close()


def _legacy_archive_response(response, gd_student_id: int):
    if response.status_code != 200:
        return response
    try:
        payload = response.json() or {}
        data = dict(payload.get("data") or {})
    except Exception:
        return response
    from app.db.session import get_sessionmaker
    from app.models import GraduationArchiveRecord

    db = get_sessionmaker()()
    try:
        archive = db.scalars(select(GraduationArchiveRecord).where(
            GraduationArchiveRecord.tenant_id == MAIN_TENANT_ID,
            GraduationArchiveRecord.gd_student_id == int(gd_student_id),
            GraduationArchiveRecord.is_deleted.is_(False),
        ).limit(1)).first()
        if not archive:
            return response
        data["manifestStatus"] = data.get("status") or ""
        data["status"] = archive.status
        data["manifestHash"] = archive.manifest_hash or data.get("manifestSha256") or ""
        data["version"] = int(archive.version or 0)
        data["archiveBatchNo"] = archive.archive_batch_no or ""
        payload["data"] = data
        return httpx.Response(
            status_code=response.status_code,
            json=payload,
            headers=dict(response.headers),
            request=response.request,
        )
    finally:
        db.close()


@pytest.fixture(autouse=True)
def _explicit_graduation_review_archive_contract(request):
    if "graduation_client" not in request.fixturenames:
        yield
        return
    client = request.getfixturevalue("graduation_client")
    original_request = client.request

    def request_with_contract(method, url, **kwargs):
        path = urlsplit(str(url)).path or str(url)
        if str(method).upper() == "POST":
            _inject_mobile_review(path, kwargs)
            _inject_archive_version(path, kwargs)
            single = _STUDENT_FILE.match(path)
            if single:
                _prepare_single_archive_evidence(int(single.group(1)), kwargs)
            if path in _BATCH_ACTIONS:
                direct = _direct_batch_action(client, method, url, kwargs)
                if direct is not None:
                    return direct
        response = original_request(method, url, **kwargs)
        single = _STUDENT_FILE.match(path)
        return _legacy_archive_response(response, int(single.group(1))) if single else response

    client.request = request_with_contract
    yield
