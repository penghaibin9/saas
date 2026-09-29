#!/usr/bin/env python3
"""G19 historical migration bridge for the standalone internship platform.

The bridge is intentionally conservative:
- MySQL -> MySQL only.
- Tenant rows keep their original primary keys and tenant_id.
- The destination tenant must be empty unless --allow-nonempty-target is explicit.
- Tables outside the frozen standalone manifest are never copied.
- File metadata parity and file-byte evidence are reported separately.
- A report can only set g19Qualified=true when database parity, logical orphan
  checks and file-byte verification all pass.

This tool does not silently remap tenant IDs and does not treat copied metadata as
proof that file bytes were migrated.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from sqlalchemy import MetaData, Table, create_engine, func, insert, select
from sqlalchemy.engine import Connection, Engine, make_url

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / "backend" / "alembic" / "sql" / "0001_internship_standalone_baseline.json"

# Core logical references are checked even when the schema deliberately has no
# physical FK. These cover the procurement-critical student, internship and file
# evidence chains.
LOGICAL_REFS = (
    ("t_internship_record", "student_id", "t_student_profile", "id"),
    ("t_internship_record", "batch_id", "t_internship_batch", "id"),
    ("t_internship_checkin", "internship_id", "t_internship_record", "id"),
    ("t_weekly_report", "internship_id", "t_internship_record", "id"),
    ("t_internship_process_report", "internship_id", "t_internship_record", "id"),
    ("t_internship_agreement", "internship_id", "t_internship_record", "id"),
    ("t_internship_insurance", "internship_id", "t_internship_record", "id"),
    ("t_internship_guidance", "internship_id", "t_internship_record", "id"),
    ("t_internship_visit", "internship_id", "t_internship_record", "id"),
    ("t_internship_change_request", "internship_id", "t_internship_record", "id"),
    ("t_file_binding", "file_id", "t_file_object", "id"),
    ("t_file_version", "file_object_id", "t_file_object", "id"),
    ("t_file_version", "asset_id", "t_file_asset", "id"),
    ("t_archive_manifest_item", "file_object_id", "t_file_object", "id"),
    ("t_archive_manifest_item", "asset_id", "t_file_asset", "id"),
    ("t_archive_manifest_item", "version_id", "t_file_version", "id"),
)

# Some standalone authority tables are not TenantMixin tables. Only a tenant row
# that can be selected unambiguously is migrated by default.
TENANT_KEY_OVERRIDES = {
    "t_tenant": "id",
}


class MigrationError(RuntimeError):
    pass


@dataclass(frozen=True)
class Manifest:
    path: Path
    sha256: str
    tables: tuple[str, ...]
    source_baseline: str


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_manifest(path: Path) -> Manifest:
    payload = json.loads(path.read_text(encoding="utf-8"))
    tables = tuple(str(value) for value in payload.get("tableNames") or [])
    if not tables:
        raise MigrationError("standalone manifest has no tableNames")
    if int(payload.get("tableCount") or 0) != len(tables):
        raise MigrationError("standalone manifest tableCount does not match tableNames")
    return Manifest(
        path=path,
        sha256=str(payload.get("sha256") or ""),
        tables=tables,
        source_baseline=str(payload.get("sourceBaseline") or ""),
    )


def masked_url(raw: str) -> str:
    return make_url(raw).render_as_string(hide_password=True)


def mysql_engine(raw: str) -> Engine:
    url = make_url(raw)
    if not str(url.drivername).startswith("mysql"):
        raise MigrationError(f"G19 only accepts MySQL URLs, got {url.drivername}")
    return create_engine(raw, pool_pre_ping=True)


def reflect_table(engine: Engine, name: str) -> Table | None:
    metadata = MetaData()
    try:
        return Table(name, metadata, autoload_with=engine)
    except Exception:
        return None


def scope_clause(table: Table, tenant_id: int):
    if "tenant_id" in table.c:
        return table.c.tenant_id == tenant_id
    override = TENANT_KEY_OVERRIDES.get(table.name)
    if override and override in table.c:
        return table.c[override] == tenant_id
    return None


def count_rows(conn: Connection, table: Table, tenant_id: int, include_global: bool) -> int | None:
    clause = scope_clause(table, tenant_id)
    if clause is None and not include_global:
        return None
    stmt = select(func.count()).select_from(table)
    if clause is not None:
        stmt = stmt.where(clause)
    return int(conn.scalar(stmt) or 0)


def migration_columns(source: Table, target: Table) -> list[str]:
    source_names = set(source.c.keys())
    names = []
    for column in target.c:
        if column.name not in source_names:
            continue
        if column.computed is not None:
            continue
        names.append(column.name)
    return names


def missing_required_target_columns(source: Table, target: Table) -> list[str]:
    source_names = set(source.c.keys())
    missing = []
    for column in target.c:
        if column.name in source_names or column.computed is not None:
            continue
        has_default = column.default is not None or column.server_default is not None
        if not column.nullable and not has_default and not column.autoincrement:
            missing.append(column.name)
    return missing


def batched(values: list[dict[str, Any]], size: int) -> Iterable[list[dict[str, Any]]]:
    for offset in range(0, len(values), size):
        yield values[offset : offset + size]


def copy_table(
    source_conn: Connection,
    target_conn: Connection,
    source: Table,
    target: Table,
    *,
    tenant_id: int,
    include_global: bool,
    batch_size: int,
) -> int | None:
    clause = scope_clause(source, tenant_id)
    if clause is None and not include_global:
        return None

    columns = migration_columns(source, target)
    if not columns:
        return 0
    stmt = select(*(source.c[name] for name in columns))
    if clause is not None:
        stmt = stmt.where(clause)
    if "id" in source.c:
        stmt = stmt.order_by(source.c.id)

    copied = 0
    buffer: list[dict[str, Any]] = []
    for row in source_conn.execute(stmt).mappings():
        buffer.append({name: row[name] for name in columns})
        if len(buffer) >= batch_size:
            target_conn.execute(insert(target), buffer)
            copied += len(buffer)
            buffer.clear()
    if buffer:
        target_conn.execute(insert(target), buffer)
        copied += len(buffer)
    return copied


def table_plan(
    source_engine: Engine,
    target_engine: Engine,
    manifest: Manifest,
    *,
    tenant_id: int,
    include_global: bool,
) -> tuple[list[dict[str, Any]], list[str]]:
    rows: list[dict[str, Any]] = []
    errors: list[str] = []
    with source_engine.connect() as src, target_engine.connect() as dst:
        for name in manifest.tables:
            source = reflect_table(source_engine, name)
            target = reflect_table(target_engine, name)
            if source is None or target is None:
                rows.append({
                    "table": name,
                    "sourcePresent": source is not None,
                    "targetPresent": target is not None,
                    "scope": "MISSING",
                })
                errors.append(f"{name}: missing from {'source' if source is None else 'target'}")
                continue
            source_count = count_rows(src, source, tenant_id, include_global)
            target_count = count_rows(dst, target, tenant_id, include_global)
            scope = "TENANT" if scope_clause(source, tenant_id) is not None else (
                "GLOBAL" if include_global else "GLOBAL_SKIPPED"
            )
            missing = missing_required_target_columns(source, target)
            if missing:
                errors.append(f"{name}: source lacks required target columns {','.join(missing)}")
            rows.append({
                "table": name,
                "scope": scope,
                "sourceRows": source_count,
                "targetRows": target_count,
                "missingRequiredTargetColumns": missing,
            })
    return rows, errors


def copy_database(
    source_engine: Engine,
    target_engine: Engine,
    manifest: Manifest,
    *,
    tenant_id: int,
    include_global: bool,
    allow_nonempty_target: bool,
    batch_size: int,
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    # Reflect up-front so a schema problem cannot leave a half-started copy.
    pairs: list[tuple[str, Table, Table, int | None, int | None]] = []
    with source_engine.connect() as src, target_engine.connect() as dst:
        for name in manifest.tables:
            source = reflect_table(source_engine, name)
            target = reflect_table(target_engine, name)
            if source is None or target is None:
                raise MigrationError(f"{name}: table missing from source or target")
            missing = missing_required_target_columns(source, target)
            if missing:
                raise MigrationError(f"{name}: source lacks required target columns {missing}")
            source_count = count_rows(src, source, tenant_id, include_global)
            target_count = count_rows(dst, target, tenant_id, include_global)
            if source_count is None:
                results.append({"table": name, "scope": "GLOBAL_SKIPPED", "copiedRows": None})
                continue
            if target_count and not allow_nonempty_target:
                raise MigrationError(
                    f"{name}: target scope is not empty ({target_count} rows); "
                    "refusing copy without --allow-nonempty-target"
                )
            pairs.append((name, source, target, source_count, target_count))

    with source_engine.connect() as src, target_engine.begin() as dst:
        dst.exec_driver_sql("SET FOREIGN_KEY_CHECKS=0")
        try:
            for name, source, target, source_count, _ in pairs:
                copied = copy_table(
                    src, dst, source, target,
                    tenant_id=tenant_id,
                    include_global=include_global,
                    batch_size=batch_size,
                )
                results.append({
                    "table": name,
                    "scope": "TENANT" if scope_clause(source, tenant_id) is not None else "GLOBAL",
                    "sourceRows": source_count,
                    "copiedRows": copied,
                })
        finally:
            dst.exec_driver_sql("SET FOREIGN_KEY_CHECKS=1")
    return results


def logical_orphans(engine: Engine, tenant_id: int) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    cache: dict[str, Table | None] = {}

    def table(name: str) -> Table | None:
        if name not in cache:
            cache[name] = reflect_table(engine, name)
        return cache[name]

    with engine.connect() as conn:
        for child_name, child_key, parent_name, parent_key in LOGICAL_REFS:
            child, parent = table(child_name), table(parent_name)
            if child is None or parent is None:
                continue
            if child_key not in child.c or parent_key not in parent.c:
                continue
            c = child.alias("c")
            p = parent.alias("p")
            join_on = c.c[child_key] == p.c[parent_key]
            if "tenant_id" in c.c and "tenant_id" in p.c:
                join_on = join_on & (c.c.tenant_id == p.c.tenant_id)
            stmt = select(func.count()).select_from(c.outerjoin(p, join_on)).where(
                c.c[child_key].is_not(None),
                p.c[parent_key].is_(None),
            )
            if "tenant_id" in c.c:
                stmt = stmt.where(c.c.tenant_id == tenant_id)
            elif child_name in TENANT_KEY_OVERRIDES:
                stmt = stmt.where(c.c[TENANT_KEY_OVERRIDES[child_name]] == tenant_id)
            count = int(conn.scalar(stmt) or 0)
            if count:
                findings.append({
                    "childTable": child_name,
                    "childKey": child_key,
                    "parentTable": parent_name,
                    "parentKey": parent_key,
                    "orphanRows": count,
                })
    return findings


def file_metadata_parity(source_engine: Engine, target_engine: Engine, tenant_id: int) -> dict[str, Any]:
    source = reflect_table(source_engine, "t_file_object")
    target = reflect_table(target_engine, "t_file_object")
    if source is None or target is None:
        return {"qualified": False, "reason": "t_file_object missing", "mismatches": []}

    keys = [name for name in ("id", "sha256", "size_bytes", "storage_backend", "bucket_name", "object_key", "file_key") if name in source.c and name in target.c]
    source_rows: dict[int, dict[str, Any]] = {}
    target_rows: dict[int, dict[str, Any]] = {}
    with source_engine.connect() as src, target_engine.connect() as dst:
        src_stmt = select(*(source.c[name] for name in keys))
        dst_stmt = select(*(target.c[name] for name in keys))
        if "tenant_id" in source.c:
            src_stmt = src_stmt.where(source.c.tenant_id == tenant_id)
        if "tenant_id" in target.c:
            dst_stmt = dst_stmt.where(target.c.tenant_id == tenant_id)
        for row in src.execute(src_stmt).mappings():
            source_rows[int(row["id"])] = dict(row)
        for row in dst.execute(dst_stmt).mappings():
            target_rows[int(row["id"])] = dict(row)

    mismatches = []
    for file_id in sorted(set(source_rows) | set(target_rows)):
        left, right = source_rows.get(file_id), target_rows.get(file_id)
        if left != right:
            mismatches.append({"fileId": file_id, "source": left, "target": right})
            if len(mismatches) >= 100:
                break
    return {
        "qualified": not mismatches and len(source_rows) == len(target_rows),
        "sourceFiles": len(source_rows),
        "targetFiles": len(target_rows),
        "mismatches": mismatches,
    }


def safe_relative_key(raw: str) -> Path:
    value = str(raw or "").replace("\\", "/").lstrip("/")
    path = Path(value)
    if not value or path.is_absolute() or ".." in path.parts:
        raise MigrationError(f"unsafe file key: {raw!r}")
    return path


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def migrate_local_file_bytes(
    source_engine: Engine,
    *,
    tenant_id: int,
    mode: str,
    source_root: Path | None,
    target_root: Path | None,
) -> dict[str, Any]:
    table = reflect_table(source_engine, "t_file_object")
    if table is None:
        return {"qualified": False, "reason": "t_file_object missing", "verified": 0, "unresolved": 0}

    required = {"id", "file_key"}
    if not required <= set(table.c.keys()):
        return {"qualified": False, "reason": "file object columns missing", "verified": 0, "unresolved": 0}

    rows = []
    with source_engine.connect() as conn:
        stmt = select(table)
        if "tenant_id" in table.c:
            stmt = stmt.where(table.c.tenant_id == tenant_id)
        rows = [dict(row) for row in conn.execute(stmt).mappings()]

    if not rows:
        return {
            "qualified": True,
            "reason": "no file objects for tenant",
            "verified": 0,
            "copied": 0,
            "unresolved": 0,
            "externalStorage": 0,
            "errors": [],
        }

    errors = []
    verified = copied = external = unresolved = 0
    for row in rows:
        backend = str(row.get("storage_backend") or "local").lower()
        if backend != "local":
            external += 1
            unresolved += 1
            continue
        if source_root is None or target_root is None:
            unresolved += 1
            continue
        try:
            rel = safe_relative_key(row.get("object_key") or row.get("file_key") or "")
            src = (source_root / rel).resolve()
            dst = (target_root / rel).resolve()
            if source_root.resolve() not in src.parents and src != source_root.resolve():
                raise MigrationError(f"source path escapes root: {rel}")
            if target_root.resolve() not in dst.parents and dst != target_root.resolve():
                raise MigrationError(f"target path escapes root: {rel}")
            if not src.is_file():
                raise MigrationError(f"source file missing: {rel}")
            expected_size = row.get("size_bytes")
            expected_sha = str(row.get("sha256") or "").lower()
            actual_source_sha = sha256_file(src)
            if expected_size is not None and src.stat().st_size != int(expected_size):
                raise MigrationError(f"source size mismatch: {rel}")
            if expected_sha and actual_source_sha != expected_sha:
                raise MigrationError(f"source sha256 mismatch: {rel}")
            if mode == "copy":
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)
                copied += 1
            if not dst.is_file():
                raise MigrationError(f"target file missing: {rel}")
            if dst.stat().st_size != src.stat().st_size or sha256_file(dst) != actual_source_sha:
                raise MigrationError(f"target byte verification failed: {rel}")
            verified += 1
        except Exception as exc:
            unresolved += 1
            errors.append({"fileId": row.get("id"), "error": str(exc)})
            if len(errors) >= 100:
                break

    return {
        "qualified": unresolved == 0,
        "verified": verified,
        "copied": copied,
        "unresolved": unresolved,
        "externalStorage": external,
        "errors": errors,
        "note": (
            "COS/other object storage requires a separate provider-level copy and checksum evidence; "
            "metadata parity is not file-byte migration proof."
            if external else ""
        ),
    }


def verify_counts(
    source_engine: Engine,
    target_engine: Engine,
    manifest: Manifest,
    *,
    tenant_id: int,
    include_global: bool,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rows = []
    mismatches = []
    with source_engine.connect() as src, target_engine.connect() as dst:
        for name in manifest.tables:
            source = reflect_table(source_engine, name)
            target = reflect_table(target_engine, name)
            if source is None or target is None:
                mismatches.append({"table": name, "reason": "missing table"})
                continue
            source_count = count_rows(src, source, tenant_id, include_global)
            target_count = count_rows(dst, target, tenant_id, include_global)
            if source_count is None:
                rows.append({"table": name, "scope": "GLOBAL_SKIPPED"})
                continue
            item = {"table": name, "sourceRows": source_count, "targetRows": target_count}
            rows.append(item)
            if source_count != target_count:
                mismatches.append(item)
    return rows, mismatches


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="G19 tenant-safe historical migration bridge")
    parser.add_argument("--source", help="source MySQL SQLAlchemy URL")
    parser.add_argument("--target", help="standalone target MySQL SQLAlchemy URL")
    parser.add_argument("--tenant-id", type=int, help="tenant id to preserve exactly")
    parser.add_argument("--mode", choices=("plan", "copy", "verify"), default="plan")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--batch-size", type=int, default=500)
    parser.add_argument("--include-global", action="store_true", help="also copy tenantless shared tables")
    parser.add_argument("--allow-nonempty-target", action="store_true")
    parser.add_argument("--source-file-root", type=Path)
    parser.add_argument("--target-file-root", type=Path)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--self-test", action="store_true")
    return parser


def self_test() -> dict[str, Any]:
    manifest = load_manifest(DEFAULT_MANIFEST)
    assert "t_internship_record" in manifest.tables
    assert "t_file_object" in manifest.tables
    assert safe_relative_key("tenant/1/a.pdf").as_posix() == "tenant/1/a.pdf"
    try:
        safe_relative_key("../escape")
    except MigrationError:
        pass
    else:
        raise AssertionError("unsafe path was not rejected")
    return {
        "ok": True,
        "manifestTables": len(manifest.tables),
        "manifestSha256": manifest.sha256,
        "logicalChecks": len(LOGICAL_REFS),
    }


def main() -> int:
    args = build_parser().parse_args()
    if args.self_test:
        print(json.dumps(self_test(), ensure_ascii=False))
        return 0

    if not args.source or not args.target or not args.tenant_id:
        raise MigrationError("--source, --target and positive --tenant-id are required")
    if args.tenant_id <= 0:
        raise MigrationError("--tenant-id must be positive")
    if args.batch_size < 1 or args.batch_size > 10000:
        raise MigrationError("--batch-size must be between 1 and 10000")
    if bool(args.source_file_root) != bool(args.target_file_root):
        raise MigrationError("--source-file-root and --target-file-root must be provided together")

    manifest = load_manifest(args.manifest)
    source_engine = mysql_engine(args.source)
    target_engine = mysql_engine(args.target)
    report: dict[str, Any] = {
        "schemaVersion": 1,
        "gate": "G19",
        "generatedAt": utc_now(),
        "mode": args.mode,
        "tenantId": args.tenant_id,
        "source": masked_url(args.source),
        "target": masked_url(args.target),
        "manifest": {
            "path": str(args.manifest),
            "sourceBaseline": manifest.source_baseline,
            "sha256": manifest.sha256,
            "tableCount": len(manifest.tables),
        },
        "includeGlobal": bool(args.include_global),
        "warnings": [],
    }

    plan, plan_errors = table_plan(
        source_engine, target_engine, manifest,
        tenant_id=args.tenant_id, include_global=args.include_global,
    )
    report["preflight"] = {"tables": plan, "errors": plan_errors}
    if plan_errors:
        report["databaseQualified"] = False
        report["g19Qualified"] = False
        report["verdict"] = "FAIL_PREFLIGHT"
    elif args.mode == "plan":
        report["databaseQualified"] = False
        report["fileBytesQualified"] = False
        report["g19Qualified"] = False
        report["verdict"] = "PLAN_ONLY"
        report["warnings"].append("Plan mode does not prove historical migration.")
    else:
        if args.mode == "copy":
            report["copy"] = copy_database(
                source_engine, target_engine, manifest,
                tenant_id=args.tenant_id,
                include_global=args.include_global,
                allow_nonempty_target=args.allow_nonempty_target,
                batch_size=args.batch_size,
            )
        count_rows_report, count_mismatches = verify_counts(
            source_engine, target_engine, manifest,
            tenant_id=args.tenant_id, include_global=args.include_global,
        )
        orphans = logical_orphans(target_engine, args.tenant_id)
        file_meta = file_metadata_parity(source_engine, target_engine, args.tenant_id)
        file_bytes = migrate_local_file_bytes(
            source_engine,
            tenant_id=args.tenant_id,
            mode=args.mode,
            source_root=args.source_file_root,
            target_root=args.target_file_root,
        )
        database_qualified = not count_mismatches and not orphans and bool(file_meta.get("qualified"))
        file_bytes_qualified = bool(file_bytes.get("qualified"))
        report.update({
            "verification": {
                "tableCounts": count_rows_report,
                "countMismatches": count_mismatches,
                "logicalOrphans": orphans,
                "fileMetadataParity": file_meta,
                "fileBytes": file_bytes,
            },
            "databaseQualified": database_qualified,
            "fileBytesQualified": file_bytes_qualified,
            "g19Qualified": database_qualified and file_bytes_qualified,
        })
        if report["g19Qualified"]:
            report["verdict"] = "PASS"
        elif database_qualified and not file_bytes_qualified:
            report["verdict"] = "BLOCKED_FILE_BYTES"
        else:
            report["verdict"] = "FAIL_VERIFY"

    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
    return 0 if report.get("verdict") in {"PASS", "PLAN_ONLY", "BLOCKED_FILE_BYTES"} else 2


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except MigrationError as exc:
        print(json.dumps({"gate": "G19", "verdict": "ERROR", "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        raise SystemExit(2)
