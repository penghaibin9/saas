"""PLAT-12 备份恢复验证与灾备。

只做"证据元数据"（M-PLAT-09），不重新实现备份/恢复本身——真正执行备份的
工具（mysqldump、云厂商托管备份、COS 同步）属于部署环境，本仓库不自带、
本地开发环境也没装。这两张表只记录"什么时候、用什么方式、备份/演练了
什么、结果如何"，由：①运维手动登记（比如云数据库自带的自动备份）、
②本卡自带的只读 schema 完整性自检（真实可跑，不需要外部工具）两种方式
写入证据。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, BigInteger, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CommonMixin, PKMixin


class BackupEvidence(PKMixin, CommonMixin, Base):
    """t_backup_evidence 备份证据记录。"""
    __tablename__ = "t_backup_evidence"

    backup_type: Mapped[str] = mapped_column(
        String(30), nullable=False, index=True,
        comment="DATABASE_DUMP/SCHEMA_INTEGRITY/FILE_STORAGE_SYNC/CLOUD_MANAGED")
    method: Mapped[str] = mapped_column(
        String(30), nullable=False, comment="MYSQLDUMP/SCHEMA_INSPECT/MANUAL_CONFIRMED/CLOUD_MANAGED")
    status: Mapped[str] = mapped_column(String(20), nullable=False, index=True, comment="SUCCEEDED/FAILED")
    location_ref: Mapped[str | None] = mapped_column(String(500), comment="备份存放位置/云厂商备份ID，人工登记时填")
    size_bytes: Mapped[int | None] = mapped_column(BigInteger)
    checksum_sha256: Mapped[str | None] = mapped_column(String(64))
    table_count: Mapped[int | None] = mapped_column(BigInteger)
    detail_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    error_message: Mapped[str | None] = mapped_column(String(1000))
    captured_by: Mapped[int | None] = mapped_column(BigInteger)
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime)


class RestoreDrill(PKMixin, CommonMixin, Base):
    """t_restore_drill 恢复演练证据记录。"""
    __tablename__ = "t_restore_drill"

    backup_evidence_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    drill_type: Mapped[str] = mapped_column(
        String(30), nullable=False, comment="SCHEMA_REBUILD_CHECK/DATA_ROW_COUNT_COMPARE/MANUAL_CONFIRMED")
    status: Mapped[str] = mapped_column(String(20), nullable=False, index=True, comment="PASSED/FAILED")
    target_description: Mapped[str | None] = mapped_column(String(300))
    detail_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    performed_by: Mapped[int | None] = mapped_column(BigInteger)
    performed_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
