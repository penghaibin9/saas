"""毕业设计中心 · 毕设批次请求 DTO（独立文件，与毕业设计域其它 schema 隔离）。"""
from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class BatchCreate(BaseModel):
    batchName: str = Field(..., min_length=1)
    batchNo: str = Field(..., min_length=1, description="批次编号，租户内唯一")
    academicYear: Optional[str] = None
    gradeYear: Optional[str] = Field(None, description="届，如 2026届")
    collegeScope: Optional[str] = None
    startDate: Optional[str] = None
    endDate: Optional[str] = None
    plannedCount: Optional[int] = 0
    stages: Optional[List[dict]] = None
    rules: Optional[dict] = None
    remark: Optional[str] = None


class BatchUpdate(BaseModel):
    batchName: Optional[str] = None
    academicYear: Optional[str] = None
    gradeYear: Optional[str] = None
    collegeScope: Optional[str] = None
    startDate: Optional[str] = None
    endDate: Optional[str] = None
    plannedCount: Optional[int] = None
    stages: Optional[List[dict]] = None
    rules: Optional[dict] = None
    remark: Optional[str] = None


class VoidBatchRequest(BaseModel):
    reason: str = Field(..., min_length=1, description="作废原因（后端强制 ≥5 字）")


class StagesRequest(BaseModel):
    stages: List[dict] = Field(default_factory=list)


class RulesRequest(BaseModel):
    rules: dict = Field(default_factory=dict)
