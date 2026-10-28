"""School-only enterprise member maintenance; enterprise login routes remain separate."""
from typing import Literal
from fastapi import APIRouter, Depends, Query
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field
from app.core.permissions import require_permission
from app.core.response import success
from app.modules.internship.services import internship_enterprise_member_admin_service as service

router = APIRouter(prefix="/internship/enterprises", tags=["岗位实习-企业成员与授权"])


def manager(user=Depends(require_permission("internship.enterprise.manage"))):
    return service.require_school_manager(user)


class ContactBinding(BaseModel):
    model_config = ConfigDict(extra="forbid")
    contactId: str = Field(pattern=r"^[1-9][0-9]{0,18}$")
    expectedVersion: int = Field(ge=0, strict=True)


class StatusChange(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: Literal["ACTIVE", "DISABLED"]
    expectedVersion: int = Field(ge=0, strict=True)
    reason: str = Field(min_length=2, max_length=500)


class CollaborationGrant(BaseModel):
    model_config = ConfigDict(extra="forbid")
    batchId: str = Field(pattern=r"^[1-9][0-9]{0,18}$")
    validFrom: AwareDatetime
    validUntil: AwareDatetime
    expectedMemberVersion: int = Field(ge=0, strict=True)


class GrantRevoke(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expectedVersion: int = Field(ge=0, strict=True)
    reason: str = Field(min_length=2, max_length=500)


@router.get("/{company_id}/members")
def members(company_id: str, page: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=100), user=Depends(manager)):
    return success(service.list_members(company_id, user, page=page, page_size=pageSize))


@router.put("/{company_id}/members/{member_id}/contact")
def bind_contact(company_id: str, member_id: str, body: ContactBinding, user=Depends(manager)):
    return success(service.bind_contact(company_id, member_id, body.contactId, body.expectedVersion, user), message="联系人已绑定，成员需重新登录")


@router.post("/{company_id}/members/{member_id}/status")
def status(company_id: str, member_id: str, body: StatusChange, user=Depends(manager)):
    return success(service.change_status(company_id, member_id, body.status, body.expectedVersion, body.reason, user), message="成员状态已更新")


@router.get("/{company_id}/members/{member_id}/collaboration-grants")
def grants(company_id: str, member_id: str, page: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=100), user=Depends(manager)):
    return success(service.list_grants(company_id, member_id, user, page=page, page_size=pageSize))


@router.post("/{company_id}/members/{member_id}/collaboration-grants")
def issue(company_id: str, member_id: str, body: CollaborationGrant, user=Depends(manager)):
    return success(service.issue_collaboration(company_id, member_id, body.batchId, body.validFrom, body.validUntil, body.expectedMemberVersion, user), message="已开通该批次实习协同")


@router.post("/{company_id}/members/{member_id}/collaboration-grants/{grant_id}/revoke")
def revoke(company_id: str, member_id: str, grant_id: str, body: GrantRevoke, user=Depends(manager)):
    return success(service.revoke_collaboration(company_id, member_id, grant_id, body.expectedVersion, body.reason, user), message="该批次协同授权已撤销")
