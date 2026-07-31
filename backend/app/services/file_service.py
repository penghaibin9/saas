"""统一文件服务权威 facade。

旧实现原样保存在 ``file_service_legacy``；本模块重新导出全部兼容符号，并只在
普通流式上传与系统字节文件两个物理写入入口建立业务模块配额作用域。不是运行时
monkey-patch，所有调用方继续导入同一个 ``app.services.file_service`` 合同。
"""
from __future__ import annotations

from app.services import file_service_legacy as _legacy
from app.services.file_storage_write_context import storage_write_scope

# 完整保留历史公开与私有兼容符号，避免生成文件、扫描和旧业务适配器断链。
for _name, _value in vars(_legacy).items():
    if _name not in {"__name__", "__loader__", "__package__", "__spec__"}:
        globals()[_name] = _value

_legacy_store_upload = _legacy.store_upload
_legacy_store_bytes = _legacy.store_bytes


async def store_upload(
    file,
    biz_type: str = "ATTACHMENT",
    *,
    biz_id: str | None = None,
    user: dict | None = None,
    visibility: str = "BIZ_SCOPED",
    security_level: str = "NORMAL",
) -> dict:
    """普通上传在物理 persist 前绑定业务模块配额上下文。"""
    with storage_write_scope(biz_type):
        return await _legacy_store_upload(
            file,
            biz_type,
            biz_id=biz_id,
            user=user,
            visibility=visibility,
            security_level=security_level,
        )


def store_bytes(
    data: bytes,
    filename: str,
    biz_type: str = "ATTACHMENT",
    mime_type: str | None = None,
    *,
    biz_id: str | None = None,
    user: dict | None = None,
    visibility: str = "PRIVATE",
    security_level: str = "NORMAL",
    db=None,
) -> dict:
    """系统字节文件在物理 persist 前绑定业务模块配额上下文。"""
    with storage_write_scope(biz_type):
        return _legacy_store_bytes(
            data,
            filename,
            biz_type,
            mime_type,
            biz_id=biz_id,
            user=user,
            visibility=visibility,
            security_level=security_level,
            db=db,
        )
