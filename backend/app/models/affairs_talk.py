"""13A-P5 谈心谈话 + 家校联系模型（草案 §3.7）。

谈话：plan(计划,批量圈定) + record(记录,可无计划直录,心理类主题按权限)。
家校：family_contact_log(append-only,不存号码本体——号码在 t_student_contact 加密;查看完整必填原因+审计)。
状态枚举按 A5 §7 状态机（列结构照 C3）。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import AuditTimeMixin, Base, CommonMixin, PKMixin, TenantMixin

TALK_TOPICS = ("DAILY", "ACADEMIC", "PSYCHOLOGY", "DISCIPLINE", "EMPLOYMENT",
               "INTERNSHIP", "AID", "DORM")  # 日常/学业/心理/违纪/就业/实习/困难帮扶/宿舍异常


class TalkPlan(PKMixin, TenantMixin, CommonMixin, Base):
    """谈话计划（批量圈定学生与主题）。DRAFT/SCHEDULED/DONE/CANCELLED。"""
    __tablename__ = "t_affairs_talk_plan"

    plan_name: Mapped[str | None] = mapped_column(String(200))
    teacher_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    topic_type: Mapped[str] = mapped_column(String(50), nullable=False, default="DAILY")
    planned_at: Mapped[datetime | None] = mapped_column(DateTime)
    student_ids_json: Mapped[str | None] = mapped_column(String(2000))
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="DRAFT", index=True)


class TalkRecord(PKMixin, TenantMixin, CommonMixin, Base):
    """谈话记录（plan_id nullable 可直录；心理类主题明细按权限）。PLANNED→COMPLETED→FOLLOW_UP→CLOSED。"""
    __tablename__ = "t_affairs_talk_record"

    plan_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    student_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    teacher_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    topic_type: Mapped[str] = mapped_column(String(50), nullable=False, default="DAILY")
    topic: Mapped[str | None] = mapped_column(String(500), comment="谈话主题")
    talk_at: Mapped[datetime | None] = mapped_column(DateTime)
    content: Mapped[str | None] = mapped_column(String(2000), comment="谈话内容(心理类按权限)")
    result: Mapped[str | None] = mapped_column(String(50), comment="谈话结果编码")
    need_follow: Mapped[bool | None] = mapped_column(Boolean, default=False)
    related_risk_id: Mapped[int | None] = mapped_column(BigInteger, comment="转风险关联")
    related_contact_id: Mapped[int | None] = mapped_column(BigInteger, comment="转家校关联")
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="PLANNED", index=True,
                                        comment="PLANNED/SCHEDULED/COMPLETED/FOLLOW_UP/CLOSED/CANCELLED")


class FamilyContactLog(PKMixin, TenantMixin, AuditTimeMixin, Base):
    """家校联系记录（append-only，不存号码本体；查看完整号码必填原因+审计）。"""
    __tablename__ = "t_affairs_family_contact_log"

    student_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    teacher_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    contact_type: Mapped[str] = mapped_column(String(50), nullable=False, default="PHONE",
                                              comment="PHONE/WECHAT/VISIT/MESSAGE")
    contact_reason: Mapped[str | None] = mapped_column(String(500))
    contact_result: Mapped[str | None] = mapped_column(String(1000))
    related_risk_id: Mapped[int | None] = mapped_column(BigInteger)
    full_phone_viewed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False,
                                                    comment="是否查看了完整号码")
    view_reason: Mapped[str | None] = mapped_column(String(500), comment="查看完整号码的原因")
    occurred_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    # 家校回执（C 包·联系/回执）——加列不改旧列
    receipt_status: Mapped[str] = mapped_column(String(20), nullable=False, default="PENDING",
                                                comment="PENDING待回执/RECEIVED已回执")
    receipt_at: Mapped[datetime | None] = mapped_column(DateTime)
    receipt_note: Mapped[str | None] = mapped_column(String(500), comment="家长回执内容")
