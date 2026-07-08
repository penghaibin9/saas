"""毕业设计中心 · 毕设归档请求 DTO。"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class ArchiveRejectRequest(BaseModel):
    reason: str = Field(..., min_length=5, description="退回原因，至少 5 字")


class ArchiveFileRequest(BaseModel):
    archiveBatchNo: Optional[str] = None
