"""公共 Excel 底座 · Pydantic 契约（V1.1）。

- 复用型请求体：ExcelImportRows / ExcelErrorRows，供接入模块的「预校验 / 确认 / 错误行」端点直接引用，
  统一 rows/errors 结构，避免每个模块各写一套。
- 响应模型：PreValidateResult / ImportJobItem，作为底座对外统一结构文档。
"""
from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class ExcelImportRows(BaseModel):
    """预校验 / 确认导入统一请求体。"""
    rows: list[dict] = Field(default_factory=list, description="行数据（表头映射后的字段 key）")


class ExcelRowError(BaseModel):
    rowNo: int
    field: str = ""
    title: str = ""
    rawValue: Any = ""
    message: str


class ExcelErrorRows(BaseModel):
    """下载错误行 Excel 请求体。"""
    rows: list[dict] = Field(default_factory=list)
    errors: list[ExcelRowError] = Field(default_factory=list)


class PreValidateResult(BaseModel):
    """统一预校验返回结构（文档用；实际接口返回 dict 即可）。"""
    moduleKey: str
    bizType: str
    templateVersion: str = "v1"
    total: int
    validRows: int
    invalidRows: int
    passed: bool
    rows: list[dict] = Field(default_factory=list)
    errors: list[ExcelRowError] = Field(default_factory=list)


class ImportJobItem(BaseModel):
    id: str
    moduleKey: str
    bizType: str
    fileName: str = ""
    templateVersion: str = "v1"
    status: str
    totalRows: int = 0
    validRows: int = 0
    invalidRows: int = 0
    successRows: int = 0
    failedRows: int = 0
    operatorName: str = ""
    startedAt: Optional[str] = None
    finishedAt: Optional[str] = None
    confirmAt: Optional[str] = None
    remark: str = ""
    createdAt: Optional[str] = None
