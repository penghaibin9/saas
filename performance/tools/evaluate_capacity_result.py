#!/usr/bin/env python3
"""Evaluate k6 + V3 identity/route artifacts into a machine-readable capacity verdict.

Teacher V3 T9 distinguishes two different questions:
- ``cold``: enough distinct identities/tokens to make a capacity claim without a tiny hot cache pool;
- ``warm``: deliberately reuse a small identity pool to observe cache behaviour. A warm run may pass its
  latency/error gates, but it is never eligible to prove user-scale capacity.
"""
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
PROFILE_PEAK_VUS = {
    "smoke": 2,
    "baseline": 20,
    "p300": 300,
    "p500": 500,
    "p1000": 1000,
    "p3000": 3000,
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


def _identity_pool_assertion(v3: dict[str, Any], *, profile: str, mode: str) -> tuple[bool, dict[str, Any], dict[str, Any]]:
    identity = v3.get("identity") or {}
    scenario = str(v3.get("scenario") or "mixed").strip().lower()
    peak = int(PROFILE_PEAK_VUS.get(profile, 1))
    actual = {
        "scenario": scenario,
        "identityMode": str(identity.get("identityMode") or ""),
        "studentTokensAvailable": int(_number(identity.get("studentTokensAvailable"), default=0)),
        "teacherTokensAvailable": int(_number(identity.get("teacherTokensAvailable"), default=0)),
        "studentCredentialsAvailable": int(_number(identity.get("studentCredentialsAvailable"), default=0)),
        "teacherCredentialsAvailable": int(_number(identity.get("teacherCredentialsAvailable"), default=0)),
        "uniqueStudentTokens": int(_number(identity.get("uniqueStudentTokens"), default=0)),
        "uniqueTeacherTokens": int(_number(identity.get("uniqueTeacherTokens"), default=0)),
        "uniqueTeacherContexts": int(_number(identity.get("uniqueTeacherContexts"), default=0)),
        "teacherRoleRatios": identity.get("teacherRoleRatios") or {},
    }
    required: dict[str, Any] = {"peakVUs": peak, "scenario": scenario}
    if mode != "cold":
        return True, actual, {**required, "eligible": False, "reason": "warm-cache diagnostic"}

    student_needed = scenario in {"student", "mixed"}
    teacher_needed = scenario in {"teacher", "mixed"}
    required["uniqueStudentTokens"] = peak if student_needed else 0
    required["uniqueTeacherTokens"] = peak if teacher_needed else 0
    # High-load runs are required by auth.js to use pre-issued Teacher tokens. For those runs,
    # token cardinality alone is insufficient: 500 different JWTs that all point at one active
    # context would still exercise one hot permission/scope identity. Machine-lock the context
    # cardinality whenever a Teacher token pool is present. Low-load credential diagnostics keep
    # their existing behaviour because external credentials may not expose activeContextId metadata.
    teacher_contexts_required = peak if teacher_needed and actual["teacherTokensAvailable"] > 0 else 0
    required["uniqueTeacherContexts"] = teacher_contexts_required
    passed = (
        (not student_needed or actual["uniqueStudentTokens"] >= peak)
        and (not teacher_needed or actual["uniqueTeacherTokens"] >= peak)
        and (teacher_contexts_required == 0 or actual["uniqueTeacherContexts"] >= teacher_contexts_required)
    )
    return passed, actual, required


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", required=True)
    parser.add_argument("--identity-mode", choices=("cold", "warm"), default="cold")
    parser.add_argument("--summary", type=Path, required=True)
    parser.add_argument("--v3", type=Path, help="k6-summary-v3.json with route + identity evidence")
    parser.add_argument("--before", type=Path, required=True)
    parser.add_argument("--after", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    summary = _load(args.summary)
    v3 = _load(args.v3) if args.v3 else {}
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

    artifact_identity_mode = str(((v3.get("identity") or {}).get("identityMode")) or "")
    missing_routes = list(v3.get("missingRoutes") or []) if v3 else []
    identity_pool_passed, identity_actual, identity_limit = _identity_pool_assertion(
        v3, profile=args.profile, mode=args.identity_mode
    ) if v3 else (False, {}, {})

    if args.identity_mode == "warm":
        verdict_mode = "warm-cache-diagnostic"
    else:
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
        {
            "key": "v3ArtifactPresent",
            "passed": bool(v3),
            "enforced": args.v3 is not None,
            "actual": bool(v3),
            "limit": True,
        },
        {
            "key": "v3RoutesCovered",
            "passed": bool(v3) and not missing_routes,
            "enforced": args.v3 is not None,
            "actual": missing_routes,
            "limit": [],
        },
        {
            "key": "identityModeMatches",
            "passed": bool(v3) and artifact_identity_mode == args.identity_mode,
            "enforced": args.v3 is not None,
            "actual": artifact_identity_mode or None,
            "limit": args.identity_mode,
        },
        {
            "key": "coldIdentityPoolCoverage",
            "passed": identity_pool_passed,
            "enforced": args.v3 is not None and args.identity_mode == "cold",
            "actual": identity_actual,
            "limit": identity_limit,
        },
    ]

    passed = all(item["passed"] for item in assertions if item["enforced"])
    identity_evidence_eligible = args.identity_mode == "cold" and identity_pool_passed
    production_capacity_evidence_eligible = bool(
        passed
        and identity_evidence_eligible
        and target_mode == "remote"
        and not local_high_load
    )
    verdict = {
        "profile": args.profile,
        "identityMode": args.identity_mode,
        "mode": verdict_mode,
        "targetMode": target_mode,
        "passed": passed,
        "latencyGateEnforced": not local_high_load,
        "identityEvidenceEligible": identity_evidence_eligible,
        "productionCapacityEvidenceEligible": production_capacity_evidence_eligible,
        "summary": {
            "requests": request_count,
            "p95Ms": None if not math.isfinite(p95) else round(p95, 3),
            "p99Ms": None if not math.isfinite(p99) else round(p99, 3),
            "httpFailureRate": failed_rate,
            "businessCheckRate": check_rate,
            "missingRoutes": missing_routes,
            "identity": identity_actual,
        },
        "assertions": assertions,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(verdict, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(
        f"capacity_verdict profile={args.profile} identity_mode={args.identity_mode} mode={verdict_mode} "
        f"passed={str(passed).lower()} requests={request_count} "
        f"p95_ms={verdict['summary']['p95Ms']} p99_ms={verdict['summary']['p99Ms']} "
        f"failed_rate={failed_rate} check_rate={check_rate} "
        f"production_capacity_evidence={str(production_capacity_evidence_eligible).lower()}"
    )
    if args.identity_mode == "warm":
        print("INFO warm-cache runs are diagnostic and can never prove identity-scale capacity")
    elif local_high_load:
        print("INFO local high-load latency is diagnostic only; HTTPS remote runs enforce full latency gates")
    if not passed:
        for item in assertions:
            if item["enforced"] and not item["passed"]:
                print(f"FAILED {item['key']}: actual={item['actual']} limit={item['limit']}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
