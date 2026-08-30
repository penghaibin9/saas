#!/usr/bin/env python3
"""Read-only 20K evidence runner for the Internship V8 hot paths.

The runner refuses to certify a dataset below ``--minimum-records``.  It records service query
count, p50/p95, serialized payload size, Python peak allocation and MySQL JSON EXPLAIN evidence.
It never creates data or changes schema; use only against an explicitly prepared test/staging
tenant and batch.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import json
from pathlib import Path
import statistics
import sys
import time
import tracemalloc

import _mysql_env  # noqa: F401

from sqlalchemy import event, text


SERVICE_BUDGETS = {
    "staff_dashboard": {"queries": 18, "p95_ms": 1000, "payload_bytes": 512_000, "peak_bytes": 64_000_000},
    "weekly_queue": {"queries": 4, "p95_ms": 800, "payload_bytes": 512_000, "peak_bytes": 32_000_000},
    "exception_queue": {"queries": 4, "p95_ms": 800, "payload_bytes": 512_000, "peak_bytes": 32_000_000},
    "material_center": {"queries": 4, "p95_ms": 1000, "payload_bytes": 512_000, "peak_bytes": 64_000_000},
    "archive_ledger": {"queries": 4, "p95_ms": 800, "payload_bytes": 512_000, "peak_bytes": 32_000_000},
}


EXPLAIN_QUERIES = (
    {
        "name": "dashboard_flow",
        "budget_rows": 25_000,
        "sql": """
            SELECT status, COUNT(*) FROM t_internship_record
            WHERE tenant_id=:tid AND batch_id=:bid AND is_deleted=0
            GROUP BY status
        """,
    },
    {
        "name": "weekly_queue",
        "budget_rows": 100_000,
        "sql": """
            SELECT w.id, r.id, s.id FROM t_weekly_report w
            JOIN t_internship_record r ON r.id=w.internship_id
            JOIN t_student_profile s ON s.id=r.student_id
            WHERE w.tenant_id=:tid AND w.is_deleted=0 AND w.status='PENDING_REVIEW'
              AND r.tenant_id=:tid AND r.batch_id=:bid AND r.is_deleted=0 AND s.is_deleted=0
            ORDER BY w.submitted_at IS NULL, w.submitted_at DESC, w.id DESC LIMIT 20
        """,
    },
    {
        "name": "exception_queue",
        "budget_rows": 100_000,
        "sql": """
            SELECT e.id, r.id, s.id FROM t_attendance_exception e
            JOIN t_internship_record r ON r.id=e.internship_id
            JOIN t_student_profile s ON s.id=r.student_id
            WHERE e.tenant_id=:tid AND e.is_deleted=0 AND e.status='PENDING_HANDLE'
              AND r.tenant_id=:tid AND r.batch_id=:bid AND r.is_deleted=0 AND s.is_deleted=0
            ORDER BY e.exception_date DESC, e.id DESC LIMIT 20
        """,
    },
    {
        "name": "material_center",
        "budget_rows": 200_000,
        "sql": """
            SELECT r.id, s.id, COALESCE(m.material_count, 0) AS material_count
            FROM t_internship_record r JOIN t_student_profile s ON s.id=r.student_id
            LEFT JOIN (
              SELECT fb.student_id, COUNT(fb.id) AS material_count
              FROM t_file_binding fb
              JOIN t_file_asset fa ON fa.id=fb.asset_id
              JOIN t_file_version fv ON fv.id=fb.version_id
              JOIN t_file_object fo ON fo.id=fb.file_id
              WHERE fb.tenant_id=:tid AND fa.tenant_id=:tid AND fv.tenant_id=:tid
                AND fo.tenant_id=:tid AND fb.module_code='INTERNSHIP'
                AND fb.batch_id=CAST(:bid AS CHAR) AND fb.is_current=1
                AND fb.status='ACTIVE' AND fb.is_deleted=0 AND fa.is_deleted=0
                AND fv.is_current=1 AND fv.is_deleted=0 AND fo.is_deleted=0
              GROUP BY fb.student_id
            ) m ON m.student_id=r.student_id
            WHERE r.tenant_id=:tid AND r.batch_id=:bid AND r.is_deleted=0 AND s.is_deleted=0
            ORDER BY r.id DESC LIMIT 20
        """,
    },
    {
        "name": "archive_ledger",
        "budget_rows": 50_000,
        "sql": """
            SELECT r.id, s.id, a.status, a.completeness
            FROM t_internship_record r JOIN t_student_profile s ON s.id=r.student_id
            LEFT JOIN t_internship_archive a ON a.tenant_id=:tid
              AND a.internship_id=r.id AND a.is_deleted=0
            WHERE r.tenant_id=:tid AND r.batch_id=:bid AND r.is_deleted=0 AND s.is_deleted=0
            ORDER BY r.id DESC LIMIT 20
        """,
    },
)


def percentile(values: list[float], ratio: float) -> float:
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, int(len(ordered) * ratio + 0.999999) - 1))
    return ordered[index]


@contextmanager
def query_counter(engine):
    state = {"count": 0}

    def before_cursor_execute(*_args, **_kwargs):
        state["count"] += 1

    event.listen(engine, "before_cursor_execute", before_cursor_execute)
    try:
        yield state
    finally:
        event.remove(engine, "before_cursor_execute", before_cursor_execute)


def json_bytes(value) -> int:
    return len(json.dumps(value, ensure_ascii=False, default=str, separators=(",", ":")).encode("utf-8"))


def benchmark(engine, fn, *, iterations: int, budget: dict) -> dict:
    fn()  # warm caches and import paths; evidence only includes the measured calls below
    latencies: list[float] = []
    query_counts: list[int] = []
    payload_sizes: list[int] = []
    tracemalloc.start()
    try:
        for _ in range(iterations):
            with query_counter(engine) as count:
                started = time.perf_counter()
                value = fn()
                latencies.append((time.perf_counter() - started) * 1000)
            query_counts.append(count["count"])
            payload_sizes.append(json_bytes(value))
        _current, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    actual = {
        "iterations": iterations,
        "queryCountMin": min(query_counts),
        "queryCountMax": max(query_counts),
        "p50Ms": round(statistics.median(latencies), 3),
        "p95Ms": round(percentile(latencies, 0.95), 3),
        "payloadBytesMax": max(payload_sizes),
        "pythonPeakBytes": peak,
    }
    checks = {
        "queryCount": actual["queryCountMax"] <= budget["queries"],
        "p95": actual["p95Ms"] <= budget["p95_ms"],
        "payload": actual["payloadBytesMax"] <= budget["payload_bytes"],
        "memory": actual["pythonPeakBytes"] <= budget["peak_bytes"],
    }
    return {**actual, "budget": budget, "checks": checks, "passed": all(checks.values())}


def walk_tables(node, output: list[dict]) -> list[dict]:
    if isinstance(node, dict):
        if isinstance(node.get("table"), dict):
            output.append(node["table"])
        for value in node.values():
            walk_tables(value, output)
    elif isinstance(node, list):
        for value in node:
            walk_tables(value, output)
    return output


def rows_examined(table: dict, query_name: str) -> int:
    for key in ("rows_examined_per_scan", "rows"):
        if key in table:
            return int(table[key] or 0)
    raise RuntimeError(f"{query_name}: EXPLAIN did not expose rows examined; refusing a false pass")


def explain(conn, tenant_id: int, batch_id: int) -> list[dict]:
    results = []
    for spec in EXPLAIN_QUERIES:
        raw = conn.execute(
            text("EXPLAIN FORMAT=JSON " + spec["sql"]),
            {"tid": tenant_id, "bid": batch_id},
        ).scalar_one()
        plan = json.loads(raw) if isinstance(raw, str) else raw
        tables = walk_tables(plan, [])
        if not tables:
            raise RuntimeError(f"{spec['name']}: EXPLAIN returned no table nodes")
        details = []
        total_rows = 0
        for table in tables:
            count = rows_examined(table, spec["name"])
            total_rows += count
            details.append({
                "table": table.get("table_name"),
                "accessType": table.get("access_type"),
                "key": table.get("key"),
                "rowsExaminedPerScan": count,
                "usingFilesort": bool(table.get("using_filesort")),
                "usingTemporaryTable": bool(table.get("using_temporary_table")),
            })
        results.append({
            "name": spec["name"],
            "budgetRows": spec["budget_rows"],
            "rowsExamined": total_rows,
            "withinBudget": total_rows <= spec["budget_rows"],
            "tables": details,
        })
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description="Internship V8 20K read-path evidence")
    parser.add_argument("--tenant-id", type=int, required=True)
    parser.add_argument("--batch-id", type=int, required=True)
    parser.add_argument("--minimum-records", type=int, default=20_000)
    parser.add_argument("--iterations", type=int, default=10)
    parser.add_argument("--json-out", required=True)
    args = parser.parse_args()
    if args.iterations < 5:
        parser.error("--iterations must be at least 5")

    from app.core.context import get_current_user_ctx, get_tenant, set_current_user, set_tenant
    from app.db.session import get_engine
    from app.modules.internship.services import internship_archive_service as archive
    from app.modules.internship.services import internship_material_center_service as material
    from app.modules.internship.services import internship_service

    engine = get_engine()
    with engine.connect() as conn:
        dataset_records = int(conn.scalar(text("""
            SELECT COUNT(*) FROM t_internship_record
            WHERE tenant_id=:tid AND batch_id=:bid AND is_deleted=0
        """), {"tid": args.tenant_id, "bid": args.batch_id}) or 0)
        if dataset_records < args.minimum_records:
            print(
                f"[internship-v8-scale] dataset={dataset_records}, required={args.minimum_records}; "
                "refusing 20K certification",
                file=sys.stderr,
            )
            return 2
        explain_results = explain(conn, args.tenant_id, args.batch_id)

    actor = {
        "userId": "internship-v8-scale-readonly",
        "realName": "Internship V8 Scale Probe",
        "currentRoleCode": "SCHOOL_ADMIN",
        "userType": "ADMIN",
        "tenantId": str(args.tenant_id),
        "permissionPatterns": ["*"],
    }
    previous_tenant = get_tenant()
    previous_user = get_current_user_ctx()
    set_tenant({"tenantId": str(args.tenant_id), "tenantCode": "internship-v8-scale"})
    set_current_user(actor)
    try:
        calls = {
            "staff_dashboard": lambda: internship_service.get_dashboard_summary(
                user=actor, batch_id=args.batch_id),
            "weekly_queue": lambda: internship_service.list_weekly_reports(
                1, 20, status="PENDING_REVIEW", batch_id=args.batch_id, user=actor),
            "exception_queue": lambda: internship_service.list_attendance_exceptions(
                1, 20, status="PENDING_HANDLE", batch_id=args.batch_id, user=actor),
            "material_center": lambda: material.list_center(
                1, 20, batch_id=args.batch_id, user=actor),
            "archive_ledger": lambda: archive.list_by_student(
                1, 20, batch_id=args.batch_id, user=actor),
        }
        service_results = {
            name: benchmark(engine, fn, iterations=args.iterations, budget=SERVICE_BUDGETS[name])
            for name, fn in calls.items()
        }
    finally:
        set_tenant(previous_tenant)
        set_current_user(previous_user)

    payload = {
        "schema": "internship-v8-scale-evidence/1",
        "tenantId": str(args.tenant_id),
        "batchId": str(args.batch_id),
        "dataset": {"internshipRecords": dataset_records, "minimumRequired": args.minimum_records},
        "services": service_results,
        "explain": explain_results,
        "browserEvidence": "SEPARATE_MEASURE_INTERNSHIP_V8_BROWSER_ARTIFACT_REQUIRED",
    }
    payload["passed"] = (
        all(item["passed"] for item in service_results.values())
        and all(item["withinBudget"] for item in explain_results)
    )
    output = Path(args.json_out).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[internship-v8-scale] dataset={dataset_records} passed={payload['passed']} artifact={output}")
    return 0 if payload["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
