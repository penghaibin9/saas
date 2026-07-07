"""岗位实习中心 · 岗位库模型（P7-INTERNSHIP / POSITION）。

独立业务对象 t_internship_position：企业(t_emp_company)之下的实习岗位。
- 复用共享企业主档 t_emp_company（company_id 关联），不重复造企业表；
- batch_id 为「实习批次」预留列（nullable），批次模块完成后再联调，本模块不依赖其已完成；
- 岗位状态机 8 态 + 容量/已分配(预留) + 专业/年级要求 + 企业导师关联 + 风险标记。

隔离说明：本文件与 batch/实习批次相关文件互不相干，未引用其表/服务。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CommonMixin, PKMixin, TenantMixin


class InternshipPosition(PKMixin, TenantMixin, CommonMixin, Base):
    """t_internship_position 实习岗位（岗位库）。"""
    __tablename__ = "t_internship_position"

    # ── 企业关联（复用 t_emp_company，不重复造企业表）──
    company_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True,
                                            comment="→ t_emp_company.id")
    company_name: Mapped[str | None] = mapped_column(String(200), comment="冗余展示名")
    # ── 实习批次预留（nullable，待批次模块联调；本模块不依赖）──
    batch_id: Mapped[int | None] = mapped_column(BigInteger, index=True,
                                                 comment="预留·t_internship_batch.id（批次模块完成后联调）")
    # ── 岗位主档 ──
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    category: Mapped[str | None] = mapped_column(String(50), comment="岗位类别")
    major_requirement: Mapped[str | None] = mapped_column(String(200), comment="专业要求")
    grade_requirement: Mapped[str | None] = mapped_column(String(100), comment="年级要求")
    work_location: Mapped[str | None] = mapped_column(String(200), comment="工作地点")
    salary_range: Mapped[str | None] = mapped_column(String(50), comment="薪资区间")
    subsidy: Mapped[str | None] = mapped_column(String(50), comment="补贴")
    headcount: Mapped[int] = mapped_column(Integer, nullable=False, default=1, comment="岗位容量")
    allocated_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0,
                                                 comment="已分配人数（预留，分配模块写入）")
    # ── 企业导师关联（→ t_internship_enterprise_contact，企业库能力）──
    mentor_contact_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    mentor_name: Mapped[str | None] = mapped_column(String(100))
    # ── 风险 ──
    risk_flag: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    risk_note: Mapped[str | None] = mapped_column(String(500))
    # ── 状态机：DRAFT/PENDING/PUBLISHED/OFFLINE/SUSPENDED/FULL/RISK/ARCHIVED ──
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="DRAFT", index=True)
    remark: Mapped[str | None] = mapped_column(String(500))
    publish_at: Mapped[datetime | None] = mapped_column(DateTime)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime)
    archived_by: Mapped[str | None] = mapped_column(String(100))
