"""Graduation V8 W14: prove the student topic catalog stays bounded at 20K rows.

This gate is intentionally restricted to the dedicated Graduation V8 database.
It seeds deterministic scale-only rows, calls the production service, and writes
machine-readable timing/query/payload evidence.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter

from sqlalchemy import event, text
from sqlalchemy.engine import make_url


TENANT_ID = 1000000000000000001
ROW_COUNT = 20_000
MARKER = "V8SCALE-"


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database-url", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--batch-id", type=int, default=1)
    return parser.parse_args()


def _assert_isolated_database(database_url: str) -> None:
    parsed = make_url(database_url)
    if parsed.get_backend_name() != "mysql":
        raise SystemExit("W14 scale gate requires the isolated MySQL database")
    if parsed.database != "graduation_v8_e2e" or int(parsed.port or 3306) != 43319:
        raise SystemExit("Refusing to seed outside graduation_v8_e2e on port 43319")


def _seed(engine, batch_id: int) -> float:
    started = perf_counter()
    insert_sql = text("""
        INSERT INTO t_gd_topic (
          batch_id, topic_no, title, source, source_type, advisor_name,
          college_id, major_id, major_name, category, difficulty,
          requirements, outcome, skills, capacity, selected,
          review_status, status, tenant_id, updated_at, is_deleted,
          version, created_at
        ) VALUES (
          :batch_id, :topic_no, :title, '教师申报', 'TEACHER', :advisor_name,
          'V8-COLLEGE', 'V8-MAJOR', 'V8 规模专业', :category, 'MEDIUM',
          :requirements, '完成可验证成果', 'Python,SQL', 5, :selected,
          'APPROVED', 'CONFIRMED', :tenant_id, UTC_TIMESTAMP(), 0,
          0, UTC_TIMESTAMP()
        )
    """)
    with engine.begin() as conn:
        conn.execute(text("""
            DELETE FROM t_gd_topic
            WHERE tenant_id = :tenant_id AND batch_id = :batch_id
              AND topic_no LIKE 'V8SCALE-%'
        """), {"tenant_id": TENANT_ID, "batch_id": batch_id})
        for start in range(0, ROW_COUNT, 1_000):
            values = []
            for index in range(start, min(start + 1_000, ROW_COUNT)):
                values.append({
                    "batch_id": batch_id,
                    "topic_no": f"{MARKER}{index:05d}",
                    "title": f"V8 规模题目 {index:05d}" + (" keyword-needle" if index == 19_999 else ""),
                    "advisor_name": f"规模导师 {index % 100:02d}",
                    "category": ("应用开发", "数据分析", "智能制造", "文化创意")[index % 4],
                    "requirements": f"第 {index:05d} 项精简要求",
                    "selected": index % 5,
                    "tenant_id": TENANT_ID,
                })
            conn.execute(insert_sql, values)
    return round((perf_counter() - started) * 1000, 2)


def main() -> None:
    args = _arguments()
    _assert_isolated_database(args.database_url)
    os.environ.update({
        "APP_ENV": "development",
        "DB_ENABLED": "true",
        "DATABASE_URL": args.database_url,
        "DEFAULT_TENANT_CODE": "demo",
    })
    backend_root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(backend_root))

    from app.core.context import set_current_user, set_tenant
    from app.db.session import get_engine
    from app.services.mobile_student_service import graduation_topics

    set_tenant({"tenantId": str(TENANT_ID), "tenantCode": "demo"})
    user = {"userType": "STUDENT", "tenantId": str(TENANT_ID), "userId": "v8-scale-student"}
    set_current_user(user)
    engine = get_engine()
    seed_ms = _seed(engine, args.batch_id)

    statements: list[str] = []

    def record_query(_conn, _cursor, statement, _parameters, _context, _executemany):
        statements.append(" ".join(statement.split()))

    event.listen(engine, "before_cursor_execute", record_query)
    cases = []

    def run_case(name: str, **params):
        statements.clear()
        started = perf_counter()
        result = graduation_topics(user, batch_id=str(args.batch_id), **params)
        elapsed_ms = round((perf_counter() - started) * 1000, 2)
        payload_bytes = len(json.dumps(result, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
        case = {
            "name": name,
            "elapsedMs": elapsed_ms,
            "queryCount": len(statements),
            "returned": len(result["items"]),
            "total": result["total"],
            "hasMore": result["hasMore"],
            "nextCursorPresent": bool(result["nextCursor"]),
            "payloadBytes": payload_bytes,
            "attachmentHistoryFields": sum(
                1 for item in result["items"] for key in item
                if "attachment" in key.lower() or "history" in key.lower()
            ),
        }
        cases.append(case)
        return result

    first = run_case("first-page", page_size=30)
    second = run_case("cursor-next-page", cursor=first["nextCursor"], page_size=30)
    keyword = run_case("keyword-sql", keyword="keyword-needle", page_size=20)
    category = run_case("category-sql", category="数据分析", page_size=20)
    advisor = run_case("advisor-sql", advisor="规模导师 42", page_size=20)
    event.remove(engine, "before_cursor_execute", record_query)

    first_ids = {item["id"] for item in first["items"]}
    second_ids = {item["id"] for item in second["items"]}
    seeded = engine.connect().execute(text("""
        SELECT COUNT(*) FROM t_gd_topic
        WHERE tenant_id = :tenant_id AND batch_id = :batch_id
          AND topic_no LIKE 'V8SCALE-%'
    """), {"tenant_id": TENANT_ID, "batch_id": args.batch_id}).scalar_one()
    checks = {
        "seededExactly20k": int(seeded) == ROW_COUNT,
        "pageSizeBounded30": all(case["returned"] <= 30 for case in cases),
        "twoQueriesPerPage": all(case["queryCount"] == 2 for case in cases),
        "cursorNoOverlap": not bool(first_ids & second_ids),
        "keywordSqlExact": keyword["total"] == 1 and len(keyword["items"]) == 1,
        "categorySqlApplied": category["total"] == 5_000,
        "advisorSqlApplied": advisor["total"] == 200,
        "payloadUnder32KiB": all(case["payloadBytes"] < 32 * 1024 for case in cases),
        "noAttachmentHistory": all(case["attachmentHistoryFields"] == 0 for case in cases),
    }
    verdict = "PASS" if all(checks.values()) else "FAIL"
    evidence = {
        "gate": "GRADUATION_V8_TOPIC_20K",
        "capturedAt": datetime.now(timezone.utc).isoformat(),
        "database": {"name": "graduation_v8_e2e", "port": 43319, "batchId": args.batch_id},
        "seed": {"rows": int(seeded), "elapsedMs": seed_ms, "marker": MARKER},
        "cases": cases,
        "checks": checks,
        "verdict": verdict,
    }
    output = Path(args.output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(evidence, ensure_ascii=False, indent=2))
    if verdict != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
