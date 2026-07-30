#!/usr/bin/env python3
"""Probe health, readiness and process metrics without leaking the ops token."""
from __future__ import annotations

import argparse
import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


def _get_json(url: str, token: str | None = None) -> tuple[int, dict[str, Any]]:
    headers = {"Accept": "application/json", "User-Agent": "Yueke-Observability-Probe/1.0"}
    if token:
        headers["X-Ops-Token"] = token
    request = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=10) as response:  # noqa: S310
            return int(response.status), json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        body = error.read().decode("utf-8", errors="replace")
        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            payload = {"message": body[:200]}
        return int(error.code), payload


def _unwrap(payload: dict[str, Any]) -> dict[str, Any]:
    data = payload.get("data")
    return data if isinstance(data, dict) else payload


def probe(base_url: str, token: str, samples: int, interval: float) -> dict[str, Any]:
    base = base_url.rstrip("/")
    health_status, health_payload = _get_json(f"{base}/health")
    ready_status, ready_payload = _get_json(f"{base}/health/ready", token)
    ready = _unwrap(ready_payload)
    metrics_samples: list[dict[str, Any]] = []
    for index in range(samples):
        status, payload = _get_json(f"{base}/internal/metrics", token)
        metrics_samples.append({"status": status, "data": _unwrap(payload)})
        if index + 1 < samples:
            time.sleep(interval)

    checks = ready.get("checks") if isinstance(ready.get("checks"), dict) else {}
    latest_metrics = metrics_samples[-1]["data"] if metrics_samples else {}
    required_metric_keys = {"sampleSize", "latencyMs", "statuses", "slowRequests", "topRoutes"}
    missing_metric_keys = sorted(required_metric_keys - set(latest_metrics))
    ready_ok = (
        ready_status == 200
        and ready.get("status") == "READY"
        and all(isinstance(value, dict) and value.get("ok") for value in checks.values())
    )
    metrics_ok = all(item["status"] == 200 for item in metrics_samples) and not missing_metric_keys
    result = {
        "ok": health_status == 200 and ready_ok and metrics_ok,
        "health": {"statusCode": health_status, "status": _unwrap(health_payload).get("status")},
        "readiness": {
            "statusCode": ready_status,
            "status": ready.get("status"),
            "checks": {key: bool(value.get("ok")) for key, value in checks.items() if isinstance(value, dict)},
        },
        "metrics": {
            "samples": len(metrics_samples),
            "missingKeys": missing_metric_keys,
            "latest": latest_metrics,
        },
    }
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe readiness and internal metrics")
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--token-env", default="INTERNAL_OPS_TOKEN")
    parser.add_argument("--samples", type=int, default=3)
    parser.add_argument("--interval", type=float, default=1.0)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if not args.base_url.startswith("https://") and not args.base_url.startswith("http://localhost"):
        raise SystemExit("Remote probes require HTTPS")
    token = os.getenv(args.token_env, "").strip()
    if len(token) < 16:
        raise SystemExit(f"Missing or weak ops token in environment variable {args.token_env}")
    result = probe(args.base_url, token, max(1, args.samples), max(0.0, args.interval))
    text = json.dumps(result, ensure_ascii=False, indent=2)
    print(text)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text + "\n", encoding="utf-8")
    raise SystemExit(0 if result["ok"] else 1)


if __name__ == "__main__":
    main()
