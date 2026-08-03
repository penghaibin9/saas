"""毕业设计域请求 DTO。"""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field


class ReviewBody(BaseModel):
    action: Literal["APPROVE", "REJECT"]
    expectedVersion: int = Field(..., ge=0)
    fileVersionId: int = Field(..., ge=1)
    comment: Optional[str] = Field(default="", description="驳回时必填≥5字")


class RemindBody(BaseModel):
    gdStudentId: str = Field(..., description="毕设学生 t_gd_student.id")
    channel: Optional[str] = Field(default="站内消息", description="催办渠道")


class ProposalSubmitBody(BaseModel):
    """学生端提交/重交开题报告。"""
    background: str = Field(..., description="选题背景")
    plan: str = Field(..., description="研究方案与进度")
    outcome: Optional[str] = Field(default="", description="预期成果")
    attachments: Optional[list] = Field(default=None, description="附件名列表")


class DefenseGroupBody(BaseModel):
    """答辩组新建/编辑：组长(副高+)+秘书+评委≥5(建议)+时间地点。

    优先传 chairMentorId / secretaryMentorId / memberMentorIds（稳定身份）；
    chair / secretary / members 姓名仅作快照或历史兼容。
    """
    groupName: str = Field(..., description="答辩组名称")
    batchId: Optional[int] = Field(default=None, description="毕设批次（新建必填；编辑不可改）")
    defenseDate: Optional[str] = Field(default="", description="答辩时间")
    location: Optional[str] = Field(default="", description="答辩地点")
    chair: Optional[str] = Field(default="", description="答辩组长姓名快照")
    chairMentorId: Optional[int] = Field(default=None, description="答辩组长→t_gd_mentor.id")
    members: Optional[list] = Field(default=None, description="评委名单（字符串或 {mentorId,name}）")
    memberMentorIds: Optional[list] = Field(default=None, description="评委 mentorId 列表（优先）")
    secretary: Optional[str] = Field(default="", description="答辩秘书姓名快照")
    secretaryMentorId: Optional[int] = Field(default=None, description="答辩秘书→t_gd_mentor.id")


class AssignStudentsBody(BaseModel):
    studentIds: list = Field(..., description="毕设学生 t_gd_student.id 列表")
