"""E-A01 recruitment campaign and enterprise invite request DTOs."""
from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

ContactSharingMode = Literal["MASKED_ONLY", "AFTER_INTERVIEW", "AFTER_ACCEPT_INTENT", "IMMEDIATE"]
ProfileSection = Literal["SELF_INTRO", "SKILLS", "AVAILABILITY", "LOCATION_PREFERENCES"]
ProfileItemType = Literal["SKILL_EVIDENCE", "CERTIFICATE", "PROJECT", "PRACTICE", "AWARD", "PORTFOLIO"]


class ApplicationMaterialPolicy(BaseModel):
    """Versioned/fail-closed material policy stored on RecruitmentCampaign."""

    model_config = ConfigDict(extra="forbid")

    schemaVersion: Literal["V1"] = "V1"
    profileRequired: bool = False
    requiredSections: list[ProfileSection] = Field(default_factory=list, max_length=10)
    requiredItemTypes: list[ProfileItemType] = Field(default_factory=list, max_length=20)
    applicationStatementRequired: bool = False
    minStatementLength: int = Field(default=0, ge=0, le=5000)
    resumePdfEnabled: bool = True
    allowedContactSharingModes: list[ContactSharingMode] = Field(
        default_factory=lambda: ["MASKED_ONLY", "AFTER_INTERVIEW", "AFTER_ACCEPT_INTENT"]
    )


class RecruitmentCampaignCreate(BaseModel):
    batchId: str
    campaignCode: str = Field(min_length=1, max_length=100)
    campaignName: str = Field(min_length=1, max_length=200)
    roundNo: int = Field(default=1, ge=1)
    inviteStartAt: Optional[datetime] = None
    inviteEndAt: Optional[datetime] = None
    positionSubmitStartAt: Optional[datetime] = None
    positionSubmitEndAt: Optional[datetime] = None
    studentSelectStartAt: Optional[datetime] = None
    studentSelectEndAt: Optional[datetime] = None
    enterpriseDecisionStartAt: Optional[datetime] = None
    enterpriseDecisionEndAt: Optional[datetime] = None
    schoolConfirmStartAt: Optional[datetime] = None
    schoolConfirmEndAt: Optional[datetime] = None
    enterpriseAccessEndAt: Optional[datetime] = None
    enterpriseConfirmRequired: bool = False
    teacherConfirmSlaHours: int = Field(default=48, ge=1, le=168)
    applicationMaterialPolicy: Optional[ApplicationMaterialPolicy] = None
    remark: Optional[str] = Field(default=None, max_length=500)


class RecruitmentCampaignUpdate(BaseModel):
    expectedVersion: int = Field(ge=0)
    batchId: Optional[str] = None
    campaignCode: Optional[str] = Field(default=None, min_length=1, max_length=100)
    campaignName: Optional[str] = Field(default=None, min_length=1, max_length=200)
    roundNo: Optional[int] = Field(default=None, ge=1)
    inviteStartAt: Optional[datetime] = None
    inviteEndAt: Optional[datetime] = None
    positionSubmitStartAt: Optional[datetime] = None
    positionSubmitEndAt: Optional[datetime] = None
    studentSelectStartAt: Optional[datetime] = None
    studentSelectEndAt: Optional[datetime] = None
    enterpriseDecisionStartAt: Optional[datetime] = None
    enterpriseDecisionEndAt: Optional[datetime] = None
    schoolConfirmStartAt: Optional[datetime] = None
    schoolConfirmEndAt: Optional[datetime] = None
    enterpriseAccessEndAt: Optional[datetime] = None
    enterpriseConfirmRequired: Optional[bool] = None
    teacherConfirmSlaHours: Optional[int] = Field(default=None, ge=1, le=168)
    applicationMaterialPolicy: Optional[ApplicationMaterialPolicy] = None
    remark: Optional[str] = Field(default=None, max_length=500)


class RecruitmentCampaignVersionAction(BaseModel):
    expectedVersion: int = Field(ge=0)


class CampaignEnterpriseInvite(BaseModel):
    companyId: str
    inviteSource: Literal["MANUAL", "REUSE", "PUBLIC_REQUEST"] = "MANUAL"
    loginName: str = Field(min_length=1, max_length=100)
    realName: str = Field(min_length=1, max_length=100)
    phone: str = Field(min_length=6, max_length=30)
    memberRole: Literal["COMPANY_ADMIN", "HR", "MENTOR"] = "COMPANY_ADMIN"


class CampaignEnterpriseRevoke(BaseModel):
    expectedVersion: int = Field(ge=0)
    reason: str = Field(min_length=2, max_length=500)


class EnterpriseInviteInspect(BaseModel):
    tenantCode: str = Field(min_length=1, max_length=100)
    token: str = Field(min_length=32, max_length=512)


class EnterpriseInviteAccept(EnterpriseInviteInspect):
    phone: str = Field(min_length=6, max_length=30)
    password: str = Field(min_length=8, max_length=128)


class EnterpriseLogin(BaseModel):
    tenantCode: str = Field(min_length=1, max_length=100)
    loginName: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=1, max_length=128)
    memberId: Optional[str] = None


class EnterpriseRefresh(BaseModel):
    refreshToken: str = Field(min_length=16)
