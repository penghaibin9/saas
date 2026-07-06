"""13A-P4 违纪处分 + 风险预警模型（草案 §3.5/§3.6）。

处分：case(11态,EFFECTIVE 事务内投影 t_cs_discipline) + remove_apply(解除子流程 辅→院→处)。
风险：risk_record(多来源,(source,source_ref_id)唯一防重,8态) + handle_record(处置留痕,不走审批)。
t_cs_discipline 加列 source_case_id 见 campus_service.py（投影来源回链）。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import (BigInteger, Boolean, DateTime, String, UniqueConstraint)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CommonMixin, PKMixin, TenantMixin

DISC_TYPES = ("WARNING", "SERIOUS_WARNING", "DEMERIT", "PROBATION", "EXPEL")  # 警告/严重警告/记过/留校察看/开除
_SEVERE = ("PROBATION", "EXPEL")  # 需校级审批的严重处分


class DisciplineCase(PKMixin, TenantMixin, CommonMixin, Base):
    """违纪处分主档（11 态）。EFFECTIVE 时事务内投影 t_cs_discipline 一行，cs_discipline_id 回链。"""
    __tablename__ = "t_affairs_discipline_case"

    student_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    disc_type: Mapped[str] = mapped_column(String(50), nullable=False, default="WARNING",
                                           comment="WARNING/SERIOUS_WARNING/DEMERIT/PROBATION/EXPEL")
    reason: Mapped[str | None] = mapped_column(String(1000), comment="违纪事实")
    doc_no: Mapped[str | None] = mapped_column(String(100), comment="决定书文号")
    decide_date: Mapped[datetime | None] = mapped_column(DateTime)
    effective_at: Mapped[datetime | None] = mapped_column(DateTime)
    removed_at: Mapped[datetime | None] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="REGISTERED", index=True)
    workflow_instance_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    cs_discipline_id: Mapped[int | None] = mapped_column(BigInteger, index=True, comment="t_cs_discipline 投影行回链")
    return_reason: Mapped[str | None] = mapped_column(String(500))


class DisciplineRemoveApply(PKMixin, TenantMixin, CommonMixin, Base):
    """处分解除申请（辅→院→处 三节点，同 REMOVE_REVIEW 内以 current_node 推进）。"""
    __tablename__ = "t_affairs_discipline_remove_apply"

    case_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    student_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    apply_reason: Mapped[str | None] = mapped_column(String(1000), comment="表现材料/解除理由")
    min_months_check: Mapped[bool | None] = mapped_column(Boolean, default=True, comment="最短解除期校验结果")
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="SUBMITTED",
                                        comment="SUBMITTED/COUNSELOR_REVIEW/COLLEGE_REVIEW/SA_OFFICE_FINAL/APPROVED/REJECTED/RETURNED")
    current_node: Mapped[str | None] = mapped_column(String(50))
    workflow_instance_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    return_reason: Mapped[str | None] = mapped_column(String(500))


class AffairsRiskRecord(PKMixin, TenantMixin, CommonMixin, Base):
    """学工风险中枢（多来源引用不复制来源数据，8 态；(source,source_ref_id) 唯一防重复）。"""
    __tablename__ = "t_affairs_risk_record"

    student_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    source: Mapped[str] = mapped_column(String(50), nullable=False, index=True,
                                        comment="LEAVE_OVERDUE/ACADEMIC_WARNING/DORM/MENTAL/DISCIPLINE/INTERNSHIP/...")
    source_ref_id: Mapped[int | None] = mapped_column(BigInteger, comment="来源单据 id（引用不复制）")
    risk_level: Mapped[str] = mapped_column(String(20), nullable=False, default="MEDIUM",
                                            comment="LOW/MEDIUM/HIGH/CRITICAL")
    title: Mapped[str | None] = mapped_column(String(200))
    detail: Mapped[str | None] = mapped_column(String(1000), comment="MENTAL 来源明细仅授权角色可见")
    owner_id: Mapped[int | None] = mapped_column(BigInteger, index=True, comment="责任人")
    deadline_at: Mapped[datetime | None] = mapped_column(DateTime)
    assigned_at: Mapped[datetime | None] = mapped_column(DateTime, comment="分派时刻(超时升级依据)")
    escalated_at: Mapped[datetime | None] = mapped_column(DateTime, comment="升级扫描幂等标记")
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="NEW", index=True,
                                        comment="NEW/ASSIGNED/PROCESSING/FOLLOWING/TRANSFERRED/ESCALATED/CLOSED/REOPENED")
    is_archived: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    closed_reason: Mapped[str | None] = mapped_column(String(500))

    __table_args__ = (UniqueConstraint("tenant_id", "source", "source_ref_id",
                                       name="uk_risk_source_ref"),)


class AffairsRiskHandle(PKMixin, TenantMixin, CommonMixin, Base):
    """风险处置留痕（每个动作一条，不走审批；PROCESS/FOLLOW/TRANSFER/ESCALATE/CLOSE/REOPEN/TAKEOVER）。"""
    __tablename__ = "t_affairs_risk_handle_record"

    risk_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    content: Mapped[str | None] = mapped_column(String(1000))
    operator: Mapped[str | None] = mapped_column(String(100))
    from_status: Mapped[str | None] = mapped_column(String(50))
    to_status: Mapped[str | None] = mapped_column(String(50))
