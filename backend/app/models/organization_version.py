"""SYS-04 组织变更版本与教职工任职（V6 控制面）。

两个设计决定，都基于当前仓库事实
────────────────────────────────
1. **不把组织重建成通用节点表。** 现有组织是三张实体表（``t_college`` / ``t_major`` /
   ``t_class``），全系统按 ``college_id`` / ``major_id`` / ``class_id`` 引用。改成通用
   节点表等于重写整个系统的外键，风险远大于收益。这里的"组织版本"因此是**计划中的
   变更集**：草稿期只记录"打算怎么改"，激活时才落到三张实体表上。未激活的版本对当前
   查询零影响，天然满足"未来版本生效前不影响当前"。

2. **任职必须成为真表。** 当前 ``/system/staff-affiliations`` 是从
   ``SchoolClass.counselor_id`` / ``head_teacher_id`` / ``College.secretary_id`` 和
   ``TeacherStudentScope`` 临时投影拼出来的只读列表，没有起止时间、没有主任职、没有
   来源，因此"任职到期自动失效"根本无从谈起。``t_staff_assignment`` 补上这层事实，
   并把既有投影回填为 ``source_type=PROJECTED``，保留双读对账窗口。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import (JSON, BigInteger, Boolean, DateTime, Index, String,
                        UniqueConstraint)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CommonMixin, PKMixin, TenantMixin

# 组织版本状态机
ORG_VERSION_DRAFT = "DRAFT"
ORG_VERSION_VALIDATED = "VALIDATED"
ORG_VERSION_SCHEDULED = "SCHEDULED"
ORG_VERSION_ACTIVATED = "ACTIVATED"
ORG_VERSION_ROLLED_BACK = "ROLLED_BACK"

ORG_VERSION_STATUSES = (
    ORG_VERSION_DRAFT,
    ORG_VERSION_VALIDATED,
    ORG_VERSION_SCHEDULED,
    ORG_VERSION_ACTIVATED,
    ORG_VERSION_ROLLED_BACK,
)

# 变更类型
ORG_CHANGE_CREATE = "CREATE"
ORG_CHANGE_RENAME = "RENAME"
ORG_CHANGE_MOVE = "MOVE"
ORG_CHANGE_DISABLE = "DISABLE"
ORG_CHANGE_ENABLE = "ENABLE"
ORG_CHANGE_TYPES = (
    ORG_CHANGE_CREATE,
    ORG_CHANGE_RENAME,
    ORG_CHANGE_MOVE,
    ORG_CHANGE_DISABLE,
    ORG_CHANGE_ENABLE,
)

# 组织类型：与现有三张实体表一一对应，不引入第四种存储
ORG_TYPE_COLLEGE = "COLLEGE"
ORG_TYPE_MAJOR = "MAJOR"
ORG_TYPE_CLASS = "CLASS"
ORG_TYPES = (ORG_TYPE_COLLEGE, ORG_TYPE_MAJOR, ORG_TYPE_CLASS)

# 任职类型：前三种与既有投影字段对应，其余供学校自定义岗位使用
ASSIGNMENT_COUNSELOR = "COUNSELOR"
ASSIGNMENT_HEAD_TEACHER = "HEAD_TEACHER"
ASSIGNMENT_SECRETARY = "SECRETARY"
ASSIGNMENT_LEADER = "LEADER"
ASSIGNMENT_OTHER = "OTHER"
ASSIGNMENT_TYPES = (
    ASSIGNMENT_COUNSELOR,
    ASSIGNMENT_HEAD_TEACHER,
    ASSIGNMENT_SECRETARY,
    ASSIGNMENT_LEADER,
    ASSIGNMENT_OTHER,
)

ASSIGNMENT_SOURCE_MANUAL = "MANUAL"
ASSIGNMENT_SOURCE_PROJECTED = "PROJECTED"  # 由既有 counselor_id 等字段回填
ASSIGNMENT_SOURCE_IMPORT = "IMPORT"

ASSIGNMENT_STATUS_ACTIVE = "ACTIVE"
ASSIGNMENT_STATUS_EXPIRED = "EXPIRED"
ASSIGNMENT_STATUS_REVOKED = "REVOKED"


class OrgVersion(PKMixin, TenantMixin, CommonMixin, Base):
    """一次组织调整（可排期到未来生效）。"""

    __tablename__ = "t_org_version"

    version_code: Mapped[str] = mapped_column(String(64), nullable=False)
    version_name: Mapped[str | None] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(24), nullable=False, default=ORG_VERSION_DRAFT, index=True)
    effective_at: Mapped[datetime | None] = mapped_column(DateTime, comment="计划生效时间（UTC）")
    activated_at: Mapped[datetime | None] = mapped_column(DateTime)
    rolled_back_at: Mapped[datetime | None] = mapped_column(DateTime)
    reason: Mapped[str | None] = mapped_column(String(1000))
    impact_json: Mapped[dict | None] = mapped_column(JSON, comment="激活前算出的影响面快照")

    __table_args__ = (
        UniqueConstraint("tenant_id", "version_code", name="uk_org_version_code"),
        Index("idx_org_version_status_effective", "tenant_id", "status", "effective_at"),
    )


class OrgVersionItem(PKMixin, TenantMixin, CommonMixin, Base):
    """版本内的一条具体变更。``before_json`` 在激活时写入，供回滚使用。"""

    __tablename__ = "t_org_version_item"

    version_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    change_type: Mapped[str] = mapped_column(String(24), nullable=False)
    org_type: Mapped[str] = mapped_column(String(24), nullable=False)
    org_node_id: Mapped[int | None] = mapped_column(BigInteger, comment="CREATE 时为空，激活后回填新建 id")
    payload_json: Mapped[dict] = mapped_column(JSON, nullable=False, comment="目标值：名称、父节点等")
    before_json: Mapped[dict | None] = mapped_column(JSON, comment="激活时快照，回滚依据")
    applied_at: Mapped[datetime | None] = mapped_column(DateTime)

    __table_args__ = (
        Index("idx_org_version_item_version", "tenant_id", "version_id"),
        Index("idx_org_version_item_node", "tenant_id", "org_type", "org_node_id"),
    )


class StaffAssignment(PKMixin, TenantMixin, CommonMixin, Base):
    """教职工任职：谁、在哪个组织、担任什么、从何时到何时、来源是什么。"""

    __tablename__ = "t_staff_assignment"

    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    org_type: Mapped[str] = mapped_column(String(24), nullable=False)
    org_node_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    assignment_type: Mapped[str] = mapped_column(String(32), nullable=False)
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, comment="主任职")
    source_type: Mapped[str] = mapped_column(String(24), nullable=False, default=ASSIGNMENT_SOURCE_MANUAL)
    source_id: Mapped[str | None] = mapped_column(String(128))
    effective_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, comment="空表示长期有效")
    status: Mapped[str] = mapped_column(String(24), nullable=False, default=ASSIGNMENT_STATUS_ACTIVE, index=True)
    reason: Mapped[str | None] = mapped_column(String(1000))

    __table_args__ = (
        # 同一人在同一组织的同一岗位，同一生效时间点只能有一条，避免重复任命
        UniqueConstraint(
            "tenant_id", "user_id", "org_type", "org_node_id", "assignment_type", "effective_at",
            name="uk_staff_assignment",
        ),
        Index("idx_assignment_user_effective", "tenant_id", "user_id", "status", "effective_at"),
        Index("idx_assignment_org_effective", "tenant_id", "org_type", "org_node_id", "status", "effective_at"),
    )
