"""Real MySQL failure injection for the governed release rollback primitive.

The test uses its own temporary database so full-regression shards cannot corrupt each other.
It snapshots DB + uploads, simulates a destructive candidate migration/write, restores the
manifest, and proves the previous schema/data/files are usable again.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import uuid
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

ROOT = Path(__file__).resolve().parents[2]
BACKUP = ROOT / "deploy/backup/backup-mysql.sh"
RESTORE = ROOT / "deploy/backup/restore-backup-set.sh"


def _run(args, *, env):
    result = subprocess.run(
        args,
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
        timeout=120,
    )
    assert result.returncode == 0, f"stdout={result.stdout}\nstderr={result.stderr}"
    return result


def test_destructive_candidate_failure_restores_previous_db_and_uploads(tmp_path: Path):
    assert shutil.which("mysqldump"), "mysqldump is required by the production rollback contract"
    assert shutil.which("mysql"), "mysql client is required by the production rollback contract"

    source_url = make_url(os.environ["TEST_DATABASE_URL"])
    assert source_url.get_backend_name() == "mysql"
    database = f"rollback_injection_{uuid.uuid4().hex[:12]}"
    admin_url = source_url.set(database=None)
    admin = create_engine(admin_url, pool_pre_ping=True)
    db_url = source_url.set(database=database)

    quoted_db = f"`{database}`"
    with admin.begin() as conn:
        conn.execute(text(f"CREATE DATABASE {quoted_db} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"))

    engine = create_engine(db_url, pool_pre_ping=True)
    backup_dir = tmp_path / "backup"
    upload_dir = tmp_path / "uploads"
    upload_dir.mkdir()
    original_file = upload_dir / "evidence.txt"
    original_file.write_text("previous-release-evidence", encoding="utf-8")

    try:
        with engine.begin() as conn:
            conn.execute(text("CREATE TABLE rollback_fact (id BIGINT PRIMARY KEY, value VARCHAR(64) NOT NULL)"))
            conn.execute(text("INSERT INTO rollback_fact (id, value) VALUES (1, 'previous')"))

        env = os.environ.copy()
        env.update(
            {
                "DB_HOST": source_url.host or "127.0.0.1",
                "DB_PORT": str(source_url.port or 3306),
                "DB_USER": source_url.username or "root",
                "DB_PASSWORD": source_url.password or "",
                "DB_NAME": database,
                "BACKUP_DIR": str(backup_dir),
                "UPLOAD_DIR": str(upload_dir),
                "REQUIRE_UPLOAD_BACKUP": "true",
                "KEEP_DAYS": "14",
                "MIN_LOCAL_BACKUP_SETS": "1",
            }
        )
        _run(["bash", str(BACKUP)], env=env)
        manifests = sorted(backup_dir.glob("manifest_*.json"))
        assert len(manifests) == 1
        manifest = manifests[0]

        # Candidate migration/write is intentionally incompatible with the previous release.
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE rollback_fact ADD COLUMN candidate_only INT NOT NULL DEFAULT 7"))
            conn.execute(text("UPDATE rollback_fact SET value='candidate' WHERE id=1"))
            conn.execute(text("INSERT INTO rollback_fact (id, value) VALUES (2, 'candidate-only')"))
        original_file.write_text("candidate-overwrite", encoding="utf-8")
        (upload_dir / "candidate-only.txt").write_text("should disappear", encoding="utf-8")

        _run(["bash", str(RESTORE), str(manifest)], env=env)

        with engine.connect() as conn:
            columns = [row[0] for row in conn.execute(text("SHOW COLUMNS FROM rollback_fact"))]
            rows = list(conn.execute(text("SELECT id, value FROM rollback_fact ORDER BY id")))
        assert columns == ["id", "value"]
        assert rows == [(1, "previous")]
        assert original_file.read_text(encoding="utf-8") == "previous-release-evidence"
        assert not (upload_dir / "candidate-only.txt").exists()
    finally:
        engine.dispose()
        with admin.begin() as conn:
            conn.execute(text(f"DROP DATABASE IF EXISTS {quoted_db}"))
        admin.dispose()
