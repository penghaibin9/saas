"""实习企业适用学院关系，复用全平台企业主档。"""
from sqlalchemy import BigInteger, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base, CommonMixin, PKMixin, TenantMixin


class InternshipEnterpriseCollegeScope(PKMixin, TenantMixin, CommonMixin, Base):
    """岗位实习企业适用学院范围。

    无任何有效 scope 行 = 全校通用；存在 scope 行 = 仅指定学院可在岗位实习分配场景使用。
    该关系只属于岗位实习域，不修改就业域共享企业主档语义。
    """
    __tablename__ = "t_internship_enterprise_college_scope"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "company_id", "college_id",
            name="uk_ix_enterprise_college_scope",
        ),
        Index(
            "ix_ix_enterprise_college_scope_lookup",
            "tenant_id", "college_id", "company_id", "is_deleted",
        ),
    )

    company_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    college_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    scope_source: Mapped[str] = mapped_column(
        String(30), nullable=False, default="MANUAL",
        comment="MANUAL/AUTO_SCOPED/IMPORT",
    )


