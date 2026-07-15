"""13A-D 心理健康自评（学生端，移动端首创）。

红线：本表仅登记学生自评原始作答与算术汇总分，不构成任何临床诊断结论（系统不做自动诊断，
与既有 t_affairs_psy_referral 一致的设计红线）。命中阈值或学生主动求助信号时，由
affairs_psy_survey_service 调用既有 affairs_mental_service.create_referral 生成人工可核实的
一般关注记录，最终是否需要关注/如何关注仍由心理老师人工判断。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CommonMixin, PKMixin, TenantMixin


class PsySurveySubmission(PKMixin, TenantMixin, CommonMixin, Base):
    """t_affairs_psy_survey_submission 学生自评问卷提交（原始作答+算术汇总分，非诊断）。"""
    __tablename__ = "t_affairs_psy_survey_submission"

    student_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    answers_json: Mapped[str] = mapped_column(Text, nullable=False, comment="[{qKey,score}]原始作答")
    total_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="算术汇总分，非诊断")
    wants_contact: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False,
                                                comment="学生是否主动勾选希望老师联系")
    triggered_referral_id: Mapped[int | None] = mapped_column(
        BigInteger, comment="命中阈值/主动求助时生成的 t_affairs_psy_referral.id，回链")
    submitted_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
