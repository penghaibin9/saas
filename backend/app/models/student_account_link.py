"""学生主档 ↔ 登录账号的稳定绑定（学生主档统一整改 阶段 C）。

为什么需要这张表：此前全系统靠「`User.login_name == StudentProfile.student_no`」把学生
和账号关联起来——登录、移动端本人解析、消息受众、家长授权全走这条隐式约定。
后果是学号一旦更正，该生立刻登录不到自己的档案、收不到班级消息，且没有任何地方
能查出「这个账号对应哪个学生」。

本表把这层关系显式化并稳定下来：

    User.login_name        = 登录凭据（可变，学校可要求跟随学号或保持不变）
    StudentProfile.id      = 学籍身份（永久，历史业务全挂在它上面）
    StudentAccountLink     = 两者之间的稳定关系

约束口径：
- 一个学生在一个租户内只允许有一条 ACTIVE 链接（uk_tenant_student_active）；
- 一个账号也只允许绑定一个学生（uk_tenant_user_active）；
- 历史链接不物理删除，改 link_status 保留，便于事后追溯谁在什么时候换过绑定。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CommonMixin, PKMixin, TenantMixin

# 链接状态：账号生命周期与学籍生命周期分开表达，不互相顶替
LINK_ACTIVE = "ACTIVE"        # 正常绑定
LINK_SUSPENDED = "SUSPENDED"  # 学生被作废/休学等，暂停但不解绑
LINK_REVOKED = "REVOKED"      # 人工解绑（换账号、误绑纠正）
LINK_MERGED = "MERGED"        # 重复档案合并后指向新主档
LINK_STATUSES = (LINK_ACTIVE, LINK_SUSPENDED, LINK_REVOKED, LINK_MERGED)


class StudentAccountLink(PKMixin, TenantMixin, CommonMixin, Base):
    """t_student_account_link：学生主档与登录账号的稳定关系。"""
    __tablename__ = "t_student_account_link"
    __table_args__ = (
        # 唯一约束只约束 ACTIVE 行不现实（MySQL 无部分索引），因此用
        # (tenant_id, student_id, link_status) 与 (tenant_id, user_id, link_status)
        # 组合：同一学生/账号可以有多条历史行，但 ACTIVE 只能有一条。
        UniqueConstraint("tenant_id", "student_id", "link_status",
                         name="uk_sal_tenant_student_status"),
        UniqueConstraint("tenant_id", "user_id", "link_status",
                         name="uk_sal_tenant_user_status"),
        Index("ix_sal_tenant_student_status", "tenant_id", "student_id", "link_status"),
        Index("ix_sal_tenant_user_status", "tenant_id", "user_id", "link_status"),
    )

    student_id: Mapped[int] = mapped_column(
        BigInteger, nullable=False, index=True,
        comment="= t_student_profile.id（学籍身份，永久不变）")
    user_id: Mapped[int] = mapped_column(
        BigInteger, nullable=False, index=True,
        comment="= t_user.id（登录账号）")
    link_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=LINK_ACTIVE, index=True,
        comment="ACTIVE/SUSPENDED/REVOKED/MERGED")
    bound_login_name: Mapped[str | None] = mapped_column(
        String(100), comment="建立绑定时的登录名快照，仅供追溯，不作为查询键")
    bound_student_no: Mapped[str | None] = mapped_column(
        String(50), comment="建立绑定时的学号快照，仅供追溯，不作为查询键")
    source: Mapped[str] = mapped_column(
        String(30), nullable=False, default="BACKFILL",
        comment="来源：IDENTITY_IMPORT/MANUAL/BACKFILL（历史 login_name==student_no 回填）")
    bound_at: Mapped[datetime | None] = mapped_column(DateTime, comment="绑定时间")
    unbound_at: Mapped[datetime | None] = mapped_column(DateTime, comment="解绑/暂停时间")
    remark: Mapped[str | None] = mapped_column(String(500), comment="备注（换绑原因等）")
