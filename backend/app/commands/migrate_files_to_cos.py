"""本地文件迁移腾讯云 COS。

示例：
python -m app.commands.migrate_files_to_cos --dry-run --tenant-id 1 --batch-size 200 --resume-from-id 0
python -m app.commands.migrate_files_to_cos --tenant-id 1 --verify-after-upload
python -m app.commands.migrate_files_to_cos --verify-only --tenant-id 1
python -m app.commands.migrate_files_to_cos --rollback --tenant-id 1
"""
from __future__ import annotations

import argparse
import json
import shutil
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

from sqlalchemy import select, text

from app.db.session import get_sessionmaker
from app.models.file import FileObject
from app.services.storage.config import effective_config
from app.services.storage.cos import CosStorageBackend
from app.services.storage.keys import build_object_key
from app.services.storage.local import LocalStorageBackend
from app.services.storage.production import hash_local_path


@dataclass
class ItemResult:
    file_id: int
    tenant_id: int
    action: str
    status: str
    source_key: str
    target_key: str | None = None
    size_bytes: int | None = None
    sha256: str | None = None
    message: str | None = None


def _cos() -> CosStorageBackend:
    cfg = effective_config()
    return CosStorageBackend(
        region=cfg["cosRegion"],
        bucket=cfg["cosBucket"],
        secret_id=cfg["cosSecretId"],
        secret_key=cfg["cosSecretKey"],
    )


def _rows(*, tenant_id: int, batch_size: int, resume_from_id: int, verify_only: bool, rollback: bool):
    db = get_sessionmaker()()
    try:
        stmt = select(FileObject).where(
            FileObject.tenant_id == tenant_id,
            FileObject.id > resume_from_id,
            FileObject.is_deleted.is_(False),
        )
        if rollback or verify_only:
            stmt = stmt.where(FileObject.storage_backend == "cos")
        else:
            stmt = stmt.where(FileObject.storage_backend != "cos")
        return list(db.scalars(stmt.order_by(FileObject.id).limit(batch_size)).all())
    finally:
        db.close()


def _legacy_key(db, file_id: int) -> str | None:
    return db.execute(text(
        "SELECT legacy_file_key FROM t_file_object WHERE id=:id"
    ), {"id": file_id}).scalar_one_or_none()


def migrate_one(row: FileObject, *, dry_run: bool, verify_after_upload: bool) -> ItemResult:
    local = LocalStorageBackend()
    cos = _cos()
    source_key = str(row.file_key)
    source = local.fetch_local(source_key)
    if not source or not source.exists():
        return ItemResult(row.id, row.tenant_id, "MIGRATE", "FAILED", source_key, message="local source missing")
    target_key = build_object_key(
        zone=row.storage_zone or "ACTIVE",
        tenant_id=row.tenant_id,
        ext=row.ext or source.suffix.lstrip(".") or "bin",
    )
    if dry_run:
        return ItemResult(row.id, row.tenant_id, "MIGRATE", "DRY_RUN", source_key, target_key, source.stat().st_size, row.sha256)

    staged = cos.staging_path(target_key)
    staged.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, staged)
    uploaded = cos.persist(target_key, staged)
    head = cos.head_object(target_key)
    if not head or int(head.get("sizeBytes") or 0) != int(row.size_bytes or source.stat().st_size):
        cos.delete(target_key)
        return ItemResult(row.id, row.tenant_id, "MIGRATE", "FAILED", source_key, target_key, message="COS HEAD size mismatch")

    verified_at = None
    if verify_after_upload:
        cached = cos.fetch_local(target_key)
        if not cached or not cached.exists():
            cos.delete(target_key)
            return ItemResult(row.id, row.tenant_id, "MIGRATE", "FAILED", source_key, target_key, message="COS readback missing")
        actual_hash = hash_local_path(cached)
        if row.sha256 and actual_hash != row.sha256:
            cos.delete(target_key)
            return ItemResult(row.id, row.tenant_id, "MIGRATE", "FAILED", source_key, target_key, message="COS SHA-256 mismatch")
        verified_at = datetime.utcnow()

    db = get_sessionmaker()()
    try:
        current = db.get(FileObject, row.id, with_for_update=True)
        if not current or current.storage_backend == "cos":
            db.rollback()
            return ItemResult(row.id, row.tenant_id, "MIGRATE", "SKIPPED", source_key, target_key, message="already migrated")
        now = datetime.utcnow()
        db.execute(text(
            "UPDATE t_file_object SET legacy_file_key=:legacy, storage_backend='cos', "
            "bucket_name=:bucket, object_key=:object_key, file_key=:object_key, etag=:etag, "
            "storage_migrated_at=:migrated, storage_verified_at=:verified "
            "WHERE id=:id AND tenant_id=:tenant"
        ), {
            "legacy": source_key,
            "bucket": cos.bucket_name,
            "object_key": target_key,
            "etag": uploaded.get("etag") or head.get("etag"),
            "migrated": now,
            "verified": verified_at,
            "id": row.id,
            "tenant": row.tenant_id,
        })
        db.commit()
    finally:
        db.close()
    return ItemResult(row.id, row.tenant_id, "MIGRATE", "SUCCEEDED", source_key, target_key, int(head.get("sizeBytes") or 0), row.sha256)


def verify_one(row: FileObject, *, full_hash: bool) -> ItemResult:
    cos = _cos()
    key = str(row.object_key or row.file_key)
    head = cos.head_object(key)
    if not head:
        return ItemResult(row.id, row.tenant_id, "VERIFY", "FAILED", key, message="COS object missing")
    if int(head.get("sizeBytes") or 0) != int(row.size_bytes or 0):
        return ItemResult(row.id, row.tenant_id, "VERIFY", "FAILED", key, size_bytes=int(head.get("sizeBytes") or 0), message="size mismatch")
    digest = None
    if full_hash:
        path = cos.fetch_local(key)
        digest = hash_local_path(path) if path else None
        if row.sha256 and digest != row.sha256:
            return ItemResult(row.id, row.tenant_id, "VERIFY", "FAILED", key, sha256=digest, message="SHA-256 mismatch")
    db = get_sessionmaker()()
    try:
        db.execute(text(
            "UPDATE t_file_object SET storage_verified_at=:now, etag=:etag "
            "WHERE id=:id AND tenant_id=:tenant"
        ), {"now": datetime.utcnow(), "etag": head.get("etag"), "id": row.id, "tenant": row.tenant_id})
        db.commit()
    finally:
        db.close()
    return ItemResult(row.id, row.tenant_id, "VERIFY", "SUCCEEDED", key, size_bytes=int(head.get("sizeBytes") or 0), sha256=digest)


def rollback_one(row: FileObject, *, dry_run: bool, delete_cos: bool) -> ItemResult:
    local = LocalStorageBackend()
    cos = _cos()
    db = get_sessionmaker()()
    try:
        source_key = _legacy_key(db, row.id)
    finally:
        db.close()
    current_key = str(row.object_key or row.file_key)
    if not source_key:
        return ItemResult(row.id, row.tenant_id, "ROLLBACK", "FAILED", current_key, message="legacy_file_key missing")
    source = local.fetch_local(source_key)
    if not source or not source.exists():
        return ItemResult(row.id, row.tenant_id, "ROLLBACK", "FAILED", current_key, source_key, message="buffer-period local copy missing")
    if dry_run:
        return ItemResult(row.id, row.tenant_id, "ROLLBACK", "DRY_RUN", current_key, source_key, source.stat().st_size, row.sha256)
    db = get_sessionmaker()()
    try:
        db.execute(text(
            "UPDATE t_file_object SET storage_backend='local', bucket_name=NULL, object_key=:legacy, "
            "file_key=:legacy, etag=NULL, storage_migrated_at=NULL, storage_verified_at=NULL "
            "WHERE id=:id AND tenant_id=:tenant"
        ), {"legacy": source_key, "id": row.id, "tenant": row.tenant_id})
        db.commit()
    finally:
        db.close()
    if delete_cos:
        cos.delete(current_key)
    return ItemResult(row.id, row.tenant_id, "ROLLBACK", "SUCCEEDED", current_key, source_key, source.stat().st_size, row.sha256)


def main() -> int:
    parser = argparse.ArgumentParser(description="MySQL FileObject 本地/COS 可恢复迁移")
    parser.add_argument("--tenant-id", type=int, required=True)
    parser.add_argument("--batch-size", type=int, default=200)
    parser.add_argument("--resume-from-id", type=int, default=0)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--verify-after-upload", action="store_true")
    parser.add_argument("--verify-only", action="store_true")
    parser.add_argument("--full-hash", action="store_true")
    parser.add_argument("--rollback", action="store_true")
    parser.add_argument("--delete-cos-on-rollback", action="store_true")
    parser.add_argument("--report", default="file-cos-migration-report.json")
    args = parser.parse_args()
    if args.verify_only and args.rollback:
        parser.error("--verify-only 与 --rollback 不能同时使用")
    rows = _rows(
        tenant_id=args.tenant_id,
        batch_size=max(1, min(args.batch_size, 2000)),
        resume_from_id=max(0, args.resume_from_id),
        verify_only=args.verify_only,
        rollback=args.rollback,
    )
    results: list[ItemResult] = []
    for row in rows:
        try:
            if args.rollback:
                item = rollback_one(row, dry_run=args.dry_run, delete_cos=args.delete_cos_on_rollback)
            elif args.verify_only:
                item = verify_one(row, full_hash=args.full_hash)
            else:
                item = migrate_one(row, dry_run=args.dry_run, verify_after_upload=args.verify_after_upload)
        except Exception as exc:  # noqa: BLE001 - one bad object must not stop the batch
            item = ItemResult(row.id, row.tenant_id, "ROLLBACK" if args.rollback else "VERIFY" if args.verify_only else "MIGRATE", "FAILED", str(row.file_key), message=str(exc))
        results.append(item)
        print(json.dumps(asdict(item), ensure_ascii=False))
    report = {
        "generatedAt": datetime.utcnow().isoformat(timespec="seconds"),
        "tenantId": args.tenant_id,
        "dryRun": args.dry_run,
        "resumeFromId": args.resume_from_id,
        "count": len(results),
        "succeeded": sum(item.status == "SUCCEEDED" for item in results),
        "failed": sum(item.status == "FAILED" for item in results),
        "items": [asdict(item) for item in results],
    }
    Path(args.report).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return 1 if report["failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
