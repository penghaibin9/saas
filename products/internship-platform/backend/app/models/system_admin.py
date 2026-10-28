"""独立产品的校内人员、配置与交付记录；账号、审批、导入及审计复用公共表。"""
from sqlalchemy import BigInteger, DateTime, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base, CommonMixin, PKMixin, TenantMixin


class SchoolDepartment(PKMixin, TenantMixin, CommonMixin, Base):
    __tablename__ = 't_school_department'
    __table_args__ = (UniqueConstraint('tenant_id', 'code', name='uk_school_department_code'),)
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default='ACTIVE')


class StaffProfile(PKMixin, TenantMixin, CommonMixin, Base):
    __tablename__ = 't_staff_profile'
    __table_args__ = (UniqueConstraint('tenant_id', 'staff_no', name='uk_staff_profile_no'),
                     UniqueConstraint('tenant_id', 'user_id', name='uk_staff_profile_user'))
    staff_no: Mapped[str] = mapped_column(String(100), nullable=False)
    real_name: Mapped[str] = mapped_column(String(100), nullable=False)
    user_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    college_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    department_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    phone_encrypted: Mapped[str | None] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(20), nullable=False, default='ACTIVE')


class SchoolSetting(PKMixin, TenantMixin, CommonMixin, Base):
    __tablename__ = 't_school_setting'
    __table_args__ = (UniqueConstraint('tenant_id', 'setting_key', name='uk_school_setting_key'),)
    setting_key: Mapped[str] = mapped_column(String(100), nullable=False)
    value_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)


class SchoolDeliveryRecord(PKMixin, TenantMixin, CommonMixin, Base):
    """学校提供的迁移/交付证据，不代表机器自动验收。"""
    __tablename__ = 't_school_delivery_record'
    kind: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default='PENDING')
    owner_user_id: Mapped[int | None] = mapped_column(BigInteger)
    detail_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    checked_at: Mapped[object | None] = mapped_column(DateTime)
