"""SQLAlchemy engine observability without logging SQL parameters."""
from __future__ import annotations

import logging
import time

from sqlalchemy import event

from app.core.config import settings

log = logging.getLogger("app.slow_sql")


def install_engine_observers(engine) -> None:
    if getattr(engine, "_school_observers_installed", False):
        return

    @event.listens_for(engine, "before_cursor_execute")
    def _before(_conn, _cursor, _statement, _parameters, context, _executemany):
        context._school_query_started = time.perf_counter()

    @event.listens_for(engine, "after_cursor_execute")
    def _after(_conn, _cursor, statement, _parameters, context, executemany):
        started = getattr(context, "_school_query_started", None)
        if started is None:
            return
        elapsed_ms = (time.perf_counter() - started) * 1000
        if elapsed_ms < max(1, settings.SLOW_QUERY_MS):
            return
        verb = (statement or "").lstrip().split(None, 1)[0].upper()[:16] or "UNKNOWN"
        log.warning("slow_sql verb=%s ms=%.1f executemany=%s", verb, elapsed_ms, executemany)

    engine._school_observers_installed = True
