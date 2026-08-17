"""B production-audit · canonical SelectionBatch management commands.

Management writes that were still falling through the compatibility core live here.
Manual OPEN/CLOSE/PUBLISH/LOCK remain owned by Selection Final; this module closes
residual write-authority gaps without creating another lifecycle truth:

- batch creation validates any explicit term reference in the same transaction while
  preserving the supported term-less DRAFT workflow;
- rule updates lock the batch and re-check term/state before writing;
- scheduler ticks reuse the same W1 OPEN/CLOSE preflight as manual commands, process
  a bounded keyset, and never wait behind a busy Batch/Term authority row.

The scheduler preserves the historical catch-up semantic: if both start and end are
already due, one tick may advance PUBLISHED -> OPEN -> CLOSED under one row lock.
"""
from __future__ import annotations

import json
from datetime import datetime

from sqlalchemy import and_, or_, select

from app.core.exceptions import AppException, not_found

from . import academic_affairs_selection_core_service as _core
from .academic_affairs_selection_preflight_service import require_batch_action
from .academic_affairs_selection_service import (
    _guard_batch_writable,
    _require_term_reference_writable,
)


_TICK_BATCH_LIMIT = 100


def _lock_batch(db, batch_id):
    """Blocking command lock; interactive writes must serialize, never skip."""
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


def _lock_next_due_batch_for_tick(db, tick_at: datetime, after_id: int):
    """Lock the next due row without waiting behind another batch writer.

    The keyset + hard limit keeps one scheduler invocation bounded. SKIP LOCKED is
    deliberately scheduler-only: a batch currently owned by an interactive/manual
    command is deferred to the next tick instead of delaying every later due batch.
    """
    from app.models import AaSelectionBatch

    due_to_open = and_(
        AaSelectionBatch.status == _core._BATCH_PUBLISHED,
        AaSelectionBatch.select_start_at.isnot(None),
        AaSelectionBatch.select_start_at <= tick_at,
    )
    due_to_close = and_(
        AaSelectionBatch.status == _core._BATCH_OPEN,
        AaSelectionBatch.select_end_at.isnot(None),
        AaSelectionBatch.select_end_at <= tick_at,
    )
    return db.execute(
        select(AaSelectionBatch).where(
            AaSelectionBatch.tenant_id == _core._tid(),
            AaSelectionBatch.is_deleted.is_(False),
            AaSelectionBatch.id > int(after_id),
            or_(due_to_open, due_to_close),
        )
        .order_by(AaSelectionBatch.id.asc())
        .limit(1)
        .with_for_update(skip_locked=True)
    ).scalar_one_or_none()


def _term_lock_available_for_tick(db, batch) -> bool:
    """Non-blocking pre-lock for the Term row used by the canonical writability guard.

    Invalid/missing references are left to ``_guard_batch_writable`` so the canonical
    business error stays unchanged. A real row that exists but cannot be locked is a
    concurrent Archive/Term mutation and must be deferred rather than waited on.
    """
    from app.models import AaTerm

    raw_term_id = getattr(batch, "term_id", None)
    if raw_term_id in (None, ""):
        return True
    try:
        term_id = int(raw_term_id)
    except (TypeError, ValueError):
        return True

    predicate = (
        AaTerm.id == term_id,
        AaTerm.tenant_id == _core._tid(),
        AaTerm.is_deleted.is_(False),
    )
    locked_id = db.execute(
        select(AaTerm.id).where(*predicate).with_for_update(skip_locked=True)
    ).scalar_one_or_none()
    if locked_id is not None:
        return True

    # A consistent read does not wait on the row lock. If the committed row is still
    # visible, SKIP LOCKED missed it because another writer owns it; otherwise the
    # canonical guard should map the genuinely missing/deleted reference.
    existing_id = db.execute(select(AaTerm.id).where(*predicate)).scalar_one_or_none()
    return existing_id is None


def create_batch(user, body) -> dict:
    """Create DRAFT; explicit termId must already resolve to a writable tenant term."""
    from app.models import AaSelectionBatch

    with _core.session() as db:
        _core._require_manage_scope(_core._ctx(user, db))
        name = (getattr(body, "batchName", None) or "").strip()
        if not name:
            raise AppException("VALIDATION_ERROR", "批次名称必填")

        raw_term_id = getattr(body, "termId", None)
        term_id = None
        if raw_term_id not in (None, ""):
            term = _require_term_reference_writable(db, raw_term_id, required=False)
            term_id = int(term.id)

        batch = AaSelectionBatch(
            tenant_id=_core._tid(),
            batch_name=name,
            term_id=term_id,
            select_start_at=_core._parse_dt(getattr(body, "selectStartAt", None)),
            select_end_at=_core._parse_dt(getattr(body, "selectEndAt", None)),
            apply_scope_json=(
                json.dumps(body.applyScope, ensure_ascii=False)
                if getattr(body, "applyScope", None)
                else None
            ),
            rule_json=(
                json.dumps(body.rule, ensure_ascii=False)
                if getattr(body, "rule", None)
                else None
            ),
            remark=getattr(body, "remark", None),
            status=_core._BATCH_DRAFT,
        )
        db.add(batch)
        db.flush()
        _core._audit(db, batch.id, "SELECTION_BATCH_CREATE", f"建批次 {name}")
        db.commit()
        return _core._batch_dto(batch)


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


def run_time_tick(user) -> dict:
    """Advance a bounded set of due batches without waiting on busy authority rows."""
    tick_at = datetime.utcnow()
    opened = 0
    closed = 0
    blocked = []
    deferred = []
    processed = 0
    after_id = 0

    while processed < _TICK_BATCH_LIMIT:
        local_opened = 0
        local_closed = 0
        batch_id = None
        try:
            with _core.session() as db:
                _core._require_manage_scope(_core._ctx(user, db))
                batch = _lock_next_due_batch_for_tick(db, tick_at, after_id)
                if batch is None:
                    break

                batch_id = int(batch.id)
                after_id = batch_id
                processed += 1

                if not _term_lock_available_for_tick(db, batch):
                    deferred.append({
                        "batchId": str(batch_id),
                        "code": "SELECTION_TERM_BUSY",
                        "message": "关联学期正在被其它命令更新，本批次延后到下一次定时轮询",
                    })
                    continue

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
            if batch_id is None:
                raise
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
        "deferredCount": len(deferred),
        "deferred": deferred,
        "processedCount": processed,
        "scanLimit": _TICK_BATCH_LIMIT,
        "scanLimitReached": processed >= _TICK_BATCH_LIMIT,
        "tickAt": tick_at.isoformat(),
    }
