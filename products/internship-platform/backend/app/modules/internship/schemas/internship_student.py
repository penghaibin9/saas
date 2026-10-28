"""岗位实习中心 · 实习学生请求 DTO（独立文件，与批次/实习域 schema 隔离）。"""
from __future__ import annotations

from typing import Literal, Optional
from datetime import date

from pydantic import BaseModel, Field, model_validator


class StudentRosterQuery(BaseModel):
    """One validated query contract for the roster and its complete export."""
    model_config = {'extra': 'forbid', 'str_strip_whitespace': True}
    page: int = Field(1, ge=1)
    pageSize: int = Field(20, ge=1, le=200)
    batchId: Optional[str] = Field(None, pattern=r'^\d+$')
    allBatches: bool = False
    keyword: Optional[str] = Field(None, max_length=200)
    classId: Optional[str] = Field(None, pattern=r'^\d+$')
    status: Optional[str] = Field(None, max_length=30)
    riskLevel: Optional[str] = Field(None, max_length=30)
    eligibility: Optional[str] = Field(None, max_length=30)
    destination: Optional[str] = Field(None, max_length=30)
    hasPosition: Optional[bool] = None
    hasAdvisor: Optional[bool] = None
    sourceRegion: Optional[str] = Field(None, max_length=100)
    studentName: Optional[str] = Field(None, max_length=100)
    studentNo: Optional[str] = Field(None, max_length=100)
    grade: Optional[str] = Field(None, max_length=20)
    collegeName: Optional[str] = Field(None, max_length=200)
    majorName: Optional[str] = Field(None, max_length=200)
    className: Optional[str] = Field(None, max_length=200)
    planName: Optional[str] = Field(None, max_length=200)
    internshipType: Optional[Literal['POST', 'COGNITIVE', 'FOLLOW_POST', 'APPRENTICESHIP', 'COMPREHENSIVE', 'OTHER']] = None
    internshipMode: Optional[str] = Field(None, max_length=30)
    enterpriseName: Optional[str] = Field(None, max_length=200)
    companyCreditCode: Optional[str] = Field(None, max_length=50)
    positionName: Optional[str] = Field(None, max_length=100)
    salaryMin: Optional[float] = Field(None, ge=0, le=9999999999, allow_inf_nan=False)
    salaryMax: Optional[float] = Field(None, ge=0, le=9999999999, allow_inf_nan=False)
    workLocation: Optional[str] = Field(None, max_length=300)
    headTeacherName: Optional[str] = Field(None, max_length=100)
    advisorName: Optional[str] = Field(None, max_length=100)
    mentorName: Optional[str] = Field(None, max_length=100)
    applicationStatus: Optional[Literal['NONE', 'DRAFT', 'PENDING_REVIEW', 'APPROVED', 'REJECTED', 'WITHDRAWN', 'CANCELLED']] = None
    companyNature: Optional[str] = Field(None, max_length=50)
    companyIndustry: Optional[str] = Field(None, max_length=100)
    majorMatch: Optional[bool] = None
    internshipDepartment: Optional[str] = Field(None, max_length=100)
    positionCategory: Optional[str] = Field(None, max_length=50)
    rotationInfo: Optional[str] = Field(None, max_length=200)
    rotationScoreMin: Optional[float] = Field(None, ge=0, le=100, allow_inf_nan=False)
    rotationScoreMax: Optional[float] = Field(None, ge=0, le=100, allow_inf_nan=False)
    agreementStatus: Optional[Literal['NONE', 'DRAFT', 'PENDING_STUDENT', 'PENDING_ENTERPRISE', 'PENDING_SCHOOL', 'EFFECTIVE', 'REJECTED', 'VOIDED', 'ARCHIVED']] = None

    @model_validator(mode='after')
    def ordered_ranges(self):
        for low, high in [('salaryMin', 'salaryMax'), ('rotationScoreMin', 'rotationScoreMax')]:
            if getattr(self, low) is not None and getattr(self, high) is not None and getattr(self, low) > getattr(self, high):
                raise ValueError('筛选下限不能大于上限')
        return self

    def service_filters(self):
        values = self.model_dump(exclude_none=True, exclude={'page', 'pageSize'})
        names = {'batchId':'batch_id', 'classId':'class_id', 'riskLevel':'risk_level',
                 'hasPosition':'has_position', 'hasAdvisor':'has_advisor', 'sourceRegion':'source_region',
                 'allBatches':'all_batches'}
        direct = {'keyword', 'status', 'eligibility', 'destination', *names}
        return {**{names.get(k, k):v for k,v in values.items() if k in direct},
                'roster_filters':{k:v for k,v in values.items() if k not in direct}}


class StudentRecordCreate(BaseModel):
    studentId: str = Field(..., description="t_student_profile.id")
    batchId: str = Field(..., description="实习批次 id（必填，禁止 NULL）")
    advisorName: Optional[str] = None
    advisorUserId: Optional[str] = None
    remark: Optional[str] = None


class StudentRecordUpdate(BaseModel):
    expectedVersion: int = Field(..., ge=0, description="实习记录乐观锁版本")
    advisorName: Optional[str] = None
    advisorUserId: Optional[str] = None
    insurance: Optional[str] = None
    agreement: Optional[str] = None
    remark: Optional[str] = None
    internStartDate: Optional[date] = None
    internEndDate: Optional[date] = None
    periodReason: Optional[str] = Field(None, max_length=500)


class AssignPositionRequest(BaseModel):
    positionId: str = Field(..., description="岗位库 t_internship_position.id（须已上架、企业非黑名单、未满员）")
    expectedVersion: int = Field(..., ge=0, description="实习学生记录乐观锁版本")


class UnassignRequest(BaseModel):
    reason: Optional[str] = ""
    expectedVersion: int = Field(..., ge=0, description="实习学生记录乐观锁版本")


class StudentStatusRequest(BaseModel):
    expectedVersion: int = Field(..., ge=0, description="实习记录乐观锁版本")
    action: str = Field(..., pattern="^(READY|ONBOARD|ASSESS)$",
                        description="READY / ONBOARD / ASSESS；归档只能走正式归档接口")
    reason: Optional[str] = ""


class EligibilityRequest(BaseModel):
    expectedVersion: int = Field(..., ge=0, description="实习记录乐观锁版本")
    status: str = Field(..., description="QUALIFIED / UNQUALIFIED / PENDING")
    reason: Optional[str] = ""
    publishReason: bool = Field(False, description="本次认定说明是否向该学生本人公开")


class DestinationRequest(BaseModel):
    expectedVersion: int = Field(..., ge=0, description="实习记录乐观锁版本")
    destination: str = Field(..., description="SELF_ARRANGED / EXEMPTED / NONE")
    reason: Optional[str] = ""


class StudentImport(BaseModel):
    batchId: str = Field(..., description="当前页面批次上下文（必填）")
    rows: list[dict] = Field(default_factory=list)


class AdvisorAssignmentRequest(BaseModel):
    advisorUserId: str = Field(..., description="Active teacher user id")
    expectedVersion: int = Field(..., ge=0, description="实习记录乐观锁版本")
    reason: Optional[str] = ""
