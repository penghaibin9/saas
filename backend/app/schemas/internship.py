"""岗位实习域请求 DTO。"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class ExceptionHandleRequest(BaseModel):
    action: str = Field(..., description="REASONABLE / ABNORMAL / TO_RISK")
    comment: str = Field(..., min_length=1, description="处理意见（后端强制 ≥5 字）")


class ReportReviewRequest(BaseModel):
    action: str = Field(..., description="APPROVE / RETURN")
    comment: Optional[str] = Field(None, description="退回时必填 ≥5 字")
