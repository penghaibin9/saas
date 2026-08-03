"""Create the real default material rule for explicit legacy graduation tests.

This plugin never touches the shared ``client`` fixture. It only completes the
setup performed by ``graduation_client``: every test batch becomes RUNNING and
has one enabled, versioned material rule before material endpoints are used.
"""
from __future__ import annotations

from datetime import datetime
from urllib.parse import urlsplit

import pytest
from sqlalchemy import select

MAIN_TENANT_ID = 1000000000000000001


def _ensure_batch_rule(batch_id) -> None:
    try:
        bid = int(batch_id)
    except (TypeError, ValueError):
        return
    from app.db.session import get_sessionmaker
    from app.models import GraduationBatch
    from app.models.graduation_material import GraduationMaterialItem, GraduationMaterialRule
    from app.modules.graduation.materials.definitions import DEFAULT_MATERIAL_DEFINITIONS

    db = get_sessionmaker()()
    try:
        batch = db.scalars(select(GraduationBatch).where(
            GraduationBatch.tenant_id == MAIN_TENANT_ID,
            GraduationBatch.id == bid,
            GraduationBatch.is_deleted.is_(False),
        ).with_for_update()).first()
        if not batch:
            return
        if batch.status == "DRAFT":
            batch.status = "RUNNING"
            batch.last_transition_at = datetime.utcnow()
            batch.last_transition_by = "legacy-graduation-test-adapter"
        rule = db.scalars(select(GraduationMaterialRule).where(
            GraduationMaterialRule.tenant_id == MAIN_TENANT_ID,
            GraduationMaterialRule.batch_id == bid,
            GraduationMaterialRule.status == "ENABLED",
            GraduationMaterialRule.enabled.is_(True),
            GraduationMaterialRule.is_deleted.is_(False),
        ).order_by(GraduationMaterialRule.rule_version.desc()).limit(1)).first()
        if rule is None:
            definitions = [dict(row) for row in DEFAULT_MATERIAL_DEFINITIONS]
            rule = GraduationMaterialRule(
                tenant_id=MAIN_TENANT_ID,
                batch_id=bid,
                rule_code="GD_MATERIAL_STANDARD",
                rule_name="毕业设计标准材料规则",
                rule_version=1,
                status="ENABLED",
                enabled=True,
                default_owner_role="STUDENT",
                version_policy="IMMUTABLE_APPEND",
                archive_required=True,
                sensitivity_level="SENSITIVE",
                applicable_scope_json={"batchId": str(bid)},
                required_items_json=[row["materialCode"] for row in definitions if row.get("required")],
                allowed_ext_json=sorted({
                    str(ext).lower().lstrip(".")
                    for row in definitions for ext in (row.get("allowedExtensions") or [])
                }),
                max_files=max(int(row.get("maxFileCount") or row.get("maxFiles") or 1) for row in definitions),
                max_size_bytes=max(int(row.get("maxSizeBytes") or 0) for row in definitions),
                effective_at=datetime.utcnow(),
            )
            db.add(rule)
            db.flush()
            for sort_no, raw in enumerate(definitions, start=1):
                db.add(GraduationMaterialItem(
                    tenant_id=MAIN_TENANT_ID,
                    rule_id=int(rule.id),
                    biz_stage=str(raw.get("stage") or raw.get("bizStage") or "").upper(),
                    material_code=str(raw.get("materialCode") or "").upper(),
                    material_name=str(raw.get("materialName") or ""),
                    owner_role=str(raw.get("ownerRole") or "STUDENT").upper(),
                    required=bool(raw.get("required", False)),
                    allowed_ext_json=sorted({
                        str(ext).lower().lstrip(".") for ext in (raw.get("allowedExtensions") or [])
                    }),
                    max_files=max(1, int(raw.get("maxFileCount") or raw.get("maxFiles") or 1)),
                    max_size_bytes=int(raw.get("maxSizeBytes") or 0),
                    version_policy=str(raw.get("versionPolicy") or "IMMUTABLE_APPEND").upper(),
                    review_required=bool(raw.get("reviewRequired", True)),
                    archive_required=bool(raw.get("archiveRequired", True)),
                    sensitivity_level=str(raw.get("sensitivityLevel") or "SENSITIVE").upper(),
                    applicable_major_id=str(raw.get("applicableMajor") or "") or None,
                    applicable_topic_type=str(raw.get("applicableTopicType") or "") or None,
                    sort_no=sort_no,
                    enabled=bool(raw.get("enabled", True)),
                    description=str(raw.get("description") or "") or None,
                ))
        db.commit()
    finally:
        db.close()


def _response_batch_id(response):
    try:
        payload = response.json() or {}
        if payload.get("code") != 0:
            return None
        return (payload.get("data") or {}).get("id")
    except Exception:
        return None


@pytest.fixture(autouse=True)
def _explicit_graduation_batch_rule(request):
    if "graduation_client" not in request.fixturenames:
        yield
        return
    client = request.getfixturevalue("graduation_client")
    original_request = client.request
    original_create_default_batch = client._create_default_batch

    def create_default_batch(headers):
        batch_id = original_create_default_batch(headers)
        if batch_id:
            _ensure_batch_rule(batch_id)
        return batch_id

    def request_with_rule(method, url, **kwargs):
        response = original_request(method, url, **kwargs)
        path = urlsplit(str(url)).path or str(url)
        if str(method).upper() == "POST" and path == "/api/v1/graduation/batches":
            batch_id = _response_batch_id(response)
            if batch_id:
                _ensure_batch_rule(batch_id)
        return response

    client._create_default_batch = create_default_batch
    client.request = request_with_rule
    yield
