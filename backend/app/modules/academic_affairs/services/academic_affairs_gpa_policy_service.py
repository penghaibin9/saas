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
import math
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
    """Validate coverage of the existing integer-score domain, without changing bands.

    AcademicGrade.score is an integer. Decimal scores are not rounded here;
    evaluation also refuses any uncovered input rather than silently returning zero.
    """
    if not isinstance(bands, list) or not bands:
        raise AppException("VALIDATION_ERROR", "BANDS 策略必须提供非空的分数区间数组")
    normalized = []
    for item in bands:
        try:
            raw = (item["minScore"], item["maxScore"], item["point"])
            if any(isinstance(value, bool) for value in raw):
                raise ValueError("boolean is not a score")
            lo, hi, point = map(float, raw)
        except (KeyError, TypeError, ValueError, OverflowError) as exc:
            raise AppException("VALIDATION_ERROR", "BANDS 每项须包含有效 minScore/maxScore/point") from exc
        if not all(math.isfinite(value) for value in (lo, hi, point)) or not (
                0 <= lo <= hi <= 100 and 0 <= point <= 5):
            raise AppException("VALIDATION_ERROR", "绩点区间须为有限数值：0≤下限≤上限≤100，绩点0至5")
        normalized.append({"minScore": lo, "maxScore": hi, "point": round(point, 2)})
    normalized.sort(key=lambda item: item["minScore"])
    for prev, cur in zip(normalized, normalized[1:]):
        if cur["minScore"] <= prev["maxScore"]:
            raise AppException("VALIDATION_ERROR", "BANDS 区间存在重叠")
    missing = [score for score in range(101)
               if not any(item["minScore"] <= score <= item["maxScore"] for item in normalized)]
    if missing:
        sample = "、".join(map(str, missing[:12]))
        raise AppException("VALIDATION_ERROR", f"BANDS 未覆盖全部0至100整数成绩，缺少：{sample}")
    return json.dumps(normalized, ensure_ascii=False)


def resolve_active_policy(db):
    """读取租户当前 ACTIVE 绩点策略；不存在则落一条与历史硬编码公式完全等价的默认策略。

    默认策略 (score-50)/10（60→1.0，100→5.0，<60→0）与升级前 `_course_point()` 的行为
    逐分值一致，保证首次上线不改变任何学生的历史 GPA。

    同一事务内缓存在 `db.info`：批量发布成绩时 `_refresh_aggregates` 会对每个学生的
    每条成绩各调用一次本函数，策略在同一事务内不会变化，逐行重复查同一张策略表是
    可量化的 N+1（P1 批次C）。`db.info` 是 SQLAlchemy Session 自带的会话级字典，
    Session 关闭即失效，不会跨请求残留旧策略。
    """
    from app.models.academic_affairs_gpa_policy import AaGpaPointPolicy

    cache_key = f"_gpa_active_policy_{_tid()}"
    cached = db.info.get(cache_key)
    if cached is not None:
        return cached
    policy = db.query(AaGpaPointPolicy).filter(
        AaGpaPointPolicy.tenant_id == _tid(),
        AaGpaPointPolicy.status == "ACTIVE",
        AaGpaPointPolicy.is_deleted.is_(False),
    ).order_by(AaGpaPointPolicy.policy_version.desc()).first()
    if not policy:
        policy = _ensure_default_policy(db)
    db.info[cache_key] = policy
    return policy


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


def _validate_linear_parameters(fail, anchor, divisor):
    """Accept existing integer configuration fields, reject silent coercion/defaulting."""
    values = []
    try:
        for value in (fail, anchor, divisor):
            if isinstance(value, bool):
                raise ValueError("boolean parameter")
            number = float(value)
            if not math.isfinite(number) or not number.is_integer():
                raise ValueError("parameter must be a finite integer")
            values.append(int(number))
    except (TypeError, ValueError, OverflowError) as exc:
        raise AppException("VALIDATION_ERROR", "线性绩点参数必须为有限整数") from exc
    fail, anchor, divisor = values
    if not (0 <= fail <= 100 and 0 <= anchor <= 100 and divisor > 0):
        raise AppException("VALIDATION_ERROR", "及格线和锚点须在0至100之间，除数须大于0")
    if (fail - anchor) / divisor < 0 or (100 - anchor) / divisor > 5:
        raise AppException("VALIDATION_ERROR", "线性公式会产生负绩点或大于5的绩点，请核对参数")
    return fail, anchor, divisor


def evaluate_policy(policy, score) -> float:
    """Evaluate the same policy; invalid inputs/rules fail rather than becoming zero."""
    try:
        if isinstance(score, bool):
            raise ValueError("boolean score")
        s = float(score if score is not None else 0)
        if not math.isfinite(s) or not 0 <= s <= 100:
            raise ValueError("score outside domain")
    except (TypeError, ValueError, OverflowError) as exc:
        raise AppException("VALIDATION_ERROR", "成绩必须是0至100之间的有限数值") from exc
    scale = str(policy.scale_type or "LINEAR").upper()
    if scale == "BANDS":
        try:
            bands = json.loads(_validate_bands(json.loads(policy.bands_json or "[]")))
        except (TypeError, ValueError, AppException) as exc:
            raise AppException("GPA_POLICY_INVALID", "绩点区间策略无效，请核对完整分段", http_status=409) from exc
        for band in bands:
            if band["minScore"] <= s <= band["maxScore"]:
                return round(band["point"], 2)
        raise AppException("GPA_POLICY_INVALID", "绩点分段未覆盖本次成绩，禁止默认为0", http_status=409)
    if scale != "LINEAR":
        raise AppException("GPA_POLICY_INVALID", "不支持的绩点换算类型", http_status=409)
    try:
        fail, anchor, divisor = _validate_linear_parameters(
            policy.linear_fail_score if policy.linear_fail_score is not None else 60,
            policy.linear_anchor_score if policy.linear_anchor_score is not None else 50,
            policy.linear_divisor if policy.linear_divisor is not None else 10,
        )
    except AppException as exc:
        raise AppException("GPA_POLICY_INVALID", "线性绩点策略参数无效", http_status=409) from exc
    return 0.0 if s < fail else round((s - anchor) / divisor, 2)


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
        linear_fail, linear_anchor, linear_divisor = _validate_linear_parameters(
            payload.get("linearFailScore") if payload.get("linearFailScore") is not None else 60,
            payload.get("linearAnchorScore") if payload.get("linearAnchorScore") is not None else 50,
            payload.get("linearDivisor") if payload.get("linearDivisor") is not None else 10,
        )

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
