"""公共文件对象授权 resolver registry 与业务绑定。

统一原则：租户、对象关系、数据范围、批次和安全状态必须同时成立；任何失败均向外表现为 404，
避免通过 403/列表数量/文件名枚举其他学校、其他学生或其他批次的文件。

RBAC-09：文件治理身份只管理容量、策略、扫描和审计元数据，绝不作为文件原文访问依据。
"""
from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Any

from sqlalchemy import select

from app.core.context import current_tenant_id, get_current_user_ctx
from app.core.exceptions import AppException, not_found
from app.core.permissions import has_permission
from app.core.rbac09_permission_bundles import (
    FILE_GOVERNANCE_VIEW,
    FILE_SCAN_RETRY,
    has_permission_compat,
)
from app.db.session import db_enabled, get_sessionmaker
from app.services.file_content_security import is_downloadable_status
from app.services.file_scan_constants import READY_SCAN_STATES, SCAN_NOT_REQUIRED

Resolver = Callable[[Any, Any, list[Any], dict, str], bool]
_RESOLVERS: dict[str, Resolver] = {}

_FILE_VIEW_PERMISSION = {
    "DISCIPLINE": "studentAffairs.discipline.view",
    "DISCIPLINE_APPEAL": "studentAffairs.discipline.view",
    "LEAGUE": "studentAffairs.league.view",
    "CLUB": "studentAffairs.club.view",
    "FUNDING": "studentAffairs.funding.view",
    "REDUCTION": "studentAffairs.funding.view",
    "LOAN": "studentAffairs.funding.view",
    "HOME_SCHOOL": "studentAffairs.homeSchool.view",
    "LEAVE": "studentAffairs.leave.view",
    "AID": "studentAffairs.aid.view",
    "RISK": "studentAffairs.risk.view",
    "MENTAL": "studentAffairs.risk.view",
    "GRADUATION_MATERIAL": "graduationDesign.view",
    "INTERNSHIP": "internship.student.material.view",
    "COURSE_MATERIAL": "academicAffairs.course.view",
    "ATTACHMENT": "studentAffairs.student.view",
}

STATUS_TEXT = {
    "NOT_REQUIRED": "无需扫描",
    "PENDING": "等待安全扫描",
    "RUNNING": "正在安全扫描",
    "CLEAN": "安全可用",
    "INFECTED": "检测到风险，已拒绝",
    "ERROR": "安全扫描失败",
}


def register_file_resolver(*biz_types: str):
    """注册业务对象 resolver；同一业务类型只允许一个权威 resolver。"""
    normalized = tuple(str(item or "").strip().upper() for item in biz_types if str(item or "").strip())

    def decorator(fn: Resolver) -> Resolver:
        for biz_type in normalized:
            existing = _RESOLVERS.get(biz_type)
            if existing is not None and existing is not fn:
                raise RuntimeError(f"duplicate file resolver: {biz_type}")
            _RESOLVERS[biz_type] = fn
        return fn

    return decorator


def resolver_registry_snapshot() -> dict[str, str]:
    return {key: f"{fn.__module__}.{fn.__name__}" for key, fn in sorted(_RESOLVERS.items())}


def _actor_id(user: dict) -> str:
    value = user.get("userId") or user.get("id") or ""
    return str(value).strip()


def _actor_student_values(user: dict) -> set[str]:
    values = {
        str(user.get("studentId") or "").strip(),
        str(user.get("studentNo") or "").strip(),
    }
    for item in user.get("allowedStudentIds") or []:
        values.add(str(item).strip())
    for item in user.get("allowedStudentNos") or []:
        values.add(str(item).strip())
    return {item for item in values if item}


def _actor_batch_values(user: dict) -> set[str]:
    keys = ("batchId", "activeBatchId", "graduationBatchId", "internshipBatchId")
    values = {str(user.get(key) or "").strip() for key in keys}
    for item in user.get("allowedBatchIds") or []:
        values.add(str(item).strip())
    return {item for item in values if item}


def _can_retry_scan(user: dict) -> bool:
    return has_permission_compat(user, FILE_SCAN_RETRY)


def _can_view_file_audit(user: dict) -> bool:
    return has_permission_compat(user, FILE_GOVERNANCE_VIEW)


def _binding_subject_allows(binding, user: dict) -> bool:
    subject_type = str(binding.subject_type or "BUSINESS_OBJECT").upper()
    subject_id = str(binding.subject_id or "").strip()
    batch_id = str(binding.batch_id or "").strip()

    if batch_id and batch_id not in _actor_batch_values(user):
        return False
    if subject_type in {"BUSINESS_OBJECT", "TENANT"}:
        # 这两类只说明“文件属于哪个对象/租户”，不证明当前访问者与对象有关系。
        # 必须继续由业务 permission/resolver 判定，不能单独作为内容放行依据。
        return False
    if subject_type == "USER":
        return bool(subject_id and subject_id == _actor_id(user))
    if subject_type == "STUDENT":
        return bool(subject_id and subject_id in _actor_student_values(user))
    if subject_type == "BATCH":
        return bool(subject_id and subject_id in _actor_batch_values(user))
    if subject_type == "ROLE":
        roles = {
            str(user.get("currentRoleCode") or "").upper(),
            str(user.get("userType") or "").upper(),
        }
        return subject_id.upper() in roles
    return False


def _default_resolver(db, file_obj, bindings: list[Any], user: dict, action: str) -> bool:
    actor_id = _actor_id(user)
    owner = str(file_obj.owner_user_id or file_obj.created_by or "").strip()
    if actor_id and owner and actor_id == owner:
        return True

    active = [item for item in bindings if not item.is_deleted and item.status == "ACTIVE"]
    # 只有指向当前用户、学生、批次或角色的主体绑定才证明直接关系；
    # BUSINESS_OBJECT/TENANT 绑定仍必须叠加业务 permission/resolver。
    if active and any(_binding_subject_allows(item, user) for item in active):
        return True

    if str(user.get("userType") or "").upper() == "STUDENT":
        biz_id = str(file_obj.biz_id or "").strip()
        return bool(biz_id and biz_id in _actor_student_values(user))
    permission = _FILE_VIEW_PERMISSION.get(str(file_obj.biz_type or "").upper())
    return bool(permission and has_permission(user, permission))


@register_file_resolver(
    "DISCIPLINE", "DISCIPLINE_APPEAL", "LEAGUE", "CLUB", "FUNDING",
    "REDUCTION", "LOAN", "HOME_SCHOOL",
)
def _student_affairs_resolver(db, file_obj, bindings: list[Any], user: dict, action: str) -> bool:
    """学工 resolver 直接调用权威业务范围校验，不再通过运行时 monkey-patch 改写 file_service。"""
    permission = _FILE_VIEW_PERMISSION.get(str(file_obj.biz_type or "").upper())
    if not permission or not has_permission(user, permission):
        return False
    try:
        from app.services.affairs_attachment_service import _require_biz_scope
        _require_biz_scope(db, str(file_obj.biz_type or "").upper(), file_obj.biz_id, user)
        return all(_binding_subject_allows(item, user) for item in bindings if item.batch_id)
    except Exception:
        return False


def _scan_ready(file_obj) -> bool:
    scan_status = str(file_obj.scan_status or SCAN_NOT_REQUIRED).upper()
    return bool(is_downloadable_status(file_obj.status) and scan_status in READY_SCAN_STATES)


def _load_file_and_bindings(db, tenant_id: int, file_id: int):
    from app.models.file import FileBinding, FileObject

    file_obj = db.scalars(select(FileObject).where(
        FileObject.id == file_id,
        FileObject.tenant_id == tenant_id,
        FileObject.is_deleted.is_(False),
    )).first()
    if not file_obj:
        return None, []
    bindings = db.scalars(select(FileBinding).where(
        FileBinding.file_id == file_id,
        FileBinding.tenant_id == tenant_id,
        FileBinding.is_deleted.is_(False),
    ).order_by(FileBinding.version_no.desc(), FileBinding.id.desc())).all()
    return file_obj, list(bindings)


def authorize_file_object(file_obj, bindings: list[Any], user: dict, action: str = "meta", db=None) -> bool:
    tenant_id = int(current_tenant_id() or 0)
    if not tenant_id or int(file_obj.tenant_id or 0) != tenant_id or file_obj.is_deleted:
        return False
    # “bind”在这里仅用于验证调用人是否与文件有关联；扫描是否完成由
    # assert_file_ready_for_business 单独返回 FILE_NOT_READY。这样授权用户能轮询
    # SCANNING，而未授权用户仍统一得到 404，不泄露文件存在性。
    if action in {"download", "preview", "submit", "archive"} and not _scan_ready(file_obj):
        return False
    resolver = _RESOLVERS.get(str(file_obj.biz_type or "").upper(), _default_resolver)
    return bool(resolver(db, file_obj, bindings, user or {}, action))


def require_file_access(file_id: str, *, user: dict | None = None, action: str = "meta"):
    """统一对象授权入口；任一校验失败均返回 404。"""
    if not db_enabled() or not str(file_id).isdigit():
        from app.services import file_service
        meta = file_service._MEM_REGISTRY.get(str(file_id))  # noqa: SLF001
        if not meta:
            raise not_found("文件不存在")
        if action in {"download", "preview", "bind", "submit", "archive"}:
            status = str(meta.get("status") or "").upper()
            scan_status = str(meta.get("scanStatus") or SCAN_NOT_REQUIRED).upper()
            if not is_downloadable_status(status) or scan_status not in READY_SCAN_STATES:
                raise not_found("文件不存在")
        return meta

    tenant_id = int(current_tenant_id() or 0)
    if not tenant_id:
        raise not_found("文件不存在")
    actor = user or get_current_user_ctx() or {}
    db = get_sessionmaker()()
    try:
        file_obj, bindings = _load_file_and_bindings(db, tenant_id, int(file_id))
        if not file_obj or not authorize_file_object(file_obj, bindings, actor, action, db=db):
            raise not_found("文件不存在")
        if action == "bind" and not _scan_ready(file_obj):
            raise not_found("文件不存在")
        return file_obj
    finally:
        db.close()


def upsert_file_binding(
    file_id: str,
    *,
    biz_type: str,
    biz_id: str,
    relation_type: str = "ATTACHMENT",
    subject_type: str = "BUSINESS_OBJECT",
    subject_id: str | None = None,
    batch_id: str | None = None,
    version_no: int = 1,
    scope_json: dict | None = None,
    user: dict | None = None,
    db=None,
):
    """幂等登记文件与业务对象关系；不改变文件字节和扫描结果。"""
    if not str(file_id).isdigit() or not db_enabled():
        return None
    from app.models.file import FileBinding, FileObject

    tenant_id = int(current_tenant_id() or 0)
    if not tenant_id:
        raise AppException("TENANT_CONTEXT_REQUIRED", "缺少租户上下文")
    actor = user or get_current_user_ctx() or {}
    own_session = db is None
    session = db or get_sessionmaker()()
    try:
        file_obj = session.scalars(select(FileObject).where(
            FileObject.id == int(file_id),
            FileObject.tenant_id == tenant_id,
            FileObject.is_deleted.is_(False),
        )).first()
        if not file_obj:
            raise not_found("文件不存在")
        normalized_biz = str(biz_type or file_obj.biz_type or "ATTACHMENT").upper()
        normalized_id = str(biz_id or file_obj.biz_id or "").strip()
        if not normalized_id:
            raise AppException("VALIDATION_ERROR", "业务对象标识不能为空")
        relation = str(relation_type or "ATTACHMENT").upper()
        row = session.scalars(select(FileBinding).where(
            FileBinding.tenant_id == tenant_id,
            FileBinding.file_id == int(file_id),
            FileBinding.biz_type == normalized_biz,
            FileBinding.biz_id == normalized_id,
            FileBinding.relation_type == relation,
            FileBinding.is_deleted.is_(False),
        )).first()
        if row is None:
            row = FileBinding(
                tenant_id=tenant_id,
                file_id=int(file_id),
                biz_type=normalized_biz,
                biz_id=normalized_id,
                relation_type=relation,
                subject_type=str(subject_type or "BUSINESS_OBJECT").upper(),
                subject_id=str(subject_id).strip() if subject_id not in (None, "") else None,
                batch_id=str(batch_id).strip() if batch_id not in (None, "") else None,
                version_no=max(1, int(version_no or 1)),
                is_current=True,
                status="ACTIVE",
                scope_json=scope_json or {},
                created_by=int(_actor_id(actor)) if _actor_id(actor).isdigit() else None,
            )
            session.add(row)
        else:
            row.subject_type = str(subject_type or row.subject_type or "BUSINESS_OBJECT").upper()
            row.subject_id = str(subject_id).strip() if subject_id not in (None, "") else row.subject_id
            row.batch_id = str(batch_id).strip() if batch_id not in (None, "") else row.batch_id
            row.version_no = max(int(row.version_no or 1), int(version_no or 1))
            row.is_current = True
            row.status = "ACTIVE"
            row.scope_json = scope_json or row.scope_json or {}
        file_obj.biz_type = normalized_biz
        file_obj.biz_id = normalized_id
        if own_session:
            session.commit()
            session.refresh(row)
        else:
            session.flush()
        return row
    finally:
        if own_session:
            session.close()


def _allowed_actions(file_obj, user: dict, bindings: list[Any], db) -> list[str]:
    actions = ["viewMetadata"]
    if authorize_file_object(file_obj, bindings, user, "preview", db=db):
        actions.extend(["preview", "download"])
    if _can_retry_scan(user):
        actions.append("retryScan")
    if _can_view_file_audit(user):
        actions.append("viewAudit")
    return actions


def file_view(file_obj, *, user: dict, bindings: list[Any], db) -> dict[str, Any]:
    scan_status = str(file_obj.scan_status or SCAN_NOT_REQUIRED).upper()
    return {
        "fileId": str(file_obj.id),
        "fileName": file_obj.file_name,
        "ext": file_obj.ext,
        "mimeType": file_obj.mime_type,
        "sizeBytes": file_obj.size_bytes,
        "sha256": file_obj.sha256,
        "bizType": file_obj.biz_type,
        "bizId": file_obj.biz_id,
        "status": file_obj.status,
        "scanRequired": bool(file_obj.scan_required),
        "scanStatus": scan_status,
        "statusText": STATUS_TEXT.get(scan_status, "状态未知"),
        "readyForBusiness": _scan_ready(file_obj),
        "allowedActions": _allowed_actions(file_obj, user, bindings, db),
        "createdAt": file_obj.created_at.isoformat(timespec="seconds") if file_obj.created_at else None,
        "scannedAt": file_obj.scanned_at.isoformat(timespec="seconds") if file_obj.scanned_at else None,
    }


def list_business_files(biz_type: str, biz_id: str, *, user: dict | None = None) -> list[dict[str, Any]]:
    from app.models.file import FileBinding, FileObject

    tenant_id = int(current_tenant_id() or 0)
    if not tenant_id:
        raise not_found("业务对象不存在")
    actor = user or get_current_user_ctx() or {}
    db = get_sessionmaker()()
    try:
        bindings = db.scalars(select(FileBinding).where(
            FileBinding.tenant_id == tenant_id,
            FileBinding.biz_type == str(biz_type or "").upper(),
            FileBinding.biz_id == str(biz_id or ""),
            FileBinding.status == "ACTIVE",
            FileBinding.is_deleted.is_(False),
        ).order_by(FileBinding.version_no.desc(), FileBinding.id.desc())).all()
        results: list[dict[str, Any]] = []
        for binding in bindings:
            file_obj = db.get(FileObject, binding.file_id)
            if not file_obj:
                continue
            file_bindings = [item for item in bindings if item.file_id == binding.file_id]
            if authorize_file_object(file_obj, file_bindings, actor, "meta", db=db):
                view = file_view(file_obj, user=actor, bindings=file_bindings, db=db)
                view.update({
                    "bindingId": str(binding.id),
                    "relationType": binding.relation_type,
                    "versionNo": int(binding.version_no or 1),
                    "isCurrent": bool(binding.is_current),
                })
                results.append(view)
        if bindings and not results:
            raise not_found("业务对象不存在")
        return results
    finally:
        db.close()


def file_versions(file_id: str, *, user: dict | None = None) -> list[dict[str, Any]]:
    from app.models.file import FileBinding, FileObject

    require_file_access(file_id, user=user, action="meta")
    tenant_id = int(current_tenant_id() or 0)
    actor = user or get_current_user_ctx() or {}
    db = get_sessionmaker()()
    try:
        current = db.get(FileObject, int(file_id))
        bindings = db.scalars(select(FileBinding).where(
            FileBinding.tenant_id == tenant_id,
            FileBinding.file_id == int(file_id),
            FileBinding.is_deleted.is_(False),
        ).order_by(FileBinding.version_no.desc(), FileBinding.id.desc())).all()
        return [{
            "bindingId": str(item.id),
            "versionNo": int(item.version_no or 1),
            "isCurrent": bool(item.is_current),
            "status": item.status,
            "relationType": item.relation_type,
            "bizType": item.biz_type,
            "bizId": item.biz_id,
            "file": file_view(current, user=actor, bindings=list(bindings), db=db),
            "boundAt": item.created_at.isoformat(timespec="seconds") if item.created_at else None,
        } for item in bindings]
    finally:
        db.close()
