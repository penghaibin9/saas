"""13A-D 辅导员考评（D 包）：指标配置 → 录评分 → 发布 → 申诉复核。

total_score = 各指标得分之和（保留原口径，历史断言不变）；
weighted_total_score = 按指标 weight 的加权平均 Σscore×weight/Σweight（附加列，无可加权项→None）。
留痕 AuditTrail(biz_type=COUNSELOR_EVAL)。
考评为管理端配置数据，按租户可见（学工处/学院管理），不含学生 PII。
"""

from app.core.optimistic_lock import atomic_claim_version

from datetime import datetime

from sqlalchemy import select

from app.core.context import get_current_user_ctx
from app.core.exceptions import AppException, check_version, not_found
from app.services.db_service import _iso, _tid, session

L_EVAL_STATUS = {"DRAFT": "草稿", "PUBLISHED": "已发布"}
L_APPEAL = {"NONE": "无申诉", "SUBMITTED": "申诉待复核", "REVIEWED": "申诉已复核"}


def _op():
    u = get_current_user_ctx() or {}
    return (u.get("realName") or "系统"), (u.get("currentRoleCode") or ""), u.get("userId")


def _uid_int(user):
    try:
        return int((user or {}).get("userId") or 0) or None
    except (TypeError, ValueError):
        return None


def _audit(db, biz_id, action, detail=""):
    from app.models import AffairsAuditTrail
    n, r, _ = _op()
    db.add(AffairsAuditTrail(tenant_id=_tid(), biz_type="COUNSELOR_EVAL",
                             biz_id=int(biz_id) if biz_id else None, action=action,
                             operator=n, role_name=r, detail=detail, occurred_at=datetime.utcnow()))


# ── 指标 ──

def _ind_row(i) -> dict:
    return {"indicatorId": str(i.id), "name": i.name, "category": i.category or "",
            "weight": float(i.weight) if i.weight is not None else None,
            "maxScore": float(i.max_score) if i.max_score is not None else None,
            "sortOrder": i.sort_order or 0, "status": i.status}


def list_indicators(user, status=None):
    from app.models import CounselorEvalIndicator
    with session() as db:
        conds = [CounselorEvalIndicator.tenant_id == _tid(), CounselorEvalIndicator.is_deleted.is_(False)]
        if status:
            conds.append(CounselorEvalIndicator.status == status)
        rows = db.scalars(select(CounselorEvalIndicator).where(*conds).order_by(
            CounselorEvalIndicator.sort_order, CounselorEvalIndicator.id)).all()
        return [_ind_row(i) for i in rows]


def create_indicator(body, user) -> dict:
    from app.models import CounselorEvalIndicator
    name = (getattr(body, "name", "") or "").strip()
    if not name:
        raise AppException("VALIDATION_ERROR", "指标名称必填")
    with session() as db:
        dup = db.scalars(select(CounselorEvalIndicator).where(
            CounselorEvalIndicator.tenant_id == _tid(), CounselorEvalIndicator.name == name,
            CounselorEvalIndicator.is_deleted.is_(False))).first()
        if dup:
            raise AppException("DATA_CONFLICT", "同名指标已存在")
        i = CounselorEvalIndicator(tenant_id=_tid(), name=name, category=getattr(body, "category", None),
                                   weight=getattr(body, "weight", None),
                                   max_score=getattr(body, "maxScore", None) or 100,
                                   sort_order=getattr(body, "sortOrder", 0) or 0, status="ENABLED",
                                   created_by=_uid_int(user))
        db.add(i); db.flush()
        _audit(db, i.id, "INDICATOR_CREATE", name)
        db.commit(); db.refresh(i)
        return _ind_row(i)


# ── 考评记录 ──

def _eval_row(e) -> dict:
    return {"evalId": str(e.id), "periodCode": e.period_code, "counselorKey": e.counselor_key,
            "counselorName": e.counselor_name or "", "scores": e.scores_json or {},
            "totalScore": float(e.total_score) if e.total_score is not None else None,
            "weightedTotalScore": float(e.weighted_total_score) if e.weighted_total_score is not None else None,
            "remark": e.remark or "", "status": e.status, "statusLabel": L_EVAL_STATUS.get(e.status, e.status),
            "publishedAt": _iso(e.published_at), "appealStatus": e.appeal_status,
            "appealStatusLabel": L_APPEAL.get(e.appeal_status, e.appeal_status),
            "appealReason": e.appeal_reason or "", "appealResult": e.appeal_result or "",
            "appealOpinion": e.appeal_opinion or "", "version": e.version}


def _total(scores) -> float:
    if not isinstance(scores, dict):
        return 0.0
    tot = 0.0
    for v in scores.values():
        try:
            tot += float(v)
        except (TypeError, ValueError):
            continue
    return round(tot, 2)


def _weighted_total(db, scores):
    """加权总分口径＝**按权重的加权平均**：Σ(score_i×weight_i) / Σweight_i，
    只统计 scores 中 key 命中「当期启用且 weight>0」指标的项（scores_json key = indicatorId）。
    无任何可加权项（指标未配权重/无匹配）→ 返回 None，前端回退展示原始 total_score，历史不受影响。"""
    if not isinstance(scores, dict) or not scores:
        return None
    from app.models import CounselorEvalIndicator
    inds = db.scalars(select(CounselorEvalIndicator).where(
        CounselorEvalIndicator.tenant_id == _tid(),
        CounselorEvalIndicator.is_deleted.is_(False),
        CounselorEvalIndicator.status == "ENABLED")).all()
    wmap = {str(i.id): float(i.weight) for i in inds if i.weight is not None and float(i.weight) > 0}
    num = den = 0.0
    for k, v in scores.items():
        w = wmap.get(str(k))
        if w is None:
            continue
        try:
            num += float(v) * w
            den += w
        except (TypeError, ValueError):
            continue
    if den <= 0:
        return None
    return round(num / den, 2)


def _self_scope_keys(user):
    """COUNSELOR 角色仅"本人"自助权（见 permissions.py 注释），非管理/复核角色收敛为自身可命中的 key 集合。"""
    role = ((user or {}).get("currentRoleCode") or "").upper()
    if role != "COUNSELOR":
        return None
    from app.core.affairs_security import _derive_keys
    return _derive_keys(user or {})


def list_evals(user, period_code=None, status=None, page=1, page_size=50):
    from app.models import CounselorEval
    my_keys = _self_scope_keys(user)
    with session() as db:
        conds = [CounselorEval.tenant_id == _tid(), CounselorEval.is_deleted.is_(False)]
        if period_code:
            conds.append(CounselorEval.period_code == period_code)
        if status:
            conds.append(CounselorEval.status == status)
        rows = db.scalars(select(CounselorEval).where(*conds).order_by(
            CounselorEval.total_score.desc())).all()
        if my_keys is not None:
            rows = [e for e in rows if e.counselor_key in my_keys]
        out = [_eval_row(e) for e in rows]
        total = len(out)
        start = (max(1, page) - 1) * page_size
        return out[start:start + page_size], total


def upsert_eval(body, user) -> dict:
    """录/改评分（DRAFT 状态可覆盖；已发布不可改，需先撤回——此处发布后禁改）。"""
    from app.models import CounselorEval
    period = (getattr(body, "periodCode", "") or "").strip()
    key = (getattr(body, "counselorKey", "") or "").strip()
    if not period or not key:
        raise AppException("VALIDATION_ERROR", "考评周期与辅导员标识必填")
    scores = getattr(body, "scores", None) or {}
    with session() as db:
        e = db.scalars(select(CounselorEval).where(
            CounselorEval.tenant_id == _tid(), CounselorEval.period_code == period,
            CounselorEval.counselor_key == key, CounselorEval.is_deleted.is_(False))).first()
        if e and e.status == "PUBLISHED":
            raise AppException("DATA_CONFLICT", "已发布考评不可修改")
        if e is None:
            e = CounselorEval(tenant_id=_tid(), period_code=period, counselor_key=key,
                              counselor_name=getattr(body, "counselorName", None),
                              scores_json=scores, total_score=_total(scores),
                              weighted_total_score=_weighted_total(db, scores), status="DRAFT",
                              remark=getattr(body, "remark", None), created_by=_uid_int(user))
            db.add(e); db.flush()
        else:
            e.scores_json, e.total_score = scores, _total(scores)
            e.weighted_total_score = _weighted_total(db, scores)
            e.counselor_name = getattr(body, "counselorName", None) or e.counselor_name
            e.remark, e.version = getattr(body, "remark", None), e.version + 1
        _audit(db, e.id, "EVAL_UPSERT", f"{period}/{key}")
        db.commit(); db.refresh(e)
        return _eval_row(e)


def _load(db, eval_id):
    from app.models import CounselorEval
    e = db.get(CounselorEval, int(eval_id))
    if not e or e.is_deleted or e.tenant_id != _tid():
        raise not_found("考评记录不存在")
    return e


def publish_eval(eval_id, user, expected_version=None) -> dict:
    with session() as db:
        e = _load(db, eval_id)
        if e.status == "PUBLISHED":
            raise AppException("DATA_CONFLICT", "已发布")
        atomic_claim_version(db, e, expected_version)
        e.status, e.published_at, e.version = "PUBLISHED", datetime.utcnow(), e.version + 1
        _audit(db, e.id, "EVAL_PUBLISH", "")
        db.commit(); db.refresh(e)
        return _eval_row(e)


def submit_eval_appeal(eval_id, body, user) -> dict:
    """辅导员对已发布考评申诉（理由≥5；一条只允许一次进行中申诉）。"""
    reason = (getattr(body, "reason", "") or "").strip()
    if len(reason) < 5:
        raise AppException("VALIDATION_ERROR", "申诉理由至少 5 字")
    with session() as db:
        e = _load(db, eval_id)
        my_keys = _self_scope_keys(user)
        if my_keys is not None and e.counselor_key not in my_keys:
            raise AppException("NO_DATA_SCOPE", "只能对本人考评发起申诉")
        if e.status != "PUBLISHED":
            raise AppException("DATA_CONFLICT", "仅已发布考评可申诉")
        if e.appeal_status == "SUBMITTED":
            raise AppException("DATA_CONFLICT", "已有待复核申诉")
        e.appeal_status, e.appeal_reason, e.version = "SUBMITTED", reason, e.version + 1
        _audit(db, e.id, "EVAL_APPEAL_SUBMIT", "")
        db.commit(); db.refresh(e)
        return _eval_row(e)


def review_eval_appeal(eval_id, body, user) -> dict:
    """申诉复核：UPHELD 维持/ADJUSTED 调整(可带新总分)。意见≥5。"""
    result = (getattr(body, "result", "") or "").strip()
    if result not in ("UPHELD", "ADJUSTED"):
        raise AppException("VALIDATION_ERROR", "复核结论非法")
    opinion = (getattr(body, "opinion", "") or "").strip()
    if len(opinion) < 5:
        raise AppException("VALIDATION_ERROR", "复核意见至少 5 字")
    with session() as db:
        e = _load(db, eval_id)
        if e.appeal_status != "SUBMITTED":
            raise AppException("DATA_CONFLICT", "无待复核申诉")
        atomic_claim_version(db, e, getattr(body, "version", None))
        e.appeal_status, e.appeal_result, e.appeal_opinion = "REVIEWED", result, opinion
        new_scores = getattr(body, "scores", None)
        if result == "ADJUSTED" and isinstance(new_scores, dict) and new_scores:
            e.scores_json, e.total_score = new_scores, _total(new_scores)
            e.weighted_total_score = _weighted_total(db, new_scores)
        e.version += 1
        _audit(db, e.id, "EVAL_APPEAL_REVIEW", result)
        db.commit(); db.refresh(e)
        return _eval_row(e)
