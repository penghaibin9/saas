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
