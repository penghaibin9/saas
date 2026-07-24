"""t_file_object 文件对象。业务表只存 file_id；本表存 key/hash/size 与对象级归属。"""
from __future__ import annotations

from sqlalchemy import BigInteger, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CommonMixin, PKMixin, TenantMixin


class FileObject(PKMixin, TenantMixin, CommonMixin, Base):
    """t_file_object。created_by 来自 CommonMixin；另存 owner_user_id/biz 绑定做对象级授权。"""
    __tablename__ = "t_file_object"

    file_key: Mapped[str] = mapped_column(String(500), nullable=False, comment="存储 key（本地相对路径 / 对象存储 key）")
    file_name: Mapped[str] = mapped_column(String(300), nullable=False, comment="原始文件名")
    ext: Mapped[str | None] = mapped_column(String(20))
    mime_type: Mapped[str | None] = mapped_column(String(100))
    size_bytes: Mapped[int | None] = mapped_column(BigInteger)
    sha256: Mapped[str | None] = mapped_column(String(64), index=True)
    biz_type: Mapped[str | None] = mapped_column(String(50), comment="用途：IMPORT/EXPORT/ATTACHMENT/LEAVE/...")
    biz_id: Mapped[str | None] = mapped_column(String(64), index=True, comment="业务对象 ID（字符串兼容雪花/UUID）")
    owner_user_id: Mapped[int | None] = mapped_column(BigInteger, index=True, comment="上传者用户 ID")
    visibility: Mapped[str] = mapped_column(
        String(30), nullable=False, default="PRIVATE",
        comment="PRIVATE/BIZ_SCOPED/STUDENT_SELF — 历史空归属默认 PRIVATE，不对普通用户开放")
    security_level: Mapped[str] = mapped_column(
        String(30), nullable=False, default="NORMAL",
        comment="NORMAL/SENSITIVE — 敏感附件需业务权限，禁止同租户猜 ID")
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, default="AVAILABLE",
        comment="UPLOADING/QUARANTINED/AVAILABLE/REJECTED/DELETED；历史 STORED 视同 AVAILABLE")
    remark: Mapped[str | None] = mapped_column(String(500))
