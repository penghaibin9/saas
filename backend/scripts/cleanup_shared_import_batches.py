"""Expire shared import payloads and purge retained personal data.

Run daily on exactly one scheduler host (or safely on several; updates are idempotent):
    python scripts/cleanup_shared_import_batches.py --apply --purge-after-days 30
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta

from sqlalchemy import delete, func, select, update

from app.db.session import db_enabled, get_sessionmaker
from app.models import IdentityImportBatch, SharedImportBatch


def run(*, apply: bool, purge_after_days: int) -> dict:
    if not db_enabled():
        raise RuntimeError("DB_ENABLED=true 才能清理共享导入批次")
    now = datetime.utcnow()
    purge_before = now - timedelta(days=max(purge_after_days, 7))
    db = get_sessionmaker()()
    try:
        models = (IdentityImportBatch, SharedImportBatch)
        due = sum(int(db.scalar(select(func.count()).select_from(model).where(
            model.expires_at <= now, model.is_deleted.is_(False))) or 0) for model in models)
        purgeable = sum(int(db.scalar(select(func.count()).select_from(model).where(
            model.expires_at <= purge_before)) or 0) for model in models)
        if apply:
            db.execute(update(IdentityImportBatch).where(
                IdentityImportBatch.expires_at <= now,
                IdentityImportBatch.is_deleted.is_(False)).values(
                    status="EXPIRED", claim_token=None, claim_started_at=None,
                    payload_json={}, raw_rows_json=[], errors_json=[], pre_errors_json=[],
                    report_json={}, relationships_json=[], relation_errors_json=[],
                    public_result_json=None))
            db.execute(update(SharedImportBatch).where(
                SharedImportBatch.expires_at <= now,
                SharedImportBatch.is_deleted.is_(False)).values(
                    status="EXPIRED", claim_token=None, claim_started_at=None,
                    payload_json={}, errors_json=[], public_result_json=None))
            for model in models:
                db.execute(delete(model).where(model.expires_at <= purge_before))
            db.commit()
        return {"expired": due, "purged": purgeable, "applied": apply,
                "purgeAfterDays": max(purge_after_days, 7)}
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--purge-after-days", type=int, default=30)
    args = parser.parse_args()
    print(run(apply=args.apply, purge_after_days=args.purge_after_days))
