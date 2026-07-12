"""岗位实习中心 · 实习学生请求 DTO（独立文件，与批次/实习域 schema 隔离）。"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class StudentRecordCreate(BaseModel):
    studentId: str = Field(..., description="t_student_profile.id")
    batchId: Optional[str] = Field(None, description="预留·实习批次 id")
    advisorName: Optional[str] = None
    remark: Optional[str] = None


class StudentRecordUpdate(BaseModel):
    advisorName: Optional[str] = None
    insurance: Optional[str] = None
    agreement: Optional[str] = None
    remark: Optional[str] = None


class AssignPositionRequest(BaseModel):
    positionId: str = Field(..., description="岗位库 t_internship_position.id（须已上架、企业非黑名单、未满员）")


class UnassignRequest(BaseModel):
    reason: Optional[str] = ""


class StudentStatusRequest(BaseModel):
    action: str = Field(..., description="READY / ONBOARD / ASSESS / ARCHIVE")
    reason: Optional[str] = ""


class EligibilityRequest(BaseModel):
    status: str = Field(..., description="QUALIFIED / UNQUALIFIED / PENDING")
    reason: Optional[str] = ""


class DestinationRequest(BaseModel):
    destination: str = Field(..., description="SELF_ARRANGED / EXEMPTED / NONE")
    reason: Optional[str] = ""


class StudentImport(BaseModel):
    rows: list[dict] = Field(default_factory=list)
