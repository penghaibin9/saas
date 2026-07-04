"""
ORM 基类与公共字段（冻结册 §1.1/§1.2）
────────────────────────────────────────────────────────────
- 表名统一 t_ 前缀蛇形；主键 id BIGINT（应用层雪花/发号器，TODO：接入发号器，测试环境暂用自增兼容 SQLite）。
- 业务表公共字段：tenant_id/created_at/updated_at/created_by/updated_by/is_deleted/version(/status 由各表定义)。
- 审计/日志/流水表 append-only：无 is_deleted / updated_at / updated_by / version。
- 敏感字段一律 *_encrypted（密文）+ *_hash（不可逆匹配），库中不存明文（冻结册 §17.2）。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Integer
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class PKMixin:
    # TODO(冻结册 §1.1)：生产由应用层雪花/发号器赋值；autoincrement 仅为 SQLite 测试兼容
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)


class TenantMixin:
    tenant_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True, comment="租户(学校)ID，行级隔离")


class AuditTimeMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    created_by: Mapped[int | None] = mapped_column(BigInteger, nullable=True)


class CommonMixin(AuditTimeMixin):
    """业务表公共字段（冻结册 §1.2）。"""
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    updated_by: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, comment="逻辑删除")
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="乐观锁")
