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
from pathlib import Path
from typing import Any


MIN_PROCUREMENT_VUS = 5000


class EvidenceError(RuntimeError):
    pass


def _metric(summary: dict[str, Any], name: str) -> dict[str, Any]:
    value = (summary.get("metrics") or {}).get(name)
    return value if isinstance(value, dict) else {}


def _value(metric: dict[str, Any], key: str) -> float | int | None:
    values = metric.get("values") or {}
    raw = values.get(key)
    return raw if isinstance(raw, (int, float)) else None


def thresholds_pass(summary: dict[str, Any]) -> tuple[bool, list[dict[str, Any]]]:
    statuses = summary.get("thresholdStatus") or {}
    checks: list[dict[str, Any]] = []
    if not statuses:
        return False, [{"metric": "*", "threshold": "*", "ok": False, "reason": "thresholdStatus missing"}]
    for metric, threshold_map in statuses.items():
        if not isinstance(threshold_map, dict) or not threshold_map:
            checks.append({"metric": metric, "threshold": "*", "ok": False})
            continue
        for threshold, ok in threshold_map.items():
            checks.append({"metric": metric, "threshold": threshold, "ok": bool(ok)})
    return bool(checks) and all(item["ok"] for item in checks), checks


def validate(summary: dict[str, Any]) -> dict[str, Any]:
    if summary.get("gate") != "G20" or summary.get("generator") != "k6":
        raise EvidenceError("not a G20 k6 evidence document")

    vus = int(summary.get("requestedVus") or 0)
    paths = [str(item) for item in (summary.get("configuredPaths") or [])]
    business_paths = [str(item) for item in (summary.get("businessPaths") or [])]
    ack = bool(summary.get("realRunAcknowledged"))
    auth = bool(summary.get("authConfigured"))
    auth_identity_count = int(summary.get("authIdentityCount") or 0)
    identity_pool_ok = auth_identity_count >= vus if vus > 0 else False
    business = bool(summary.get("businessScenarioConfigured")) and bool(business_paths)
    threshold_ok, threshold_checks = thresholds_pass(summary)

    req_metric = _metric(summary, "http_reqs")
    failed_metric = _metric(summary, "http_req_failed")
    duration_metric = _metric(summary, "http_req_duration")
    checks_metric = _metric(summary, "checks")

    request_count = int(_value(req_metric, "count") or 0)
    request_rate = _value(req_metric, "rate")
    failed_rate = _value(failed_metric, "rate")
    avg_ms = _value(duration_metric, "avg")
    p95_ms = _value(duration_metric, "p(95)")
    p99_ms = _value(duration_metric, "p(99)")
    check_rate = _value(checks_metric, "rate")

    procurement_scale = vus >= MIN_PROCUREMENT_VUS
    evidence_complete = request_count > 0 and failed_rate is not None and avg_ms is not None and p95_ms is not None
    qualified = (
        procurement_scale
        and ack
        and auth
        and identity_pool_ok
        and business
        and threshold_ok
        and evidence_complete
    )

    if qualified:
        verdict = "PASS"
    elif not procurement_scale:
        verdict = "SMOKE_ONLY"
    elif not ack or not auth or not business:
        verdict = "FAIL_CONFIG"
    elif not identity_pool_ok:
        verdict = "FAIL_IDENTITY_POOL"
    elif not evidence_complete:
        verdict = "FAIL_EVIDENCE"
    else:
        verdict = "FAIL_THRESHOLDS"

    return {
        "schemaVersion": 1,
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
        "thresholdChecks": threshold_checks,
        "metrics": {
            "httpRequests": request_count,
            "requestsPerSecond": request_rate,
            "httpFailureRate": failed_rate,
            "averageResponseMs": avg_ms,
            "p95ResponseMs": p95_ms,
            "p99ResponseMs": p99_ms,
            "checkPassRate": check_rate,
        },
        "sourceGeneratedAt": summary.get("generatedAt"),
        "target": summary.get("target"),
        "notes": [
            "SMOKE_ONLY is not procurement performance acceptance.",
            "5000 rows of seed/demo data are not accepted as 5000-user concurrency evidence.",
            "Formal PASS requires at least one distinct authenticated test identity per requested VU; a shared single token is smoke evidence only.",
            "PASS means the supplied k6 run met the configured thresholds; school/tender SLA values must override operational defaults when formally specified.",
        ],
    }


def self_test() -> dict[str, Any]:
    fake = {
        "gate": "G20",
        "generator": "k6",
        "requestedVus": 5000,
        "realRunAcknowledged": True,
        "authConfigured": True,
        "authIdentityCount": 5000,
        "businessScenarioConfigured": True,
        "configuredPaths": ["/health", "/api/v1/internship/dashboard"],
        "businessPaths": ["/api/v1/internship/dashboard"],
        "thresholdStatus": {
            "http_req_failed": {"rate<0.01": True},
            "http_req_duration": {"p(95)<1500": True, "p(99)<3000": True},
        },
        "metrics": {
            "http_reqs": {"values": {"count": 10000, "rate": 1000.0}},
            "http_req_failed": {"values": {"rate": 0.001}},
            "http_req_duration": {"values": {"avg": 100.0, "p(95)": 300.0, "p(99)": 600.0}},
            "checks": {"values": {"rate": 0.999}},
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
