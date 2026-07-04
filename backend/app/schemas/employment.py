"""就业服务域请求 DTO。"""
from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class ReasonBody(BaseModel):
    reason: str = Field(..., min_length=1)


class CommentBody(BaseModel):
    comment: Optional[str] = Field(default="")


class StudentCreate(BaseModel):
    name: str = Field(..., min_length=1)
    studentNo: str = Field(..., min_length=1)
    classId: Optional[str] = None
    className: Optional[str] = None
    phone: Optional[str] = None
    destinationType: Optional[str] = None
    companyName: Optional[str] = None
    signDate: Optional[str] = None
    counselor: Optional[str] = None


class StudentUpdate(BaseModel):
    destinationType: Optional[str] = None
    companyName: Optional[str] = None
    jobTitle: Optional[str] = None
    salaryRange: Optional[str] = None
    signDate: Optional[str] = None
    employmentTeacher: Optional[str] = None


class MarkDestBody(BaseModel):
    ids: List[str] = Field(default_factory=list)
    destinationType: str


class IdsBody(BaseModel):
    ids: List[str] = Field(default_factory=list)


class AssignTeacherBody(BaseModel):
    ids: List[str] = Field(default_factory=list)
    teacher: str = Field(..., min_length=1)


class FollowUpCreate(BaseModel):
    studentId: str
    content: str = Field(..., min_length=1)
    way: Optional[str] = "PHONE"
    result: Optional[str] = None
    nextPlan: Optional[str] = None


class CompanyCreate(BaseModel):
    name: str = Field(..., min_length=1)
    creditCode: str = Field(..., min_length=1)
    industry: Optional[str] = None
    nature: Optional[str] = None
    city: Optional[str] = None
    contactPerson: Optional[str] = None
    contactPhone: Optional[str] = None
    cooperationLevel: Optional[str] = None


class JobCreate(BaseModel):
    companyId: str
    title: str = Field(..., min_length=1)
    category: Optional[str] = None
    salaryRange: Optional[str] = None
    headcount: Optional[int] = 1
    publishTime: Optional[str] = None
