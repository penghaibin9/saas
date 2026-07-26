"""就业服务域请求 DTO。"""
from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class ReasonBody(BaseModel):
    reason: str = Field(..., min_length=1)


class CommentBody(BaseModel):
    comment: Optional[str] = Field(default="")


class StudentCreate(BaseModel):
    # 阶段 D：业务台账不再独立建学生，必须指到已有学籍档案。
    # 优先传 studentId（从学籍选人）；只传 studentNo 时后端按学号唯一匹配主档。
    # name 保留只为兼容旧调用方，后端一律以主档姓名为准，不采信此值。
    studentId: Optional[str] = None
    studentNo: Optional[str] = None
    name: Optional[str] = None
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
