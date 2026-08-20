"""Bounded read-only pagination helper for Graduation batch scope projection.

The legacy batch reader paginates tenant-wide rows before D-W0's college-scope filter.
That can yield an empty first page while a visible batch exists later.  This helper keeps
that mature DTO reader as the only batch formatter, but scans it in bounded chunks and
applies scope before the caller's page window.  It performs no writes and owns no
Graduation truth.
"""
from __future__ import annotations

from collections.abc import Callable
from typing import Any


_DEFAULT_SCAN_PAGE_SIZE = 200
_MAX_SCAN_PAGES = 10_000


def _positive_int(value: object, *, default: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed > 0 else default


def collect_scoped_batch_page(
    *,
    user,
    status: str | None,
    page: int,
    page_size: int,
    original_list_batches: Callable[..., tuple[list[dict[str, Any]], int]],
    visible_ids_for_candidates: Callable[[list[int]], set[int]],
    scoped_stats_for_batch: Callable[[int], dict[str, int]],
    scan_page_size: int = _DEFAULT_SCAN_PAGE_SIZE,
) -> tuple[list[dict[str, Any]], int]:
    """Return page/total after scope filtering while preserving mature batch DTOs.

    `original_list_batches` remains the canonical formatter/order source. Candidate IDs are
    checked in bounded chunks; only visible DTOs are retained.  The function scans through
    the tenant batch sequence so `total` is the exact scoped total, not the number visible
    on the current tenant-wide page.
    """
    requested_page = _positive_int(page, default=1)
    requested_size = _positive_int(page_size, default=50)
    chunk_size = min(_positive_int(scan_page_size, default=_DEFAULT_SCAN_PAGE_SIZE), _DEFAULT_SCAN_PAGE_SIZE)
    skip_visible = (requested_page - 1) * requested_size
    take_until = skip_visible + requested_size

    collected: list[dict[str, Any]] = []
    visible_total = 0
    tenant_total: int | None = None
    scanned_rows = 0
    scan_page = 1

    while True:
        if scan_page > _MAX_SCAN_PAGES:
            raise RuntimeError("graduation scoped batch pagination exceeded bounded scan pages")

        rows, reported_total = original_list_batches(
            user,
            status=status,
            page=scan_page,
            page_size=chunk_size,
        )
        if tenant_total is None:
            tenant_total = max(0, int(reported_total or 0))
        else:
            # A changing tenant-wide total during one read projection is unsafe for page math.
            if int(reported_total or 0) != tenant_total:
                raise RuntimeError("graduation batch total changed during scoped pagination")

        if not rows:
            break

        batch_ids = [int(row["batchId"]) for row in rows if str(row.get("batchId") or "").isdigit()]
        visible_ids = visible_ids_for_candidates(batch_ids)
        if not visible_ids.issubset(set(batch_ids)):
            raise RuntimeError("graduation scope resolver returned a batch outside the candidate chunk")

        for row in rows:
            raw_id = str(row.get("batchId") or "")
            if not raw_id.isdigit() or int(raw_id) not in visible_ids:
                continue
            index = visible_total
            visible_total += 1
            if skip_visible <= index < take_until:
                projected = dict(row)
                projected.update(scoped_stats_for_batch(int(raw_id)))
                collected.append(projected)

        scanned_rows += len(rows)
        if tenant_total is not None and scanned_rows >= tenant_total:
            break
        if len(rows) < chunk_size:
            break
        scan_page += 1

    return collected, visible_total
