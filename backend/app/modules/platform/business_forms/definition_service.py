"""Transactional operations for platform-owned form definitions and versions.

Methods mutate only the two PLAT-B tables and deliberately leave commit/rollback
to the request transaction owner.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select

from app.core.exceptions import AppException, check_version, not_found

from .models import BusinessFormDefinition, BusinessFormVersion
from .schema_validator import BusinessFormSchemaValidator, compute_schema_hash
from .schemas import BusinessFormVersionDTO


def _definition_row(db, tenant_id: int, definition_id: int, *, lock: bool = False):
    stmt = select(BusinessFormDefinition).where(
        BusinessFormDefinition.tenant_id == int(tenant_id),
        BusinessFormDefinition.id == int(definition_id),
        BusinessFormDefinition.is_deleted.is_(False),
    )
    row = db.scalars(stmt.with_for_update() if lock else stmt).first()
    if not row:
        raise not_found("业务表单定义不存在")
    return row


def _version_row(db, tenant_id: int, version_id: int, *, lock: bool = False):
    stmt = select(BusinessFormVersion).where(
        BusinessFormVersion.tenant_id == int(tenant_id),
        BusinessFormVersion.id == int(version_id),
        BusinessFormVersion.is_deleted.is_(False),
    )
    if lock:
        # A prior identity-map read must not leave stale status/version fields
        # after waiting for the definition lock.
        stmt = stmt.with_for_update().execution_options(populate_existing=True)
    row = db.scalars(stmt).first()
    if not row:
        raise not_found("业务表单版本不存在")
    return row


def version_dto(row: BusinessFormVersion) -> BusinessFormVersionDTO:
    schema = row.schema_json or {}
    return BusinessFormVersionDTO.model_validate({
        "form_code": row.form_code,
        "version_id": int(row.id),
        "version_no": int(row.version_no),
        "schema_hash": row.schema_hash,
        "schema_version": row.schema_version,
        "supported_clients": row.supported_clients_json or [],
        "policy_refs": row.policy_refs_json or [],
        "domain_data_adapter": row.domain_data_adapter,
        "domain_command_adapter": row.domain_command_adapter,
        "fields": schema.get("fields") or [],
        "conditions": schema.get("conditions") or [],
    })


class BusinessFormDefinitionService:
    def __init__(self, db, *, tenant_id: int, actor_id: int | None):
        self.db = db
        self.tenant_id = int(tenant_id)
        self.actor_id = actor_id
        self.validator = BusinessFormSchemaValidator()

    def create_definition(self, *, form_code: str, form_name: str, domain_code: str, description: str = ""):
        code = str(form_code or "").strip().upper()
        if not code or not str(form_name or "").strip() or not str(domain_code or "").strip():
            raise AppException("VALIDATION_ERROR", "formCode/formName/domainCode 必填")
        exists = self.db.scalars(select(BusinessFormDefinition).where(
            BusinessFormDefinition.tenant_id == self.tenant_id,
            BusinessFormDefinition.form_code == code,
            BusinessFormDefinition.is_deleted.is_(False),
        )).first()
        if exists:
            raise AppException("DATA_CONFLICT", "业务表单 code 已存在", http_status=409)
        row = BusinessFormDefinition(
            tenant_id=self.tenant_id,
            form_code=code,
            form_name=str(form_name).strip()[:200],
            domain_code=str(domain_code).strip().upper()[:80],
            description=str(description or "").strip() or None,
            enabled=True,
            created_by=self.actor_id,
        )
        self.db.add(row)
        self.db.flush()
        return row

    def create_draft_version(self, definition_id: int, payload: dict) -> BusinessFormVersion:
        definition = _definition_row(self.db, self.tenant_id, definition_id, lock=True)
        latest = int(self.db.scalar(select(func.max(BusinessFormVersion.version_no)).where(
            BusinessFormVersion.tenant_id == self.tenant_id,
            BusinessFormVersion.definition_id == int(definition.id),
        )) or 0)
        candidate = BusinessFormVersionDTO.model_validate({
            "form_code": definition.form_code,
            "version_id": 0,
            "version_no": latest + 1,
            "schema_hash": "pending",
            "schema_version": payload.get("schemaVersion") or "1.0",
            "supported_clients": payload.get("supportedClients") or [],
            "policy_refs": payload.get("policyRefs") or [],
            "domain_data_adapter": payload.get("domainDataAdapter"),
            "domain_command_adapter": payload.get("domainCommandAdapter"),
            "fields": payload.get("fields") or [],
            "conditions": payload.get("conditions") or [],
        })
        candidate = candidate.model_copy(update={"schema_hash": compute_schema_hash(candidate)})
        self.validator.validate(candidate)
        row = BusinessFormVersion(
            tenant_id=self.tenant_id,
            definition_id=int(definition.id),
            form_code=definition.form_code,
            version_no=candidate.version_no,
            schema_hash=candidate.schema_hash,
            schema_version=candidate.schema_version,
            supported_clients_json=sorted(value.value for value in candidate.supported_clients),
            policy_refs_json=[ref.model_dump(mode="json") for ref in candidate.policy_refs],
            domain_data_adapter=candidate.domain_data_adapter,
            domain_command_adapter=candidate.domain_command_adapter,
            schema_json={
                "fields": [field.model_dump(mode="json", by_alias=True) for field in candidate.fields],
                "conditions": candidate.conditions,
            },
            status="DRAFT",
            created_by=self.actor_id,
        )
        self.db.add(row)
        self.db.flush()
        return row

    def validate_version(self, version_id: int) -> BusinessFormVersionDTO:
        dto = version_dto(_version_row(self.db, self.tenant_id, version_id))
        return self.validator.validate(dto)

    def impact_analysis(self, version_id: int) -> dict:
        candidate = _version_row(self.db, self.tenant_id, version_id)
        definition = _definition_row(self.db, self.tenant_id, int(candidate.definition_id))
        active = (
            _version_row(self.db, self.tenant_id, int(definition.active_version_id))
            if definition.active_version_id else None
        )
        candidate_dto = version_dto(candidate)
        active_dto = version_dto(active) if active else None
        candidate_fields = {field.code for field in candidate_dto.fields}
        active_fields = {field.code for field in active_dto.fields} if active_dto else set()
        candidate_clients = {value.value for value in candidate_dto.supported_clients}
        active_clients = {value.value for value in active_dto.supported_clients} if active_dto else set()
        return {
            "candidateVersionId": str(candidate.id),
            "activeVersionId": str(active.id) if active else "",
            "addedFields": sorted(candidate_fields - active_fields),
            "removedFields": sorted(active_fields - candidate_fields),
            "addedClients": sorted(candidate_clients - active_clients),
            "removedClients": sorted(active_clients - candidate_clients),
            "policyChanged": bool(active_dto and candidate_dto.policy_refs != active_dto.policy_refs),
            "resolveActivePolicyRefs": [
                ref.model_dump(mode="json")
                for ref in candidate_dto.policy_refs
                if ref.binding_mode.value == "RESOLVE_ACTIVE"
            ],
            "adapterChanged": bool(active_dto and (
                candidate_dto.domain_data_adapter != active_dto.domain_data_adapter
                or candidate_dto.domain_command_adapter != active_dto.domain_command_adapter
            )),
        }

    def publish_version(
        self,
        version_id: int,
        *,
        expected_version: int,
        resolve_active_impact_ack: bool = False,
    ) -> BusinessFormVersion:
        candidate_ref = _version_row(self.db, self.tenant_id, version_id)
        # All lifecycle writers use definition -> version lock order.  The old
        # version -> definition order could deadlock a publish of a draft
        # against a concurrent disable of the currently published version.
        definition = _definition_row(
            self.db, self.tenant_id, int(candidate_ref.definition_id), lock=True,
        )
        candidate = _version_row(self.db, self.tenant_id, version_id, lock=True)
        if int(candidate.definition_id) != int(definition.id):
            raise AppException("DATA_CONFLICT", "业务表单版本归属已变化", http_status=409)
        check_version(int(candidate.version or 0), expected_version)
        if candidate.status != "DRAFT":
            raise AppException("DATA_CONFLICT", "仅草稿表单版本可发布", http_status=409)
        candidate_dto = self.validator.validate(version_dto(candidate))
        resolve_active_refs = [
            ref for ref in candidate_dto.policy_refs
            if ref.binding_mode.value == "RESOLVE_ACTIVE"
        ]
        if resolve_active_refs and not resolve_active_impact_ack:
            raise AppException(
                "FORM_POLICY_IMPACT_ACK_REQUIRED",
                "RESOLVE_ACTIVE 策略引用必须先完成并确认影响分析",
                details={
                    "policyRefs": [ref.model_dump(mode="json") for ref in resolve_active_refs],
                },
                http_status=409,
            )
        prior = list(self.db.scalars(select(BusinessFormVersion).where(
            BusinessFormVersion.tenant_id == self.tenant_id,
            BusinessFormVersion.definition_id == int(definition.id),
            BusinessFormVersion.status == "PUBLISHED",
            BusinessFormVersion.is_deleted.is_(False),
        ).with_for_update()).all())
        now = datetime.utcnow()
        for row in prior:
            row.status = "DISABLED"
            row.disabled_at = now
            row.version = int(row.version or 0) + 1
            row.updated_by = self.actor_id
        candidate.status = "PUBLISHED"
        candidate.published_at = now
        candidate.published_by = self.actor_id
        candidate.version = int(candidate.version or 0) + 1
        candidate.updated_by = self.actor_id
        definition.active_version_id = int(candidate.id)
        definition.version = int(definition.version or 0) + 1
        definition.updated_by = self.actor_id
        self.db.flush()
        return candidate

    def disable_version(self, version_id: int, *, expected_version: int) -> BusinessFormVersion:
        row_ref = _version_row(self.db, self.tenant_id, version_id)
        definition = _definition_row(
            self.db, self.tenant_id, int(row_ref.definition_id), lock=True,
        )
        row = _version_row(self.db, self.tenant_id, version_id, lock=True)
        if int(row.definition_id) != int(definition.id):
            raise AppException("DATA_CONFLICT", "业务表单版本归属已变化", http_status=409)
        check_version(int(row.version or 0), expected_version)
        if row.status != "PUBLISHED":
            raise AppException("DATA_CONFLICT", "仅已发布表单版本可停用", http_status=409)
        row.status = "DISABLED"
        row.disabled_at = datetime.utcnow()
        row.version = int(row.version or 0) + 1
        row.updated_by = self.actor_id
        if int(definition.active_version_id or 0) == int(row.id):
            definition.active_version_id = None
            definition.version = int(definition.version or 0) + 1
            definition.updated_by = self.actor_id
        self.db.flush()
        return row
