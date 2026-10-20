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


def _authorized_attachment_metadata(file_id: str) -> dict | None:
    """读取附件展示元数据，并由统一 File Center resolver 计算真实可执行能力。"""
    from app.core.context import current_tenant_id, get_current_user_ctx
    from app.db.session import db_enabled, get_sessionmaker

    actor = get_current_user_ctx() or {}
    normalized_id = str(file_id or "").strip()
    if not normalized_id:
        return None

    if db_enabled() and normalized_id.isdigit():
        from sqlalchemy import select

        from app.models.file import FileBinding, FileObject
        from app.services import file_access_resolvers as _file_access_resolvers  # noqa: F401
        from app.services.file_access_service import authorize_file_object, file_view
        from app.services.file_scan_service import assert_file_ready_for_business

        tenant_id = int(current_tenant_id() or 0)
        if not tenant_id:
            return None
        db = get_sessionmaker()()
        try:
            file_obj = db.scalars(select(FileObject).where(
                FileObject.id == int(normalized_id),
                FileObject.tenant_id == tenant_id,
                FileObject.is_deleted.is_(False),
            )).first()
            if not file_obj:
                return None
            bindings = list(db.scalars(select(FileBinding).where(
                FileBinding.tenant_id == tenant_id,
                FileBinding.file_id == int(normalized_id),
                FileBinding.is_deleted.is_(False),
            )).all())
            if not authorize_file_object(file_obj, bindings, actor, "meta", db=db):
                return None
            view = file_view(file_obj, user=actor, bindings=bindings, db=db)
            if not view.get("readyForBusiness"):
                # Preserve legacy attachment_view semantics: business attachments are not
                # exposed until the same fail-closed scan gate says they are usable.
                assert_file_ready_for_business(normalized_id, user=actor)
            return view
        finally:
            db.close()

    # DB-off compatibility stays fail-closed and uses the same legacy authorization object.
    meta = _legacy.get_file_meta(normalized_id, user=actor)
    if not meta:
        return None
    obj = _legacy._MemFile(normalized_id)
    allowed_actions = ["viewMetadata"]
    if _legacy.authorize_file_access(actor, obj, "preview"):
        allowed_actions.extend(["preview", "download"])
    return {**meta, "allowedActions": allowed_actions}


def attachment_view(file_id: str | None) -> dict | None:
    """返回附件展示项，并保留由权威 resolver 计算的 preview/download 能力。

    历史实现只保留 fileId/fileName/ext/sizeBytes，导致业务 DTO 在持久化后丢失
    ``canPreview``，前端阅读器会在真正的票据鉴权前错误地拒绝合法文件。这里不新增
    任何授权旁路，只投影 File Center 已经计算出的 allowedActions。
    """
    if not file_id:
        return None
    meta = _authorized_attachment_metadata(str(file_id))
    if not meta:
        return None
    allowed_actions = list(meta.get("allowedActions") or [])
    return {
        "fileId": meta["fileId"],
        "fileName": meta.get("fileName"),
        "ext": meta.get("ext"),
        "mimeType": meta.get("mimeType"),
        "sizeBytes": meta.get("sizeBytes"),
        "allowedActions": allowed_actions,
        "canPreview": "preview" in allowed_actions,
        "canDownload": "download" in allowed_actions,
    }


async def store_upload(
    file,
    biz_type: str = "ATTACHMENT",
    *,
    biz_id: str | None = None,
    user: dict | None = None,
    visibility: str = "BIZ_SCOPED",
    security_level: str = "NORMAL",
) -> dict:
    """普通上传先锁定租户边界，再校验商业能力并进入物理写入。"""
    # 租户隔离是所有商业能力判断的前置条件。缺失 tenant context 时必须先
    # fail-closed 为 TENANT_CONTEXT_REQUIRED，不能拿 tenant=0 去查询商业套餐后
    # 误报 MODULE_NOT_AUTHORIZED。
    _legacy._require_tenant_id()
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
    """系统生成文件可信写入；仍做结构校验，但不进入用户上传杀毒队列。"""
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
