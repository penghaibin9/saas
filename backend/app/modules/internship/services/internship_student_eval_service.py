"""岗位实习 · 学生鉴定/自评（P2-C）。

学生本人(mobile)提交自评（总结/收获/问题）→ SUBMITTED；指导教师补意见；学校审核 PENDING→APPROVED/RETURNED。
一名学生一条（内实习记录唯一）。owner + 数据范围复用 internship_service。审计 target_type=STU_EVAL。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import select

from app.core.exceptions import AppException, no_permission, not_found
from app.models import (InternshipAuditTrail, InternshipRecord, InternshipStudentEval,
                        StudentProfile)
from app.services.db_service import _as_id, _iso, _tid, session

SUBMIT_LABEL = {"DRAFT": "草稿", "SUBMITTED": "已提交"}
REVIEW_LABEL = {"PENDING": "待审核", "APPROVED": "已通过", "RETURNED": "已退回"}


def _op_name(user) -> str:
    return (user or {}).get("realName") or "系统"


def _trail(db, eid, action, detail=None, operator="系统"):
    db.add(InternshipAuditTrail(tenant_id=_tid(), target_id=eid, target_type="STU_EVAL",
                                action=action, operator_name=operator, detail_json=detail or {},
                                occurred_at=datetime.utcnow()))


def _get(db, eid) -> InternshipStudentEval:
    e = db.get(InternshipStudentEval, _as_id(eid))
    if not e or e.is_deleted or e.tenant_id != _tid():
        raise not_found("学生鉴定不存在")
    return e


def _ctx(db, e):
    rec = db.get(InternshipRecord, e.internship_id)
    stu = db.get(StudentProfile, e.student_id)
    return rec, stu


def _scope_ctx(user):
    from app.modules.internship.services.internship_service import _current_scope, _rec_in_scope
    return _current_scope(user), _rec_in_scope


def _student_record(db, user, *, batch_id=None, for_write: bool = False):
    from app.modules.internship.services.internship_record_resolver import (
        require_active_student_record,
        resolve_optional_student_record,
    )
    sno = (user or {}).get("studentNo")
    if not sno:
        if for_write:
            raise AppException("VALIDATION_ERROR", "学生身份信息缺失")
        return None, None
    if for_write:
        return require_active_student_record(db, user, batch_id=batch_id, student_no=sno)
    rec, stu, _ctx = resolve_optional_student_record(db, user, batch_id=batch_id, student_no=sno)
    return rec, stu


def _row(e, rec, stu):
    return {
        "id": str(e.id), "internId": str(e.internship_id),
        "studentName": stu.real_name if stu else "-", "studentNo": stu.student_no if stu else "-",
        "advisorName": rec.advisor_name if rec else "",
        "submitStatus": e.submit_status, "submitStatusLabel": SUBMIT_LABEL.get(e.submit_status),
        "reviewStatus": e.school_review_status, "reviewStatusLabel": REVIEW_LABEL.get(e.school_review_status),
        "hasAdvisorOpinion": bool(e.advisor_opinion), "hasMentorOpinion": bool(e.mentor_opinion),
        "createdAt": _iso(e.created_at) or "",
    }


def _full(e):
    return {"selfSummary": e.self_summary or "", "selfHarvest": e.self_harvest or "",
            "selfProblem": e.self_problem or "", "advisorOpinion": e.advisor_opinion or "",
            "mentorOpinion": e.mentor_opinion or "", "reviewComment": e.school_review_comment or "",
            "enterpriseRating": e.enterprise_rating, "positionRating": e.position_rating,
            "enterpriseFeedback": e.enterprise_feedback or "", "positionFeedback": e.position_feedback or ""}


# ═══════════ 学生本人（移动端） ═══════════

def my_eval(user) -> dict | None:
    with session() as db:
        rec, stu = _student_record(db, user)
        if not rec:
            return None
        e = db.scalars(select(InternshipStudentEval).where(
            InternshipStudentEval.tenant_id == _tid(), InternshipStudentEval.internship_id == rec.id,
            InternshipStudentEval.is_deleted.is_(False))).first()
        if not e:
            return None
        return {**_row(e, rec, stu), **_full(e)}


def student_submit(user, body) -> dict:
    b = body or {}
    if not (b.get("selfSummary") or "").strip():
        raise AppException("VALIDATION_ERROR", "实习总结必填")
    with session() as db:
        rec, stu = _student_record(db, user, for_write=True)
        e = db.scalars(select(InternshipStudentEval).where(
            InternshipStudentEval.tenant_id == _tid(), InternshipStudentEval.internship_id == rec.id,
            InternshipStudentEval.is_deleted.is_(False))).first()
        new = e is None
        if new:
            e = InternshipStudentEval(tenant_id=_tid(), internship_id=rec.id, student_id=rec.student_id,
                                      batch_id=rec.batch_id)
            db.add(e)
        elif e.school_review_status == "APPROVED":
            raise AppException("DATA_CONFLICT", "鉴定已通过学校审核，不可再修改")
        e.self_summary = (b.get("selfSummary") or "").strip()
        e.self_harvest = b.get("selfHarvest")
        e.self_problem = b.get("selfProblem")
        # 学生对企业/岗位评价（0037 列；可选）
        if b.get("enterpriseRating") is not None:
            e.enterprise_rating = b.get("enterpriseRating")
        if b.get("positionRating") is not None:
            e.position_rating = b.get("positionRating")
        if b.get("enterpriseFeedback") is not None:
            e.enterprise_feedback = b.get("enterpriseFeedback")
        if b.get("positionFeedback") is not None:
            e.position_feedback = b.get("positionFeedback")
        e.submit_status = "SUBMITTED"
        e.submitted_at = datetime.utcnow()
        if e.school_review_status == "RETURNED":  # 退回后重交，回到待审
            e.school_review_status = "PENDING"
        e.version = (e.version or 0) + 1  # 新建对象 version 尚未取默认值
        db.flush()
        _trail(db, e.id, "STUDENT_SUBMIT", {"resubmit": not new},
               operator=(user or {}).get("realName") or "学生")
        db.commit()
        return {"id": str(e.id), "submitStatus": e.submit_status}


# ═══════════ 教师 / 管理员（PC，owner + 数据范围） ═══════════

def advisor_comment(user, eid, body) -> dict:
    b = body or {}
    if not (b.get("advisorOpinion") or "").strip():
        raise AppException("VALIDATION_ERROR", "指导教师意见必填")
    scope, in_scope = _scope_ctx(user)
    with session() as db:
        e = _get(db, eid)
        rec, stu = _ctx(db, e)
        if not in_scope(scope, db, rec, stu):
            raise no_permission("只能对本人指导学生填写意见")
        if e.submit_status != "SUBMITTED":
            raise AppException("DATA_CONFLICT", "学生尚未提交自评，暂不能填写意见")
        e.advisor_opinion = (b.get("advisorOpinion") or "").strip()[:1000]
        if (b.get("mentorOpinion") or "").strip():
            e.mentor_opinion = (b.get("mentorOpinion") or "").strip()[:1000]
        e.version += 1
        _trail(db, e.id, "ADVISOR_COMMENT", {"hasMentor": bool(b.get("mentorOpinion"))},
               operator=_op_name(user))
        db.commit()
        return {"id": str(e.id)}


def review(user, eid, action: str, comment: str = "") -> dict:
    if action not in ("APPROVE", "RETURN"):
        raise AppException("VALIDATION_ERROR", "action 必须是 APPROVE/RETURN")
    if action == "RETURN" and (not comment or len(comment.strip()) < 5):
        raise AppException("VALIDATION_ERROR", "退回原因必填且不少于 5 字")
    scope, in_scope = _scope_ctx(user)
    with session() as db:
        e = _get(db, eid)
        rec, stu = _ctx(db, e)
        if not in_scope(scope, db, rec, stu):
            raise no_permission("只能审核本人数据范围内的学生鉴定")
        if e.submit_status != "SUBMITTED":
            raise AppException("DATA_CONFLICT", "学生尚未提交自评")
        if e.school_review_status != "PENDING":
            raise AppException("DATA_CONFLICT", "该鉴定已审核，请刷新")
        e.school_review_status = "APPROVED" if action == "APPROVE" else "RETURNED"
        e.school_review_comment = (comment or "").strip() or None
        e.reviewed_by_name = _op_name(user)
        e.reviewed_at = datetime.utcnow()
        e.version += 1
        _trail(db, e.id, f"REVIEW_{action}", {"comment": (comment or "").strip()}, operator=_op_name(user))
        db.commit()
        return {"id": str(e.id), "reviewStatus": e.school_review_status,
                "reviewStatusLabel": REVIEW_LABEL[e.school_review_status]}


def list_evals(page, page_size, review_status=None, keyword=None, view=None, batch_id=None, user=None):
    scope, in_scope = _scope_ctx(user)
    with session() as db:
        from app.modules.internship.services.internship_batch_context import batch_record_ids
        _, record_ids = batch_record_ids(db, batch_id)
        if not record_ids:
            return [], 0
        q = select(InternshipStudentEval).where(InternshipStudentEval.tenant_id == _tid(),
                                                InternshipStudentEval.is_deleted.is_(False),
                                                InternshipStudentEval.internship_id.in_(record_ids))
        if review_status:
            q = q.where(InternshipStudentEval.school_review_status == review_status)
        # 一页台账、按菜单 view 分工作队列（成熟产品：多维评价共用一张台账）
        v = (view or "").lower()
        if v == "self":
            q = q.where(InternshipStudentEval.submit_status == "SUBMITTED")
        elif v == "enterprise":
            q = q.where((InternshipStudentEval.mentor_opinion.is_(None)) | (InternshipStudentEval.mentor_opinion == ""))
        elif v == "position":
            q = q.where(InternshipStudentEval.position_rating.is_(None))
        elif v == "advisor":
            q = q.where((InternshipStudentEval.advisor_opinion.is_(None)) | (InternshipStudentEval.advisor_opinion == ""))
        rows = db.scalars(q.order_by(InternshipStudentEval.id.desc())).all()
        items = []
        for e in rows:
            rec, stu = _ctx(db, e)
            if keyword and (not stu or keyword.strip() not in (stu.real_name or "")):
                continue
            if not in_scope(scope, db, rec, stu):
                continue
            items.append(_row(e, rec, stu))
        total = len(items)
        start = (max(1, page) - 1) * page_size
        return items[start:start + page_size], total


def get_eval(eid, user=None) -> dict:
    from app.services import file_service
    scope, in_scope = _scope_ctx(user)
    with session() as db:
        e = _get(db, eid)
        rec, stu = _ctx(db, e)
        if not in_scope(scope, db, rec, stu):
            raise no_permission("该学生鉴定不在你的数据范围内")
        trail = db.scalars(select(InternshipAuditTrail).where(
            InternshipAuditTrail.tenant_id == _tid(), InternshipAuditTrail.target_type == "STU_EVAL",
            InternshipAuditTrail.target_id == e.id).order_by(InternshipAuditTrail.id)).all()
        return {**_row(e, rec, stu), **_full(e),
                "attachment": file_service.attachment_view(e.file_id),
                "auditTrail": [{"action": t.action, "operator": t.operator_name or "",
                                "detail": t.detail_json or {}, "occurredAt": _iso(t.occurred_at)}
                               for t in trail]}


def export_evals(review_status=None, keyword=None, batch_id=None, user=None) -> dict:
    from app.services import xlsx_util
    from app.modules.internship.services.internship_export_util import load_export_rows
    items, _ = load_export_rows(
        list_evals, review_status=review_status, keyword=keyword,
        batch_id=batch_id, user=user)
    headers = ["学号", "姓名", "指导教师", "自评提交", "指导教师意见", "企业导师意见", "学校审核"]
    rows = [[it["studentNo"], it["studentName"], it["advisorName"], it["submitStatusLabel"],
             "已填" if it["hasAdvisorOpinion"] else "未填", "已填" if it["hasMentorOpinion"] else "未填",
             it["reviewStatusLabel"]] for it in items]
    wm = f"岗位实习中心·学生鉴定台账 · 导出人：{_op_name(user)} · {datetime.now():%Y-%m-%d %H:%M} · 导出留痕"
    content = xlsx_util.build_ledger_xlsx("学生鉴定台账", headers, rows, watermark=wm)
    return xlsx_util.pack_xlsx_result(content, "学生鉴定台账.xlsx", len(items))
