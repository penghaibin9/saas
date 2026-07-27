"""R9 选课、考勤、考务、成绩统一名单版本消费服务。

该服务只做三件事：
1. 解析教学任务当前独立教学班名单版本；
2. 在调用方事务内冻结消费者快照；
3. 发布或继续流转前验证冻结版本仍是当前版本。

同一消费者退回重提时必须显式允许换版，旧快照标记 SUPERSEDED 并永久保留。
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime

from sqlalchemy import func

from app.core.context import get_current_user_ctx
from app.core.exceptions import AppException, not_found
from app.services.db_service import _tid

from . import academic_affairs_teaching_class_service as teaching_class_service

_ALLOWED_CONSUMERS = {"ATTENDANCE_SESSION", "EXAM_COURSE", "GRADE_TASK"}
_ACTIVE = "ACTIVE"
_SUPERSEDED = "SUPERSEDED"


def _operator() -> str:
    ctx = get_current_user_ctx() or {}
    return str(ctx.get("userId") or ctx.get("loginName") or ctx.get("realName") or "")


def _ids(values) -> list[int]:
    return sorted({int(value) for value in (values or []) if str(value).isdigit()})


def roster_hash(student_ids) -> str:
    return hashlib.sha256(
        ",".join(str(value) for value in _ids(student_ids)).encode("utf-8")
    ).hexdigest()


def _kind(value) -> str:
    result = str(value or "").strip().upper()
    if result not in _ALLOWED_CONSUMERS:
        raise AppException("VALIDATION_ERROR", "名单消费者类型非法")
    return result


def _row_student_ids(row) -> list[int]:
    try:
        values = json.loads(row.student_ids_json or "[]")
    except (TypeError, ValueError, json.JSONDecodeError):
        values = []
    return _ids(values)


def _snapshot_dto(row, *, created=False) -> dict:
    return {
        "snapshotId": str(row.id),
        "snapshotVersion": int(row.snapshot_version or 1),
        "consumerType": row.consumer_type,
        "consumerId": str(row.consumer_id),
        "teachingTaskId": str(row.teaching_task_id),
        "teachingClassId": str(row.teaching_class_id or ""),
        "rosterVersionId": str(row.roster_version_id or ""),
        "rosterVersionNo": int(row.roster_version_no or 0),
        "rosterHash": row.roster_hash,
        "memberCount": int(row.member_count or 0),
        "studentIds": _row_student_ids(row),
        "source": row.roster_source,
        "status": row.status,
        "capturedAt": row.captured_at.isoformat() if row.captured_at else None,
        "capturedBy": row.captured_by,
        "created": bool(created),
    }


def _consumer_rows(db, consumer_type: str, consumer_id: int, *, lock=False):
    from app.models.academic_affairs_roster_consumer import AaRosterConsumerSnapshot

    query = db.query(AaRosterConsumerSnapshot).filter(
        AaRosterConsumerSnapshot.tenant_id == _tid(),
        AaRosterConsumerSnapshot.consumer_type == consumer_type,
        AaRosterConsumerSnapshot.consumer_id == int(consumer_id),
        AaRosterConsumerSnapshot.is_deleted.is_(False),
    ).order_by(
        AaRosterConsumerSnapshot.snapshot_version.desc(),
        AaRosterConsumerSnapshot.id.desc(),
    )
    if lock:
        query = query.with_for_update()
    return query.all()


def _active_row(rows):
    active = [row for row in rows if str(row.status or "").upper() == _ACTIVE]
    if len(active) > 1:
        raise AppException(
            "DATA_CONFLICT",
            "同一业务对象存在多条ACTIVE名单快照，请先完成数据治理",
            details={"snapshotIds": [str(row.id) for row in active]},
            http_status=409,
        )
    return active[0] if active else None


def resolve_versioned_roster(db, teaching_task_id: int) -> dict:
    """确保教学任务已有独立教学班与当前LOCKED版本，再返回同一权威名单。"""
    teaching_class_service.ensure_teaching_class_for_task(db, int(teaching_task_id))
    roster = teaching_class_service.resolve_teaching_task_roster(db, int(teaching_task_id))
    if not roster.get("ready"):
        raise AppException(
            "DATA_CONFLICT",
            f"教学任务正式名单尚不可用：{roster.get('note') or '未知原因'}",
            details=roster,
            http_status=409,
        )
    teaching_class_id = roster.get("teachingClassId")
    roster_version_id = roster.get("rosterVersionId")
    if not teaching_class_id or not roster_version_id:
        raise AppException(
            "DATA_CONFLICT",
            "教学任务尚未形成独立教学班和正式名单版本，请先执行名单投影",
            details=roster,
            http_status=409,
        )

    from app.models import AaTeachingClassRosterVersion

    version = db.query(AaTeachingClassRosterVersion).filter(
        AaTeachingClassRosterVersion.id == int(roster_version_id),
        AaTeachingClassRosterVersion.tenant_id == _tid(),
        AaTeachingClassRosterVersion.is_deleted.is_(False),
    ).first()
    if not version:
        raise not_found("教学班名单版本不存在")

    student_ids = _ids(roster.get("studentIds"))
    digest = roster_hash(student_ids)
    if version.roster_hash != digest or int(version.member_count or 0) != len(student_ids):
        raise AppException(
            "APPROVAL_VERSION_CONFLICT",
            "教学班名单版本摘要与成员事实不一致，请重新投影并对账",
            details={
                "teachingClassId": str(teaching_class_id),
                "rosterVersionId": str(roster_version_id),
                "versionHash": version.roster_hash,
                "actualHash": digest,
                "versionMemberCount": int(version.member_count or 0),
                "actualMemberCount": len(student_ids),
            },
            http_status=409,
        )
    return {
        **roster,
        "teachingClassId": str(teaching_class_id),
        "rosterVersionId": str(roster_version_id),
        "rosterVersionNo": int(roster.get("rosterVersionNo") or version.version_no),
        "rosterHash": digest,
        "memberCount": len(student_ids),
        "studentIds": student_ids,
    }


def _matches(row, teaching_task_id: int, resolved: dict) -> bool:
    return (
        int(row.teaching_task_id) == int(teaching_task_id)
        and int(row.teaching_class_id or 0) == int(resolved["teachingClassId"])
        and int(row.roster_version_id or 0) == int(resolved["rosterVersionId"])
        and int(row.roster_version_no or 0) == int(resolved["rosterVersionNo"])
        and row.roster_hash == resolved["rosterHash"]
        and int(row.member_count or 0) == int(resolved["memberCount"])
        and _row_student_ids(row) == _ids(resolved.get("studentIds"))
    )


def freeze_consumer_snapshot(
    db,
    consumer_type: str,
    consumer_id: int,
    teaching_task_id: int,
    *,
    roster: dict | None = None,
    allow_replace: bool = False,
    replace_reason: str = "",
) -> dict:
    """在调用方事务内冻结名单版本。

    默认情况下，已冻结消费者只能重复命中同一版本。业务被正式退回并允许重新提交时，
    调用方须显式传 ``allow_replace=True`` 和可审计原因，旧版转为 SUPERSEDED。
    """
    from app.models.academic_affairs_roster_consumer import AaRosterConsumerSnapshot

    kind = _kind(consumer_type)
    resolved = roster or resolve_versioned_roster(db, int(teaching_task_id))
    rows = _consumer_rows(db, kind, int(consumer_id), lock=True)
    existing = _active_row(rows)

    if existing and _matches(existing, int(teaching_task_id), resolved):
        return _snapshot_dto(existing, created=False)

    if existing and not allow_replace:
        raise AppException(
            "APPROVAL_VERSION_CONFLICT",
            "该业务已冻结其它教学班名单版本，禁止静默切换",
            details={
                "existing": _snapshot_dto(existing),
                "requested": {
                    "teachingTaskId": str(teaching_task_id),
                    "teachingClassId": str(resolved["teachingClassId"]),
                    "rosterVersionId": str(resolved["rosterVersionId"]),
                    "rosterVersionNo": int(resolved["rosterVersionNo"]),
                    "rosterHash": resolved["rosterHash"],
                    "memberCount": int(resolved["memberCount"]),
                },
            },
            http_status=409,
        )

    reason = str(replace_reason or "").strip()
    if existing and allow_replace and len(reason) < 5:
        raise AppException("VALIDATION_ERROR", "名单快照换版原因必填且不少于5字")

    if existing:
        existing.status = _SUPERSEDED

    next_version = max((int(row.snapshot_version or 0) for row in rows), default=0) + 1
    student_ids = _ids(resolved.get("studentIds"))
    snapshot = AaRosterConsumerSnapshot(
        tenant_id=_tid(),
        consumer_type=kind,
        consumer_id=int(consumer_id),
        snapshot_version=next_version,
        teaching_task_id=int(teaching_task_id),
        teaching_class_id=int(resolved["teachingClassId"]),
        roster_version_id=int(resolved["rosterVersionId"]),
        roster_version_no=int(resolved["rosterVersionNo"]),
        roster_source=str(resolved.get("source") or "UNKNOWN"),
        roster_hash=resolved["rosterHash"],
        member_count=int(resolved["memberCount"]),
        student_ids_json=json.dumps(student_ids, ensure_ascii=False, separators=(",", ":")),
        captured_at=datetime.utcnow(),
        captured_by=_operator(),
        status=_ACTIVE,
    )
    db.add(snapshot)
    db.flush()
    result = _snapshot_dto(snapshot, created=True)
    if existing:
        result["supersededSnapshotId"] = str(existing.id)
        result["replaceReason"] = reason
    return result


def get_consumer_snapshot(db, consumer_type: str, consumer_id: int) -> dict | None:
    kind = _kind(consumer_type)
    row = _active_row(_consumer_rows(db, kind, int(consumer_id)))
    return _snapshot_dto(row) if row else None


def consumer_snapshot_history(db, consumer_type: str, consumer_id: int) -> list[dict]:
    kind = _kind(consumer_type)
    return [_snapshot_dto(row) for row in _consumer_rows(db, kind, int(consumer_id))]


def require_consumer_snapshot_current(
    db,
    consumer_type: str,
    consumer_id: int,
    teaching_task_id: int,
) -> tuple[dict, dict]:
    """要求消费者已有ACTIVE快照，且仍与教学班当前名单版本完全一致。"""
    kind = _kind(consumer_type)
    row = _active_row(_consumer_rows(db, kind, int(consumer_id)))
    if not row:
        raise AppException(
            "DATA_CONFLICT",
            "该业务尚未冻结正式名单版本，请退回前置节点重新生成",
            details={"consumerType": kind, "consumerId": str(consumer_id)},
            http_status=409,
        )

    current = resolve_versioned_roster(db, int(teaching_task_id))
    if not _matches(row, int(teaching_task_id), current):
        raise AppException(
            "APPROVAL_VERSION_CONFLICT",
            "正式名单已换版，当前业务仍引用旧名单；请按业务规则退回并重新生成",
            details={
                "frozen": _snapshot_dto(row),
                "current": {
                    "teachingTaskId": str(teaching_task_id),
                    "teachingClassId": str(current["teachingClassId"]),
                    "rosterVersionId": str(current["rosterVersionId"]),
                    "rosterVersionNo": int(current["rosterVersionNo"]),
                    "rosterHash": current["rosterHash"],
                    "memberCount": int(current["memberCount"]),
                    "studentIds": _ids(current.get("studentIds")),
                },
            },
            http_status=409,
        )
    return _snapshot_dto(row), current


def consumer_counts(db, *, teaching_class_id: int | None = None, teaching_task_id: int | None = None) -> dict:
    """返回当前ACTIVE快照的消费者数量，供名单变更影响预检使用。"""
    from app.models.academic_affairs_roster_consumer import AaRosterConsumerSnapshot

    query = db.query(
        AaRosterConsumerSnapshot.consumer_type,
        func.count(AaRosterConsumerSnapshot.id),
    ).filter(
        AaRosterConsumerSnapshot.tenant_id == _tid(),
        AaRosterConsumerSnapshot.status == _ACTIVE,
        AaRosterConsumerSnapshot.is_deleted.is_(False),
    )
    if teaching_class_id is not None:
        query = query.filter(AaRosterConsumerSnapshot.teaching_class_id == int(teaching_class_id))
    if teaching_task_id is not None:
        query = query.filter(AaRosterConsumerSnapshot.teaching_task_id == int(teaching_task_id))
    rows = query.group_by(AaRosterConsumerSnapshot.consumer_type).all()
    counts = {kind: 0 for kind in sorted(_ALLOWED_CONSUMERS)}
    counts.update({str(kind): int(count or 0) for kind, count in rows})
    counts["TOTAL"] = sum(counts[kind] for kind in _ALLOWED_CONSUMERS)
    return counts
