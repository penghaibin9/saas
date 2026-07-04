"""通用 schema：统一响应包络（用于 OpenAPI 文档展示）。"""
from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class ApiResponse(BaseModel):
    code: str = Field("SUCCESS", description="业务码（冻结契约 §三），非 HTTP 状态码")
    message: str = "success"
    data: Any = None
    traceId: str = Field("req-xxxx", description="请求链路 ID（= 审计表 request_id）")
    timestamp: str = Field("2026-07-04T12:00:00+08:00", description="ISO8601 带时区")


class Pagination(BaseModel):
    items: list = []
    page: int = 1
    pageSize: int = 20
    total: int = 0
    nextCursor: Optional[str] = None
