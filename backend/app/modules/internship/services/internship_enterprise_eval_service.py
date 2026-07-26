"""岗位实习 · 企业评价：纸质材料代录、退回重交与学校独立审核。

企业评价分只来自企业盖章原始材料。学校/教师可按数据范围代录，审核仅限学校
或学院授权角色；录入人与审核人必须分离。退回后复用同一记录按版本修改重交，
旧评分、附件、退回意见和经办人进入 append-only 审计，禁止新增重复评价绕过链路。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import select

from app.core.exceptions import AppException, no_permission, not_found
from app.core.permissions import is_super_admin
from app.models import (
    InternshipAuditTrail, InternshipEnterpriseEval, InternshipRecord, StudentProfile,
)
from app.services.db_service import _as_id, _iso, _tid, session

REVIEW_LABEL = {"PENDING": "待审核", "APPROVED": "已通过", "RETURNED": "已退回"}
SOURCE_LABEL = {
    "ENTERPRISE_ONLINE": "企业在线提交",
    "SCHOOL_RECORDED": "学校根据企业纸质材料录入",
    "FILE_EVIDENCE": "企业盖章材料",
    "IMPORTED": "Excel导入",
    "SYSTEM_GENERATED": "系统生成",
    "LEGACY_UNKNOWN": "历史来源未知",
}
SCORE_FIELDS = [
    ("attendanceScore", "attendance_score", "出勤"),
    ("skillScore", "skill_score", "技能"),
    ("attitudeScore", "attitude_score", "态度"),
    ("collaborationScore", "collaboration_score", "协作"),
    ("safetyScore", "safety_score", "安全纪律"),
]
_REVIEW_ROLES = {
    "SCHOOL_ADMIN", "COLLEGE_ADMIN", "INTERNSHIP_ADMIN",
    "INTERN_ADMIN", "COLLEGE_INTERNSHIP_ADMIN",
}


def _op_name(user) -> str:
    return (user or {}).get("realName") or "系统"


def _user_id(user) -> str:
    return str((user or {}).get("userId") or "")


def _role_code(user) -> str:
    return str(
        (user or {}).get("currentRoleCode") or
        (user or {}).get("roleCode") or
        (user or {}).get("userType") or ""
    ).strip().upper()


def _is_review_admin(user) -> bool:
    return is_super_admin(user or {}) or _role_code(user) in _REVIEW_ROLES


def _trail(db, eval_id, action, detail=None, operator="系统"):
    db.add(InternshipAuditTrail(
        tenant_id=_tid(), target_id=eval_id, target_type="ENT_EVAL",
        action=action, operator_name=operator, detail_json=detail or {},
        occurred_at=datetime.utcnow()))


def _get(db, eval_id, *, lock=False) -> InternshipEnterpriseEval:
    query = select(InternshipEnterpriseEval).where(
        InternshipEnterpriseEval.id == _as_id(eval_id),
        InternshipEnterpriseEval.tenant_id == _tid(),
        InternshipEnterpriseEval.is_deleted.is_(False),
    )
    row = db.scalar(query.with_for_update() if lock else query)
    if not row:
        raise not_found("企业评价不存在")
    return row


def _ctx(db, row):
    record = db.get(InternshipRecord, row.internship_id)
    student = db.get(StudentProfile, row.student_id)
    return record, student


def _scope_ctx(user):
    from app.modules.internship.services.internship_service import _current_scope, _rec_in_scope
    return _current_scope(user), _rec_in_scope


def _assert_scope(db, row, user, message):
    scope, in_scope = _scope_ctx(user)
    record, student = _ctx(db, row)
    if not record or record.tenant_id != _tid() or record.is_deleted:
        raise not_found("关联实习记录不存在")
    if not in_scope(scope, db, record, student):
        raise no_permission(message)
    return record, student


def _total(row) -> int:
    return sum(int(getattr(row, attr) or 0) for _, attr, _ in SCORE_FIELDS)


def _snapshot(row) -> dict:
    return {
        "mentorName": row.mentor_name or "",
        "scores": {json_key: int(getattr(row, attr) or 0) for json_key, attr, _ in SCORE_FIELDS},
        "avgScore": round(_total(row) / 5, 1),
        "overallComment": row.overall_comment or "",
        "recommendHire": bool(row.recommend_hire),
        "sourceType": row.source_type or row.source,
        "sourceFileId": row.source_file_id or row.file_id,
        "recordedByUserId": str(row.recorded_by_user_id or ""),
        "recordedByName": row.recorded_by_name or "",
        "recordedAt": _iso(row.recorded_at),
        "reviewStatus": row.school_review_status,
        "reviewComment": row.school_review_comment or "",
        "reviewedByName": row.reviewed_by_name or "",
        "reviewedAt": _iso(row.reviewed_at),
        "version": int(row.version or 0),
    }


def _row(row, record, student):
    return {
        "id": str(row.id), "internId": str(row.internship_id),
        "internshipId": str(row.internship_id), "batchId": str(row.batch_id or ""),
        "studentName": student.real_name if student else "-",
        "studentNo": student.student_no if student else "-",
        "advisorName": record.advisor_name if record else "",
        "positionName": row.position_name or (record.position_name if record else ""),
        "mentorName": row.mentor_name or "",
        "attendanceScore": row.attendance_score, "skillScore": row.skill_score,
        "attitudeScore": row.attitude_score,
        "collaborationScore": row.collaboration_score,
        "safetyScore": row.safety_score,
        "avgScore": round(_total(row) / 5, 1),
        "overallComment": row.overall_comment or "",
        "recommendHire": bool(row.recommend_hire),
        "source": row.source_type or row.source,
        "sourceLabel": SOURCE_LABEL.get(row.source_type or row.source, "历史来源未知"),
        "sourceFileId": row.source_file_id or row.file_id or "",
        "reviewStatus": row.school_review_status,
        "reviewStatusLabel": REVIEW_LABEL.get(row.school_review_status, row.school_review_status),
        "reviewComment": row.school_review_comment or "",
        "recordedByName": row.recorded_by_name or "",
        "recordedByUserId": str(row.recorded_by_user_id or ""),
        "reviewedByName": row.reviewed_by_name or "",
        "createdAt": _iso(row.created_at) or "",
        "version": int(row.version or 0),
    }


def _validate_scores(body):
    values = {}
    for json_key, column, label in SCORE_FIELDS:
        value = body.get(json_key)
        if value is None or str(value) == "":
            raise AppException("VALIDATION_ERROR", f"{label}评分必填")
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            raise AppException("VALIDATION_ERROR", f"{label}评分必须是 0-100 的整数")
        if not 0 <= parsed <= 100:
            raise AppException("VALIDATION_ERROR", f"{label}评分必须在 0-100 之间")
        values[column] = parsed
    return values


def _validate_file(file_id):
    value = str(file_id or "").strip()
    if not value:
        raise AppException("VALIDATION_ERROR", "学校代录企业评价必须绑定企业纸质评价扫描件")
    from app.services import file_service
    meta = file_service.get_file_meta(value)
    if not meta:
        raise AppException("VALIDATION_ERROR", "评价扫描件不存在或无权访问，请重新上传")
    return value


def _validate_source(body):
    requested = str(body.get("sourceType") or "SCHOOL_RECORDED").upper()
    if requested == "ENTERPRISE_ONLINE":
        raise no_permission("当前未接入企业独立账号，不能标记为企业在线提交")
    return "SCHOOL_RECORDED"


def _editable_values(body):
    mentor = str(body.get("mentorName") or "").strip()
    if not mentor:
        raise AppException("VALIDATION_ERROR", "企业导师姓名必填（评价来源可追溯）")
    file_id = _validate_file(body.get("sourceFileId") or body.get("fileId"))
    source = _validate_source(body)
    return {
        "mentor_name": mentor,
        "overall_comment": str(body.get("overallComment") or "").strip() or None,
        "recommend_hire": bool(body.get("recommendHire")),
        "source": source, "source_type": source,
        "file_id": file_id, "source_file_id": file_id,
        "source_remark": str(body.get("sourceRemark") or "").strip() or None,
        **_validate_scores(body),
    }


def _assert_review_authority(user):
    if not _is_review_admin(user):
        raise no_permission("企业评价学校审核仅限学校或学院授权管理员")


def create(user, body) -> dict:
    payload = body or {}
    internship_id = payload.get("internshipId") or payload.get("internId")
    if not internship_id:
        raise AppException("VALIDATION_ERROR", "缺少实习记录 internshipId")
    values = _editable_values(payload)
    scope, in_scope = _scope_ctx(user)
    with session() as db:
        record = db.get(InternshipRecord, _as_id(internship_id))
        if not record or record.is_deleted or record.tenant_id != _tid():
            raise not_found("实习记录不存在")
        student = db.get(StudentProfile, record.student_id)
        if not in_scope(scope, db, record, student):
            raise no_permission("只能为本人指导或授权范围内学生录入企业评价")
        duplicate = db.scalars(select(InternshipEnterpriseEval).where(
            InternshipEnterpriseEval.tenant_id == _tid(),
            InternshipEnterpriseEval.internship_id == record.id,
            InternshipEnterpriseEval.is_deleted.is_(False),
        ).with_for_update()).first()
        if duplicate:
            if duplicate.school_review_status == "RETURNED":
                raise AppException("DATA_CONFLICT", "该评价已退回，请在原记录上修改重交")
            raise AppException("DATA_CONFLICT", "该学生已有企业评价，请勿重复录入")
        row = InternshipEnterpriseEval(
            tenant_id=_tid(), internship_id=record.id, student_id=record.student_id,
            batch_id=record.batch_id, position_name=record.position_name,
            submit_status="SUBMITTED", school_review_status="PENDING",
            recorded_by_user_id=_user_id(user), recorded_by_name=_op_name(user),
            recorded_at=datetime.utcnow(),
            enterprise_contact_id=_as_id(payload["enterpriseContactId"])
            if payload.get("enterpriseContactId") else None,
            **values,
        )
        db.add(row)
        db.flush()
        _trail(db, row.id, "CREATE", {
            "sourceType": row.source_type, "sourceFileId": row.source_file_id,
            "mentor": row.mentor_name, "avg": round(_total(row) / 5, 1),
            "actorUserId": _user_id(user), "actorRole": _role_code(user),
            "afterStatus": "PENDING", "newVersion": int(row.version or 0),
        }, operator=_op_name(user))
        db.commit()
        return {"id": str(row.id), "source": row.source_type,
                "reviewStatus": "PENDING", "version": int(row.version or 0)}


def resubmit(user, eval_id, body) -> dict:
    payload = body or {}
    if payload.get("expectedVersion") is None:
        raise AppException("DATA_CONFLICT", "修改重交必须携带当前版本")
    values = _editable_values(payload)
    with session() as db:
        row = _get(db, eval_id, lock=True)
        _assert_scope(db, row, user, "只能修改本人指导或授权范围内企业评价")
        if row.school_review_status != "RETURNED":
            raise AppException("DATA_CONFLICT", "仅已退回企业评价可修改重交")
        if int(payload["expectedVersion"]) != int(row.version or 0):
            raise AppException("DATA_CONFLICT", "企业评价版本已变化，请刷新后重试")
        actor_id = _user_id(user)
        if (actor_id and actor_id != str(row.recorded_by_user_id or "")
                and not _is_review_admin(user)):
            raise no_permission("仅原录入人或学校/学院授权管理员可修改重交")
        before = _snapshot(row)
        for key, value in values.items():
            setattr(row, key, value)
        row.submit_status = "SUBMITTED"
        row.school_review_status = "PENDING"
        row.school_review_comment = None
        row.reviewed_by_name = None
        row.reviewed_at = None
        row.recorded_by_user_id = actor_id
        row.recorded_by_name = _op_name(user)
        row.recorded_at = datetime.utcnow()
        row.version = int(row.version or 0) + 1
        _trail(db, row.id, "RESUBMIT", {
            "before": before,
            "after": {
                "mentorName": row.mentor_name,
                "scores": {json_key: int(getattr(row, attr) or 0)
                           for json_key, attr, _ in SCORE_FIELDS},
                "avgScore": round(_total(row) / 5, 1),
                "sourceFileId": row.source_file_id,
                "recordedByUserId": actor_id,
                "reviewStatus": row.school_review_status,
                "version": int(row.version or 0),
            },
            "actorRole": _role_code(user),
        }, operator=_op_name(user))
        db.commit()
        return {"id": str(row.id), "reviewStatus": row.school_review_status,
                "reviewStatusLabel": REVIEW_LABEL[row.school_review_status],
                "version": int(row.version or 0)}


def review(user, eval_id, action: str, comment: str = "", expected_version=None) -> dict:
    normalized = str(action or "").upper()
    if normalized not in ("APPROVE", "RETURN"):
        raise AppException("VALIDATION_ERROR", "action 必须是 APPROVE/RETURN")
    reason = str(comment or "").strip()
    if normalized == "RETURN" and len(reason) < 5:
        raise AppException("VALIDATION_ERROR", "退回原因必填且不少于 5 字")
    _assert_review_authority(user)
    with session() as db:
        row = _get(db, eval_id, lock=True)
        _assert_scope(db, row, user, "只能审核本人数据范围内的企业评价")
        if row.school_review_status != "PENDING":
            raise AppException("DATA_CONFLICT", "该评价已被处理，请刷新")
        if expected_version is not None and int(expected_version) != int(row.version or 0):
            raise AppException("DATA_CONFLICT", "企业评价版本已变化，请刷新后重试")
        actor_id = _user_id(user)
        if actor_id and str(row.recorded_by_user_id or "") == actor_id:
            raise no_permission("企业评价录入人与审核人必须分离，不得审核本人录入记录")
        before_status = row.school_review_status
        row.school_review_status = "APPROVED" if normalized == "APPROVE" else "RETURNED"
        row.school_review_comment = reason or None
        row.reviewed_by_name = _op_name(user)
        row.reviewed_at = datetime.utcnow()
        row.version = int(row.version or 0) + 1
        _trail(db, row.id, f"REVIEW_{normalized}", {
            "comment": reason, "actorUserId": actor_id,
            "actorRole": _role_code(user),
            "recordedByUserId": str(row.recorded_by_user_id or ""),
            "beforeStatus": before_status,
            "afterStatus": row.school_review_status,
            "newVersion": int(row.version or 0),
        }, operator=_op_name(user))
        db.commit()
        return {"id": str(row.id), "reviewStatus": row.school_review_status,
                "reviewStatusLabel": REVIEW_LABEL[row.school_review_status],
                "version": int(row.version or 0)}


def list_evals(page, page_size, review_status=None, keyword=None, batch_id=None, user=None):
    scope, in_scope = _scope_ctx(user)
    with session() as db:
        from app.modules.internship.services.internship_batch_context import batch_record_ids
        _, record_ids = batch_record_ids(db, batch_id)
        if not record_ids:
            return [], 0
        query = select(InternshipEnterpriseEval).where(
            InternshipEnterpriseEval.tenant_id == _tid(),
            InternshipEnterpriseEval.is_deleted.is_(False),
            InternshipEnterpriseEval.internship_id.in_(record_ids),
        )
        if review_status:
            query = query.where(InternshipEnterpriseEval.school_review_status == review_status)
        rows = db.scalars(query.order_by(InternshipEnterpriseEval.id.desc())).all()
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
    with session() as db:
        row = _get(db, eval_id)
        record, student = _assert_scope(
            db, row, user, "该企业评价不在你的数据范围内")
        trail = db.scalars(select(InternshipAuditTrail).where(
            InternshipAuditTrail.tenant_id == _tid(),
            InternshipAuditTrail.target_type == "ENT_EVAL",
            InternshipAuditTrail.target_id == row.id,
        ).order_by(InternshipAuditTrail.id)).all()
        return {
            **_row(row, record, student),
            "attachment": file_service.attachment_view(row.source_file_id or row.file_id),
            "auditTrail": [{
                "action": item.action, "operator": item.operator_name or "",
                "detail": item.detail_json or {}, "occurredAt": _iso(item.occurred_at),
            } for item in trail],
        }


def export_evals(review_status=None, keyword=None, batch_id=None, user=None) -> dict:
    from app.services import xlsx_util
    from app.modules.internship.services.internship_export_util import load_export_rows
    items, _ = load_export_rows(
        list_evals, review_status=review_status, keyword=keyword,
        batch_id=batch_id, user=user)
    headers = [
        "学号", "姓名", "岗位", "企业导师", "出勤", "技能", "态度", "协作", "安全纪律",
        "均分", "建议录用", "来源", "录入人", "审核人", "审核状态", "退回/审核意见",
    ]
    rows = [[
        item["studentNo"], item["studentName"], item["positionName"], item["mentorName"],
        item["attendanceScore"], item["skillScore"], item["attitudeScore"],
        item["collaborationScore"], item["safetyScore"], item["avgScore"],
        "是" if item["recommendHire"] else "否", item["sourceLabel"],
        item["recordedByName"], item["reviewedByName"], item["reviewStatusLabel"],
        item["reviewComment"],
    ] for item in items]
    watermark = (
        f"岗位实习中心·企业评价台账 · 导出人：{_op_name(user)} · "
        f"{datetime.now():%Y-%m-%d %H:%M} · 导出留痕")
    content = xlsx_util.build_ledger_xlsx("企业评价台账", headers, rows, watermark=watermark)
    return xlsx_util.pack_xlsx_result(content, "企业评价台账.xlsx", len(items))
