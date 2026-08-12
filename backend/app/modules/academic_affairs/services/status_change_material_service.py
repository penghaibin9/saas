"""D3-U 学籍异动材料便利性。

便利性入口只编排原 canonical ``change_service.submit``：
- effectiveDate 仍由既有 temporal guard 解释；
- materialFileIds 通过 ContextVar 只在本次 submit 事务内生效；
- AaStatusChange flush 获得 changeId 后，在同一 SQLAlchemy 事务中把 TEMP_PRIVATE
  文件绑定为 ``AA_STATUS_CHANGE`` 正式证据；任何文件失败都会让整笔异动回滚；
- 不修改 AaStatusChange 表，不给 legacy StatusChangeSubmit 增字段，不复制状态机。
"""
from __future__ import annotations

from contextvars import ContextVar
from typing import Any

from sqlalchemy import event, select
from sqlalchemy.orm import Session as OrmSession

from app.core.exceptions import AppException
from app.core.permissions import has_permission
from app.services.db_service import _tid, session
from app.services.file_access_service import list_business_files, register_file_resolver
from app.services.file_business_binding_service import bind_file_to_business

from . import academic_affairs_change_safety_guard as safety_guard
from . import academic_affairs_change_service as change_service

_BIZ_TYPE = "AA_STATUS_CHANGE"
_MAX_MATERIALS = 10
_PENDING: ContextVar[tuple[tuple[str, ...], dict] | None] = ContextVar(
    "aa_status_change_materials_pending", default=None
)
_INFO_KEY = "aa_status_change_material_bindings_pending"
_PROCESSING_KEY = "aa_status_change_material_bindings_processing"

_STAFF_FILE_PERMISSIONS = (
    "academicAffairs.statusChange.apply",
    "academicAffairs.statusChange.view",
    "academicAffairs.statusChange.counselorReview",
    "academicAffairs.statusChange.collegeReview",
    "academicAffairs.statusChange.officeReview",
)


def _validate_file_ids(values) -> tuple[str, ...]:
    ids: list[str] = []
    seen: set[str] = set()
    for raw in values or []:
        value = str(raw or "").strip()
        if not value.isdigit() or int(value) <= 0:
            raise AppException("VALIDATION_ERROR", "材料 fileId 非法")
        if value in seen:
            continue
        seen.add(value)
        ids.append(value)
    if len(ids) > _MAX_MATERIALS:
        raise AppException("VALIDATION_ERROR", f"单次最多提交 {_MAX_MATERIALS} 份材料")
    return tuple(ids)


def _binding_matches_change(binding, change) -> bool:
    if binding.is_deleted or str(binding.status or "").upper() != "ACTIVE":
        return False
    if str(binding.biz_type or "").upper() != _BIZ_TYPE or str(binding.biz_id or "") != str(change.id):
        return False
    if str(binding.subject_type or "").upper() != "STUDENT":
        return False
    if str(binding.subject_id or "") != str(change.student_id):
        return False
    if binding.student_id and int(binding.student_id) != int(change.student_id):
        return False
    return True


@register_file_resolver(_BIZ_TYPE)
def status_change_file_resolver(db, file_obj, bindings: list[Any], user: dict, action: str) -> bool:
    """异动材料访问 = 文件关系完整 + 异动对象 dataScope + 对应业务身份，绝不靠文件管理员旁路。"""
    del action
    if db is None:
        return False
    biz_id = str(file_obj.biz_id or "").strip()
    if not biz_id.isdigit():
        return False
    try:
        from app.models import AaStatusChange

        change = db.scalars(select(AaStatusChange).where(
            AaStatusChange.id == int(biz_id),
            AaStatusChange.tenant_id == int(file_obj.tenant_id),
            AaStatusChange.is_deleted.is_(False),
        )).first()
        if not change or not any(_binding_matches_change(item, change) for item in bindings):
            return False
        safety_guard.require_change_scope(db, user or {}, change)
        if str((user or {}).get("userType") or "").upper() == "STUDENT":
            return True
        return any(has_permission(user or {}, code) for code in _STAFF_FILE_PERMISSIONS)
    except Exception:
        return False


def _before_flush(db, flush_context, instances) -> None:
    del flush_context, instances
    selected = _PENDING.get()
    if not selected or db.info.get(_PROCESSING_KEY):
        return
    file_ids, actor = selected
    if not file_ids:
        return
    from app.models import AaStatusChange

    pending = list(db.info.get(_INFO_KEY, []))
    known = {id(item[0]) for item in pending}
    for obj in list(db.new):
        if isinstance(obj, AaStatusChange) and id(obj) not in known:
            pending.append((obj, file_ids, dict(actor or {})))
            known.add(id(obj))
    if pending:
        db.info[_INFO_KEY] = pending


def _after_flush_postexec(db, flush_context) -> None:
    del flush_context
    pending = db.info.pop(_INFO_KEY, [])
    if not pending or db.info.get(_PROCESSING_KEY):
        return
    db.info[_PROCESSING_KEY] = True
    try:
        for change, file_ids, actor in pending:
            for file_id in file_ids:
                bind_file_to_business(
                    db,
                    file_id=file_id,
                    biz_type=_BIZ_TYPE,
                    biz_id=change.id,
                    actor=actor,
                    subject_type="STUDENT",
                    subject_id=change.student_id,
                    relation_type="APPLICATION_MATERIAL",
                    module_code="ACADEMIC_AFFAIRS",
                    student_id=int(change.student_id),
                    college_id=change.from_college_id,
                    class_id=change.from_class_id,
                    scope={
                        "changeId": str(change.id),
                        "studentId": str(change.student_id),
                        "changeType": change.change_type,
                        "fromStatus": change.from_status,
                        "toStatus": change.to_status,
                        "fromCollegeId": str(change.from_college_id or ""),
                        "toCollegeId": str(change.to_college_id or ""),
                        "fromClassId": str(change.from_class_id or ""),
                        "toClassId": str(change.to_class_id or ""),
                    },
                )
    finally:
        db.info[_PROCESSING_KEY] = False


def install() -> None:
    if not event.contains(OrmSession, "before_flush", _before_flush):
        event.listen(OrmSession, "before_flush", _before_flush)
    if not event.contains(OrmSession, "after_flush_postexec", _after_flush_postexec):
        event.listen(OrmSession, "after_flush_postexec", _after_flush_postexec)


def list_materials(change_id, user) -> list[dict]:
    """先按权威异动对象裁决范围，再交公共文件中心做逐文件 resolver 授权。"""
    with session() as db:
        from app.models import AaStatusChange

        change = db.scalars(select(AaStatusChange).where(
            AaStatusChange.id == int(change_id),
            AaStatusChange.tenant_id == _tid(),
            AaStatusChange.is_deleted.is_(False),
        )).first()
        if not change:
            from app.core.exceptions import not_found
            raise not_found("学籍异动不存在")
        safety_guard.require_change_scope(db, user or {}, change)
    return list_business_files(_BIZ_TYPE, str(change_id), user=user)


def submit_with_materials(body, user, material_file_ids=None) -> dict:
    """一次请求提交异动 + 正式材料；canonical/temporal 服务保持原 owner。"""
    file_ids = _validate_file_ids(material_file_ids)
    token = _PENDING.set((file_ids, dict(user or {}))) if file_ids else None
    try:
        result = change_service.submit(body, user)
    finally:
        if token is not None:
            _PENDING.reset(token)

    if not file_ids:
        return {**result, "materialCount": 0}

    # strict_submit 的 idempotencyKey 允许网络重放直接返回既有异动单。重放时不会产生新 ORM insert，
    # 因而 flush hook 也不会再次执行；这里必须核对既有正式 binding，防止同 key 换材料后虚报成功。
    bound = list_materials(result["changeId"], user)
    bound_ids = {str(item.get("fileId") or "") for item in bound}
    requested = set(file_ids)
    if not requested.issubset(bound_ids):
        raise AppException(
            "IDEMPOTENCY_MATERIAL_MISMATCH",
            "该幂等异动已存在，但正式材料与本次提交不一致，请刷新异动详情后处理",
            details={
                "changeId": str(result.get("changeId") or ""),
                "requestedCount": len(requested),
                "boundCount": len(requested.intersection(bound_ids)),
            },
            http_status=409,
        )
    return {**result, "materialCount": len(requested)}


install()
