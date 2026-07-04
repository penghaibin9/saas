"""学生主档 DTO（DTO≠表结构，敏感字段只出脱敏值，冻结册 §18.5）。"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class StudentCreateRequest(BaseModel):
    studentNo: str = Field(..., description="学号（租户内唯一）")
    realName: str = Field(..., description="姓名")
    gender: Optional[str] = Field(None, description="男/女")
    collegeId: Optional[str] = Field(None, description="学院ID")
    majorId: Optional[str] = Field(None, description="专业ID")
    classId: Optional[str] = Field(None, description="班级ID")
    grade: Optional[str] = Field(None, description="年级，如 2024")
    phone: Optional[str] = Field(None, description="手机号（后端将加密存储，响应恒脱敏）")
    idCard: Optional[str] = Field(None, description="身份证号（后端将加密存储，响应恒脱敏）")


class StudentUpdateRequest(BaseModel):
    realName: Optional[str] = None
    gender: Optional[str] = None
    collegeId: Optional[str] = None
    majorId: Optional[str] = None
    classId: Optional[str] = None
    grade: Optional[str] = None
    phone: Optional[str] = Field(None, description="脱敏响应；TODO 接库后走加密列")
    remark: Optional[str] = None


class StudentVoidRequest(BaseModel):
    reason: str = Field(..., min_length=5, description="作废原因（≥5 字，写审计；逻辑删除不物理删除）")
