"""岗位实习中心 · 实习协议模板库 Pydantic 契约。"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class TemplateVariable(BaseModel):
    key: str
    label: str
    example: str = ""


class AgreementTemplateCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=200)
    category: Optional[str] = None
    version: str = Field("v1.0", max_length=32)
    scopeCollegeIds: list = Field(default_factory=list)
    scopeMajorIds: list = Field(default_factory=list)
    scopeGrades: list = Field(default_factory=list)
    scopeBatchIds: list = Field(default_factory=list)
    body: Optional[str] = None
    variables: list[TemplateVariable] = Field(default_factory=list)
    remark: Optional[str] = None


class AgreementTemplateUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=200)
    category: Optional[str] = None
    version: Optional[str] = Field(None, max_length=32)
    scopeCollegeIds: Optional[list] = None
    scopeMajorIds: Optional[list] = None
    scopeGrades: Optional[list] = None
    scopeBatchIds: Optional[list] = None
    body: Optional[str] = None
    variables: Optional[list[TemplateVariable]] = None
    remark: Optional[str] = None


class StatusAction(BaseModel):
    action: str = Field(..., description="ENABLE / DISABLE / ARCHIVE")
    reason: Optional[str] = None


class SetDefaultRequest(BaseModel):
    on: bool = True


class TemplatePreviewRequest(BaseModel):
    internshipId: str = Field(..., description="实习记录 ID，用于填充变量预览")
