"""毕业设计中心 · 查重记录 + 教师评阅服务。

查重：对齐老系统 t_gd_plagiarism 检测中/完成/失败语义 + 复查申请闭环。
教师评阅：独立评阅角色，SoD——评阅人不得是该生指导教师（对齐 CLAUDE.md §权限矩阵 SoD 冻结）。

隔离说明：不引用实习/迎新域文件。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select

from app.core.context import get_current_user_ctx
from app.core.exceptions import AppException, not_found
from app.models import GraduationAuditTrail, GraduationPlagiarismCheck, GraduationReview, GraduationStudent
from app.services.db_service import _iso, _tid, session
from app.services.graduation_scope_service import accessible_student_ids, assert_student_access

PLAG_STATUS_LABEL = {"CHECKING": "检测中", "DONE": "已完成", "FAILED": "失败"}
REVIEW_STATUS_LABEL = {"ASSIGNED": "待评阅", "REVIEWING": "评阅中", "COMPLETED": "已完成", "RETURNED": "已退回"}
REVIEW_STATUS_TONE = {"ASSIGNED": "warning", "REVIEWING": "warning", "COMPLETED": "success", "RETURNED": "danger"}


def _op() -> tuple[str, str]:
    u = get_current_user_ctx() or {}
    return u.get("realName") or "系统", u.get("roleName") or u.get("currentRoleCode") or ""


def _audit(db, biz_type, bid, action, detail="", before="", after=""):
    n, r = _op()
    db.add(GraduationAuditTrail(tenant_id=_tid(), biz_type=biz_type, biz_id=str(bid), action=action,
                                operator=n, role_name=r, detail=detail, before_val=before, after_val=after,
                                occurred_at=datetime.utcnow()))


def _stu(db, sid) -> GraduationStudent:
    s = db.get(GraduationStudent, int(sid))
    if not s or s.is_deleted or s.tenant_id != _tid():
        raise not_found("毕设学生不存在或不在当前数据范围内")
    return assert_student_access(db, s, "review")


# ═══════════ 查重记录 ═══════════

def _plag_row(p: GraduationPlagiarismCheck, stu=None) -> dict:
    return {"id": str(p.id), "gdStudentId": str(p.gd_student_id), "gdFinalId": str(p.gd_final_id or ""),
            "studentName": stu.name if stu else "", "studentNo": stu.student_no if stu else "",
            "submitAt": _iso(p.submit_at), "status": p.status,
            "statusLabel": PLAG_STATUS_LABEL.get(p.status, p.status),
            "rate": p.rate or "", "reportUrl": p.report_url or "", "threshold": p.threshold,
            "overThreshold": p.over_threshold, "disputeReason": p.dispute_reason or "",
            "disputeStatus": p.dispute_status or "", "disputeComment": p.dispute_comment or "",
            "updatedAt": _iso(p.updated_at)}


def list_plagiarism(page: int, page_size: int, gd_student_id=None, status=None) -> tuple[list[dict], int]:
    with session() as db:
        scope_ids = accessible_student_ids(db, _tid())
        q = select(GraduationPlagiarismCheck).where(GraduationPlagiarismCheck.tenant_id == _tid(),
                                                     GraduationPlagiarismCheck.is_deleted.is_(False),
                                                     GraduationPlagiarismCheck.gd_student_id.in_(scope_ids or [-1]))
        if gd_student_id:
            q = q.where(GraduationPlagiarismCheck.gd_student_id == int(gd_student_id))
        if status:
            q = q.where(GraduationPlagiarismCheck.status == status)
        total = int(db.scalar(select(func.count()).select_from(q.subquery())) or 0)
        rows = db.scalars(q.order_by(GraduationPlagiarismCheck.id.desc())
                          .offset((max(1, page) - 1) * page_size).limit(page_size)).all()
        items = [_plag_row(p, db.get(GraduationStudent, p.gd_student_id)) for p in rows]
        return items, total


def submit_plagiarism(gd_student_id, gd_final_id=None, threshold: int = 30) -> dict:
    with session() as db:
        stu = _stu(db, gd_student_id)
        p = GraduationPlagiarismCheck(tenant_id=_tid(), gd_student_id=stu.id,
                                      gd_final_id=int(gd_final_id) if gd_final_id else None,
                                      submit_at=datetime.utcnow(), status="CHECKING", threshold=threshold)
        db.add(p)
        db.flush()
        _audit(db, "PLAGIARISM", p.id, "发起查重")
        db.commit()
        return _plag_row(p, stu)


def set_plagiarism_result(pid, rate: str, report_url: str = None) -> dict:
    with session() as db:
        p = db.get(GraduationPlagiarismCheck, int(pid))
        if not p or p.is_deleted or p.tenant_id != _tid():
            raise not_found("查重记录不存在")
        assert_student_access(db, db.get(GraduationStudent, p.gd_student_id), "plagiarism.result")
        if p.status != "CHECKING":
            raise AppException("DATA_CONFLICT", "仅「检测中」记录可回填结果")
        try:
            rate_val = float(str(rate).replace("%", ""))
        except ValueError:
            raise AppException("VALIDATION_ERROR", "重复率格式错误")
        p.rate = f"{rate_val}%"
        p.report_url = report_url
        p.status = "DONE"
        p.over_threshold = rate_val > p.threshold
        _audit(db, "PLAGIARISM", p.id, "查重结果回填", detail=p.rate)
        db.commit()
        return _plag_row(p, db.get(GraduationStudent, p.gd_student_id))


def dispute_plagiarism(pid, reason: str) -> dict:
    if not reason or len(reason.strip()) < 5:
        raise AppException("VALIDATION_ERROR", "复查理由必填且不少于 5 字")
    with session() as db:
        p = db.get(GraduationPlagiarismCheck, int(pid))
        if not p or p.is_deleted or p.tenant_id != _tid():
            raise not_found("查重记录不存在")
        assert_student_access(db, db.get(GraduationStudent, p.gd_student_id), "plagiarism.dispute")
        if p.status != "DONE" or not p.over_threshold:
            raise AppException("DATA_CONFLICT", "仅超标记录可申请复查")
        p.dispute_reason = reason.strip()
        p.dispute_status = "PENDING"
        _audit(db, "PLAGIARISM", p.id, "申请复查", reason.strip())
        db.commit()
        return _plag_row(p, db.get(GraduationStudent, p.gd_student_id))


def review_dispute(pid, action: str, comment: str = None) -> dict:
    if action not in ("APPROVE", "REJECT"):
        raise AppException("VALIDATION_ERROR", "action 必须是 APPROVE/REJECT")
    with session() as db:
        p = db.get(GraduationPlagiarismCheck, int(pid))
        if not p or p.is_deleted or p.tenant_id != _tid():
            raise not_found("查重记录不存在")
        assert_student_access(db, db.get(GraduationStudent, p.gd_student_id), "plagiarism.dispute.review")
        if p.dispute_status != "PENDING":
            raise AppException("DATA_CONFLICT", "无待处理的复查申请")
        p.dispute_status = "APPROVED" if action == "APPROVE" else "REJECTED"
        p.dispute_comment = (comment or "").strip()
        if action == "APPROVE":
            p.over_threshold = False
        _audit(db, "PLAGIARISM", p.id, "复查审核-" + ("通过" if action == "APPROVE" else "驳回"),
               (comment or "").strip())
        db.commit()
        return _plag_row(p, db.get(GraduationStudent, p.gd_student_id))


def plagiarism_stats() -> dict:
    with session() as db:
        scope_ids = accessible_student_ids(db, _tid())
        base = [GraduationPlagiarismCheck.tenant_id == _tid(), GraduationPlagiarismCheck.is_deleted.is_(False),
                GraduationPlagiarismCheck.gd_student_id.in_(scope_ids or [-1])]
        total = int(db.scalar(select(func.count()).select_from(GraduationPlagiarismCheck).where(*base)) or 0)
        over = int(db.scalar(select(func.count()).select_from(GraduationPlagiarismCheck).where(
            *base, GraduationPlagiarismCheck.over_threshold.is_(True))) or 0)
        checking = int(db.scalar(select(func.count()).select_from(GraduationPlagiarismCheck).where(
            *base, GraduationPlagiarismCheck.status == "CHECKING")) or 0)
        return {"total": total, "overThresholdCount": over, "checkingCount": checking}


# ═══════════ 教师评阅 ═══════════

def _review_row(r: GraduationReview, stu=None) -> dict:
    return {"id": str(r.id), "gdStudentId": str(r.gd_student_id), "gdFinalId": str(r.gd_final_id or ""),
            "studentName": stu.name if stu else "", "studentNo": stu.student_no if stu else "",
            "advisorName": stu.advisor_name if stu else "", "reviewerName": r.reviewer_name,
            "status": r.status, "statusLabel": REVIEW_STATUS_LABEL.get(r.status, r.status),
            "statusTone": REVIEW_STATUS_TONE.get(r.status, "default"),
            "score": r.score, "opinion": r.opinion or "", "reviewedAt": _iso(r.reviewed_at),
            "assignedBy": r.assigned_by or "", "assignedAt": _iso(r.assigned_at)}


def list_reviews(page: int, page_size: int, gd_student_id=None, reviewer_name=None,
                 status=None) -> tuple[list[dict], int]:
    with session() as db:
        scope_ids = accessible_student_ids(db, _tid())
        q = select(GraduationReview).where(GraduationReview.tenant_id == _tid(),
                                           GraduationReview.is_deleted.is_(False),
                                           GraduationReview.gd_student_id.in_(scope_ids or [-1]))
        if gd_student_id:
            q = q.where(GraduationReview.gd_student_id == int(gd_student_id))
        if reviewer_name:
            q = q.where(GraduationReview.reviewer_name == reviewer_name)
        if status:
            q = q.where(GraduationReview.status == status)
        total = int(db.scalar(select(func.count()).select_from(q.subquery())) or 0)
        rows = db.scalars(q.order_by(GraduationReview.id.desc())
                          .offset((max(1, page) - 1) * page_size).limit(page_size)).all()
        items = [_review_row(r, db.get(GraduationStudent, r.gd_student_id)) for r in rows]
        return items, total


def assign_review(gd_student_id, reviewer_name: str, gd_final_id=None) -> dict:
    with session() as db:
        stu = _stu(db, gd_student_id)
        if stu.advisor_name and reviewer_name.strip() == stu.advisor_name:
            raise AppException("VALIDATION_ERROR", "评阅人不得是该生指导教师（SoD 冲突）")
        n, _ = _op()
        r = GraduationReview(tenant_id=_tid(), gd_student_id=stu.id,
                             gd_final_id=int(gd_final_id) if gd_final_id else None,
                             reviewer_name=reviewer_name.strip(), status="ASSIGNED",
                             assigned_by=n, assigned_at=datetime.utcnow())
        db.add(r)
        db.flush()
        _audit(db, "REVIEW", r.id, "分配评阅任务", detail=f"{stu.name}→{reviewer_name}")
        db.commit()
        return _review_row(r, stu)


def submit_review(rid, score: int, opinion: str) -> dict:
    with session() as db:
        r = db.get(GraduationReview, int(rid))
        if not r or r.is_deleted or r.tenant_id != _tid():
            raise not_found("评阅任务不存在")
        assert_student_access(db, db.get(GraduationStudent, r.gd_student_id), "review.submit")
        if r.status not in ("ASSIGNED", "REVIEWING", "RETURNED"):
            raise AppException("DATA_CONFLICT", "当前状态不可提交评阅")
        r.score = score
        r.opinion = opinion
        r.status = "COMPLETED"
        r.reviewed_at = datetime.utcnow()
        _audit(db, "REVIEW", r.id, "提交评阅", detail=f"score={score}")
        db.commit()
        return _review_row(r, db.get(GraduationStudent, r.gd_student_id))


def return_review(rid, reason: str) -> dict:
    if not reason or len(reason.strip()) < 5:
        raise AppException("VALIDATION_ERROR", "退回原因必填且不少于 5 字")
    with session() as db:
        r = db.get(GraduationReview, int(rid))
        if not r or r.is_deleted or r.tenant_id != _tid():
            raise not_found("评阅任务不存在")
        assert_student_access(db, db.get(GraduationStudent, r.gd_student_id), "review.return")
        if r.status != "COMPLETED":
            raise AppException("DATA_CONFLICT", "仅「已完成」评阅可退回重评")
        r.status = "RETURNED"
        _audit(db, "REVIEW", r.id, "退回重评", reason.strip())
        db.commit()
        return _review_row(r, db.get(GraduationStudent, r.gd_student_id))


def review_stats() -> dict:
    with session() as db:
        scope_ids = accessible_student_ids(db, _tid())
        base = [GraduationReview.tenant_id == _tid(), GraduationReview.is_deleted.is_(False),
                GraduationReview.gd_student_id.in_(scope_ids or [-1])]
        total = int(db.scalar(select(func.count()).select_from(GraduationReview).where(*base)) or 0)
        by_status = [{"status": s, "label": REVIEW_STATUS_LABEL[s],
                      "count": int(db.scalar(select(func.count()).select_from(GraduationReview).where(
                          *base, GraduationReview.status == s)) or 0)} for s in REVIEW_STATUS_LABEL]
        return {"total": total, "byStatus": by_status}
