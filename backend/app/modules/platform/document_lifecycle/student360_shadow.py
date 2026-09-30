"""Anonymous timeline-only parity metrics for Student360 shadow migration."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True, slots=True)
class TimelineIdentity:
    source_module: str
    fact_type: str
    event_time: str


def timeline_shadow_metrics(
    legacy: Iterable[TimelineIdentity],
    facts: Iterable[TimelineIdentity],
) -> dict[str, int]:
    """Return counts only; never log a title, summary, reason, student id or payload."""
    left = list(legacy)
    right = list(facts)
    left_types = [(item.source_module, item.fact_type) for item in left]
    right_types = [(item.source_module, item.fact_type) for item in right]
    return {
        "legacyCount": len(left),
        "factCount": len(right),
        "missingCount": max(0, len(left) - len(right)),
        "extraCount": max(0, len(right) - len(left)),
        "orderMismatch": int(
            [(item.source_module, item.fact_type, item.event_time) for item in left]
            != [(item.source_module, item.fact_type, item.event_time) for item in right]
        ),
        "factTypeMismatch": sum(1 for a, b in zip(left_types, right_types) if a != b),
    }
