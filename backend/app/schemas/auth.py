"""认证相关请求体（mock 阶段）。字段命名对齐 docs/api/01。"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class MockLoginRequest(BaseModel):
    tenantCode: str = Field("demo", description="学校(租户)编码，定位学校")
    loginName: str = Field("20230101", description="登录名/学号/工号")
    # mock 阶段不校验密码；真实接库后走口令哈希校验
    password: Optional[str] = Field(None, description="mock 阶段可不传")
    userType: str = Field("TEACHER", description="STUDENT / TEACHER / ADMIN / PLATFORM")
    clientType: str = Field("PC", description="PC / STUDENT_MINI / TEACHER_MINI")


class SwitchRoleRequest(BaseModel):
    contextId: str = Field(..., description="要切换到的身份 contextId（见 /auth/me contexts）")
    clientType: str = Field("PC", description="PC / STUDENT_MINI / TEACHER_MINI")
