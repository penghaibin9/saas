"""毕业设计中心 · 答辩评分请求 DTO。"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class DefenseScoreEntryRequest(BaseModel):
    gdStudentId: str
    judgeName: str = Field(..., min_length=1)
    score: Optional[int] = Field(None, ge=0, le=100)
    comment: Optional[str] = None
    absent: bool = Field(default=False)
    absentReason: Optional[str] = None


class SecondDefenseRequest(BaseModel):
    reason: str = Field(..., min_length=5, description="二次答辩原因，至少 5 字")
