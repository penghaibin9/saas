"""毕业设计中心 · 选题变更申请 DTO。"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class GdTopicChangeRequestCreate(BaseModel):
    gdStudentId: str
    newTopicId: str
    reason: str = Field(..., min_length=5, max_length=500)


class GdTopicChangeReview(BaseModel):
    action: str = Field(..., description="APPROVE / REJECT")
    comment: Optional[str] = None
