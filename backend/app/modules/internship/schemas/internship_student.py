"""岗位实习中心 · 实习学生请求 DTO（独立文件，与批次/实习域 schema 隔离）。"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class StudentRecordCreate(BaseModel):
    studentId: str = Field(..., description="t_student_profile.id")
    batchId: str = Field(..., description="实习批次 id（必填，禁止 NULL）")
    advisorName: Optional[str] = None
    advisorUserId: Optional[str] = None
    remark: Optional[str] = None


class StudentRecordUpdate(BaseModel):
    advisorName: Optional[str] = None
    advisorUserId: Optional[str] = None
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
    batchId: str = Field(..., description="当前页面批次上下文（必填）")
    rows: list[dict] = Field(default_factory=list)


class AdvisorAssignmentRequest(BaseModel):
    advisorUserId: str = Field(..., description="Active teacher user id")
    reason: Optional[str] = ""
