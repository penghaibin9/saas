"""岗位匹配 schemas。"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class IntentionCreate(BaseModel):
    recordId: str
    preferredCity: Optional[str] = None
    preferredIndustry: Optional[str] = None
    preferredCompanyId: Optional[str] = None
    preferredPositionId: Optional[str] = None
    intentionNote: Optional[str] = None


class IntentionUpdate(BaseModel):
    preferredCity: Optional[str] = None
    preferredIndustry: Optional[str] = None
    preferredCompanyId: Optional[str] = None
    preferredPositionId: Optional[str] = None
    intentionNote: Optional[str] = None


class IntentionImport(BaseModel):
    rows: list[dict] = Field(default_factory=list)
    batchId: Optional[str] = Field(None, description="实习批次（必填，导入归属）")


class IntentionImportErrors(BaseModel):
    rows: list[dict] = Field(default_factory=list)
    errors: list[dict] = Field(default_factory=list)


class ManualMatchBody(BaseModel):
    recordId: str
    positionId: str
    remark: Optional[str] = None


class BatchMatchBody(BaseModel):
    pairs: list[dict] = Field(default_factory=list, description="[{recordId, positionId}]")


class MatchActionBody(BaseModel):
    reason: Optional[str] = None
    expectedVersion: Optional[int] = Field(None, ge=0)
    recordExpectedVersion: Optional[int] = Field(None, ge=0)
