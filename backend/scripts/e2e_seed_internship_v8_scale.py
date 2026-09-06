#!/usr/bin/env python3
"""Prepare the guarded, idempotent 20K Internship V8 scale fixture."""
from __future__ import annotations

import argparse
import os
from urllib.parse import urlparse

import _mysql_env  # noqa: F401
from sqlalchemy import text


DEFAULT_TENANT_ID = 9_000_000_000_000_000_008
BATCH_NO = "E2E-INTERNSHIP-V8-SCALE-20K"
STUDENT_PREFIX = "V8SCALE"


def _assert_safe(engine) -> None:
    if os.getenv("E2E_ALLOW_DESTRUCTIVE_TESTS") != "true":
        raise SystemExit("E2E_ALLOW_DESTRUCTIVE_TESTS=true is required")
    if (os.getenv("APP_ENV") or "").lower() in {"prod", "production"}:
        raise SystemExit("scale fixture refuses production APP_ENV")
    parsed = urlparse(str(engine.url))
    if parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
        raise SystemExit(f"scale fixture requires a local database, got {parsed.hostname}")
    database = (parsed.path or "").lstrip("/").lower()
    if "e2e" not in database and "test" not in database:
        raise SystemExit(f"scale fixture requires an e2e/test database, got {database}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed the guarded Internship V8 20K fixture")
    parser.add_argument("--confirm", action="store_true")
    parser.add_argument("--records", type=int, default=20_000)
    parser.add_argument("--tenant-id", type=int, default=DEFAULT_TENANT_ID)
    args = parser.parse_args()
    if not args.confirm:
        parser.error("--confirm is required")
    if args.records != 20_000:
        parser.error("the final fixture is fixed at exactly 20000 records")

    from app.db.session import get_engine

    engine = get_engine()
    _assert_safe(engine)
    tenant_id = args.tenant_id
    with engine.begin() as conn:
        conn.execute(text("""
            INSERT INTO t_internship_batch
              (tenant_id, batch_name, batch_no, academic_year, term, planned_count,
               status, rules_version, archive_status, is_deleted, version,
               created_at, updated_at)
            VALUES
              (:tenant_id, 'Internship V8 20K scale fixture', :batch_no,
               '2026-2027', 'AUTUMN', :records, 'RUNNING', 1,
               'NOT_ARCHIVED', 0, 1, NOW(), NOW())
            ON DUPLICATE KEY UPDATE planned_count=VALUES(planned_count), updated_at=NOW()
        """), {"tenant_id": tenant_id, "batch_no": BATCH_NO, "records": args.records})
        batch_id = int(conn.scalar(text("""
            SELECT id FROM t_internship_batch
            WHERE tenant_id=:tenant_id AND batch_no=:batch_no
        """), {"tenant_id": tenant_id, "batch_no": BATCH_NO}))

        insert_student = text("""
            INSERT IGNORE INTO t_student_profile
              (tenant_id, student_no, real_name, college_id, major_id, class_id,
               grade, current_stage, student_status, status, is_deleted, version,
               created_at, updated_at)
            VALUES
              (:tenant_id, :student_no, :real_name, 81001, 82001, :class_id,
               '2026', 'INTERNSHIP', 'NORMAL', 'ACTIVE', 0, 1, NOW(), NOW())
        """)
        for start in range(1, args.records + 1, 1_000):
            stop = min(start + 1_000, args.records + 1)
            conn.execute(insert_student, [
                {
                    "tenant_id": tenant_id,
                    "student_no": f"{STUDENT_PREFIX}{number:05d}",
                    "real_name": f"Scale Student {number:05d}",
                    "class_id": 83000 + ((number - 1) // 50),
                }
                for number in range(start, stop)
            ])

        conn.execute(text("""
            INSERT IGNORE INTO t_internship_record
              (tenant_id, student_id, batch_id, enterprise_name, position_name,
               eligibility_status, destination_type, status, risk_level,
               is_deleted, version, created_at, updated_at)
            SELECT :tenant_id, s.id, :batch_id, 'V8 Scale Enterprise',
                   'Scale Verification Position', 'QUALIFIED', 'ASSIGNED',
                   'ONBOARD', 'NONE', 0, 1, NOW(), NOW()
            FROM t_student_profile s
            WHERE s.tenant_id=:tenant_id AND s.student_no LIKE :prefix
              AND s.is_deleted=0
        """), {
            "tenant_id": tenant_id,
            "batch_id": batch_id,
            "prefix": f"{STUDENT_PREFIX}%",
        })
        count = int(conn.scalar(text("""
            SELECT COUNT(*) FROM t_internship_record
            WHERE tenant_id=:tenant_id AND batch_id=:batch_id AND is_deleted=0
        """), {"tenant_id": tenant_id, "batch_id": batch_id}) or 0)
        if count != args.records:
            raise RuntimeError(f"expected {args.records} records, found {count}")

    print(f"[internship-v8-scale-seed] tenant={tenant_id} batch={batch_id} records={count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
