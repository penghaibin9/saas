"""13A 学工中心 · 班级材料 + 辅导员考评域模型（t_affairs_ 前缀 + 公共字段）。

- 班级材料：班级台账材料清单（班会/主题活动/评优/考勤/总结等），附件走 t_file_object（存 file_id）。
- 辅导员考评：考评周期 + 每辅导员考评记录（系统自动抓取工作量指标 + 学院评分 + 排名）。
  设计对齐 13A-04.5（P2，五类留痕自动生成工作量 + 学院打分）；申诉/发布为简化版，见历史欠账。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CommonMixin, PKMixin, TenantMixin


class AffairsClassMaterial(PKMixin, TenantMixin, CommonMixin, Base):
    """班级材料（班级台账，附件存 file_id 回链 t_file_object）。审计=TRAIL；不走审批。"""
    __tablename__ = "t_affairs_class_material"

    class_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    material_type: Mapped[str] = mapped_column(
        String(50), nullable=False,
        comment="CLASS_MEETING 班会/THEME_ACTIVITY 主题活动/EVALUATION 评优/ATTENDANCE 考勤/SUMMARY 总结/OTHER 其他")
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    file_id: Mapped[str | None] = mapped_column(String(100), comment="附件 file_id（文件中心）")
    file_name: Mapped[str | None] = mapped_column(String(255))
    material_at: Mapped[datetime | None] = mapped_column(DateTime, comment="材料日期")
    remark: Mapped[str | None] = mapped_column(String(500))
    uploader: Mapped[str | None] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="ACTIVE", comment="ACTIVE/VOIDED")


class AffairsCounselorAssessmentPeriod(PKMixin, TenantMixin, CommonMixin, Base):
    """辅导员考评周期。"""
    __tablename__ = "t_affairs_counselor_assessment_period"

    period_name: Mapped[str] = mapped_column(String(100), nullable=False)
    semester: Mapped[str | None] = mapped_column(String(50))
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="DRAFT",
                                        comment="DRAFT/COLLECTED 已生成/SCORING 评分中/PUBLISHED 已发布")
    remark: Mapped[str | None] = mapped_column(String(500))


class AffairsCounselorAssessment(PKMixin, TenantMixin, CommonMixin, Base):
    """辅导员考评记录（一辅导员一周期一条，系统自动指标 + 学院评分 + 排名）。"""
    __tablename__ = "t_affairs_counselor_assessment"

    period_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    counselor_id: Mapped[int | None] = mapped_column(BigInteger, index=True, comment="SchoolClass.counselor_id")
    counselor_name: Mapped[str | None] = mapped_column(String(100))
    class_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    student_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    metrics_json: Mapped[str | None] = mapped_column(Text, comment="系统自动抓取的五类工作量指标 JSON")
    auto_score: Mapped[float | None] = mapped_column(Numeric(6, 1), comment="系统自动分（工作量折算）")
    college_score: Mapped[float | None] = mapped_column(Numeric(6, 1), comment="学院评分")
    total_score: Mapped[float | None] = mapped_column(Numeric(6, 1), comment="综合分=自动*0.6+学院*0.4")
    rank_no: Mapped[int | None] = mapped_column(Integer, comment="周期内排名")
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="PENDING",
                                        comment="PENDING 待评分/SCORED 已评分")
    scored_by: Mapped[str | None] = mapped_column(String(100))
    scored_at: Mapped[datetime | None] = mapped_column(DateTime)
