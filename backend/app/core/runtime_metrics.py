"""Small dependency-free runtime metrics for health probes and log-based alerts.

Metrics are process-local by design.  Production monitoring should scrape every
backend replica (or aggregate access logs); this endpoint intentionally exposes no
tenant identifiers, request bodies, SQL text or parameters.
"""
from __future__ import annotations

import threading
from collections import Counter, deque

_lock = threading.Lock()
_durations: deque[float] = deque(maxlen=2000)
_statuses: Counter[str] = Counter()
_routes: Counter[str] = Counter()
_slow_requests = 0


def record_request(path: str, status: int, duration_ms: float, slow_ms: int) -> None:
    global _slow_requests
    with _lock:
        _durations.append(float(duration_ms))
        _statuses[f"{int(status) // 100}xx"] += 1
        _routes[path[:160]] += 1
        if duration_ms >= slow_ms:
            _slow_requests += 1


def _percentile(values: list[float], fraction: float) -> float:
    if not values:
        return 0.0
    values.sort()
    index = min(len(values) - 1, max(0, int(round((len(values) - 1) * fraction))))
    return round(values[index], 1)


def snapshot() -> dict:
    with _lock:
        values = list(_durations)
        statuses = dict(_statuses)
        routes = _routes.most_common(10)
        slow = _slow_requests
    return {
        "sampleSize": len(values),
        "latencyMs": {
            "p50": _percentile(values.copy(), 0.50),
            "p95": _percentile(values.copy(), 0.95),
            "p99": _percentile(values.copy(), 0.99),
            "max": round(max(values), 1) if values else 0.0,
        },
        "statuses": statuses,
        "slowRequests": slow,
        "topRoutes": [{"path": path, "count": count} for path, count in routes],
    }


def reset_for_tests() -> None:
    global _slow_requests
    with _lock:
        _durations.clear()
        _statuses.clear()
        _routes.clear()
        _slow_requests = 0
