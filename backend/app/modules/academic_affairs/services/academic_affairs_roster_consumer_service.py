"""R9 选课、考勤、考务、成绩统一名单版本消费服务。"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime

from app.core.context import get_current_user_ctx
from app.core.exceptions import AppException, not_found
from app.services.db_service import _tid

from . import academic_affairs_teaching_class_service as teaching_class_service

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
            details=roster, http_status=409,
        )
    teaching_class_id = roster.get("teachingClassId")
    roster_version_id = roster.get("rosterVersionId")
    if not teaching_class_id or not roster_version_id:
        raise AppException(
            "DATA_CONFLICT",
            "教学任务尚未形成独立教学班和正式名单版本，请先执行名单投影",
            details=roster, http_status=409,
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
        "teachingClassId": resolved["teachingClassId"],
        "rosterVersionId": resolved["rosterVersionId"],
        "rosterVersionNo": resolved["rosterVersionNo"],
        "rosterHash": resolved["rosterHash"],
        "memberCount": resolved["memberCount"],
        "source": resolved.get("source"),
    }
    if existing:
        if (
            int(existing.teaching_task_id) != int(teaching_task_id)
            or int(existing.teaching_class_id) != int(resolved["teachingClassId"])
            or int(existing.roster_version_id) != int(resolved["rosterVersionId"])
            or existing.roster_hash != resolved["rosterHash"]
        ):
            raise AppException(
                "APPROVAL_VERSION_CONFLICT",
                "该业务已冻结其它教学班名单版本，禁止静默切换",
                details={
                    "existing": {
                        "teachingTaskId": str(existing.teaching_task_id),
                        "teachingClassId": str(existing.teaching_class_id),
                        "rosterVersionId": str(existing.roster_version_id),
                        "rosterHash": existing.roster_hash,
                    },
                    "requested": payload,
                },
                http_status=409,
            )
        return {**payload, "snapshotId": str(existing.id), "created": False}

    snapshot = AaRosterConsumerSnapshot(
        tenant_id=_tid(), consumer_type=kind, consumer_id=int(consumer_id),
        teaching_task_id=int(teaching_task_id),
        teaching_class_id=int(resolved["teachingClassId"]),
        roster_version_id=int(resolved["rosterVersionId"]),
        roster_version_no=int(resolved["rosterVersionNo"]),
        roster_hash=resolved["rosterHash"], member_count=int(resolved["memberCount"]),
        source_type=resolved.get("source") or "UNKNOWN",
        snapshot_json=json.dumps(payload, ensure_ascii=False, sort_keys=True),
        frozen_at=datetime.utcnow(), frozen_by=_operator(), status="FROZEN",
    )
    db.add(snapshot)
    db.flush()
    return {**payload, "snapshotId": str(snapshot.id), "created": True}


def get_consumer_snapshot(db, consumer_type: str, consumer_id: int) -> dict | None:
    from app.models.academic_affairs_roster_consumer import AaRosterConsumerSnapshot

    row = db.query(AaRosterConsumerSnapshot).filter(
        AaRosterConsumerSnapshot.tenant_id == _tid(),
        AaRosterConsumerSnapshot.consumer_type == str(consumer_type or "").strip().upper(),
        AaRosterConsumerSnapshot.consumer_id == int(consumer_id),
        AaRosterConsumerSnapshot.is_deleted.is_(False),
    ).first()
    if not row:
        return None
    return {
        "snapshotId": str(row.id), "consumerType": row.consumer_type,
        "consumerId": str(row.consumer_id), "teachingTaskId": str(row.teaching_task_id),
        "teachingClassId": str(row.teaching_class_id),
        "rosterVersionId": str(row.roster_version_id),
        "rosterVersionNo": int(row.roster_version_no),
        "rosterHash": row.roster_hash, "memberCount": int(row.member_count),
        "sourceType": row.source_type, "status": row.status,
    }
