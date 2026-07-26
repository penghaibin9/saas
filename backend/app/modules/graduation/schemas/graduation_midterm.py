"""毕业设计中心 · 中期检查请求 DTO。"""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field


class MidtermCheckRequest(BaseModel):
    conclusion: str = Field(..., description="PASS/RECTIFY/FAIL")
    comment: Optional[str] = None
    rectifyDeadline: Optional[str] = None


class MidtermRectifySubmit(BaseModel):
    content: str = Field(..., min_length=2, max_length=2000)


class MidtermRectifyReview(BaseModel):
    action: Literal["PASS", "FAIL"]
    comment: Optional[str] = None
