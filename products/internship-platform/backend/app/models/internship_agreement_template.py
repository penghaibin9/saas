"""岗位实习中心 · 实习协议模板库模型（t_internship_agreement_template）。

独立业务对象：学校维护「实习协议 / 三方协议 / 安全责任书」等模板，供后续协议发起复用。
- 适用范围：学院/专业/年级/批次（JSON 数组，空=全校通用）；
- 模板变量：如学生姓名/企业名称/岗位名称/实习时间（JSON，供协议渲染占位）；
- 状态机 4 态 + 默认模板标记（同租户同类型仅一个默认）。

隔离说明：本文件为协议模板配置主数据，不引用实习学生/打卡/周报/毕设等表；
审计复用 t_internship_audit_trail(target_type=AGREEMENT_TEMPLATE)。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CommonMixin, PKMixin, TenantMixin


class InternshipAgreementTemplate(PKMixin, TenantMixin, CommonMixin, Base):
    """t_internship_agreement_template 实习协议模板。"""
    __tablename__ = "t_internship_agreement_template"

    # ── 基本信息 ──
    name: Mapped[str] = mapped_column(String(200), nullable=False, comment="模板名称")
    category: Mapped[str | None] = mapped_column(String(50), comment="协议类型：三方/顶岗/安全责任书等")
    # 注：列名用 template_version，避免与 CommonMixin.version（乐观锁 Int）同名冲突
    template_version: Mapped[str] = mapped_column(String(32), nullable=False, default="v1.0",
                                                  comment="模板版本号")
    # ── 适用范围（JSON 数组；空/[] 表示全校通用）──
    scope_college_ids: Mapped[list | None] = mapped_column(JSON, comment="适用学院ID列表")
    scope_major_ids: Mapped[list | None] = mapped_column(JSON, comment="适用专业ID列表")
    scope_grades: Mapped[list | None] = mapped_column(JSON, comment="适用年级列表，如['2024级']")
    scope_batch_ids: Mapped[list | None] = mapped_column(JSON, comment="适用实习批次ID列表")
    # ── 正文与变量 ──
    body: Mapped[str | None] = mapped_column(Text, comment="模板正文（可含 {{变量}} 占位）")
    variables: Mapped[list | None] = mapped_column(
        JSON, comment="变量说明 [{key,label,example}]，如 studentName/companyName/positionName/internPeriod")
    # ── 状态与默认 ──
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False,
                                             comment="是否默认模板（同租户同类型唯一）")
    # 状态机：DRAFT/ENABLED/DISABLED/ARCHIVED
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="DRAFT", index=True)
    remark: Mapped[str | None] = mapped_column(String(500))
    enabled_at: Mapped[datetime | None] = mapped_column(DateTime)
    disabled_at: Mapped[datetime | None] = mapped_column(DateTime)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime)
    archived_by: Mapped[str | None] = mapped_column(String(100))
