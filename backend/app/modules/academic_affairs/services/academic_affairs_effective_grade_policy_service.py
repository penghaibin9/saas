"""P0-11 有效成绩统一策略与不可变快照。"""
from __future__ import annotations

import hashlib
import json
import logging
import unicodedata
from decimal import Decimal, InvalidOperation

from sqlalchemy import select

from app.core.exceptions import AppException
from app.services.db_service import _tid

_LOG = logging.getLogger(__name__)

POLICY_CODE = "LATEST_FORMAL_SOURCE_V1"
POLICY_VERSION = 1
SOURCE_PRIORITY = {
    "CHANGE": 100,
    "RECHECK": 95,
    "CLEARANCE": 90,
    "MAKEUP": 85,
    "DEFERRED": 85,
    "RETAKE": 80,
    "RECOGNIZED": 75,
    "RECOGNITION": 75,
    "EXEMPTION": 75,
    "PUBLISH": 50,
    "MANUAL": 40,
    "LEGACY": 10,
}
EXAM_PRIORITY = {
    "CLEARANCE": 50,
    "DEFERRED": 45,
    "MAKEUP": 40,
    "RETAKE": 30,
    "FINAL": 20,
    "NORMAL": 10,
}


def _canonical(payload) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _hash(payload) -> str:
    return hashlib.sha256(_canonical(payload).encode("utf-8")).hexdigest()


def _normalize_name(value) -> str:
    text = unicodedata.normalize("NFKC", str(value or "")).strip().casefold()
    return "".join(text.split())


def _credit_key(value) -> str:
    try:
        return str(Decimal(str(value or 0)).quantize(Decimal("0.1")))
    except (InvalidOperation, ValueError):
        return str(value or "")


def grade_identity_key(row):
    """稳定课程身份；历史无ID行每行独立，禁止按同名课程静默合并。"""
    student_id = getattr(row, "acad_student_id", None)
    course_id = getattr(row, "course_id", None)
    if course_id not in (None, ""):
        return (student_id, "COURSE_ID", str(course_id))
    course_code = str(getattr(row, "course_code", None) or "").strip().upper()
    if course_code:
        return (
            student_id,
            "COURSE_CODE",
            course_code,
            str(getattr(row, "course_version", None) or ""),
        )
    return (
        student_id,
        "LEGACY_NAME_KEY",
        str(getattr(row, "id", None) or "UNPERSISTED"),
        _normalize_name(getattr(row, "course_name", None)),
        str(getattr(row, "nature", None) or "").upper(),
        _credit_key(getattr(row, "credit_value", None)),
    )


def _attempt_rank(row):
    """同一课程身份：先选最新修读次数，再选该次修读中优先级最高的正式来源。

    分数完全不参与选择；记录ID只作为同口径重复脏数据的最后确定性兜底。
    """
    source = str(getattr(row, "source", None) or "LEGACY").upper()
    exam_type = str(getattr(row, "exam_type", None) or "NORMAL").upper()
    record_status = str(getattr(row, "record_status", None) or "ACTIVE").upper()
    pass_status = str(getattr(row, "pass_status", None) or "PENDING").upper()
    try:
        attempt_no = int(getattr(row, "attempt_no", None) or 0)
    except (TypeError, ValueError):
        attempt_no = 0
    row_id = int(getattr(row, "id", None) or 0)
    return (
        1 if record_status == "ACTIVE" else 0,
        attempt_no,
        SOURCE_PRIORITY.get(source, 20),
        EXAM_PRIORITY.get(exam_type, 15),
        1 if pass_status in {"PASSED", "FAILED", "FAIL"} else 0,
        row_id,
    )


def resolve_effective_grade(rows):
    """返回按稳定课程身份、修读次数与正式来源排序后的有效成绩行。"""
    selected = {}
    legacy_ids = []
    for row in rows or []:
        key = grade_identity_key(row)
        if len(key) > 1 and key[1] == "LEGACY_NAME_KEY":
            legacy_ids.append(str(getattr(row, "id", None) or ""))
        current = selected.get(key)
        if current is None or _attempt_rank(row) > _attempt_rank(current):
            selected[key] = row
    if legacy_ids:
        _LOG.warning(
            "effective grade kept %s LEGACY_NAME_KEY rows separate; migrate course identity; sample=%s",
            len(legacy_ids), legacy_ids[:20],
        )
    return list(selected.values())


def policy_payload() -> dict:
    return {
        "policyCode": POLICY_CODE,
        "policyVersion": POLICY_VERSION,
        "identityOrder": ["COURSE_ID", "COURSE_CODE", "LEGACY_NAME_KEY"],
        "legacyMerge": "NEVER",
        "selectionOrder": ["RECORD_STATUS", "ATTEMPT_NO", "SOURCE_PRIORITY", "EXAM_PRIORITY"],
        "sourcePriority": SOURCE_PRIORITY,
        "examPriority": EXAM_PRIORITY,
        "scoreComparison": "DISABLED",
        "recordStatus": "ACTIVE_ONLY",
    }


def identity_snapshot(grade) -> dict:
    key = grade_identity_key(grade)
    return {
        "identityType": key[1],
        "identityKey": "|".join(str(value) for value in key[1:]),
        "courseId": int(grade.course_id) if getattr(grade, "course_id", None) else None,
        "courseCode": str(getattr(grade, "course_code", None) or "").strip() or None,
        "courseVersion": int(grade.course_version) if getattr(grade, "course_version", None) else None,
        "attemptNo": int(grade.attempt_no) if getattr(grade, "attempt_no", None) else None,
    }


def freeze_effective_grade_policy(
    db,
    grade,
    *,
    event_type: str,
    source_biz_type: str,
    source_biz_id: int | None,
):
    """在成绩写事务内保存策略快照；相同event_key重试幂等，不允许内容漂移。"""
    from app.models.academic_affairs_effective_grade import AaEffectiveGradePolicySnapshot

    if not getattr(grade, "id", None):
        db.flush()
    event = str(event_type or "").strip().upper()
    biz_type = str(source_biz_type or "").strip().upper()
    biz_id = int(source_biz_id) if source_biz_id not in (None, "") else None
    if not event or not biz_type:
        raise AppException("VALIDATION_ERROR", "有效成绩策略快照缺少事件类型或来源业务")

    event_key = f"{event}:{biz_type}:{biz_id if biz_id is not None else int(grade.id)}"
    identity = identity_snapshot(grade)
    policy = policy_payload()
    decision = {
        "academicGradeId": str(grade.id),
        "studentId": str(getattr(grade, "acad_student_id", None) or ""),
        "score": getattr(grade, "score", None),
        "passStatus": getattr(grade, "pass_status", None),
        "recordStatus": getattr(grade, "record_status", None),
        "gradeSource": getattr(grade, "source", None),
        "examType": getattr(grade, "exam_type", None),
        **identity,
    }
    payload_hash = _hash({"policy": policy, "decision": decision})

    existing = db.scalars(select(AaEffectiveGradePolicySnapshot).where(
        AaEffectiveGradePolicySnapshot.tenant_id == _tid(),
        AaEffectiveGradePolicySnapshot.event_key == event_key,
        AaEffectiveGradePolicySnapshot.is_deleted.is_(False),
    ).with_for_update()).first()
    if existing:
        if existing.policy_hash != payload_hash or int(existing.academic_grade_id) != int(grade.id):
            raise AppException(
                "APPROVAL_VERSION_CONFLICT",
                "同一成绩策略事件已存在但内容发生变化，禁止覆盖历史快照",
                details={"eventKey": event_key, "snapshotId": str(existing.id)},
                http_status=409,
            )
        return existing

    row = AaEffectiveGradePolicySnapshot(
        tenant_id=_tid(),
        academic_grade_id=int(grade.id),
        event_key=event_key[:160],
        event_type=event,
        source_biz_type=biz_type,
        source_biz_id=biz_id,
        policy_code=POLICY_CODE,
        policy_version=POLICY_VERSION,
        policy_json=_canonical(policy),
        policy_hash=payload_hash,
        identity_type=identity["identityType"],
        identity_key=identity["identityKey"][:300],
        course_id=identity["courseId"],
        course_code=identity["courseCode"],
        course_version=identity["courseVersion"],
        attempt_no=identity["attemptNo"],
        grade_source=str(getattr(grade, "source", None) or "") or None,
        decision_json=_canonical(decision),
    )
    db.add(row)
    db.flush()
    return row


def policy_snapshot_debt(db, *, term=None) -> dict:
    """只读欠账：历史成绩不自动补快照。"""
    from app.models import AcademicGrade
    from app.models.academic_affairs_effective_grade import AaEffectiveGradePolicySnapshot

    query = db.query(AcademicGrade).filter(
        AcademicGrade.tenant_id == _tid(),
        AcademicGrade.record_status == "ACTIVE",
        AcademicGrade.is_deleted.is_(False),
    )
    if term:
        query = query.filter(AcademicGrade.term == term)
    grades = query.all()
    grade_ids = [int(row.id) for row in grades]
    snap_ids = {
        int(value) for (value,) in db.query(AaEffectiveGradePolicySnapshot.academic_grade_id).filter(
            AaEffectiveGradePolicySnapshot.tenant_id == _tid(),
            AaEffectiveGradePolicySnapshot.academic_grade_id.in_(grade_ids or [0]),
            AaEffectiveGradePolicySnapshot.is_deleted.is_(False),
        ).all()
    }
    missing = [row for row in grades if int(row.id) not in snap_ids]
    legacy = [row for row in grades if grade_identity_key(row)[1] == "LEGACY_NAME_KEY"]
    return {
        "total": len(grades),
        "missingPolicySnapshot": len(missing),
        "legacyNameKey": len(legacy),
        "ready": not missing and not legacy,
        "sampleGradeIds": [str(row.id) for row in (missing + legacy)[:50]],
    }
