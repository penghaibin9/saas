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
from sqlalchemy import func, literal, select, union_all

from app.core.exceptions import AppException
from app.core.timeutil import iso_utc, tenant_tz, utc_now_naive
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


def available_actions(kind_meta: dict, row, *, can_manage: bool) -> dict:
    status = str(getattr(row, kind_meta["statusField"]))
    expired = bool(getattr(row, "expires_at", None) and row.expires_at <= utc_now_naive())
    revision_field = kind_meta.get("revisionField")
    stale = bool(revision_field and kind_meta.get("currentRevision")
                 and getattr(row, revision_field, None) != kind_meta["currentRevision"])
    result = {}
    for action, statuses in (("retry", kind_meta.get("retryableFrom") or []),
                             ("cancel", kind_meta.get("cancellableFrom") or [])):
        reason = ("当前身份没有任务管理权限" if not can_manage else "任务已过期，请回所属业务核对" if expired
                  else "任务版本已变化，请回所属业务重新校验" if action == "retry" and stale
                  else "此类任务不支持在此办理" if not statuses
                  else "当前状态不可执行此操作" if status not in statuses else "")
        result[action] = {"allowed": not reason, "reason": reason}
    return result


def _row_to_dto(kind: str, kind_meta: dict, row, *, can_manage: bool = False) -> dict:
    scope_field = kind_meta.get("scopeSnapshotField")
    revision_field = kind_meta.get("revisionField")
    return {
        "jobId": f"{kind}:{row.id}",
        "kind": kind,
        "ownerModule": getattr(row, "module_code", None) or kind_meta.get("ownerModule"),
        "tenantId": str(row.tenant_id),
        "initiator": str(getattr(row, "operator_id", None) or row.created_by) if (getattr(row, "operator_id", None) or row.created_by) is not None else None,
        "status": getattr(row, kind_meta["statusField"]),
        "scopeSnapshot": getattr(row, scope_field, None) if scope_field else None,
        "revision": getattr(row, revision_field, None) if revision_field else None,
        "idempotency": getattr(row, "idempotency_key", None) or getattr(row, "dedupe_key", None),
        "version": int(row.version or 0),
        "createdAt": iso_utc(row.created_at), "timeZone": str(tenant_tz()),
        "updatedAt": iso_utc(getattr(row, "updated_at", None)),
        "availableActions": available_actions(kind_meta, row, can_manage=can_manage),
    }


def list_jobs(db, *, kind: str | None = None, status: str | None = None,
             page: int = 1, page_size: int = 50, actor=None) -> tuple[list[dict], int]:
    tid = _tid()
    kinds = _kinds()
    from app.services import job_authorization_service as jauth
    can_manage = jauth.classify(actor, "systemAdmin.job.manage") is not None
    target_kinds = [kind] if kind and kind in kinds else (list(kinds.keys()) if not kind else [])
    page = max(1, int(page))
    page_size = min(200, max(1, int(page_size)))
    queries = []
    sources = {}
    total = 0
    for k in target_kinds:
        meta = kinds[k]
        model = _model_for(meta)
        conds = [model.tenant_id == tid, model.is_deleted.is_(False)]
        if status:
            conds.append(getattr(model, meta["statusField"]) == status)
        total += int(db.scalar(select(func.count()).select_from(model).where(*conds)) or 0)
        queries.append(select(literal(k).label('kind'), model.id.label('id'), model.created_at.label('created_at')).where(*conds))
        sources[k] = (meta, model, conds)
    if not queries or not total or (page - 1) * page_size >= total:
        return [], total
    combined = union_all(*queries).subquery()
    selected = db.execute(select(combined.c.kind, combined.c.id).order_by(
        combined.c.created_at.desc(), combined.c.kind, combined.c.id.desc()).offset((page - 1) * page_size).limit(page_size)).all()
    items = {}
    for k, (meta, model, conds) in sources.items():
        ids = [pk for selected_kind, pk in selected if selected_kind == k]
        if not ids:
            continue
        for row in db.scalars(select(model).where(*conds, model.id.in_(ids))).all():
            items[(k, row.id)] = _row_to_dto(k, meta, row, can_manage=can_manage)
    return [items[(k, pk)] for k, pk in selected if (k, pk) in items], total


def get_job(db, job_id: str, *, for_update: bool = False):
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
    query = select(model).where(model.id == pk, model.tenant_id == _tid(), model.is_deleted.is_(False))
    if for_update:
        query = query.with_for_update().execution_options(populate_existing=True)
    row = db.scalars(query).first()
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
        counts = dict(db.execute(select(status_field, func.count()).where(
            model.tenant_id == tid, model.is_deleted.is_(False)).group_by(status_field)).all())
        k_failed = sum(counts.get(value, 0) for value in ("FAILED", "DEAD", "TIMEOUT"))
        k_running = sum(counts.get(value, 0) for value in ("RUNNING", "PROCESSING", "VALIDATING", "CONFIRMING"))
        k_backlog = sum(counts.get(value, 0) for value in ("PENDING", "CREATED", "UPLOADED", "VALIDATED"))
        running += k_running
        failed += k_failed
        backlog += k_backlog
        per_kind.append({"kind": k, "total": sum(counts.values()), "running": k_running,
                         "failed": k_failed, "backlog": k_backlog})
    return {
        "running": running, "failed": failed, "backlog": backlog,
        "perKind": per_kind, "registryVersion": _load_registry().get("version"),
    }


def _require_action_permission(actor):
    from app.services import job_authorization_service as jauth
    return jauth.classify_and_authorize(actor, "systemAdmin.job.manage")


def _check_command(row, expected_version, reason: str) -> str:
    from app.core.optimistic_lock import require_expected_version
    if type(expected_version) is not int or expected_version < 0:
        raise AppException("VALIDATION_ERROR", "任务版本无效，请重新读取", http_status=422)
    version = require_expected_version(expected_version)
    if version != int(row.version or 0):
        raise AppException("DATA_CONFLICT", "任务已被其他操作更新，请重新读取后核对", http_status=409)
    if not isinstance(reason, str):
        raise AppException("VALIDATION_ERROR", "操作原因必须是文字说明", http_status=422)
    reason = reason.strip()
    if len(reason) < 5:
        raise AppException("VALIDATION_ERROR", "请填写至少5个字的具体操作原因", http_status=422)
    return reason


def retry_job(db, job_id: str, *, actor, expected_version, reason: str) -> dict:
    from app.services import audit_log

    evidence = _require_action_permission(actor)
    kind, meta, row = get_job(db, job_id, for_update=True)
    reason = _check_command(row, expected_version, reason)
    retryable_from = meta.get("retryableFrom") or []
    action = available_actions(meta, row, can_manage=True)["retry"]
    if not action["allowed"]:
        raise AppException("DATA_CONFLICT" if retryable_from else "VALIDATION_ERROR",
                           action["reason"], http_status=409 if retryable_from else 422)
    current_status = getattr(row, meta["statusField"])

    setattr(row, meta["statusField"], meta.get("initialStatus") or "PENDING")
    if hasattr(row, "locked_by"):
        row.locked_by = None
    if hasattr(row, "locked_at"):
        row.locked_at = None
    row.version = int(row.version or 0) + 1
    row.updated_at = datetime.utcnow()
    audit_log.record_critical_in_session(db, "JOB_RETRY", f"job:{job_id}",
        detail={"kind": kind, "fromStatus": current_status, "toStatus": getattr(row, meta["statusField"]),
         "reason": reason, "expectedVersion": expected_version, "version": row.version, "authorization": evidence},
        tenant_id=row.tenant_id, resource_id=job_id)
    db.commit()
    return {"jobId": job_id, "status": getattr(row, meta["statusField"]), "version": row.version, "authorization": evidence}


def cancel_job(db, job_id: str, *, actor, expected_version, reason: str) -> dict:
    from app.services import audit_log

    evidence = _require_action_permission(actor)
    kind, meta, row = get_job(db, job_id, for_update=True)
    reason = _check_command(row, expected_version, reason)
    action = available_actions(meta, row, can_manage=True)["cancel"]
    if not action["allowed"]:
        raise AppException("DATA_CONFLICT", action["reason"], http_status=409)
    current_status = getattr(row, meta["statusField"])

    setattr(row, meta["statusField"], "CANCELLED")
    row.version = int(row.version or 0) + 1
    row.updated_at = datetime.utcnow()
    audit_log.record_critical_in_session(db, "JOB_CANCEL", f"job:{job_id}",
        detail={"kind": kind, "fromStatus": current_status, "toStatus": "CANCELLED", "reason": reason,
         "expectedVersion": expected_version, "version": row.version, "authorization": evidence},
        tenant_id=row.tenant_id, resource_id=job_id)
    db.commit()
    return {"jobId": job_id, "status": "CANCELLED", "version": row.version, "authorization": evidence}


def authorization_evidence(db, job_id: str, *, actor) -> dict:
    """展示任务本身已有的可核验事实（initiator/scopeSnapshot/revision/idempotency），
    并附带"如果现在由你来操作这个任务"会走哪种授权策略——不伪造任务创建时的历史授权
    （创建方不在本卡白名单内，没有真实数据可读）。"""
    from app.services import job_authorization_service as jauth

    kind, meta, row = get_job(db, job_id)
    live_policy = jauth.classify(actor, "systemAdmin.job.manage")
    dto = _row_to_dto(kind, meta, row, can_manage=live_policy is not None)
    return {**dto, "currentActorAuthorization": live_policy, "checkedAt": datetime.utcnow().isoformat()}
