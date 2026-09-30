"""Canonical domain command adapters; no domain ORM writes are allowed here."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from app.core.exceptions import AppException

from .runtime import BusinessFormRuntimeValidator
from .schemas import BusinessFormVersionDTO, FormClient


@dataclass(frozen=True)
class DomainCommandResult:
    domain: str
    command: str
    record_id: str
    status: str
    version: int
    next_action: dict | None = None


class IBusinessFormCommandAdapter(Protocol):
    code: str

    def validate_context(self, *, context: dict, user: dict) -> None: ...

    def submit(
        self,
        *,
        context: dict,
        values: dict,
        form_version: BusinessFormVersionDTO,
        expected_business_version: int | None,
        user: dict,
    ) -> DomainCommandResult: ...


class IBusinessFormDataAdapter(Protocol):
    code: str

    def load_initial(self, *, context: dict, user: dict) -> dict: ...


class InternshipSpecialFilingDataAdapter:
    """Source-backed initial data without reading Internship ORM models.

    The canonical compliance evaluator performs tenant/data-scope checks and
    already owns special-filing trigger semantics.  This adapter only exposes
    its current source status as presentation metadata.
    """

    code = "INTERNSHIP_SPECIAL_FILING_INITIAL"

    def __init__(self, *, compliance_evaluator=None):
        self._compliance_evaluator = compliance_evaluator

    def load_initial(self, *, context: dict, user: dict) -> dict:
        internship_id = context.get("internshipId")
        if not internship_id:
            raise AppException("FORM_CONTEXT_INVALID", "缺少 internshipId")
        if self._compliance_evaluator is None:
            from app.modules.internship.services.internship_compliance_authoritative_service import (
                evaluate_internship_compliance,
            )

            evaluator = evaluate_internship_compliance
        else:
            evaluator = self._compliance_evaluator
        assessment = evaluator(str(internship_id), "ONBOARD", user=user)
        special_filing = next(
            (
                item for item in assessment.get("items") or []
                if str(item.get("code") or "").lower() == "specialfiling"
            ),
            None,
        )
        return {
            "serverStatus": str((special_filing or {}).get("status") or "NOT_EVALUATED"),
        }


class InternshipSpecialFilingCommandAdapter:
    code = "INTERNSHIP_SPECIAL_FILING"
    _CREATE_FIELDS = {
        "filingType", "triggerReason", "destinationRegion", "workAddress",
        "riskDescription", "studentApplication", "guardianConsentRequired",
        "fileIds", "validUntil",
    }

    def __init__(self, *, create_command=None, submit_command=None):
        self._create_command = create_command
        self._submit_command = submit_command

    def validate_context(self, *, context: dict, user: dict) -> None:
        del user
        action = str(context.get("action") or "CREATE").upper()
        if action == "CREATE" and not context.get("internshipId"):
            raise AppException("FORM_CONTEXT_INVALID", "缺少 internshipId")
        if action == "SUBMIT" and not context.get("filingId"):
            raise AppException("FORM_CONTEXT_INVALID", "缺少 filingId")
        if action not in {"CREATE", "SUBMIT"}:
            raise AppException("FORM_CONTEXT_INVALID", "特殊备案表单 action 仅支持 CREATE/SUBMIT")

    def submit(
        self,
        *,
        context: dict,
        values: dict,
        form_version: BusinessFormVersionDTO,
        expected_business_version: int | None,
        user: dict,
    ) -> DomainCommandResult:
        del form_version
        action = str(context.get("action") or "CREATE").upper()
        if action == "CREATE":
            from app.modules.internship.services import internship_special_filing_service as canonical
            command = self._create_command or canonical.create
            body = {key: value for key, value in values.items() if key in self._CREATE_FIELDS}
            body["internshipId"] = str(context["internshipId"])
            result = command(body, user)
        else:
            if expected_business_version is None:
                raise AppException("FORM_EXPECTED_VERSION_REQUIRED", "提交特殊备案必须提供 expectedBusinessVersion", http_status=409)
            from app.modules.internship.services import internship_special_filing_service as canonical
            command = self._submit_command or canonical.submit
            result = command(
                str(context["filingId"]), user=user,
                expected_version=expected_business_version,
            )
        return DomainCommandResult(
            domain="INTERNSHIP",
            command=f"SPECIAL_FILING_{action}",
            record_id=str(result["id"]),
            status=str(result["status"]),
            version=int(result.get("version") or 0),
            next_action=result.get("nextAction"),
        )


class BusinessFormCommandAdapterRegistry:
    def __init__(self, adapters: list[IBusinessFormCommandAdapter]):
        self._adapters = {}
        for adapter in adapters:
            code = str(adapter.code or "").strip().upper()
            if not code or code in self._adapters:
                raise AppException("FORM_ADAPTER_INVALID", "业务表单命令适配器 code 为空或重复")
            self._adapters[code] = adapter

    def get(self, code: str) -> IBusinessFormCommandAdapter:
        adapter = self._adapters.get(str(code or "").strip().upper())
        if not adapter:
            raise AppException("FORM_ADAPTER_NOT_FOUND", "未知业务表单命令适配器", http_status=409)
        return adapter


class BusinessFormDataAdapterRegistry:
    def __init__(self, adapters: list[IBusinessFormDataAdapter]):
        self._adapters = {}
        for adapter in adapters:
            code = str(adapter.code or "").strip().upper()
            if not code or code in self._adapters:
                raise AppException("FORM_ADAPTER_INVALID", "业务表单数据适配器 code 为空或重复")
            self._adapters[code] = adapter

    def get(self, code: str) -> IBusinessFormDataAdapter:
        adapter = self._adapters.get(str(code or "").strip().upper())
        if not adapter:
            raise AppException("FORM_ADAPTER_NOT_FOUND", "未知业务表单数据适配器", http_status=409)
        return adapter


class BusinessFormSubmissionService:
    def __init__(self, runtime: BusinessFormRuntimeValidator, registry: BusinessFormCommandAdapterRegistry):
        self._runtime = runtime
        self._registry = registry

    def submit(
        self,
        *,
        version: BusinessFormVersionDTO,
        values: dict,
        client: FormClient | str,
        schema_hash: str,
        version_id: int,
        context: dict,
        expected_business_version: int | None,
        user: dict,
        authoritative_values: dict | None = None,
    ) -> DomainCommandResult:
        sanitized = self._runtime.validate_submission(
            version=version,
            submitted_values=values,
            client=client,
            schema_hash=schema_hash,
            version_id=version_id,
            context=context,
            user=user,
            authoritative_values=authoritative_values,
        )
        adapter = self._registry.get(version.domain_command_adapter)
        adapter.validate_context(context=context, user=user)
        return adapter.submit(
            context=context,
            values=sanitized,
            form_version=version,
            expected_business_version=expected_business_version,
            user=user,
        )
