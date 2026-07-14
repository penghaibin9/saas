"""13A-P3 困难认定 + 奖助模型（草案 §3.3/§3.4；P0 已冻结表名与字段）。

困难认定 4 表：批次 / 申请单(12态) / 家庭经济(强敏感隔离表) / 等级变动史(困难库数据源,append-only)。
奖助 3 表：项目定义(七类) / 学年批次 / 资助申请单(唯一键防同批次重复)。
敏感：家庭经济 *_encrypted 密文列，列表接口永不返回，查看完整必审计（见 service）。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import (BigInteger, DateTime, Integer, Numeric, String,
                        UniqueConstraint)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import AuditTimeMixin, Base, CommonMixin, PKMixin, TenantMixin

# ═══════════ 困难认定组（13A-06）═══════════


class AidBatch(PKMixin, TenantMixin, CommonMixin, Base):
    """困难认定批次（学年/时间窗/公示天数/等级配置）。状态 DRAFT/OPEN/REVIEWING/PUBLICITY/CLOSED/ARCHIVED。"""
    __tablename__ = "t_affairs_aid_batch"

    batch_name: Mapped[str] = mapped_column(String(200), nullable=False)
    year_code: Mapped[str] = mapped_column(String(50), nullable=False, index=True, comment="学年编码")
    apply_start: Mapped[datetime | None] = mapped_column(DateTime)
    apply_end: Mapped[datetime | None] = mapped_column(DateTime)
    publicity_days: Mapped[int | None] = mapped_column(Integer, default=5, comment="公示天数,规则中心 affairs.aid.publicity_days")
    level_config_json: Mapped[str | None] = mapped_column(String(2000), comment="等级配置 JSON(SPECIAL/DIFFICULT/GENERAL)")
    scope_json: Mapped[str | None] = mapped_column(String(2000), comment="适用范围 JSON")
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="DRAFT", index=True)


class AidApply(PKMixin, TenantMixin, CommonMixin, Base):
    """困难认定申请单（12 态）。真相列 status；workflow 建流；APPROVED 写 level_history 进困难库。"""
    __tablename__ = "t_affairs_aid_apply"

    batch_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    student_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    apply_level: Mapped[str | None] = mapped_column(String(50), comment="申请等级 SPECIAL/DIFFICULT/GENERAL")
    suggest_level: Mapped[str | None] = mapped_column(String(50), comment="辅导员建议等级")
    final_level: Mapped[str | None] = mapped_column(String(50), comment="核定等级")
    statement: Mapped[str | None] = mapped_column(String(1000), comment="困难情况说明(强敏感,10-500字)")
    class_review_score: Mapped[float | None] = mapped_column(Numeric(6, 2), comment="班级评议得分")
    class_review_rank: Mapped[int | None] = mapped_column(Integer, comment="班级评议排名")
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="DRAFT", index=True)
    workflow_instance_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    publicity_at: Mapped[datetime | None] = mapped_column(DateTime, comment="进入公示时刻(定时到期依据)")
    result_at: Mapped[datetime | None] = mapped_column(DateTime)
    return_reason: Mapped[str | None] = mapped_column(String(500))

    __table_args__ = (UniqueConstraint("tenant_id", "batch_id", "student_id",
                                       name="uk_aid_apply_batch_student"),)


class AidObjection(PKMixin, TenantMixin, CommonMixin, Base):
    """困难认定异议（C 包·公示与异议）。公示期内对某申请提异议→复核 成立(驳回申请)/不成立(维持)。
    status SUBMITTED/CLOSED；result SUSTAINED异议成立/OVERRULED异议不成立。"""
    __tablename__ = "t_affairs_aid_objection"

    apply_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    student_id: Mapped[int | None] = mapped_column(BigInteger, index=True, comment="被异议申请的学生")
    objector_name: Mapped[str | None] = mapped_column(String(100), comment="异议人(可实名/匿名)")
    reason: Mapped[str | None] = mapped_column(String(1000))
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="SUBMITTED", index=True)
    result: Mapped[str | None] = mapped_column(String(30), comment="SUSTAINED/OVERRULED")
    review_opinion: Mapped[str | None] = mapped_column(String(1000))
    reviewer: Mapped[str | None] = mapped_column(String(100))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime)


class AidFamilyEconomy(PKMixin, TenantMixin, CommonMixin, Base):
    """家庭经济信息（强敏感隔离表，1:1 回链 apply_id）。列表接口永不返回；查看完整值必写审计。"""
    __tablename__ = "t_affairs_aid_family_economy"

    apply_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    student_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    member_count: Mapped[int | None] = mapped_column(Integer, comment="家庭人口数(可脱敏展示)")
    family_members_json: Mapped[str | None] = mapped_column(String(2000), comment="家庭成员 JSON(密文/脱敏)")
    income_encrypted: Mapped[str | None] = mapped_column(String(200), comment="年收入(密文,列表永不返回)")
    debt_encrypted: Mapped[str | None] = mapped_column(String(200), comment="负债(密文)")
    special_flags_json: Mapped[str | None] = mapped_column(String(500), comment="特殊标记 JSON(单亲/低保/残疾…可脱敏展示)")


class AidLevelHistory(PKMixin, TenantMixin, AuditTimeMixin, Base):
    """困难等级变动史（困难学生库数据源，append-only）。change_type 认定/调整/年度复核/毕业移除。"""
    __tablename__ = "t_affairs_aid_level_history"

    student_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    from_level: Mapped[str | None] = mapped_column(String(50))
    to_level: Mapped[str | None] = mapped_column(String(50))
    change_type: Mapped[str] = mapped_column(String(50), nullable=False,
                                             comment="IDENTIFY/ADJUST/ANNUAL_REVIEW/GRADUATE_REMOVE")
    apply_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    batch_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    year_code: Mapped[str | None] = mapped_column(String(50))
    effective_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)


# ═══════════ 奖助组（13A-07，统一资助抽象）═══════════


class FundingProject(PKMixin, TenantMixin, CommonMixin, Base):
    """资助项目定义（七类）。V1 只启用 SCHOLARSHIP/GRANT，勤工/贷款等 P2 复用同抽象。"""
    __tablename__ = "t_affairs_funding_project"

    project_name: Mapped[str] = mapped_column(String(200), nullable=False)
    project_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True,
                                              comment="SCHOLARSHIP/GRANT/WORK_STUDY/LOAN/TUITION_REDUCTION/TEMPORARY_AID/GREEN_CHANNEL")
    amount: Mapped[float | None] = mapped_column(Numeric(12, 2), comment="金额(元)")
    quota: Mapped[int | None] = mapped_column(Integer, comment="名额")
    condition_json: Mapped[str | None] = mapped_column(String(2000), comment="申请条件 JSON(绩点/挂科门槛/准入等级)")
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="ENABLED", comment="ENABLED/DISABLED")


class FundingBatch(PKMixin, TenantMixin, CommonMixin, Base):
    """项目学年批次（申请窗/公示天数/名额）。状态 DRAFT/OPEN/REVIEWING/PUBLICITY/ANNOUNCED/CLOSED/ARCHIVED。"""
    __tablename__ = "t_affairs_funding_batch"

    project_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    project_type: Mapped[str | None] = mapped_column(String(50), index=True, comment="冗余项目类型,便于按类筛选")
    year_code: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    apply_start: Mapped[datetime | None] = mapped_column(DateTime)
    apply_end: Mapped[datetime | None] = mapped_column(DateTime)
    publicity_days: Mapped[int | None] = mapped_column(Integer, default=5)
    quota: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="DRAFT", index=True)


class FundingApplication(PKMixin, TenantMixin, CommonMixin, Base):
    """资助申请单（11 态，唯一键防同批次重复）。GRANTED 写 StageEvent 进 360。"""
    __tablename__ = "t_affairs_funding_application"

    batch_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    student_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    apply_source: Mapped[str] = mapped_column(String(20), nullable=False, default="SELF", comment="SELF/RECOMMEND")
    project_type: Mapped[str | None] = mapped_column(String(50), index=True)
    amount: Mapped[float | None] = mapped_column(Numeric(12, 2), comment="金额(脱敏按角色)")
    statement: Mapped[str | None] = mapped_column(String(1000), comment="申请理由")
    check_snapshot_json: Mapped[str | None] = mapped_column(String(2000), comment="资格校验快照(学籍/处分/成绩/困难库)")
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="DRAFT", index=True)
    workflow_instance_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    publicity_at: Mapped[datetime | None] = mapped_column(DateTime)
    result_at: Mapped[datetime | None] = mapped_column(DateTime)
    return_reason: Mapped[str | None] = mapped_column(String(500))

    __table_args__ = (UniqueConstraint("tenant_id", "batch_id", "student_id",
                                       name="uk_funding_app_batch_student"),)


class FundingDisbursement(PKMixin, TenantMixin, CommonMixin, Base):
    """资助发放台账（C 包·发放台账）。GRANTED 申请生成一条(1:1)；发放状态与银行回执留痕。
    金额按角色脱敏；不落银行卡全号。bank_status PENDING/ISSUED/FAILED/RETURNED。"""
    __tablename__ = "t_affairs_funding_disbursement"

    application_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    batch_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    student_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    project_type: Mapped[str | None] = mapped_column(String(50))
    amount: Mapped[float | None] = mapped_column(Numeric(12, 2), comment="发放金额(脱敏按角色)")
    disburse_no: Mapped[str | None] = mapped_column(String(100), comment="发放批次号")
    bank_last4: Mapped[str | None] = mapped_column(String(10), comment="银行卡后4位(不落全号)")
    bank_status: Mapped[str] = mapped_column(String(30), nullable=False, default="PENDING", index=True)
    issued_at: Mapped[datetime | None] = mapped_column(DateTime)
    fail_reason: Mapped[str | None] = mapped_column(String(500))

    __table_args__ = (UniqueConstraint("tenant_id", "application_id",
                                       name="uk_funding_disbursement_app"),)
