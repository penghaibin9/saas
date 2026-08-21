"""Machine-only disaster-recovery evidence authority.

The web application never executes backup/restore commands.  A privileged
systemd/ops runner executes the existing shell scripts and invokes the local CLI
which calls this service.  Manual evidence remains visible but is never accepted
for GREEN health.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select

from app.core.exceptions import AppException
from app.db.session import get_sessionmaker
from app.models.recovery_run import RecoveryRun

RUN_TYPES = {"BACKUP", "RESTORE", "PITR"}
STATUSES = {"RUNNING", "VERIFYING", "PASSED", "FAILED"}
BACKUP_FRESHNESS = timedelta(days=2)
RESTORE_FRESHNESS = timedelta(days=30)


def _session():
    return get_sessionmaker()()


def _utcnow() -> datetime:
    return datetime.utcnow()


def _parse_dt(value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        result = value
    else:
        raw = str(value).strip()
        if raw.endswith("Z"):
            raw = raw[:-1] + "+00:00"
        try:
            result = datetime.fromisoformat(raw)
        except ValueError as exc:
            raise AppException("VALIDATION_ERROR", f"无效时间：{value}") from exc
    if result.tzinfo is not None:
        result = result.astimezone(timezone.utc).replace(tzinfo=None)
    return result


def canonical_evidence(payload: dict) -> dict:
    run_type = str(payload.get("runType") or "").upper()
    status = str(payload.get("status") or "").upper()
    if run_type not in RUN_TYPES:
        raise AppException("VALIDATION_ERROR", f"不支持的 recovery runType：{run_type}")
    if status not in STATUSES:
        raise AppException("VALIDATION_ERROR", f"不支持的 recovery status：{status}")
    source = str(payload.get("source") or "MACHINE").upper()
    if source != "MACHINE":
        raise AppException("VALIDATION_ERROR", "RecoveryRun authority 只接受 MACHINE 证据")
    run_id = str(payload.get("runId") or "").strip()
    if not run_id:
        raise AppException("VALIDATION_ERROR", "runId 必填")
    assertions = dict(payload.get("assertions") or {})
    detail = dict(payload.get("detail") or {})
    result = {
        "schemaVersion": 2,
        "runId": run_id,
        "runType": run_type,
        "source": "MACHINE",
        "status": status,
        "backupSetId": str(payload.get("backupSetId") or "").strip() or None,
        "manifestSha256": str(payload.get("manifestSha256") or "").strip().lower() or None,
        "sourceCommit": str(payload.get("sourceCommit") or "").strip() or None,
        "runnerId": str(payload.get("runnerId") or "").strip() or None,
        "rpoSeconds": int(payload["rpoSeconds"]) if payload.get("rpoSeconds") is not None else None,
        "rtoSeconds": int(payload["rtoSeconds"]) if payload.get("rtoSeconds") is not None else None,
        "targetRpoSeconds": int(payload["targetRpoSeconds"]) if payload.get("targetRpoSeconds") is not None else None,
        "targetRtoSeconds": int(payload["targetRtoSeconds"]) if payload.get("targetRtoSeconds") is not None else None,
        "assertions": assertions,
        "detail": detail,
        "startedAt": _parse_dt(payload.get("startedAt")).isoformat() if _parse_dt(payload.get("startedAt")) else None,
        "finishedAt": _parse_dt(payload.get("finishedAt")).isoformat() if _parse_dt(payload.get("finishedAt")) else None,
    }
    if status == "PASSED" and not result["finishedAt"]:
        raise AppException("VALIDATION_ERROR", "PASSED 机器证据必须有 finishedAt")
    if status == "PASSED" and run_type in {"BACKUP", "RESTORE", "PITR"}:
        digest = str(result["manifestSha256"] or "")
        if not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise AppException("VALIDATION_ERROR", "PASSED 机器证据必须包含64位 manifest SHA256")
    return result


def evidence_sha256(payload: dict) -> str:
    canonical = canonical_evidence(payload)
    raw = json.dumps(canonical, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _require_metric(evidence: dict, actual_key: str, target_key: str, label: str) -> None:
    actual = evidence.get(actual_key)
    target = evidence.get(target_key)
    if actual is None or target is None:
        raise AppException("VALIDATION_ERROR", f"PASSED 机器证据必须包含 {label} 实际值与目标值")
    if int(actual) < 0 or int(target) <= 0:
        raise AppException("VALIDATION_ERROR", f"PASSED 机器证据的 {label} 数值无效")
    if int(actual) > int(target):
        raise AppException("VALIDATION_ERROR", f"PASSED 证据的 {label} 实际值超过目标")


def _passed_contract(evidence: dict) -> None:
    if evidence["status"] != "PASSED":
        return
    assertions = evidence["assertions"]
    if evidence["runType"] == "BACKUP":
        required = (
            "manifestVerified",
            "databaseShaVerified",
            "offsiteReadbackVerified",
            "immutableRemoteConfirmed",
        )
    else:
        required = (
            "manifestVerified",
            "databaseRestoreVerified",
            "schemaVerified",
            "indexesVerified",
            "fileObjectsVerified",
        )
    missing = [key for key in required if assertions.get(key) is not True]
    if missing:
        raise AppException("VALIDATION_ERROR", f"PASSED 机器证据缺少通过断言：{','.join(missing)}")

    # GREEN is meaningful only when freshness/recovery objectives were actually
    # measured. Missing metrics must never be interpreted as "no breach".
    _require_metric(evidence, "rpoSeconds", "targetRpoSeconds", "RPO")
    if evidence["runType"] in {"RESTORE", "PITR"}:
        _require_metric(evidence, "rtoSeconds", "targetRtoSeconds", "RTO")


def record_machine_evidence(payload: dict) -> dict:
    evidence = canonical_evidence(payload)
    _passed_contract(evidence)
    digest = evidence_sha256(payload)
    with _session() as db:
        existing = db.scalars(select(RecoveryRun).where(RecoveryRun.run_id == evidence["runId"])).first()
        if existing is not None:
            if existing.evidence_sha256 != digest:
                raise AppException("DATA_CONFLICT", "runId 已存在但证据摘要不同，拒绝覆盖", http_status=409)
            return _dto(existing)
        same_digest = db.scalars(select(RecoveryRun).where(RecoveryRun.evidence_sha256 == digest)).first()
        if same_digest is not None:
            return _dto(same_digest)
        row = RecoveryRun(
            run_id=evidence["runId"], run_type=evidence["runType"], source="MACHINE",
            status=evidence["status"], backup_set_id=evidence["backupSetId"],
            manifest_sha256=evidence["manifestSha256"], evidence_sha256=digest,
            source_commit=evidence["sourceCommit"], runner_id=evidence["runnerId"],
            rpo_seconds=evidence["rpoSeconds"], rto_seconds=evidence["rtoSeconds"],
            target_rpo_seconds=evidence["targetRpoSeconds"], target_rto_seconds=evidence["targetRtoSeconds"],
            assertions_json=evidence["assertions"], detail_json=evidence["detail"],
            started_at=_parse_dt(evidence["startedAt"]), finished_at=_parse_dt(evidence["finishedAt"]),
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return _dto(row)


def _dto(row: RecoveryRun) -> dict:
    return {
        "id": str(row.id), "runId": row.run_id, "runType": row.run_type,
        "source": row.source, "status": row.status, "backupSetId": row.backup_set_id,
        "manifestSha256": row.manifest_sha256, "evidenceSha256": row.evidence_sha256,
        "sourceCommit": row.source_commit, "runnerId": row.runner_id,
        "rpoSeconds": row.rpo_seconds, "rtoSeconds": row.rto_seconds,
        "targetRpoSeconds": row.target_rpo_seconds, "targetRtoSeconds": row.target_rto_seconds,
        "assertions": row.assertions_json or {}, "detail": row.detail_json or {},
        "startedAt": row.started_at.isoformat() if row.started_at else None,
        "finishedAt": row.finished_at.isoformat() if row.finished_at else None,
    }


def list_machine_runs(*, run_type: str | None = None, limit: int = 50) -> list[dict]:
    with _session() as db:
        q = select(RecoveryRun).where(RecoveryRun.source == "MACHINE")
        if run_type:
            q = q.where(RecoveryRun.run_type == str(run_type).upper())
        rows = db.scalars(q.order_by(RecoveryRun.id.desc()).limit(max(1, min(int(limit), 500)))).all()
        return [_dto(row) for row in rows]


def _latest(db, run_type: str) -> RecoveryRun | None:
    return db.scalars(select(RecoveryRun).where(
        RecoveryRun.source == "MACHINE", RecoveryRun.run_type == run_type,
    ).order_by(RecoveryRun.finished_at.desc(), RecoveryRun.id.desc())).first()


def _state(row: RecoveryRun | None, *, freshness: timedelta, now: datetime) -> dict:
    if row is None:
        return {"status": "UNKNOWN", "stale": True, "lastRun": None}
    finished = row.finished_at
    stale = finished is None or now - finished > freshness
    if row.status != "PASSED":
        status = "RED"
    elif stale:
        status = "RED"
    else:
        status = "GREEN"
    return {"status": status, "stale": stale, "lastRun": _dto(row)}


def machine_health() -> dict:
    now = _utcnow()
    with _session() as db:
        backup = _state(_latest(db, "BACKUP"), freshness=BACKUP_FRESHNESS, now=now)
        restore = _state(_latest(db, "RESTORE"), freshness=RESTORE_FRESHNESS, now=now)
        pitr_row = _latest(db, "PITR")
        pitr = _state(pitr_row, freshness=RESTORE_FRESHNESS, now=now) if pitr_row else {
            "status": "UNKNOWN", "stale": True, "lastRun": None,
        }
    # A known failed/stale authority must dominate missing evidence. UNKNOWN is
    # reserved for the case where no dimension is RED but evidence is incomplete.
    if backup["status"] == "RED" or restore["status"] == "RED":
        overall = "RED"
    elif backup["status"] == "GREEN" and restore["status"] == "GREEN":
        overall = "GREEN"
    else:
        overall = "UNKNOWN"
    return {
        "status": overall,
        "authority": "MACHINE_ONLY",
        "manualEvidenceHealthEligible": False,
        "backup": backup,
        "restore": restore,
        "pitr": pitr,
        "backupFreshnessHours": int(BACKUP_FRESHNESS.total_seconds() // 3600),
        "restoreFreshnessDays": RESTORE_FRESHNESS.days,
    }


def governance_overview_with_machine(base_overview: dict) -> dict:
    """Overlay legacy display DTO with machine-only health semantics."""
    health = machine_health()
    result = dict(base_overview or {})
    result["machineHealth"] = health
    restore = dict(result.get("restoreDrill") or {})
    machine_restore = health["restore"].get("lastRun")
    restore.update({
        "hasPassedDrill": bool(machine_restore and health["restore"]["status"] == "GREEN"),
        "lastPassedAt": machine_restore.get("finishedAt") if machine_restore and machine_restore.get("status") == "PASSED" else None,
        "stale": health["restore"]["status"] != "GREEN",
        "healthAuthority": "MACHINE_ONLY",
        "manualRecordsHealthEligible": False,
    })
    result["restoreDrill"] = restore
    for info in (result.get("byType") or {}).values():
        info["manualRecordsHealthEligible"] = False
    return result
