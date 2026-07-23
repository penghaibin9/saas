"""毕业设计中心 · 指导过程记录请求 DTO。"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class GuidanceCreate(BaseModel):
    guidanceDate: Optional[str] = None
    method: str = Field(default="ONLINE", description="ONLINE/OFFLINE")
    content: str = Field(..., min_length=2, max_length=2000)
    issues: Optional[str] = None
    attachments: Optional[list[dict]] = None


class GuidanceVoidRequest(BaseModel):
    reason: str = Field(..., min_length=5, description="撤销原因，至少 5 字")


class GuidancePlanCreate(BaseModel):
    title: str = Field(..., min_length=2, max_length=200)
    planDate: Optional[str] = None
    content: Optional[str] = Field(default=None, max_length=2000)


class GuidancePlanCheckin(BaseModel):
    method: Optional[str] = Field(default="MANUAL", description="ONLINE/OFFLINE/MANUAL")
    note: Optional[str] = Field(default=None, max_length=500)


class GuidancePlanCancel(BaseModel):
    reason: str = Field(..., min_length=5, description="取消原因，至少 5 字")
