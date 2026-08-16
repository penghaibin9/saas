"""sandbox-school · 20K 历史教务归档事实。

不复制第二套归档判断：先补齐完整三年制培养方案、历史教学闭环和历史结账前置事实，
再直接复用正式 13 域归档策略评估 2025-2026-2。只有不存在 BLOCKED / UNKNOWN 域才生成
ARCHIVED 批次；NOT_APPLICABLE 保留为正式四态事实且不构成阻断。参考日 2026-08-13 的
2026-2027-1 尚未开学，严禁提前归档。

每次正式预检都会把完整 PASS/BLOCKED/NOT_APPLICABLE/UNKNOWN 结果和耗时写入
``test-results/sandbox-20k/archive-precheck.json``，供 20K gate artifact 留证。
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from time import perf_counter

from sqlalchemy import func, select

REFERENCE_NOW = datetime(2026, 8, 13, 9, 0)
HISTORICAL_TERM_CODE = "2025-2026-2"
EXPECTED_ARCHIVE_DOMAINS = 13


def _with_tenant_context(tenant_id: int):
    from app.core.context import get_tenant, set_tenant

    class _TenantContext:
        def __enter__(self):
            self.previous = get_tenant()
            set_tenant({"tenantId": str(tenant_id), "tenantCode": "sandbox-school"})
            return self

        def __exit__(self, exc_type, exc, tb):
            set_tenant(self.previous)
            return False

    return _TenantContext()


def _write_precheck_artifact(payload: dict) -> None:
    target = Path("test-results/sandbox-20k/archive-precheck.json")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, default=str),
        encoding="utf-8",
    )


def seed_school_academic_archive_20k(db, tenant_id: int) -> dict:
    from app.models import AaArchiveBatch, AaArchiveItem, AaTerm
    from app.modules.academic_affairs.services import academic_affairs_archive_service as archive_service
    from app.services.sandbox_school_academic_affairs_reconcile import reconcile_exam_rooms
    from app.services.sandbox_school_academic_archive_prereq import (
        seed_school_academic_archive_prerequisites_20k,
    )
    from app.services.sandbox_school_curriculum_closure import (
        prepare_school_curriculum_20k,
        seed_historical_teaching_closure_20k,
    )
    from app.services.sandbox_school_professional_runner import (
        reconcile_professional_academic_snapshots,
    )

    # 先把“名义140学分但只有28学分课程”的方案补成真实三年制140学分方案，
    # 再补齐 2024/2025 两届已经发生的 1024 教学任务和 52K 成绩闭环。
    curriculum = prepare_school_curriculum_20k(db, tenant_id)
    historical_teaching = seed_historical_teaching_closure_20k(db, tenant_id)

    # 历史闭环会新增 1024 条课表/成绩/考务快照；必须在归档预检前重新按
    # course/class/task canonical 关系收口，避免重建主流程缓存旧的“已通过”结果。
    snapshot_reconciliation = reconcile_professional_academic_snapshots(db, tenant_id)

    # 结账前置：96正式方案绑定、13K春季注册、历史正式课表状态、52K成绩身份/策略快照。
    prerequisites = seed_school_academic_archive_prerequisites_20k(db, tenant_id)

    # 历史考试课程已经扩到1024门；统一考场容量重排器负责拆考场/座位/监考，
    # 正式 EXAM policy 因此看到的就是最终可归档考务事实。
    exam_reconciliation = reconcile_exam_rooms(db, tenant_id)

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

    started = perf_counter()
    with _with_tenant_context(tenant_id):
        evaluated = archive_service._evaluate_domains(
            db,
            int(historical_term.id),
            HISTORICAL_TERM_CODE,
        )
    elapsed_ms = round((perf_counter() - started) * 1000, 2)

    domains = {}
    blocked = {}
    for code, row in evaluated.items():
        public = archive_service._public_result(code, row)
        summary = {
            "result": public.get("result"),
            "recordCount": int(public.get("recordCount") or 0),
            "blockingCount": int(public.get("blockingCount") or 0),
            "ruleCode": public.get("ruleCode"),
            "summary": public.get("summary") or public.get("remark") or "",
            "route": public.get("route"),
            "evidence": list(public.get("evidence") or []),
        }
        domains[code] = summary
        if summary["result"] in archive_service._BLOCKING_RESULTS:
            blocked[code] = summary

    precheck = {
        "tenantId": str(tenant_id),
        "termCode": HISTORICAL_TERM_CODE,
        "termId": str(historical_term.id),
        "evaluatedAt": "2026-08-13T09:00:00",
        "elapsedMs": elapsed_ms,
        "domainCount": len(domains),
        # 兼容历史 artifact 字段名；语义是“归档门禁无阻断”，不是十三域字面全部 PASS。
        "allPass": not blocked and len(domains) == EXPECTED_ARCHIVE_DOMAINS,
        "blockedDomains": list(blocked),
        "curriculum": curriculum.get("validation") or curriculum,
        "historicalTeaching": historical_teaching,
        "snapshotReconciliation": snapshot_reconciliation,
        "prerequisites": prerequisites.get("validation") or prerequisites,
        "examReconciliation": exam_reconciliation,
        "domains": domains,
    }
    _write_precheck_artifact(precheck)

    if len(domains) != EXPECTED_ARCHIVE_DOMAINS:
        raise RuntimeError(
            f"正式归档规则域数量异常 expected={EXPECTED_ARCHIVE_DOMAINS} actual={len(domains)}"
        )
    if blocked:
        compact = {
            code: {
                "result": row["result"],
                "blockingCount": row["blockingCount"],
                "summary": row["summary"],
            }
            for code, row in blocked.items()
        }
        raise RuntimeError(f"2025-2026-2 正式十三域归档仍有阻断: {compact}")

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
            # 与正式 run_check 完全一致：N/A/UNKNOWN/BLOCKED 的兼容位均为 false，
            # 四态真值由 remark 持久化并在读取时恢复。
            present=row["result"] == "PASS",
            remark=archive_service._persisted_remark(code, row),
        ))
    db.commit()
    validation = validate_school_academic_archive_20k(db, tenant_id)
    return {
        "curriculum": curriculum,
        "historicalTeaching": historical_teaching,
        "snapshotReconciliation": snapshot_reconciliation,
        "prerequisites": prerequisites,
        "examReconciliation": exam_reconciliation,
        "precheckElapsedMs": elapsed_ms,
        "precheckArtifact": "test-results/sandbox-20k/archive-precheck.json",
        "validation": validation,
    }


def validate_school_academic_archive_20k(db, tenant_id: int) -> dict:
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

    blocking_items = []
    invalid_present_items = []
    not_applicable_items = []
    for row in items:
        restored = archive_service.parse_persisted_remark(
            row.domain,
            row.remark,
            present=bool(row.present),
            record_count=int(row.record_count or 0),
        )
        state = restored["result"]
        if state in archive_service._BLOCKING_RESULTS:
            blocking_items.append(row.domain)
        if state == "NOT_APPLICABLE":
            not_applicable_items.append(row.domain)
        if bool(row.present) != (state == "PASS"):
            invalid_present_items.append(f"{row.domain}:{state}:present={bool(row.present)}")

    if (
        batch.status != "ARCHIVED"
        or int(batch.missing_count or 0) != 0
        or len(items) != EXPECTED_ARCHIVE_DOMAINS
        or blocking_items
        or invalid_present_items
        or current_batches != 0
    ):
        raise RuntimeError(
            "20K 教务归档验收失败: "
            f"status={batch.status} missing={batch.missing_count} items={len(items)} "
            f"blocking={blocking_items} invalidPresent={invalid_present_items} "
            f"currentAutumn={current_batches}"
        )
    return {
        "historicalArchiveBatches": 1,
        "historicalArchiveItems": len(items),
        "missingDomains": 0,
        "notApplicableDomains": not_applicable_items,
        "currentAutumnArchiveBatches": current_batches,
        "status": batch.status,
        "passed": True,
    }
