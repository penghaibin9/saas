"""组织架构（冻结册 §4.6 表卡：t_college / t_major / t_class）。
冻结册无 t_org / t_menu 表：组织=三级实体表；菜单由 RBAC 配置推导，不建表（TODO 若后续冻结新增再补）。"""
from __future__ import annotations

from sqlalchemy import BigInteger, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CommonMixin, PKMixin, TenantMixin


class College(PKMixin, TenantMixin, CommonMixin, Base):
    """t_college 学院（二级学院）。TODO：更多字段以 01 中心深化文档为准。"""
    __tablename__ = "t_college"

    college_name: Mapped[str] = mapped_column(String(200), nullable=False)
    code: Mapped[str | None] = mapped_column(String(50))
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="ACTIVE")
    remark: Mapped[str | None] = mapped_column(String(500))


class Major(PKMixin, TenantMixin, CommonMixin, Base):
    """t_major 专业目录。"""
    __tablename__ = "t_major"

    college_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    major_name: Mapped[str] = mapped_column(String(200), nullable=False)
    code: Mapped[str | None] = mapped_column(String(50))
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="ACTIVE")
    remark: Mapped[str | None] = mapped_column(String(500))


class SchoolClass(PKMixin, TenantMixin, CommonMixin, Base):
    """t_class 行政班。"""
    __tablename__ = "t_class"

    major_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    class_name: Mapped[str] = mapped_column(String(200), nullable=False)
    grade: Mapped[str | None] = mapped_column(String(20), comment="年级，如 2024")
    counselor_id: Mapped[int | None] = mapped_column(BigInteger, comment="辅导员 user_id")
    head_teacher_id: Mapped[int | None] = mapped_column(BigInteger, comment="班主任 user_id")
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="ACTIVE")
    remark: Mapped[str | None] = mapped_column(String(500))
