"""帮助与反馈（移动端本人提交，学工/管理侧受理）。

t_feedback：学生/教师提交问题、建议、咨询、投诉；本人只读自己的历史，
处理侧按租户查看。纯新增表，不改动任何现有结构，可回滚。
"""
from __future__ import annotations

from sqlalchemy import BigInteger, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CommonMixin, PKMixin, TenantMixin


class Feedback(PKMixin, TenantMixin, CommonMixin, Base):
    """t_feedback 帮助与反馈工单。"""
    __tablename__ = "t_feedback"

    user_key: Mapped[str] = mapped_column(String(100), nullable=False, index=True,
                                          comment="提交人 userId（原样存，含 db-/u_ 前缀）")
    user_type: Mapped[str] = mapped_column(String(20), nullable=False, default="STUDENT",
                                           comment="STUDENT/TEACHER")
    category: Mapped[str] = mapped_column(String(30), nullable=False, default="OTHER",
                                          comment="BUG/建议/咨询/投诉/OTHER")
    title: Mapped[str | None] = mapped_column(String(120), nullable=True, comment="标题（可选）")
    content: Mapped[str] = mapped_column(String(2000), nullable=False, comment="反馈正文")
    contact: Mapped[str | None] = mapped_column(String(100), nullable=True, comment="联系方式（可选）")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="SUBMITTED",
                                        comment="SUBMITTED/HANDLING/CLOSED")
    reply: Mapped[str | None] = mapped_column(String(2000), nullable=True, comment="处理侧回复")
    handled_by: Mapped[int | None] = mapped_column(BigInteger, nullable=True, comment="受理人 userId")
