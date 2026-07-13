"""岗位实习 · 实习成绩五项权重核算（P2-D，成熟商业核心）。

五项：打卡 / 周报 / 月报总结 / 企业评价 / 学校(指导教师)评价，权重和须=100。
状态机：PENDING_CALC 待核算 → PENDING_REVIEW 待复核 → PUBLISHED 已发布 → WITHDRAWN 已撤回 → ARCHIVED 已归档。
缺项(incomplete)不得发布。企业评价分可自动取已通过企业评价均分。
owner + 数据范围复用 internship_service。审计 target_type=SCORE。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import select

from app.core.exceptions import AppException, no_permission, not_found
from app.models import (InternshipAuditTrail, InternshipEnterpriseEval, InternshipFinalScore,
                        InternshipRecord, InternshipScoreConfig, StudentProfile)
from app.services.db_service import _iso, _tid, session

STATUS_LABEL = {"PENDING_CALC": "待核算", "PENDING_REVIEW": "待复核", "PUBLISHED": "已发布",
                "WITHDRAWN": "已撤回", "ARCHIVED": "已归档"}
COMPONENTS = [("checkinScore", "checkin_score", "w_checkin", "打卡"),
              ("weeklyScore", "weekly_score", "w_weekly", "周报"),
              ("monthlyScore", "monthly_score", "w_monthly", "月报总结"),
              ("enterpriseScore", "enterprise_score", "w_enterprise", "企业评价"),
              ("schoolScore", "school_score", "w_school", "学校评价")]
DEFAULT_CFG = dict(checkin_weight=20, weekly_weight=20, monthly_weight=10,
                   enterprise_weight=30, school_weight=20, pass_line=60.0)


def _op_name(user) -> str:
    return (user or {}).get("realName") or "系统"


def _trail(db, sid, action, detail=None, operator="系统"):
    db.add(InternshipAuditTrail(tenant_id=_tid(), target_id=sid, target_type="SCORE",
                                action=action, operator_name=operator, detail_json=detail or {},
                                occurred_at=datetime.utcnow()))


def _get(db, sid) -> InternshipFinalScore:
    s = db.get(InternshipFinalScore, int(sid))
    if not s or s.is_deleted or s.tenant_id != _tid():
        raise not_found("成绩不存在")
    return s


def _ctx(db, s):
    rec = db.get(InternshipRecord, s.internship_id)
    stu = db.get(StudentProfile, s.student_id)
    return rec, stu


def _scope_ctx(user):
    from app.modules.internship.services.internship_service import _current_scope, _rec_in_scope
    return _current_scope(user), _rec_in_scope


# ═══════════ 权重配置 ═══════════

def _active_config(db, batch_id=None):
    """Batch-specific active config wins; each save creates a new immutable active snapshot."""
    base = [InternshipScoreConfig.tenant_id == _tid(), InternshipScoreConfig.status == "ACTIVE",
            InternshipScoreConfig.is_deleted.is_(False)]
    if batch_id:
        batch = db.scalars(select(InternshipScoreConfig).where(
            *base, InternshipScoreConfig.batch_id == int(batch_id)).order_by(InternshipScoreConfig.id.desc())).first()
        if batch:
            return batch
    return db.scalars(select(InternshipScoreConfig).where(
        *base, InternshipScoreConfig.batch_id.is_(None)).order_by(InternshipScoreConfig.id.desc())).first()


def get_config(user=None) -> dict:
    with session() as db:
        c = _active_config(db, batch_id=None)
        if not c:
            return {**{k: v for k, v in DEFAULT_CFG.items()},
                    "checkinWeight": 20, "weeklyWeight": 20, "monthlyWeight": 10,
                    "enterpriseWeight": 30, "schoolWeight": 20, "passLine": 60.0, "isDefault": True,
                    "configId": "", "configVersion": 0}
        return {"checkinWeight": c.checkin_weight, "weeklyWeight": c.weekly_weight,
                "monthlyWeight": c.monthly_weight, "enterpriseWeight": c.enterprise_weight,
                "schoolWeight": c.school_weight, "passLine": c.pass_line, "isDefault": False,
                "configId": str(c.id), "configVersion": int(c.version or 0)}


def save_config(user, body) -> dict:
    from app.core.permissions import enforce_permission
    enforce_permission(user or {}, "internship.score.config.manage")
    b = body or {}
    weights = {"checkin_weight": b.get("checkinWeight"), "weekly_weight": b.get("weeklyWeight"),
               "monthly_weight": b.get("monthlyWeight"), "enterprise_weight": b.get("enterpriseWeight"),
               "school_weight": b.get("schoolWeight")}
    parsed = {}
    for k, v in weights.items():
        try:
            iv = int(v)
        except (TypeError, ValueError):
            raise AppException("VALIDATION_ERROR", "五项权重均必填且为整数")
        if iv < 0 or iv > 100:
            raise AppException("VALIDATION_ERROR", "权重须在 0-100 之间")
        parsed[k] = iv
    if sum(parsed.values()) != 100:
        raise AppException("VALIDATION_ERROR", f"五项权重之和须为 100，当前为 {sum(parsed.values())}")
    try:
        pass_line = float(b.get("passLine", 60))
    except (TypeError, ValueError):
        raise AppException("VALIDATION_ERROR", "及格线必须是数字")
    if not 0 <= pass_line <= 100:
        raise AppException("VALIDATION_ERROR", "及格线须在 0-100 之间")
    with session() as db:
        batch_id = b.get("batchId") or None
        if batch_id:
            from app.models import InternshipBatch
            batch = db.get(InternshipBatch, int(batch_id))
            if not batch or batch.is_deleted or batch.tenant_id != _tid():
                raise not_found("实习批次不存在")
            if batch.status != "DRAFT":
                raise AppException("DATA_CONFLICT", "运行中的批次不可替换评分规则，请创建新批次版本")
        old = _active_config(db, batch_id=batch_id)
        if old and old.batch_id == (int(batch_id) if batch_id else None):
            old.status = "RETIRED"
        c = InternshipScoreConfig(tenant_id=_tid(), batch_id=int(batch_id) if batch_id else None,
                                  status="ACTIVE")
        db.add(c)
        for k, v in parsed.items():
            setattr(c, k, v)
        c.pass_line = pass_line
        c.version = (c.version or 0) + 1
        db.flush()
        _trail(db, c.id, "SAVE_CONFIG", {**parsed, "passLine": pass_line}, operator=_op_name(user))
        db.commit()
        return {"ok": True, "configId": str(c.id), "configVersion": int(c.version or 0),
                "batchId": str(c.batch_id) if c.batch_id else ""}


# ═══════════ 核算 / 复核 / 发布 ═══════════

def _enterprise_avg(db, internship_id):
    e = db.scalars(select(InternshipEnterpriseEval).where(
        InternshipEnterpriseEval.tenant_id == _tid(), InternshipEnterpriseEval.internship_id == internship_id,
        InternshipEnterpriseEval.school_review_status == "APPROVED",
        InternshipEnterpriseEval.is_deleted.is_(False))).first()
    if not e:
        return None
    return round((e.attendance_score + e.skill_score + e.attitude_score
                  + e.collaboration_score + e.safety_score) / 5)


def _score_or_none(v):
    if v is None or str(v) == "":
        return None
    iv = int(v)
    if not 0 <= iv <= 100:
        raise AppException("VALIDATION_ERROR", "各项成绩须在 0-100 之间")
    return iv


def compute(user, body) -> dict:
    b = body or {}
    iid = b.get("internshipId") or b.get("internId")
    if not iid:
        raise AppException("VALIDATION_ERROR", "缺少实习记录 internshipId")
    comps = {"checkin_score": _score_or_none(b.get("checkinScore")),
             "weekly_score": _score_or_none(b.get("weeklyScore")),
             "monthly_score": _score_or_none(b.get("monthlyScore")),
             "school_score": _score_or_none(b.get("schoolScore"))}
    scope, in_scope = _scope_ctx(user)
    with session() as db:
        rec = db.get(InternshipRecord, int(iid))
        if not rec or rec.is_deleted or rec.tenant_id != _tid():
            raise not_found("实习记录不存在")
        stu = db.get(StudentProfile, rec.student_id)
        if not in_scope(scope, db, rec, stu):
            raise no_permission("只能核算本人指导学生的成绩")
        # 企业评价分：body 优先，否则自动取已通过企业评价均分
        ent = _score_or_none(b.get("enterpriseScore"))
        if ent is None:
            ent = _enterprise_avg(db, rec.id)
        comps["enterprise_score"] = ent
        cfg = _active_config(db, rec.batch_id)
        w = dict(w_checkin=(cfg.checkin_weight if cfg else DEFAULT_CFG["checkin_weight"]),
                 w_weekly=(cfg.weekly_weight if cfg else DEFAULT_CFG["weekly_weight"]),
                 w_monthly=(cfg.monthly_weight if cfg else DEFAULT_CFG["monthly_weight"]),
                 w_enterprise=(cfg.enterprise_weight if cfg else DEFAULT_CFG["enterprise_weight"]),
                 w_school=(cfg.school_weight if cfg else DEFAULT_CFG["school_weight"]))
        pass_line = cfg.pass_line if cfg else DEFAULT_CFG["pass_line"]
        missing = [label for jk, col, wk, label in COMPONENTS if comps[col] is None]
        incomplete = bool(missing)
        total = None
        if not incomplete:
            total = round(
                (comps["checkin_score"] * w["w_checkin"] + comps["weekly_score"] * w["w_weekly"]
                 + comps["monthly_score"] * w["w_monthly"] + comps["enterprise_score"] * w["w_enterprise"]
                 + comps["school_score"] * w["w_school"]) / 100, 1)
        s = db.scalars(select(InternshipFinalScore).where(
            InternshipFinalScore.tenant_id == _tid(), InternshipFinalScore.internship_id == rec.id,
            InternshipFinalScore.is_deleted.is_(False))).first()
        if s and s.status == "PUBLISHED":
            raise AppException("DATA_CONFLICT", "成绩已发布，请先撤回再重算")
        new = s is None
        if new:
            s = InternshipFinalScore(tenant_id=_tid(), internship_id=rec.id, student_id=rec.student_id,
                                     batch_id=rec.batch_id)
            db.add(s)
        for col, v in comps.items():
            setattr(s, col, v)
        for wk, wv in w.items():
            setattr(s, wk, wv)
        s.total_score = total
        s.score_config_id = cfg.id if cfg else None
        s.score_config_version = int(cfg.version or 0) if cfg else 0
        s.pass_line = pass_line
        s.is_pass = bool(total is not None and total >= pass_line)
        s.incomplete = incomplete
        s.incomplete_reason = ("缺：" + "、".join(missing)) if missing else None
        s.status = "PENDING_REVIEW"
        s.version = (s.version or 0) + 1
        db.flush()
        _trail(db, s.id, "COMPUTE", {"total": total, "incomplete": incomplete, "missing": missing,
               "scoreConfigId": str(cfg.id) if cfg else "", "scoreConfigVersion": int(cfg.version or 0) if cfg else 0},
               operator=_op_name(user))
        db.commit()
        return {"id": str(s.id), "total": total, "incomplete": incomplete,
                "incompleteReason": s.incomplete_reason, "isPass": s.is_pass}


def publish(user, sid) -> dict:
    scope, in_scope = _scope_ctx(user)
    with session() as db:
        s = _get(db, sid)
        rec, stu = _ctx(db, s)
        if not in_scope(scope, db, rec, stu):
            raise no_permission("只能发布本人数据范围内的成绩")
        if s.status != "PENDING_REVIEW":
            raise AppException("DATA_CONFLICT", "仅待复核成绩可发布")
        if s.incomplete:
            raise AppException("DATA_CONFLICT", f"成绩缺项不可发布（{s.incomplete_reason}）")
        s.status = "PUBLISHED"
        s.reviewed_by_name = _op_name(user)
        s.reviewed_at = datetime.utcnow()
        s.published_by_name = _op_name(user)
        s.published_at = datetime.utcnow()
        s.version = (s.version or 0) + 1
        _trail(db, s.id, "PUBLISH", {"total": s.total_score, "isPass": s.is_pass}, operator=_op_name(user))
        db.commit()
        return {"id": str(s.id), "status": s.status, "statusLabel": STATUS_LABEL[s.status]}


def return_recalc(user, sid, reason="") -> dict:
    with session() as db:
        s = _get(db, sid)
        rec, stu = _ctx(db, s)
        scope, in_scope = _scope_ctx(user)
        if not in_scope(scope, db, rec, stu):
            raise no_permission("只能退回本人数据范围内的成绩")
        if s.status != "PENDING_REVIEW":
            raise AppException("DATA_CONFLICT", "仅待复核成绩可退回重算")
        s.status = "PENDING_CALC"
        s.version = (s.version or 0) + 1
        _trail(db, s.id, "RETURN_RECALC", {"reason": (reason or "").strip()}, operator=_op_name(user))
        db.commit()
        return {"id": str(s.id), "status": s.status}


def withdraw(user, sid, reason="") -> dict:
    if not (reason or "").strip() or len(reason.strip()) < 5:
        raise AppException("VALIDATION_ERROR", "撤回原因必填且不少于 5 字")
    with session() as db:
        s = _get(db, sid)
        rec, stu = _ctx(db, s)
        scope, in_scope = _scope_ctx(user)
        if not in_scope(scope, db, rec, stu):
            raise no_permission("只能撤回本人数据范围内的成绩")
        if s.status != "PUBLISHED":
            raise AppException("DATA_CONFLICT", "仅已发布成绩可撤回")
        s.status = "WITHDRAWN"
        s.version = (s.version or 0) + 1
        _trail(db, s.id, "WITHDRAW", {"reason": reason.strip()}, operator=_op_name(user))
        db.commit()
        return {"id": str(s.id), "status": s.status}


def archive(user, sid) -> dict:
    with session() as db:
        s = _get(db, sid)
        rec, stu = _ctx(db, s)
        scope, in_scope = _scope_ctx(user)
        if not in_scope(scope, db, rec, stu):
            raise no_permission("只能归档本人数据范围内的成绩")
        if s.status != "PUBLISHED":
            raise AppException("DATA_CONFLICT", "仅已发布成绩可归档")
        s.status = "ARCHIVED"
        s.version = (s.version or 0) + 1
        _trail(db, s.id, "ARCHIVE", {}, operator=_op_name(user))
        db.commit()
        return {"id": str(s.id), "status": s.status}


def _row(s, rec, stu):
    return {
        "id": str(s.id), "internId": str(s.internship_id),
        "studentName": stu.real_name if stu else "-", "studentNo": stu.student_no if stu else "-",
        "advisorName": rec.advisor_name if rec else "",
        "checkinScore": s.checkin_score, "weeklyScore": s.weekly_score, "monthlyScore": s.monthly_score,
        "enterpriseScore": s.enterprise_score, "schoolScore": s.school_score,
        "totalScore": s.total_score, "passLine": s.pass_line, "isPass": bool(s.is_pass),
        "scoreConfigId": str(s.score_config_id) if s.score_config_id else "",
        "scoreConfigVersion": int(s.score_config_version or 0),
        "incomplete": bool(s.incomplete), "incompleteReason": s.incomplete_reason or "",
        "status": s.status, "statusLabel": STATUS_LABEL.get(s.status, s.status),
        "createdAt": _iso(s.created_at) or "",
    }


def list_scores(page, page_size, status=None, keyword=None, user=None):
    scope, in_scope = _scope_ctx(user)
    with session() as db:
        q = select(InternshipFinalScore).where(InternshipFinalScore.tenant_id == _tid(),
                                               InternshipFinalScore.is_deleted.is_(False))
        if status:
            q = q.where(InternshipFinalScore.status == status)
        rows = db.scalars(q.order_by(InternshipFinalScore.id.desc())).all()
        items = []
        for s in rows:
            rec, stu = _ctx(db, s)
            if keyword and (not stu or keyword.strip() not in (stu.real_name or "")):
                continue
            if not in_scope(scope, db, rec, stu):
                continue
            items.append(_row(s, rec, stu))
        total = len(items)
        start = (max(1, page) - 1) * page_size
        return items[start:start + page_size], total


def get_score(sid, user=None) -> dict:
    scope, in_scope = _scope_ctx(user)
    with session() as db:
        s = _get(db, sid)
        rec, stu = _ctx(db, s)
        if not in_scope(scope, db, rec, stu):
            raise no_permission("该成绩不在你的数据范围内")
        trail = db.scalars(select(InternshipAuditTrail).where(
            InternshipAuditTrail.tenant_id == _tid(), InternshipAuditTrail.target_type == "SCORE",
            InternshipAuditTrail.target_id == s.id).order_by(InternshipAuditTrail.id)).all()
        return {**_row(s, rec, stu),
                "weights": {"checkin": s.w_checkin, "weekly": s.w_weekly, "monthly": s.w_monthly,
                            "enterprise": s.w_enterprise, "school": s.w_school},
                "auditTrail": [{"action": t.action, "operator": t.operator_name or "",
                                "detail": t.detail_json or {}, "occurredAt": _iso(t.occurred_at)}
                               for t in trail]}


def export_scores(status=None, keyword=None, user=None) -> dict:
    from app.services import xlsx_util
    items, _ = list_scores(1, 100000, status=status, keyword=keyword, user=user)
    headers = ["学号", "姓名", "指导教师", "打卡", "周报", "月报总结", "企业评价", "学校评价",
               "总分", "及格线", "是否及格", "缺项", "状态"]
    rows = [[it["studentNo"], it["studentName"], it["advisorName"], it["checkinScore"], it["weeklyScore"],
             it["monthlyScore"], it["enterpriseScore"], it["schoolScore"], it["totalScore"], it["passLine"],
             "是" if it["isPass"] else "否", it["incompleteReason"] or "无", it["statusLabel"]]
            for it in items]
    wm = f"岗位实习中心·实习成绩台账 · 导出人：{_op_name(user)} · {datetime.now():%Y-%m-%d %H:%M} · 导出留痕"
    content = xlsx_util.build_ledger_xlsx("实习成绩台账", headers, rows, watermark=wm)
    return xlsx_util.pack_xlsx_result(content, "实习成绩台账.xlsx", len(items))
