"""岗位实习中心 · 岗位库请求 DTO（独立文件，与批次/实习域 schema 隔离）。"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class PositionCreate(BaseModel):
    companyId: str = Field(..., description="所属企业 t_emp_company.id（岗位必须关联企业）")
    batchId: Optional[str] = Field(None, description="预留·实习批次 id（可空，待批次模块联调）")
    title: str = Field(..., min_length=1, description="岗位名称")
    category: Optional[str] = None
    majorRequirement: Optional[str] = Field(None, description="专业要求")
    gradeRequirement: Optional[str] = Field(None, description="年级要求")
    workLocation: Optional[str] = None
    geofenceLat: Optional[float] = Field(None, ge=-90, le=90)
    geofenceLng: Optional[float] = Field(None, ge=-180, le=180)
    geofenceRadiusM: Optional[int] = Field(None, ge=30, le=5000)
    salaryRange: Optional[str] = None
    subsidy: Optional[str] = None
    headcount: int = Field(1, ge=1, le=9999, description="岗位容量")
    mentorContactId: Optional[str] = Field(None, description="企业导师 t_internship_enterprise_contact.id")
    remark: Optional[str] = None


class PositionUpdate(BaseModel):
    title: Optional[str] = None
    category: Optional[str] = None
    majorRequirement: Optional[str] = None
    gradeRequirement: Optional[str] = None
    workLocation: Optional[str] = None
    geofenceLat: Optional[float] = Field(None, ge=-90, le=90)
    geofenceLng: Optional[float] = Field(None, ge=-180, le=180)
    geofenceRadiusM: Optional[int] = Field(None, ge=30, le=5000)
    salaryRange: Optional[str] = None
    subsidy: Optional[str] = None
    headcount: Optional[int] = Field(None, ge=1, le=9999)
    mentorContactId: Optional[str] = None
    batchId: Optional[str] = None
    remark: Optional[str] = None


class PositionStatusAction(BaseModel):
    action: str = Field(..., description="SUBMIT/PUBLISH/OFFLINE/SUSPEND/ARCHIVE")
    reason: Optional[str] = ""


class PositionRiskRequest(BaseModel):
    on: bool = Field(..., description="true 标记风险岗位 / false 解除")
    note: Optional[str] = ""


class PositionImport(BaseModel):
    rows: list[dict] = Field(default_factory=list)


class PositionImportErrors(BaseModel):
    rows: list[dict] = Field(default_factory=list)
    errors: list[dict] = Field(default_factory=list)
