"""毕业设计中心 · 成绩评定请求 DTO。"""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field


class GradeCalculateRequest(BaseModel):
    advisorScore: Optional[int] = Field(None, ge=0, le=100)
    reviewerScore: Optional[int] = Field(None, ge=0, le=100)
    defenseScore: Optional[int] = Field(None, ge=0, le=100)


class GradeReviewRequest(BaseModel):
    action: Literal["APPROVE", "RETURN"]
    comment: Optional[str] = None


class GradeWithdrawRequest(BaseModel):
    reason: str = Field(..., min_length=5, description="撤回原因，至少 5 字")
