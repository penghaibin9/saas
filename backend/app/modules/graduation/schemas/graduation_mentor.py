"""毕业设计中心 · 导师管理 / 导师分配请求 DTO。"""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


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
    action: Literal["APPROVE", "REJECT"]
    comment: Optional[str] = None


class MentorDisableRequest(BaseModel):
    reason: str = Field(..., min_length=5, description="停用原因，至少 5 字")


class MentorAssignRequest(BaseModel):
    """导师分配只接受校内导师或外聘导师的稳定主体 ID。"""

    model_config = ConfigDict(extra="forbid")

    gdStudentId: str
    mentorId: Optional[str] = None
    externalAdvisorId: Optional[str] = None
    reason: Optional[str] = None

    @model_validator(mode="after")
    def validate_stable_subject(self):
        mentor_id = str(self.mentorId or "").strip()
        external_id = str(self.externalAdvisorId or "").strip()
        if bool(mentor_id) == bool(external_id):
            raise ValueError("mentorId 与 externalAdvisorId 必须且只能提供一个")
        self.mentorId = mentor_id or external_id
        self.externalAdvisorId = external_id or None
        return self


class MentorChangeRequest(BaseModel):
    """调导师同样只认稳定主体 ID；姓名只作为展示快照。"""

    model_config = ConfigDict(extra="forbid")

    gdStudentId: str
    newMentorId: Optional[str] = None
    mentorId: Optional[str] = None
    externalAdvisorId: Optional[str] = None
    reason: str = Field(..., min_length=5, description="调导师原因，至少 5 字")

    @model_validator(mode="after")
    def validate_stable_subject(self):
        values = [
            str(self.newMentorId or "").strip(),
            str(self.mentorId or "").strip(),
            str(self.externalAdvisorId or "").strip(),
        ]
        supplied = [value for value in values if value]
        if len(supplied) != 1:
            raise ValueError("newMentorId、mentorId、externalAdvisorId 必须且只能提供一个")
        self.newMentorId = supplied[0]
        self.mentorId = str(self.mentorId or "").strip() or None
        self.externalAdvisorId = str(self.externalAdvisorId or "").strip() or None
        return self


class MentorAssignCancelRequest(BaseModel):
    reason: str = Field(..., min_length=5, description="取消原因，至少 5 字")