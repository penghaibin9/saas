"""毕业设计材料下载的业务对象授权链。

专用下载路由先验证“附件确实绑定到开题/成果 + 当前角色可访问该学生”，
通过后仅按当前租户、文件状态和毕业设计业务类型解析存储对象。通用裸文件下载
仍保留原有对象权限，不在这里放宽。
"""
from __future__ import annotations

from sqlalchemy import select

from app.models import FileObject, GraduationFinal, GraduationProposal, GraduationStudent
from app.modules.graduation.services.graduation_scope_service import assert_student_access
from app.services.db_service import _tid, session
from app.services.file_content_security import is_downloadable_status
from app.services.storage import get_backend

_INSTALLED = False


def _attachment_id(raw) -> str:
    if isinstance(raw, dict):
        return str(raw.get("fileId") or raw.get("id") or "")
    return str(raw or "")


def _bound_student_id(db, file_id: str) -> int | None:
    for model in (GraduationProposal, GraduationFinal):
        rows = db.scalars(select(model).where(
            model.tenant_id == _tid(),
            model.is_deleted.is_(False),
            model.attachments_json.is_not(None),
        )).all()
        for row in rows:
            if file_id in {_attachment_id(item) for item in (row.attachments_json or [])}:
                return int(row.gd_student_id)
    return None


def resolve_material_download(file_id: str):
    """业务关系已核验时返回本地文件；不存在、跨租户、隔离中或未绑定均返回 None。"""
    if not str(file_id or "").isdigit():
        return None
    with session() as db:
        file_row = db.scalars(select(FileObject).where(
            FileObject.id == int(file_id),
            FileObject.tenant_id == _tid(),
            FileObject.is_deleted.is_(False),
            FileObject.biz_type == "GRADUATION_MATERIAL",
        )).first()
        if not file_row or not is_downloadable_status(file_row.status):
            return None

        gd_student_id = _bound_student_id(db, str(file_id))
        if gd_student_id is None:
            return None
        student = db.scalars(select(GraduationStudent).where(
            GraduationStudent.id == gd_student_id,
            GraduationStudent.tenant_id == _tid(),
            GraduationStudent.is_deleted.is_(False),
        )).first()
        assert_student_access(db, student, "graduation.material.download")
        file_key = file_row.file_key
        filename = file_row.file_name

    path = get_backend().fetch_local(file_key)
    if not path or not path.exists():
        return None
    return path, filename or path.name


def install_material_access_consistency() -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    from app.modules.graduation.services import graduation_service as service
    service.resolve_material_download = resolve_material_download
    _INSTALLED = True
