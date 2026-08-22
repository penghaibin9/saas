"""Verify MySQL persistence after the real-browser internship leave audit journey.

This script is verification-only: it never creates, updates, or deletes business data.
The browser must have completed the E2E-AUDIT-20260823-* journey first.
"""
from __future__ import annotations

import json
import os

import pymysql

PREFIX = os.getenv("E2E_INTERNSHIP_AUDIT_PREFIX", "E2E-AUDIT-20260823")


def fail(message: str) -> None:
    raise SystemExit(f"[internship-db-audit] FAIL: {message}")


def main() -> None:
    conn = pymysql.connect(
        host=os.getenv("DB_HOST", "127.0.0.1"),
        port=int(os.getenv("DB_PORT", "3306")),
        user=os.getenv("DB_USER", "root"),
        password=os.getenv("DB_PASSWORD", ""),
        database=os.getenv("DB_NAME", "student_lifecycle_e2e"),
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=True,
    )
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, tenant_id, internship_id, student_id, status, reason,
                       review_by_name, review_comment, review_at,
                       returned_at, return_note,
                       created_at, updated_at, created_by, updated_by,
                       is_deleted, version
                  FROM t_internship_leave
                 WHERE reason LIKE %s
                 ORDER BY id
                """,
                (f"{PREFIX}-%",),
            )
            leaves = list(cur.fetchall())

            if len(leaves) != 2:
                fail(f"expected exactly 2 persisted audit leave rows, got {len(leaves)}")

            rejected = next((row for row in leaves if row["status"] == "REJECTED"), None)
            returned = next((row for row in leaves if row["status"] == "RETURNED"), None)
            if not rejected or not returned:
                fail(f"expected REJECTED + RETURNED, got {[row['status'] for row in leaves]}")

            for row in leaves:
                if not row["tenant_id"] or not row["internship_id"] or not row["student_id"]:
                    fail(f"missing tenant/student/internship identity on leave {row['id']}")
                if not row["created_at"] or not row["updated_at"]:
                    fail(f"missing timestamps on leave {row['id']}")
                if row["is_deleted"]:
                    fail(f"audit leave {row['id']} was unexpectedly soft-deleted")
                if int(row["version"] or 0) < 1:
                    fail(f"leave {row['id']} did not advance optimistic-lock version")

            identity = (rejected["tenant_id"], rejected["internship_id"], rejected["student_id"])
            if identity != (returned["tenant_id"], returned["internship_id"], returned["student_id"]):
                fail("rejected and resubmitted rows do not belong to the same tenant/student/internship")

            if not str(rejected["review_comment"] or "").startswith(PREFIX):
                fail("rejected row did not persist the browser-entered rejection reason")
            if not rejected["review_by_name"] or not rejected["review_at"]:
                fail("rejected row is missing reviewer identity/time")
            if not returned["returned_at"] or not str(returned["return_note"] or "").startswith(PREFIX):
                fail("returned row did not persist browser return confirmation")

            ids = [int(rejected["id"]), int(returned["id"])]
            cur.execute(
                """
                SELECT target_id, tenant_id, action, operator_name, detail_json, occurred_at
                  FROM t_internship_audit_trail
                 WHERE target_type = 'LEAVE' AND target_id IN (%s, %s)
                 ORDER BY id
                """,
                ids,
            )
            trails = list(cur.fetchall())

            by_id: dict[int, list[dict]] = {ids[0]: [], ids[1]: []}
            for trail in trails:
                by_id.setdefault(int(trail["target_id"]), []).append(trail)
                if int(trail["tenant_id"]) != int(rejected["tenant_id"]):
                    fail(f"audit trail tenant mismatch for leave {trail['target_id']}")
                if not trail["occurred_at"]:
                    fail(f"audit trail missing timestamp for leave {trail['target_id']}")

            rejected_actions = {row["action"] for row in by_id[int(rejected["id"])]}
            returned_actions = {row["action"] for row in by_id[int(returned["id"])]}
            if not {"APPLY", "REVIEW_REJECT"}.issubset(rejected_actions):
                fail(f"rejected audit chain incomplete: {sorted(rejected_actions)}")
            if not {"APPLY", "REVIEW_APPROVE", "RETURN_VERSIONED"}.issubset(returned_actions):
                fail(f"returned audit chain incomplete: {sorted(returned_actions)}")

            evidence = {
                "prefix": PREFIX,
                "tenantId": str(rejected["tenant_id"]),
                "studentId": str(rejected["student_id"]),
                "internshipId": str(rejected["internship_id"]),
                "rejected": {
                    "id": str(rejected["id"]),
                    "status": rejected["status"],
                    "version": int(rejected["version"] or 0),
                    "reviewBy": rejected["review_by_name"],
                    "reviewComment": rejected["review_comment"],
                    "actions": sorted(rejected_actions),
                },
                "resubmitted": {
                    "id": str(returned["id"]),
                    "status": returned["status"],
                    "version": int(returned["version"] or 0),
                    "returnNote": returned["return_note"],
                    "actions": sorted(returned_actions),
                },
            }
            print("[internship-db-audit] DB_EVIDENCE_OK")
            print(json.dumps(evidence, ensure_ascii=False, default=str, sort_keys=True))
    finally:
        conn.close()


if __name__ == "__main__":
    main()
