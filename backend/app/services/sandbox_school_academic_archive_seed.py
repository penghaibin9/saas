"""sandbox-school · 20K 历史教务归档事实。

不复制第二套归档判断：直接复用正式 13 域归档策略评估 2025-2026-2。
只有全部域 PASS 才生成 ARCHIVED 批次；参考日 2026-08-13 的 2026-2027-1 尚未开学，严禁提前归档。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select

REFERENCE_NOW = datetime(2026, 8, 13, 9, 0)
HISTORICAL_TERM_CODE = "2025-2026-2"
EXPECTED_ARCHIVE_DOMAINS = 13


def _with_tenant_context(tenant_id: int):
    from app.core.context import get_tenant, set_tenant

    class _TenantContext:
        def __enter__(self):
            self.previous = get_tenant()
            set_tenant({"tenantId": str(tenant_id)})
            return self

        def __exit__(self, exc_type, exc, tb):
            set_tenant(self.previous)
            return False

    return _TenantContext()


def seed_school_academic_archive_20k(db, tenant_id: int) -> dict:
    from app.models import AaArchiveBatch, AaArchiveItem, AaTerm
    from app.modules.academic_affairs.services import academic_affairs_archive_service as archive_service

    historical_term = db.scalars(select(AaTerm).where(
        AaTerm.tenant_id == tenant_id,
        AaTerm.year_code == "2025-2026",
        AaTerm.term_no == 2,
        AaTerm.is_deleted.is_(False),
    )).one()
    current_term = db.scalars(select(AaTerm).where(
        AaTerm.tenant_id == tenant_id,
        AaTerm.year_code == "2026-2027",
        AaTerm.term_no == 1,
        AaTerm.is_deleted.is_(False),
    )).one()

    current_count = int(db.scalar(select(func.count()).select_from(AaArchiveBatch).where(
        AaArchiveBatch.tenant_id == tenant_id,
        AaArchiveBatch.term_id == int(current_term.id),
        AaArchiveBatch.is_deleted.is_(False),
    )) or 0)
    if current_count:
        raise RuntimeError("2026-2027-1 尚未开学，禁止提前生成教务归档批次")

    with _with_tenant_context(tenant_id):
        evaluated = archive_service._evaluate_domains(
            db,
            int(historical_term.id),
            HISTORICAL_TERM_CODE,
        )

    blocked = {
        code: {
            "result": row.get("result"),
            "blockingCount": int(row.get("blockingCount") or 0),
            "summary": row.get("summary") or row.get("remark") or "",
        }
        for code, row in evaluated.items()
        if row.get("result") != "PASS"
    }
    if blocked:
        raise RuntimeError(f"2025-2026-2 正式十三域归档仍有阻断: {blocked}")

    batch = AaArchiveBatch(
        tenant_id=tenant_id,
        batch_name="2025-2026学年第二学期教务归档",
        term_id=int(historical_term.id),
        term_code=HISTORICAL_TERM_CODE,
        checked_at=datetime(2026, 7, 20, 10, 0),
        archived_at=datetime(2026, 7, 20, 10, 30),
        missing_count=0,
        remark="由正式十三域归档策略校验通过后生成的历史学期归档事实",
        status="ARCHIVED",
    )
    db.add(batch)
    db.flush()

    labels = dict(archive_service._DOMAINS)
    for code, _label in archive_service._DOMAINS:
        row = archive_service._public_result(code, evaluated[code])
        db.add(AaArchiveItem(
            tenant_id=tenant_id,
            batch_id=int(batch.id),
            domain=code,
            domain_label=labels[code],
            record_count=int(row.get("recordCount") or 0),
            present=True,
            remark=archive_service._persisted_remark(code, row),
        ))
    db.commit()
    return validate_school_academic_archive_20k(db, tenant_id)


def validate_school_academic_archive_20k(db, tenant_id: int) -> dict:
    from app.models import AaArchiveBatch, AaArchiveItem, AaTerm

    historical_term = db.scalars(select(AaTerm).where(
        AaTerm.tenant_id == tenant_id,
        AaTerm.year_code == "2025-2026",
        AaTerm.term_no == 2,
        AaTerm.is_deleted.is_(False),
    )).one()
    current_term = db.scalars(select(AaTerm).where(
        AaTerm.tenant_id == tenant_id,
        AaTerm.year_code == "2026-2027",
        AaTerm.term_no == 1,
        AaTerm.is_deleted.is_(False),
    )).one()
    historical_batches = list(db.scalars(select(AaArchiveBatch).where(
        AaArchiveBatch.tenant_id == tenant_id,
        AaArchiveBatch.term_id == int(historical_term.id),
        AaArchiveBatch.is_deleted.is_(False),
    )).all())
    current_batches = int(db.scalar(select(func.count()).select_from(AaArchiveBatch).where(
        AaArchiveBatch.tenant_id == tenant_id,
        AaArchiveBatch.term_id == int(current_term.id),
        AaArchiveBatch.is_deleted.is_(False),
    )) or 0)
    if len(historical_batches) != 1:
        raise RuntimeError(f"历史教务归档批次异常 expected=1 actual={len(historical_batches)}")
    batch = historical_batches[0]
    items = list(db.scalars(select(AaArchiveItem).where(
        AaArchiveItem.tenant_id == tenant_id,
        AaArchiveItem.batch_id == int(batch.id),
        AaArchiveItem.is_deleted.is_(False),
    )).all())
    failed_items = [row.domain for row in items if not row.present]
    if (
        batch.status != "ARCHIVED"
        or int(batch.missing_count or 0) != 0
        or len(items) != EXPECTED_ARCHIVE_DOMAINS
        or failed_items
        or current_batches != 0
    ):
        raise RuntimeError(
            "20K 教务归档验收失败: "
            f"status={batch.status} missing={batch.missing_count} items={len(items)} "
            f"failed={failed_items} currentAutumn={current_batches}"
        )
    return {
        "historicalArchiveBatches": 1,
        "historicalArchiveItems": len(items),
        "missingDomains": 0,
        "currentAutumnArchiveBatches": current_batches,
        "status": batch.status,
        "passed": True,
    }
