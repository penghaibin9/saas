"""SYS-16 批处理、调度与后台任务：跨既有任务表的只读聚合 + 有限管理动作。

不新建统一任务大表；权威数据仍是 t_import_job / t_export_job / t_file_job /
t_excel_import_job / t_affairs_batch_job 五张既有表，注册表见
docs/architecture/job-registry.yaml。任务的创建方（file_service.py、
data_exchange_confirm_service.py、academic_file_exchange_service.py 等）不在
本卡白名单内，本模块只读它们写的行，retry/cancel 只在注册表登记为安全的
范围内翻转状态列，不重放任何业务导入/导出逻辑。

jobId 编码为 "{KIND}:{原表主键}"，跨表还能唯一定位、还能按 tenant_id 过滤
做到"跨租户 jobId 一律 404"（SYS16-T02）——永远在 WHERE 里带 tenant_id，
不是先查到再比对，避免用错误信息把别的租户任务的存在性泄露出去。
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

import yaml
from sqlalchemy import select

from app.core.exceptions import AppException
from app.services.db_service import _tid

REGISTRY_PATH = Path(__file__).resolve().parents[3] / "docs" / "architecture" / "job-registry.yaml"

_cache: dict[str, Any] = {}


def _load_registry() -> dict[str, Any]:
    mtime = REGISTRY_PATH.stat().st_mtime if REGISTRY_PATH.exists() else None
    if _cache.get("_mtime") == mtime and "_mtime" in _cache:
        return _cache["data"]
    data = {"version": 0, "kinds": []} if not REGISTRY_PATH.exists() else \
        (yaml.safe_load(REGISTRY_PATH.read_text(encoding="utf-8")) or {})
    _cache["_mtime"] = mtime
    _cache["data"] = data
    return data


def _kinds() -> dict[str, dict]:
    return {str(k.get("kind")): k for k in _load_registry().get("kinds", [])}


def list_kinds() -> list[dict]:
    return _load_registry().get("kinds", [])


def _model_for(kind_meta: dict):
    """按注册表登记的 module 直接导模型类，不依赖 app.models 聚合导出
    （FileJob/AffairsBatchJob 等本就没有在 app/models/__init__.py 里重新导出，
    那个文件不在本卡白名单内，不代它补导出）。"""
    import importlib
    mod = importlib.import_module(kind_meta["module"])
    return getattr(mod, kind_meta["model"])


def _row_to_dto(kind: str, kind_meta: dict, row) -> dict:
    scope_field = kind_meta.get("scopeSnapshotField")
    revision_field = kind_meta.get("revisionField")
    return {
        "jobId": f"{kind}:{row.id}",
        "kind": kind,
        "ownerModule": kind_meta.get("ownerModule"),
        "tenantId": str(row.tenant_id),
        "initiator": str(row.created_by) if row.created_by is not None else None,
        "status": getattr(row, kind_meta["statusField"]),
        "scopeSnapshot": getattr(row, scope_field, None) if scope_field else None,
        "revision": getattr(row, revision_field, None) if revision_field else None,
        "idempotency": getattr(row, "idempotency_key", None) or getattr(row, "dedupe_key", None),
        "version": int(row.version or 0),
        "createdAt": row.created_at.isoformat() if row.created_at else None,
        "updatedAt": row.updated_at.isoformat() if getattr(row, "updated_at", None) else None,
    }


def list_jobs(db, *, kind: str | None = None, status: str | None = None,
             page: int = 1, page_size: int = 50) -> tuple[list[dict], int]:
    tid = _tid()
    kinds = _kinds()
    target_kinds = [kind] if kind and kind in kinds else (list(kinds.keys()) if not kind else [])
    items: list[dict] = []
    for k in target_kinds:
        meta = kinds[k]
        model = _model_for(meta)
        conds = [model.tenant_id == tid, model.is_deleted.is_(False)]
        if status:
            conds.append(getattr(model, meta["statusField"]) == status)
        rows = db.scalars(select(model).where(*conds).order_by(model.id.desc()).limit(500)).all()
        items.extend(_row_to_dto(k, meta, r) for r in rows)
    items.sort(key=lambda x: x["createdAt"] or "", reverse=True)
    total = len(items)
    start = (page - 1) * page_size
    return items[start:start + page_size], total


def get_job(db, job_id: str):
    """按 jobId=kind:id 定位，永远带 tenant_id 过滤；找不到或跨租户一律 404。"""
    kinds = _kinds()
    try:
        kind, raw_id = job_id.split(":", 1)
        pk = int(raw_id)
    except (ValueError, AttributeError):
        raise AppException("DATA_NOT_FOUND", "任务不存在", http_status=404)
    meta = kinds.get(kind)
    if not meta:
        raise AppException("DATA_NOT_FOUND", "任务不存在", http_status=404)
    model = _model_for(meta)
    row = db.scalars(select(model).where(
        model.id == pk, model.tenant_id == _tid(), model.is_deleted.is_(False))).first()
    if not row:
        raise AppException("DATA_NOT_FOUND", "任务不存在", http_status=404)
    return kind, meta, row


def job_overview(db=None) -> dict[str, Any]:
    if db is None:
        from app.db.session import get_sessionmaker
        session = get_sessionmaker()()
        try:
            return job_overview(session)
        finally:
            session.close()

    tid = _tid()
    kinds = _kinds()
    running = failed = backlog = 0
    per_kind: list[dict] = []
    for k, meta in kinds.items():
        model = _model_for(meta)
        status_field = getattr(model, meta["statusField"])
        rows = db.scalars(select(model).where(
            model.tenant_id == tid, model.is_deleted.is_(False))).all()
        k_failed = sum(1 for r in rows if str(getattr(r, meta["statusField"])) in
                      ("FAILED", "DEAD", "TIMEOUT"))
        k_running = sum(1 for r in rows if str(getattr(r, meta["statusField"])) in
                        ("RUNNING", "PROCESSING", "VALIDATING", "CONFIRMING"))
        k_backlog = sum(1 for r in rows if str(getattr(r, meta["statusField"])) in
                        ("PENDING", "CREATED", "UPLOADED", "VALIDATED"))
        running += k_running
        failed += k_failed
        backlog += k_backlog
        per_kind.append({"kind": k, "total": len(rows), "running": k_running,
                         "failed": k_failed, "backlog": k_backlog})
    return {
        "running": running, "failed": failed, "backlog": backlog,
        "perKind": per_kind, "registryVersion": _load_registry().get("version"),
    }


def _require_action_permission(actor):
    from app.services import job_authorization_service as jauth
    return jauth.classify_and_authorize(actor, "systemAdmin.job.manage")


def retry_job(db, job_id: str, *, actor) -> dict:
    from app.services import audit_log

    evidence = _require_action_permission(actor)
    kind, meta, row = get_job(db, job_id)
    retryable_from = meta.get("retryableFrom") or []
    current_status = getattr(row, meta["statusField"])
    if current_status not in retryable_from:
        if not retryable_from:
            raise AppException("VALIDATION_ERROR",
                               f"{kind} 类型任务不支持在本页重试，请到所属模块处理", http_status=422)
        raise AppException("DATA_CONFLICT",
                           f"仅 {retryable_from} 状态可重试，当前状态为 {current_status}", http_status=409)

    revision_field = meta.get("revisionField")
    current_revision = meta.get("currentRevision")
    if revision_field and current_revision and getattr(row, revision_field, None) != current_revision:
        raise AppException(
            "DATA_CONFLICT",
            f"任务基于旧版本（{getattr(row, revision_field)}，当前为 {current_revision}），"
            "拒绝直接重试，请回所属模块重新校验后再执行", http_status=409)

    setattr(row, meta["statusField"], meta.get("initialStatus") or "PENDING")
    if hasattr(row, "locked_by"):
        row.locked_by = None
    if hasattr(row, "locked_at"):
        row.locked_at = None
    row.version = int(row.version or 0) + 1
    row.updated_at = datetime.utcnow()
    db.commit()

    audit_log.record("JOB_RETRY", f"job:{job_id}",
                     {"kind": kind, "fromStatus": current_status, "authorization": evidence})
    return {"jobId": job_id, "status": getattr(row, meta["statusField"]), "authorization": evidence}


def cancel_job(db, job_id: str, *, actor, reason: str = "") -> dict:
    from app.services import audit_log

    evidence = _require_action_permission(actor)
    kind, meta, row = get_job(db, job_id)
    cancellable_from = meta.get("cancellableFrom") or []
    current_status = getattr(row, meta["statusField"])
    if current_status not in cancellable_from:
        raise AppException(
            "DATA_CONFLICT",
            f"任务已开始处理（当前状态 {current_status}），无法在本页取消，请到所属模块处理",
            http_status=409)

    setattr(row, meta["statusField"], "CANCELLED")
    row.version = int(row.version or 0) + 1
    row.updated_at = datetime.utcnow()
    db.commit()

    audit_log.record("JOB_CANCEL", f"job:{job_id}",
                     {"kind": kind, "fromStatus": current_status, "reason": reason,
                      "authorization": evidence})
    return {"jobId": job_id, "status": "CANCELLED", "authorization": evidence}


def authorization_evidence(db, job_id: str, *, actor) -> dict:
    """展示任务本身已有的可核验事实（initiator/scopeSnapshot/revision/idempotency），
    并附带"如果现在由你来操作这个任务"会走哪种授权策略——不伪造任务创建时的历史授权
    （创建方不在本卡白名单内，没有真实数据可读）。"""
    from app.services import job_authorization_service as jauth

    kind, meta, row = get_job(db, job_id)
    dto = _row_to_dto(kind, meta, row)
    live_policy = jauth.classify(actor, "systemAdmin.job.manage")
    return {**dto, "currentActorAuthorization": live_policy, "checkedAt": datetime.utcnow().isoformat()}
