"""13A-D 学生活动 波次3 · 学生干部与组织（06 卡）模型。

学生组织 t_affairs_student_org（校/院学生会、社联等）+ 任职 t_affairs_org_position。
班级级班干部继续复用既有 t_affairs_class_cadre（AffairsClassCadre）；"干部履历"由 service
union 两者。全表带 tenant_id。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CommonMixin, PKMixin, TenantMixin


class AffairsStudentOrg(PKMixin, TenantMixin, CommonMixin, Base):
    """学生组织。org_type STUDENT_UNION学生会/SOCIETY_FEDERATION社联/SELF_GOV自管会/OTHER。
    level SCHOOL校级/COLLEGE院级。status ACTIVE/DISABLED。"""
    __tablename__ = "t_affairs_student_org"

    org_name: Mapped[str] = mapped_column(String(200), nullable=False)
    org_type: Mapped[str] = mapped_column(String(50), nullable=False, default="STUDENT_UNION",
                                          comment="STUDENT_UNION/SOCIETY_FEDERATION/SELF_GOV/OTHER")
    level: Mapped[str] = mapped_column(String(30), nullable=False, default="SCHOOL",
                                       comment="SCHOOL/COLLEGE")
    college_id: Mapped[int | None] = mapped_column(BigInteger, index=True, comment="院级组织归属学院")
    advisor_name: Mapped[str | None] = mapped_column(String(100), comment="指导老师")
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="ACTIVE", index=True)

    __table_args__ = (UniqueConstraint("tenant_id", "org_name", name="uk_student_org_name"),)


class AffairsOrgPosition(PKMixin, TenantMixin, CommonMixin, Base):
    """学生组织任职（任期制）。status ACTIVE(在任)/REMOVED(卸任)。"""
    __tablename__ = "t_affairs_org_position"

    org_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    student_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    position: Mapped[str] = mapped_column(String(100), nullable=False, comment="主席/部长/干事等")
    term_code: Mapped[str | None] = mapped_column(String(50), comment="任期，如 2025-2026")
    appointed_at: Mapped[datetime | None] = mapped_column(DateTime)
    removed_at: Mapped[datetime | None] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="ACTIVE", index=True)

    __table_args__ = (UniqueConstraint("tenant_id", "org_id", "student_id", "position", "status",
                                       name="uk_org_position_active"),)
