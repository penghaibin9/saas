"""学业过程域请求 DTO。"""
from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class ReasonBody(BaseModel):
    reason: str = Field(..., min_length=1)


class StudentCreate(BaseModel):
    name: str = Field(..., min_length=1)
    studentNo: str = Field(..., min_length=1)
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
