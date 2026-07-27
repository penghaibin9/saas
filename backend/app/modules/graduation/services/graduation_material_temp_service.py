"""毕业设计临时上传附件生命周期。

学生选择文件后，文件中心会先创建 GRADUATION_MATERIAL 行；开题/成果提交成功时
业务 Service 再将 fileId 绑定到材料。用户移除附件或放弃表单时，只允许删除：
1. 当前租户；2. 当前登录上传者本人；3. 仍未绑定任何开题/成果；4. biz_id 为空。
已提交材料绝不允许经本入口删除。
"""
from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import or_, select

from app.core.exceptions import AppException, no_permission, not_found
from app.models import FileObject
from app.modules.graduation.services.graduation_material_access_consistency import _binding
from app.services import audit_log, file_service
from app.services.db_service import _tid, session
from app.services.storage import get_backend


def _delete_storage(file_key: str) -> None:
    if not file_key:
        return
    try:
        get_backend().delete(file_key)
    except Exception:  # noqa: BLE001 - DB 已软删，物理残留交给后续存储巡检继续清理
        pass


def abandon_temporary_material(file_id: str, user: dict) -> dict:
    if not str(file_id or "").isdigit():
        raise not_found("临时附件不存在")
    actor_id = file_service._actor_user_id(user)
    if not actor_id:
        raise no_permission("无法确认当前上传者身份")

    file_key = ""
    file_name = ""
    with session() as db:
        row = db.get(FileObject, int(file_id), with_for_update=True)
        if not row or row.tenant_id != _tid() or row.is_deleted:
            raise not_found("临时附件不存在")
        if (row.biz_type or "").upper() != "GRADUATION_MATERIAL":
            raise AppException("DATA_CONFLICT", "该文件不是毕业设计临时材料")
        owner_id = row.owner_user_id or row.created_by
        if not owner_id or int(owner_id) != int(actor_id):
            raise no_permission("只能放弃本人刚上传且尚未提交的附件")
        if row.biz_id not in (None, "") or _binding(db, str(row.id)) is not None:
            raise AppException("DATA_CONFLICT", "附件已绑定开题或成果记录，不可作为临时文件删除")

        file_key = row.file_key or ""
        file_name = row.file_name or ""
        row.is_deleted = True
        db.commit()

    _delete_storage(file_key)
    audit_log.record("GRADUATION_TEMP_FILE_ABANDON", f"file:{file_id}", {"fileName": file_name})
    return {"fileId": str(file_id), "abandoned": True}


def cleanup_stale_temporary_materials(user: dict, *, older_than_hours: int = 24, limit: int = 50) -> dict:
    """机会式清理当前上传者的过期孤儿；上传前调用，避免需要额外定时器。"""
    actor_id = file_service._actor_user_id(user)
    if not actor_id:
        return {"cleaned": 0}
    cutoff = datetime.utcnow() - timedelta(hours=max(1, older_than_hours))
    deleted: list[tuple[str, str]] = []
    with session() as db:
        rows = db.scalars(select(FileObject).where(
            FileObject.tenant_id == _tid(),
            FileObject.biz_type == "GRADUATION_MATERIAL",
            FileObject.is_deleted.is_(False),
            FileObject.owner_user_id == int(actor_id),
            or_(FileObject.biz_id.is_(None), FileObject.biz_id == ""),
            FileObject.created_at < cutoff,
        ).order_by(FileObject.id).limit(max(1, min(200, limit))).with_for_update()).all()
        for row in rows:
            if _binding(db, str(row.id)) is not None:
                continue
            row.is_deleted = True
            deleted.append((str(row.id), row.file_key or ""))
        if deleted:
            db.commit()

    for file_id, file_key in deleted:
        _delete_storage(file_key)
        audit_log.record("GRADUATION_TEMP_FILE_EXPIRE", f"file:{file_id}", {"olderThanHours": older_than_hours})
    return {"cleaned": len(deleted)}
