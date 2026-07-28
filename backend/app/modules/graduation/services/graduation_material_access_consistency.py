"""毕业设计材料下载的业务对象授权链。

专用下载路由验证“附件确实绑定到开题/成果 + 当前角色拥有明确业务关系”：
- 学生本人只能访问自己的材料；
- 被分配的互查学生只能访问任务绑定的那一份正式定稿；
- 教师/管理员继续按导师、评阅、答辩或组织数据范围访问。
通用裸文件下载仍保留原有对象权限，不在这里放宽。
"""
from __future__ import annotations

from sqlalchemy import select

from app.core.context import get_current_user_ctx
from app.core.exceptions import no_permission
from app.models import (
    FileObject,
    GraduationFinal,
    GraduationPeerReview,
    GraduationProposal,
    GraduationStudent,
)
from app.modules.graduation.services.graduation_record_resolver import resolve_current_gd_student
from app.modules.graduation.services.graduation_scope_service import assert_student_access
from app.services.db_service import _tid, session
from app.services.file_content_security import is_downloadable_status
from app.services.storage import get_backend

_INSTALLED = False


def _attachment_id(raw) -> str:
    if isinstance(raw, dict):
        return str(raw.get("fileId") or raw.get("id") or "")
    return str(raw or "")


def _binding(db, file_id: str):
    """返回 (kind, material_id, gd_student_id)，仅限当前租户有效绑定。"""
    for kind, model in (("PROPOSAL", GraduationProposal), ("FINAL", GraduationFinal)):
        rows = db.scalars(select(model).where(
            model.tenant_id == _tid(),
            model.is_deleted.is_(False),
            model.attachments_json.is_not(None),
        )).all()
        for row in rows:
            if file_id in {_attachment_id(item) for item in (row.attachments_json or [])}:
                return kind, int(row.id), int(row.gd_student_id)
    return None


def _authorize_binding(db, binding) -> None:
    kind, material_id, gd_student_id = binding
    student = db.scalars(select(GraduationStudent).where(
        GraduationStudent.id == gd_student_id,
        GraduationStudent.tenant_id == _tid(),
        GraduationStudent.is_deleted.is_(False),
    )).first()
    user = get_current_user_ctx() or {}
    role = str(user.get("currentRoleCode") or "").strip().upper()
    user_type = str(user.get("userType") or "").strip().upper()
    if role == "STUDENT" or user_type == "STUDENT":
        current = resolve_current_gd_student(db, user)
        if not current:
            raise no_permission("无法确认当前毕业设计学生身份")
        if int(current.id) == gd_student_id:
            return
        if kind == "FINAL":
            peer = db.scalars(select(GraduationPeerReview.id).where(
                GraduationPeerReview.tenant_id == _tid(),
                GraduationPeerReview.gd_final_id == material_id,
                GraduationPeerReview.reviewer_gd_student_id == int(current.id),
                GraduationPeerReview.is_deleted.is_(False),
                GraduationPeerReview.status.in_(("ASSIGNED", "REVIEWED", "RECTIFIED")),
            ).limit(1)).first()
            if peer is not None:
                return
        raise no_permission("该材料不属于本人，也未分配给本人互查")
    assert_student_access(db, student, "graduation.material.download")


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

        binding = _binding(db, str(file_id))
        if binding is None:
            return None
        _authorize_binding(db, binding)
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
