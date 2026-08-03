"""SYS-14：流程节点动作安全策略与版本变更策略。

真实缺口先说清楚
──────────────────
真实审批执行链路（``db_service.act_task`` / ``_can_manage_all_approvals``）里，
任何持有通配页面权限 ``approval.manage`` 或 ``*`` 的账号可以代批**任意流程任意节点**，
不管该节点的责任角色是谁——"页面权限" 和 "流程动作权限" 在代码里其实是同一个判断。
本卡把它们拆开：一条 ``t_workflow_action_policy`` 的 NODE_ACTION 行**一旦激活**，
就把该节点（或整条流程）的"通配旁路"关掉，只放行两类人：真正的 assignee，
或者额外持有该策略指定的 ``action_permission_code`` 的人。没有激活策略时，
行为跟以前完全一样（不激活 = 不改变现状，向后兼容）。

VERSION_STRATEGY 行（node_code 为空字符串占位）管的是另一件事：流程定义被改动、
且该流程还有 RUNNING 中的实例时怎么办——SNAPSHOT 直接拒绝改动，逼一次人工决定；
MIGRATE 允许改但必须留痕受影响实例数；不设策略（DYNAMIC，默认）保持现状：
运行中实例读的是当前最新节点配置。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, BigInteger, DateTime, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CommonMixin, PKMixin, TenantMixin

POLICY_NODE_ACTION = "NODE_ACTION"
POLICY_VERSION_STRATEGY = "VERSION_STRATEGY"
POLICY_TYPES = (POLICY_NODE_ACTION, POLICY_VERSION_STRATEGY)

STATUS_DRAFT = "DRAFT"
STATUS_PENDING_REVIEW = "PENDING_REVIEW"
STATUS_ACTIVE = "ACTIVE"
STATUS_RETIRED = "RETIRED"

STRATEGY_DYNAMIC = "DYNAMIC"
STRATEGY_SNAPSHOT = "SNAPSHOT"
STRATEGY_MIGRATE = "MIGRATE"
VERSION_STRATEGIES = (STRATEGY_DYNAMIC, STRATEGY_SNAPSHOT, STRATEGY_MIGRATE)

# node_code 为空字符串表示"整条流程级"（VERSION_STRATEGY 恒用这个；NODE_ACTION 也可以用它表示全节点通用策略）
WORKFLOW_LEVEL_NODE = ""


class WorkflowActionPolicy(PKMixin, TenantMixin, CommonMixin, Base):
    """一行 = 一条策略。同 (workflow_code, node_code, policy_type) 只允许一条生效中的记录。"""

    __tablename__ = "t_workflow_action_policy"

    workflow_code: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    node_code: Mapped[str] = mapped_column(String(100), nullable=False, default=WORKFLOW_LEVEL_NODE)
    policy_type: Mapped[str] = mapped_column(String(24), nullable=False, default=POLICY_NODE_ACTION)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=STATUS_DRAFT)
    # NODE_ACTION 专用：持有此权限码才能越过 assignee 限制代批该节点
    action_permission_code: Mapped[str | None] = mapped_column(String(160))
    # VERSION_STRATEGY 专用：流程定义变更时，在途 RUNNING 实例怎么处理
    version_strategy: Mapped[str] = mapped_column(String(16), nullable=False, default=STRATEGY_DYNAMIC)
    reason: Mapped[str | None] = mapped_column(String(500))
    submitted_by: Mapped[int | None] = mapped_column(BigInteger)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime)
    reviewed_by: Mapped[int | None] = mapped_column(BigInteger)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime)
    retired_by: Mapped[int | None] = mapped_column(BigInteger)
    retired_at: Mapped[datetime | None] = mapped_column(DateTime)

    __table_args__ = (
        UniqueConstraint("tenant_id", "workflow_code", "node_code", "policy_type",
                         name="uk_workflow_action_policy_scope"),
        Index("idx_workflow_action_policy_lookup", "tenant_id", "workflow_code", "status"),
    )


class WorkflowVersionMigrationEvent(PKMixin, TenantMixin, CommonMixin, Base):
    """MIGRATE 策略每次真实生效时留痕：改了什么、影响了多少条在途实例。append-only 审计。"""

    __tablename__ = "t_workflow_version_migration_event"

    workflow_code: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    from_definition_version: Mapped[str | None] = mapped_column(String(30))
    to_definition_version: Mapped[str | None] = mapped_column(String(30))
    affected_instance_count: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    affected_instance_ids_json: Mapped[list | None] = mapped_column(JSON)
    reason: Mapped[str | None] = mapped_column(String(500))

    __table_args__ = (
        Index("idx_workflow_version_migration_lookup", "tenant_id", "workflow_code", "created_at"),
    )
