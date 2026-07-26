"""学业过程域请求 DTO。"""
from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class ReasonBody(BaseModel):
    reason: str = Field(..., min_length=1)


class StudentCreate(BaseModel):
    # 阶段 D：业务台账不再独立建学生，必须指到已有学籍档案。
    # 优先传 studentId（从学籍选人）；只传 studentNo 时后端按学号唯一匹配主档。
    # name 保留只为兼容旧调用方，后端一律以主档姓名为准，不采信此值。
    studentId: Optional[str] = None
    studentNo: Optional[str] = None
    name: Optional[str] = None
    classId: Optional[str] = None
    className: Optional[str] = None
    counselor: Optional[str] = None
    phone: Optional[str] = None
    obtainedCredits: Optional[float] = None
    requiredCredits: Optional[float] = None


class StudentUpdate(BaseModel):
    name: Optional[str] = None
    classId: Optional[str] = None
    className: Optional[str] = None
    counselor: Optional[str] = None
    obtainedCredits: Optional[float] = None


class GradeCreate(BaseModel):
    studentId: str
    courseName: str = Field(..., min_length=1)
    term: Optional[str] = None
    nature: Optional[str] = "REQUIRED"
    creditValue: Optional[float] = 0
    score: Optional[int] = None
    examType: Optional[str] = "FINAL"


class GradeUpdate(BaseModel):
    score: int
    reason: str = Field(..., min_length=1)


class MakeupCreate(BaseModel):
    studentId: str
    courseName: str = Field(..., min_length=1)
    term: Optional[str] = None
    originScore: Optional[int] = None
    examDate: Optional[str] = None


class StatusBody(BaseModel):
    status: str


class WarningCreate(BaseModel):
    studentId: str
    type: str
    level: Optional[str] = "MEDIUM"
    reason: str = Field(..., min_length=1)
    owner: Optional[str] = None
    deadline: Optional[str] = None
    sourceRule: Optional[str] = None


class LevelBody(BaseModel):
    level: str
    reason: str = Field(..., min_length=1)


class AssignBody(BaseModel):
    ids: List[str] = Field(default_factory=list)
    ownerId: Optional[str] = None
    ownerName: str = Field(..., min_length=1)


class IdsBody(BaseModel):
    ids: List[str] = Field(default_factory=list)


class InterventionBody(BaseModel):
    content: str = Field(..., min_length=1)
    way: Optional[str] = "TALK"
    result: Optional[str] = None
    nextPlan: Optional[str] = None


class ResultBody(BaseModel):
    result: str = Field(..., min_length=1)
