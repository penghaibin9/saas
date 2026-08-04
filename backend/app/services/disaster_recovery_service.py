"""PLAT-12 备份恢复验证与灾备：证据记录 + 只读 schema 完整性自检。

真正执行备份/恢复的工具（mysqldump、云厂商托管备份、COS 同步）不在本服务
职责内——那些是部署环境的事，本仓库不自带。本服务提供两类真实能力：
①记录证据（运维手动登记，或未来的定时脚本调用）；②唯一不需要任何外部
工具、随时能真跑的自检——校验当前数据库实际表结构是否与代码里声明的
模型完全一致，这本身就是"能不能用现有迁移链重建出正确 schema"的一个
真实证据点（不证明数据能恢复，只证明结构能恢复）。
"""
from __future__ import annotations

import hashlib
from datetime import datetime, timedelta

from sqlalchemy import inspect, select

from app.core.context import get_current_user_ctx
from app.core.exceptions import AppException, not_found
from app.db.session import get_sessionmaker
from app.models.disaster_recovery import BackupEvidence, RestoreDrill

BACKUP_TYPES = ("DATABASE_DUMP", "SCHEMA_INTEGRITY", "FILE_STORAGE_SYNC", "CLOUD_MANAGED")
BACKUP_METHODS = ("MYSQLDUMP", "SCHEMA_INSPECT", "MANUAL_CONFIRMED", "CLOUD_MANAGED")
DRILL_TYPES = ("SCHEMA_REBUILD_CHECK", "DATA_ROW_COUNT_COMPARE", "MANUAL_CONFIRMED")

# 多久没有一条"成功"证据就算过期风险；数据库备份比 schema 自检要求更严格。
STALENESS_DAYS = {"DATABASE_DUMP": 2, "SCHEMA_INTEGRITY": 7, "FILE_STORAGE_SYNC": 2, "CLOUD_MANAGED": 2}
DRILL_STALENESS_DAYS = 30


def _now() -> datetime:
    return datetime.utcnow()


def _session():
    return get_sessionmaker()()


def _actor_id(user: dict | None = None) -> int | None:
    u = user or get_current_user_ctx() or {}
    uid = u.get("userId")
    try:
        return int(str(uid).removeprefix("db-")) if uid is not None else None
    except (TypeError, ValueError):
        return None


def _evidence_dto(row: BackupEvidence) -> dict:
    return {
        "id": str(row.id), "backupType": row.backup_type, "method": row.method,
        "status": row.status, "locationRef": row.location_ref,
        "sizeBytes": row.size_bytes, "checksumSha256": row.checksum_sha256,
        "tableCount": row.table_count, "detail": row.detail_json or {},
        "errorMessage": row.error_message,
        "startedAt": row.started_at.isoformat() if row.started_at else None,
        "finishedAt": row.finished_at.isoformat() if row.finished_at else None,
    }


def _drill_dto(row: RestoreDrill) -> dict:
    return {
        "id": str(row.id), "backupEvidenceId": str(row.backup_evidence_id) if row.backup_evidence_id else None,
        "drillType": row.drill_type, "status": row.status,
        "targetDescription": row.target_description, "detail": row.detail_json or {},
        "performedAt": row.performed_at.isoformat() if row.performed_at else None,
    }


def record_backup_evidence(user: dict | None, body: dict) -> dict:
    """人工登记（比如云数据库自带自动备份、运维手动跑了 mysqldump）。"""
    backup_type = str(body.get("backupType") or "").upper()
    method = str(body.get("method") or "").upper()
    status = str(body.get("status") or "").upper()
    if backup_type not in BACKUP_TYPES:
        raise AppException("VALIDATION_ERROR", f"不支持的备份类型：{backup_type}")
    if method not in BACKUP_METHODS:
        raise AppException("VALIDATION_ERROR", f"不支持的备份方式：{method}")
    if status not in ("SUCCEEDED", "FAILED"):
        raise AppException("VALIDATION_ERROR", "status 必须是 SUCCEEDED 或 FAILED")
    if status == "SUCCEEDED" and not str(body.get("locationRef") or "").strip():
        raise AppException("VALIDATION_ERROR", "登记成功的备份必须填写存放位置/备份ID，否则出事时找不到")

    with _session() as db:
        now = _now()
        row = BackupEvidence(
            backup_type=backup_type, method=method, status=status,
            location_ref=body.get("locationRef") or None,
            size_bytes=int(body["sizeBytes"]) if body.get("sizeBytes") else None,
            checksum_sha256=body.get("checksumSha256") or None,
            detail_json={"note": body.get("note") or ""},
            error_message=body.get("errorMessage") or None,
            captured_by=_actor_id(user), started_at=now, finished_at=now,
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return _evidence_dto(row)


def record_restore_drill(user: dict | None, body: dict) -> dict:
    """人工登记一次真实做过的恢复演练（比如运维在隔离环境真的拿备份恢复过一次并核对了数据）。"""
    drill_type = str(body.get("drillType") or "").upper()
    status = str(body.get("status") or "").upper()
    if drill_type not in DRILL_TYPES:
        raise AppException("VALIDATION_ERROR", f"不支持的演练类型：{drill_type}")
    if status not in ("PASSED", "FAILED"):
        raise AppException("VALIDATION_ERROR", "status 必须是 PASSED 或 FAILED")
    backup_evidence_id = body.get("backupEvidenceId")
    with _session() as db:
        if backup_evidence_id:
            evidence = db.get(BackupEvidence, int(backup_evidence_id))
            if evidence is None or evidence.is_deleted:
                raise not_found("关联的备份证据不存在")
        row = RestoreDrill(
            backup_evidence_id=int(backup_evidence_id) if backup_evidence_id else None,
            drill_type=drill_type, status=status,
            target_description=body.get("targetDescription") or None,
            detail_json={"note": body.get("note") or ""},
            performed_by=_actor_id(user), performed_at=_now(),
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return _drill_dto(row)


def run_schema_integrity_check(user: dict | None = None) -> dict:
    """唯一不需要任何外部工具、随时可跑的真实自检：当前数据库实际表结构是否与
    代码里声明的模型（app.db.base.metadata）完全一致。只读，不改一行数据。"""
    from app.db.base import metadata as declared_metadata

    with _session() as db:
        bind = db.get_bind()
        insp = inspect(bind)
        actual_tables = set(insp.get_table_names())
        declared_tables = {t.name for t in declared_metadata.sorted_tables}
        missing = sorted(declared_tables - actual_tables)
        extra = sorted(actual_tables - declared_tables)

        column_mismatches: list[dict] = []
        for table in declared_metadata.sorted_tables:
            if table.name not in actual_tables:
                continue
            actual_cols = {c["name"] for c in insp.get_columns(table.name)}
            declared_cols = {c.name for c in table.columns}
            col_missing = sorted(declared_cols - actual_cols)
            if col_missing:
                column_mismatches.append({"table": table.name, "missingColumns": col_missing})

        fingerprint_src = "|".join(sorted(
            f"{t.name}:{','.join(sorted(c.name for c in t.columns))}" for t in declared_metadata.sorted_tables
        ))
        fingerprint = hashlib.sha256(fingerprint_src.encode()).hexdigest()

        ok = not missing and not column_mismatches
        status = "SUCCEEDED" if ok else "FAILED"
        detail = {
            "declaredTableCount": len(declared_tables), "actualTableCount": len(actual_tables),
            "missingTables": missing[:50], "extraTables": extra[:50],
            "columnMismatches": column_mismatches[:50],
        }
        row = BackupEvidence(
            backup_type="SCHEMA_INTEGRITY", method="SCHEMA_INSPECT", status=status,
            table_count=len(actual_tables), checksum_sha256=fingerprint, detail_json=detail,
            error_message=None if ok else f"{len(missing)} 张表缺失，{len(column_mismatches)} 张表列不全",
            captured_by=_actor_id(user), started_at=_now(), finished_at=_now(),
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return _evidence_dto(row)


def list_backup_evidence(*, backup_type: str | None = None, limit: int = 50) -> list[dict]:
    with _session() as db:
        q = select(BackupEvidence).where(BackupEvidence.is_deleted.is_(False))
        if backup_type:
            q = q.where(BackupEvidence.backup_type == backup_type.upper())
        rows = db.scalars(q.order_by(BackupEvidence.id.desc()).limit(max(1, min(limit, 500)))).all()
        return [_evidence_dto(r) for r in rows]


def list_restore_drills(*, limit: int = 50) -> list[dict]:
    with _session() as db:
        rows = db.scalars(select(RestoreDrill).where(RestoreDrill.is_deleted.is_(False))
                          .order_by(RestoreDrill.id.desc()).limit(max(1, min(limit, 500)))).all()
        return [_drill_dto(r) for r in rows]


def governance_overview() -> dict:
    """按备份类型分别看"最近一次成功是什么时候"，过期就是真实风险，不是摆设。"""
    now = _now()
    with _session() as db:
        by_type: dict[str, dict] = {}
        for backup_type in BACKUP_TYPES:
            latest_success = db.scalars(select(BackupEvidence).where(
                BackupEvidence.backup_type == backup_type, BackupEvidence.status == "SUCCEEDED",
                BackupEvidence.is_deleted.is_(False)
            ).order_by(BackupEvidence.finished_at.desc())).first()
            threshold = STALENESS_DAYS.get(backup_type, 7)
            stale = True
            days_since = None
            if latest_success and latest_success.finished_at:
                days_since = (now - latest_success.finished_at).days
                stale = days_since > threshold
            by_type[backup_type] = {
                "hasEvidence": latest_success is not None,
                "lastSuccessAt": latest_success.finished_at.isoformat() if latest_success and latest_success.finished_at else None,
                "daysSinceLastSuccess": days_since, "stale": stale, "thresholdDays": threshold,
            }

        latest_drill = db.scalars(select(RestoreDrill).where(
            RestoreDrill.status == "PASSED", RestoreDrill.is_deleted.is_(False)
        ).order_by(RestoreDrill.performed_at.desc())).first()
        drill_days_since = (now - latest_drill.performed_at).days if latest_drill else None
        drill_stale = drill_days_since is None or drill_days_since > DRILL_STALENESS_DAYS

        recent_failures = db.scalars(select(BackupEvidence).where(
            BackupEvidence.status == "FAILED", BackupEvidence.is_deleted.is_(False),
            BackupEvidence.started_at >= now - timedelta(days=7),
        ).order_by(BackupEvidence.id.desc())).all()

    return {
        "byType": by_type,
        "restoreDrill": {
            "hasPassedDrill": latest_drill is not None,
            "lastPassedAt": latest_drill.performed_at.isoformat() if latest_drill else None,
            "daysSinceLastPassed": drill_days_since, "stale": drill_stale,
            "thresholdDays": DRILL_STALENESS_DAYS,
        },
        "recentFailuresLast7Days": [_evidence_dto(r) for r in recent_failures[:20]],
    }
