"""Resumable PLAT-C backfill from append-only StudentStageEvent (never Alembic)."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from sqlalchemy import and_, func, or_, select

from app.core.context import set_tenant
from app.db.session import get_sessionmaker
from app.models import StudentStageEvent, StudentProfile
from app.core.exceptions import AppException
from app.modules.platform.document_lifecycle.lifecycle_fact_writer import (
    LifecycleFactInput,
    fact_dedupe_key,
    record_in_session,
)
from app.modules.platform.document_lifecycle.models import StudentLifecycleFact


CHECKPOINT_VERSION = 1


def _checkpoint(path: Path, *, tenant_id: int) -> int:
    if not path.exists():
        return 0
    raw = json.loads(path.read_text(encoding="utf-8"))
    if int(raw.get("schemaVersion") or 0) != CHECKPOINT_VERSION \
            or int(raw.get("tenantId") or 0) != tenant_id:
        raise AppException("BACKFILL_CHECKPOINT_MISMATCH", "checkpoint 不属于当前租户或版本")
    return int(raw.get("lastId") or 0)


def _save_checkpoint(path: Path, *, tenant_id: int, last_id: int, written: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps({
        "schemaVersion": CHECKPOINT_VERSION,
        "tenantId": tenant_id,
        "lastId": last_id,
        "written": written,
    }), encoding="utf-8")
    temporary.replace(path)


def run(*, tenant_id: int, batch_size: int, dry_run: bool, checkpoint_path: Path,
        max_rows: int | None = None) -> dict:
    set_tenant(tenant_id)
    last_id = _checkpoint(checkpoint_path, tenant_id=tenant_id)
    scanned = written = skipped = excluded = 0
    db = get_sessionmaker()()
    try:
        while True:
            rows = list(db.execute(
                select(StudentStageEvent, StudentProfile)
                .outerjoin(StudentProfile, and_(
                    StudentProfile.tenant_id == StudentStageEvent.tenant_id,
                    StudentProfile.id == StudentStageEvent.student_id,
                    StudentProfile.is_deleted.is_(False),
                ))
                .where(
                    StudentStageEvent.tenant_id == tenant_id,
                    StudentStageEvent.id > last_id,
                )
                .order_by(StudentStageEvent.id)
                .limit(batch_size)
            ).all())
            if not rows:
                break
            prepared: list[tuple[StudentStageEvent, LifecycleFactInput]] = []
            for event, profile in rows:
                scanned += 1
                last_id = int(event.id)
                stop_after_current = bool(max_rows and scanned >= max_rows)
                if str(event.source_module or "").strip().upper() == "SANDBOX":
                    excluded += 1
                    if stop_after_current:
                        break
                    continue
                if profile is None:
                    skipped += 1
                    if stop_after_current:
                        break
                    continue
                prepared.append((event, LifecycleFactInput(
                    student_id=int(profile.id), college_id=profile.college_id,
                    source_module=str(event.source_module or "student"),
                    fact_type=str(event.to_stage), source_biz_type="STUDENT_STAGE_EVENT",
                    source_biz_id=str(event.id), source_version=str(event.id),
                    event_time=event.occurred_at, title="生命周期里程碑", summary=None,
                    importance="NORMAL", visibility_code="STUDENT_SELF_AND_SCOPED_STAFF",
                    sensitivity_level="PERSONAL", target_ref={
                        "type": "STUDENT_STAGE_EVENT", "id": str(event.id), "action": "VIEW",
                    }, created_by=event.created_by,
                )))
                if stop_after_current:
                    break

            existing_keys: set[str] = set()
            if not dry_run and prepared:
                keys = [fact_dedupe_key(fact) for _event, fact in prepared]
                existing_keys = set(db.scalars(select(StudentLifecycleFact.dedupe_key).where(
                    StudentLifecycleFact.tenant_id == tenant_id,
                    StudentLifecycleFact.dedupe_key.in_(keys),
                )).all())
            for _event, fact in prepared:
                if not dry_run:
                    key = fact_dedupe_key(fact)
                    record_in_session(db, fact)
                    if key not in existing_keys:
                        written += 1
                        existing_keys.add(key)
                if max_rows and scanned >= max_rows:
                    break
            if dry_run:
                db.rollback()
            else:
                db.commit()
                _save_checkpoint(
                    checkpoint_path, tenant_id=tenant_id, last_id=last_id, written=written,
                )
            if max_rows and scanned >= max_rows:
                break
        fact_count = int(db.scalar(select(func.count()).select_from(StudentLifecycleFact).where(
            StudentLifecycleFact.tenant_id == tenant_id,
            StudentLifecycleFact.source_biz_type == "STUDENT_STAGE_EVENT",
        )) or 0) if not dry_run else 0
        source_count = int(db.scalar(
            select(func.count()).select_from(StudentStageEvent).join(
                StudentProfile,
                and_(
                    StudentProfile.tenant_id == StudentStageEvent.tenant_id,
                    StudentProfile.id == StudentStageEvent.student_id,
                    StudentProfile.is_deleted.is_(False),
                ),
            ).where(
                StudentStageEvent.tenant_id == tenant_id,
                or_(
                    StudentStageEvent.source_module.is_(None),
                    func.upper(StudentStageEvent.source_module) != "SANDBOX",
                ),
            )
        ) or 0)
        return {"tenantId": tenant_id, "dryRun": dry_run, "scanned": scanned,
                "written": written, "skipped": skipped, "excluded": excluded,
                "lastId": last_id, "sourceEligibleCount": source_count,
                "postFactCount": fact_count,
                "missingCount": max(0, source_count - fact_count) if not dry_run else None}
    finally:
        db.close()
        set_tenant(None)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tenant-id", type=int, required=True)
    parser.add_argument("--batch-size", type=int, default=500)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--max-rows", type=int)
    parser.add_argument("--apply", action="store_true", help="write facts; default is dry-run")
    args = parser.parse_args()
    print(json.dumps(run(
        tenant_id=args.tenant_id, batch_size=min(2000, max(1, args.batch_size)),
        dry_run=not args.apply, checkpoint_path=args.checkpoint, max_rows=args.max_rows,
    ), ensure_ascii=False))


if __name__ == "__main__":
    main()
