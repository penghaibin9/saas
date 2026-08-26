"""Read-only MySQL verification for the browser-rendered internship leave compliance metric."""
from __future__ import annotations

import os
import sys

import pymysql

PREFIX = os.getenv("E2E_INTERNSHIP_AUDIT_PREFIX", "E2E-XLSX-STATS-20260823")


def fail(message: str) -> None:
    raise SystemExit(f"[internship-leave-stats-audit] FAIL: {message}")


def main() -> None:
    if len(sys.argv) != 4:
        fail("usage: <batch_id> <browser_numerator> <browser_denominator>")
    batch_id = int(sys.argv[1])
    browser_numerator = int(sys.argv[2])
    browser_denominator = int(sys.argv[3])

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
                SELECT tenant_id, internship_id, student_id, status, reason
                  FROM t_internship_leave
                 WHERE reason LIKE %s AND is_deleted = 0
                 ORDER BY id
                """,
                (f"{PREFIX}-%",),
            )
            proof_rows = list(cur.fetchall())
            if len(proof_rows) < 2:
                fail(f"browser proof leaves missing for prefix {PREFIX}: {proof_rows}")
            returned = [row for row in proof_rows if row["status"] == "RETURNED"]
            rejected = [row for row in proof_rows if row["status"] == "REJECTED"]
            if not returned or not rejected:
                fail(f"expected browser-created REJECTED + RETURNED proof rows: {proof_rows}")

            tenant_ids = {int(row["tenant_id"]) for row in proof_rows}
            if len(tenant_ids) != 1:
                fail(f"proof rows span multiple tenants: {tenant_ids}")
            tenant_id = next(iter(tenant_ids))

            cur.execute(
                """
                SELECT l.status, COUNT(*) AS cnt
                  FROM t_internship_leave AS l
                  JOIN t_internship_record AS r
                    ON r.id = l.internship_id
                   AND r.tenant_id = l.tenant_id
                 WHERE l.tenant_id = %s
                   AND r.batch_id = %s
                   AND l.is_deleted = 0
                   AND r.is_deleted = 0
                 GROUP BY l.status
                """,
                (tenant_id, batch_id),
            )
            counts = {str(row["status"]): int(row["cnt"] or 0) for row in cur.fetchall()}
            db_denominator = sum(counts.values())
            db_numerator = counts.get("APPROVED", 0) + counts.get("RETURNED", 0)

            if browser_denominator != db_denominator:
                fail(
                    f"browser denominator {browser_denominator} != MySQL all-leave denominator "
                    f"{db_denominator}; counts={counts}"
                )
            if browser_numerator != db_numerator:
                fail(
                    f"browser numerator {browser_numerator} != MySQL compliant APPROVED+RETURNED "
                    f"numerator {db_numerator}; counts={counts}"
                )

            print("[internship-leave-stats-audit] STATS_EVIDENCE_OK")
            print(
                f"tenantId={tenant_id} batchId={batch_id} numerator={db_numerator} "
                f"denominator={db_denominator} counts={counts}"
            )
    finally:
        conn.close()


if __name__ == "__main__":
    main()
