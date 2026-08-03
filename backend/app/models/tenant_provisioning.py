"""PLAT-04 租户自动开通、初始化与上线验收。

平台级实体（开通发生在租户尚不存在或刚存在的阶段，不能挂在业务租户下），
不经过 _tid()。开通的具体动作复用 platform_service.py 已有的、经过验证的
函数（Tenant+TenantBrandConfig+TENANT_META 创建、ensure_builtin_roles、
create_school_admin）；本文件只是给这些真实动作加一层"任务+步骤"track，
不重新发明开通业务逻辑本身。
"""
from __future__ import annotations

from sqlalchemy import JSON, BigInteger, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CommonMixin, PKMixin


class ProvisioningJob(PKMixin, CommonMixin, Base):
    """t_provisioning_job 一次"新校开通"任务。"""
    __tablename__ = "t_provisioning_job"
    __table_args__ = (UniqueConstraint("idempotency_key", name="uk_provisioning_job_idempotency"),)

    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    tenant_code: Mapped[str] = mapped_column(String(64), nullable=False)
    tenant_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    input_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="PENDING", index=True,
        comment="PENDING/RUNNING/WAITING_INPUT/SUCCEEDED/FAILED/COMPENSATING/CANCELLED")
    current_step: Mapped[str | None] = mapped_column(String(40))
    last_error: Mapped[str | None] = mapped_column(String(1000))
    requested_by: Mapped[int | None] = mapped_column(BigInteger)


class ProvisioningStepRun(PKMixin, CommonMixin, Base):
    """t_provisioning_step_run 任务下每一步的执行记录（幂等键+尝试次数+补偿状态）。"""
    __tablename__ = "t_provisioning_step_run"
    __table_args__ = (UniqueConstraint("job_id", "step_code", name="uk_provisioning_step_scope"),)

    job_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    step_code: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(
        String(24), nullable=False, default="PENDING",
        comment="PENDING/RUNNING/SUCCEEDED/FAILED/COMPENSATING/COMPENSATED/NEEDS_MANUAL_REVIEW")
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    output_summary_json: Mapped[dict | None] = mapped_column(JSON)
    error_message: Mapped[str | None] = mapped_column(String(1000))
    trace_id: Mapped[str | None] = mapped_column(String(80))
