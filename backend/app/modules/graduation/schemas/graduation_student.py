"""毕业设计中心 · 毕设学生请求 DTO（独立文件，与批次/毕设域其它 schema 隔离）。"""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field


class GdStudentCreate(BaseModel):
    studentId: str = Field(..., description="t_student_profile.id")
    batchId: Optional[str] = Field(None, description="毕设批次 t_gd_batch.id")
    advisorName: Optional[str] = None
    remark: Optional[str] = None


class GdStudentUpdate(BaseModel):
    advisorName: Optional[str] = None
    remark: Optional[str] = None


class AssignTopicRequest(BaseModel):
    topicId: str = Field(..., description="选题库 t_gd_topic.id（须已确认、未满员）")


class UnassignTopicRequest(BaseModel):
    reason: Optional[str] = ""


class AssignAdvisorRequest(BaseModel):
    advisorName: str = Field(..., min_length=1, description="指导教师姓名")


class GdStudentStageRequest(BaseModel):
    action: Literal["ADVANCE", "ARCHIVE"]
    reason: Optional[str] = ""


class GdStudentRiskRequest(BaseModel):
    riskLevel: str = Field(..., description="NONE / LOW / MEDIUM / HIGH")
    reason: Optional[str] = ""


class GdStudentImport(BaseModel):
    rows: list[dict] = Field(default_factory=list)


class GdStudentEligibilityRequest(BaseModel):
    status: str = Field(..., description="PENDING / QUALIFIED / UNQUALIFIED")
    reason: Optional[str] = ""


class GdStudentGroupRequest(BaseModel):
    groupName: str = Field(..., min_length=1, max_length=100)
    reason: Optional[str] = ""


class GdStudentBatchGroupRequest(BaseModel):
    recordIds: list[str] = Field(..., min_length=1)
    groupName: str = Field(..., min_length=1, max_length=100)
    reason: Optional[str] = ""


class GdStudentDefenseGroupRequest(BaseModel):
    defenseGroupId: str = Field(..., description="t_gd_defense_group.id")
    reason: Optional[str] = ""


class GdStudentGradQualRequest(BaseModel):
    status: str = Field(..., description="UNKNOWN/NONE/PENDING/PASS/FAIL")
    note: Optional[str] = ""
    reason: Optional[str] = ""


class GdStudentBatchArchiveRequest(BaseModel):
    recordIds: list[str] = Field(..., min_length=1)
    reason: Optional[str] = ""
