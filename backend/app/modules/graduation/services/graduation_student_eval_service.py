"""毕业设计中心 · 导师对学生过程评价（区别于学院评导师 t_gd_mentor_eval）。"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func, select

from app.core.context import get_current_user_ctx
from app.core.exceptions import AppException, not_found
from app.models import GraduationAuditTrail, GraduationStudent, GraduationStudentEval
from app.modules.graduation.services.graduation_scope_service import (
    accessible_student_ids, assert_student_access,
)
from app.services.db_service import _iso, _tid, session

EVAL_LEVELS = ("优秀", "良好", "合格", "不合格")
STATUS_LABEL = {"DRAFT": "草稿", "SUBMITTED": "已提交"}


def _op() -> tuple[str, str]:
    u = get_current_user_ctx() or {}
    return u.get("realName") or "系统", u.get("roleName") or u.get("currentRoleCode") or ""


def _audit(db, bid, action, detail="", before="", after=""):
    n, r = _op()
    db.add(GraduationAuditTrail(
        tenant_id=_tid(), biz_type="STUDENT_EVAL", biz_id=str(bid), action=action,
        operator=n, role_name=r, detail=detail, before_val=before, after_val=after,
        occurred_at=datetime.now(timezone.utc)))


def _stu(db, sid) -> GraduationStudent:
    s = db.get(GraduationStudent, int(sid))
    if not s or s.is_deleted or s.tenant_id != _tid():
        raise not_found("毕设学生不存在或不在当前数据范围内")
    return assert_student_access(db, s, "student_eval")


def _row(e: GraduationStudentEval, stu=None) -> dict:
    return {
        "id": str(e.id),
        "gdStudentId": str(e.gd_student_id),
        "studentName": stu.name if stu else "",
        "studentNo": stu.student_no if stu else "",
        "mentorId": str(e.mentor_id) if e.mentor_id else "",
        "period": e.period or "",
        "score": e.score,
        "level": e.level,
        "content": e.content or "",
        "status": e.status,
        "statusLabel": STATUS_LABEL.get(e.status, e.status),
        "submittedBy": e.submitted_by or "",
        "submittedAt": _iso(e.submitted_at),
        "createdAt": _iso(e.created_at),
    }


def list_evals(page: int, page_size: int, gd_student_id=None) -> tuple[list[dict], int]:
    with session() as db:
        scope_ids = accessible_student_ids(db, _tid())
        q = select(GraduationStudentEval).where(
            GraduationStudentEval.tenant_id == _tid(),
            GraduationStudentEval.is_deleted.is_(False),
            GraduationStudentEval.gd_student_id.in_(scope_ids or [-1]))
        if gd_student_id:
            q = q.where(GraduationStudentEval.gd_student_id == int(gd_student_id))
        total = int(db.scalar(select(func.count()).select_from(q.subquery())) or 0)
        rows = db.scalars(
            q.order_by(GraduationStudentEval.id.desc())
            .offset((max(1, page) - 1) * page_size).limit(page_size)
        ).all()
        items = []
        for e in rows:
            stu = db.get(GraduationStudent, e.gd_student_id)
            items.append(_row(e, stu))
        return items, total


def create_eval(gd_student_id, body: dict) -> dict:
    """导师创建并提交（或保留草稿）对学生的过程评价。"""
    try:
        score = int(body.get("score"))
    except (TypeError, ValueError):
        raise AppException("VALIDATION_ERROR", "评分必须是 0-100 的整数")
    if not 0 <= score <= 100:
        raise AppException("VALIDATION_ERROR", "评分范围 0-100")
    level = (body.get("level") or "").strip()
    if level not in EVAL_LEVELS:
        raise AppException("VALIDATION_ERROR", "评价等级必须是 优秀/良好/合格/不合格")
    status = (body.get("status") or "SUBMITTED").strip().upper()
    if status not in ("DRAFT", "SUBMITTED"):
        raise AppException("VALIDATION_ERROR", "状态仅支持 DRAFT/SUBMITTED")
    with session() as db:
        stu = _stu(db, gd_student_id)
        n, _ = _op()
        now = datetime.now(timezone.utc)
        e = GraduationStudentEval(
            tenant_id=_tid(), gd_student_id=stu.id, mentor_id=stu.mentor_id,
            period=(body.get("period") or "").strip() or None,
            score=score, level=level,
            content=(body.get("content") or body.get("note") or "").strip() or None,
            status=status,
            submitted_by=n if status == "SUBMITTED" else None,
            submitted_at=now if status == "SUBMITTED" else None,
        )
        db.add(e)
        db.flush()
        _audit(db, e.id, "提交导师评价" if status == "SUBMITTED" else "保存评价草稿",
               detail=f"{stu.name}/{level}/{score}")
        db.commit()
        return _row(e, stu)


def submit_eval(eval_id) -> dict:
    with session() as db:
        e = db.get(GraduationStudentEval, int(eval_id))
        if not e or e.is_deleted or e.tenant_id != _tid():
            raise not_found("评价记录不存在")
        stu = _stu(db, e.gd_student_id)
        if e.status == "SUBMITTED":
            raise AppException("DATA_CONFLICT", "评价已提交，无需重复提交")
        n, _ = _op()
        before = e.status
        e.status = "SUBMITTED"
        e.submitted_by = n
        e.submitted_at = datetime.now(timezone.utc)
        _audit(db, e.id, "提交导师评价", before=before, after="SUBMITTED")
        db.commit()
        return _row(e, stu)
