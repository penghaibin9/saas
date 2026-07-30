#!/usr/bin/env python3
"""Fail-closed audit for production capacity settings.

Run from repository root or backend directory after production environment variables are loaded:
    python performance/tools/audit_capacity_runtime.py

No secret values or full connection strings are printed.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


def _load_settings():
    root = Path(__file__).resolve().parents[2]
    backend = root / "backend"
    sys.path.insert(0, str(backend))
    os.chdir(backend)
    from app.core.config import settings  # noqa: PLC0415
    return settings


def _check(name: str, ok: bool, message: str, *, severity: str = "error") -> dict:
    return {"name": name, "ok": bool(ok), "severity": severity, "message": message}


def build_report(*, allow_non_production: bool = False) -> dict:
    settings = _load_settings()
    workers = max(1, int(settings.WEB_CONCURRENCY or 1))
    pool_size = max(0, int(settings.DB_POOL_SIZE or 0))
    overflow = max(0, int(settings.DB_MAX_OVERFLOW or 0))
    peak_connections = workers * (pool_size + overflow)
    budget = max(0, int(os.getenv("CAPACITY_DB_CONNECTION_BUDGET", "0") or 0))
    database_url = str(settings.DATABASE_URL or "").strip().lower()
    redis_url = str(settings.REDIS_URL or "").strip()
    ops_token = str(settings.INTERNAL_OPS_TOKEN or "").strip()
    scaled = workers > 1 or bool(settings.MULTI_INSTANCE)

    checks = [
        _check(
            "production_mode",
            allow_non_production or (settings.APP_ENV == "production" and settings.DEPLOYMENT_MODE == "production"),
            "APP_ENV and DEPLOYMENT_MODE must both be production",
        ),
        _check("real_mysql", bool(settings.DB_ENABLED) and database_url.startswith("mysql"),
               "DB_ENABLED=true and DATABASE_URL must use MySQL"),
        _check("redis_enabled", bool(redis_url),
               "REDIS_URL is required before capacity validation"),
        _check("scaled_runtime", scaled,
               "WEB_CONCURRENCY must be >1 or MULTI_INSTANCE=true"),
        _check("multi_instance_redis", not settings.MULTI_INSTANCE or bool(redis_url),
               "MULTI_INSTANCE requires Redis-backed shared state"),
        _check("external_scheduler", not scaled or settings.SCHEDULER_MODE == "external",
               "scaled runtime requires SCHEDULER_MODE=external"),
        _check("ops_token", len(ops_token) >= 16,
               "INTERNAL_OPS_TOKEN must be configured for readiness and metrics probes"),
        _check("db_pool", pool_size > 0 and overflow >= 0,
               "DB_POOL_SIZE must be positive and DB_MAX_OVERFLOW non-negative"),
        _check("slow_query_threshold", 0 < int(settings.SLOW_QUERY_MS) <= 500,
               "SLOW_QUERY_MS should be between 1 and 500ms", severity="warning"),
        _check("slow_request_threshold", 0 < int(settings.HTTP_SLOW_REQUEST_MS) <= 1000,
               "HTTP_SLOW_REQUEST_MS should be between 1 and 1000ms", severity="warning"),
    ]
    if budget:
        checks.append(_check(
            "db_connection_budget",
            peak_connections <= budget,
            f"worker peak connection budget: calculated={peak_connections}, configured={budget}",
        ))
    else:
        checks.append(_check(
            "db_connection_budget",
            False,
            f"CAPACITY_DB_CONNECTION_BUDGET is not set; calculated worker peak={peak_connections}",
            severity="warning",
        ))

    errors = [item for item in checks if not item["ok"] and item["severity"] == "error"]
    warnings = [item for item in checks if not item["ok"] and item["severity"] == "warning"]
    return {
        "ok": not errors,
        "summary": {
            "workers": workers,
            "multiInstance": bool(settings.MULTI_INSTANCE),
            "schedulerMode": settings.SCHEDULER_MODE,
            "redisConfigured": bool(redis_url),
            "dbPoolSize": pool_size,
            "dbMaxOverflow": overflow,
            "calculatedPeakDbConnections": peak_connections,
            "dbConnectionBudget": budget or None,
        },
        "errors": errors,
        "warnings": warnings,
        "checks": checks,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit production capacity runtime settings")
    parser.add_argument("--allow-non-production", action="store_true",
                        help="skip the production mode assertion for staging dry runs")
    parser.add_argument("--json", action="store_true", help="emit compact JSON")
    args = parser.parse_args()
    report = build_report(allow_non_production=args.allow_non_production)
    print(json.dumps(report, ensure_ascii=False, indent=None if args.json else 2))
    raise SystemExit(0 if report["ok"] else 1)


if __name__ == "__main__":
    main()
