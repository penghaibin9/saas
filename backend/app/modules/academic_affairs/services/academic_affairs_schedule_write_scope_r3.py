"""P1-05 / AA-008 schedule writer Authority hardening.

Only authorization/lock ordering is added here. Scheduling algorithms, conflict rules,
publish gates and truth-head logic remain owned by ``academic_affairs_schedule_final_service``.
"""
from __future__ import annotations

import inspect
from contextvars import ContextVar
from functools import wraps

from app.core.affairs_security import build_affairs_context, no_data_scope
from app.core.exceptions import AppException, not_found

_actor = ContextVar("aa_schedule_write_actor", default=None)
_INSTALLED = False


def _college_id(value):
    if value in (None, ""):
        return None
    return int(value)


def assert_schedule_write_scope(db, user, batch_or_college) -> None:
    """TENANT_ALL may write school-wide/any college; COLLEGE only its explicit college."""
    college_id = getattr(batch_or_college, "college_id", batch_or_college)
    target_college_id = _college_id(college_id)
    ctx = build_affairs_context(user or {}, db)
    scope_type = str(getattr(ctx, "scope_type", None) or "NONE").upper()
    if scope_type == "TENANT_ALL":
        return
    if scope_type != "COLLEGE":
        raise no_data_scope("当前账号没有课表写入数据范围")
    allowed = {int(value) for value in getattr(ctx, "college_ids", set()) if value is not None}
    if target_college_id is None:
        raise no_data_scope("学院范围账号不能操作全校课表批次")
    if target_college_id not in allowed:
        raise no_data_scope("该课表批次不在您的学院管理范围内")


def _bind_actor(fn):
    signature = inspect.signature(fn)

    @wraps(fn)
    def wrapped(*args, **kwargs):
        bound = signature.bind_partial(*args, **kwargs)
        token = _actor.set(bound.arguments.get("user") or {})
        try:
            return fn(*args, **kwargs)
        finally:
            _actor.reset(token)

    return wrapped


def install(target) -> None:
    """Install once on the canonical final schedule module."""
    global _INSTALLED
    if _INSTALLED or getattr(target, "_aa_r3_write_scope_installed", False):
        return

    def guarded_load_batch(db, batch_id, *, writable=True, lock=True):
        from app.models import AaScheduleBatch

        query = db.query(AaScheduleBatch).filter(
            AaScheduleBatch.id == int(batch_id),
            AaScheduleBatch.tenant_id == target._base._tid(),
            AaScheduleBatch.is_deleted.is_(False),
        )
        if lock:
            query = query.with_for_update()
        batch = query.first()
        if not batch:
            raise not_found("课表批次不存在")
        if writable:
            actor = _actor.get()
            if actor is None:
                raise no_data_scope("无法确认课表写入操作者")
            assert_schedule_write_scope(db, actor, batch)
        target.policy.resolve_scope(
            db,
            term_id=batch.term_id,
            batch_id=batch.id,
            writable=writable,
        )
        return batch

    target._load_batch = guarded_load_batch

    for name in ("add_item", "import_items", "adjust_item", "pre_publish", "publish"):
        setattr(target, name, _bind_actor(getattr(target, name)))

    original_create_batch = target.create_batch
    create_signature = inspect.signature(original_create_batch)

    @wraps(original_create_batch)
    def create_batch(*args, **kwargs):
        bound = create_signature.bind_partial(*args, **kwargs)
        body = bound.arguments.get("body")
        user = bound.arguments.get("user") or {}
        college_id = getattr(body, "collegeId", None) if body is not None else None
        # No batch row exists yet. Authorize before the legacy writer performs any insert.
        with target._base.session() as db:
            assert_schedule_write_scope(db, user, college_id)
        return original_create_batch(*args, **kwargs)

    target.create_batch = create_batch

    original_move_item = target.move_item
    move_signature = inspect.signature(original_move_item)

    @wraps(original_move_item)
    def move_item(*args, **kwargs):
        """Keep fixed lock order Batch -> Item while preserving the existing move algorithm."""
        bound = move_signature.bind_partial(*args, **kwargs)
        item_id = int(bound.arguments["item_id"])
        user = bound.arguments.get("user") or {}
        body = bound.arguments["body"]
        token = _actor.set(user)
        try:
            from app.models import AaScheduleItem
            with target._base.session() as db:
                probe = db.query(AaScheduleItem.batch_id).filter(
                    AaScheduleItem.id == item_id,
                    AaScheduleItem.tenant_id == target._base._tid(),
                    AaScheduleItem.is_deleted.is_(False),
                ).first()
                if not probe:
                    raise not_found("排课条目不存在")
                batch = guarded_load_batch(db, int(probe[0]), writable=True, lock=True)
                item = db.query(AaScheduleItem).filter(
                    AaScheduleItem.id == item_id,
                    AaScheduleItem.batch_id == batch.id,
                    AaScheduleItem.tenant_id == target._base._tid(),
                    AaScheduleItem.is_deleted.is_(False),
                ).with_for_update().first()
                if not item:
                    raise AppException("DATA_CONFLICT", "排课条目所属批次已变化，请刷新后重试", http_status=409)
                if batch.status not in {"DRAFT", "PRE_PUBLISHED"}:
                    raise AppException("DATA_CONFLICT", "已发布课表不可直接改动", http_status=409)
                task = target._resolve_task(db, batch, {"taskId": item.task_id})
                source = {
                    "weekday": body.weekday,
                    "slotNo": body.slotNo,
                    "startWeek": item.start_week,
                    "endWeek": item.end_week,
                    "weekParity": item.week_parity,
                    "classroom": item.classroom_text,
                }
                weekday, slot_no, start_week, end_week, parity = target._coordinate(db, batch, task, source)
                conflict = target._base._detect_conflict(
                    db, batch.id, weekday, slot_no, start_week, end_week, parity,
                    task.teacher_key, task.class_id, item.classroom_text, exclude_id=item.id,
                )
                if conflict:
                    raise AppException(
                        "DATA_CONFLICT",
                        f"排课冲突（{conflict['type']}）：{conflict['detail']}",
                        details=conflict,
                        http_status=409,
                    )
                item.weekday = weekday
                item.slot_no = slot_no
                if item.source == "AUTO":
                    item.source = "MANUAL"
                reset = batch.status == "PRE_PUBLISHED"
                if reset:
                    batch.status = "DRAFT"
                target._base._audit(
                    db, "AA_SCHEDULE", item.id, "MOVE_ITEM",
                    f"周{weekday}第{slot_no}节;prePublishReset={reset}",
                )
                db.commit()
                return {**target._base._item_row(item), "prePublishReset": reset}
        finally:
            _actor.reset(token)

    target.move_item = move_item
    target._aa_r3_write_scope_installed = True
    _INSTALLED = True
