"""毕业设计临时上传附件生命周期。

学生选择文件后，文件中心会先创建 GRADUATION_MATERIAL 行；开题/成果提交成功时
业务 Service 再将 fileId 绑定到材料。用户移除附件或放弃表单时，只允许删除：
1. 当前租户；2. 当前登录上传者本人；3. 仍未绑定任何开题/成果；4. biz_id 为空。
已提交材料绝不允许经本入口删除。
"""
from __future__ import annotations

from app.core.exceptions import AppException, no_permission, not_found
from app.models import FileObject
from app.modules.graduation.services.graduation_material_access_consistency import _binding
from app.services import audit_log, file_service
from app.services.db_service import _tid, session
from app.services.storage import get_backend


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

    # 数据库先软删，存储删除失败也不会再对外暴露；后台存储巡检可继续清理物理残留。
    if file_key:
        try:
            get_backend().delete(file_key)
        except Exception:  # noqa: BLE001 - 不把物理存储短暂故障变成用户误以为仍可访问
            pass
    audit_log.record("GRADUATION_TEMP_FILE_ABANDON", f"file:{file_id}", {"fileName": file_name})
    return {"fileId": str(file_id), "abandoned": True}
