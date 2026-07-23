"""毕业设计中心 · 成绩评定服务。

三段成绩（导师分/评阅分/答辩分）按批次规则权重核算综合分 → 复核 → 发布 → 撤回（留痕）。
权重取该生所在批次 rules_config.score，缺省沿用 graduation_batch_service.DEFAULT_RULES 权重 0.4/0.3/0.3。

隔离说明：不引用实习/迎新域文件。
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone

from sqlalchemy import func, select

from app.core.context import get_current_user_ctx
from app.core.exceptions import AppException, not_found
from app.models import (GraduationAuditTrail, GraduationBatch, GraduationDefenseScore,
                        GraduationFinal, GraduationGrade, GraduationReview, GraduationStudent)
from app.services.db_service import _iso, _tid, session
from app.modules.graduation.services.graduation_scope_service import accessible_student_ids, assert_student_access

STATUS_LABEL = {"DRAFT": "待核算", "CALCULATED": "已核算", "PUBLISHED": "已发布", "WITHDRAWN": "已撤回待重发"}
STATUS_TONE = {"DRAFT": "default", "CALCULATED": "warning", "PUBLISHED": "success", "WITHDRAWN": "danger"}
DEFAULT_WEIGHTS = {"advisorWeight": 0.4, "reviewerWeight": 0.3, "defenseWeight": 0.3}


def _op() -> tuple[str, str]:
    u = get_current_user_ctx() or {}
    return u.get("realName") or "系统", u.get("roleName") or u.get("currentRoleCode") or ""


def _audit(db, bid, action, detail="", before="", after=""):
    n, r = _op()
    db.add(GraduationAuditTrail(tenant_id=_tid(), biz_type="GRADE", biz_id=str(bid), action=action,
                                operator=n, role_name=r, detail=detail, before_val=before, after_val=after,
                                occurred_at=datetime.now(timezone.utc)))


def _stu(db, sid) -> GraduationStudent:
    s = db.get(GraduationStudent, int(sid))
    if not s or s.is_deleted or s.tenant_id != _tid():
        raise not_found("毕设学生不存在或不在当前数据范围内")
    return assert_student_access(db, s, "grade")


def _stu_for_update(db, sid) -> GraduationStudent:
    s = db.scalars(select(GraduationStudent).where(
        GraduationStudent.id == int(sid), GraduationStudent.tenant_id == _tid(),
        GraduationStudent.is_deleted.is_(False),
    ).with_for_update()).first()
    if not s:
        raise not_found("Graduation student does not exist in the current scope")
    return assert_student_access(db, s, "grade.write")


def _weights(db, stu: GraduationStudent) -> dict:
    if stu.batch_id:
        b = db.get(GraduationBatch, stu.batch_id)
        if b and b.rules_config and b.rules_config.get("score"):
            return {**DEFAULT_WEIGHTS, **b.rules_config["score"]}
    return DEFAULT_WEIGHTS


def _grade_level(total: int | None) -> str | None:
    if total is None:
        return None
    if total >= 90:
        return "优秀"
    if total >= 80:
        return "良好"
    if total >= 70:
        return "中等"
    if total >= 60:
        return "及格"
    return "不及格"


def _source_scores(db, stu: GraduationStudent) -> dict:
    final = db.scalars(select(GraduationFinal).where(
        GraduationFinal.tenant_id == _tid(),
        GraduationFinal.gd_student_id == stu.id,
        GraduationFinal.final_type == "定稿",
        GraduationFinal.status == "APPROVED",
        GraduationFinal.is_deleted.is_(False),
    ).order_by(GraduationFinal.id.desc())).first()
    review_rows = db.scalars(select(GraduationReview).where(
        GraduationReview.tenant_id == _tid(),
        GraduationReview.gd_student_id == stu.id,
        GraduationReview.gd_final_id == (final.id if final else -1),
        GraduationReview.status == "COMPLETED",
        GraduationReview.score.is_not(None),
        GraduationReview.is_deleted.is_(False),
    ).order_by(GraduationReview.id)).all()
    review_scores = [row.score for row in review_rows]
    defense_round = db.scalar(select(func.max(GraduationDefenseScore.round_no)).where(
        GraduationDefenseScore.tenant_id == _tid(),
        GraduationDefenseScore.gd_student_id == stu.id,
        GraduationDefenseScore.status == "CONFIRMED",
        GraduationDefenseScore.is_deleted.is_(False),
    ))
    defense_rows = db.scalars(select(GraduationDefenseScore).where(
        GraduationDefenseScore.tenant_id == _tid(),
        GraduationDefenseScore.gd_student_id == stu.id,
        GraduationDefenseScore.round_no == defense_round,
        GraduationDefenseScore.status == "CONFIRMED",
        GraduationDefenseScore.absent.is_(False),
        GraduationDefenseScore.score.is_not(None),
        GraduationDefenseScore.is_deleted.is_(False),
    ).order_by(GraduationDefenseScore.id)).all() if defense_round else []
    defense_scores = [row.score for row in defense_rows]
    payload = {
        "studentId": int(stu.id),
        "finalId": int(final.id) if final else None,
        "reviews": [{"id": int(row.id), "score": int(row.score)} for row in review_rows],
        "defenseRound": int(defense_round) if defense_round else None,
        "defenseScores": [{"id": int(row.id), "score": int(row.score)} for row in defense_rows],
    }
    source_hash = hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return {
        "reviewerScore": round(sum(review_scores) / len(review_scores)) if review_scores else None,
        "finalId": str(final.id) if final else "",
        "reviewSourceCount": len(review_scores),
        "defenseScore": round(sum(defense_scores) / len(defense_scores)) if defense_scores else None,
        "defenseSourceCount": len(defense_scores),
        "defenseRound": defense_round,
        "sourceSnapshotHash": source_hash,
    }


def _get_or_create(db, stu: GraduationStudent, *, for_update: bool = False) -> GraduationGrade:
    query = select(GraduationGrade).where(
        GraduationGrade.tenant_id == _tid(),
        GraduationGrade.gd_student_id == stu.id,
        GraduationGrade.is_deleted.is_(False),
    )
    if for_update:
        query = query.with_for_update()
    g = db.scalars(query).first()
    if not g:
        g = GraduationGrade(tenant_id=_tid(), gd_student_id=stu.id, status="DRAFT")
        db.add(g)
        db.flush()
    return g


def _row(g: GraduationGrade, stu=None) -> dict:
    return {"id": str(g.id), "gdStudentId": str(g.gd_student_id),
            "studentName": stu.name if stu else "", "studentNo": stu.student_no if stu else "",
            "advisorScore": g.advisor_score, "reviewerScore": g.reviewer_score,
            "defenseScore": g.defense_score, "totalScore": g.total_score, "gradeLevel": g.grade_level or "",
            "status": g.status, "statusLabel": STATUS_LABEL.get(g.status, g.status),
            "statusTone": STATUS_TONE.get(g.status, "default"), "remark": g.remark or "",
            "calculatedAt": _iso(g.calculated_at), "reviewedBy": g.reviewed_by or "",
            "reviewedAt": _iso(g.reviewed_at), "publishedBy": g.published_by or "",
            "publishedAt": _iso(g.published_at), "withdrawReason": g.withdraw_reason or "",
            "sourceSnapshotHash": g.source_snapshot_hash or "",
            "updatedAt": _iso(g.updated_at), "version": g.version}


def list_grades(page: int, page_size: int, keyword=None, status=None) -> tuple[list[dict], int]:
    with session() as db:
        scope_ids = accessible_student_ids(db, _tid())
        q = select(GraduationGrade).where(GraduationGrade.tenant_id == _tid(),
                                           GraduationGrade.is_deleted.is_(False),
                                           GraduationGrade.gd_student_id.in_(scope_ids or [-1]))
        if status:
            q = q.where(GraduationGrade.status == status)
        rows = db.scalars(q.order_by(GraduationGrade.id.desc())).all()
        items = []
        for g in rows:
            stu = db.get(GraduationStudent, g.gd_student_id)
            if keyword and (not stu or keyword.strip() not in (stu.name or "")):
                continue
            items.append(_row(g, stu))
        total = len(items)
        start = (max(1, page) - 1) * page_size
        return items[start:start + page_size], total


def get_grade(gd_student_id) -> dict:
    with session() as db:
        stu = _stu(db, gd_student_id)
        g = _get_or_create(db, stu)
        db.commit()
        return {**_row(g, stu), "sourceScores": _source_scores(db, stu)}


def calculate_grade(gd_student_id, advisor_score=None, reviewer_score=None, defense_score=None) -> dict:
    with session() as db:
        stu = _stu_for_update(db, gd_student_id)
        g = _get_or_create(db, stu, for_update=True)
        if g.status == "PUBLISHED":
            raise AppException("DATA_CONFLICT", "已发布成绩不可直接核算，请先撤回")
        sources = _source_scores(db, stu)
        if sources["reviewerScore"] is None or sources["defenseScore"] is None:
            raise AppException("DATA_CONFLICT", "Review and confirmed defense scores must exist before calculation")
        authoritative_reviewer = sources["reviewerScore"]
        authoritative_defense = sources["defenseScore"]
        if reviewer_score is not None and reviewer_score != authoritative_reviewer:
            raise AppException("DATA_CONFLICT", "Reviewer score differs from completed review records")
        if defense_score is not None and defense_score != authoritative_defense:
            raise AppException("DATA_CONFLICT", "Defense score differs from confirmed defense records")
        if advisor_score is not None:
            g.advisor_score = advisor_score
        g.reviewer_score = authoritative_reviewer
        g.defense_score = authoritative_defense
        if g.advisor_score is None or g.defense_score is None:
            raise AppException("VALIDATION_ERROR", "导师分与答辩分为必需项，评阅分缺失时按 0 计")
        w = _weights(db, stu)
        reviewer = g.reviewer_score if g.reviewer_score is not None else 0
        total = round(g.advisor_score * w["advisorWeight"] + reviewer * w["reviewerWeight"]
                     + g.defense_score * w["defenseWeight"])
        g.total_score = total
        g.grade_level = _grade_level(total)
        g.status = "CALCULATED"
        g.calculated_at = datetime.now(timezone.utc)
        g.reviewed_by = None
        g.reviewed_at = None
        g.source_snapshot_hash = sources["sourceSnapshotHash"]
        g.version += 1
        _audit(db, g.id, "核算成绩", detail=(
            f"total={total};reviewSources={sources['reviewSourceCount']};"
            f"defenseRound={sources['defenseRound']};defenseSources={sources['defenseSourceCount']}"
        ))
        db.commit()
        return _row(g, stu)


def review_grade(gd_student_id, action: str, comment: str = None) -> dict:
    if action not in ("APPROVE", "RETURN"):
        raise AppException("VALIDATION_ERROR", "action 必须是 APPROVE/RETURN")
    with session() as db:
        stu = _stu_for_update(db, gd_student_id)
        g = _get_or_create(db, stu, for_update=True)
        if action == "APPROVE" and g.status == "CALCULATED" and g.reviewed_at:
            return _row(g, stu)
        if g.status != "CALCULATED":
            raise AppException("DATA_CONFLICT", "仅「已核算」成绩可复核")
        n, _ = _op()
        if action == "APPROVE":
            g.reviewed_by = n
            g.reviewed_at = datetime.now(timezone.utc)
            g.remark = comment
            _audit(db, g.id, "复核通过", comment or "")
        else:
            if not comment or len(comment.strip()) < 5:
                raise AppException("VALIDATION_ERROR", "复核退回原因必填且不少于 5 字")
            g.status = "DRAFT"
            g.remark = comment
            _audit(db, g.id, "复核退回", comment.strip())
        g.version += 1
        db.commit()
        return _row(g, stu)


def publish_grade(gd_student_id) -> dict:
    with session() as db:
        stu = _stu_for_update(db, gd_student_id)
        g = _get_or_create(db, stu, for_update=True)
        if g.status == "PUBLISHED":
            return _row(g, stu)
        if g.status != "CALCULATED" or not g.reviewed_at:
            raise AppException("DATA_CONFLICT", "仅「复核通过」成绩可发布")
        current_sources = _source_scores(db, stu)
        if not g.source_snapshot_hash or g.source_snapshot_hash != current_sources["sourceSnapshotHash"]:
            raise AppException("APPROVAL_VERSION_CONFLICT", "Authoritative scores changed; recalculate before publishing")
        n, _ = _op()
        g.status = "PUBLISHED"
        g.published_by = n
        g.published_at = datetime.now(timezone.utc)
        g.version += 1
        if stu.stage == "DEFENSE":
            stu.stage = "COMPLETED"
        _audit(db, g.id, "发布成绩", detail=f"total={g.total_score}")
        db.commit()
        return _row(g, stu)


def withdraw_grade(gd_student_id, reason: str) -> dict:
    if not reason or len(reason.strip()) < 5:
        raise AppException("VALIDATION_ERROR", "撤回原因必填且不少于 5 字")
    with session() as db:
        stu = _stu_for_update(db, gd_student_id)
        g = _get_or_create(db, stu, for_update=True)
        if g.status == "WITHDRAWN" and g.withdraw_reason == reason.strip():
            return _row(g, stu)
        if g.status != "PUBLISHED":
            raise AppException("DATA_CONFLICT", "仅「已发布」成绩可撤回")
        g.status = "WITHDRAWN"
        g.withdraw_reason = reason.strip()
        g.reviewed_at = None
        g.version += 1
        if stu.stage == "COMPLETED":
            stu.stage = "DEFENSE"
        _audit(db, g.id, "撤回成绩", reason.strip())
        db.commit()
        return _row(g, stu)


def grade_stats() -> dict:
    with session() as db:
        scope_ids = accessible_student_ids(db, _tid())
        base = [GraduationGrade.tenant_id == _tid(), GraduationGrade.is_deleted.is_(False),
                GraduationGrade.gd_student_id.in_(scope_ids or [-1])]
        total = int(db.scalar(select(func.count()).select_from(GraduationGrade).where(*base)) or 0)
        by_status = [{"status": s, "label": STATUS_LABEL[s],
                      "count": int(db.scalar(select(func.count()).select_from(GraduationGrade).where(
                          *base, GraduationGrade.status == s)) or 0)} for s in STATUS_LABEL]
        published = db.scalars(select(GraduationGrade).where(*base, GraduationGrade.status == "PUBLISHED")).all()
        avg = round(sum(g.total_score for g in published) / len(published), 1) if published else 0
        excellent = sum(1 for g in published if g.grade_level == "优秀")
        return {"total": total, "byStatus": by_status, "publishedAvg": avg, "excellentCount": excellent}
