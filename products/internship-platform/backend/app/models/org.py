"""组织架构（冻结册 §4.6 表卡：t_college / t_major / t_class）。
冻结册无 t_org / t_menu 表：组织=三级实体表；菜单由 RBAC 配置推导，不建表（TODO 若后续冻结新增再补）。"""
from __future__ import annotations

from sqlalchemy import BigInteger, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CommonMixin, PKMixin, TenantMixin


class College(PKMixin, TenantMixin, CommonMixin, Base):
    """t_college 学院（二级学院）。

    13B-R3 学院专业班级补列（融合设计 §加列表 / 学院专业班级施工卡）：
    short_name 简称 / sort_order 展示排序 / secretary_id 教学秘书 user_id（orgs 教学秘书绑定）。
    """
    __tablename__ = "t_college"

    college_name: Mapped[str] = mapped_column(String(200), nullable=False)
    code: Mapped[str | None] = mapped_column(String(50))
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="ACTIVE")
    remark: Mapped[str | None] = mapped_column(String(500))
    # ── 13B-R3 学院专业班级 ──
    short_name: Mapped[str | None] = mapped_column(String(100), comment="学院简称")
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="展示排序（升序）")
    secretary_id: Mapped[int | None] = mapped_column(BigInteger, comment="教学秘书 user_id（orgs 教学秘书绑定）")


class Major(PKMixin, TenantMixin, CommonMixin, Base):
    """t_major 专业目录。

    13B-R3 补列（融合设计 §加列表）：education_years 学制(默 3) / training_level 培养层次 /
    enroll_status 招生状态（ENROLLING 招生中 / STOPPED 停招）/ direction 专业方向。
    """
    __tablename__ = "t_major"

    college_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    major_name: Mapped[str] = mapped_column(String(200), nullable=False)
    code: Mapped[str | None] = mapped_column(String(50))
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="ACTIVE")
    remark: Mapped[str | None] = mapped_column(String(500))
    # ── 13B-R3 学院专业班级 ──
    education_years: Mapped[int] = mapped_column(Integer, nullable=False, default=3, comment="学制（年），默认3")
    training_level: Mapped[str | None] = mapped_column(String(50), comment="培养层次 SECONDARY/HIGHER/FIVE_YEAR 等")
    enroll_status: Mapped[str] = mapped_column(String(50), nullable=False, default="ENROLLING",
                                               comment="招生状态 ENROLLING 招生中 / STOPPED 停招")
    direction: Mapped[str | None] = mapped_column(String(200), comment="专业方向（可空）")


class SchoolClass(PKMixin, TenantMixin, CommonMixin, Base):
    """t_class 行政班。

    13B-R3 补列（融合设计 §加列表）：class_code 班级编号 / capacity 编制人数 /
    graduate_year 应毕业年份 / class_status（NORMAL 在读 / GRADUATED 已毕业 / DISBANDED 已解散）。
    """
    __tablename__ = "t_class"

    major_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    class_name: Mapped[str] = mapped_column(String(200), nullable=False)
    grade: Mapped[str | None] = mapped_column(String(20), comment="年级，如 2024")
    counselor_id: Mapped[int | None] = mapped_column(BigInteger, comment="辅导员 user_id")
    head_teacher_id: Mapped[int | None] = mapped_column(BigInteger, comment="班主任 user_id")
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="ACTIVE")
    remark: Mapped[str | None] = mapped_column(String(500))
    # ── 13B-R3 学院专业班级 ──
    class_code: Mapped[str | None] = mapped_column(String(50), comment="班级编号")
    capacity: Mapped[int | None] = mapped_column(Integer, comment="编制人数（教学任务班级容量校验）")
    graduate_year: Mapped[str | None] = mapped_column(String(20), comment="应毕业年份，如 2027")
    class_status: Mapped[str] = mapped_column(String(50), nullable=False, default="NORMAL",
                                              comment="班级状态 NORMAL 在读 / GRADUATED 已毕业 / DISBANDED 已解散")
