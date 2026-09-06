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
import re
import shutil
import subprocess
from datetime import date, datetime, time
from decimal import Decimal
from pathlib import Path
from urllib.parse import unquote, urlparse

from sqlalchemy import inspect

TENANT_ID = 1000000000000000007
TENANT_CODE = "sandbox-school"


def _validated_restore_database(source_database: str, requested: str | None) -> str | None:
    if not requested:
        return None
    target = requested.strip()
    safe_name = re.fullmatch(r"[A-Za-z0-9_]+", target) and re.search(
        r"(?:^|_)(?:restore|recovery)(?:_|$)", target, re.IGNORECASE
    )
    if not safe_name or target == source_database:
        raise SystemExit(
            "--isolated-restore-database 必须是不同于源库、且名称含独立 restore/recovery 段的隔离库"
        )
    return target


def _write_restore_target_guard(stream, target_database: str) -> None:
    """Fail before trigger DDL when mysql is pointed at any unexpected schema."""
    expected = target_database.replace("'", "''")
    stream.write(f"SET @codex_expected_restore_database = '{expected}';\n")
    stream.write(
        "SET @codex_restore_guard_sql = IF(DATABASE() = @codex_expected_restore_database, "
        "'DO 0', 'SELECT * FROM `__ACADEMIC_V81_RESTORE_TARGET_MISMATCH__`');\n"
    )
    stream.write("PREPARE codex_restore_guard FROM @codex_restore_guard_sql;\n")
    stream.write("EXECUTE codex_restore_guard;\n")
    stream.write("DEALLOCATE PREPARE codex_restore_guard;\n\n")


def _trigger_specs(engine) -> list[dict[str, str]]:
    """Return portable trigger definitions for an already-migrated restore target.

    Tenant backups are restored into a schema that already owns its production triggers.
    Some AFTER INSERT triggers materialise lock rows, so leaving them enabled while the
    corresponding backed-up lock rows are inserted makes an otherwise clean restore fail
    with duplicate keys.  Capture every schema trigger and recreate it after the atomic
    data import instead of silently changing restored facts.
    """
    with engine.connect() as connection:
        rows = connection.exec_driver_sql(
            """
            SELECT TRIGGER_NAME, ACTION_TIMING, EVENT_MANIPULATION,
                   EVENT_OBJECT_TABLE, ACTION_STATEMENT
              FROM information_schema.TRIGGERS
             WHERE TRIGGER_SCHEMA = DATABASE()
             ORDER BY TRIGGER_NAME
            """
        ).mappings().all()
    return [dict(row) for row in rows]


def _write_trigger_preamble(stream, engine, triggers: list[dict[str, str]]) -> None:
    quote = engine.dialect.identifier_preparer.quote
    stream.write("-- Suspend migrated-schema triggers so backed-up materialized rows restore exactly.\n")
    for trigger in triggers:
        stream.write(f"DROP TRIGGER IF EXISTS {quote(trigger['TRIGGER_NAME'])};\n")
    stream.write("\n")


def _write_trigger_epilogue(stream, engine, triggers: list[dict[str, str]]) -> None:
    quote = engine.dialect.identifier_preparer.quote
    if not triggers:
        return
    stream.write("\nDELIMITER $$\n")
    for trigger in triggers:
        stream.write(
            f"CREATE TRIGGER {quote(trigger['TRIGGER_NAME'])} "
            f"{trigger['ACTION_TIMING']} {trigger['EVENT_MANIPULATION']} "
            f"ON {quote(trigger['EVENT_OBJECT_TABLE'])} FOR EACH ROW "
            f"{trigger['ACTION_STATEMENT']}$$\n"
        )
    stream.write("DELIMITER ;\n")


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


def _write_sqlalchemy_dump(
    engine,
    tables: list[str],
    output: Path,
    triggers: list[dict[str, str]],
    restore_database: str | None,
) -> None:
    """Fallback export when local MySQL client tools are unavailable.

    This intentionally produces an INSERT-only logical backup for a schema already managed by
    Alembic. ``FOREIGN_KEY_CHECKS`` makes restore order independent; restoration is still an
    explicit operator action into a clean/isolated 007 target.
    """
    quote = engine.dialect.identifier_preparer.quote
    with engine.connect() as connection, output.open("w", encoding="utf-8", newline="\n") as stream:
        stream.write("-- sandbox-school 007 tenant-scoped SQLAlchemy logical backup\n")
        stream.write(f"-- tenant_id={TENANT_ID} tenant_code={TENANT_CODE}\n")
        stream.write("SET NAMES utf8mb4;\n")
        stream.write("SET FOREIGN_KEY_CHECKS=0;\n")
        if restore_database:
            _write_restore_target_guard(stream, restore_database)
            _write_trigger_preamble(stream, engine, triggers)
        stream.write("START TRANSACTION;\n\n")
        all_tables = [("t_tenant", "id"), *((table, "tenant_id") for table in tables)]
        for table, scope_column in all_tables:
            # Generated columns must be omitted: MySQL computes them and rejects explicit
            # values even when the value equals the generated expression.
            columns = [
                column["name"] for column in inspect(engine).get_columns(table)
                if not column.get("computed")
            ]
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
        stream.write("COMMIT;\n")
        if restore_database:
            _write_trigger_epilogue(stream, engine, triggers)
        stream.write("SET FOREIGN_KEY_CHECKS=1;\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="创建仅含 007 sandbox-school 的 MySQL 逻辑备份")
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument(
        "--isolated-restore-database",
        default=None,
        help="仅为指定的隔离 restore/recovery 库生成触发器暂停包装；默认绝不删除目标库触发器",
    )
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
    restore_database = _validated_restore_database(database, args.isolated_restore_database)
    triggers = _trigger_specs(engine) if restore_database else []
    method = "MYSQLDUMP"
    if binary:
        with dump_file.open("wb") as stream:
            stream.write(b"-- sandbox-school 007 tenant-scoped backup\n")
            stream.write(f"-- tenant_id={TENANT_ID} tenant_code={TENANT_CODE}\n\n".encode())
            stream.write(b"SET NAMES utf8mb4;\n")
            stream.write(b"SET FOREIGN_KEY_CHECKS=0;\n")
            if restore_database:
                from io import StringIO
                trigger_preamble = StringIO()
                _write_restore_target_guard(trigger_preamble, restore_database)
                _write_trigger_preamble(trigger_preamble, engine, triggers)
                stream.write(trigger_preamble.getvalue().encode("utf-8"))
            commands = [("t_tenant", f"id={TENANT_ID}"), *((table, f"tenant_id={TENANT_ID}") for table in tables)]
            for table, where in commands:
                result = subprocess.run([binary, *options, f"--where={where}", database, table], stdout=stream,
                                        stderr=subprocess.PIPE, env=env, check=False)
                if result.returncode:
                    raise RuntimeError(f"mysqldump 导出 {table} 失败：{result.stderr.decode(errors='replace')[:500]}")
                stream.write(b"\n")
            if restore_database:
                trigger_epilogue = StringIO()
                _write_trigger_epilogue(trigger_epilogue, engine, triggers)
                stream.write(trigger_epilogue.getvalue().encode("utf-8"))
            stream.write(b"SET FOREIGN_KEY_CHECKS=1;\n")
    else:
        method = "SQLALCHEMY_INSERT_FALLBACK"
        _write_sqlalchemy_dump(engine, tables, dump_file, triggers, restore_database)
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
        f"  \"isolatedRestoreDatabase\": {json.dumps(restore_database)},\n"
        f"  \"targetTriggersSuspended\": {str(bool(restore_database)).lower()},\n"
        f"  \"method\": \"{method}\"\n"
        "}\n",
        encoding="utf-8",
    )
    print(f"[007-backup] PASS method={method} file={dump_file} size={dump_file.stat().st_size} sha256={digest} tables={len(tables)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
