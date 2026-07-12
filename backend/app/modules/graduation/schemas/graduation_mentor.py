"""毕业设计中心 · 导师管理 / 导师分配请求 DTO（独立文件，与毕业设计域其它 schema 隔离）。"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class MentorCreate(BaseModel):
    teacherNo: str = Field(..., min_length=1, max_length=50)
    teacherName: str = Field(..., min_length=1, max_length=100)
    mentorType: str = Field(default="INTERNAL", description="INTERNAL/ENTERPRISE/DUAL")
    title: Optional[str] = None
    collegeName: Optional[str] = None
    majorName: Optional[str] = None
    researchDirection: Optional[str] = None
    maxCapacity: int = Field(default=8, ge=1, le=99)
    phone: Optional[str] = None
    remark: Optional[str] = None
    submitReview: bool = Field(default=False, description="创建后是否直接提交资格审核")


class MentorUpdate(BaseModel):
    teacherName: Optional[str] = None
    mentorType: Optional[str] = None
    title: Optional[str] = None
    collegeName: Optional[str] = None
    majorName: Optional[str] = None
    researchDirection: Optional[str] = None
    maxCapacity: Optional[int] = Field(None, ge=1, le=99)
    phone: Optional[str] = None
    remark: Optional[str] = None


class MentorReviewRequest(BaseModel):
    action: str = Field(..., description="APPROVE/REJECT")
    comment: Optional[str] = None


class MentorDisableRequest(BaseModel):
    reason: str = Field(..., min_length=5, description="停用原因，至少 5 字")


class MentorAssignRequest(BaseModel):
    gdStudentId: str
    mentorId: str
    reason: Optional[str] = None


class MentorChangeRequest(BaseModel):
    gdStudentId: str
    newMentorId: str
    reason: str = Field(..., min_length=5, description="调导师原因，至少 5 字")


class MentorAssignCancelRequest(BaseModel):
    reason: str = Field(..., min_length=5, description="取消原因，至少 5 字")
