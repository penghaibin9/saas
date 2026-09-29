"""毕业设计中心 · Batch 7/8 新增业务：成果互查整改 / 答辩专家库 / 成绩更正申诉。
隔离说明：仅依赖毕设域模型与公共 db_service。
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func, or_, select

from app.core.context import get_current_user_ctx
from app.core.exceptions import AppException, not_found
from app.models import (GraduationAuditTrail, GraduationDefenseExpert, GraduationGrade,
                        GraduationGradeAppeal, GraduationPeerReview, GraduationStudent)
from app.services.db_service import _iso, _tid, session
from app.modules.graduation.services.graduation_scope_service import accessible_student_ids, assert_student_access


def _op():
    u = get_current_user_ctx() or {}
    return u.get("realName") or "系统", u.get("currentRoleCode") or ""


def _audit(db, bt, bid, action, detail=""):
    n, r = _op()
    db.add(GraduationAuditTrail(tenant_id=_tid(), biz_type=bt, biz_id=str(bid), action=action,
                                operator=n, role_name=r, detail=detail, occurred_at=datetime.now(timezone.utc)))


def _stu(db, sid) -> GraduationStudent:
    s = db.get(GraduationStudent, int(sid))
    if not s or s.is_deleted or s.tenant_id != _tid():
        raise not_found("毕设学生不存在")
    return assert_student_access(db, s, "graduation.more")


# ═══════════ 成果互查整改（互评） ═══════════

PEER_LABEL = {"ASSIGNED": "待互查", "REVIEWED": "已互查", "RECTIFIED": "已整改"}


def list_peer(gd_student_id=None, status=None) -> list:
    with session() as db:
        scope_ids = accessible_student_ids(db, _tid())
        q = select(GraduationPeerReview).where(GraduationPeerReview.tenant_id == _tid(),
                                              GraduationPeerReview.is_deleted.is_(False),
                                              or_(GraduationPeerReview.gd_student_id.in_(scope_ids or [-1]),
                                                  GraduationPeerReview.reviewer_gd_student_id.in_(scope_ids or [-1])))
        if gd_student_id:
            q = q.where(GraduationPeerReview.gd_student_id == int(gd_student_id))
        if status:
            q = q.where(GraduationPeerReview.status == status)
        return [_peer_row(db, p) for p in db.scalars(q.order_by(GraduationPeerReview.id.desc())).all()]


def peer_stats(batch_id=None) -> dict:
    with session() as db:
        scope_ids = accessible_student_ids(db, _tid(), batch_id=batch_id)
        base = [GraduationPeerReview.tenant_id == _tid(), GraduationPeerReview.is_deleted.is_(False),
                or_(GraduationPeerReview.gd_student_id.in_(scope_ids or [-1]),
                    GraduationPeerReview.reviewer_gd_student_id.in_(scope_ids or [-1]))]
        total = int(db.scalar(select(func.count()).select_from(GraduationPeerReview).where(*base)) or 0)
        by_status = [{"status": s, "label": PEER_LABEL[s],
                     "count": int(db.scalar(select(func.count()).select_from(GraduationPeerReview).where(
                         *base, GraduationPeerReview.status == s)) or 0)} for s in PEER_LABEL]
        return {"total": total, "byStatus": by_status,
                "batchId": str(batch_id) if batch_id else None}


# ═══════════ 答辩专家库 ═══════════

def _expert_row(e: GraduationDefenseExpert) -> dict:
    return {"id": str(e.id), "expertName": e.expert_name, "title": e.title or "",
            "collegeName": e.college_name or "", "isExternal": e.is_external,
            "avoidNote": e.avoid_note or "", "status": e.status,
            "statusLabel": "启用" if e.status == "ACTIVE" else "停用", "updatedAt": _iso(e.updated_at)}


def create_expert(name, title=None, college=None, is_external=False, avoid_note=None) -> dict:
    if not (name and name.strip()):
        raise AppException("VALIDATION_ERROR", "专家姓名不能为空")
    with session() as db:
        e = GraduationDefenseExpert(tenant_id=_tid(), expert_name=name.strip(),
                                   title=(title or "").strip() or None,
                                   college_name=(college or "").strip() or None,
                                   is_external=bool(is_external),
                                   avoid_note=(avoid_note or "").strip() or None, status="ACTIVE")
        db.add(e)
        db.flush()
        _audit(db, "DEFENSE_EXPERT", e.id, "新增答辩专家", e.expert_name)
        db.commit()
        return _expert_row(e)


def list_experts(status=None, keyword=None) -> list:
    with session() as db:
        q = select(GraduationDefenseExpert).where(GraduationDefenseExpert.tenant_id == _tid(),
                                                 GraduationDefenseExpert.is_deleted.is_(False))
        if status:
            q = q.where(GraduationDefenseExpert.status == status)
        rows = db.scalars(q.order_by(GraduationDefenseExpert.id.desc())).all()
        items = [_expert_row(e) for e in rows]
        if keyword:
            items = [i for i in items if keyword.strip() in i["expertName"]]
        return items


def set_expert_status(eid, action) -> dict:
    if action not in ("ENABLE", "DISABLE"):
        raise AppException("VALIDATION_ERROR", "action 必须是 ENABLE 或 DISABLE")
    with session() as db:
        e = db.get(GraduationDefenseExpert, int(eid))
        if not e or e.is_deleted or e.tenant_id != _tid():
            raise not_found("专家不存在")
        e.status = {"DISABLE": "DISABLED", "ENABLE": "ACTIVE"}[action]
        _audit(db, "DEFENSE_EXPERT", e.id, "停用专家" if action == "DISABLE" else "启用专家")
        db.commit()
        return _expert_row(e)


# ═══════════ 成绩更正申诉 ═══════════

APPEAL_LABEL = {"PENDING": "待复核", "APPROVED": "已受理", "REJECTED": "已驳回"}


def _appeal_row(db, a: GraduationGradeAppeal) -> dict:
    s = db.get(GraduationStudent, a.gd_student_id)
    return {"id": str(a.id), "gdStudentId": str(a.gd_student_id), "studentName": s.name if s else "",
            "reason": a.reason, "status": a.status, "statusLabel": APPEAL_LABEL.get(a.status, a.status),
            "reviewComment": a.review_comment or "", "reviewedBy": a.reviewed_by or "",
            "reviewedAt": _iso(a.reviewed_at), "createdAt": _iso(a.created_at)}


def create_appeal(gd_student_id, reason) -> dict:
    """学生对已发布成绩申诉。须成绩已发布；同一学生同时只能有一条待复核申诉。"""
    if not reason or len(reason.strip()) < 5:
        raise AppException("VALIDATION_ERROR", "申诉理由必填且不少于 5 字")
    with session() as db:
        s = db.scalars(select(GraduationStudent).where(
            GraduationStudent.id == int(gd_student_id),
            GraduationStudent.tenant_id == _tid(),
            GraduationStudent.is_deleted.is_(False),
        ).with_for_update()).first()
        if not s:
            raise not_found("毕设学生不存在")
        grade = db.scalars(select(GraduationGrade).where(
            GraduationGrade.tenant_id == _tid(), GraduationGrade.gd_student_id == s.id,
            GraduationGrade.is_deleted.is_(False)).with_for_update()).first()
        if not grade or grade.status != "PUBLISHED":
            raise AppException("DATA_CONFLICT", "成绩未发布，暂不可申诉")
        pending = db.scalar(select(func.count()).select_from(GraduationGradeAppeal).where(
            GraduationGradeAppeal.tenant_id == _tid(), GraduationGradeAppeal.gd_student_id == s.id,
            GraduationGradeAppeal.status == "PENDING",
            GraduationGradeAppeal.is_deleted.is_(False))) or 0
        if pending:
            raise AppException("DATA_CONFLICT", "已有待复核的申诉，请等待处理")
        a = GraduationGradeAppeal(tenant_id=_tid(), gd_student_id=s.id, reason=reason.strip(),
                                  status="PENDING", active_key=f"pending:{s.id}")
        db.add(a)
        db.flush()
        _audit(db, "GRADE_APPEAL", a.id, "提交成绩申诉", s.name)
        db.commit()
        return _appeal_row(db, a)
def list_appeals(status=None) -> list:
    with session() as db:
        scope_ids = accessible_student_ids(db, _tid())
        q = select(GraduationGradeAppeal).where(GraduationGradeAppeal.tenant_id == _tid(),
                                               GraduationGradeAppeal.is_deleted.is_(False),
                                               GraduationGradeAppeal.gd_student_id.in_(scope_ids or [-1]))
        if status:
            q = q.where(GraduationGradeAppeal.status == status)
        return [_appeal_row(db, a) for a in db.scalars(q.order_by(GraduationGradeAppeal.id.desc())).all()]


from app.modules.graduation.services.graduation_grade_appeal_consistency import review_appeal
from app.modules.graduation.services.graduation_peer_consistency import (
    assign_peer,
    peer_row as _peer_row,
    rectify_peer,
    submit_peer,
)
