"""Production application boundary for exact-version form reads and commands.

The shared router is intentionally deferred to PLAT-B C7.  This private service
is the only endpoint-ready path: it loads the tenant's exact active published
version from the database, then delegates business mutation to a canonical
domain command adapter.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import or_, select

from app.core.exceptions import AppException, not_found

from .definition_service import version_dto
from .domain_adapters import (
    BusinessFormCommandAdapterRegistry,
    BusinessFormDataAdapterRegistry,
    BusinessFormSubmissionService,
    DomainCommandResult,
)
from .models import BusinessFormDefinition, BusinessFormVersion
from .runtime import BusinessFormRuntimeValidator
from .schema_validator import BusinessFormSchemaValidator
from .schemas import BusinessFormVersionDTO, FormClient


class BusinessFormApplicationService:
    def __init__(
        self,
        db,
        *,
        tenant_id: int,
        runtime: BusinessFormRuntimeValidator,
        command_adapters: BusinessFormCommandAdapterRegistry,
        data_adapters: BusinessFormDataAdapterRegistry,
    ):
        self.db = db
        self.tenant_id = int(tenant_id)
        self.runtime = runtime
        self.command_adapters = command_adapters
        self.data_adapters = data_adapters
        self.schema_validator = BusinessFormSchemaValidator()

    def load_exact_published_version(
        self, *, form_code: str, version_id: int,
    ) -> BusinessFormVersionDTO:
        code = str(form_code or "").strip().upper()
        now = datetime.utcnow()
        stmt = (
            select(BusinessFormVersion)
            .join(
                BusinessFormDefinition,
                BusinessFormDefinition.id == BusinessFormVersion.definition_id,
            )
            .where(
                BusinessFormVersion.tenant_id == self.tenant_id,
                BusinessFormVersion.id == int(version_id),
                BusinessFormVersion.form_code == code,
                BusinessFormVersion.status == "PUBLISHED",
                BusinessFormVersion.is_deleted.is_(False),
                BusinessFormDefinition.tenant_id == self.tenant_id,
                BusinessFormDefinition.form_code == code,
                BusinessFormDefinition.enabled.is_(True),
                BusinessFormDefinition.active_version_id == BusinessFormVersion.id,
                BusinessFormDefinition.is_deleted.is_(False),
                or_(
                    BusinessFormVersion.effective_at.is_(None),
                    BusinessFormVersion.effective_at <= now,
                ),
            )
        )
        row = self.db.scalars(stmt).first()
        if not row:
            raise not_found("业务表单版本不存在、未生效或已停用")
        dto = version_dto(row)
        # Recompute the hash from persisted content on every read.  This catches
        # direct DB drift as well as caller tampering before any domain command.
        return self.schema_validator.validate(dto)

    def _load_authoritative_initial(
        self, *, version: BusinessFormVersionDTO, context: dict, user: dict,
    ) -> dict:
        adapter = self.data_adapters.get(version.domain_data_adapter)
        raw_initial = adapter.load_initial(context=context, user=user)
        if raw_initial is None:
            raw_initial = {}
        if not isinstance(raw_initial, dict):
            raise AppException(
                "FORM_ADAPTER_INVALID", "业务表单数据适配器必须返回对象", http_status=500,
            )
        field_codes = {field.code for field in version.fields}
        return {key: value for key, value in raw_initial.items() if key in field_codes}

    @staticmethod
    def _condition_field_codes(version: BusinessFormVersionDTO) -> set[str]:
        references: set[str] = set()

        def collect(node: dict | None) -> None:
            if not node:
                return
            field = str(node.get("field") or "").strip()
            if field:
                references.add(field)
            for child in node.get("conditions") or []:
                if isinstance(child, dict):
                    collect(child)

        for field in version.fields:
            collect(field.visible_when)
            collect(field.required_when)
            collect(field.readonly_when)
        return references

    def load_form(
        self,
        *,
        form_code: str,
        version_id: int,
        client: FormClient | str,
        context: dict,
        user: dict,
    ) -> dict:
        version = self.load_exact_published_version(form_code=form_code, version_id=version_id)
        try:
            normalized_client = FormClient(client)
        except (TypeError, ValueError) as exc:
            raise AppException(
                "FORM_CLIENT_UNSUPPORTED", "当前端不支持此表单，请前往 PC 办理", http_status=409,
            ) from exc
        if normalized_client not in version.supported_clients:
            raise AppException(
                "FORM_CLIENT_UNSUPPORTED", "当前端不支持此表单，请前往 PC 办理", http_status=409,
            )
        initial = self._load_authoritative_initial(version=version, context=context, user=user)
        return {
            "formVersion": version,
            "initialData": initial,
        }

    def submit(
        self,
        *,
        form_code: str,
        version_id: int,
        schema_hash: str,
        client: FormClient | str,
        values: dict,
        context: dict,
        expected_business_version: int | None,
        user: dict,
    ) -> DomainCommandResult:
        version = self.load_exact_published_version(form_code=form_code, version_id=version_id)
        if not isinstance(values, dict):
            raise AppException("FORM_VALUE_INVALID", "表单 values 必须是对象", http_status=400)
        condition_fields = self._condition_field_codes(version)
        missing_condition_fields = condition_fields - set(values)
        if missing_condition_fields:
            authoritative_values = self._load_authoritative_initial(
                version=version, context=context, user=user,
            )
        else:
            # Resolve even when no read is necessary so a published version
            # cannot bypass the unknown-adapter fail-closed contract.
            self.data_adapters.get(version.domain_data_adapter)
            authoritative_values = {}
        return BusinessFormSubmissionService(self.runtime, self.command_adapters).submit(
            version=version,
            values=values,
            client=client,
            schema_hash=schema_hash,
            version_id=version_id,
            context=context,
            expected_business_version=expected_business_version,
            user=user,
            authoritative_values=authoritative_values,
        )
