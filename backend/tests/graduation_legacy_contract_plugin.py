"""Explicit compatibility adapter for legacy graduation tests only.

The shared ``client`` fixture remains a plain TestClient. This plugin only
augments tests that explicitly request ``graduation_client`` so old scenarios
can exercise current optimistic-lock and archive-preview contracts without
silently changing requests in unrelated domains.
"""
from __future__ import annotations

import hashlib
import re
from datetime import datetime
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


def _ensure_running_batch(db, student) -> None:
    from app.models import GraduationBatch

    batch = db.get(GraduationBatch, int(student.batch_id)) if student and student.batch_id else None
    if batch and batch.tenant_id == MAIN_TENANT_ID and batch.status == "DRAFT":
        batch.status = "RUNNING"
        batch.last_transition_at = datetime.utcnow()
        batch.last_transition_by = "legacy-graduation-test-adapter"
        db.commit()


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
        _ensure_running_batch(db, student)
        if path.endswith("/proposal"):
            code = "PROPOSAL_REPORT"
        else:
            code = "THESIS_FINAL" if str(body.get("finalType") or "初稿") == "定稿" else "THESIS_DRAFT"
        row = _material(db, int(student.id), code)
        body["expectedVersion"] = int(getattr(row, "version", 0) or 0)
    finally:
        db.close()


def _ensure_review_evidence(db, record, kind: str):
    """Link old direct ORM records to a minimal authoritative material version."""
    from app.models import GraduationStudent
    from app.models.file import FileAsset, FileBinding, FileObject, FileVersion
    from app.models.graduation_material import (
        GraduationMaterialItem,
        GraduationMaterialRule,
        GraduationStudentMaterial,
    )

    student = db.get(GraduationStudent, int(record.gd_student_id))
    if not student or not student.batch_id:
        return None
    material_code = "PROPOSAL_REPORT"
    if kind == "FINAL":
        material_code = "THESIS_FINAL" if str(record.final_type or "") == "定稿" else "THESIS_DRAFT"
    existing = _material(db, int(student.id), material_code)
    if existing and existing.current_version_id:
        existing.source_record_type = kind
        existing.source_record_id = str(record.id)
        db.commit()
        return existing

    rule = db.scalars(select(GraduationMaterialRule).where(
        GraduationMaterialRule.tenant_id == MAIN_TENANT_ID,
        GraduationMaterialRule.batch_id == int(student.batch_id),
        GraduationMaterialRule.enabled.is_(True),
        GraduationMaterialRule.is_deleted.is_(False),
    ).order_by(GraduationMaterialRule.rule_version.desc()).limit(1)).first()
    if not rule:
        return existing
    item = db.scalars(select(GraduationMaterialItem).where(
        GraduationMaterialItem.tenant_id == MAIN_TENANT_ID,
        GraduationMaterialItem.rule_id == int(rule.id),
        GraduationMaterialItem.material_code == material_code,
        GraduationMaterialItem.enabled.is_(True),
        GraduationMaterialItem.is_deleted.is_(False),
    ).limit(1)).first()
    if not item:
        return existing
    material = existing or GraduationStudentMaterial(
        tenant_id=MAIN_TENANT_ID,
        batch_id=int(student.batch_id),
        gd_student_id=int(student.id),
        student_id=student.student_id,
        topic_id=student.topic_id,
        rule_id=int(rule.id),
        rule_version=int(rule.rule_version),
        material_code=material_code,
        material_name=item.material_name,
        biz_stage=item.biz_stage,
        owner_role=item.owner_role,
        required_status="REQUIRED" if item.required else "OPTIONAL",
        sensitivity_level=item.sensitivity_level,
        migration_status="LEGACY_TEST_ADAPTER",
    )
    if existing is None:
        db.add(material)
        db.flush()
    digest = hashlib.sha256(f"legacy:{kind}:{record.id}".encode()).hexdigest()
    file_obj = FileObject(
        tenant_id=MAIN_TENANT_ID,
        file_key=f"legacy-test/{kind.lower()}-{record.id}.pdf",
        file_name=f"legacy-{kind.lower()}-{record.id}.pdf",
        ext="pdf",
        mime_type="application/pdf",
        size_bytes=1,
        sha256=digest,
        biz_type="GRADUATION_MATERIAL",
        biz_id=str(material.id),
        visibility="BIZ_SCOPED",
        security_level=item.sensitivity_level,
        status="AVAILABLE",
        storage_backend="local",
        storage_zone="ACTIVE",
        upload_source="SYSTEM",
        scan_required=False,
        scan_status="NOT_REQUIRED",
        available_at=datetime.utcnow(),
    )
    db.add(file_obj)
    db.flush()
    asset = FileAsset(
        tenant_id=MAIN_TENANT_ID,
        asset_code=f"GD-LEGACY-TEST:{student.id}:{material_code}:{record.id}",
        title=f"{student.name}·{item.material_name}",
        category_code=material_code,
        owner_type="GRADUATION_STUDENT_MATERIAL",
        owner_id=str(student.id),
        lifecycle_status="ACTIVE",
        version_count=1,
        sensitivity_level=item.sensitivity_level,
    )
    db.add(asset)
    db.flush()
    version = FileVersion(
        tenant_id=MAIN_TENANT_ID,
        asset_id=int(asset.id),
        file_object_id=int(file_obj.id),
        version_no=1,
        source_channel="LEGACY_TEST_ADAPTER",
        uploader_name_snapshot="legacy-graduation-test-adapter",
        status="SUBMITTED",
        is_current=True,
        submitted_at=datetime.utcnow(),
    )
    db.add(version)
    db.flush()
    db.add(FileBinding(
        tenant_id=MAIN_TENANT_ID,
        file_id=int(file_obj.id),
        biz_type="GRADUATION_MATERIAL",
        biz_id=str(material.id),
        relation_type="GRADUATION_MATERIAL_ITEM",
        subject_type="STUDENT",
        subject_id=str(student.student_id or student.id),
        batch_id=str(student.batch_id),
        version_no=1,
        is_current=True,
        status="ACTIVE",
        asset_id=int(asset.id),
        version_id=int(version.id),
        module_code="GRADUATION",
        student_id=int(student.student_id or student.id),
        scope_json={"gdStudentId": str(student.id), "materialCode": material_code},
        data_scope_snapshot_json={"batchId": str(student.batch_id)},
    ))
    asset.current_version_id = int(version.id)
    material.asset_id = int(asset.id)
    material.current_version_id = int(version.id)
    material.business_status = "SUBMITTED"
    material.review_status = "PENDING"
    material.archive_status = "NOT_ARCHIVED"
    material.source_record_type = kind
    material.source_record_id = str(record.id)
    material.submitted_at = datetime.utcnow()
    material.version = max(int(material.version or 0), 1)
    record.attachments_json = [int(file_obj.id)]
    db.commit()
    return material


def _inject_review_versions(path: str, body: dict) -> None:
    match = _REVIEW_RE.match(path)
    if not match:
        return
    kind_path, raw_id = match.groups()
    from app.db.session import get_sessionmaker
    from app.models import GraduationFinal, GraduationProposal

    record_id = int(raw_id)
    model = GraduationProposal if kind_path == "proposals" else GraduationFinal
    record_type = "PROPOSAL" if kind_path == "proposals" else "FINAL"
    material_code = "PROPOSAL_REPORT"
    db = get_sessionmaker()()
    try:
        record = db.get(model, record_id)
        if not record:
            return
        if kind_path == "finals":
            material_code = "THESIS_FINAL" if str(record.final_type or "") == "定稿" else "THESIS_DRAFT"
        row = _material(
            db, int(record.gd_student_id), material_code,
            record_type=record_type, record_id=record_id,
        ) or _material(db, int(record.gd_student_id), material_code)
        if not row or not row.current_version_id:
            row = _ensure_review_evidence(db, record, record_type)
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


def _prepare_contract(client, original_prepare, method: str, url, kwargs: dict) -> None:
    method = str(method).upper()
    path, _query = _path_query(url)
    original_prepare(method, url, kwargs)
    if method != "POST":
        return
    body = _body(kwargs)
    if body is not None:
        _inject_mobile_material_version(client, path, kwargs, body)
        _inject_review_versions(path, body)
        _inject_plagiarism_version(path, body)


def _archive_request(client, method: str, url, kwargs: dict):
    path, query = _path_query(url)
    bid = _batch_id(client, kwargs, query)
    params = dict(kwargs.get("params") or {})
    if bid:
        params["batchId"] = str(bid)
    preview = client._wrapped.post(
        f"{path}/preview",
        headers=kwargs.get("headers") or {},
        params=params,
    )
    payload = preview.json() or {}
    if payload.get("code") == 0:
        data = payload.get("data") or {}
        current = dict(_body(kwargs) or {})
        if data.get("previewToken"):
            current["previewToken"] = data["previewToken"]
        if data.get("archiveBatchNo"):
            current["archiveBatchNo"] = data["archiveBatchNo"]
        kwargs["json"] = current
    kwargs["params"] = params
    response = client._wrapped.request(method, url, **kwargs)
    client._remember_batch(str(method).upper(), url, kwargs, response)
    return response


@pytest.fixture(autouse=True)
def _explicit_graduation_legacy_contract(request):
    """Patch only a test that explicitly asks for ``graduation_client``."""
    if "graduation_client" not in request.fixturenames:
        yield
        return
    client = request.getfixturevalue("graduation_client")
    original_prepare = client._prepare_batch
    original_request = client.request

    def prepared(method, url, kwargs):
        return _prepare_contract(client, original_prepare, method, url, kwargs)

    def compat_request(method, url, **kwargs):
        path, _query = _path_query(url)
        if str(method).upper() == "POST" and path in _BATCH_ARCHIVE_ACTIONS:
            return _archive_request(client, method, url, kwargs)
        return original_request(method, url, **kwargs)

    client._prepare_batch = prepared
    client.request = compat_request
    yield
