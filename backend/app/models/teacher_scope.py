"""教师数据范围映射（teacher_student_scope 最小可用版）。
────────────────────────────────────────────────────────────
一行 = 一条「教师 → 数据范围」授权：
- scope_type=CLASS    → ref_value 存班级名（辅导员/就业老师按班级）
- scope_type=COLLEGE  → ref_value 存学院名（学院管理员/就业老师按学院）
- scope_type=STUDENT  → ref_value 存学号（点名授权个别学生）
- scope_type=ADVISOR  → 按各域表 advisor_name == 教师姓名 收敛（毕设/实习导师，
                        不需要行数据，登记一行仅作声明）
teacher_key 优先用登录名（mock：counselor01 / db：login_name），姓名兜底。
无任何行 → 该教师回落 TENANT_FALLBACK（仅租户隔离，标准版应逐步清零）。
"""
from __future__ import annotations

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CommonMixin, PKMixin, TenantMixin


class TeacherStudentScope(Base, PKMixin, TenantMixin, CommonMixin):
    __tablename__ = "t_teacher_student_scope"

    teacher_key: Mapped[str] = mapped_column(String(64), nullable=False, index=True,
                                             comment="教师标识：登录名或 userId")
    teacher_name: Mapped[str | None] = mapped_column(String(64), nullable=True, comment="教师姓名（冗余，便于排查）")
    role_code: Mapped[str | None] = mapped_column(String(32), nullable=True, comment="生效角色（COUNSELOR/GD_MENTOR/...）；空=全部角色")
    scope_type: Mapped[str] = mapped_column(String(16), nullable=False, comment="CLASS/COLLEGE/STUDENT/ADVISOR")
    ref_value: Mapped[str | None] = mapped_column(String(128), nullable=True, comment="班级名/学院名/学号；ADVISOR 可空")
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="ACTIVE")
