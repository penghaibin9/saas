"""创建只包含 sandbox-school（007）的可恢复 MySQL 逻辑备份。

每张带 tenant_id 的实际业务表分别以 ``--where tenant_id=...`` 导出，另导出
t_tenant 的 007 行。脚本不会执行任何写操作；输出 SHA-256 与表清单，供写入前
保护点和恢复演练核对使用。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
from datetime import date, datetime, time
from decimal import Decimal
from pathlib import Path
from urllib.parse import unquote, urlparse

from sqlalchemy import inspect

TENANT_ID = 1000000000000000007
TENANT_CODE = "sandbox-school"


def _mysql_options() -> tuple[list[str], dict[str, str], str]:
    import _mysql_env  # noqa: F401 - load backend/.env without printing credentials
    from app.core.config import settings

    raw_url = settings.effective_database_url
    parsed = urlparse(raw_url)
    if not parsed.scheme.startswith(("mysql", "mariadb")):
        raise RuntimeError("007 备份仅允许 MySQL/MariaDB，当前不是 MySQL 连接")
    database = (parsed.path or "").lstrip("/")
    if not database:
        raise RuntimeError("数据库连接串缺少数据库名")
    options = [
        "--single-transaction", "--skip-lock-tables", "--skip-triggers", "--no-create-info",
        "--complete-insert", "--default-character-set=utf8mb4",
        f"--host={parsed.hostname or '127.0.0.1'}", f"--port={parsed.port or 3306}",
    ]
    if parsed.username:
        options.append(f"--user={unquote(parsed.username)}")
    env = os.environ.copy()
    password = unquote(parsed.password) if parsed.password else os.environ.get("DB_PASSWORD", "")
    if password:
        env["MYSQL_PWD"] = password
    return options, env, database


def _literal(value: object) -> str:
    """Render a value as portable MySQL SQL; used only when mysqldump is absent."""
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, (int, float, Decimal)):
        return str(value)
    if isinstance(value, bytes):
        return "X'" + value.hex() + "'"
    if isinstance(value, (dict, list)):
        value = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    if isinstance(value, (datetime, date, time)):
        value = value.isoformat(sep=" ") if isinstance(value, datetime) else value.isoformat()
    text_value = str(value).replace("\\", "\\\\").replace("'", "''")
    return "'" + text_value + "'"


def _write_sqlalchemy_dump(engine, tables: list[str], output: Path) -> None:
    """Fallback export when local MySQL client tools are unavailable.

    This intentionally produces an INSERT-only logical backup for a schema already managed by
    Alembic. ``FOREIGN_KEY_CHECKS`` makes restore order independent; restoration is still an
    explicit operator action into a clean/isolated 007 target.
    """
    quote = engine.dialect.identifier_preparer.quote
    with engine.connect() as connection, output.open("w", encoding="utf-8", newline="\n") as stream:
        stream.write("-- sandbox-school 007 tenant-scoped SQLAlchemy logical backup\n")
        stream.write(f"-- tenant_id={TENANT_ID} tenant_code={TENANT_CODE}\n")
        stream.write("SET FOREIGN_KEY_CHECKS=0;\nSTART TRANSACTION;\n\n")
        all_tables = [("t_tenant", "id"), *((table, "tenant_id") for table in tables)]
        for table, scope_column in all_tables:
            columns = [column["name"] for column in inspect(engine).get_columns(table)]
            rendered_columns = ", ".join(quote(column) for column in columns)
            result = connection.execution_options(stream_results=True).exec_driver_sql(
                f"SELECT {rendered_columns} FROM {quote(table)} WHERE {quote(scope_column)} = %s", (TENANT_ID,)
            )
            while True:
                chunk = result.fetchmany(500)
                if not chunk:
                    break
                for row in chunk:
                    values = ", ".join(_literal(value) for value in row)
                    stream.write(f"INSERT INTO {quote(table)} ({rendered_columns}) VALUES ({values});\n")
            stream.write("\n")
        stream.write("COMMIT;\nSET FOREIGN_KEY_CHECKS=1;\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="创建仅含 007 sandbox-school 的 MySQL 逻辑备份")
    parser.add_argument("--output-dir", type=Path, default=None)
    args = parser.parse_args()
    binary = shutil.which("mysqldump")

    import _mysql_env  # noqa: F401
    from app.db.session import db_enabled, get_engine
    if not db_enabled():
        raise SystemExit("DB_ENABLED=false，无法备份真实 007")
    engine = get_engine()
    inspector = inspect(engine)
    tables = sorted(
        table for table in inspector.get_table_names()
        if "tenant_id" in {column["name"] for column in inspector.get_columns(table)}
    )
    with engine.connect() as connection:
        row = connection.exec_driver_sql(
            "SELECT tenant_code FROM t_tenant WHERE id = %s", (TENANT_ID,)
        ).first()
    if row is None or row[0] != TENANT_CODE:
        raise SystemExit("007 tenant identity mismatch; backup not started")

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    root = args.output_dir or (Path.home() / "Documents" / "CodexBackups" / "vocational-saas-sandbox" / stamp)
    root.mkdir(parents=True, exist_ok=False)
    dump_file = root / "sandbox-school-007.sql"
    options, env, database = _mysql_options()
    method = "MYSQLDUMP"
    if binary:
        with dump_file.open("wb") as stream:
            stream.write(b"-- sandbox-school 007 tenant-scoped backup\n")
            stream.write(f"-- tenant_id={TENANT_ID} tenant_code={TENANT_CODE}\n\n".encode())
            commands = [("t_tenant", f"id={TENANT_ID}"), *((table, f"tenant_id={TENANT_ID}") for table in tables)]
            for table, where in commands:
                result = subprocess.run([binary, *options, f"--where={where}", database, table], stdout=stream,
                                        stderr=subprocess.PIPE, env=env, check=False)
                if result.returncode:
                    raise RuntimeError(f"mysqldump 导出 {table} 失败：{result.stderr.decode(errors='replace')[:500]}")
                stream.write(b"\n")
    else:
        method = "SQLALCHEMY_INSERT_FALLBACK"
        _write_sqlalchemy_dump(engine, tables, dump_file)
    digest = hashlib.sha256(dump_file.read_bytes()).hexdigest()
    manifest = root / "sandbox-school-007-backup-manifest.json"
    manifest.write_text(
        "{\n"
        f"  \"tenantId\": \"{TENANT_ID}\",\n"
        f"  \"tenantCode\": \"{TENANT_CODE}\",\n"
        f"  \"dumpFile\": \"{dump_file.name}\",\n"
        f"  \"sha256\": \"{digest}\",\n"
        f"  \"sizeBytes\": {dump_file.stat().st_size},\n"
        f"  \"tenantScopedTableCount\": {len(tables)},\n"
        f"  \"method\": \"{method}\"\n"
        "}\n",
        encoding="utf-8",
    )
    print(f"[007-backup] PASS method={method} file={dump_file} size={dump_file.stat().st_size} sha256={digest} tables={len(tables)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
