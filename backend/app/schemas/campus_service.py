"""在校服务域请求 DTO。"""
from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class ReasonBody(BaseModel):
    reason: str = Field(..., min_length=1)
    version: int = Field(..., description="乐观锁版本，必填")


class NoteBody(BaseModel):
    note: Optional[str] = Field(default="")
    version: int = Field(..., description="乐观锁版本，必填")


class CommentBody(BaseModel):
    comment: Optional[str] = Field(default="")
    version: int = Field(..., description="乐观锁版本，必填")


class VersionedIdItem(BaseModel):
    id: str
    version: int = Field(..., description="乐观锁版本，必填")


class IdsBody(BaseModel):
    """兼容旧调用：仅 ids。新批量写路径请用 VersionedIdsBody。"""
    ids: List[str] = Field(default_factory=list)


class VersionedIdsBody(BaseModel):
    items: List[VersionedIdItem] = Field(default_factory=list)


class StudentCreate(BaseModel):
    # 阶段 D：业务台账不再独立建学生，必须指到已有学籍档案。
    # 优先传 studentId（从学籍选人）；只传 studentNo 时后端按学号唯一匹配主档。
    # name 保留只为兼容旧调用方，后端一律以主档姓名为准，不采信此值。
    studentId: Optional[str] = None
    studentNo: Optional[str] = None
    name: Optional[str] = None
    classId: Optional[str] = None
    className: Optional[str] = None
    careLevel: Optional[str] = None
    building: Optional[str] = None
    room: Optional[str] = None
    counselor: Optional[str] = None
    phone: Optional[str] = None


class StudentUpdate(BaseModel):
    careLevel: Optional[str] = None
    building: Optional[str] = None
    room: Optional[str] = None
    counselor: Optional[str] = None
    className: Optional[str] = None


class DormExcMark(BaseModel):
    studentId: str
    type: Optional[str] = "NIGHT_OUT"
    detail: str = Field(..., min_length=1)


class DormExcHandle(BaseModel):
    note: str = Field(..., min_length=1)
    complete: bool = False
    version: int = Field(..., description="乐观锁版本，必填")


class DisciplineCreate(BaseModel):
    studentId: str
    type: str
    reason: str = Field(..., min_length=1)
    docNo: Optional[str] = None


class DisciplineUpdate(BaseModel):
    type: Optional[str] = None
    reason: Optional[str] = None
    status: Optional[str] = None
    revokeReason: Optional[str] = None


class WorkOrderCreate(BaseModel):
    studentId: str
    title: str = Field(..., min_length=1)
    type: str
    priority: Optional[str] = "MEDIUM"
    detail: Optional[str] = None


class AssignBody(BaseModel):
    ids: List[str] = Field(default_factory=list)
    handlerId: Optional[str] = None
    handler: Optional[str] = None


class HandleBody(BaseModel):
    note: str = Field(..., min_length=1)
    close: bool = False
    version: int = Field(..., description="乐观锁版本，必填")
