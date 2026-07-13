"""13A-D 学生活动与第二课堂模型（波次1 活动底座）。

依据：中青联发〔2018〕5号《关于在高校实施共青团"第二课堂成绩单"制度的意见》
（共青团中央+教育部，2018-06-22，已核验原文）——课程项目体系(七类)/记录评价体系
(记录式/学分式[学时·积分]/综合式)/价值应用(综测·评优·推优入党引用)。

波次1 四表：
- 活动主表（活动/志愿/讲座/竞赛复用，8 态状态机）
- 报名签到子记录（(tenant,activity_id,student_id) 唯一）
- 第二课堂学时/积分/志愿时长流水（(tenant,student_id,activity_id,credit_type) 唯一防重复入账）
- 二课积分类目配置（学校可配，seed 默认五类）
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import (BigInteger, DateTime, Integer, Numeric, String,
                        UniqueConstraint)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import AuditTimeMixin, Base, CommonMixin, PKMixin, TenantMixin

# 活动类型：普通活动/志愿服务/讲座报告/竞赛/社会实践（对齐 CAND-STD-1 课程项目七类的落地归并）
ACTIVITY_TYPES = ("ACTIVITY", "VOLUNTEER", "LECTURE", "COMPETITION", "PRACTICE")
# 活动状态机（施工包 §7.1）
ACTIVITY_STATUS = ("DRAFT", "PUBLISHED", "ENROLL_CLOSED", "ONGOING",
                   "FINISHED", "CONFIRMED", "CANCELLED", "ARCHIVED")
# 学分类型：第二课堂学时 / 德育积分 / 志愿时长
CREDIT_TYPES = ("SECOND_CLASS", "MORAL", "VOLUNTEER_HOUR")


class AffairsActivity(PKMixin, TenantMixin, CommonMixin, Base):
    """活动主表（活动/志愿/讲座/竞赛复用一套闭环；CONFIRMED 生成学时/积分进360）。"""
    __tablename__ = "t_affairs_activity"

    activity_name: Mapped[str] = mapped_column(String(200), nullable=False)
    activity_type: Mapped[str] = mapped_column(String(30), nullable=False, default="ACTIVITY",
                                               index=True, comment="ACTIVITY/VOLUNTEER/LECTURE/COMPETITION/PRACTICE")
    scope_type: Mapped[str | None] = mapped_column(String(30), comment="SCHOOL/COLLEGE/CLASS 适用范围")
    scope_ref: Mapped[str | None] = mapped_column(String(100), comment="范围引用（学院/班级标识）")
    org_id: Mapped[int | None] = mapped_column(BigInteger, index=True, comment="挂靠社团/组织（波次3）")
    location: Mapped[str | None] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(String(2000))
    start_at: Mapped[datetime | None] = mapped_column(DateTime, index=True)
    end_at: Mapped[datetime | None] = mapped_column(DateTime)
    enroll_deadline: Mapped[datetime | None] = mapped_column(DateTime, comment="报名截止")
    quota: Mapped[int | None] = mapped_column(Integer, comment="名额上限，空=不限")
    credit_type: Mapped[str | None] = mapped_column(String(30), comment="确认后生成的学分类型 SECOND_CLASS/MORAL/VOLUNTEER_HOUR")
    credit_value: Mapped[float | None] = mapped_column(Numeric(6, 2), comment="学时/积分/时长数值")
    category_code: Mapped[str | None] = mapped_column(String(50), comment="二课积分类目 code")
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="DRAFT", index=True)
    publisher_id: Mapped[int | None] = mapped_column(BigInteger, index=True, comment="发布方 user id")
    publisher_name: Mapped[str | None] = mapped_column(String(100))
    confirm_at: Mapped[datetime | None] = mapped_column(DateTime)


class AffairsActivitySignup(PKMixin, TenantMixin, CommonMixin, Base):
    """报名/签到子记录。(tenant,activity_id,student_id) 唯一防重复报名。"""
    __tablename__ = "t_affairs_activity_signup"

    activity_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    student_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    signup_status: Mapped[str] = mapped_column(String(30), nullable=False, default="ENROLLED",
                                               comment="ENROLLED/WAITLIST/CANCELLED/CHECKED_IN/CONFIRMED")
    enrolled_at: Mapped[datetime | None] = mapped_column(DateTime, default=datetime.utcnow)
    checkin_at: Mapped[datetime | None] = mapped_column(DateTime)
    checkin_method: Mapped[str | None] = mapped_column(String(30), comment="QR/LOCATION/MANUAL")

    __table_args__ = (UniqueConstraint("tenant_id", "activity_id", "student_id",
                                       name="uk_activity_signup"),)


class AffairsActivityCredit(PKMixin, TenantMixin, AuditTimeMixin, Base):
    """第二课堂学时/德育积分/志愿时长流水（append-only）。
    (tenant,student_id,activity_id,credit_type) 唯一防重复入账；供综测/评优只读引用。"""
    __tablename__ = "t_affairs_activity_credit"

    student_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    activity_id: Mapped[int | None] = mapped_column(BigInteger, index=True, comment="来源活动，可空=手工/线下补录")
    credit_type: Mapped[str] = mapped_column(String(30), nullable=False, default="SECOND_CLASS",
                                             comment="SECOND_CLASS/MORAL/VOLUNTEER_HOUR")
    credit_value: Mapped[float] = mapped_column(Numeric(6, 2), nullable=False, default=0)
    category_code: Mapped[str | None] = mapped_column(String(50), index=True)
    source: Mapped[str] = mapped_column(String(30), nullable=False, default="ACTIVITY",
                                        comment="ACTIVITY/MANUAL_ADJUST/VOLUNTEER_RECORD")
    remark: Mapped[str | None] = mapped_column(String(500))
    granted_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (UniqueConstraint("tenant_id", "student_id", "activity_id", "credit_type",
                                       name="uk_activity_credit"),)


class AffairsVolunteerRecord(PKMixin, TenantMixin, CommonMixin, Base):
    """校外/线下志愿时长补录认定（04 卡）。PENDING→CONFIRMED(生成 VOLUNTEER_HOUR 学分)/REJECTED。
    activity_id 可空（平台活动外的补录）；credit_id 记确认时生成的学分行，防重复入账。"""
    __tablename__ = "t_affairs_volunteer_record"

    student_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    activity_id: Mapped[int | None] = mapped_column(BigInteger, index=True, comment="来源平台活动，可空=纯线下补录")
    service_name: Mapped[str] = mapped_column(String(200), nullable=False, comment="服务名称/项目")
    org_name: Mapped[str | None] = mapped_column(String(200), comment="服务单位/组织")
    hours: Mapped[float] = mapped_column(Numeric(6, 2), nullable=False, default=0, comment="认定时长(小时)")
    service_date: Mapped[datetime | None] = mapped_column(DateTime, comment="服务日期")
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="PENDING", index=True,
                                        comment="PENDING/CONFIRMED/REJECTED")
    credit_id: Mapped[int | None] = mapped_column(BigInteger, comment="确认后生成的 t_affairs_activity_credit 行")
    reject_reason: Mapped[str | None] = mapped_column(String(500))
    remark: Mapped[str | None] = mapped_column(String(500))


class AffairsCreditCategory(PKMixin, TenantMixin, CommonMixin, Base):
    """二课积分类目配置（学校可配；seed 默认五类：思想成长/社会实践/志愿公益/创新创业/文体活动）。"""
    __tablename__ = "t_affairs_credit_category"

    category_code: Mapped[str] = mapped_column(String(50), nullable=False, comment="类目编码")
    category_name: Mapped[str] = mapped_column(String(100), nullable=False)
    credit_type: Mapped[str | None] = mapped_column(String(30), comment="默认学分类型")
    description: Mapped[str | None] = mapped_column(String(500))
    sort_order: Mapped[int | None] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="ENABLED")

    __table_args__ = (UniqueConstraint("tenant_id", "category_code",
                                       name="uk_credit_category"),)
