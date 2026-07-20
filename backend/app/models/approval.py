"""审批与待办（冻结册 §2 模块13/14：t_unified_todo、t_workflow_instance/t_workflow_task；DDL 细节见 11 中心 §11.13–11.18）。"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, BigInteger, Boolean, DateTime, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CommonMixin, PKMixin, TenantMixin


class WorkflowInstance(PKMixin, TenantMixin, CommonMixin, Base):
    """t_workflow_instance 审批实例（横切公共表：source_module + source_biz_type + source_biz_id）。"""
    __tablename__ = "t_workflow_instance"

    workflow_code: Mapped[str] = mapped_column(String(100), nullable=False, comment="流程编码")
    source_module: Mapped[str] = mapped_column(String(50), nullable=False, comment="来源模块（student/gd/intern/...）")
    source_biz_type: Mapped[str] = mapped_column(String(100), nullable=False)
    source_biz_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    applicant_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True, comment="申请人 user_id")
    title: Mapped[str | None] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="RUNNING",
                                        comment="RUNNING/APPROVED/REJECTED/RETURNED/CANCELLED（TODO 以 11 中心为准）")
    current_node: Mapped[str | None] = mapped_column(String(100))
    remark: Mapped[str | None] = mapped_column(String(500))


class WorkflowTask(PKMixin, TenantMixin, CommonMixin, Base):
    """t_workflow_task 审批任务（待我审批的最小单元）。"""
    __tablename__ = "t_workflow_task"

    instance_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    node_code: Mapped[str | None] = mapped_column(String(100))
    assignee_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True, comment="审批人 user_id")
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="PENDING",
                                        comment="PENDING/APPROVED/REJECTED/TRANSFERRED/CANCELLED")
    action_reason: Mapped[str | None] = mapped_column(String(500), comment="驳回/退回原因（≥5 字，§1.4）")
    acted_at: Mapped[datetime | None] = mapped_column(DateTime)
    deadline_at: Mapped[datetime | None] = mapped_column(DateTime)
    remark: Mapped[str | None] = mapped_column(String(500))


class UnifiedTodo(PKMixin, TenantMixin, CommonMixin, Base):
    """t_unified_todo 统一待办（单表，全模块统一生成；去重键见冻结册 §11 模块13）。"""
    __tablename__ = "t_unified_todo"
    __table_args__ = (
        UniqueConstraint("tenant_id", "source_module", "source_biz_id", "todo_type", "assignee_id",
                         name="uk_todo_dedup"),
        Index("ix_todo_tenant_student_status_id", "tenant_id", "student_id", "is_deleted", "status", "id"),
        Index("ix_todo_tenant_assignee_status_id", "tenant_id", "assignee_id", "is_deleted", "status", "id"),
    )

    source_module: Mapped[str] = mapped_column(String(50), nullable=False)
    source_biz_type: Mapped[str | None] = mapped_column(String(100))
    source_biz_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    todo_type: Mapped[str] = mapped_column(String(100), nullable=False)
    assignee_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    student_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="PENDING",
                                        comment="PENDING/DONE/CANCELLED")
    due_at: Mapped[datetime | None] = mapped_column(DateTime)
    remark: Mapped[str | None] = mapped_column(String(500))


class WorkflowDefinition(PKMixin, TenantMixin, CommonMixin, Base):
    """租户级流程定义主表；运行实例通过 workflow_code 引用。"""
    __tablename__ = "t_workflow_definition"
    __table_args__ = (UniqueConstraint("tenant_id", "workflow_code", name="uk_workflow_definition_code"),)

    workflow_code: Mapped[str] = mapped_column(String(100), nullable=False)
    workflow_name: Mapped[str] = mapped_column(String(200), nullable=False)
    source_module: Mapped[str] = mapped_column(String(60), nullable=False)
    source_biz_type: Mapped[str] = mapped_column(String(100), nullable=False)
    definition_version: Mapped[str] = mapped_column(String(30), nullable=False, default="2026.1")
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="PENDING_CONFIRMATION", index=True,
                                        comment="PENDING_CONFIRMATION/ENABLED/DISABLED")
    policy_confirmed: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="0")
    policy_confirmed_by: Mapped[int | None] = mapped_column(BigInteger)
    policy_confirmed_at: Mapped[datetime | None] = mapped_column(DateTime)
    timeout_hours: Mapped[int] = mapped_column(Integer, nullable=False, default=48)
    allow_transfer: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    allow_reject: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    allow_withdraw: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    starter_role_codes_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    cc_role_codes_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    policy_snapshot_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    source_profile: Mapped[str] = mapped_column(String(50), nullable=False)
    installed_project_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(String(500))


class WorkflowNodeDefinition(PKMixin, TenantMixin, CommonMixin, Base):
    """流程节点定义；责任角色是稳定角色编码，不写死具体人员。"""
    __tablename__ = "t_workflow_node_definition"
    __table_args__ = (UniqueConstraint("tenant_id", "workflow_definition_id", "node_code",
                                      name="uk_workflow_node_definition_code"),)

    workflow_definition_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    node_code: Mapped[str] = mapped_column(String(100), nullable=False)
    node_name: Mapped[str] = mapped_column(String(150), nullable=False)
    sequence_no: Mapped[int] = mapped_column(Integer, nullable=False)
    approver_role_code: Mapped[str] = mapped_column(String(50), nullable=False)
    assignee_strategy: Mapped[str] = mapped_column(String(40), nullable=False, default="ROLE_AND_SCOPE")
    data_scope_code: Mapped[str] = mapped_column(String(40), nullable=False, default="ASSIGNED")
    timeout_hours: Mapped[int] = mapped_column(Integer, nullable=False, default=48)
    condition_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="ACTIVE")
