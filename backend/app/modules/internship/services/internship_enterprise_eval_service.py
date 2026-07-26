"""岗位实习 · 企业评价（P2-B）。企业导师五维评价 + 学校审核。

来源 source：企业导师本人提交(ENTERPRISE，门户权限预留) / 学校录入企业纸质评价(SCHOOL_RECORDED)。
学校录入须填企业导师姓名（可附签署扫描件），source 可追溯，避免学校代填假闭环。
审核：submit_status SUBMITTED；school_review_status PENDING→APPROVED/RETURNED。
owner + 数据范围复用 internship_service。审计 target_type=ENT_EVAL。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import select

from app.core.exceptions import AppException, no_permission, not_found
from app.models import (InternshipAuditTrail, InternshipEnterpriseEval, InternshipRecord,
                        StudentProfile)
from app.services.db_service import _as_id, _iso, _tid, session

REVIEW_LABEL = {"PENDING": "待审核", "APPROVED": "已通过", "RETURNED": "已退回"}
# 四端统一口径：「学校录入」= 教师代录企业纸质评价，不得展示为「企业已评」
SOURCE_LABEL = {
    "ENTERPRISE_ONLINE": "企业在线提交",
    "SCHOOL_RECORDED": "学校根据企业纸质材料录入",
    "FILE_EVIDENCE": "企业盖章材料",
    "IMPORTED": "Excel导入",
    "SYSTEM_GENERATED": "系统生成",
    "LEGACY_UNKNOWN": "历史来源未知",
}
SCORE_FIELDS = [("attendanceScore", "attendance_score", "出勤"), ("skillScore", "skill_score", "技能"),
                ("attitudeScore", "attitude_score", "态度"), ("collaborationScore", "collaboration_score", "协作"),
                ("safetyScore", "safety_score", "安全纪律")]
_ENTERPRISE_ROLES = {"ENTERPRISE_MENTOR", "ENTERPRISE_CONTACT"}


def _op_name(user) -> str:
    return (user or {}).get("realName") or "系统"


def _trail(db, eid, action, detail=None, operator="系统"):
    db.add(InternshipAuditTrail(tenant_id=_tid(), target_id=eid, target_type="ENT_EVAL",
                                action=action, operator_name=operator, detail_json=detail or {},
                                occurred_at=datetime.utcnow()))


def _get(db, eid) -> InternshipEnterpriseEval:
    e = db.get(InternshipEnterpriseEval, _as_id(eid))
    if not e or e.is_deleted or e.tenant_id != _tid():
        raise not_found("企业评价不存在")
    return e


def _ctx(db, e):
    rec = db.get(InternshipRecord, e.internship_id)
    stu = db.get(StudentProfile, e.student_id)
    return rec, stu


def _scope_ctx(user):
    from app.modules.internship.services.internship_service import _current_scope, _rec_in_scope
    return _current_scope(user), _rec_in_scope


def _total(e) -> int:
    return e.attendance_score + e.skill_score + e.attitude_score + e.collaboration_score + e.safety_score


def _row(e, rec, stu):
    return {
        "id": str(e.id), "internId": str(e.internship_id),
        "studentName": stu.real_name if stu else "-", "studentNo": stu.student_no if stu else "-",
        "advisorName": rec.advisor_name if rec else "", "positionName": e.position_name or (rec.position_name if rec else ""),
        "mentorName": e.mentor_name or "", "attendanceScore": e.attendance_score, "skillScore": e.skill_score,
        "attitudeScore": e.attitude_score, "collaborationScore": e.collaboration_score, "safetyScore": e.safety_score,
        "avgScore": round(_total(e) / 5, 1), "recommendHire": bool(e.recommend_hire),
        "source": e.source_type or e.source,
        "sourceLabel": SOURCE_LABEL.get(e.source_type or e.source, "历史来源未知"),
        "reviewStatus": e.school_review_status, "reviewStatusLabel": REVIEW_LABEL.get(e.school_review_status),
        "createdAt": _iso(e.created_at) or "",
    }


def _validate_scores(b):
    vals = {}
    for jk, col, label in SCORE_FIELDS:
        v = b.get(jk)
        if v is None or str(v) == "":
            raise AppException("VALIDATION_ERROR", f"{label}评分必填")
        try:
            iv = int(v)
        except (TypeError, ValueError):
            raise AppException("VALIDATION_ERROR", f"{label}评分必须是 0-100 的整数")
        if not 0 <= iv <= 100:
            raise AppException("VALIDATION_ERROR", f"{label}评分必须在 0-100 之间")
        vals[col] = iv
    return vals


def _validate_file(file_id):
    fid = (file_id or "").strip()
    if not fid:
        return None
    from app.services import file_service
    if not file_service.get_file_meta(fid):
        raise AppException("VALIDATION_ERROR", "评价扫描件不存在或无权访问，请重新上传")
    return fid


def create(user, body) -> dict:
    b = body or {}
    iid = b.get("internshipId") or b.get("internId")
    if not iid:
        raise AppException("VALIDATION_ERROR", "缺少实习记录 internshipId")
    if not (b.get("mentorName") or "").strip():
        raise AppException("VALIDATION_ERROR", "企业导师姓名必填（评价来源可追溯）")
    scores = _validate_scores(b)
    file_id = _validate_file(b.get("sourceFileId") or b.get("fileId"))
    if not file_id:
        raise AppException("VALIDATION_ERROR", "学校代录企业评价必须绑定企业纸质评价扫描件")
    source = "SCHOOL_RECORDED"
    if (b.get("sourceType") or source) == "ENTERPRISE_ONLINE":
        raise AppException("NO_PERMISSION", "当前未接入企业独立账号，不能标记为企业在线提交")
    scope, in_scope = _scope_ctx(user)
    with session() as db:
        rec = db.get(InternshipRecord, _as_id(iid))
        if not rec or rec.is_deleted or rec.tenant_id != _tid():
            raise not_found("实习记录不存在")
        stu = db.get(StudentProfile, rec.student_id)
        if not in_scope(scope, db, rec, stu):
            raise no_permission("只能为本人指导/授权学生录入企业评价")
        dup = db.scalars(select(InternshipEnterpriseEval).where(
            InternshipEnterpriseEval.tenant_id == _tid(), InternshipEnterpriseEval.internship_id == rec.id,
            InternshipEnterpriseEval.is_deleted.is_(False))).first()
        if dup:
            raise AppException("DATA_CONFLICT", "该学生已有企业评价，请勿重复录入")
        e = InternshipEnterpriseEval(
            tenant_id=_tid(), internship_id=rec.id, student_id=rec.student_id, batch_id=rec.batch_id,
            position_name=rec.position_name, mentor_name=(b.get("mentorName") or "").strip(),
            overall_comment=b.get("overallComment"), recommend_hire=bool(b.get("recommendHire")),
            source=source, source_type=source, submit_status="SUBMITTED",
            school_review_status="PENDING", file_id=file_id, source_file_id=file_id,
            recorded_by_user_id=str((user or {}).get("userId") or ""),
            recorded_by_name=_op_name(user), recorded_at=datetime.utcnow(),
            enterprise_contact_id=_as_id(b["enterpriseContactId"]) if b.get("enterpriseContactId") else None,
            source_remark=(b.get("sourceRemark") or "").strip() or None, **scores)
        db.add(e); db.flush()
        _trail(db, e.id, "CREATE", {"sourceType": source, "sourceFileId": file_id,
                                    "mentor": e.mentor_name, "avg": round(_total(e) / 5, 1)},
               operator=_op_name(user))
        db.commit()
        return {"id": str(e.id), "source": source}


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
            raise no_permission("只能审核本人数据范围内的企业评价")
        if e.school_review_status != "PENDING":
            raise AppException("DATA_CONFLICT", "该评价已审核，请刷新")
        e.school_review_status = "APPROVED" if action == "APPROVE" else "RETURNED"
        e.school_review_comment = (comment or "").strip() or None
        e.reviewed_by_name = _op_name(user)
        e.reviewed_at = datetime.utcnow()
        e.version += 1
        _trail(db, e.id, f"REVIEW_{action}", {"comment": (comment or "").strip()}, operator=_op_name(user))
        db.commit()
        return {"id": str(e.id), "reviewStatus": e.school_review_status,
                "reviewStatusLabel": REVIEW_LABEL[e.school_review_status]}


def list_evals(page, page_size, review_status=None, keyword=None, batch_id=None, user=None):
    scope, in_scope = _scope_ctx(user)
    with session() as db:
        from app.modules.internship.services.internship_batch_context import batch_record_ids
        _, record_ids = batch_record_ids(db, batch_id)
        if not record_ids:
            return [], 0
        q = select(InternshipEnterpriseEval).where(InternshipEnterpriseEval.tenant_id == _tid(),
                                                   InternshipEnterpriseEval.is_deleted.is_(False),
                                                   InternshipEnterpriseEval.internship_id.in_(record_ids))
        if review_status:
            q = q.where(InternshipEnterpriseEval.school_review_status == review_status)
        rows = db.scalars(q.order_by(InternshipEnterpriseEval.id.desc())).all()
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
            raise no_permission("该企业评价不在你的数据范围内")
        trail = db.scalars(select(InternshipAuditTrail).where(
            InternshipAuditTrail.tenant_id == _tid(), InternshipAuditTrail.target_type == "ENT_EVAL",
            InternshipAuditTrail.target_id == e.id).order_by(InternshipAuditTrail.id)).all()
        return {**_row(e, rec, stu), "overallComment": e.overall_comment or "",
                "reviewComment": e.school_review_comment or "",
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
    headers = ["学号", "姓名", "岗位", "企业导师", "出勤", "技能", "态度", "协作", "安全纪律",
               "均分", "建议录用", "来源", "审核状态"]
    rows = [[it["studentNo"], it["studentName"], it["positionName"], it["mentorName"],
             it["attendanceScore"], it["skillScore"], it["attitudeScore"], it["collaborationScore"],
             it["safetyScore"], it["avgScore"], "是" if it["recommendHire"] else "否",
             it["sourceLabel"], it["reviewStatusLabel"]] for it in items]
    wm = f"岗位实习中心·企业评价台账 · 导出人：{_op_name(user)} · {datetime.now():%Y-%m-%d %H:%M} · 导出留痕"
    content = xlsx_util.build_ledger_xlsx("企业评价台账", headers, rows, watermark=wm)
    return xlsx_util.pack_xlsx_result(content, "企业评价台账.xlsx", len(items))
