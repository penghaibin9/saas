"""学工归档文件对象级授权：租户 + archive.view + 目标学生数据范围。"""
from __future__ import annotations

from app.core.context import current_tenant_id
from app.core.permissions import has_permission
from app.services.db_service import session

_INSTALLED = False


def install() -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    from app.services import file_service
    from app.services.file_content_security import is_downloadable_status

    old_store_bytes = file_service.store_bytes
    old_authorize = file_service.authorize_file_access

    def store_bytes(data, filename, biz_type="ATTACHMENT", mime_type=None, **kwargs):
        # 仅本系统生成的每生学工档案快照改为独立对象类型，禁止落入通用附件权限。
        if biz_type == "ATTACHMENT" and str(filename or "").startswith("学工档案_"):
            biz_type = "AFFAIRS_ARCHIVE"
        return old_store_bytes(data, filename, biz_type, mime_type, **kwargs)

    def authorize_file_access(user, file_obj, action="download"):
        if (getattr(file_obj, "biz_type", None) or "").upper() != "AFFAIRS_ARCHIVE":
            return old_authorize(user, file_obj, action)
        try:
            tenant_id = int(current_tenant_id() or 0)
            file_tenant = int(getattr(file_obj, "tenant_id", 0) or 0)
        except (TypeError, ValueError):
            return False
        if not tenant_id or tenant_id != file_tenant or getattr(file_obj, "is_deleted", False):
            return False
        if action == "download" and not is_downloadable_status(getattr(file_obj, "status", None)):
            return False
        if not has_permission(user or {}, "studentAffairs.archive.view"):
            return False
        student_id = str(getattr(file_obj, "biz_id", None) or "")
        if not student_id.isdigit():
            return False
        try:
            from app.core.affairs_security import build_affairs_context
            with session() as db:
                build_affairs_context(user or {}, db).require_student(db, int(student_id))
            return True
        except Exception:  # 统一返回无权，下载端转404避免枚举文件存在性
            return False

    file_service._BIZ_VIEW_PERM["AFFAIRS_ARCHIVE"] = "studentAffairs.archive.view"
    file_service.store_bytes = store_bytes
    file_service.authorize_file_access = authorize_file_access
    _INSTALLED = True
