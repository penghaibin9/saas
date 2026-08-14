"""D3-U 学籍异动材料便利性。

便利性入口只编排原 canonical ``change_service.submit``：
- effectiveDate 仍由既有 temporal guard 解释；
- materialFileIds 通过 ContextVar 只在本次 submit 事务内生效；
- AaStatusChange flush 获得 changeId 后，在同一 SQLAlchemy 事务中把 TEMP_PRIVATE
  文件绑定为 ``AA_STATUS_CHANGE`` 正式证据；任何文件失败都会让整笔异动回滚；
- 不修改 AaStatusChange 表，不给 legacy StatusChangeSubmit 增字段，不复制状态机；
- 后续补材料只允许 SUBMITTED / IN_REVIEW / RETURNED，终审及计划生效后冻结。
"""
from __future__ import annotations

from contextvars import ContextVar
from typing import Any

from sqlalchemy import event, select
from sqlalchemy.orm import Session as OrmSession

from app.core.exceptions import AppException, no_permission, not_found
from app.core.permissions import has_permission
from app.services.db_service import _tid, session
from app.services.file_access_service import list_business_files, register_file_resolver
from app.services.file_business_binding_service import bind_file_to_business

from . import academic_affairs_change_safety_guard as safety_guard
from . import academic_affairs_change_service as change_service

_BIZ_TYPE = "AA_STATUS_CHANGE"
_MAX_MATERIALS = 10
EDITABLE_MATERIAL_STATUSES = frozenset({"SUBMITTED", "IN_REVIEW", "RETURNED"})
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
_APPLY_PERMISSION = "academicAffairs.statusChange.apply"


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


def _active_material_file_ids(db, change_id) -> set[str]:
    from app.models.file import FileBinding

    rows = db.scalars(select(FileBinding.file_id).where(
        FileBinding.tenant_id == _tid(),
        FileBinding.biz_type == _BIZ_TYPE,
        FileBinding.biz_id == str(change_id),
        FileBinding.status == "ACTIVE",
        FileBinding.is_current.is_(True),
        FileBinding.is_deleted.is_(False),
    )).all()
    return {str(value) for value in rows if value is not None}


def _assert_materials_editable(change) -> None:
    status = str(change.status or "").upper()
    if status not in EDITABLE_MATERIAL_STATUSES:
        raise AppException(
            "STATUS_CHANGE_MATERIALS_FROZEN",
            "异动已完成审批或进入生效阶段，申请材料已冻结",
            details={"changeId": str(change.id), "status": status},
            http_status=409,
        )


def _bind_materials_in_session(db, change, file_ids: tuple[str, ...], actor: dict) -> None:
    """只建立正式 binding，不 commit；调用方事务失败时与业务对象一起回滚。"""
    if not file_ids:
        return
    _assert_materials_editable(change)
    existing = _active_material_file_ids(db, change.id)
    requested_new = {file_id for file_id in file_ids if file_id not in existing}
    if len(existing) + len(requested_new) > _MAX_MATERIALS:
        raise AppException("VALIDATION_ERROR", f"学籍异动正式材料最多 {_MAX_MATERIALS} 份")

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
            # 新便利性只接受通用上传产生的 TEMP_PRIVATE，或幂等复用已绑定到同一异动的文件；
            # 不允许借补材料入口接管历史 BIZ_SCOPED 文件。
            legacy_target_values=set(),
        )


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
            _bind_materials_in_session(db, change, file_ids, actor)
    finally:
        db.info[_PROCESSING_KEY] = False


def install() -> None:
    if not event.contains(OrmSession, "before_flush", _before_flush):
        event.listen(OrmSession, "before_flush", _before_flush)
    if not event.contains(OrmSession, "after_flush_postexec", _after_flush_postexec):
        event.listen(OrmSession, "after_flush_postexec", _after_flush_postexec)


def _load_change(db, change_id, *, lock: bool = False):
    from app.models import AaStatusChange

    try:
        parsed = int(change_id)
    except (TypeError, ValueError):
        raise not_found("学籍异动不存在") from None
    stmt = select(AaStatusChange).where(
        AaStatusChange.id == parsed,
        AaStatusChange.tenant_id == _tid(),
        AaStatusChange.is_deleted.is_(False),
    )
    if lock:
        stmt = stmt.with_for_update()
    change = db.scalars(stmt).first()
    if not change:
        raise not_found("学籍异动不存在")
    return change


def list_materials(change_id, user) -> list[dict]:
    """先按权威异动对象裁决范围，再交公共文件中心做逐文件 resolver 授权。"""
    with session() as db:
        change = _load_change(db, change_id)
        safety_guard.require_change_scope(db, user or {}, change)
    return list_business_files(_BIZ_TYPE, str(change_id), user=user)


def add_materials(change_id, user, material_file_ids=None) -> list[dict]:
    """在提交/在审/退回窗口补材料；终审或待生效以后冻结，任一失败整笔补充回滚。"""
    file_ids = _validate_file_ids(material_file_ids)
    if not file_ids:
        return list_materials(change_id, user)
    if not has_permission(user or {}, _APPLY_PERMISSION):
        raise no_permission("无权补充学籍异动材料")

    db = session()
    try:
        change = _load_change(db, change_id, lock=True)
        safety_guard.require_change_scope(db, user or {}, change)
        _bind_materials_in_session(db, change, file_ids, dict(user or {}))
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
    return list_materials(change_id, user)


def submit_with_materials(body, user, material_file_ids=None) -> dict:
    """一次请求提交异动 + 正式材料；canonical/temporal 服务保持原 owner。"""
    file_ids = _validate_file_ids(material_file_ids)
    token = _PENDING.set((file_ids, dict(user or {}))) if file_ids else None
    try:
        result = change_service.submit(body, user)
    finally:
        if token is not None:
            _PENDING.reset(token)

    # strict_submit 的 idempotencyKey 允许网络重放直接返回既有异动单。无论本次是否带材料，
    # 都必须读取正式 binding 并要求集合完全一致；A+B → A、A+B → 空、空 → A 都是幂等事实冲突。
    bound = list_materials(result["changeId"], user)
    bound_ids = {str(item.get("fileId") or "") for item in bound if str(item.get("fileId") or "")}
    requested = set(file_ids)
    if requested != bound_ids:
        raise AppException(
            "IDEMPOTENCY_MATERIAL_MISMATCH",
            "该幂等异动已存在，但正式材料与本次提交不一致，请刷新异动详情后处理",
            details={
                "changeId": str(result.get("changeId") or ""),
                "requestedCount": len(requested),
                "boundCount": len(bound_ids),
                "missingCount": len(requested - bound_ids),
                "extraCount": len(bound_ids - requested),
            },
            http_status=409,
        )
    return {**result, "materialCount": len(requested)}


install()
