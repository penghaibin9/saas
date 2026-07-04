"""在校服务域请求 DTO。"""
from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class ReasonBody(BaseModel):
    reason: str = Field(..., min_length=1)


class NoteBody(BaseModel):
    note: Optional[str] = Field(default="")


class CommentBody(BaseModel):
    comment: Optional[str] = Field(default="")


class IdsBody(BaseModel):
    ids: List[str] = Field(default_factory=list)


class StudentCreate(BaseModel):
    name: str = Field(..., min_length=1)
    studentNo: str = Field(..., min_length=1)
    classId: Optional[str] = None
    className: Optional[str] = None
    careLevel: Optional[str] = None
    building: Optional[str] = None
    room: Optional[str] = None
    counselor: Optional[str] = None
    phone: Optional[str] = None


class StudentUpdate(BaseModel):
    careLevel: Optional[str] = None
    building: Optional[str] = None
    room: Optional[str] = None
    counselor: Optional[str] = None
    className: Optional[str] = None


class DormExcMark(BaseModel):
    studentId: str
    type: Optional[str] = "NIGHT_OUT"
    detail: str = Field(..., min_length=1)


class DormExcHandle(BaseModel):
    note: str = Field(..., min_length=1)
    complete: bool = False


class DisciplineCreate(BaseModel):
    studentId: str
    type: str
    reason: str = Field(..., min_length=1)
    docNo: Optional[str] = None


class DisciplineUpdate(BaseModel):
    type: Optional[str] = None
    reason: Optional[str] = None
    status: Optional[str] = None
    revokeReason: Optional[str] = None


class WorkOrderCreate(BaseModel):
    studentId: str
    title: str = Field(..., min_length=1)
    type: str
    priority: Optional[str] = "MEDIUM"
    detail: Optional[str] = None


class AssignBody(BaseModel):
    ids: List[str] = Field(default_factory=list)
    handlerId: Optional[str] = None
    handler: Optional[str] = None


class HandleBody(BaseModel):
    note: str = Field(..., min_length=1)
    close: bool = False
