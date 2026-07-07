"""就业服务域模型（P7-EMPLOYMENT）。t_emp_ 前缀 + 公共字段；审计链 append-only。"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import AuditTimeMixin, Base, CommonMixin, PKMixin, TenantMixin


class EmpStudent(PKMixin, TenantMixin, CommonMixin, Base):
    __tablename__ = "t_emp_student"
    student_no: Mapped[str | None] = mapped_column(String(50), index=True)
    student_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    gender: Mapped[str | None] = mapped_column(String(10))
    grade: Mapped[str | None] = mapped_column(String(20))
    college_name: Mapped[str | None] = mapped_column(String(100))
    major_name: Mapped[str | None] = mapped_column(String(100))
    class_id: Mapped[str | None] = mapped_column(String(50))
    class_name: Mapped[str | None] = mapped_column(String(100))
    phone_encrypted: Mapped[str | None] = mapped_column(String(500))
    id_card_encrypted: Mapped[str | None] = mapped_column(String(500))
    destination_type: Mapped[str] = mapped_column(String(50), nullable=False, default="UNEMPLOYED")
    company_name: Mapped[str | None] = mapped_column(String(200))
    job_title: Mapped[str | None] = mapped_column(String(100))
    salary_range: Mapped[str | None] = mapped_column(String(50))
    sign_date: Mapped[str | None] = mapped_column(String(20))
    is_match_major: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    from_internship: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    verify_status: Mapped[str] = mapped_column(String(50), nullable=False, default="PENDING_VERIFY")
    material_status: Mapped[str] = mapped_column(String(50), nullable=False, default="SUBMITTED")
    help_level: Mapped[str] = mapped_column(String(50), nullable=False, default="NORMAL")
    risk_level: Mapped[str] = mapped_column(String(50), nullable=False, default="LOW")
    record_status: Mapped[str] = mapped_column(String(50), nullable=False, default="ACTIVE")
    void_reason: Mapped[str | None] = mapped_column(String(500))
    counselor: Mapped[str | None] = mapped_column(String(100))
    employment_teacher: Mapped[str | None] = mapped_column(String(100))
    unemployed_reason: Mapped[str | None] = mapped_column(String(500))
    last_follow_up_time: Mapped[datetime | None] = mapped_column(DateTime)
    follow_up_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class EmpMaterial(PKMixin, TenantMixin, CommonMixin, Base):
    __tablename__ = "t_emp_material"
    emp_student_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    material_type: Mapped[str] = mapped_column(String(50), nullable=False, default="AGREEMENT")
    file_name: Mapped[str | None] = mapped_column(String(300))
    submit_time: Mapped[datetime | None] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="SUBMITTED")
    reviewer: Mapped[str | None] = mapped_column(String(100))
    review_time: Mapped[datetime | None] = mapped_column(DateTime)
    return_reason: Mapped[str | None] = mapped_column(String(500))
    remark: Mapped[str | None] = mapped_column(String(500))


class EmpFollowup(PKMixin, TenantMixin, CommonMixin, Base):
    __tablename__ = "t_emp_followup"
    emp_student_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    follow_time: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    way: Mapped[str] = mapped_column(String(50), nullable=False, default="PHONE")
    content: Mapped[str | None] = mapped_column(String(1000))
    result: Mapped[str | None] = mapped_column(String(500))
    next_plan: Mapped[str | None] = mapped_column(String(500))
    operator: Mapped[str | None] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="OPEN")
    void_reason: Mapped[str | None] = mapped_column(String(500))


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
    intern_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="累计接收实习生数")
    remark: Mapped[str | None] = mapped_column(String(500))
    archived_at: Mapped[datetime | None] = mapped_column(DateTime)
    archived_by: Mapped[str | None] = mapped_column(String(100))


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


class EmpJob(PKMixin, TenantMixin, CommonMixin, Base):
    __tablename__ = "t_emp_job"
    company_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    company_name: Mapped[str | None] = mapped_column(String(200))
    title: Mapped[str] = mapped_column(String(100), nullable=False)
    category: Mapped[str | None] = mapped_column(String(50))
    salary_range: Mapped[str | None] = mapped_column(String(50))
    headcount: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    signed_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="OPEN")
    disable_reason: Mapped[str | None] = mapped_column(String(500))
    publish_time: Mapped[str | None] = mapped_column(String(20))


class EmpAuditTrail(PKMixin, TenantMixin, AuditTimeMixin, Base):
    __tablename__ = "t_emp_audit_trail"
    biz_type: Mapped[str] = mapped_column(String(50), nullable=False)
    biz_id: Mapped[str | None] = mapped_column(String(50))
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    operator: Mapped[str | None] = mapped_column(String(100))
    role_name: Mapped[str | None] = mapped_column(String(100))
    detail: Mapped[str | None] = mapped_column(String(1000))
    before_val: Mapped[str | None] = mapped_column(String(200))
    after_val: Mapped[str | None] = mapped_column(String(200))
    occurred_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
