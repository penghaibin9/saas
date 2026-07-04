"""文件对象（冻结册 §1.3 / t_file_object 表卡）：业务表只存 file_id，本表存 key/hash/size/mime。"""
from __future__ import annotations

from sqlalchemy import BigInteger, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CommonMixin, PKMixin, TenantMixin


class FileObject(PKMixin, TenantMixin, CommonMixin, Base):
    """t_file_object 文件对象。当前存本地 UPLOAD_DIR；接 MinIO/OSS 时 file_key 语义不变。"""
    __tablename__ = "t_file_object"

    file_key: Mapped[str] = mapped_column(String(500), nullable=False, comment="存储 key（本地相对路径 / 对象存储 key）")
    file_name: Mapped[str] = mapped_column(String(300), nullable=False, comment="原始文件名")
    ext: Mapped[str | None] = mapped_column(String(20))
    mime_type: Mapped[str | None] = mapped_column(String(100))
    size_bytes: Mapped[int | None] = mapped_column(BigInteger)
    sha256: Mapped[str | None] = mapped_column(String(64), index=True)
    biz_type: Mapped[str | None] = mapped_column(String(50), comment="用途：IMPORT/EXPORT/ATTACHMENT/...")
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="STORED", comment="STORED/DELETED")
    remark: Mapped[str | None] = mapped_column(String(500))
