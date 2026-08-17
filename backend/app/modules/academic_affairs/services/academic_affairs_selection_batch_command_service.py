"""B production-audit · canonical SelectionBatch management commands.

Only management writes that were still falling through the compatibility core live
here.  Manual OPEN/CLOSE/PUBLISH/LOCK remain owned by Selection Final; this module
closes two residual gaps without creating another lifecycle truth:

- rule updates lock the batch and re-check term/state before writing;
- scheduler ticks reuse the same W1 OPEN/CLOSE preflight as manual commands, one
  locked batch at a time, so malformed/archived batches fail closed without blocking
  unrelated due batches.

The scheduler preserves the historical catch-up semantic: if both start and end are
already due, one tick may advance PUBLISHED -> OPEN -> CLOSED under one row lock.
"""
from __future__ import annotations

import json
from datetime import datetime

from sqlalchemy import select

from app.core.exceptions import AppException, not_found

from . import academic_affairs_selection_core_service as _core
from .academic_affairs_selection_preflight_service import require_batch_action
from .academic_affairs_selection_service import _guard_batch_writable


def _lock_batch(db, batch_id):
    from app.models import AaSelectionBatch

    row = db.execute(
        select(AaSelectionBatch).where(
            AaSelectionBatch.id == int(batch_id),
            AaSelectionBatch.tenant_id == _core._tid(),
            AaSelectionBatch.is_deleted.is_(False),
        ).with_for_update()
    ).scalar_one_or_none()
    if not row:
        raise not_found("选课批次不存在")
    return row


def save_rule(user, batch_id, rule) -> dict:
    """Persist rule config only while the locked batch is still DRAFT/PUBLISHED."""
    with _core.session() as db:
        _core._require_manage_scope(_core._ctx(user, db))
        batch = _lock_batch(db, batch_id)
        _guard_batch_writable(db, batch)
        if batch.status not in (_core._BATCH_DRAFT, _core._BATCH_PUBLISHED):
            raise _core._invalid("仅 DRAFT/PUBLISHED 批次可改规则")
        batch.rule_json = json.dumps(rule, ensure_ascii=False) if rule else None
        _core._audit(db, batch.id, "SELECTION_RULE_UPDATE", "保存选课规则")
        db.commit()
        return _core._batch_dto(batch)


def _due_batch_ids(user, tick_at: datetime) -> list[int]:
    """Pure discovery; every candidate is locked and revalidated before mutation."""
    from app.models import AaSelectionBatch

    with _core.session() as db:
        _core._require_manage_scope(_core._ctx(user, db))
        common = (
            AaSelectionBatch.tenant_id == _core._tid(),
            AaSelectionBatch.is_deleted.is_(False),
        )
        opening = db.query(AaSelectionBatch.id).filter(
            *common,
            AaSelectionBatch.status == _core._BATCH_PUBLISHED,
            AaSelectionBatch.select_start_at.isnot(None),
            AaSelectionBatch.select_start_at <= tick_at,
        ).all()
        closing = db.query(AaSelectionBatch.id).filter(
            *common,
            AaSelectionBatch.status == _core._BATCH_OPEN,
            AaSelectionBatch.select_end_at.isnot(None),
            AaSelectionBatch.select_end_at <= tick_at,
        ).all()
        return sorted({int(row[0]) for row in [*opening, *closing]})


def run_time_tick(user) -> dict:
    """Advance due batches with locked W1 preflight; one bad batch cannot poison peers."""
    tick_at = datetime.utcnow()
    opened = 0
    closed = 0
    blocked = []

    for batch_id in _due_batch_ids(user, tick_at):
        local_opened = 0
        local_closed = 0
        try:
            with _core.session() as db:
                _core._require_manage_scope(_core._ctx(user, db))
                batch = _lock_batch(db, batch_id)

                if (
                    batch.status == _core._BATCH_PUBLISHED
                    and batch.select_start_at is not None
                    and batch.select_start_at <= tick_at
                ):
                    _guard_batch_writable(db, batch)
                    require_batch_action(db, batch, "OPEN")
                    batch.status = _core._BATCH_OPEN
                    _core._audit(db, batch.id, "SELECTION_BATCH_AUTO_OPEN", "定时开选；preflight=PASS")
                    local_opened = 1

                # Preserve historical catch-up: a long-offline scheduler may need to
                # OPEN and immediately CLOSE the same batch in one locked transaction.
                if (
                    batch.status == _core._BATCH_OPEN
                    and batch.select_end_at is not None
                    and batch.select_end_at <= tick_at
                ):
                    _guard_batch_writable(db, batch)
                    require_batch_action(db, batch, "CLOSE")
                    batch.status = _core._BATCH_CLOSED
                    _core._audit(db, batch.id, "SELECTION_BATCH_AUTO_CLOSE", "定时截止；preflight=PASS")
                    local_closed = 1

                if local_opened or local_closed:
                    db.commit()
                opened += local_opened
                closed += local_closed
        except AppException as exc:
            blocked.append({
                "batchId": str(batch_id),
                "code": str(getattr(exc, "code", "") or "DATA_CONFLICT"),
                "message": str(getattr(exc, "message", "") or str(exc)),
            })

    return {
        "opened": opened,
        "closed": closed,
        "blockedCount": len(blocked),
        "blocked": blocked,
        "tickAt": tick_at.isoformat(),
    }
