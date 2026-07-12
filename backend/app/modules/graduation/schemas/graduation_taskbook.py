"""毕业设计中心 · 任务书请求 DTO（独立文件，与毕业设计域其它 schema 隔离）。"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class TaskBookIssue(BaseModel):
    objective: str = Field(..., min_length=2, max_length=2000)
    content: str = Field(..., min_length=2, max_length=2000)
    progressPlan: Optional[str] = None
    outcomeRequirement: Optional[str] = None


class TaskBookChangeRequest(BaseModel):
    objective: Optional[str] = None
    content: Optional[str] = None
    progressPlan: Optional[str] = None
    outcomeRequirement: Optional[str] = None
    reason: str = Field(..., min_length=5, description="变更原因，至少 5 字")
