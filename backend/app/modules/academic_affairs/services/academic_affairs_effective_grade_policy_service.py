"""P0-11 有效成绩统一策略与不可变快照。"""
from __future__ import annotations

import hashlib
import json
import logging
import unicodedata
from decimal import Decimal, InvalidOperation

from sqlalchemy import select

from app.core.context import get_current_user_ctx
from app.core.exceptions import AppException
from app.services.db_service import _tid

_LOG = logging.getLogger(__name__)

POLICY_CODE = "LEGACY_LATEST_ATTEMPT_V1"
POLICY_VERSION = 1
VALID_ATTEMPT_STRATEGIES = {
    "LATEST_ATTEMPT", "HIGHEST_SCORE", "HIGHEST_PASSED", "LATEST_PASSED",
    "MAKEUP_CAP_AND_OVERRIDE", "RETAKE_OVERRIDE_ONLY_IF_PASSED",
}
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


def resolve_active_policy(db, term_id=None, *, required=True):
    """按租户和生效学期读取唯一当前策略；无策略时正式成绩写入必须阻断。"""
    from app.models.academic_affairs_effective_grade import AaEffectiveGradePolicy

    query = db.query(AaEffectiveGradePolicy).filter(
        AaEffectiveGradePolicy.tenant_id == _tid(),
        AaEffectiveGradePolicy.status == "ACTIVE",
        AaEffectiveGradePolicy.is_deleted.is_(False),
    )
    if term_id:
        query = query.filter(
            (AaEffectiveGradePolicy.effective_from_term_id.is_(None))
            | (AaEffectiveGradePolicy.effective_from_term_id <= int(term_id))
        )
    rows = query.order_by(
        AaEffectiveGradePolicy.effective_from_term_id.desc(),
        AaEffectiveGradePolicy.policy_version.desc(),
        AaEffectiveGradePolicy.id.desc(),
    ).limit(2).all()
    if not rows:
        if required:
            raise AppException(
                "DATA_CONFLICT",
                "当前租户未配置生效的有效成绩策略，禁止发布或更正正式成绩",
                http_status=409,
            )
        return None
    first = rows[0]
    if str(first.attempt_strategy or "").upper() not in VALID_ATTEMPT_STRATEGIES:
        raise AppException("DATA_CONFLICT", "有效成绩策略包含不支持的attemptStrategy", http_status=409)
    if len(rows) > 1 and rows[1].effective_from_term_id == first.effective_from_term_id:
        raise AppException("DATA_CONFLICT", "同一生效学期存在多条有效成绩策略", http_status=409)
    return first


def apply_policy_to_grade(grade, policy, *, pass_line=None):
    grade.effective_policy_code = str(policy.policy_code)
    grade.effective_policy_version = int(policy.policy_version or 1)
    grade.effective_attempt_strategy = str(policy.attempt_strategy or "").upper()
    if pass_line is not None:
        grade.pass_line_snapshot = int(pass_line)
    return grade


def _base_rank(row):
    source = str(getattr(row, "source", None) or "LEGACY").upper()
    exam_type = str(getattr(row, "exam_type", None) or "NORMAL").upper()
    try:
        attempt_no = int(getattr(row, "attempt_no", None) or 0)
    except (TypeError, ValueError):
        attempt_no = 0
    row_id = int(getattr(row, "id", None) or 0)
    score = getattr(row, "score", None)
    score = float(score) if score is not None else -1.0
    passed = 1 if str(getattr(row, "pass_status", None) or "").upper() == "PASSED" else 0
    return attempt_no, SOURCE_PRIORITY.get(source, 20), EXAM_PRIORITY.get(exam_type, 15), passed, score, row_id


def _rank(row, strategy):
    attempt, source, exam, passed, score, row_id = _base_rank(row)
    strategy = str(strategy or "").upper()
    if strategy == "HIGHEST_SCORE":
        return score, passed, attempt, source, exam, row_id
    if strategy == "HIGHEST_PASSED":
        return passed, score, attempt, source, exam, row_id
    if strategy == "LATEST_PASSED":
        return passed, attempt, source, exam, score, row_id
    if strategy == "RETAKE_OVERRIDE_ONLY_IF_PASSED":
        return passed, attempt if passed else -attempt, source, exam, score, row_id
    # LATEST_ATTEMPT / MAKEUP_CAP_AND_OVERRIDE
    return attempt, source, exam, passed, row_id


def _group_strategy(rows, explicit=None):
    if explicit:
        strategy = str(explicit).upper()
    else:
        frozen = [row for row in rows if getattr(row, "effective_attempt_strategy", None)]
        if frozen:
            latest = max(frozen, key=lambda row: (_base_rank(row)[0], _base_rank(row)[5]))
            strategy = str(latest.effective_attempt_strategy).upper()
        elif len(rows) == 1:
            return "SINGLE_RECORD"
        else:
            raise AppException(
                "DATA_CONFLICT",
                "历史成绩存在多次修读但缺少冻结的有效成绩策略，必须先治理后再判定",
                details={"gradeIds": [str(getattr(row, "id", "")) for row in rows[:20]]},
                http_status=409,
            )
    if strategy not in VALID_ATTEMPT_STRATEGIES:
        raise AppException("DATA_CONFLICT", f"不支持的有效成绩策略：{strategy}", http_status=409)
    return strategy


def resolve_effective_grade(rows, strategy=None):
    """按课程身份和每条正式成绩冻结的租户策略解析唯一有效成绩。"""
    grouped = {}
    legacy = []
    for row in rows or []:
        key = grade_identity_key(row)
        if len(key) > 1 and key[1] == "LEGACY_NAME_KEY":
            legacy.append(row)
            continue
        grouped.setdefault(key, []).append(row)
    selected = list(legacy)
    if legacy:
        _LOG.warning("effective grade kept %s LEGACY_NAME_KEY rows separate", len(legacy))
    for group in grouped.values():
        active = [row for row in group if str(getattr(row, "record_status", None) or "ACTIVE").upper() == "ACTIVE"]
        candidates = active or group
        group_strategy = _group_strategy(candidates, strategy)
        if group_strategy == "SINGLE_RECORD":
            selected.append(candidates[0])
        else:
            selected.append(max(candidates, key=lambda row: _rank(row, group_strategy)))
    return selected


def policy_payload(source=None) -> dict:
    strategy = str(
        getattr(source, "attempt_strategy", None)
        or getattr(source, "effective_attempt_strategy", None)
        or "UNRESOLVED"
    ).upper()
    return {
        "policyCode": str(getattr(source, "policy_code", None) or getattr(source, "effective_policy_code", None) or POLICY_CODE),
        "policyVersion": int(getattr(source, "policy_version", None) or getattr(source, "effective_policy_version", None) or POLICY_VERSION),
        "attemptStrategy": strategy,
        "makeupStrategy": str(getattr(source, "makeup_strategy", None) or "CAP_AND_OVERRIDE"),
        "makeupCap": getattr(source, "makeup_cap", None),
        "retakeStrategy": str(getattr(source, "retake_strategy", None) or "REPLACE_IF_PASSED"),
        "recognitionPriority": int(getattr(source, "recognition_priority", None) or 75),
        "identityOrder": ["COURSE_ID", "COURSE_CODE", "LEGACY_NAME_KEY"],
        "legacyMerge": "NEVER",
        "sourcePriority": SOURCE_PRIORITY,
        "examPriority": EXAM_PRIORITY,
        "scoreComparison": (
            "ENABLED_BY_POLICY" if strategy in {"HIGHEST_SCORE", "HIGHEST_PASSED"} else "DISABLED"
        ),
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
    policy = policy_payload(grade)
    decision = {
        "academicGradeId": str(grade.id),
        "studentId": str(getattr(grade, "acad_student_id", None) or ""),
        "score": getattr(grade, "score", None),
        "passStatus": getattr(grade, "pass_status", None),
        "recordStatus": getattr(grade, "record_status", None),
        "gradeSource": getattr(grade, "source", None),
        "examType": getattr(grade, "exam_type", None),
        "effectivePolicyCode": getattr(grade, "effective_policy_code", None),
        "effectivePolicyVersion": getattr(grade, "effective_policy_version", None),
        "attemptStrategy": getattr(grade, "effective_attempt_strategy", None),
        "passLineSnapshot": getattr(grade, "pass_line_snapshot", None),
        **identity,
    }
    payload_hash = _hash({"policy": policy, "decision": decision})

    existing = db.scalars(select(AaEffectiveGradePolicySnapshot).where(
        AaEffectiveGradePolicySnapshot.tenant_id == _tid(),
        AaEffectiveGradePolicySnapshot.event_key == event_key,
    ).with_for_update()).first()
    if existing:
        if existing.is_deleted:
            raise AppException(
                "DATA_CONFLICT",
                "有效成绩策略快照曾被软删除，禁止静默重建同一事件",
                details={"eventKey": event_key, "snapshotId": str(existing.id)},
                http_status=409,
            )
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
        policy_code=policy["policyCode"],
        policy_version=policy["policyVersion"],
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


def _policy_dto(row) -> dict:
    return {
        "policyId": str(row.id),
        "policyCode": row.policy_code,
        "policyVersion": int(row.policy_version or 1),
        "attemptStrategy": row.attempt_strategy,
        "makeupStrategy": row.makeup_strategy,
        "makeupCap": row.makeup_cap,
        "retakeStrategy": row.retake_strategy,
        "recognitionPriority": int(row.recognition_priority or 75),
        "effectiveFromTermId": str(row.effective_from_term_id) if row.effective_from_term_id else None,
        "status": row.status,
        "activatedAt": row.activated_at.isoformat() if row.activated_at else None,
    }


def list_grade_policies(user) -> list[dict]:
    """学校教务查看租户策略版本链。"""
    from app.models.academic_affairs_effective_grade import AaEffectiveGradePolicy
    from app.services.db_service import session

    with session() as db:
        rows = db.query(AaEffectiveGradePolicy).filter(
            AaEffectiveGradePolicy.tenant_id == _tid(),
            AaEffectiveGradePolicy.is_deleted.is_(False),
        ).order_by(
            AaEffectiveGradePolicy.effective_from_term_id.desc(),
            AaEffectiveGradePolicy.policy_version.desc(),
            AaEffectiveGradePolicy.id.desc(),
        ).all()
        return [_policy_dto(row) for row in rows]


def activate_grade_policy(user, payload) -> dict:
    """新增一个按学期生效的策略版本；历史成绩继续使用发布时快照。"""
    from datetime import datetime

    from app.models import AaTerm, AffairsAuditTrail
    from app.models.academic_affairs_effective_grade import AaEffectiveGradePolicy
    from app.services.db_service import session

    strategy = str(payload.get("attemptStrategy") or "").strip().upper()
    if strategy not in VALID_ATTEMPT_STRATEGIES:
        raise AppException("VALIDATION_ERROR", "不支持的attemptStrategy")
    term_id = payload.get("effectiveFromTermId")
    term_id = int(term_id) if term_id not in (None, "") else None
    with session() as db:
        if term_id:
            term = db.query(AaTerm).filter(
                AaTerm.id == term_id,
                AaTerm.tenant_id == _tid(),
                AaTerm.is_deleted.is_(False),
            ).first()
            if not term:
                raise AppException("VALIDATION_ERROR", "生效学期不存在")
        same = db.query(AaEffectiveGradePolicy).filter(
            AaEffectiveGradePolicy.tenant_id == _tid(),
            AaEffectiveGradePolicy.effective_from_term_id == term_id,
            AaEffectiveGradePolicy.status == "ACTIVE",
            AaEffectiveGradePolicy.is_deleted.is_(False),
        ).with_for_update().all()
        next_version = max([int(row.policy_version or 1) for row in same] + [0]) + 1
        for row in same:
            row.status = "SUPERSEDED"
        code = str(payload.get("policyCode") or f"{strategy}_T{term_id or 'BASE'}_V{next_version}").strip().upper()
        exists = db.query(AaEffectiveGradePolicy.id).filter(
            AaEffectiveGradePolicy.tenant_id == _tid(),
            AaEffectiveGradePolicy.policy_code == code,
        ).first()
        if exists:
            raise AppException("APPROVAL_VERSION_CONFLICT", "策略编码已存在", http_status=409)
        row = AaEffectiveGradePolicy(
            tenant_id=_tid(),
            policy_code=code,
            policy_version=next_version,
            attempt_strategy=strategy,
            makeup_strategy=str(payload.get("makeupStrategy") or "CAP_AND_OVERRIDE").upper(),
            makeup_cap=(int(payload["makeupCap"]) if payload.get("makeupCap") is not None else None),
            retake_strategy=str(payload.get("retakeStrategy") or "REPLACE_IF_PASSED").upper(),
            recognition_priority=int(payload.get("recognitionPriority") or 75),
            effective_from_term_id=term_id,
            status="ACTIVE",
            activated_at=datetime.utcnow(),
        )
        db.add(row)
        db.flush()
        ctx = get_current_user_ctx() or user or {}
        db.add(AffairsAuditTrail(
            tenant_id=_tid(),
            biz_type="AA_EFFECTIVE_GRADE_POLICY",
            biz_id=row.id,
            action="POLICY_ACTIVATE",
            operator=str(ctx.get("userId") or ctx.get("loginName") or ""),
            role_name=str(ctx.get("currentRoleCode") or ""),
            detail=_canonical(_policy_dto(row))[:990],
            occurred_at=datetime.utcnow(),
        ))
        db.commit()
        return _policy_dto(row)
