"""岗位实习 · 学生自评、指导教师意见与学校独立审核。

学生提交后不可任意覆盖；学校退回后可按版本修改重交。学生正文变化会使旧指导
意见失效，必须由指导教师重新填写。学校审核仅限授权管理员，普通指导教师不能
同时填写意见和完成学校终审。
"""
from __future__ import annotations

from datetime import datetime
from sqlalchemy import select

from app.core.exceptions import AppException, no_permission, not_found
from app.core.permissions import enforce_permission, is_super_admin
from app.models import (
    InternshipAuditTrail, InternshipRecord, InternshipStudentEval, StudentProfile,
)
from app.services.db_service import _as_id, _iso, _tid, session

SUBMIT_LABEL = {"DRAFT": "草稿", "SUBMITTED": "已提交"}
REVIEW_LABEL = {"PENDING": "待审核", "APPROVED": "已通过", "RETURNED": "已退回"}
_REVIEW_ROLES = {
    "SCHOOL_ADMIN", "COLLEGE_ADMIN", "INTERNSHIP_ADMIN",
    "INTERN_ADMIN", "COLLEGE_INTERNSHIP_ADMIN",
}


def _op_name(user) -> str:
    return (user or {}).get("realName") or "系统"


def _user_id(user) -> str:
    return str((user or {}).get("userId") or "")


def _role_code(user) -> str:
    return str((user or {}).get("currentRoleCode") or (user or {}).get("roleCode") or "").upper()


def _trail(db, eval_id, action, detail=None, operator="系统"):
    db.add(InternshipAuditTrail(
        tenant_id=_tid(), target_id=eval_id, target_type="STU_EVAL",
        action=action, operator_name=operator, detail_json=detail or {},
        occurred_at=datetime.utcnow()))


def _get(db, eval_id, *, lock=False) -> InternshipStudentEval:
    query = select(InternshipStudentEval).where(
        InternshipStudentEval.id == _as_id(eval_id),
        InternshipStudentEval.tenant_id == _tid(),
        InternshipStudentEval.is_deleted.is_(False))
    row = db.scalar(query.with_for_update() if lock else query)
    if not row:
        raise not_found("学生鉴定不存在")
    return row


def _ctx(db, row):
    return db.get(InternshipRecord, row.internship_id), db.get(StudentProfile, row.student_id)


def _scope_ctx(user):
    from app.modules.internship.services.internship_service import _current_scope, _rec_in_scope
    return _current_scope(user), _rec_in_scope


def _student_record(db, user, *, batch_id=None, for_write: bool = False):
    from app.modules.internship.services.internship_record_resolver import (
        require_active_student_record, resolve_optional_student_record,
    )
    student_no = (user or {}).get("studentNo")
    if not student_no:
        if for_write:
            raise AppException("VALIDATION_ERROR", "学生身份信息缺失")
        return None, None
    if for_write:
        return require_active_student_record(
            db, user, batch_id=batch_id, student_no=student_no)
    record, student, _context = resolve_optional_student_record(
        db, user, batch_id=batch_id, student_no=student_no)
    return record, student


def _row(row, record, student):
    return {
        "id": str(row.id), "internId": str(row.internship_id),
        "internshipId": str(row.internship_id), "batchId": str(row.batch_id or ""),
        "studentName": student.real_name if student else "-",
        "studentNo": student.student_no if student else "-",
        "advisorName": record.advisor_name if record else "",
        "submitStatus": row.submit_status,
        "submitStatusLabel": SUBMIT_LABEL.get(row.submit_status, row.submit_status),
        "reviewStatus": row.school_review_status,
        "schoolReviewStatus": row.school_review_status,
        "reviewStatusLabel": REVIEW_LABEL.get(row.school_review_status, row.school_review_status),
        "hasAdvisorOpinion": bool(row.advisor_opinion),
        "hasMentorOpinion": bool(row.mentor_opinion),
        "version": int(row.version or 0),
        "createdAt": _iso(row.created_at) or "",
    }


def _full(row):
    return {
        "selfSummary": row.self_summary or "", "selfHarvest": row.self_harvest or "",
        "selfProblem": row.self_problem or "", "advisorOpinion": row.advisor_opinion or "",
        "mentorOpinion": row.mentor_opinion or "",
        "reviewComment": row.school_review_comment or "",
        "reviewedByName": row.reviewed_by_name or "",
        "reviewedAt": _iso(row.reviewed_at) or "",
        "enterpriseRating": row.enterprise_rating,
        "positionRating": row.position_rating,
        "enterpriseFeedback": row.enterprise_feedback or "",
        "positionFeedback": row.position_feedback or "",
    }


def _snapshot(row):
    return {
        "selfSummary": row.self_summary or "", "selfHarvest": row.self_harvest or "",
        "selfProblem": row.self_problem or "", "advisorOpinion": row.advisor_opinion or "",
        "mentorOpinion": row.mentor_opinion or "", "reviewStatus": row.school_review_status,
        "reviewComment": row.school_review_comment or "", "version": int(row.version or 0),
    }


def _expected(payload, current, *, required=True):
    value = (payload or {}).get("expectedVersion", (payload or {}).get("version"))
    if value is None:
        if required:
            raise AppException("DATA_CONFLICT", "缺少数据版本，请刷新后重试")
        return int(current or 0)
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        raise AppException("VALIDATION_ERROR", "expectedVersion 必须是整数")
    if parsed != int(current or 0):
        raise AppException("DATA_CONFLICT", "学生鉴定已被其他用户修改，请刷新后重试")
    return parsed


def _rating(value, label):
    if value in (None, ""):
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        raise AppException("VALIDATION_ERROR", f"{label}必须是1-5的整数")
    if not 1 <= parsed <= 5:
        raise AppException("VALIDATION_ERROR", f"{label}必须在1-5之间")
    return parsed


# ═══════════ 学生本人 ═══════════

def my_eval(user) -> dict | None:
    with session() as db:
        record, student = _student_record(db, user)
        if not record:
            return None
        row = db.scalars(select(InternshipStudentEval).where(
            InternshipStudentEval.tenant_id == _tid(),
            InternshipStudentEval.internship_id == record.id,
            InternshipStudentEval.is_deleted.is_(False))).first()
        return {**_row(row, record, student), **_full(row)} if row else None


def student_submit(user, body) -> dict:
    payload = body or {}
    summary = str(payload.get("selfSummary") or "").strip()
    if len(summary) < 20:
        raise AppException("VALIDATION_ERROR", "实习总结至少20个字")
    with session() as db:
        record, student = _student_record(db, user, for_write=True)
        row = db.scalar(select(InternshipStudentEval).where(
            InternshipStudentEval.tenant_id == _tid(),
            InternshipStudentEval.internship_id == record.id,
            InternshipStudentEval.is_deleted.is_(False)).with_for_update())
        is_new = row is None
        before = _snapshot(row) if row else None
        if not row:
            row = InternshipStudentEval(
                tenant_id=_tid(), internship_id=record.id,
                student_id=record.student_id, batch_id=record.batch_id,
                submit_status="DRAFT", school_review_status="PENDING")
            db.add(row)
        else:
            _expected(payload, row.version, required=True)
            if row.school_review_status == "APPROVED":
                raise AppException("DATA_CONFLICT", "鉴定已通过学校审核，不可再修改")
            if row.submit_status == "SUBMITTED" and row.school_review_status != "RETURNED":
                raise AppException("DATA_CONFLICT", "鉴定正在审核，只有退回后才能修改重交")
        row.self_summary = summary
        row.self_harvest = str(payload.get("selfHarvest") or "").strip() or None
        row.self_problem = str(payload.get("selfProblem") or "").strip() or None
        row.enterprise_rating = _rating(payload.get("enterpriseRating"), "企业评分")
        row.position_rating = _rating(payload.get("positionRating"), "岗位评分")
        row.enterprise_feedback = str(payload.get("enterpriseFeedback") or "").strip() or None
        row.position_feedback = str(payload.get("positionFeedback") or "").strip() or None
        row.submit_status = "SUBMITTED"
        row.submitted_at = datetime.utcnow()
        # 正文发生变化后，旧导师意见和旧学校审核结论不再代表新版本。
        row.advisor_opinion = None
        row.mentor_opinion = None
        row.school_review_status = "PENDING"
        row.school_review_comment = None
        row.reviewed_by_name = None
        row.reviewed_at = None
        row.version = int(row.version or 0) + 1
        db.flush()
        _trail(db, row.id, "STUDENT_SUBMIT" if is_new else "STUDENT_RESUBMIT", {
            "before": before, "afterVersion": int(row.version or 0),
            "studentUserId": _user_id(user), "advisorOpinionInvalidated": not is_new,
        }, operator=_op_name(user) or "学生")
        db.commit()
        return {**_row(row, record, student), **_full(row)}


# ═══════════ 指导教师 / 学校管理员 ═══════════

def advisor_comment(user, eval_id, body, *, expected_batch_id=None) -> dict:
    enforce_permission(user or {}, "internship.eval.advisor.manage")
    payload = body or {}
    opinion = str(payload.get("advisorOpinion") or "").strip()
    if len(opinion) < 5:
        raise AppException("VALIDATION_ERROR", "指导教师意见至少5个字")
    scope, in_scope = _scope_ctx(user)
    with session() as db:
        row = _get(db, eval_id, lock=True)
        record, student = _ctx(db, row)
        if not in_scope(scope, db, record, student):
            raise no_permission("只能对本人指导学生填写意见")
        from app.modules.internship.services.internship_batch_context import assert_record_batch
        assert_record_batch(record, expected_batch_id)
        _expected(payload, row.version, required=True)
        if row.submit_status != "SUBMITTED" or row.school_review_status != "PENDING":
            raise AppException("DATA_CONFLICT", "当前鉴定状态不可填写指导意见")
        before = {"advisorOpinion": row.advisor_opinion or "", "version": int(row.version or 0)}
        row.advisor_opinion = opinion[:1000]
        row.mentor_opinion = str(payload.get("mentorOpinion") or "").strip()[:1000] or None
        row.version = int(row.version or 0) + 1
        _trail(db, row.id, "ADVISOR_COMMENT", {
            "before": before, "newVersion": int(row.version or 0),
            "actorUserId": _user_id(user), "actorRole": _role_code(user),
        }, operator=_op_name(user))
        db.commit()
        return {"id": str(row.id), "version": int(row.version or 0),
                "advisorOpinion": row.advisor_opinion}


def _assert_school_reviewer(user):
    if is_super_admin(user or {}):
        return
    if _role_code(user) not in _REVIEW_ROLES:
        raise no_permission("学生鉴定学校审核仅限学校或学院授权管理员")


def review(user, eval_id, action: str, comment: str = "", expected_version=None,
           expected_batch_id=None) -> dict:
    enforce_permission(user or {}, "internship.eval.self.review")
    _assert_school_reviewer(user)
    action = str(action or "").upper()
    if action not in ("APPROVE", "RETURN"):
        raise AppException("VALIDATION_ERROR", "action 必须是 APPROVE/RETURN")
    if action == "RETURN" and len(str(comment or "").strip()) < 5:
        raise AppException("VALIDATION_ERROR", "退回原因必填且不少于5字")
    scope, in_scope = _scope_ctx(user)
    with session() as db:
        row = _get(db, eval_id, lock=True)
        record, student = _ctx(db, row)
        if not in_scope(scope, db, record, student):
            raise no_permission("只能审核本人数据范围内的学生鉴定")
        from app.modules.internship.services.internship_batch_context import assert_record_batch
        assert_record_batch(record, expected_batch_id)
        _expected({"expectedVersion": expected_version}, row.version,
                  required=expected_version is not None)
        if row.submit_status != "SUBMITTED" or row.school_review_status != "PENDING":
            raise AppException("DATA_CONFLICT", "该鉴定已处理，请刷新")
        if action == "APPROVE" and not str(row.advisor_opinion or "").strip():
            raise AppException("DATA_CONFLICT", "指导教师尚未填写鉴定意见，不能完成学校审核")
        before_status = row.school_review_status
        row.school_review_status = "APPROVED" if action == "APPROVE" else "RETURNED"
        row.school_review_comment = str(comment or "").strip() or None
        row.reviewed_by_name = _op_name(user)
        row.reviewed_at = datetime.utcnow()
        row.version = int(row.version or 0) + 1
        _trail(db, row.id, f"REVIEW_{action}", {
            "beforeStatus": before_status, "afterStatus": row.school_review_status,
            "newVersion": int(row.version or 0), "actorUserId": _user_id(user),
            "actorRole": _role_code(user), "comment": str(comment or "").strip(),
        }, operator=_op_name(user))
        db.commit()
        return {"id": str(row.id), "reviewStatus": row.school_review_status,
                "reviewStatusLabel": REVIEW_LABEL[row.school_review_status],
                "version": int(row.version or 0)}


def list_evals(page, page_size, review_status=None, keyword=None, view=None,
               batch_id=None, user=None):
    scope, in_scope = _scope_ctx(user)
    with session() as db:
        from app.modules.internship.services.internship_batch_context import batch_record_ids
        _, record_ids = batch_record_ids(db, batch_id)
        if not record_ids:
            return [], 0
        query = select(InternshipStudentEval).where(
            InternshipStudentEval.tenant_id == _tid(),
            InternshipStudentEval.is_deleted.is_(False),
            InternshipStudentEval.internship_id.in_(record_ids))
        if review_status:
            query = query.where(InternshipStudentEval.school_review_status == review_status)
        mode = str(view or "").lower()
        if mode == "self":
            query = query.where(InternshipStudentEval.submit_status == "SUBMITTED")
        elif mode == "enterprise":
            query = query.where((InternshipStudentEval.mentor_opinion.is_(None)) |
                                (InternshipStudentEval.mentor_opinion == ""))
        elif mode == "position":
            query = query.where(InternshipStudentEval.position_rating.is_(None))
        elif mode == "advisor":
            query = query.where((InternshipStudentEval.advisor_opinion.is_(None)) |
                                (InternshipStudentEval.advisor_opinion == ""))
        rows = db.scalars(query.order_by(InternshipStudentEval.id.desc())).all()
        items = []
        for row in rows:
            record, student = _ctx(db, row)
            if keyword and (not student or keyword.strip() not in (student.real_name or "")):
                continue
            if not in_scope(scope, db, record, student):
                continue
            items.append(_row(row, record, student))
        total = len(items)
        start = (max(1, page) - 1) * page_size
        return items[start:start + page_size], total


def get_eval(eval_id, user=None) -> dict:
    from app.services import file_service
    scope, in_scope = _scope_ctx(user)
    with session() as db:
        row = _get(db, eval_id)
        record, student = _ctx(db, row)
        if not in_scope(scope, db, record, student):
            raise no_permission("该学生鉴定不在你的数据范围内")
        trail = db.scalars(select(InternshipAuditTrail).where(
            InternshipAuditTrail.tenant_id == _tid(),
            InternshipAuditTrail.target_type == "STU_EVAL",
            InternshipAuditTrail.target_id == row.id).order_by(
                InternshipAuditTrail.id)).all()
        return {**_row(row, record, student), **_full(row),
                "attachment": file_service.attachment_view(row.file_id),
                "auditTrail": [{
                    "action": item.action, "operator": item.operator_name or "",
                    "detail": item.detail_json or {}, "occurredAt": _iso(item.occurred_at),
                } for item in trail]}


def export_evals(review_status=None, keyword=None, batch_id=None, user=None) -> dict:
    from app.services import xlsx_util
    from app.modules.internship.services.internship_export_util import load_export_rows
    items, _ = load_export_rows(
        list_evals, review_status=review_status, keyword=keyword,
        batch_id=batch_id, user=user)
    headers = ["学号", "姓名", "指导教师", "自评提交", "指导教师意见", "企业导师意见", "学校审核", "版本"]
    rows = [[item["studentNo"], item["studentName"], item["advisorName"],
             item["submitStatusLabel"], "已填" if item["hasAdvisorOpinion"] else "未填",
             "已填" if item["hasMentorOpinion"] else "未填",
             item["reviewStatusLabel"], item["version"]] for item in items]
    watermark = (f"岗位实习中心·学生鉴定台账 · 导出人：{_op_name(user)} · "
                 f"{datetime.now():%Y-%m-%d %H:%M} · 导出留痕")
    content = xlsx_util.build_ledger_xlsx("学生鉴定台账", headers, rows, watermark=watermark)
    return xlsx_util.pack_xlsx_result(content, "学生鉴定台账.xlsx", len(items))
