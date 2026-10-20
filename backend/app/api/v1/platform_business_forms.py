"""PLAT-B compliance federation and immutable schema-form APIs."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Path, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select

from app.core.context import current_tenant_id
from app.core.exceptions import AppException
from app.core.permissions import is_super_admin, require_any_permission
from app.core.response import success
from app.core.security import get_current_user
from app.db.session import get_db
from app.models import StudentProfile
from app.modules.platform.business_forms import (
    BusinessFormApplicationService,
    BusinessFormCommandAdapterRegistry,
    BusinessFormDataAdapterRegistry,
    BusinessFormDefinitionService,
    BusinessFormRuntimeValidator,
    InternshipSpecialFilingCommandAdapter,
    InternshipSpecialFilingDataAdapter,
)
from app.modules.platform.business_forms.definition_service import version_dto
from app.modules.platform.business_forms.models import BusinessFormDefinition, BusinessFormVersion
from app.modules.platform.compliance_federation import SubjectRef, default_federation
from app.services.message_identity import resolve_message_user_id


router = APIRouter(tags=["PLAT-B·合规与业务表单"])

_FORM_VIEW = require_any_permission(
    "systemAdmin.config.view", "systemAdmin.config.manage",
)
_FORM_MANAGE = require_any_permission("systemAdmin.config.manage")


class ComplianceEvaluateBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    providerCode: str
    subjectRef: SubjectRef
    operation: str = "READ"


class DefinitionCreateBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    formCode: str
    formName: str
    domainCode: str
    description: str = ""


class DraftCreateBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schemaVersion: str = "1.0"
    supportedClients: list[str]
    policyRefs: list[dict[str, Any]] = Field(default_factory=list)
    domainDataAdapter: str
    domainCommandAdapter: str
    fields: list[dict[str, Any]]
    conditions: list[dict[str, Any]] = Field(default_factory=list)


class LifecycleBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expectedVersion: int = Field(ge=0)
    resolveActiveImpactAck: bool = False


class FormLoadBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    formCode: str
    versionId: int = Field(ge=1)
    client: str
    context: dict[str, Any] = Field(default_factory=dict)
    complianceRequests: list[ComplianceEvaluateBody] = Field(default_factory=list)


class FormSubmitBody(FormLoadBody):
    schemaHash: str
    values: dict[str, Any]
    expectedBusinessVersion: int | None = Field(default=None, ge=0)


def _tenant_id() -> int:
    try:
        tenant_id = int(current_tenant_id() or 0)
    except (TypeError, ValueError):
        tenant_id = 0
    if not tenant_id:
        raise AppException("TENANT_CONTEXT_REQUIRED", "缺少租户上下文", http_status=403)
    return tenant_id


def _definition_payload(row: BusinessFormDefinition) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "formCode": row.form_code,
        "formName": row.form_name,
        "domainCode": row.domain_code,
        "description": row.description or "",
        "enabled": bool(row.enabled),
        "activeVersionId": str(row.active_version_id) if row.active_version_id else "",
        "version": int(row.version or 0),
    }


def _version_payload(row: BusinessFormVersion) -> dict[str, Any]:
    dto = version_dto(row)
    return {
        "formVersion": dto,
        "versionId": str(row.id),
        "versionNo": int(row.version_no),
        "schemaHash": row.schema_hash,
        "supportedClients": sorted(value.value for value in dto.supported_clients),
        "definitionId": str(row.definition_id),
        "status": row.status,
        "effectiveAt": row.effective_at,
        "publishedAt": row.published_at,
        "disabledAt": row.disabled_at,
        "version": int(row.version or 0),
    }


def _student_authorizer(db, tenant_id: int):
    def authorize(student_id: Any, _context: dict, user: dict) -> bool:
        try:
            value = int(student_id)
        except (TypeError, ValueError):
            return False
        student = db.scalars(select(StudentProfile).where(
            StudentProfile.id == value,
            StudentProfile.tenant_id == tenant_id,
            StudentProfile.is_deleted.is_(False),
        )).first()
        if not student:
            return False
        user_type = str((user or {}).get("userType") or "").upper()
        if user_type == "STUDENT":
            own_ids = {
                str((user or {}).get("studentId") or ""),
                str((user or {}).get("profileId") or ""),
            }
            return str(student.id) in own_ids
        if is_super_admin(user or {}):
            return True
        from app.core.affairs_security import build_affairs_context

        allowed = build_affairs_context(user or {}, db).allowed_class_ids(db)
        return allowed is None or (
            student.class_id is not None
            and int(student.class_id) in {int(item) for item in allowed}
        )

    return authorize


def _file_authorizer(file_id: Any, _context: dict, user: dict) -> bool:
    from app.services.file_access_service import require_file_access
    from app.services.file_scan_service import assert_file_ready_for_business

    require_file_access(str(file_id), user=user, action="bind")
    assert_file_ready_for_business(str(file_id), user=user)
    return True


def _application_service(db, tenant_id: int) -> BusinessFormApplicationService:
    runtime = BusinessFormRuntimeValidator(
        student_authorizer=_student_authorizer(db, tenant_id),
        file_authorizer=_file_authorizer,
    )
    return BusinessFormApplicationService(
        db,
        tenant_id=tenant_id,
        runtime=runtime,
        command_adapters=BusinessFormCommandAdapterRegistry([
            InternshipSpecialFilingCommandAdapter(),
        ]),
        data_adapters=BusinessFormDataAdapterRegistry([
            InternshipSpecialFilingDataAdapter(),
        ]),
    )


def _evaluate_requests(
    requests: list[ComplianceEvaluateBody], *, user: dict, allowed_providers: set[str] | None = None,
) -> list:
    federation = default_federation()
    results = []
    for item in requests:
        provider_code = str(item.providerCode or "").strip().upper()
        if allowed_providers is not None and provider_code not in allowed_providers:
            raise AppException(
                "FORM_POLICY_REF_MISMATCH",
                "表单未引用该合规 provider",
                http_status=409,
            )
        results.append(federation.evaluate(
            provider_code=provider_code,
            subject_ref=item.subjectRef,
            operation=item.operation,
            user=user,
        ))
    return results


@router.post("/platform/compliance/evaluate", summary="按来源域实时评估合规状态")
def evaluate_compliance(body: ComplianceEvaluateBody, user=Depends(get_current_user)):
    return success(_evaluate_requests([body], user=user)[0])


@router.get("/platform/business-forms", summary="Staff PC·表单定义列表")
def list_definitions(
    domainCode: str | None = Query(None),
    limit: int = Query(100, ge=1, le=200),
    user=Depends(_FORM_VIEW),
    db=Depends(get_db),
):
    del user
    stmt = select(BusinessFormDefinition).where(
        BusinessFormDefinition.tenant_id == _tenant_id(),
        BusinessFormDefinition.is_deleted.is_(False),
    )
    if domainCode:
        stmt = stmt.where(BusinessFormDefinition.domain_code == domainCode.strip().upper())
    rows = db.scalars(stmt.order_by(BusinessFormDefinition.id.desc()).limit(limit)).all()
    return success([_definition_payload(row) for row in rows])


@router.post("/platform/business-forms", summary="Staff PC·创建表单定义")
def create_definition(
    body: DefinitionCreateBody,
    user=Depends(_FORM_MANAGE),
    db=Depends(get_db),
):
    service = BusinessFormDefinitionService(
        db, tenant_id=_tenant_id(), actor_id=resolve_message_user_id(user) or None,
    )
    try:
        row = service.create_definition(
            form_code=body.formCode,
            form_name=body.formName,
            domain_code=body.domainCode,
            description=body.description,
        )
        db.commit()
        return success(_definition_payload(row))
    except Exception:
        db.rollback()
        raise


@router.get("/platform/business-forms/{definition_id}/versions", summary="Staff PC·版本列表")
def list_versions(
    definition_id: int = Path(..., ge=1),
    user=Depends(_FORM_VIEW),
    db=Depends(get_db),
):
    del user
    tenant_id = _tenant_id()
    definition = db.scalars(select(BusinessFormDefinition).where(
        BusinessFormDefinition.id == definition_id,
        BusinessFormDefinition.tenant_id == tenant_id,
        BusinessFormDefinition.is_deleted.is_(False),
    )).first()
    if not definition:
        from app.core.exceptions import not_found
        raise not_found("业务表单定义不存在")
    rows = db.scalars(select(BusinessFormVersion).where(
        BusinessFormVersion.definition_id == definition_id,
        BusinessFormVersion.tenant_id == tenant_id,
        BusinessFormVersion.is_deleted.is_(False),
    ).order_by(BusinessFormVersion.version_no.desc())).all()
    return success([_version_payload(row) for row in rows])


@router.get("/platform/business-form-versions/{version_id}", summary="Staff PC·版本预览数据")
def get_version(
    version_id: int = Path(..., ge=1),
    user=Depends(_FORM_VIEW),
    db=Depends(get_db),
):
    del user
    row = db.scalars(select(BusinessFormVersion).where(
        BusinessFormVersion.id == version_id,
        BusinessFormVersion.tenant_id == _tenant_id(),
        BusinessFormVersion.is_deleted.is_(False),
    )).first()
    if not row:
        from app.core.exceptions import not_found
        raise not_found("业务表单版本不存在")
    return success(_version_payload(row))


@router.post("/platform/business-forms/{definition_id}/versions", summary="Staff PC·创建不可变草稿版本")
def create_draft_version(
    body: DraftCreateBody,
    definition_id: int = Path(..., ge=1),
    user=Depends(_FORM_MANAGE),
    db=Depends(get_db),
):
    service = BusinessFormDefinitionService(
        db, tenant_id=_tenant_id(), actor_id=resolve_message_user_id(user) or None,
    )
    try:
        row = service.create_draft_version(definition_id, body.model_dump())
        db.commit()
        return success(_version_payload(row))
    except Exception:
        db.rollback()
        raise


@router.get("/platform/business-form-versions/{version_id}/validate", summary="Staff PC·验证版本")
def validate_version(
    version_id: int = Path(..., ge=1),
    user=Depends(_FORM_VIEW),
    db=Depends(get_db),
):
    del user
    service = BusinessFormDefinitionService(db, tenant_id=_tenant_id(), actor_id=None)
    return success(service.validate_version(version_id))


@router.get("/platform/business-form-versions/{version_id}/impact", summary="Staff PC·发布影响分析")
def version_impact(
    version_id: int = Path(..., ge=1),
    user=Depends(_FORM_VIEW),
    db=Depends(get_db),
):
    del user
    service = BusinessFormDefinitionService(db, tenant_id=_tenant_id(), actor_id=None)
    return success(service.impact_analysis(version_id))


@router.post("/platform/business-form-versions/{version_id}/publish", summary="Staff PC·发布版本")
def publish_version(
    body: LifecycleBody,
    version_id: int = Path(..., ge=1),
    user=Depends(_FORM_MANAGE),
    db=Depends(get_db),
):
    service = BusinessFormDefinitionService(
        db, tenant_id=_tenant_id(), actor_id=resolve_message_user_id(user) or None,
    )
    try:
        row = service.publish_version(
            version_id,
            expected_version=body.expectedVersion,
            resolve_active_impact_ack=body.resolveActiveImpactAck,
        )
        db.commit()
        return success(_version_payload(row))
    except Exception:
        db.rollback()
        raise


@router.post("/platform/business-form-versions/{version_id}/disable", summary="Staff PC·停用版本")
def disable_version(
    body: LifecycleBody,
    version_id: int = Path(..., ge=1),
    user=Depends(_FORM_MANAGE),
    db=Depends(get_db),
):
    service = BusinessFormDefinitionService(
        db, tenant_id=_tenant_id(), actor_id=resolve_message_user_id(user) or None,
    )
    try:
        row = service.disable_version(version_id, expected_version=body.expectedVersion)
        db.commit()
        return success(_version_payload(row))
    except Exception:
        db.rollback()
        raise


@router.post("/business-forms/runtime/load", summary="四端·加载 exact FormVersion 与服务端初始值")
def load_form(
    body: FormLoadBody,
    user=Depends(get_current_user),
    db=Depends(get_db),
):
    service = _application_service(db, _tenant_id())
    result = service.load_form(
        form_code=body.formCode,
        version_id=body.versionId,
        client=body.client,
        context=body.context,
        user=user,
    )
    allowed = {ref.provider_code.upper() for ref in result["formVersion"].policy_refs}
    result["complianceSummary"] = _evaluate_requests(
        body.complianceRequests, user=user, allowed_providers=allowed,
    )
    return success(result)


@router.post("/business-forms/runtime/submit", summary="四端·校验后调用现有 canonical command")
def submit_form(
    body: FormSubmitBody,
    user=Depends(get_current_user),
    db=Depends(get_db),
):
    result = _application_service(db, _tenant_id()).submit(
        form_code=body.formCode,
        version_id=body.versionId,
        schema_hash=body.schemaHash,
        client=body.client,
        values=body.values,
        context=body.context,
        expected_business_version=body.expectedBusinessVersion,
        user=user,
    )
    return success({
        "domain": result.domain,
        "command": result.command,
        "recordId": result.record_id,
        "status": result.status,
        "version": result.version,
        "nextAction": result.next_action,
    })


__all__ = ["router"]
