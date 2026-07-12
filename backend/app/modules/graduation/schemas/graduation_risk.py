"""毕业设计中心 · 问题预警请求 DTO。"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class RiskAcceptRequest(BaseModel):
    assignee: Optional[str] = None


class RiskProcessRequest(BaseModel):
    note: str = Field(..., min_length=2, max_length=1000)


class RiskCloseRequest(BaseModel):
    reason: str = Field(..., min_length=5, description="关闭原因，至少 5 字")
