"""预留能力（文件/导入/导出）的请求体（占位，不落库、不真处理）。"""
from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class ImportValidateRequest(BaseModel):
    bizType: str = Field("student", description="导入业务类型，如 student/teacher")
    fileId: Optional[str] = Field(None, description="已上传文件的 fileId（两步式，见冻结契约 §十）")
    rows: Optional[list[dict[str, Any]]] = Field(None, description="可选：直接校验的行数据样例")


class ExportCreateRequest(BaseModel):
    bizType: str = Field("student", description="导出业务类型")
    fileFormat: str = Field("xlsx", description="xlsx / csv / pdf")
    query: Optional[dict[str, Any]] = Field(None, description="导出筛选条件（占位）")
