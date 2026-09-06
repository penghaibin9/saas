"""Read-only Academic V8.1 20K pagination/query-budget evidence.

The product Authority requires real dataset size, query count, EXPLAIN, p50/p95,
payload, memory/CPU and wall-clock evidence.  This probe never seeds or mutates
data: it runs representative production-shaped reads against ``sandbox-school``
and emits a machine-readable artifact.

The paired pytest scale contracts prove that the production services keep these
SQL shapes (server pagination, SQL aggregation and constant query count).  This
script supplies the real 20K MySQL execution evidence that source-only contracts
cannot provide.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import subprocess
import sys
import tracemalloc
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from statistics import median
from time import perf_counter, process_time
from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection, Engine, make_url


SANDBOX_TENANT_ID = 1_000_000_000_000_000_007
SANDBOX_TENANT_CODE = "sandbox-school"
RUNS = 25
WARMUPS = 3
LATENCY_P95_LIMIT_MS = 1_000.0  # repository capacity gate policy
PAYLOAD_LIMIT_BYTES = 32 * 1024  # existing 20K page-gate policy
PAGE_SCAN_LIMIT_ROWS = 5_000


@dataclass(frozen=True)
class Probe:
    name: str
    category: str
    sql: str
    page_limit: int | None
    scan_budget_rows: int | None
    note: str


PROBES = (
    Probe(
        "dashboard_ranked_todos",
        "dashboard/task-queue",
        """
        SELECT id, source_module, source_biz_type, source_biz_id, title, due_at, created_at
        FROM t_unified_todo
        WHERE tenant_id=:tid AND assignee_id=:assignee_id
          AND is_deleted=0 AND status='PENDING'
        ORDER BY (due_at IS NULL), due_at ASC, id DESC
        LIMIT 50
        """,
        50,
        PAGE_SCAN_LIMIT_ROWS,
        "Today First queue is ranked in MySQL and returns exact object ids.",
    ),
    Probe(
        "student_20k_keyset_page",
        "four-end-projection",
        """
        SELECT id, student_no, real_name, college_id, major_id, class_id, student_status
        FROM t_student_profile
        WHERE tenant_id=:tid AND is_deleted=0 AND id>:student_cursor
        ORDER BY id ASC
        LIMIT 100
        """,
        100,
        500,
        "20K student projection uses a keyset cursor and never materializes the school.",
    ),
    Probe(
        "schedule_staff_page",
        "schedule",
        """
        SELECT id, task_id, course_id, course_name, class_id, teacher_key,
               weekday, slot_no, start_week, end_week, status, version
        FROM t_aa_schedule_item
        WHERE tenant_id=:tid AND is_deleted=0 AND batch_id=:schedule_batch_id
        ORDER BY id DESC
        LIMIT 50
        """,
        50,
        PAGE_SCAN_LIMIT_ROWS,
        "Schedule administration stays server-paged.",
    ),
    Probe(
        "schedule_student_projection",
        "four-end-projection",
        """
        SELECT id, task_id, course_name, teacher_name, weekday, slot_no,
               start_week, end_week, classroom_text, version
        FROM t_aa_schedule_item
        WHERE tenant_id=:tid AND is_deleted=0 AND class_id=:class_id
        ORDER BY weekday ASC, slot_no ASC, id ASC
        LIMIT 100
        """,
        100,
        500,
        "Student PC/Mini schedule projection is bounded to the current class.",
    ),
    Probe(
        "registration_student_page",
        "registration",
        """
        SELECT id, batch_id, student_id, eligibility_status, status, version
        FROM t_aa_registration
        WHERE tenant_id=:tid AND is_deleted=0 AND student_id=:student_id
        ORDER BY id DESC
        LIMIT 50
        """,
        50,
        500,
        "Registration history is scoped to one student and paged by the server.",
    ),
    Probe(
        "selection_batch_page",
        "selection",
        """
        SELECT id, selection_course_id, course_id, course_name, student_id, status, version
        FROM t_aa_selection_record
        WHERE tenant_id=:tid AND is_deleted=0 AND batch_id=:selection_batch_id
        ORDER BY id DESC
        LIMIT 50
        """,
        50,
        500,
        "Selection records remain server-paged even when a future round grows.",
    ),
    Probe(
        "exam_student_projection",
        "exam",
        """
        SELECT id, exam_course_id, exam_room_id, student_id, seat_no,
               admission_no, attendance_status, version
        FROM t_aa_exam_room_student
        WHERE tenant_id=:tid AND is_deleted=0 AND student_id=:student_id
        ORDER BY id DESC
        LIMIT 50
        """,
        50,
        500,
        "Student PC/Mini exam projection is student-scoped and bounded.",
    ),
    Probe(
        "grade_student_projection",
        "grade",
        """
        SELECT id, task_id, student_id, total_score, pass_status, source, version_no, version
        FROM t_aa_grade_record
        WHERE tenant_id=:tid AND is_deleted=0 AND student_id=:student_id
        ORDER BY id DESC
        LIMIT 50
        """,
        50,
        500,
        "Student PC/Mini grade projection is student-scoped and bounded.",
    ),
    Probe(
        "grade_task_staff_page",
        "grade",
        """
        SELECT id, teaching_task_id, term_id, course_name, class_id, teacher_key,
               status, deadline_at, version
        FROM t_aa_grade_task
        WHERE tenant_id=:tid AND is_deleted=0 AND term_id=:grade_term_id
        ORDER BY id DESC
        LIMIT 50
        """,
        50,
        PAGE_SCAN_LIMIT_ROWS,
        "GradeTask queue is term-filtered and server-paged.",
    ),
    Probe(
        "warning_student_projection",
        "warning",
        """
        SELECT id, code, acad_student_id, warn_type, level, reason, owner,
               status, trigger_time, deadline, version
        FROM t_acad_warning
        WHERE tenant_id=:tid AND is_deleted=0 AND acad_student_id=:warning_student_id
        ORDER BY id DESC
        LIMIT 50
        """,
        50,
        500,
        "Warning handoff stays exact-student and bounded.",
    ),
    Probe(
        "formation_program_courses",
        "formation",
        """
        SELECT id, program_id, course_id, course_name, open_term_no,
               module, credit_snapshot, formation_mode, version
        FROM t_aa_program_course
        WHERE tenant_id=:tid AND is_deleted=0 AND program_id=:program_id
        ORDER BY open_term_no ASC, id ASC
        LIMIT 100
        """,
        100,
        500,
        "Formation reads one program version with a fixed payload budget.",
    ),
    Probe(
        "archive_precheck_server_aggregate",
        "archive",
        """
        SELECT 'REGISTRATION' AS domain, COUNT(*) AS record_count
          FROM t_aa_registration WHERE tenant_id=:tid AND is_deleted=0
        UNION ALL
        SELECT 'SCHEDULE', COUNT(*) FROM t_aa_schedule_item
          WHERE tenant_id=:tid AND is_deleted=0
        UNION ALL
        SELECT 'EXAM', COUNT(*) FROM t_aa_exam_room_student
          WHERE tenant_id=:tid AND is_deleted=0
        UNION ALL
        SELECT 'GRADE', COUNT(*) FROM t_aa_grade_record
          WHERE tenant_id=:tid AND is_deleted=0
        UNION ALL
        SELECT 'WARNING', COUNT(*) FROM t_acad_warning
          WHERE tenant_id=:tid AND is_deleted=0
        UNION ALL
        SELECT 'EVALUATION', COUNT(*) FROM t_aa_evaluation_record
          WHERE tenant_id=:tid AND is_deleted=0
        """,
        None,
        None,
        "Archive precheck aggregates in MySQL; only six counters cross the wire.",
    ),
    Probe(
        "stats_server_aggregate",
        "stats",
        """
        SELECT 'GRADE_TASK' AS domain, status, COUNT(*) AS record_count
          FROM t_aa_grade_task
          WHERE tenant_id=:tid AND is_deleted=0
          GROUP BY status
        UNION ALL
        SELECT 'WARNING', status, COUNT(*)
          FROM t_acad_warning
          WHERE tenant_id=:tid AND is_deleted=0
          GROUP BY status
        UNION ALL
        SELECT 'SCHEDULE', status, COUNT(*)
          FROM t_aa_schedule_item
          WHERE tenant_id=:tid AND is_deleted=0
          GROUP BY status
        """,
        None,
        None,
        "Stats grouping happens in MySQL; the frontend receives only grouped counters.",
    ),
)


DATASET_TABLES = (
    "t_student_profile",
    "t_unified_todo",
    "t_aa_course",
    "t_aa_program",
    "t_aa_program_course",
    "t_aa_registration",
    "t_aa_teaching_task",
    "t_aa_schedule_item",
    "t_aa_selection_record",
    "t_aa_exam_room_student",
    "t_aa_grade_task",
    "t_aa_grade_record",
    "t_acad_warning",
    "t_aa_evaluation_record",
    "t_aa_archive_batch",
    "t_aa_archive_item",
)


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Academic V8.1 read-only 20K performance audit")
    parser.add_argument("--output", required=True)
    parser.add_argument("--database-url", default="")
    parser.add_argument("--runs", type=int, default=RUNS)
    return parser.parse_args()


def _json_default(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    return str(value)


def _percentile(values: list[float], percentile: float) -> float:
    ordered = sorted(values)
    if not ordered:
        return math.nan
    rank = max(0, math.ceil(percentile * len(ordered)) - 1)
    return ordered[rank]


def _walk_plan(node: Any, tables: list[dict[str, Any]]) -> None:
    if isinstance(node, dict):
        table = node.get("table")
        if isinstance(table, dict):
            tables.append(table)
        for value in node.values():
            _walk_plan(value, tables)
    elif isinstance(node, list):
        for value in node:
            _walk_plan(value, tables)


def _explain(conn: Connection, probe: Probe, params: dict[str, Any]) -> dict[str, Any]:
    raw = conn.execute(text("EXPLAIN FORMAT=JSON " + probe.sql), params).scalar_one()
    plan = json.loads(raw) if isinstance(raw, str) else raw
    tables: list[dict[str, Any]] = []
    _walk_plan(plan, tables)
    details = []
    scanned = 0
    for table in tables:
        rows = table.get("rows_examined_per_scan", table.get("rows"))
        if rows is None:
            raise RuntimeError(f"{probe.name}: EXPLAIN omitted rows examined")
        rows = int(rows or 0)
        scanned += rows
        details.append(
            {
                "table": table.get("table_name"),
                "accessType": table.get("access_type"),
                "key": table.get("key"),
                "rowsExaminedPerScan": rows,
                "filteredPercent": table.get("filtered"),
            }
        )
    if not details:
        raise RuntimeError(f"{probe.name}: EXPLAIN contained no table plan")
    return {"rowsExamined": scanned, "tables": details}


def _session_counters(conn: Connection) -> dict[str, int]:
    names = {
        "Bytes_sent",
        "Handler_read_first",
        "Handler_read_key",
        "Handler_read_next",
        "Handler_read_prev",
        "Handler_read_rnd",
        "Handler_read_rnd_next",
        "Select_full_join",
        "Select_scan",
    }
    rows = conn.execute(text("SHOW SESSION STATUS")).all()
    return {str(name): int(value) for name, value in rows if str(name) in names}


def _delta(after: dict[str, int], before: dict[str, int]) -> dict[str, int]:
    return {name: int(after.get(name, 0) - before.get(name, 0)) for name in sorted(after)}


def _run_probe(
    conn: Connection, probe: Probe, params: dict[str, Any], runs: int
) -> dict[str, Any]:
    statement = text(probe.sql)
    for _ in range(WARMUPS):
        conn.execute(statement, params).mappings().all()

    before_status = _session_counters(conn)
    latencies: list[float] = []
    cpu_ms = 0.0
    payload_bytes = 0
    returned = 0
    peak_bytes = 0
    tracemalloc.start()
    wall_started = perf_counter()
    for _ in range(runs):
        cpu_started = process_time()
        started = perf_counter()
        rows = [dict(row) for row in conn.execute(statement, params).mappings().all()]
        latencies.append((perf_counter() - started) * 1_000)
        cpu_ms += (process_time() - cpu_started) * 1_000
        payload_bytes = len(
            json.dumps(rows, ensure_ascii=False, separators=(",", ":"), default=_json_default).encode("utf-8")
        )
        returned = len(rows)
        _, current_peak = tracemalloc.get_traced_memory()
        peak_bytes = max(peak_bytes, current_peak)
    wall_ms = (perf_counter() - wall_started) * 1_000
    tracemalloc.stop()
    after_status = _session_counters(conn)
    status_delta = _delta(after_status, before_status)
    handler_rows = sum(
        status_delta.get(name, 0)
        for name in (
            "Handler_read_first",
            "Handler_read_key",
            "Handler_read_next",
            "Handler_read_prev",
            "Handler_read_rnd",
            "Handler_read_rnd_next",
        )
    )
    handler_rows_per_run = handler_rows / runs
    plan = _explain(conn, probe, params)

    checks = {
        "singleStatementPerInvocation": True,
        "latencyP95UnderRepositoryLimit": _percentile(latencies, 0.95) < LATENCY_P95_LIMIT_MS,
        "payloadUnder32KiB": payload_bytes < PAYLOAD_LIMIT_BYTES,
        "pageResultBounded": probe.page_limit is None or returned <= probe.page_limit,
        # EXPLAIN rows are optimizer estimates and can be deliberately conservative
        # for range + LIMIT plans.  The session Handler_read delta is measured from
        # all real executions, so it is the authoritative bounded-read gate.
        "pageRowsReadWithinBudget": (
            probe.scan_budget_rows is None or handler_rows_per_run <= probe.scan_budget_rows
        ),
    }
    return {
        "name": probe.name,
        "category": probe.category,
        "note": probe.note,
        "runs": runs,
        "queryCountPerInvocation": 1,
        "returnedRows": returned,
        "pageLimit": probe.page_limit,
        "payloadBytes": payload_bytes,
        "latencyMs": {
            "min": round(min(latencies), 3),
            "p50": round(median(latencies), 3),
            "p95": round(_percentile(latencies, 0.95), 3),
            "max": round(max(latencies), 3),
        },
        "wallClockMsForAllRuns": round(wall_ms, 3),
        "processCpuMsForAllRuns": round(cpu_ms, 3),
        "peakPythonAllocatedBytes": peak_bytes,
        "sessionCounterDelta": status_delta,
        "actualHandlerRowsReadPerInvocation": round(handler_rows_per_run, 3),
        "explain": {
            **plan,
            "scanBudgetRows": probe.scan_budget_rows,
            "estimateWithinBudget": (
                probe.scan_budget_rows is None
                or plan["rowsExamined"] <= probe.scan_budget_rows
            ),
        },
        "checks": checks,
        "verdict": "PASS" if all(checks.values()) else "FAIL",
    }


def _scalar(conn: Connection, sql: str, params: dict[str, Any]) -> int:
    value = conn.execute(text(sql), params).scalar_one_or_none()
    if value is None:
        raise RuntimeError(f"discovery query returned no value: {sql.strip()[:80]}")
    return int(value)


def _dataset_counts(conn: Connection, tenant_id: int) -> dict[str, int]:
    return {
        table: _scalar(
            conn,
            f"SELECT COUNT(*) FROM `{table}` WHERE tenant_id=:tid AND is_deleted=0",
            {"tid": tenant_id},
        )
        for table in DATASET_TABLES
    }


def _discovery(conn: Connection, tenant_id: int) -> dict[str, int]:
    params = {"tid": tenant_id}
    student_row = conn.execute(
        text(
            """
            SELECT gr.student_id, sp.class_id
            FROM t_aa_grade_record gr
            JOIN t_student_profile sp
              ON sp.tenant_id=gr.tenant_id AND sp.id=gr.student_id AND sp.is_deleted=0
            WHERE gr.tenant_id=:tid AND gr.is_deleted=0
            GROUP BY gr.student_id, sp.class_id
            ORDER BY COUNT(*) DESC, gr.student_id ASC
            LIMIT 1
            """
        ),
        params,
    ).first()
    if not student_row:
        raise RuntimeError("sandbox tenant has no grade-backed student projection")
    student_id, class_id = map(int, student_row)
    return {
        "student_id": student_id,
        "class_id": class_id,
        "student_cursor": max(
            0,
            _scalar(
                conn,
                "SELECT MIN(id) FROM t_student_profile WHERE tenant_id=:tid AND is_deleted=0",
                params,
            )
            - 1,
        ),
        "assignee_id": _scalar(
            conn,
            """
            SELECT assignee_id FROM t_unified_todo
            WHERE tenant_id=:tid AND is_deleted=0 AND status='PENDING' AND assignee_id IS NOT NULL
            GROUP BY assignee_id ORDER BY COUNT(*) DESC, assignee_id ASC LIMIT 1
            """,
            params,
        ),
        "schedule_batch_id": _scalar(
            conn,
            """
            SELECT batch_id FROM t_aa_schedule_item
            WHERE tenant_id=:tid AND is_deleted=0
            GROUP BY batch_id ORDER BY COUNT(*) DESC, batch_id ASC LIMIT 1
            """,
            params,
        ),
        "selection_batch_id": _scalar(
            conn,
            """
            SELECT batch_id FROM t_aa_selection_record
            WHERE tenant_id=:tid AND is_deleted=0
            GROUP BY batch_id ORDER BY COUNT(*) DESC, batch_id ASC LIMIT 1
            """,
            params,
        ),
        "grade_term_id": _scalar(
            conn,
            """
            SELECT term_id FROM t_aa_grade_task
            WHERE tenant_id=:tid AND is_deleted=0
            GROUP BY term_id ORDER BY COUNT(*) DESC, term_id ASC LIMIT 1
            """,
            params,
        ),
        "program_id": _scalar(
            conn,
            """
            SELECT program_id FROM t_aa_program_course
            WHERE tenant_id=:tid AND is_deleted=0
            GROUP BY program_id ORDER BY COUNT(*) DESC, program_id ASC LIMIT 1
            """,
            params,
        ),
        "warning_student_id": _scalar(
            conn,
            """
            SELECT acad_student_id FROM t_acad_warning
            WHERE tenant_id=:tid AND is_deleted=0
            GROUP BY acad_student_id ORDER BY COUNT(*) DESC, acad_student_id ASC LIMIT 1
            """,
            params,
        ),
    }


def _head(backend_root: Path) -> str:
    return subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=backend_root.parent, text=True
    ).strip()


def _engine(database_url: str) -> tuple[Engine, dict[str, Any]]:
    parsed = make_url(database_url)
    if parsed.get_backend_name() != "mysql":
        raise SystemExit("D-GATE-AA-70 requires real MySQL")
    safe_target = {
        "driver": parsed.drivername,
        "host": parsed.host,
        "port": int(parsed.port or 3306),
        "database": parsed.database,
    }
    return create_engine(database_url, pool_pre_ping=True), safe_target


def main() -> int:
    args = _args()
    if args.runs < 5:
        raise SystemExit("--runs must be at least 5")
    backend_root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(backend_root))
    if args.database_url:
        database_url = args.database_url
    else:
        from app.core.config import settings

        database_url = settings.DATABASE_URL
    engine, safe_target = _engine(database_url)
    captured_at = datetime.now(timezone.utc).isoformat()

    with engine.connect() as conn:
        tenant = conn.execute(
            text("SELECT tenant_code FROM t_tenant WHERE id=:tid"),
            {"tid": SANDBOX_TENANT_ID},
        ).scalar_one_or_none()
        if tenant != SANDBOX_TENANT_CODE:
            raise SystemExit(f"refusing non-sandbox tenant: {tenant!r}")
        conn.execute(text("SET SESSION TRANSACTION READ ONLY"))
        conn.execute(text("START TRANSACTION READ ONLY"))
        read_only = bool(
            conn.execute(text("SELECT @@session.transaction_read_only")).scalar_one()
        )
        before_counts = _dataset_counts(conn, SANDBOX_TENANT_ID)
        discovery = _discovery(conn, SANDBOX_TENANT_ID)
        params = {"tid": SANDBOX_TENANT_ID, **discovery}
        cases = [_run_probe(conn, probe, params, args.runs) for probe in PROBES]
        after_counts = _dataset_counts(conn, SANDBOX_TENANT_ID)
        conn.rollback()

    checks = {
        "realMySQL": safe_target["driver"].startswith("mysql"),
        "sandboxTenantExact": tenant == SANDBOX_TENANT_CODE,
        "sessionReadOnly": read_only,
        "studentDatasetExactly20K": before_counts["t_student_profile"] == 20_000,
        "datasetUnchanged": before_counts == after_counts,
        "allCasesPass": all(case["verdict"] == "PASS" for case in cases),
        "allCategoriesCovered": {
            "dashboard/task-queue",
            "four-end-projection",
            "schedule",
            "registration",
            "selection",
            "exam",
            "grade",
            "warning",
            "formation",
            "archive",
            "stats",
        }.issubset({case["category"] for case in cases}),
    }
    verdict = "PASS" if all(checks.values()) else "FAIL"
    evidence = {
        "gate": "D-GATE-AA-70",
        "capturedAt": captured_at,
        "gitHead": _head(backend_root),
        "target": safe_target,
        "tenant": {"id": str(SANDBOX_TENANT_ID), "code": SANDBOX_TENANT_CODE},
        "policies": {
            "runsPerCase": args.runs,
            "warmupsPerCase": WARMUPS,
            "latencyP95LimitMs": LATENCY_P95_LIMIT_MS,
            "payloadLimitBytes": PAYLOAD_LIMIT_BYTES,
            "defaultPageExplainScanLimitRows": PAGE_SCAN_LIMIT_ROWS,
        },
        "datasetCountsBefore": before_counts,
        "datasetCountsAfter": after_counts,
        "discovery": discovery,
        "cases": cases,
        "checks": checks,
        "verdict": verdict,
    }
    output = Path(args.output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2, default=_json_default) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "gate": evidence["gate"],
                "gitHead": evidence["gitHead"],
                "studentCount": before_counts["t_student_profile"],
                "caseCount": len(cases),
                "maxP95Ms": max(case["latencyMs"]["p95"] for case in cases),
                "maxPayloadBytes": max(case["payloadBytes"] for case in cases),
                "failedCases": [case["name"] for case in cases if case["verdict"] != "PASS"],
                "checks": checks,
                "verdict": verdict,
                "output": str(output),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if verdict == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
