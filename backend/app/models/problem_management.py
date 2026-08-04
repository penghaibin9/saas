"""PLAT-10 问题管理、已知错误与事故复盘。

平台级实体（一个问题可能溯源多个事件、指向一次跨租户变更），不经过 _tid()。
Problem 和 PLAT-09 的 Incident 是一对多：一个 RESOLVED 事件请求转 Problem
后，落一条 Problem 记录（之前 PLAT-09 只做资格判定和请求标记，没有落地）；
PLAT-11 的 ChangeRequest 作为"永久修复"的证据链接，不重复实现变更流程。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, BigInteger, Boolean, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CommonMixin, PKMixin


class Problem(PKMixin, CommonMixin, Base):
    """t_problem 问题主记录。"""
    __tablename__ = "t_problem"

    title: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="OPEN", index=True,
        comment="OPEN/INVESTIGATING/KNOWN_ERROR/RESOLVED/CLOSED")
    root_cause: Mapped[str | None] = mapped_column(String(2000))
    workaround: Mapped[str | None] = mapped_column(String(2000))
    source_incident_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    permanent_fix_change_id: Mapped[int | None] = mapped_column(BigInteger)
    known_error_published: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime)


class ProblemPostmortem(PKMixin, CommonMixin, Base):
    """t_problem_postmortem 事故复盘（内部记录，发布前不对外可见）。"""
    __tablename__ = "t_problem_postmortem"

    problem_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    what_happened: Mapped[str | None] = mapped_column(String(4000))
    timeline_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    impact_summary: Mapped[str | None] = mapped_column(String(2000))
    action_items_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    published: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    published_at: Mapped[datetime | None] = mapped_column(DateTime)
    author_user_id: Mapped[int | None] = mapped_column(BigInteger)
