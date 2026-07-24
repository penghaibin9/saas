"""成绩复查申请服务（对标正方 学生端3.12 成绩复查申请 / 教师端3.11 成绩复查审核）。

学生对本人某门已发布成绩(t_acad_grade)发起复查 → 教务复审：
- 维持原成绩 UPHELD（不改分，留意见）；
- 调整成绩 ADJUSTED（回写 t_acad_grade.score/pass_status source=RECHECK + 刷新学生台账聚合 + 通知学生）；
- 不予受理 REJECTED（留原因）。

纪律：
- 只能复查本人成绩（acad_grade.acad_student_id → t_acad_student.student_id == 当前学生 profile）；
- 同一成绩仅一条在途(SUBMITTED)申请（幂等防重复）；
- 处理留痕（复审人/时间/意见），调整回写与刷台账原子提交。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import select

from app.core.affairs_security import build_affairs_context, no_data_scope
from app.core.context import get_current_user_ctx
from app.core.exceptions import AppException, not_found
from app.services.db_service import _iso, _tid, session


def _bad(m):
    return AppException("VALIDATION_ERROR", m)


def _invalid(m):
    return AppException("DATA_CONFLICT", m, http_status=409)


def _op():
    ctx = get_current_user_ctx() or {}
    return str(ctx.get("realName") or ctx.get("loginName") or ctx.get("userId") or "")


def _role():
    ctx = get_current_user_ctx() or {}
    return str(ctx.get("currentRoleCode") or "")


def _audit(db, biz_id, action, detail=""):
    from app.models import AffairsAuditTrail
    db.add(AffairsAuditTrail(tenant_id=_tid(), biz_type="AA_GRADE_RECHECK", biz_id=biz_id,
                             action=action, operator=_op(), role_name=_role(), detail=detail[:990],
                             occurred_at=datetime.utcnow()))


def _require_school(user, db):
    ctx = build_affairs_context(user, db)
    if ctx.scope_type != "TENANT_ALL":
        raise no_data_scope("仅教务处可复审成绩复查")
    return ctx


def _field(body, key, default=None):
    if isinstance(body, dict):
        return body.get(key, default)
    return getattr(body, key, default)


def _dto(r):
    return {"recheckId": str(r.id), "studentId": str(r.student_id), "studentNo": r.student_no,
            "studentName": r.student_name, "acadGradeId": str(r.acad_grade_id),
            "courseName": r.course_name, "term": r.term, "originalScore": r.original_score,
            "reason": r.reason, "status": r.status, "newScore": r.new_score,
            "reviewNote": r.review_note, "reviewedBy": r.reviewed_by, "reviewedAt": _iso(r.reviewed_at),
            "createdAt": _iso(r.created_at)}


def _resolve_student(db):
    from app.models import StudentProfile
    ctx = get_current_user_ctx() or {}
    sno = ctx.get("studentNo")
    p = db.query(StudentProfile).filter(StudentProfile.tenant_id == _tid(),
                                        StudentProfile.student_no == sno,
                                        StudentProfile.is_deleted.is_(False)).first()
    if not p:
        raise not_found("学生档案不存在")
    return p


def submit(user, body) -> dict:
    """学生本人对某门已发布成绩发起复查（学生端小程序，唯一学生写入口，只能给自己）。"""
    from app.models import AaGradeRecheck, AcademicGrade, AcademicStudent
    with session() as db:
        p = _resolve_student(db)
        acad_grade_id = _field(body, "acadGradeId")
        if not acad_grade_id or not str(acad_grade_id).isdigit():
            raise _bad("请指定要复查的成绩")
        reason = (_field(body, "reason") or "").strip()
        if len(reason) < 5:
            raise _bad("复查理由必填且不少于 5 字")
        g = db.get(AcademicGrade, int(acad_grade_id))
        if not g or g.is_deleted or g.tenant_id != _tid() or g.record_status != "ACTIVE":
            raise not_found("成绩不存在")
        a = db.get(AcademicStudent, int(g.acad_student_id)) if g.acad_student_id else None
        if not a or a.student_id != p.id:
            raise no_data_scope("只能复查本人成绩")
        existing = db.query(AaGradeRecheck).filter(
            AaGradeRecheck.tenant_id == _tid(), AaGradeRecheck.acad_grade_id == g.id,
            AaGradeRecheck.status == "SUBMITTED", AaGradeRecheck.is_deleted.is_(False)).first()
        if existing:
            raise _invalid("该成绩已有在途复查申请，不可重复发起")
        r = AaGradeRecheck(tenant_id=_tid(), student_id=p.id, student_no=p.student_no,
                           student_name=p.real_name, acad_grade_id=g.id, course_name=g.course_name,
                           term=g.term, original_score=g.score, reason=reason, status="SUBMITTED")
        db.add(r)
        db.flush()
        _audit(db, r.id, "RECHECK_SUBMIT", f"{g.course_name or ''} 原{g.score}分")
        db.commit()
        return _dto(r)


def my(user):
    """我的复查申请列表（学生端）。"""
    from app.models import AaGradeRecheck
    with session() as db:
        p = _resolve_student(db)
        rows = db.query(AaGradeRecheck).filter(
            AaGradeRecheck.tenant_id == _tid(), AaGradeRecheck.student_id == p.id,
            AaGradeRecheck.is_deleted.is_(False)).order_by(AaGradeRecheck.id.desc()).all()
        return [_dto(r) for r in rows]


def list_all(user, status=None, page=1, page_size=50):
    """成绩复查台账（教务处口径，读写口径一致收敛 TENANT_ALL）。"""
    from app.models import AaGradeRecheck
    with session() as db:
        _require_school(user, db)
        q = db.query(AaGradeRecheck).filter(AaGradeRecheck.tenant_id == _tid(),
                                            AaGradeRecheck.is_deleted.is_(False))
        if status:
            q = q.filter(AaGradeRecheck.status == status)
        rows = q.order_by(AaGradeRecheck.id.desc()).all()
        return [_dto(r) for r in rows[(page - 1) * page_size: page * page_size]], len(rows)


def review(user, recheck_id, action, note="", new_score=None) -> dict:
    """教务复审：UPHOLD 维持 / ADJUST 调整(回写 t_acad_grade + 刷台账 + 通知学生) / REJECT 不予受理。"""
    from app.models import AaGradeRecheck, AcademicGrade, AcademicStudent, UnifiedMessage
    from app.modules.academic_affairs.services.academic_affairs_grade_service import _refresh_aggregates
    with session() as db:
        _require_school(user, db)
        r = db.get(AaGradeRecheck, int(recheck_id))
        if not r or r.is_deleted or r.tenant_id != _tid():
            raise not_found("复查申请不存在")
        if r.status != "SUBMITTED":
            raise _invalid("仅待复查记录可处理")
        act = (action or "").upper()
        if act == "REJECT":
            if not note or len(note.strip()) < 5:
                raise _bad("不予受理原因必填且不少于 5 字")
            r.status, r.review_note = "REJECTED", note.strip()
            r.reviewed_by, r.reviewed_at = _op(), datetime.utcnow()
            _audit(db, r.id, "RECHECK_REJECT", note.strip()[:100])
            db.commit()
            return _dto(r)
        if act == "UPHOLD":
            r.status, r.review_note = "UPHELD", (note or "").strip() or None
            r.reviewed_by, r.reviewed_at = _op(), datetime.utcnow()
            _audit(db, r.id, "RECHECK_UPHOLD", "维持原成绩")
            db.commit()
            return _dto(r)
        if act != "ADJUST":
            raise _bad("无效操作（UPHOLD/ADJUST/REJECT）")
        if new_score is None or not (0 <= int(new_score) <= 100):
            raise _bad("调整后成绩必须为 0-100")
        g = db.get(AcademicGrade, int(r.acad_grade_id))
        if not g or g.is_deleted or g.tenant_id != _tid() or g.record_status != "ACTIVE":
            raise not_found("被复查成绩不存在或已失效")
        ns = int(new_score)
        g.score, g.pass_status, g.source = ns, ("PASSED" if ns >= 60 else "FAILED"), "RECHECK"
        r.new_score, r.status = ns, "ADJUSTED"
        r.review_note = (note or "").strip() or None
        r.reviewed_by, r.reviewed_at = _op(), datetime.utcnow()
        # 回写教务录入明细（若发布投影时建立了 acad_grade_id 回链），保持工作流表与权威读模型一致
        from app.models import AaGradeRecord
        aa_rec = db.scalars(select(AaGradeRecord).where(
            AaGradeRecord.tenant_id == _tid(), AaGradeRecord.acad_grade_id == g.id,
            AaGradeRecord.is_deleted.is_(False))).first()
        if aa_rec:
            aa_rec.total_score = ns
            aa_rec.pass_status = g.pass_status
        a = db.get(AcademicStudent, int(g.acad_student_id)) if g.acad_student_id else None
        if a:
            _refresh_aggregates(db, a)
        from app.services.message_event_outbox_service import emit_receiver_notice
        emit_receiver_notice(
            db,
            event_code="GRADE.RECHECK_RESULT",
            source_module="academic-affairs",
            source_biz_type="aa_grade_recheck",
            source_biz_id=r.id,
            receiver_id=int(r.student_id),
            title="成绩复查结果",
            content=f"{r.course_name or ''} 经复查成绩由 {r.original_score} 调整为 {ns}",
            receiver_as="student",
        )
        _audit(db, r.id, "RECHECK_ADJUST", f"{r.course_name or ''} {r.original_score}→{ns}")
        db.commit()
        from app.services.message_event_outbox_service import try_process_pending_outbox
        try_process_pending_outbox(worker_id="aa-grade-recheck-inline")
        return _dto(r)
