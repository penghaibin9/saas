"""数字迎新域请求 DTO。"""
from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class StudentCreate(BaseModel):
    name: str = Field(..., min_length=1)
    admissionNo: str = Field(..., min_length=1)
    majorName: Optional[str] = None
    classId: Optional[str] = None
    className: Optional[str] = None
    phone: Optional[str] = None
    idCard: Optional[str] = None
    origin: Optional[str] = None
    counselor: Optional[str] = None


class StudentUpdate(BaseModel):
    name: Optional[str] = None
    majorName: Optional[str] = None
    classId: Optional[str] = None
    className: Optional[str] = None
    origin: Optional[str] = None
    counselor: Optional[str] = None
    reportStatus: Optional[str] = None
    phone: Optional[str] = None
    building: Optional[str] = None
    room: Optional[str] = None


class ReasonBody(BaseModel):
    reason: str = Field(..., min_length=1)


class NoteBody(BaseModel):
    note: Optional[str] = Field(default="")


class BlockedBody(BaseModel):
    blockedStep: Optional[str] = None
    blockedReason: Optional[str] = None


class RemarkBody(BaseModel):
    remark: Optional[str] = Field(default="")


class CommentBody(BaseModel):
    comment: Optional[str] = Field(default="")


class DormBody(BaseModel):
    building: Optional[str] = None
    room: Optional[str] = None
    dormStatus: Optional[str] = None
    remark: Optional[str] = None


class IdsBody(BaseModel):
    ids: List[str] = Field(default_factory=list)


class FollowUpBody(BaseModel):
    content: str = Field(..., min_length=1)
    way: Optional[str] = Field(default="PHONE")


class ExceptionCreate(BaseModel):
    studentId: str = Field(..., min_length=1)
    exceptionType: str = Field(..., min_length=1)
    description: str = Field(..., min_length=5)
    riskLevel: Optional[str] = Field(default="MEDIUM")


class BatchCreate(BaseModel):
    batchName: str = Field(..., min_length=1)
    batchNo: str = Field(..., min_length=1)
    year: Optional[str] = None
    startDate: Optional[str] = None
    endDate: Optional[str] = None
    reportStartDate: Optional[str] = None
    reportEndDate: Optional[str] = None
    plannedCount: Optional[int] = 0
    remark: Optional[str] = None


class BatchUpdate(BaseModel):
    batchName: Optional[str] = None
    year: Optional[str] = None
    startDate: Optional[str] = None
    endDate: Optional[str] = None
    reportStartDate: Optional[str] = None
    reportEndDate: Optional[str] = None
    plannedCount: Optional[int] = None
    remark: Optional[str] = None


class VerifyBody(BaseModel):
    passed: bool = True
    reason: Optional[str] = Field(default="")


class PointCreate(BaseModel):
    name: str = Field(..., min_length=1)
    location: Optional[str] = None
    capacity: Optional[int] = 0
    inCharge: Optional[str] = None
    remark: Optional[str] = None


class PointUpdate(BaseModel):
    name: Optional[str] = None
    location: Optional[str] = None
    capacity: Optional[int] = None
    inCharge: Optional[str] = None
    remark: Optional[str] = None


class FlowUpdate(BaseModel):
    enabled: Optional[bool] = None
    required: Optional[bool] = None
    remark: Optional[str] = None


class NoticeCreate(BaseModel):
    title: str = Field(..., min_length=1)
    content: Optional[str] = None
    channel: Optional[str] = "INAPP"
    targetScope: Optional[str] = None


class ArchiveCreate(BaseModel):
    archiveName: str = Field(..., min_length=1)
    batchNo: Optional[str] = None
    scope: Optional[str] = None
    remark: Optional[str] = None
