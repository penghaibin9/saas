"""Destructive failure-injection recovery smoke in an isolated temporary MySQL DB."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import time
from datetime import datetime
from pathlib import Path

import pymysql


SAFE_DATABASE = re.compile(r"^graduation_v8_recovery_[a-z0-9_]+$")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=43319)
    parser.add_argument("--user", default="root")
    parser.add_argument("--source-database", default="graduation_v8_e2e")
    parser.add_argument("--database", default="graduation_v8_recovery_smoke")
    parser.add_argument("--container", default="graduation-v8-mysql")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not SAFE_DATABASE.fullmatch(args.database):
        raise SystemExit("temporary database must match graduation_v8_recovery_[a-z0-9_]+")
    if not args.source_database.startswith("graduation_v8_"):
        raise SystemExit("source database must be a graduation_v8_* test database")
    password = os.environ.get("MYSQL_PASSWORD")
    if not password:
        raise SystemExit("MYSQL_PASSWORD is required")

    started = time.monotonic()
    admin = pymysql.connect(host=args.host, port=args.port, user=args.user, password=password, charset="utf8mb4", autocommit=True)
    created = False
    try:
        with admin.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM information_schema.schemata WHERE schema_name=%s", (args.database,))
            if cursor.fetchone()[0]:
                raise SystemExit(f"refusing to overwrite existing database {args.database}")
            cursor.execute(f"CREATE DATABASE `{args.database}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
            created = True

        source = pymysql.connect(host=args.host, port=args.port, user=args.user, password=password, database=args.source_database, charset="utf8mb4")
        try:
            with source.cursor() as cursor:
                cursor.execute("SELECT COUNT(*) FROM t_gd_student WHERE batch_id=2 AND is_deleted=0")
                student_count = int(cursor.fetchone()[0])
                cursor.execute("SELECT COUNT(*) FROM t_gd_archive_record WHERE gd_student_id IN (SELECT id FROM t_gd_student WHERE batch_id=2 AND is_deleted=0) AND is_deleted=0")
                archive_count = int(cursor.fetchone()[0])
        finally:
            source.close()
        source_fact = json.dumps({"batchId": 2, "studentCount": student_count, "archiveCount": archive_count}, sort_keys=True, separators=(",", ":"))
        source_hash = hashlib.sha256(source_fact.encode("utf-8")).hexdigest()

        candidate = pymysql.connect(host=args.host, port=args.port, user=args.user, password=password, database=args.database, charset="utf8mb4", autocommit=True)
        try:
            with candidate.cursor() as cursor:
                cursor.execute("CREATE TABLE graduation_recovery_fact (id BIGINT PRIMARY KEY, source_fact JSON NOT NULL, source_sha256 CHAR(64) NOT NULL)")
                cursor.execute("INSERT INTO graduation_recovery_fact (id,source_fact,source_sha256) VALUES (1,%s,%s)", (source_fact, source_hash))
        finally:
            candidate.close()

        dump_run = subprocess.run([
            "docker", "exec", args.container, "mysqldump",
            f"-u{args.user}", f"-p{password}", "--single-transaction", "--no-tablespaces", args.database,
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
        if dump_run.returncode:
            raise SystemExit(dump_run.stderr.decode("utf-8", errors="replace"))
        dump = dump_run.stdout
        dump_hash = hashlib.sha256(dump).hexdigest()

        candidate = pymysql.connect(host=args.host, port=args.port, user=args.user, password=password, database=args.database, charset="utf8mb4", autocommit=True)
        try:
            with candidate.cursor() as cursor:
                cursor.execute("ALTER TABLE graduation_recovery_fact ADD COLUMN candidate_only INT NOT NULL DEFAULT 7")
                cursor.execute("UPDATE graduation_recovery_fact SET source_sha256=REPEAT('0',64) WHERE id=1")
                cursor.execute("CREATE TABLE candidate_only_table (id BIGINT PRIMARY KEY)")
        finally:
            candidate.close()

        with admin.cursor() as cursor:
            cursor.execute(f"DROP DATABASE `{args.database}`")
            created = False
            cursor.execute(f"CREATE DATABASE `{args.database}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
            created = True
        restore = subprocess.run(
            ["docker", "exec", "-i", args.container, "mysql", f"-u{args.user}", f"-p{password}", args.database],
            input=dump, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False,
        )
        if restore.returncode:
            raise SystemExit(restore.stdout.decode("utf-8", errors="replace"))

        verified = pymysql.connect(host=args.host, port=args.port, user=args.user, password=password, database=args.database, charset="utf8mb4")
        try:
            with verified.cursor() as cursor:
                cursor.execute("SELECT source_fact,source_sha256 FROM graduation_recovery_fact WHERE id=1")
                restored_fact, restored_hash = cursor.fetchone()
                cursor.execute("SHOW COLUMNS FROM graduation_recovery_fact")
                columns = [row[0] for row in cursor.fetchall()]
                cursor.execute("SELECT COUNT(*) FROM information_schema.tables WHERE table_schema=%s AND table_name='candidate_only_table'", (args.database,))
                candidate_table_count = int(cursor.fetchone()[0])
        finally:
            verified.close()
        passed = json.loads(restored_fact) == json.loads(source_fact) and restored_hash == source_hash and columns == ["id", "source_fact", "source_sha256"] and candidate_table_count == 0
        evidence = {
            "result": "S5_RECOVERY_PASS" if passed else "S5_RECOVERY_FAIL",
            "generatedAt": datetime.now().astimezone().isoformat(),
            "sourceDatabase": args.source_database,
            "temporaryDatabase": args.database,
            "sourceFact": json.loads(source_fact),
            "sourceSha256": source_hash,
            "dumpSha256": dump_hash,
            "dumpBytes": len(dump),
            "restoredColumns": columns,
            "candidateOnlyTableCount": candidate_table_count,
            "durationSeconds": round(time.monotonic() - started, 3),
            "temporaryDatabaseRemoved": True,
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(evidence, ensure_ascii=False, indent=2))
        return 0 if passed else 1
    finally:
        if created:
            with admin.cursor() as cursor:
                cursor.execute(f"DROP DATABASE `{args.database}`")
        admin.close()


if __name__ == "__main__":
    raise SystemExit(main())
