"""公共文件版本时间线：以业务对象 + 关系类型为版本族，而不是单个 fileId。"""
from __future__ import annotations

from collections import defaultdict

from sqlalchemy import select

from app.core.context import current_tenant_id, get_current_user_ctx
from app.core.exceptions import not_found
from app.db.session import get_sessionmaker
from app.services.file_access_service import authorize_file_object, file_view, require_file_access


def file_version_timeline(file_id: str, *, user: dict | None = None) -> list[dict]:
    from app.models.file import FileBinding, FileObject

    require_file_access(file_id, user=user, action="meta")
    tenant_id = int(current_tenant_id() or 0)
    actor = user or get_current_user_ctx() or {}
    db = get_sessionmaker()()
    try:
        anchor = db.scalars(select(FileBinding).where(
            FileBinding.tenant_id == tenant_id,
            FileBinding.file_id == int(file_id),
            FileBinding.is_deleted.is_(False),
        ).order_by(FileBinding.is_current.desc(), FileBinding.version_no.desc(), FileBinding.id.desc())).first()
        if anchor is None:
            current = db.get(FileObject, int(file_id))
            if not current:
                raise not_found("文件不存在")
            return [{
                "bindingId": None,
                "versionNo": 1,
                "isCurrent": True,
                "status": "LEGACY",
                "relationType": "ATTACHMENT",
                "bizType": current.biz_type,
                "bizId": current.biz_id,
                "file": file_view(current, user=actor, bindings=[], db=db),
                "boundAt": current.created_at.isoformat(timespec="seconds") if current.created_at else None,
            }]

        family = db.scalars(select(FileBinding).where(
            FileBinding.tenant_id == tenant_id,
            FileBinding.biz_type == anchor.biz_type,
            FileBinding.biz_id == anchor.biz_id,
            FileBinding.relation_type == anchor.relation_type,
            FileBinding.is_deleted.is_(False),
        ).order_by(FileBinding.version_no.desc(), FileBinding.id.desc())).all()
        by_file: dict[int, list] = defaultdict(list)
        for item in family:
            by_file[int(item.file_id)].append(item)

        results: list[dict] = []
        for item in family:
            file_obj = db.get(FileObject, item.file_id)
            if not file_obj:
                continue
            bindings = by_file[int(item.file_id)]
            if not authorize_file_object(file_obj, bindings, actor, "meta", db=db):
                continue
            results.append({
                "bindingId": str(item.id),
                "versionNo": int(item.version_no or 1),
                "isCurrent": bool(item.is_current),
                "status": item.status,
                "relationType": item.relation_type,
                "bizType": item.biz_type,
                "bizId": item.biz_id,
                "file": file_view(file_obj, user=actor, bindings=bindings, db=db),
                "boundAt": item.created_at.isoformat(timespec="seconds") if item.created_at else None,
            })
        if not results:
            raise not_found("文件不存在")
        return results
    finally:
        db.close()
