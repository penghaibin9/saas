"""困难认定与奖助公示安全门：正式公示期限、日期校验、并发扫描行锁。"""
from __future__ import annotations

import re
from datetime import datetime, timedelta

from sqlalchemy import select

from app.core.exceptions import AppException
from app.services.db_service import _tid, session

_INSTALLED = False


def _days(value) -> int:
    try:
        days = int(value if value is not None else 5)
    except (TypeError, ValueError) as exc:
        raise AppException("VALIDATION_ERROR", "公示天数必须为整数") from exc
    if days < 1 or days > 30:
        raise AppException("VALIDATION_ERROR", "正式公示天数应为1-30天")
    return days


def _school_year(value) -> str:
    text = str(value or "").strip()
    if not re.fullmatch(r"\d{4}-\d{4}", text):
        raise AppException("VALIDATION_ERROR", "学年格式应为YYYY-YYYY")
    start, end = (int(part) for part in text.split("-"))
    if end != start + 1:
        raise AppException("VALIDATION_ERROR", "学年起止年份必须连续")
    return text


def _validate_dates(service, body) -> None:
    start = service._parse_dt(getattr(body, "applyStart", None))
    end = service._parse_dt(getattr(body, "applyEnd", None))
    if getattr(body, "applyStart", None) and not start:
        raise AppException("VALIDATION_ERROR", "申请开始时间格式不正确")
    if getattr(body, "applyEnd", None) and not end:
        raise AppException("VALIDATION_ERROR", "申请结束时间格式不正确")
    if start and end and end <= start:
        raise AppException("VALIDATION_ERROR", "申请结束时间必须晚于开始时间")


def install() -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    from app.services import affairs_aid_service as aid
    from app.services import affairs_funding_service as funding

    old_aid_create = aid.create_batch
    old_funding_create = funding.create_batch

    def create_aid_batch(body, user):
        body.batchName = str(getattr(body, "batchName", None) or "").strip()
        if not 2 <= len(body.batchName) <= 200:
            raise AppException("VALIDATION_ERROR", "认定批次名称需2-200字")
        body.schoolYear = _school_year(getattr(body, "schoolYear", None))
        body.publicityDays = _days(getattr(body, "publicityDays", None))
        _validate_dates(aid, body)
        return old_aid_create(body, user)

    def create_funding_batch(body, user):
        body.schoolYear = _school_year(getattr(body, "schoolYear", None))
        body.publicityDays = _days(getattr(body, "publicityDays", None))
        _validate_dates(funding, body)
        quota = getattr(body, "quota", None)
        if quota not in (None, ""):
            try:
                quota = int(quota)
            except (TypeError, ValueError) as exc:
                raise AppException("VALIDATION_ERROR", "资助名额必须为整数") from exc
            if quota < 1 or quota > 100000:
                raise AppException("VALIDATION_ERROR", "资助名额应为1-100000")
            body.quota = quota
        return old_funding_create(body, user)

    def scan_aid_publicity():
        from app.models import AidApply, AidBatch
        now = datetime.utcnow()
        with session() as db:
            rows = db.scalars(select(AidApply).where(
                AidApply.tenant_id == _tid(), AidApply.status == "PUBLICITY",
                AidApply.publicity_at.is_not(None), AidApply.is_deleted.is_(False),
            ).order_by(AidApply.id).limit(200).with_for_update(skip_locked=True)).all()
            pending = aid._pending_objection_ids(db, [row.id for row in rows])
            confirmed = skipped = invalid = 0
            for row in rows:
                if int(row.id) in pending:
                    skipped += 1
                    continue
                batch = db.get(AidBatch, int(row.batch_id))
                if not batch or batch.is_deleted or batch.tenant_id != _tid():
                    invalid += 1
                    continue
                due = row.publicity_at + timedelta(days=max(1, int(batch.publicity_days or 5)))
                if due > now:
                    continue
                if int(row.id) in aid._pending_objection_ids(db, [row.id]):
                    skipped += 1
                    continue
                aid._confirm_one(db, row)
                confirmed += 1
            db.commit()
        aid._drain_message_outbox()
        return {"count": confirmed, "skippedObjection": skipped, "invalidBatch": invalid}

    def scan_funding_publicity():
        from app.models import FundingApplication, FundingBatch
        now = datetime.utcnow()
        with session() as db:
            rows = db.scalars(select(FundingApplication).where(
                FundingApplication.tenant_id == _tid(), FundingApplication.status == "PUBLICITY",
                FundingApplication.publicity_at.is_not(None), FundingApplication.is_deleted.is_(False),
            ).order_by(FundingApplication.id).limit(200).with_for_update(skip_locked=True)).all()
            pending = funding._pending_appeal_ids(db, [row.id for row in rows])
            confirmed = skipped = invalid = 0
            for row in rows:
                if int(row.id) in pending:
                    skipped += 1
                    continue
                batch = db.get(FundingBatch, int(row.batch_id))
                if not batch or batch.is_deleted or batch.tenant_id != _tid():
                    invalid += 1
                    continue
                due = row.publicity_at + timedelta(days=max(1, int(batch.publicity_days or 5)))
                if due > now:
                    continue
                if int(row.id) in funding._pending_appeal_ids(db, [row.id]):
                    skipped += 1
                    continue
                funding._grant_one(db, row)
                confirmed += 1
            db.commit()
        funding._drain_message_outbox()
        return {"count": confirmed, "skippedAppeal": skipped, "invalidBatch": invalid}

    aid.create_batch = create_aid_batch
    aid.scan_publicity = scan_aid_publicity
    funding.create_batch = create_funding_batch
    funding.scan_publicity = scan_funding_publicity
    _INSTALLED = True
