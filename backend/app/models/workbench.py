"""角色工作台配置主表。"""
from __future__ import annotations

from sqlalchemy import JSON, BigInteger, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CommonMixin, PKMixin, TenantMixin


class RoleWorkbenchConfig(PKMixin, TenantMixin, CommonMixin, Base):
    __tablename__ = "t_role_workbench_config"
    __table_args__ = (UniqueConstraint("tenant_id", "role_code", name="uk_role_workbench_role"),)

    role_code: Mapped[str] = mapped_column(String(50), nullable=False)
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    subtitle: Mapped[str | None] = mapped_column(String(300))
    layout_code: Mapped[str] = mapped_column(String(40), nullable=False, default="STANDARD")
    card_keys_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    quick_entries_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    alert_keys_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    source_profile: Mapped[str] = mapped_column(String(50), nullable=False)
    installed_project_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="ENABLED")
