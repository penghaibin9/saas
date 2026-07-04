"""审批与待办（冻结册 §2 模块13/14：t_unified_todo、t_workflow_instance/t_workflow_task；DDL 细节见 11 中心 §11.13–11.18）。"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, String, UniqueConstraint
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
    __table_args__ = (UniqueConstraint("tenant_id", "source_module", "source_biz_id", "todo_type", "assignee_id",
                                       name="uk_todo_dedup"),)

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
