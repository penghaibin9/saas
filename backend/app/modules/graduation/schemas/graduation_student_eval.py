"""毕业设计中心 · 导师对学生过程评价请求 DTO。"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class StudentEvalCreate(BaseModel):
    period: Optional[str] = None
    score: int = Field(..., ge=0, le=100)
    level: str = Field(..., description="优秀/良好/合格/不合格")
    content: Optional[str] = Field(default=None, max_length=2000)
    note: Optional[str] = Field(default=None, max_length=2000, description="兼容字段，等同 content")
    status: Optional[str] = Field(default="SUBMITTED", description="DRAFT/SUBMITTED")
