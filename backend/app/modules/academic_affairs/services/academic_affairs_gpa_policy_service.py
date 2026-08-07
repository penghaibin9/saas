"""GPA 绩点换算策略：租户配置、版本发布与历史冻结求值（P1 GPA）。

与 `academic_affairs_effective_grade_policy_service.py` 同一套版本化合同（DRAFT/ACTIVE/
SUPERSEDED + active_scope_key 唯一索引兜底并发发布），职责不同：那边管"多次修读成绩选哪
一条算数"，这里管"一条成绩的分数换算成多少绩点"。

历史冻结的核心不变量（GPA-POLICY-01）：`_course_point_frozen()` 只在成绩记录第一次真正
计入 GPA（`gpa_point IS NULL`）时才调用当前生效策略求值并写回冻结列；已冻结的记录永远直接
返回冻结值，不因租户后续发布新策略版本而改变——2028 年调整绩点口径，不会改写 2026 届学生
已经算过的历史 GPA。
"""
from __future__ import annotations

import json
from datetime import datetime

from sqlalchemy.exc import IntegrityError

from app.core.exceptions import AppException
from app.services.db_service import _tid

DEFAULT_POLICY_CODE = "DEFAULT"
_ACTIVE_SCOPE = "BASE"
VALID_SCALE_TYPES = {"LINEAR", "BANDS"}


def _policy_dto(row) -> dict:
    bands = None
    if row.bands_json:
        try:
            bands = json.loads(row.bands_json)
        except (TypeError, ValueError):
            bands = None
    return {
        "policyId": str(row.id),
        "policyCode": row.policy_code,
        "policyVersion": int(row.policy_version or 1),
        "scaleType": row.scale_type,
        "linearFailScore": row.linear_fail_score,
        "linearAnchorScore": row.linear_anchor_score,
        "linearDivisor": row.linear_divisor,
        "bands": bands,
        "status": row.status,
        "activatedAt": row.activated_at.isoformat() if row.activated_at else None,
        "remark": row.remark,
    }


def _validate_bands(bands) -> str:
    if not isinstance(bands, list) or not bands:
        raise AppException("VALIDATION_ERROR", "BANDS 策略必须提供非空的分数区间数组")
    normalized = []
    for item in bands:
        try:
            lo, hi, point = float(item["minScore"]), float(item["maxScore"]), float(item["point"])
        except (KeyError, TypeError, ValueError) as exc:
            raise AppException("VALIDATION_ERROR", "BANDS 每项须包含 minScore/maxScore/point") from exc
        if lo > hi:
            raise AppException("VALIDATION_ERROR", f"区间下限不能大于上限：{lo}-{hi}")
        normalized.append({"minScore": lo, "maxScore": hi, "point": round(point, 2)})
    normalized.sort(key=lambda b: b["minScore"])
    for prev, cur in zip(normalized, normalized[1:]):
        if cur["minScore"] <= prev["maxScore"]:
            raise AppException(
                "VALIDATION_ERROR",
                f"BANDS 区间存在重叠：{prev['minScore']}-{prev['maxScore']} 与 {cur['minScore']}-{cur['maxScore']}",
            )
    return json.dumps(normalized, ensure_ascii=False)


def resolve_active_policy(db):
    """读取租户当前 ACTIVE 绩点策略；不存在则落一条与历史硬编码公式完全等价的默认策略。

    默认策略 (score-50)/10（60→1.0，100→5.0，<60→0）与升级前 `_course_point()` 的行为
    逐分值一致，保证首次上线不改变任何学生的历史 GPA。
    """
    from app.models.academic_affairs_gpa_policy import AaGpaPointPolicy

    policy = db.query(AaGpaPointPolicy).filter(
        AaGpaPointPolicy.tenant_id == _tid(),
        AaGpaPointPolicy.status == "ACTIVE",
        AaGpaPointPolicy.is_deleted.is_(False),
    ).order_by(AaGpaPointPolicy.policy_version.desc()).first()
    if policy:
        return policy
    return _ensure_default_policy(db)


def _ensure_default_policy(db):
    """get-or-create 默认策略；并发下靠 uk_aa_gpa_policy_scope 唯一索引兜底，不靠先查后写。"""
    from app.models.academic_affairs_gpa_policy import AaGpaPointPolicy

    db.flush()
    nested = db.begin_nested()
    try:
        row = AaGpaPointPolicy(
            tenant_id=_tid(),
            policy_code=DEFAULT_POLICY_CODE,
            policy_version=1,
            active_scope_key=_ACTIVE_SCOPE,
            scale_type="LINEAR",
            linear_fail_score=60,
            linear_anchor_score=50,
            linear_divisor=10,
            status="ACTIVE",
            activated_at=datetime.utcnow(),
            remark="系统默认：与升级前硬编码公式 (score-50)/10 等价",
        )
        db.add(row)
        db.flush()
        nested.commit()
        return row
    except IntegrityError:
        nested.rollback()
        existing = db.query(AaGpaPointPolicy).filter(
            AaGpaPointPolicy.tenant_id == _tid(),
            AaGpaPointPolicy.status == "ACTIVE",
            AaGpaPointPolicy.is_deleted.is_(False),
        ).order_by(AaGpaPointPolicy.policy_version.desc()).first()
        if not existing:
            raise AppException("DATA_CONFLICT", "默认绩点策略初始化失败，请重试", http_status=409)
        return existing


def evaluate_policy(policy, score) -> float:
    """按策略把 0-100 分数换算成绩点；LINEAR 支持自定义锚点，BANDS 按区间查表。"""
    s = float(score if score is not None else 0)
    scale = str(policy.scale_type or "LINEAR").upper()
    if scale == "BANDS":
        try:
            bands = json.loads(policy.bands_json or "[]")
        except (TypeError, ValueError):
            bands = []
        for band in bands:
            if float(band["minScore"]) <= s <= float(band["maxScore"]):
                return round(float(band["point"]), 2)
        return 0.0
    fail = float(policy.linear_fail_score if policy.linear_fail_score is not None else 60)
    anchor = float(policy.linear_anchor_score if policy.linear_anchor_score is not None else 50)
    divisor = float(policy.linear_divisor or 10)
    if s < fail:
        return 0.0
    return round((s - anchor) / divisor, 2)


def course_point_frozen(db, grade_row) -> float:
    """课程绩点：已冻结直接返回；未冻结（历史遗留或第一次计入 GPA）按当前生效策略冻结一次。

    冻结之后写在 `grade_row` 上但由调用方负责 flush/commit——本函数不单独开事务，
    与 `_refresh_aggregates` 统一的成绩写事务共用同一次提交。
    """
    if grade_row.gpa_point is not None and grade_row.gpa_policy_code:
        return float(grade_row.gpa_point)
    policy = resolve_active_policy(db)
    point = evaluate_policy(policy, grade_row.score)
    grade_row.gpa_point = point
    grade_row.gpa_policy_code = policy.policy_code
    grade_row.gpa_policy_version = int(policy.policy_version)
    return point


def list_gpa_policies(user) -> list[dict]:
    from app.models.academic_affairs_gpa_policy import AaGpaPointPolicy
    from app.services.db_service import session

    with session() as db:
        rows = db.query(AaGpaPointPolicy).filter(
            AaGpaPointPolicy.tenant_id == _tid(),
            AaGpaPointPolicy.is_deleted.is_(False),
        ).order_by(AaGpaPointPolicy.policy_version.desc(), AaGpaPointPolicy.id.desc()).all()
        return [_policy_dto(row) for row in rows]


def activate_gpa_policy(user, payload: dict) -> dict:
    """发布一个绩点策略版本：锁定现有 ACTIVE → SUPERSEDED → 落新 ACTIVE，一次事务。

    只影响此后"第一次计入 GPA"的成绩记录；已冻结 `gpa_point` 的历史记录不受影响
    （GPA-POLICY-01）。
    """
    from app.core.context import get_current_user_ctx
    from app.models import AffairsAuditTrail
    from app.models.academic_affairs_gpa_policy import AaGpaPointPolicy
    from app.services.db_service import session

    scale_type = str(payload.get("scaleType") or "LINEAR").strip().upper()
    if scale_type not in VALID_SCALE_TYPES:
        raise AppException("VALIDATION_ERROR", "scaleType 仅支持 LINEAR/BANDS")
    bands_json = None
    linear_fail = linear_anchor = linear_divisor = None
    if scale_type == "BANDS":
        bands_json = _validate_bands(payload.get("bands"))
    else:
        linear_fail = int(payload.get("linearFailScore") if payload.get("linearFailScore") is not None else 60)
        linear_anchor = int(payload.get("linearAnchorScore") if payload.get("linearAnchorScore") is not None else 50)
        linear_divisor = int(payload.get("linearDivisor") or 10)
        if linear_divisor <= 0:
            raise AppException("VALIDATION_ERROR", "linearDivisor 必须大于 0")

    with session() as db:
        same = db.query(AaGpaPointPolicy).filter(
            AaGpaPointPolicy.tenant_id == _tid(),
            AaGpaPointPolicy.status == "ACTIVE",
            AaGpaPointPolicy.is_deleted.is_(False),
        ).with_for_update().all()
        code = str(payload.get("policyCode") or DEFAULT_POLICY_CODE).strip().upper()
        chain = db.query(AaGpaPointPolicy.policy_version).filter(
            AaGpaPointPolicy.tenant_id == _tid(),
            AaGpaPointPolicy.policy_code == code,
        ).all()
        next_version = max([int(value) for (value,) in chain] + [0]) + 1
        for row in same:
            row.status = "SUPERSEDED"
            row.active_scope_key = None
        db.flush()
        row = AaGpaPointPolicy(
            tenant_id=_tid(),
            policy_code=code,
            policy_version=next_version,
            active_scope_key=_ACTIVE_SCOPE,
            scale_type=scale_type,
            linear_fail_score=linear_fail,
            linear_anchor_score=linear_anchor,
            linear_divisor=linear_divisor,
            bands_json=bands_json,
            status="ACTIVE",
            activated_at=datetime.utcnow(),
            remark=str(payload.get("remark") or "")[:200] or None,
        )
        db.add(row)
        try:
            db.flush()
        except IntegrityError as exc:
            db.rollback()
            raise AppException(
                "APPROVAL_VERSION_CONFLICT",
                "已有并发发布的绩点策略，请刷新后重试",
                details={"policyCode": code},
                http_status=409,
            ) from exc
        ctx = get_current_user_ctx() or user or {}
        db.add(AffairsAuditTrail(
            tenant_id=_tid(),
            biz_type="AA_GPA_POINT_POLICY",
            biz_id=row.id,
            action="POLICY_ACTIVATE",
            operator=str(ctx.get("userId") or ctx.get("loginName") or ""),
            role_name=str(ctx.get("currentRoleCode") or ""),
            detail=json.dumps(_policy_dto(row), ensure_ascii=False, sort_keys=True)[:990],
            occurred_at=datetime.utcnow(),
        ))
        db.commit()
        return _policy_dto(row)
