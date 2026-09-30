"""13A 奖助扩展（勤工助学 / 助学贷款 / 减免与临时补助）模型。

V1 冻结解除后补建（原属 P2「编码已冻结」）。金额按角色脱敏；不落银行卡全号（仅后4位）。
- 勤工：岗位 t_affairs_work_study_post + 上岗记录 t_affairs_work_study_record（申请→审核→上岗→终止）。
- 贷款：t_affairs_student_loan（登记→回执→核对→确认）。
- 减免/临补：t_affairs_fee_reduction（申请→审核→发放）。
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, Boolean, DateTime, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CommonMixin, PKMixin, TenantMixin


class WorkStudyPost(PKMixin, TenantMixin, CommonMixin, Base):
    """勤工助学岗位（部门发岗）。status ENABLED/DISABLED。"""
    __tablename__ = "t_affairs_work_study_post"

    dept_name: Mapped[str] = mapped_column(String(200), nullable=False, comment="用人部门")
    post_name: Mapped[str] = mapped_column(String(200), nullable=False, comment="岗位名称")
    salary: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), comment="月薪酬(元)")
    headcount: Mapped[int | None] = mapped_column(Integer, comment="需求人数")
    requirement: Mapped[str | None] = mapped_column(String(1000), comment="岗位要求")
    employment_type: Mapped[str] = mapped_column(
        String(20), nullable=False, default="FIXED", comment="FIXED固定岗位/TEMPORARY临时岗位"
    )
    work_location: Mapped[str | None] = mapped_column(String(200), comment="工作地点")
    schedule_text: Mapped[str | None] = mapped_column(String(500), comment="工作时段说明")
    apply_end: Mapped[datetime | None] = mapped_column(DateTime, comment="申请截止时间")
    monthly_hours_limit: Mapped[Decimal] = mapped_column(
        Numeric(6, 2), nullable=False, default=Decimal("40.00"), comment="单生月工时上限"
    )
    agreement_required: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, comment="上岗前是否必须确认协议"
    )
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="ENABLED", index=True)


class WorkStudyRecord(PKMixin, TenantMixin, CommonMixin, Base):
    """勤工上岗记录。status APPLIED/APPROVED/ONBOARD/REJECTED/TERMINATED；月度补贴累计 subsidy_total。"""
    __tablename__ = "t_affairs_work_study_record"

    post_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    student_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="APPLIED", index=True)
    onboard_at: Mapped[datetime | None] = mapped_column(DateTime)
    terminated_at: Mapped[datetime | None] = mapped_column(DateTime)
    subsidy_total: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), default=Decimal("0.00"), comment="累计补贴")
    apply_statement: Mapped[str | None] = mapped_column(String(1000), comment="本人申请说明")
    availability: Mapped[str | None] = mapped_column(String(500), comment="可工作时段")
    agreement_confirmed: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, comment="已核验勤工助学协议"
    )
    agreement_confirmed_at: Mapped[datetime | None] = mapped_column(DateTime, comment="协议核验时间")
    remark: Mapped[str | None] = mapped_column(String(500))

    __table_args__ = (UniqueConstraint("tenant_id", "post_id", "student_id", "status",
                                       name="uk_work_study_active"),)


class WorkStudyMonthly(PKMixin, TenantMixin, CommonMixin, Base):
    """勤工月度考核（一岗一生一月一条）。rating GOOD优/PASS合格/FAIL不合格；确认即累计补贴。"""
    __tablename__ = "t_affairs_work_study_monthly"

    record_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    student_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    month_code: Mapped[str] = mapped_column(String(20), nullable=False, comment="考核月，如 2025-10")
    work_hours: Mapped[float | None] = mapped_column(Numeric(6, 2), comment="工时")
    rating: Mapped[str] = mapped_column(String(20), nullable=False, default="PASS",
                                        comment="GOOD/PASS/FAIL")
    subsidy_amount: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), comment="当月补贴")
    remark: Mapped[str | None] = mapped_column(String(500))

    __table_args__ = (UniqueConstraint("tenant_id", "record_id", "month_code",
                                       name="uk_work_study_monthly"),)


class StudentLoan(PKMixin, TenantMixin, CommonMixin, Base):
    """助学贷款登记台账。loan_type ORIGIN生源地/CAMPUS校园地；
    status REGISTERED待回执/RECEIPT待核验/RETURNED已退回/VERIFIED已核验/
    CONFIRMED已确认/WITHDRAWN已撤回。银行卡仅后4位，回执编号静态加密。"""
    __tablename__ = "t_affairs_student_loan"

    student_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    loan_type: Mapped[str] = mapped_column(String(30), nullable=False, default="ORIGIN",
                                           comment="ORIGIN/CAMPUS")
    bank_name: Mapped[str | None] = mapped_column(String(200))
    bank_last4: Mapped[str | None] = mapped_column(String(10))
    year_code: Mapped[str | None] = mapped_column(String(50), comment="贷款学年")
    amount: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), comment="贷款金额(脱敏)")
    receipt_file_id: Mapped[int | None] = mapped_column(BigInteger, comment="回执附件")
    receipt_code_encrypted: Mapped[str | None] = mapped_column(String(500), comment="电子回执编号(密文)")
    receipt_code_hash: Mapped[str | None] = mapped_column(String(64), index=True, comment="电子回执编号检索哈希")
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="REGISTERED", index=True)
    remark: Mapped[str | None] = mapped_column(String(500))
    review_opinion: Mapped[str | None] = mapped_column(String(1000))
    reviewer: Mapped[str | None] = mapped_column(String(100))
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime)
    returned_at: Mapped[datetime | None] = mapped_column(DateTime)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime)
    withdrawn_at: Mapped[datetime | None] = mapped_column(DateTime)


class FeeReduction(PKMixin, TenantMixin, CommonMixin, Base):
    """学费减免 / 临时困难补助。item_type REDUCTION减免/TEMP_AID临补；
    status SUBMITTED/RETURNED/APPROVED/REJECTED/ISSUED/WITHDRAWN。金额脱敏。"""
    __tablename__ = "t_affairs_fee_reduction"

    student_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    item_type: Mapped[str] = mapped_column(String(30), nullable=False, default="REDUCTION",
                                           comment="REDUCTION/TEMP_AID")
    amount: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    year_code: Mapped[str | None] = mapped_column(String(20), index=True, comment="申请学年")
    reason_category: Mapped[str | None] = mapped_column(String(50), comment="困难原因类别")
    reason: Mapped[str | None] = mapped_column(String(1000))
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="SUBMITTED", index=True)
    review_opinion: Mapped[str | None] = mapped_column(String(1000))
    reviewer: Mapped[str | None] = mapped_column(String(100))
    fulfillment_channel: Mapped[str | None] = mapped_column(String(30), comment="TUITION_LEDGER/BANK_TRANSFER")
    fulfillment_reference: Mapped[str | None] = mapped_column(String(200), comment="结果凭证或流水摘要")
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime)
    returned_at: Mapped[datetime | None] = mapped_column(DateTime)
    withdrawn_at: Mapped[datetime | None] = mapped_column(DateTime)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime)
    issued_at: Mapped[datetime | None] = mapped_column(DateTime)
