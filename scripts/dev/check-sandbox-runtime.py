"""Guard the persistent local acceptance environment; never migrate or seed it."""
from __future__ import annotations

import json
import os
from pathlib import Path
import sys
import time

from dotenv import dotenv_values
import pymysql
from sqlalchemy.engine import make_url

ROOT = Path(__file__).resolve().parents[2]
DATABASE = "student_lifecycle_runtime_20260902"
TENANT_ID = 1000000000000000007
TENANT_CODE = "sandbox-school"


def load_environment():
    values = {k: v for k, v in dotenv_values(ROOT / "backend/.env").items() if v is not None}
    url = make_url(values.get("DATABASE_URL", ""))
    if (url.host, url.port, url.database) != ("127.0.0.1", 3307, DATABASE):
        raise RuntimeError("backend/.env must point to the agreed persistent sandbox on 127.0.0.1:3307")
    if values.get("DEFAULT_TENANT_CODE") != TENANT_CODE or values.get("DB_ENABLED", "").lower() != "true":
        raise RuntimeError("The daily runtime must use the real sandbox-school database")
    if values.get("SANDBOX_AUTO_RESET", "").lower() != "false":
        raise RuntimeError("Automatic reset must be disabled for the persistent sandbox")
    if values.get("APP_ENV") not in {"development", "test"} or values.get("DEPLOYMENT_MODE") != "local":
        raise RuntimeError("This launcher is only for the local acceptance sandbox")
    # Inherited per-task connection overrides must not win over this explicit local profile.
    os.environ.update(values)
    return url


def check():
    url = load_environment()
    with pymysql.connect(host=url.host, port=url.port, user=url.username, password=url.password or "",
                         database=url.database, charset="utf8mb4", connect_timeout=5,
                         read_timeout=10, write_timeout=10) as db:
        with db.cursor() as cursor:
            cursor.execute("START TRANSACTION READ ONLY")
            cursor.execute("SELECT tenant_code FROM t_tenant WHERE id=%s AND is_deleted=0", (TENANT_ID,))
            if cursor.fetchone() != (TENANT_CODE,):
                raise RuntimeError("Sandbox school identity does not match; refusing to start")
            cursor.execute("SELECT version_num FROM alembic_version")
            database_heads = {row[0] for row in cursor.fetchall()}
            from alembic.config import Config
            from alembic.script import ScriptDirectory
            config = Config()
            config.set_main_option("script_location", str(ROOT / "backend/alembic"))
            if database_heads != set(ScriptDirectory.from_config(config).get_heads()):
                raise RuntimeError("Code and sandbox migration versions differ; review migration before starting")
            cursor.execute("SELECT COUNT(*) FROM information_schema.tables WHERE table_schema=DATABASE()")
            tables = cursor.fetchone()[0]
            db.rollback()
    return {"database": DATABASE, "tenantCode": TENANT_CODE, "tenantId": str(TENANT_ID),
            "tables": tables, "migrationHeads": sorted(database_heads)}


if __name__ == "__main__":
    try:
        load_environment()
        started = time.monotonic()
        deadline = started + (300 if sys.argv[1:] == ["wait"] else 0)
        last_notice = started - 15
        while True:
            try:
                result = check()
                break
            except pymysql.err.OperationalError as error:
                if error.args[0] not in {2003, 2006, 2013} or time.monotonic() >= deadline:
                    raise
                if time.monotonic() - last_notice >= 15:
                    print(f"[WAIT] MySQL is not ready yet ({int(time.monotonic() - started)}s). Keeping the original database.", flush=True)
                    last_notice = time.monotonic()
                time.sleep(0.5)
        print(json.dumps(result), flush=True)
        if len(sys.argv) > 1 and sys.argv[1] == "serve":
            os.chdir(ROOT / "backend")
            sys.path.insert(0, str(ROOT / "backend"))
            import uvicorn
            uvicorn.run("app.main:app", host="127.0.0.1", port=8000)
    except Exception as error:
        # Connection errors can contain credentials; only controlled messages leave this process.
        if isinstance(error, pymysql.err.OperationalError) and error.args[0] in {2003, 2006, 2013}:
            message = "Sandbox MySQL did not become ready. Check the student-lifecycle-v8-mysql container logs, then retry; do not reset the database."
        else:
            message = str(error) if isinstance(error, RuntimeError) else f"Sandbox check failed ({type(error).__name__}); inspect local configuration."
        print(message, file=sys.stderr)
        sys.exit(1)
