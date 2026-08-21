#!/usr/bin/env python3
"""V3 §11.4 / Teacher T9 EXPLAIN gate for mobile hot paths.

Rules:
  - pagination must stay server-bounded; deep pages use keyset, never Python slicing;
  - add a targeted index only after EXPLAIN proves the existing index is insufficient;
  - any new index requires migration + rollback + before/after evidence.

This script only captures query plans and budgets. It never mutates schema.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta
import json
import sys

import _mysql_env  # noqa: F401

from sqlalchemy import text

QUERIES = [
    {
        "name": "home_todos",
        "note": "首页/消息页待办：应命中 ix_todo_tenant_student_status_id",
        "budget_rows": 500,
        "sql": """
            SELECT id, title, status, due_at FROM t_unified_todo
            WHERE tenant_id = :tid AND is_deleted = 0 AND student_id = :sid AND status = 'PENDING'
            ORDER BY id DESC LIMIT 20
        """,
    },
    {
        "name": "home_todos_by_due",
        "note": "Agenda 时间窗待办：按 due_at 过滤，验证是否出现 filesort/大量扫描",
        "budget_rows": 2000,
        "sql": """
            SELECT id, title, due_at FROM t_unified_todo
            WHERE tenant_id = :tid AND is_deleted = 0 AND student_id = :sid
              AND status = 'PENDING' AND due_at IS NOT NULL
              AND due_at BETWEEN :from_at AND :to_at
            ORDER BY due_at ASC, id ASC LIMIT 100
        """,
    },
    {
        "name": "messages_page",
        "note": "学生本人消息分页：receiver_user_id + id desc",
        "budget_rows": 2000,
        "sql": """
            SELECT id, title, status FROM t_unified_message
            WHERE tenant_id = :tid AND is_deleted = 0 AND receiver_user_id = :sid
            ORDER BY id DESC LIMIT 20
        """,
    },
    {
        "name": "teacher_messages_page",
        "note": "Teacher T9 eventAt/id keyset：user + activeContext + created_at/id desc",
        "budget_rows": 2000,
        "sql": """
            SELECT id, title, status, created_at FROM t_unified_message
            WHERE tenant_id = :tid AND is_deleted = 0
              AND receiver_user_id = :teacher_uid
              AND receiver_context_key IN ('GLOBAL', :teacher_ctx)
              AND created_at IS NOT NULL
            ORDER BY created_at DESC, id DESC LIMIT 21
        """,
    },
    {
        "name": "teacher_messages_badges",
        "note": "Teacher T9 独立未读 badge 聚合：user + activeContext + UNREAD",
        "budget_rows": 2000,
        "sql": """
            SELECT COUNT(*) FROM t_unified_message
            WHERE tenant_id = :tid AND is_deleted = 0
              AND receiver_user_id = :teacher_uid
              AND receiver_context_key IN ('GLOBAL', :teacher_ctx)
              AND status = 'UNREAD' AND withdrawn_at IS NULL
        """,
    },
    {
        "name": "cases_keyset",
        "note": "我的办理 keyset 首页：本人记录按 updated_at 降序",
        "budget_rows": 2000,
        "sql": """
            SELECT id, status, updated_at FROM t_cs_leave
            WHERE tenant_id = :tid AND is_deleted = 0 AND student_id = :sid
            ORDER BY updated_at DESC, id DESC LIMIT 21
        """,
    },
    {
        "name": "search_messages",
        "note": "受限搜索：本人 + 时间窗 + 标题匹配",
        "budget_rows": 5000,
        "sql": """
            SELECT id, title FROM t_unified_message
            WHERE tenant_id = :tid AND is_deleted = 0 AND receiver_user_id = :sid
              AND withdrawn_at IS NULL AND created_at >= :from_at
              AND title LIKE :prefix
            ORDER BY id DESC LIMIT 20
        """,
    },
]


def _explain(conn, sql: str, params: dict) -> dict:
    rows = conn.execute(text("EXPLAIN FORMAT=JSON " + sql), params).fetchall()
    payload = rows[0][0]
    return json.loads(payload) if isinstance(payload, str) else payload


_ROWS_KEYS = ("rows_examined_per_scan", "rows")


def _rows_of(table: dict, label: str) -> int:
    for key in _ROWS_KEYS:
        if key in table:
            try:
                return int(table[key] or 0)
            except (TypeError, ValueError):
                break
    raise SystemExit(
        f"[explain] {label}: 执行计划里找不到扫描行数（尝试过 {', '.join(_ROWS_KEYS)}）；"
        " 拒绝按 0 行判定通过。"
    )


def _walk(node, out):
    if isinstance(node, dict):
        table = node.get("table")
        if isinstance(table, dict):
            out.append(table)
        for value in node.values():
            _walk(value, out)
    elif isinstance(node, list):
        for value in node:
            _walk(value, out)
    return out


def _teacher_identity(conn, tenant_id: int, requested_uid: int, requested_context: str) -> tuple[int, str, str]:
    if requested_uid > 0:
        return requested_uid, requested_context or "GLOBAL", "cli"
    row = conn.execute(text("""
        SELECT receiver_user_id, receiver_context_key
        FROM t_unified_message
        WHERE tenant_id=:tid AND is_deleted=0 AND receiver_user_id IS NOT NULL
          AND receiver_type='STAFF'
        ORDER BY id LIMIT 1
    """), {"tid": tenant_id}).first()
    if row:
        return int(row[0]), str(row[1] or "GLOBAL"), "dataset"
    # Legacy student-only capacity datasets can still explain the access shape. T9 Gold should pass
    # an explicit teacher id/context or seed STAFF messages so evidenceSource is not fallback.
    return 1, "GLOBAL", "fallback-no-staff-row"


def main() -> int:
    parser = argparse.ArgumentParser(description="移动端 V3 热路径 EXPLAIN 取证")
    parser.add_argument("--tenant-id", type=int, required=True)
    parser.add_argument("--student-id", type=int, default=0, help="留空则取该租户第一名学生")
    parser.add_argument("--teacher-user-id", type=int, default=0, help="Teacher T9 消息 receiver_user_id")
    parser.add_argument("--teacher-context", default="", help="Teacher T9 activeContextId")
    parser.add_argument("--json-out", default="", help="把结果写到文件，供 CI 作为 artifact")
    args = parser.parse_args()

    from app.db.session import get_engine

    engine = get_engine()
    with engine.connect() as conn:
        sid = args.student_id
        if not sid:
            row = conn.execute(text(
                "SELECT id FROM t_student_profile WHERE tenant_id=:tid ORDER BY id LIMIT 1"
            ), {"tid": args.tenant_id}).first()
            if not row:
                print("[explain] 该租户没有学生数据，先跑 seed_mobile_capacity_school.py", file=sys.stderr)
                return 2
            sid = int(row[0])

        teacher_uid, teacher_ctx, teacher_source = _teacher_identity(
            conn, args.tenant_id, args.teacher_user_id, args.teacher_context
        )
        now = datetime.utcnow()
        params = {
            "tid": args.tenant_id,
            "sid": sid,
            "teacher_uid": teacher_uid,
            "teacher_ctx": teacher_ctx,
            "from_at": now - timedelta(days=180),
            "to_at": now + timedelta(days=7),
            "prefix": "容量%",
        }

        results = []
        over_budget = []
        for spec in QUERIES:
            plan = _explain(conn, spec["sql"], params)
            tables = _walk(plan, [])
            if not tables:
                print(f"[explain] 无法解析 {spec['name']} 的执行计划", file=sys.stderr)
                return 2
            scanned = 0
            details = []
            for table in tables:
                rows_examined = _rows_of(table, spec["name"])
                scanned += rows_examined
                details.append({
                    "table": table.get("table_name"),
                    "accessType": table.get("access_type"),
                    "key": table.get("key"),
                    "rowsExaminedPerScan": rows_examined,
                    "usingFilesort": bool(table.get("using_filesort")),
                    "usingTemporaryTable": bool(table.get("using_temporary_table")),
                })
            entry = {
                "name": spec["name"],
                "note": spec["note"],
                "budgetRows": spec["budget_rows"],
                "rowsExamined": scanned,
                "withinBudget": scanned <= spec["budget_rows"],
                "tables": details,
            }
            results.append(entry)
            if not entry["withinBudget"]:
                over_budget.append(entry)
            flag = "OK " if entry["withinBudget"] else "OVER"
            print(f"[explain] {flag} {spec['name']:<26} rows={scanned:<8} budget={spec['budget_rows']}")
            for detail in details:
                print(
                    f"          table={detail['table']} type={detail['accessType']} key={detail['key']}"
                    f" filesort={detail['usingFilesort']}"
                )

    payload = {
        "tenantId": args.tenant_id,
        "studentId": sid,
        "teacherMessageIdentity": {
            "receiverUserId": teacher_uid,
            "context": teacher_ctx,
            "evidenceSource": teacher_source,
        },
        "queries": results,
        "overBudget": [entry["name"] for entry in over_budget],
    }
    if args.json_out:
        with open(args.json_out, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
        print(f"[explain] 结果已写入 {args.json_out}")

    if over_budget:
        print(
            "\n[explain] 以下查询超出扫描预算，请看 EXPLAIN 后再决定是否加 targeted index："
            + ", ".join(entry["name"] for entry in over_budget),
            file=sys.stderr,
        )
        return 1
    print("\n[explain] 全部热路径在扫描预算内，无需新增索引。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
