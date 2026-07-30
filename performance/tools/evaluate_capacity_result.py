#!/usr/bin/env python3
"""Evaluate k6 and observability artifacts into a machine-readable capacity verdict."""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

PROFILE_MIN_REQUESTS = {
    "smoke": 100,
    "baseline": 1000,
    "p300": 10000,
    "p500": 20000,
}
LOCAL_DIAGNOSTIC_PROFILES = {"p300", "p500"}


def _load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SystemExit(f"missing capacity artifact: {path}") from exc
    except json.JSONDecodeError as exc:
        raise SystemExit(f"invalid JSON artifact {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise SystemExit(f"capacity artifact must be a JSON object: {path}")
    return value


def _number(value: Any, *, default: float = math.nan) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _ready(doc: dict[str, Any]) -> bool:
    health = doc.get("health") or {}
    readiness = doc.get("readiness") or {}
    checks = readiness.get("checks") or {}
    return bool(
        doc.get("ok") is True
        and health.get("statusCode") == 200
        and health.get("status") == "UP"
        and readiness.get("statusCode") == 200
        and readiness.get("status") == "READY"
        and checks
        and all(value is True for value in checks.values())
    )


def _status_failures(doc: dict[str, Any]) -> dict[str, int]:
    latest = ((doc.get("metrics") or {}).get("latest") or {})
    statuses = latest.get("statuses") or {}
    failures: dict[str, int] = {}
    for key, value in statuses.items():
        if str(key).lower() == "2xx":
            continue
        try:
            count = int(value or 0)
        except (TypeError, ValueError):
            count = 0
        if count > 0:
            failures[str(key)] = count
    return failures


def _metric_values(summary: dict[str, Any], key: str) -> dict[str, Any]:
    metric = (summary.get("metrics") or {}).get(key) or {}
    values = metric.get("values") or {}
    return values if isinstance(values, dict) else {}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", required=True)
    parser.add_argument("--summary", type=Path, required=True)
    parser.add_argument("--before", type=Path, required=True)
    parser.add_argument("--after", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    summary = _load(args.summary)
    before = _load(args.before)
    after = _load(args.after)

    duration = _metric_values(summary, "http_req_duration")
    failed = _metric_values(summary, "http_req_failed")
    checks = _metric_values(summary, "checks")
    requests = _metric_values(summary, "http_reqs")

    request_count = int(_number(requests.get("count"), default=0))
    p95 = _number(duration.get("p(95)"))
    p99 = _number(duration.get("p(99)"))
    failed_rate = _number(failed.get("rate"), default=1)
    check_rate = _number(checks.get("rate"), default=0)
    minimum_requests = PROFILE_MIN_REQUESTS.get(args.profile, 1)
    missing_keys = ((after.get("metrics") or {}).get("missingKeys") or [])
    non_2xx = _status_failures(after)
    target_mode = str(before.get("targetMode") or after.get("targetMode") or "unknown")
    local_high_load = target_mode == "local" and args.profile in LOCAL_DIAGNOSTIC_PROFILES
    verdict_mode = "local-functional" if local_high_load else "full-capacity"

    assertions = [
        {
            "key": "minimumRequests",
            "passed": request_count >= minimum_requests,
            "enforced": True,
            "actual": request_count,
            "limit": minimum_requests,
        },
        {
            "key": "httpFailureRate",
            "passed": failed_rate < 0.005,
            "enforced": True,
            "actual": failed_rate,
            "limit": 0.005,
        },
        {
            "key": "businessCheckRate",
            "passed": check_rate > 0.995,
            "enforced": True,
            "actual": check_rate,
            "limit": 0.995,
        },
        {
            "key": "p95Ms",
            "passed": math.isfinite(p95) and p95 < 1000,
            "enforced": not local_high_load,
            "actual": None if not math.isfinite(p95) else round(p95, 3),
            "limit": 1000,
        },
        {
            "key": "p99Ms",
            "passed": math.isfinite(p99) and p99 < 2000,
            "enforced": not local_high_load,
            "actual": None if not math.isfinite(p99) else round(p99, 3),
            "limit": 2000,
        },
        {
            "key": "readinessBefore",
            "passed": _ready(before),
            "enforced": True,
            "actual": (before.get("readiness") or {}).get("status"),
            "limit": "READY",
        },
        {
            "key": "readinessAfter",
            "passed": _ready(after),
            "enforced": True,
            "actual": (after.get("readiness") or {}).get("status"),
            "limit": "READY",
        },
        {
            "key": "metricsKeysAfter",
            "passed": not missing_keys,
            "enforced": True,
            "actual": missing_keys,
            "limit": [],
        },
        {
            "key": "non2xxAfter",
            "passed": not non_2xx,
            "enforced": True,
            "actual": non_2xx,
            "limit": {},
        },
    ]

    passed = all(item["passed"] for item in assertions if item["enforced"])
    verdict = {
        "profile": args.profile,
        "mode": verdict_mode,
        "targetMode": target_mode,
        "passed": passed,
        "latencyGateEnforced": not local_high_load,
        "summary": {
            "requests": request_count,
            "p95Ms": None if not math.isfinite(p95) else round(p95, 3),
            "p99Ms": None if not math.isfinite(p99) else round(p99, 3),
            "httpFailureRate": failed_rate,
            "businessCheckRate": check_rate,
        },
        "assertions": assertions,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(verdict, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(
        f"capacity_verdict profile={args.profile} mode={verdict_mode} "
        f"passed={str(passed).lower()} requests={request_count} "
        f"p95_ms={verdict['summary']['p95Ms']} p99_ms={verdict['summary']['p99Ms']} "
        f"failed_rate={failed_rate} check_rate={check_rate}"
    )
    if local_high_load:
        print("INFO local high-load latency is diagnostic only; HTTPS remote runs enforce full latency gates")
    if not passed:
        for item in assertions:
            if item["enforced"] and not item["passed"]:
                print(f"FAILED {item['key']}: actual={item['actual']} limit={item['limit']}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
