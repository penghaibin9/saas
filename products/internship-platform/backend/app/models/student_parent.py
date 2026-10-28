"""学生 PC 门户 · 家长授权代理（proxy）绑定。

学生本人在门户发起授权：填家长姓名/关系/手机号 + 勾选可见范围；家长凭手机号验证码登录，
全程只读，仅见被授权学生的授权范围；学生可随时撤销（link_status=REVOKED，保留行做审计）。

敏感字段（家长手机号）沿用本仓库既有约定：*_encrypted 存值（读时经 _mask_phone 脱敏）
+ *_hash 供家长侧验证码登录/查重匹配（见 app/services/db_service 的联系值写法）。
可见范围最小化：心理关注、家庭隐私证明材料明细、敏感字段明文一律不进入本表授权范围。
"""
from __future__ import annotations

from sqlalchemy import JSON, BigInteger, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CommonMixin, PKMixin, TenantMixin


class StudentParentLink(PKMixin, TenantMixin, CommonMixin, Base):
    """t_student_parent_link：学生-家长授权代理绑定（行级隔离 tenant_id）。"""
    __tablename__ = "t_student_parent_link"

    student_id: Mapped[int] = mapped_column(
        BigInteger, nullable=False, index=True, comment="= t_student_profile.id（被查看学生）")
    student_no: Mapped[str] = mapped_column(
        String(50), nullable=False, index=True, comment="学号（冗余，便于家长侧解析）")
    guardian_name: Mapped[str] = mapped_column(
        String(100), nullable=False, comment="家长/监护人姓名")
    relation: Mapped[str] = mapped_column(
        String(20), nullable=False, default="PARENT",
        comment="关系：FATHER/MOTHER/GUARDIAN/OTHER/PARENT")
    guardian_phone_encrypted: Mapped[str] = mapped_column(
        String(500), nullable=False, comment="敏感：家长手机号（照既有约定存值，读时脱敏）")
    guardian_phone_hash: Mapped[str] = mapped_column(
        String(128), nullable=False, index=True, comment="手机号 hash：家长验证码登录/查重匹配")
    visible_scopes: Mapped[list | None] = mapped_column(
        JSON, comment="授权可见范围：ACADEMIC_GRADE/FEE_AID_STATUS/CAMPUS_ALERT/CAREER_PROGRESS")
    link_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="ACTIVE", index=True, comment="ACTIVE/REVOKED")
