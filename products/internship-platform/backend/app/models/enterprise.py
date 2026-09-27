"""岗位实习 Standalone 共享企业权威模型。

仅保留原 SaaS canonical EmpCompany 与 InternshipEnterpriseContact。
不复制 EmpStudent/就业台账，避免把完整就业域拖入 Standalone。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CommonMixin, PKMixin, TenantMixin


class EmpCompany(PKMixin, TenantMixin, CommonMixin, Base):
    """t_emp_company —— 全系统共享「企业主档」。
    就业域(录用/岗位)与岗位实习域(企业库)共用同一张表，避免重复造企业表。
    就业侧沿用 status/cooperation_level/hired_count；实习企业库侧新增下方 additive 列，
    两域不争抢同一状态字段：企业库合作生命周期走 coop_status。"""
    __tablename__ = "t_emp_company"
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    credit_code: Mapped[str | None] = mapped_column(String(50), index=True)
    industry: Mapped[str | None] = mapped_column(String(100))
    nature: Mapped[str | None] = mapped_column(String(50))
    city: Mapped[str | None] = mapped_column(String(50))
    contact_person: Mapped[str | None] = mapped_column(String(100))
    contact_phone_encrypted: Mapped[str | None] = mapped_column(String(500))
    cooperation_level: Mapped[str | None] = mapped_column(String(50))
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="ACTIVE")
    disable_reason: Mapped[str | None] = mapped_column(String(500))
    hired_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # ── 岗位实习「企业库」additive 扩展（就业域不引用，向后兼容）──
    region: Mapped[str | None] = mapped_column(String(100), comment="省市/地区")
    address: Mapped[str | None] = mapped_column(String(300), comment="详细地址")
    scale: Mapped[str | None] = mapped_column(String(50), comment="规模：微/小/中/大型")
    source: Mapped[str | None] = mapped_column(String(50), comment="来源 SELF_BUILT/SCHOOL_ENTERPRISE/STUDENT_SELF/RECOMMENDED")
    coop_status: Mapped[str] = mapped_column(String(50), nullable=False, default="PENDING",
                                             index=True, comment="企业库合作状态机 PENDING/ACTIVE/REJECTED/SUSPENDED/BLACKLIST/ARCHIVED")
    qualification_status: Mapped[str] = mapped_column(String(50), nullable=False, default="UNREVIEWED",
                                                      comment="资质核验 UNREVIEWED/PASSED/FAILED")
    blacklist: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    blacklist_reason: Mapped[str | None] = mapped_column(String(500))
    review_by: Mapped[str | None] = mapped_column(String(100))
    review_at: Mapped[datetime | None] = mapped_column(DateTime)
    review_comment: Mapped[str | None] = mapped_column(String(500))
    access_valid_until: Mapped[datetime | None] = mapped_column(DateTime, comment="实习企业准入有效期")
    intern_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="累计接收实习生数")
    remark: Mapped[str | None] = mapped_column(String(500))
    archived_at: Mapped[datetime | None] = mapped_column(DateTime)
    archived_by: Mapped[str | None] = mapped_column(String(100))
    # E4 企业 Portal 公开展示资料；学校准入/黑名单/资质字段仍由上方 canonical 字段控制。
    logo_file_id: Mapped[str | None] = mapped_column(String(64))
    cover_file_id: Mapped[str | None] = mapped_column(String(64))
    short_name: Mapped[str | None] = mapped_column(String(100))
    short_intro: Mapped[str | None] = mapped_column(String(500))
    website: Mapped[str | None] = mapped_column(String(300))
    main_business: Mapped[str | None] = mapped_column(Text)
    established_year: Mapped[int | None] = mapped_column(Integer)


class InternshipEnterpriseContact(PKMixin, TenantMixin, CommonMixin, Base):
    """t_internship_enterprise_contact —— 企业库·联系人 / 企业导师（挂在 t_emp_company 下）。"""
    __tablename__ = "t_internship_enterprise_contact"
    company_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    contact_type: Mapped[str] = mapped_column(String(50), nullable=False, default="CONTACT",
                                              comment="CONTACT 联系人 / MENTOR 企业导师")
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    title: Mapped[str | None] = mapped_column(String(100), comment="职务")
    phone_encrypted: Mapped[str | None] = mapped_column(String(500))
    email: Mapped[str | None] = mapped_column(String(200))
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    remark: Mapped[str | None] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="ACTIVE",
                                        comment="ACTIVE/INACTIVE")
