"""Platform form metadata maintenance; every object stays bound to the selected school."""
from fastapi import APIRouter, Depends, Path, Query
from pydantic import ConfigDict, Field
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.core.exceptions import AppException, not_found
from app.core.platform_principal import require_platform_principal
from app.core.response import success
from app.core.tenant_identity import PLATFORM
from app.db.session import get_db
from app.models import Tenant
from app.api.v1.platform_business_forms import (
    DefinitionCreateBody, DraftCreateBody, LifecycleBody,
    _definition_payload, _version_payload,
)
from app.modules.platform.business_forms.definition_service import BusinessFormDefinitionService, _definition_row, _version_row
from app.modules.platform.business_forms.models import BusinessFormDefinition, BusinessFormVersion
from app.services.db_service import audit_insert_in_session
from app.services.message_identity import resolve_message_user_id

VIEW = "platform.businessForms.view"
MANAGE = "platform.businessForms.manage"
router = APIRouter(prefix="/platform", tags=["平台·业务表单维护"])
def _view(user=Depends(require_platform_principal)):
    from app.services.platform_access_governance_service import assert_platform_capability
    return assert_platform_capability(user, "businessForms.view")


def _manage(user=Depends(require_platform_principal)):
    from app.services.platform_access_governance_service import assert_platform_capability
    return assert_platform_capability(user, "businessForms.manage")


class CreateDefinition(DefinitionCreateBody):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    reason: str = Field(min_length=5, max_length=500)


class CreateDraft(DraftCreateBody):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    reason: str = Field(min_length=5, max_length=500)


class Lifecycle(LifecycleBody):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    reason: str = Field(min_length=5, max_length=500)


def _school(db, tenant_id):
    row = db.scalar(select(Tenant).where(Tenant.id == tenant_id, Tenant.is_deleted.is_(False)))
    if row is None or int(row.id) <= 0 or int(row.id) == PLATFORM.tenant_id:
        raise not_found("目标学校不存在")
    return row


def _service(db, tenant_id, user):
    _school(db, tenant_id)
    return BusinessFormDefinitionService(db, tenant_id=tenant_id, actor_id=resolve_message_user_id(user) or None)


def _commit(db, tenant_id, row, action, reason):
    try:
        audit_insert_in_session(db, action, f"business-form:{row.id}",
                                {"targetTenantId": str(tenant_id), "objectId": str(row.id),
                                 "version": int(row.version or 0), "reason": reason},
                                "SUCCESS", tenant_id=0, resource_id=str(row.id))
        db.commit()
    except Exception:
        db.rollback()
        raise


@router.get("/business-form-schools")
def schools(keyword: str = Query("", max_length=100), limit: int = Query(30, ge=1, le=50),
            user=Depends(_view), db=Depends(get_db)):
    stmt = select(Tenant).where(Tenant.id > 0, Tenant.id != PLATFORM.tenant_id, Tenant.is_deleted.is_(False))
    if keyword.strip():
        stmt = stmt.where(Tenant.school_name.contains(keyword.strip()) | Tenant.tenant_code.contains(keyword.strip()))
    rows = db.scalars(stmt.order_by(Tenant.id).limit(limit + 1)).all()
    return success({"items": [{"tenantId": str(x.id), "tenantName": x.school_name, "tenantCode": x.tenant_code}
                              for x in rows[:limit]], "hasMore": len(rows) > limit})


@router.get("/tenants/{tenant_id}/business-forms")
def definitions(tenant_id: int = Path(gt=0), limit: int = Query(200, ge=1, le=200),
                user=Depends(_view), db=Depends(get_db)):
    school = _school(db, tenant_id)
    rows = db.scalars(select(BusinessFormDefinition).where(
        BusinessFormDefinition.tenant_id == tenant_id, BusinessFormDefinition.is_deleted.is_(False)
    ).order_by(BusinessFormDefinition.id.desc()).limit(limit)).all()
    return success({"tenantId": str(school.id), "tenantName": school.school_name,
                    "items": [_definition_payload(x) for x in rows]})


@router.get("/tenants/{tenant_id}/business-form-sources")
def sources(tenant_id: int = Path(gt=0), user=Depends(_view), db=Depends(get_db)):
    _school(db, tenant_id)
    from app.modules.platform.compliance_federation import default_federation
    from app.modules.platform.compliance_federation.inventory import DOMAIN_COMPLIANCE_INVENTORY
    registered = set(default_federation().provider_codes)
    names = {"INTERNSHIP": "岗位实习", "GRADUATION": "毕业设计", "STUDENT_AFFAIRS": "学工", "ACADEMIC": "教务"}
    return success({"tenantId": str(tenant_id), "scope": "REGISTERED_CAPABILITIES_ONLY", "items": [
        {"domain": item['domain'], "domainName": names.get(item['domain'], '其他业务域'),
         "providerCode": item['providerCode'], "registered": item['providerCode'] in registered,
         "mode": item['mode'], "supportedClients": list(item['fourClientConsumers']),
         "operationCodes": list(item['operationCodes']), "ruleSource": item['ruleSource']}
        for item in DOMAIN_COMPLIANCE_INVENTORY]})


@router.post("/tenants/{tenant_id}/business-forms")
def create_definition(body: CreateDefinition, tenant_id: int = Path(gt=0), user=Depends(_manage), db=Depends(get_db)):
    try:
        row = _service(db, tenant_id, user).create_definition(form_code=body.formCode, form_name=body.formName,
                                                            domain_code=body.domainCode, description=body.description)
    except IntegrityError:
        db.rollback()
        raise AppException("DATA_CONFLICT", "该学校已有同编码表单，请重新读取核对", http_status=409) from None
    _commit(db, tenant_id, row, "PLATFORM_FORM_CREATE", body.reason)
    return success(_definition_payload(row))


@router.get("/tenants/{tenant_id}/business-forms/{definition_id}/versions")
def versions(tenant_id: int = Path(gt=0), definition_id: int = Path(gt=0), page: int = Query(1, ge=1),
             pageSize: int = Query(50, ge=1, le=100), user=Depends(_view), db=Depends(get_db)):
    _school(db, tenant_id)
    _definition_row(db, tenant_id, definition_id)
    clauses = (
        BusinessFormVersion.tenant_id == tenant_id, BusinessFormVersion.definition_id == definition_id,
        BusinessFormVersion.is_deleted.is_(False))
    total = int(db.scalar(select(func.count()).select_from(BusinessFormVersion).where(*clauses)) or 0)
    rows = db.scalars(select(BusinessFormVersion).where(*clauses).order_by(BusinessFormVersion.version_no.desc())
                      .offset((page - 1) * pageSize).limit(pageSize)).all()
    return success({"items": [{"versionId": str(x.id), "definitionId": str(x.definition_id),
                               "versionNo": x.version_no, "version": int(x.version or 0), "status": x.status,
                               "schemaHash": x.schema_hash, "supportedClients": x.supported_clients_json or []}
                              for x in rows], "page": page, "pageSize": pageSize, "total": total})


@router.post("/tenants/{tenant_id}/business-forms/{definition_id}/versions")
def create_draft(body: CreateDraft, tenant_id: int = Path(gt=0), definition_id: int = Path(gt=0),
                 user=Depends(_manage), db=Depends(get_db)):
    try:
        row = _service(db, tenant_id, user).create_draft_version(definition_id, body.model_dump(exclude={"reason"}))
    except IntegrityError:
        db.rollback()
        raise AppException("DATA_CONFLICT", "该学校已有相同结构版本，请重新读取核对", http_status=409) from None
    _commit(db, tenant_id, row, "PLATFORM_FORM_DRAFT", body.reason)
    return success(_version_payload(row))


@router.get("/tenants/{tenant_id}/business-form-versions/{version_id}")
def version(tenant_id: int = Path(gt=0), version_id: int = Path(gt=0), user=Depends(_view), db=Depends(get_db)):
    _school(db, tenant_id)
    return success(_version_payload(_version_row(db, tenant_id, version_id)))


@router.get("/tenants/{tenant_id}/business-form-versions/{version_id}/validate")
def validate(tenant_id: int = Path(gt=0), version_id: int = Path(gt=0), user=Depends(_view), db=Depends(get_db)):
    return success(_service(db, tenant_id, user).validate_version(version_id))


@router.get("/tenants/{tenant_id}/business-form-versions/{version_id}/impact")
def impact(tenant_id: int = Path(gt=0), version_id: int = Path(gt=0), user=Depends(_view), db=Depends(get_db)):
    return success(_service(db, tenant_id, user).impact_analysis(version_id))


@router.post("/tenants/{tenant_id}/business-form-versions/{version_id}/publish")
def publish(body: Lifecycle, tenant_id: int = Path(gt=0), version_id: int = Path(gt=0),
            user=Depends(_manage), db=Depends(get_db)):
    row = _service(db, tenant_id, user).publish_version(version_id, expected_version=body.expectedVersion,
                                                      resolve_active_impact_ack=body.resolveActiveImpactAck)
    _commit(db, tenant_id, row, "PLATFORM_FORM_PUBLISH", body.reason)
    return success(_version_payload(row))


@router.post("/tenants/{tenant_id}/business-form-versions/{version_id}/disable")
def disable(body: Lifecycle, tenant_id: int = Path(gt=0), version_id: int = Path(gt=0),
            user=Depends(_manage), db=Depends(get_db)):
    row = _service(db, tenant_id, user).disable_version(version_id, expected_version=body.expectedVersion)
    _commit(db, tenant_id, row, "PLATFORM_FORM_DISABLE", body.reason)
    return success(_version_payload(row))
