"""13A-D 学生活动 波次3 · 社团管理（05 卡）模型。

社团档案 t_affairs_club（建社→审批→运营→年审→换届/注销）+ 成员/任职 t_affairs_club_member
+ 年审记录 t_affairs_club_annual_review。全表带 tenant_id；软删除+乐观锁复用 CommonMixin。
依据教育部/共青团高校学生社团管理办法（社团登记、指导教师、年度审核口径）。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CommonMixin, PKMixin, TenantMixin


class AffairsClub(PKMixin, TenantMixin, CommonMixin, Base):
    """社团档案。状态 PENDING(待审批)/ACTIVE(运营中)/SUSPENDED(暂停)/DISBANDED(注销)。"""
    __tablename__ = "t_affairs_club"

    club_name: Mapped[str] = mapped_column(String(200), nullable=False)
    club_type: Mapped[str] = mapped_column(String(50), nullable=False, default="INTEREST",
                                           comment="INTEREST兴趣/ACADEMIC学术/SPORTS体育/ARTS文艺/VOLUNTEER公益/PRACTICE实践")
    college_id: Mapped[int | None] = mapped_column(BigInteger, index=True, comment="挂靠学院，空=校级")
    advisor_name: Mapped[str | None] = mapped_column(String(100), comment="指导教师")
    president_student_id: Mapped[int | None] = mapped_column(BigInteger, index=True, comment="社长（学生主档）")
    founder_student_id: Mapped[int | None] = mapped_column(BigInteger, comment="发起人")
    charter_file_id: Mapped[int | None] = mapped_column(BigInteger, comment="章程附件")
    member_count: Mapped[int | None] = mapped_column(Integer, default=0, comment="成员数(冗余,成员变更同步)")
    established_at: Mapped[datetime | None] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="PENDING", index=True)
    reject_reason: Mapped[str | None] = mapped_column(String(500))

    __table_args__ = (UniqueConstraint("tenant_id", "club_name", name="uk_club_name"),)


class AffairsClubMember(PKMixin, TenantMixin, CommonMixin, Base):
    """社团成员/任职。role 普通成员/部长/副社长/社长；status ACTIVE/QUIT。"""
    __tablename__ = "t_affairs_club_member"

    club_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    student_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(50), nullable=False, default="MEMBER",
                                      comment="MEMBER/DEPT_HEAD/VICE_PRESIDENT/PRESIDENT")
    joined_at: Mapped[datetime | None] = mapped_column(DateTime)
    quit_at: Mapped[datetime | None] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="ACTIVE", index=True)

    __table_args__ = (UniqueConstraint("tenant_id", "club_id", "student_id", "status",
                                       name="uk_club_member_active"),)


class AffairsClubAnnualReview(PKMixin, TenantMixin, CommonMixin, Base):
    """社团年审记录（一社一年一条）。result PASS/CONDITIONAL/FAIL。"""
    __tablename__ = "t_affairs_club_annual_review"

    club_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    review_year: Mapped[str] = mapped_column(String(20), nullable=False, comment="学年，如 2025-2026")
    result: Mapped[str] = mapped_column(String(30), nullable=False, default="PASS",
                                        comment="PASS/CONDITIONAL/FAIL")
    activity_count: Mapped[int | None] = mapped_column(Integer, comment="年度活动数")
    material_file_id: Mapped[int | None] = mapped_column(BigInteger)
    comment: Mapped[str | None] = mapped_column(String(1000))
    reviewer_name: Mapped[str | None] = mapped_column(String(100))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (UniqueConstraint("tenant_id", "club_id", "review_year",
                                       name="uk_club_annual_review"),)
