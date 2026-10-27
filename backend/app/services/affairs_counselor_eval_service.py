"""13A-D 辅导员考评（D 包）：指标配置 → 录评分 → 发布 → 申诉复核。

total_score = 各指标得分之和（保留原口径，历史断言不变）；
weighted_total_score = 按指标 weight 的加权平均 Σscore×weight/Σweight（附加列，无可加权项→None）。
留痕 AuditTrail(biz_type=COUNSELOR_EVAL)。
考评为管理端配置数据，按租户可见（学工处/学院管理），不含学生 PII。
"""

from app.core.optimistic_lock import atomic_claim_version

from datetime import datetime

from sqlalchemy import String, cast, func, or_, select

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
        return int(str((user or {}).get("userId") or "0").removeprefix("db-")) or None
    except (TypeError, ValueError):
        return None


def _audit(db, biz_id, action, detail=""):
    from app.models import AffairsAuditTrail
    n, r, _ = _op()
    db.add(AffairsAuditTrail(tenant_id=_tid(), biz_type="COUNSELOR_EVAL",
                             biz_id=int(biz_id) if biz_id else None, action=action,
                             operator=n, role_name=r, detail=detail, occurred_at=datetime.utcnow(),
                             created_by=_uid_int(get_current_user_ctx())))


def _accounts(db, keys):
    from app.models import User
    keys = {str(key) for key in keys}
    ids = {int(key.removeprefix("db-")) for key in keys if key.removeprefix("db-").isdigit()}
    users = db.scalars(select(User).where(User.tenant_id == _tid(),
        or_(User.login_name.collate("utf8mb4_bin").in_(keys), User.id.in_(ids or {-1})))).all()
    matches = {}
    for account in users:
        for key in (account.login_name, str(account.id), f"db-{account.id}"):
            matches.setdefault(key, []).append(account)
    result = {}
    for key in keys:
        found = {row.id: row for row in matches.get(key, [])}
        result[key] = next(iter(found.values())) if len(found) == 1 else None
    return result


def _scope(db, user):
    from app.core.affairs_security import build_affairs_context
    from app.models import AffairsCounselorAssignment, SchoolClass
    ctx = build_affairs_context(user, db)
    if ctx.scope_type == "TENANT_ALL":
        return ctx, None
    if str(user.get("currentRoleCode") or "").upper() == "COUNSELOR":
        return ctx, {_uid_int(user)} - {None}
    classes = ctx.allowed_class_ids(db) or {-1}
    ids = set(db.scalars(select(SchoolClass.counselor_id).where(
        SchoolClass.tenant_id == _tid(), SchoolClass.is_deleted.is_(False),
        SchoolClass.id.in_(classes), SchoolClass.counselor_id.is_not(None))).all())
    now = datetime.utcnow()
    ids.update(db.scalars(select(AffairsCounselorAssignment.user_id).where(
        AffairsCounselorAssignment.tenant_id == _tid(), AffairsCounselorAssignment.class_id.in_(classes),
        AffairsCounselorAssignment.is_deleted.is_(False), AffairsCounselorAssignment.status == "ACTIVE",
        AffairsCounselorAssignment.effective_from <= now,
        or_(AffairsCounselorAssignment.effective_to.is_(None), AffairsCounselorAssignment.effective_to > now))).all())
    return ctx, ids


def _active_counselors(db, ids):
    from app.models import Role, UserRole
    from app.services.role_assignment_scope_service import active_role_membership_query
    return {row.user_id for row in db.scalars(active_role_membership_query(_tid()).where(
        Role.role_code == "COUNSELOR", UserRole.user_id.in_(ids or {-1}))).all()}


def _target(db, key, user, *, self_forbidden=True):
    target = _accounts(db, [key]).get(str(key))
    if not target or target.id not in _active_counselors(db, {target.id}):
        raise AppException("DATA_CONFLICT", "辅导员账号、任职或历史标识尚无法核实，请先核验；原记录保留")
    ctx, ids = _scope(db, user)
    if ids is not None and target.id not in ids:
        raise AppException("NO_DATA_SCOPE", "该辅导员不在当前考评职责的授权范围内")
    actor = _uid_int(user)
    if not actor or (self_forbidden and actor == target.id):
        raise AppException("NO_PERMISSION", "本人考评必须回避，请由其他有权人员办理")
    return target, ctx


def _score_actors(db, eval_ids):
    from app.models import AffairsAuditTrail
    result = {int(eid): [] for eid in eval_ids}
    # 两套考评共用业务类型，必须以现用动作区分，不能按编号混入另一套留痕。
    for row in db.scalars(select(AffairsAuditTrail).where(
        AffairsAuditTrail.tenant_id == _tid(), AffairsAuditTrail.biz_type == "COUNSELOR_EVAL",
        AffairsAuditTrail.biz_id.in_(eval_ids or {-1}),
        or_(AffairsAuditTrail.action == "EVAL_UPSERT",
            (AffairsAuditTrail.action == "EVAL_APPEAL_REVIEW") & (AffairsAuditTrail.detail == "ADJUSTED")))).all():
        result[int(row.biz_id)].append(row.created_by)
    return result


def capabilities(user):
    from app.core.permissions import has_permission
    with session() as db:
        ctx, ids = _scope(db, user)
        manage = has_permission(user, "studentAffairs.counselorEval.manage")
        return {"canScore": manage and (ids is None or bool(ids)),
                "canManageIndicators": manage and ctx.scope_type == "TENANT_ALL"}


def _present(db, rows, user):
    from app.core.permissions import has_permission
    accounts = _accounts(db, [row.counselor_key for row in rows])
    active = _active_counselors(db, {u.id for u in accounts.values() if u})
    ctx, ids = _scope(db, user)
    actor = _uid_int(user)
    manage = has_permission(user, "studentAffairs.counselorEval.manage")
    scorers = _score_actors(db, {row.id for row in rows if row.appeal_status == "SUBMITTED"})
    out = []
    for row in rows:
        data = _eval_row(row); actions = []; target = accounts.get(row.counselor_key)
        own = bool(target and actor == target.id)
        writable = bool(target and target.id in active and (ids is None or target.id in ids))
        if manage and writable and not own and row.status == "DRAFT":
            actions.append("SCORE")
            if ctx.scope_type == "TENANT_ALL": actions.append("PUBLISH")
        if own and row.status == "PUBLISHED" and row.appeal_status != "SUBMITTED" and has_permission(user, "studentAffairs.counselorEval.appeal.create"):
            actions.append("APPEAL")
        if row.appeal_status == "SUBMITTED":
            actors = scorers.get(row.id, [])
            if not actors or any(not uid for uid in actors):
                data["reviewBlockReason"] = "历史实际评分人尚无法核实，申诉与原结果保留，待核验处理。"
            elif manage and writable and not own and actor not in actors:
                actions.append("REVIEW")
            else:
                data["reviewBlockReason"] = "本次申诉须由未参与评分且符合回避要求的有权人员复核。"
        data["allowedActions"] = actions; out.append(data)
    return out


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
        from app.core.affairs_security import require_school_scope
        require_school_scope(db, user)
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


def list_evals(user, period_code=None, status=None, page=1, page_size=50):
    from app.models import CounselorEval, User
    with session() as db:
        _, ids = _scope(db, user)
        conds = [CounselorEval.tenant_id == _tid(), CounselorEval.is_deleted.is_(False)]
        if ids is not None:
            key = CounselorEval.counselor_key.collate("utf8mb4_bin")
            identity = [User.tenant_id == _tid(), or_(User.login_name.collate("utf8mb4_bin") == key,
                cast(User.id, String).collate("utf8mb4_bin") == key,
                func.concat("db-", User.id).collate("utf8mb4_bin") == key)]
            conds.append(select(func.count(User.id)).where(*identity).correlate(CounselorEval).scalar_subquery() == 1)
            conds.append(select(func.max(User.id)).where(*identity).correlate(CounselorEval).scalar_subquery().in_(ids or {-1}))
        if str(user.get("currentRoleCode") or "").upper() == "COUNSELOR":
            conds.append(CounselorEval.status == "PUBLISHED")
        if period_code:
            conds.append(CounselorEval.period_code == period_code)
        if status:
            conds.append(CounselorEval.status == status)
        total = int(db.scalar(select(func.count()).select_from(CounselorEval).where(*conds)) or 0)
        start = (max(1, page) - 1) * page_size
        rows = db.scalars(select(CounselorEval).where(*conds).order_by(
            CounselorEval.total_score.desc(), CounselorEval.id).offset(start).limit(page_size)).all()
        return _present(db, rows, user), total


def upsert_eval(body, user) -> dict:
    """录/改评分（DRAFT 状态可覆盖；已发布不可改，需先撤回——此处发布后禁改）。"""
    from app.models import CounselorEval
    period = (getattr(body, "periodCode", "") or "").strip()
    key = (getattr(body, "counselorKey", "") or "").strip()
    if not period or not key:
        raise AppException("VALIDATION_ERROR", "考评周期与辅导员标识必填")
    scores = getattr(body, "scores", None) or {}
    with session() as db:
        target, _ = _target(db, key, user)
        key = target.login_name
        existing = db.scalars(select(CounselorEval).where(
            CounselorEval.tenant_id == _tid(), CounselorEval.period_code == period,
            CounselorEval.counselor_key.in_((key, str(target.id), f"db-{target.id}")), CounselorEval.is_deleted.is_(False)).with_for_update()).all()
        if len(existing) > 1:
            raise AppException("DATA_CONFLICT", "同周期存在多个历史身份标识，原记录保留，请先核验归属")
        e = existing[0] if existing else None
        if e:
            resolved, _ = _target(db, e.counselor_key, user)
            if resolved.id != target.id:
                raise AppException("DATA_CONFLICT", "历史辅导员标识归属冲突，原记录保留，请先核验")
        if e and e.status == "PUBLISHED":
            raise AppException("DATA_CONFLICT", "已发布考评不可修改")
        if e is None:
            e = CounselorEval(tenant_id=_tid(), period_code=period, counselor_key=key,
                              counselor_name=target.real_name,
                              scores_json=scores, total_score=_total(scores),
                              weighted_total_score=_weighted_total(db, scores), status="DRAFT",
                              remark=getattr(body, "remark", None), created_by=_uid_int(user))
            db.add(e); db.flush()
        else:
            atomic_claim_version(db, e, getattr(body, "version", None))
            e.scores_json, e.total_score = scores, _total(scores)
            e.weighted_total_score = _weighted_total(db, scores)
            e.counselor_name = target.real_name
            e.remark, e.version = getattr(body, "remark", None), e.version + 1
        e.updated_by = _uid_int(user)
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
        _target(db, e.counselor_key, user)
        from app.core.affairs_security import require_school_scope
        require_school_scope(db, user)
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
        target = _accounts(db, [e.counselor_key]).get(e.counselor_key)
        if not target or target.id != _uid_int(user):
            raise AppException("NO_DATA_SCOPE", "只能对本人考评发起申诉")
        if e.status != "PUBLISHED":
            raise AppException("DATA_CONFLICT", "仅已发布考评可申诉")
        if e.appeal_status == "SUBMITTED":
            raise AppException("DATA_CONFLICT", "已有待复核申诉")
        atomic_claim_version(db, e, getattr(body, "version", None))
        e.appeal_status, e.appeal_reason, e.version = "SUBMITTED", reason, e.version + 1
        _audit(db, e.id, "EVAL_APPEAL_SUBMIT", reason)
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
        _target(db, e.counselor_key, user)
        actors = _score_actors(db, {e.id})[e.id]
        if not actors or any(not uid for uid in actors):
            raise AppException("DATA_CONFLICT", "历史实际评分人尚无法核实，原结果与申诉保留，请先核验")
        if _uid_int(user) in actors:
            raise AppException("NO_PERMISSION", "原评分人不能独自复核对自己评分的申诉，请转其他有权人员")
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
