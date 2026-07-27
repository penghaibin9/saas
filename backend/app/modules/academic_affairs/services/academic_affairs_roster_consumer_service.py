"""R9 选课、考勤、考务、成绩统一名单版本消费服务。"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime

from app.core.context import get_current_user_ctx
from app.core.exceptions import AppException, not_found
from app.services.db_service import _tid

from . import academic_affairs_teaching_class_compat_migration_service as teaching_class_service

_ALLOWED_CONSUMERS = {"ATTENDANCE_SESSION", "EXAM_COURSE", "GRADE_TASK"}


def _operator() -> str:
    ctx = get_current_user_ctx() or {}
    return str(ctx.get("userId") or ctx.get("loginName") or ctx.get("realName") or "")


def _ids(values) -> list[int]:
    return sorted({int(value) for value in (values or []) if str(value).isdigit()})


def roster_hash(student_ids) -> str:
    return hashlib.sha256(",".join(str(value) for value in _ids(student_ids)).encode("utf-8")).hexdigest()


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
            "教学任务尚未形成独立教学班和正式名单版本，请先执行R8名单投影",
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


def freeze_consumer_snapshot(db, consumer_type: str, consumer_id: int, teaching_task_id: int,
                             *, roster: dict | None = None) -> dict:
    """在调用方事务内冻结名单版本；已冻结消费者只能重复命中同一版本。"""
    from app.models.academic_affairs_roster_consumer import AaRosterConsumerSnapshot

    kind = str(consumer_type or "").strip().upper()
    if kind not in _ALLOWED_CONSUMERS:
        raise AppException("VALIDATION_ERROR", "名单消费者类型非法")
    resolved = roster or resolve_versioned_roster(db, int(teaching_task_id))
    existing = db.query(AaRosterConsumerSnapshot).filter(
        AaRosterConsumerSnapshot.tenant_id == _tid(),
        AaRosterConsumerSnapshot.consumer_type == kind,
        AaRosterConsumerSnapshot.consumer_id == int(consumer_id),
        AaRosterConsumerSnapshot.is_deleted.is_(False),
    ).with_for_update().first()
    payload = {
        "teachingTaskId": str(teaching_task_id),
        "teachingClassId": str(resolved["teachingClassId"]),
        "rosterVersionId": str(resolved["rosterVersionId"]),
        "rosterVersionNo": int(resolved["rosterVersionNo"]),
        "rosterSource": str(resolved.get("source") or ""),
        "rosterHash": resolved["rosterHash"],
        "memberCount": int(resolved["memberCount"]),
        "studentIds": _ids(resolved["studentIds"]),
    }
    if existing:
        same = (
            int(existing.teaching_task_id) == int(teaching_task_id)
            and int(existing.teaching_class_id or 0) == int(payload["teachingClassId"])
            and int(existing.roster_version_id or 0) == int(payload["rosterVersionId"])
            and existing.roster_hash == payload["rosterHash"]
        )
        if not same:
            raise AppException(
                "APPROVAL_VERSION_CONFLICT",
                "该业务已冻结另一版正式名单，禁止静默换版；请撤销或退回后重建",
                details={
                    "consumerType": kind,
                    "consumerId": str(consumer_id),
                    "frozenRosterVersionId": str(existing.roster_version_id or ""),
                    "currentRosterVersionId": payload["rosterVersionId"],
                },
                http_status=409,
            )
        return {"snapshotId": str(existing.id), **payload, "created": False}

    row = AaRosterConsumerSnapshot(
        tenant_id=_tid(), consumer_type=kind, consumer_id=int(consumer_id),
        teaching_task_id=int(teaching_task_id),
        teaching_class_id=int(payload["teachingClassId"]),
        roster_version_id=int(payload["rosterVersionId"]),
        roster_version_no=payload["rosterVersionNo"],
        roster_source=payload["rosterSource"], roster_hash=payload["rosterHash"],
        member_count=payload["memberCount"],
        student_ids_json=json.dumps(payload["studentIds"], ensure_ascii=False, separators=(",", ":")),
        captured_at=datetime.utcnow(), captured_by=_operator(), status="ACTIVE",
    )
    db.add(row)
    db.flush()
    return {"snapshotId": str(row.id), **payload, "created": True}


def get_consumer_snapshot(db, consumer_type: str, consumer_id: int) -> dict | None:
    from app.models.academic_affairs_roster_consumer import AaRosterConsumerSnapshot

    row = db.query(AaRosterConsumerSnapshot).filter(
        AaRosterConsumerSnapshot.tenant_id == _tid(),
        AaRosterConsumerSnapshot.consumer_type == str(consumer_type or "").upper(),
        AaRosterConsumerSnapshot.consumer_id == int(consumer_id),
        AaRosterConsumerSnapshot.status == "ACTIVE",
        AaRosterConsumerSnapshot.is_deleted.is_(False),
    ).first()
    if not row:
        return None
    try:
        student_ids = _ids(json.loads(row.student_ids_json or "[]"))
    except (TypeError, ValueError, json.JSONDecodeError):
        student_ids = []
    return {
        "snapshotId": str(row.id),
        "consumerType": row.consumer_type,
        "consumerId": str(row.consumer_id),
        "teachingTaskId": str(row.teaching_task_id),
        "teachingClassId": str(row.teaching_class_id or ""),
        "rosterVersionId": str(row.roster_version_id or ""),
        "rosterVersionNo": int(row.roster_version_no or 0),
        "rosterSource": row.roster_source,
        "rosterHash": row.roster_hash,
        "memberCount": int(row.member_count or 0),
        "studentIds": student_ids,
        "capturedAt": row.captured_at.isoformat() if row.captured_at else None,
    }


def require_consumer_snapshot_current(db, consumer_type: str, consumer_id: int,
                                      teaching_task_id: int) -> tuple[dict, dict]:
    """业务继续写入前，确认冻结版本仍是教学班当前版本。"""
    snapshot = get_consumer_snapshot(db, consumer_type, consumer_id)
    if not snapshot:
        raise AppException(
            "DATA_CONFLICT",
            "该业务尚未冻结正式名单版本，请退回上一节点重新确认",
            details={"consumerType": consumer_type, "consumerId": str(consumer_id)},
            http_status=409,
        )
    current = resolve_versioned_roster(db, int(teaching_task_id))
    if (
        str(snapshot["rosterVersionId"]) != str(current["rosterVersionId"])
        or snapshot["rosterHash"] != current["rosterHash"]
    ):
        raise AppException(
            "APPROVAL_VERSION_CONFLICT",
            "正式名单已换版，当前业务仍引用旧版本；请退回重建名单相关数据",
            details={
                "consumerType": consumer_type,
                "consumerId": str(consumer_id),
                "frozenRosterVersionId": snapshot["rosterVersionId"],
                "currentRosterVersionId": str(current["rosterVersionId"]),
                "frozenMemberCount": snapshot["memberCount"],
                "currentMemberCount": current["memberCount"],
            },
            http_status=409,
        )
    return snapshot, current


def consumer_counts(db, teaching_class_id: int, roster_version_id: int | None = None) -> dict:
    from app.models.academic_affairs_roster_consumer import AaRosterConsumerSnapshot

    query = db.query(AaRosterConsumerSnapshot).filter(
        AaRosterConsumerSnapshot.tenant_id == _tid(),
        AaRosterConsumerSnapshot.teaching_class_id == int(teaching_class_id),
        AaRosterConsumerSnapshot.status == "ACTIVE",
        AaRosterConsumerSnapshot.is_deleted.is_(False),
    )
    if roster_version_id:
        query = query.filter(AaRosterConsumerSnapshot.roster_version_id == int(roster_version_id))
    rows = query.all()
    counts = {kind: 0 for kind in _ALLOWED_CONSUMERS}
    for row in rows:
        counts[row.consumer_type] = counts.get(row.consumer_type, 0) + 1
    return counts
