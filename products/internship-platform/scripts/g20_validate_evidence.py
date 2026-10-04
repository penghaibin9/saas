#!/usr/bin/env python3
"""Validate k6 evidence for Yiyang procurement G20.

A small CI/load smoke can validate the harness but can never become a procurement
PASS. G20 PASS requires evidence produced with at least 5000 VUs, a business
endpoint mix, authentication, explicit real-run acknowledgement and all k6
thresholds passing.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any


MIN_PROCUREMENT_VUS = 5000
MAX_AVERAGE_MS = 3000
MIN_HOLD_SECONDS = 60  # Existing engineering observation window, not a school SLA substitute.
BUSINESS_PREFIXES = ('/api/v1/internship/', '/api/v1/mobile/internship/', '/api/v1/student-portal/internship/')


class EvidenceError(RuntimeError):
    pass


def _mapping(raw: Any) -> dict[str, Any]:
    return raw if isinstance(raw, dict) else {}


def _metric(summary: dict[str, Any], name: str) -> dict[str, Any]:
    return _mapping(_mapping(summary.get("metrics")).get(name))


def _value(metric: dict[str, Any], key: str) -> float | int | None:
    values = _mapping(metric.get("values"))
    raw = values.get(key)
    return raw if type(raw) in (int, float) and math.isfinite(raw) and raw >= 0 else None


def _count(raw) -> int:
    return int(raw) if type(raw) in (int, float) and math.isfinite(raw) and raw >= 0 and int(raw) == raw else 0


def thresholds_pass(summary: dict[str, Any]) -> tuple[bool, list[dict[str, Any]]]:
    statuses = _mapping(summary.get("thresholdStatus"))
    checks: list[dict[str, Any]] = []
    if not statuses:
        return False, [{"metric": "*", "threshold": "*", "ok": False, "reason": "thresholdStatus missing"}]
    for metric, threshold_map in statuses.items():
        if not isinstance(threshold_map, dict) or not threshold_map:
            checks.append({"metric": metric, "threshold": "*", "ok": False})
            continue
        for threshold, ok in threshold_map.items():
            checks.append({"metric": metric, "threshold": threshold, "ok": ok is True})
    return bool(checks) and all(item["ok"] for item in checks), checks


def validate(summary: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(summary, dict) or summary.get("gate") != "G20" or summary.get("generator") != "k6":
        raise EvidenceError("not a G20 k6 evidence document")

    vus = summary.get("requestedVus") if type(summary.get("requestedVus")) is int else 0
    paths = summary.get('configuredPaths')
    business_paths = summary.get('businessPaths')
    paths = paths if isinstance(paths, list) and all(isinstance(item, str) for item in paths) else []
    business_paths = business_paths if isinstance(business_paths, list) and all(isinstance(item, str) for item in business_paths) else []
    ack = summary.get("realRunAcknowledged") is True
    auth = summary.get("authConfigured") is True
    auth_identity_count = _count(summary.get("authIdentityCount"))
    verification = _mapping(summary.get('identityVerification'))
    verified_count = _count(verification.get('verifiedTokenCount'))
    distinct_count = _count(verification.get('distinctAccountCount'))
    identity_pool_ok = (vus > 0 and auth_identity_count == vus == verified_count == distinct_count
                        and verification.get('method') == 'server-auth-me'
                        and verification.get('endpoint') == '/api/v1/auth/me'
                        and verification.get('allVerified') is True)
    business = (summary.get("businessScenarioConfigured") is True and bool(business_paths)
                and all(path.startswith(BUSINESS_PREFIXES) and path in paths for path in business_paths))
    schema_ok = (type(summary.get('schemaVersion')) is int and summary['schemaVersion'] == 2
                 and summary.get('runMode') == 'single-generator')
    threshold_ok, threshold_checks = thresholds_pass(summary)

    req_metric = _metric(summary, "http_reqs")
    failed_metric = _metric(summary, "http_req_failed")
    duration_metric = _metric(summary, "http_req_duration")
    checks_metric = _metric(summary, "checks")

    request_count = _count(_value(req_metric, "count"))
    request_rate = _value(req_metric, "rate")
    failed_rate = _value(failed_metric, "rate")
    avg_ms = _value(duration_metric, "avg")
    p95_ms = _value(duration_metric, "p(95)")
    p99_ms = _value(duration_metric, "p(99)")
    check_rate = _value(checks_metric, "rate")

    business_duration = _metric(summary, 'g20_business_duration')
    business_avg = _value(business_duration, 'avg')
    business_p95 = _value(business_duration, 'p(95)')
    business_p99 = _value(business_duration, 'p(99)')
    business_failure = _value(_metric(summary, 'g20_business_failure'), 'rate')
    business_requests = _count(_value(_metric(summary, 'g20_business_requests'), 'count'))
    business_users = _count(_value(_metric(summary, 'g20_business_users'), 'count'))
    samples = _count(_value(_metric(summary, 'g20_hold_samples'), 'count'))
    min_vus = _value(_metric(summary, 'g20_hold_vus'), 'min')
    max_vus = _value(_metric(summary, 'g20_hold_vus'), 'max')
    first_sample = _value(_metric(summary, 'g20_hold_elapsed_seconds'), 'min')
    last_sample = _value(_metric(summary, 'g20_hold_elapsed_seconds'), 'max')
    hold = _value({'values': {'seconds': summary.get('holdSeconds')}}, 'seconds')
    average_ok = (avg_ms is not None and business_avg is not None
                  and avg_ms <= MAX_AVERAGE_MS and business_avg <= MAX_AVERAGE_MS)
    concurrency_ok = (hold is not None and hold >= MIN_HOLD_SECONDS
                      and min_vus is not None and max_vus is not None and min_vus >= vus and max_vus >= min_vus
                      and first_sample is not None and last_sample is not None
                      and first_sample <= 3 and hold - 3 <= last_sample <= hold
                      and last_sample - first_sample >= hold * .9
                      and samples >= vus and business_users == vus and business_requests >= business_users)
    limits = _mapping(summary.get('operationalThresholds'))
    p95_limit = _value({'values': limits}, 'p95Ms')
    p99_limit = _value({'values': limits}, 'p99Ms')
    error_limit = _value({'values': limits}, 'maxErrorRate')
    limits_ok = (p95_limit is not None and p99_limit is not None and error_limit is not None
                 and p95_limit > 0 and p99_limit >= p95_limit and 0 < error_limit <= 1)
    actual_limits_ok = (limits_ok and all(value is not None for value in
                        (p95_ms, p99_ms, failed_rate, check_rate, business_p95, business_p99, business_failure))
                        and p95_ms < p95_limit and p99_ms < p99_limit
                        and business_p95 < p95_limit and business_p99 < p99_limit
                        and failed_rate < error_limit and business_failure < error_limit and check_rate >= 1 - error_limit)
    required_checks = {}
    if limits_ok:
        required_checks = {
            'http_req_failed': [f'rate<{error_limit:g}'],
            'http_req_duration': [f'p(95)<{p95_limit:g}', f'p(99)<{p99_limit:g}'],
            'g20_business_duration': ['avg<=3000', f'p(95)<{p95_limit:g}', f'p(99)<{p99_limit:g}'],
            'g20_business_failure': [f'rate<{error_limit:g}'],
            'g20_hold_vus': [f'min>={vus}'],
        }
    statuses = _mapping(summary.get('thresholdStatus'))
    required_thresholds_ok = bool(required_checks) and all(
        _mapping(statuses.get(metric)).get(expression) is True
        for metric, expressions in required_checks.items() for expression in expressions)

    procurement_scale = vus >= MIN_PROCUREMENT_VUS
    evidence_complete = (request_count > 0 and business_requests > 0 and limits_ok
                         and all(value is not None for value in (failed_rate, avg_ms, p95_ms, p99_ms, check_rate,
                                 business_avg, business_p95, business_p99, business_failure, min_vus, max_vus,
                                 first_sample, last_sample, hold)))
    qualified = (
        procurement_scale
        and ack
        and auth
        and identity_pool_ok
        and business
        and threshold_ok
        and evidence_complete
        and schema_ok
        and required_thresholds_ok
        and actual_limits_ok
        and average_ok
        and concurrency_ok
    )

    if qualified:
        verdict = "PASS"
    elif not procurement_scale:
        verdict = "SMOKE_ONLY"
    elif not ack or not auth or not business:
        verdict = "FAIL_CONFIG"
    elif not schema_ok:
        verdict = "FAIL_EVIDENCE"
    elif not identity_pool_ok:
        verdict = "FAIL_IDENTITY_POOL"
    elif not evidence_complete:
        verdict = "FAIL_EVIDENCE"
    elif not concurrency_ok:
        verdict = "FAIL_CONCURRENCY"
    else:
        verdict = "FAIL_THRESHOLDS"

    return {
        "schemaVersion": 2,
        "gate": "G20",
        "verdict": verdict,
        "g20Qualified": qualified,
        "procurementMinimumVus": MIN_PROCUREMENT_VUS,
        "requestedVus": vus,
        "realRunAcknowledged": ack,
        "authConfigured": auth,
        "authIdentityCount": auth_identity_count,
        "identityPoolMatchesVus": identity_pool_ok,
        "businessScenarioConfigured": business,
        "configuredPaths": paths,
        "businessPaths": business_paths,
        "thresholdsPassed": threshold_ok,
        "requiredThresholdsPassed": required_thresholds_ok,
        "actualMetricsWithinThresholds": bool(actual_limits_ok),
        "fixedAverageRequirementPassed": average_ok,
        "identityVerificationPassed": identity_pool_ok,
        "concurrencyObservationPassed": concurrency_ok,
        "concurrency": {'holdSeconds': hold, 'minimumHoldVus': min_vus, 'maximumHoldVus': max_vus,
                        'firstSampleSeconds': first_sample, 'lastSampleSeconds': last_sample,
                        'samples': samples, 'successfulBusinessVus': business_users},
        "thresholdChecks": threshold_checks,
        "metrics": {
            "httpRequests": request_count,
            "requestsPerSecond": request_rate,
            "httpFailureRate": failed_rate,
            "averageResponseMs": avg_ms,
            "p95ResponseMs": p95_ms,
            "p99ResponseMs": p99_ms,
            "checkPassRate": check_rate,
            "businessAverageResponseMs": business_avg,
            "businessP95ResponseMs": business_p95,
            "businessP99ResponseMs": business_p99,
            "businessFailureRate": business_failure,
            "holdBusinessRequests": business_requests,
        },
        "sourceGeneratedAt": summary.get("generatedAt"),
        "target": summary.get("target"),
        "notes": [
            "SMOKE_ONLY is not procurement performance acceptance.",
            "5000 rows of seed/demo data are not accepted as 5000-user concurrency evidence.",
            "Formal PASS requires server-verified distinct accounts and one successful hold-stage business participant per requested VU.",
            "Mean response <=3000ms is fixed; healthy health-check requests cannot replace hold-stage business timing.",
            "60 seconds is the engineering observation minimum; the authorized school performance plan may require a longer window.",
            "PASS qualifies this measured performance run only. Annual 99.5% availability, filing, trial operation and complete G20 delivery remain separate evidence.",
        ],
    }


def self_test() -> dict[str, Any]:
    fake = {
        "schemaVersion": 2, "runMode": "single-generator", "holdSeconds": 60,
        "gate": "G20",
        "generator": "k6",
        "requestedVus": 5000,
        "realRunAcknowledged": True,
        "authConfigured": True,
        "authIdentityCount": 5000,
        "identityVerification": {"method": "server-auth-me", "endpoint": "/api/v1/auth/me",
                                 "verifiedTokenCount": 5000, "distinctAccountCount": 5000, "allVerified": True},
        "operationalThresholds": {"p95Ms": 1500, "p99Ms": 3000, "maxErrorRate": 0.01},
        "businessScenarioConfigured": True,
        "configuredPaths": ["/health", "/api/v1/internship/dashboard"],
        "businessPaths": ["/api/v1/internship/dashboard"],
        "thresholdStatus": {
            "http_req_failed": {"rate<0.01": True},
            "http_req_duration": {"p(95)<1500": True, "p(99)<3000": True},
            "g20_business_duration": {"avg<=3000": True, "p(95)<1500": True, "p(99)<3000": True},
            "g20_business_failure": {"rate<0.01": True},
            "g20_hold_vus": {"min>=5000": True},
        },
        "metrics": {
            "http_reqs": {"values": {"count": 10000, "rate": 1000.0}},
            "http_req_failed": {"values": {"rate": 0.001}},
            "http_req_duration": {"values": {"avg": 100.0, "p(95)": 300.0, "p(99)": 600.0}},
            "checks": {"values": {"rate": 0.999}},
            "g20_business_duration": {"values": {"avg": 100, "p(95)": 300, "p(99)": 600}},
            "g20_business_failure": {"values": {"rate": 0.001}},
            "g20_business_requests": {"values": {"count": 10000}},
            "g20_business_users": {"values": {"count": 5000}},
            "g20_hold_samples": {"values": {"count": 10000}},
            "g20_hold_vus": {"values": {"min": 5000, "max": 5000}},
            "g20_hold_elapsed_seconds": {"values": {"min": 0.01, "max": 59.99}},
        },
    }
    result = validate(fake)
    assert result["g20Qualified"] is True and result["verdict"] == "PASS"
    fake["authIdentityCount"] = 1
    shared = validate(fake)
    assert shared["g20Qualified"] is False and shared["verdict"] == "FAIL_IDENTITY_POOL"
    fake["requestedVus"] = 20
    smoke = validate(fake)
    assert smoke["g20Qualified"] is False and smoke["verdict"] == "SMOKE_ONLY"
    return {
        "ok": True,
        "testHarnessOnly": True,
        "qualifiedCase": result["verdict"],
        "sharedTokenCase": shared["verdict"],
        "smokeCase": smoke["verdict"],
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate G20 k6 procurement evidence")
    parser.add_argument("summary", nargs="?", type=Path, help="g20-k6-summary.json")
    parser.add_argument("--report", type=Path, help="write normalized procurement evidence JSON")
    parser.add_argument("--require-qualified", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.self_test:
        print(json.dumps(self_test(), ensure_ascii=False))
        return 0
    if args.summary is None:
        raise EvidenceError("summary path is required")
    summary = json.loads(args.summary.read_text(encoding="utf-8"))
    result = validate(summary)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if args.require_qualified and not result["g20Qualified"]:
        return 2
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (EvidenceError, json.JSONDecodeError, OSError, ValueError) as exc:
        print(json.dumps({"gate": "G20", "verdict": "ERROR", "error": str(exc)}, ensure_ascii=False))
        raise SystemExit(2)
