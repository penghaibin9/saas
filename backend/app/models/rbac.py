"""用户与 RBAC（冻结册 §4.2 t_user 完整 DDL；§4.3 采用 11 中心 t_role/t_permission/t_role_permission/t_user_role）。
t_permission 为跨租户系统级定义（无 tenant_id）。"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CommonMixin, PKMixin, TenantMixin


class User(PKMixin, TenantMixin, CommonMixin, Base):
    """t_user 用户账号（§4.2.1）。"""
    __tablename__ = "t_user"
    __table_args__ = (UniqueConstraint("tenant_id", "login_name", name="uk_tenant_login"),)

    login_name: Mapped[str] = mapped_column(String(100), nullable=False, comment="工号/学号/手机号登录名")
    real_name: Mapped[str] = mapped_column(String(100), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(200), nullable=False, comment="bcrypt（TODO P1/P2 接真实口令体系）")
    user_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True,
                                           comment="SCHOOL_ADMIN/TEACHER/STUDENT/ENTERPRISE_MENTOR/GUARDIAN/PLATFORM_OP")
    phone_encrypted: Mapped[str | None] = mapped_column(String(500), comment="敏感：手机号密文")
    phone_hash: Mapped[str | None] = mapped_column(String(128), index=True, comment="手机号不可逆 hash（查重/匹配）")
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="ACTIVE", comment="ACTIVE/DISABLED/LOCKED")
    must_change_password: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime)


class Role(PKMixin, TenantMixin, CommonMixin, Base):
    """t_role 角色（各校独立；DDL 细节以 11 中心 §11.6 为准，此处为第一批骨架）。"""
    __tablename__ = "t_role"
    __table_args__ = (UniqueConstraint("tenant_id", "role_code", name="uk_tenant_role_code"),)

    role_code: Mapped[str] = mapped_column(String(50), nullable=False, comment="如 COUNSELOR/COLLEGE_ADMIN")
    role_name: Mapped[str] = mapped_column(String(100), nullable=False)
    role_type: Mapped[str | None] = mapped_column(String(50), comment="SYSTEM/CUSTOM，TODO 以 11 中心为准")
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="ACTIVE")
    remark: Mapped[str | None] = mapped_column(String(500))


class Permission(PKMixin, Base):
    """t_permission 权限点——跨租户系统级定义（无 tenant_id，§4.3）。append 语义弱，仍保留创建时间。"""
    __tablename__ = "t_permission"
    __table_args__ = (UniqueConstraint("permission_code", name="uk_permission_code"),)

    permission_code: Mapped[str] = mapped_column(String(200), nullable=False,
                                                 comment="模块:资源:动作，如 student:profile:export")
    permission_name: Mapped[str] = mapped_column(String(200), nullable=False)
    module_code: Mapped[str | None] = mapped_column(String(50))
    action: Mapped[str | None] = mapped_column(String(50), comment="17 个动作枚举之一（§4.3）")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)


class UserRole(PKMixin, TenantMixin, CommonMixin, Base):
    """t_user_role 用户-角色（§4.3）。"""
    __tablename__ = "t_user_role"
    __table_args__ = (UniqueConstraint("tenant_id", "user_id", "role_id", name="uk_user_role"),)

    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    role_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="ACTIVE")


class RolePermission(PKMixin, TenantMixin, CommonMixin, Base):
    """t_role_permission 角色-权限（§4.3）。"""
    __tablename__ = "t_role_permission"
    __table_args__ = (UniqueConstraint("tenant_id", "role_id", "permission_id", name="uk_role_permission"),)

    role_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    permission_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="ACTIVE")
