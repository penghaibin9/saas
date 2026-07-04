"""毕业设计域请求 DTO。"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class ReviewBody(BaseModel):
    action: str = Field(..., description="APPROVE / REJECT")
    comment: Optional[str] = Field(default="", description="驳回时必填≥5字")
