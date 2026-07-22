"""岗位实习域请求 DTO。"""
from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field, model_validator


# ═══════════ 实习批次 ═══════════

class StageItem(BaseModel):
    code: str = Field(..., min_length=1, description="阶段代码，如 PREP/ONBOARD/REVIEW")
    name: str = Field(..., min_length=1, description="阶段名称，如 岗前准备")
    startDate: Optional[str] = None
    endDate: Optional[str] = None


class CheckinRule(BaseModel):
    requireDaily: bool = True
    geofenceRadiusM: int = Field(500, ge=0, le=5000, description="电子围栏半径（米）")
    allowedExceptionTypes: List[str] = Field(
        default_factory=lambda: ["OUT_OF_RANGE", "MOCK_LOCATION", "MISSING"])


class WeeklyReportRuleCfg(BaseModel):
    frequency: str = Field("WEEKLY", description="WEEKLY/BIWEEKLY")
    minWordCount: int = Field(800, ge=0, le=5000)
    deadlineWeekday: int = Field(7, ge=1, le=7, description="每周几前必须提交，1=周一...7=周日")


class GuidanceRuleCfg(BaseModel):
    minVisitsPerTerm: int = Field(2, ge=0, le=52, description="每学期最少现场巡访次数")
    minCommunicationsPerMonth: int = Field(2, ge=0, le=31, description="每月最少沟通次数")


class EvaluationRuleCfg(BaseModel):
    enterpriseWeight: float = Field(0.4, ge=0, le=1)
    teacherWeight: float = Field(0.4, ge=0, le=1)
    selfWeight: float = Field(0.2, ge=0, le=1)

    @model_validator(mode="after")
    def _weights_sum_to_one(self):
        total = float(self.enterpriseWeight) + float(self.teacherWeight) + float(self.selfWeight)
        if abs(total - 1.0) > 1e-6:
            raise ValueError(f"评价权重之和须为 1.0，当前为 {total:.4f}")
        return self


class ScoreComponent(BaseModel):
    name: str = Field(..., min_length=1)
    weight: float = Field(..., ge=0, le=1)


class ScoreRuleCfg(BaseModel):
    passThreshold: float = Field(60.0, ge=0, le=100)
    components: List[ScoreComponent] = Field(default_factory=lambda: [
        ScoreComponent(name="企业评价", weight=0.4), ScoreComponent(name="教师评价", weight=0.4),
        ScoreComponent(name="考核成绩", weight=0.2)])

    @model_validator(mode="after")
    def _components_sum_to_one(self):
        comps = self.components or []
        if not comps:
            return self
        total = sum(float(c.weight) for c in comps)
        if abs(total - 1.0) > 1e-6:
            raise ValueError(f"成绩规则分项权重之和须为 1.0，当前为 {total:.4f}")
        return self


class OnboardRuleCfg(BaseModel):
    """上岗前置（BUG-010）：学校可按批次关闭其中某项，默认全部要求。"""
    requireAgreement: bool = Field(True, description="须三方协议生效")
    requireInsurance: bool = Field(True, description="须实习保险核验通过")
    requireAdvisor: bool = Field(True, description="须分配校内指导教师")


class RulesConfig(BaseModel):
    checkin: CheckinRule = Field(default_factory=CheckinRule)
    weeklyReport: WeeklyReportRuleCfg = Field(default_factory=WeeklyReportRuleCfg)
    guidance: GuidanceRuleCfg = Field(default_factory=GuidanceRuleCfg)
    evaluation: EvaluationRuleCfg = Field(default_factory=EvaluationRuleCfg)
    score: ScoreRuleCfg = Field(default_factory=ScoreRuleCfg)
    onboard: OnboardRuleCfg = Field(default_factory=OnboardRuleCfg)


class BatchCreate(BaseModel):
    batchName: str = Field(..., min_length=1)
    batchNo: str = Field(..., min_length=1)
    academicYear: Optional[str] = None
    term: Optional[str] = None
    startDate: Optional[str] = None
    endDate: Optional[str] = None
    signupStartDate: Optional[str] = None
    signupEndDate: Optional[str] = None
    plannedCount: Optional[int] = 0
    remark: Optional[str] = None
    stages: Optional[List[StageItem]] = None
    # 注意：rules 用宽松 dict 而非严格 RulesConfig ——
    # 允许只提交需要覆盖的分组/字段，未提交部分在 service 层与默认值/已存值做深度合并，
    # 避免"只改打卡规则却把周报/指导/评价规则冲回默认值"。
    rules: Optional[dict] = None


class BatchUpdate(BaseModel):
    batchName: Optional[str] = None
    academicYear: Optional[str] = None
    term: Optional[str] = None
    startDate: Optional[str] = None
    endDate: Optional[str] = None
    signupStartDate: Optional[str] = None
    signupEndDate: Optional[str] = None
    plannedCount: Optional[int] = None
    remark: Optional[str] = None
    stages: Optional[List[StageItem]] = None
    rules: Optional[dict] = None


class VoidBatchRequest(BaseModel):
    reason: str = Field(..., min_length=1, description="作废原因（后端强制 ≥5 字）")


class ExceptionHandleRequest(BaseModel):
    action: str = Field(..., description="REASONABLE / ABNORMAL / TO_RISK")
    comment: str = Field(..., min_length=1, description="处理意见（后端强制 ≥5 字）")


class ReportReviewRequest(BaseModel):
    action: str = Field(..., description="APPROVE / RETURN")
    comment: Optional[str] = Field(None, description="退回时必填 ≥5 字")


# ═══════════ 企业库 ═══════════

class EnterpriseCreate(BaseModel):
    name: str = Field(..., min_length=1, description="企业名称")
    creditCode: Optional[str] = Field(None, description="统一社会信用代码（租户内唯一）")
    industry: Optional[str] = None
    nature: Optional[str] = Field(None, description="企业性质")
    scale: Optional[str] = None
    region: Optional[str] = Field(None, description="省市/地区")
    city: Optional[str] = None
    address: Optional[str] = None
    source: Optional[str] = Field(None, description="SELF_BUILT/SCHOOL_ENTERPRISE/STUDENT_SELF/RECOMMENDED")
    cooperationLevel: Optional[str] = None
    contactPerson: Optional[str] = None
    contactPhone: Optional[str] = None
    remark: Optional[str] = None


class EnterpriseUpdate(BaseModel):
    name: Optional[str] = None
    creditCode: Optional[str] = None
    industry: Optional[str] = None
    nature: Optional[str] = None
    scale: Optional[str] = None
    region: Optional[str] = None
    city: Optional[str] = None
    address: Optional[str] = None
    source: Optional[str] = None
    cooperationLevel: Optional[str] = None
    contactPerson: Optional[str] = None
    contactPhone: Optional[str] = None
    remark: Optional[str] = None


class EnterpriseReview(BaseModel):
    action: str = Field(..., description="APPROVE / REJECT")
    comment: Optional[str] = ""


class CoopActionRequest(BaseModel):
    action: str = Field(..., description="SUSPEND / RESUME / ARCHIVE")
    reason: Optional[str] = ""


class BlacklistRequest(BaseModel):
    on: bool = Field(..., description="true 拉黑 / false 移出黑名单")
    reason: Optional[str] = ""


class ContactCreate(BaseModel):
    contactType: str = Field("CONTACT", description="CONTACT 联系人 / MENTOR 企业导师")
    name: str = Field(..., min_length=1)
    title: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    isPrimary: bool = False
    remark: Optional[str] = None


class ContactUpdate(BaseModel):
    contactType: Optional[str] = None
    name: Optional[str] = None
    title: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    isPrimary: Optional[bool] = None
    remark: Optional[str] = None


class EnterpriseImport(BaseModel):
    rows: list[dict] = Field(default_factory=list)


class ImportErrorsExport(BaseModel):
    rows: list[dict] = Field(default_factory=list)
    errors: list[dict] = Field(default_factory=list)

