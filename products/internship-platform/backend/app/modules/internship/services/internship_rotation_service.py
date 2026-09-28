"""Yiyang C05/G12 structured internship rotation workflow."""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from sqlalchemy import and_, or_, select

from app.core.exceptions import AppException, not_found
from app.models import (
    InternshipAuditTrail,
    InternshipBatch,
    InternshipRotation,
    InternshipRotationProject,
)
from app.modules.internship.services.internship_scope import assert_internship_record_scope
from app.modules.internship.services.internship_student_context_guard import require_explicit_context
from app.services.db_service import _as_id, _tid, session


def _op(user):
    return str((user or {}).get("realName") or "系统")


def _date_value(value, label, required=True):
    raw = str(value or "").strip()
    if not raw and not required:
        return None
    try:
        return date.fromisoformat(raw)
    except ValueError:
        raise AppException("VALIDATION_ERROR", f"{label}格式必须为 YYYY-MM-DD") from None


def _score(value, label) -> Decimal:
    try:
        score = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise AppException("VALIDATION_ERROR", f"{label}必须是0-100数字") from None
    if score < 0 or score > 100:
        raise AppException("VALIDATION_ERROR", f"{label}必须在0-100之间")
    return score.quantize(Decimal("0.01"))


def _weights(batch: InternshipBatch | None) -> dict:
    raw = ((batch.rules_config or {}).get("rotationScoreWeights") or {}) if batch else {}
    if not raw:
        return {"theory": 30, "skill": 40, "mentor": 30, "source": "DEFAULT_V1"}
    try:
        weights = {
            "theory": int(raw.get("theory")),
            "skill": int(raw.get("skill")),
            "mentor": int(raw.get("mentor")),
        }
    except (TypeError, ValueError):
        raise AppException("SERVER_CONFIG_ERROR", "轮岗成绩权重配置不合法", http_status=503) from None
    if any(v < 0 or v > 100 for v in weights.values()) or sum(weights.values()) != 100:
        raise AppException("SERVER_CONFIG_ERROR", "轮岗成绩权重必须均为0-100且合计100", http_status=503)
    return {**weights, "source": "BATCH_RULES"}


def _trail(db, rotation, action, detail, user):
    db.add(InternshipAuditTrail(
        tenant_id=_tid(),
        target_id=rotation.id,
        target_type="ROTATION",
        action=action,
        operator_name=_op(user),
        detail_json=detail or {},
        occurred_at=datetime.utcnow(),
    ))


def _projects(db, rotation_id):
    return db.scalars(select(InternshipRotationProject).where(
        InternshipRotationProject.tenant_id == _tid(),
        InternshipRotationProject.rotation_id == int(rotation_id),
        InternshipRotationProject.is_deleted.is_(False),
    ).order_by(InternshipRotationProject.project_seq, InternshipRotationProject.id)).all()


def _view(db, row):
    return {
        "id": str(row.id),
        "internshipId": str(row.internship_id),
        "studentId": str(row.student_id),
        "batchId": str(row.batch_id),
        "rotationSeq": int(row.rotation_seq),
        "departmentName": row.department_name,
        "departmentManagerName": row.department_manager_name or "",
        "mentorUserId": str(row.mentor_user_id or ""),
        "mentorName": row.mentor_name,
        "startDate": row.start_date.isoformat(),
        "endDate": row.end_date.isoformat(),
        "status": row.status,
        "studentSelfEvaluation": row.student_self_evaluation or "",
        "studentSelfRating": row.student_self_rating,
        "selfSubmittedAt": row.self_submitted_at.isoformat() + "Z" if row.self_submitted_at else "",
        "scores": {
            "theory": float(row.theory_score) if row.theory_score is not None else None,
            "skill": float(row.skill_score) if row.skill_score is not None else None,
            "mentor": float(row.mentor_score) if row.mentor_score is not None else None,
            "total": float(row.total_score) if row.total_score is not None else None,
            "rule": row.score_rule_snapshot_json or None,
        },
        "evaluationComment": row.evaluation_comment or "",
        "evaluatorName": row.evaluator_name or "",
        "evaluatedAt": row.evaluated_at.isoformat() + "Z" if row.evaluated_at else "",
        "version": int(row.version or 0),
        "projects": [{
            "id": str(project.id),
            "projectSeq": int(project.project_seq),
            "projectName": project.project_name,
            "projectContent": project.project_content or "",
            "startDate": project.start_date.isoformat() if project.start_date else "",
            "endDate": project.end_date.isoformat() if project.end_date else "",
            "status": project.status,
            "mentorNote": project.mentor_note or "",
            "version": int(project.version or 0),
        } for project in _projects(db, row.id)],
    }


def create_rotation(record_id, body: dict, user: dict):
    payload = body or {}
    department = str(payload.get("departmentName") or "").strip()
    mentor = str(payload.get("mentorName") or "").strip()
    if len(department) < 2:
        raise AppException("VALIDATION_ERROR", "轮岗部门名称至少2个字符")
    if len(mentor) < 2:
        raise AppException("VALIDATION_ERROR", "请填写轮岗带教老师")
    start = _date_value(payload.get("startDate"), "轮岗开始日期")
    end = _date_value(payload.get("endDate"), "轮岗结束日期")
    if start > end:
        raise AppException("VALIDATION_ERROR", "轮岗结束日期不能早于开始日期")

    with session() as db:
        record = assert_internship_record_scope(db, record_id, user, "新增轮岗安排", lock=True)
        requested_batch = payload.get("batchId")
        if requested_batch in (None, ""):
            raise AppException("VALIDATION_ERROR", "缺少当前实习批次 batchId")
        if int(record.batch_id or 0) != int(requested_batch):
            raise AppException("DATA_CONFLICT", "学生记录不属于当前实习批次，请刷新后重试")
        if str(record.status or "").upper() not in {"ONBOARD", "ASSESSING", "APPROVED"}:
            raise AppException("DATA_CONFLICT", "当前实习状态不能新增轮岗安排")
        batch = db.get(InternshipBatch, record.batch_id) if record.batch_id else None
        lower = record.intern_start_date.date() if record.intern_start_date else (batch.start_date.date() if batch and batch.start_date else None)
        upper = record.intern_end_date.date() if record.intern_end_date else (batch.end_date.date() if batch and batch.end_date else None)
        if lower and start < lower or upper and end > upper:
            raise AppException("VALIDATION_ERROR", "轮岗日期必须在当前实习起止日期内")

        overlap = db.scalar(select(InternshipRotation.id).where(
            InternshipRotation.tenant_id == _tid(),
            InternshipRotation.internship_id == record.id,
            InternshipRotation.status != "CANCELLED",
            InternshipRotation.is_deleted.is_(False),
            InternshipRotation.start_date <= end,
            InternshipRotation.end_date >= start,
        ))
        if overlap:
            raise AppException("DATA_CONFLICT", "轮岗时间与已有部门安排重叠，请调整起止日期")

        last = db.scalar(select(InternshipRotation.rotation_seq).where(
            InternshipRotation.tenant_id == _tid(),
            InternshipRotation.internship_id == record.id,
            InternshipRotation.is_deleted.is_(False),
        ).order_by(InternshipRotation.rotation_seq.desc()).limit(1))
        seq = int(last or 0) + 1
        row = InternshipRotation(
            tenant_id=_tid(),
            internship_id=record.id,
            student_id=record.student_id,
            batch_id=record.batch_id,
            rotation_seq=seq,
            department_name=department,
            department_manager_name=str(payload.get("departmentManagerName") or "").strip()[:100] or None,
            mentor_user_id=int(payload["mentorUserId"]) if str(payload.get("mentorUserId") or "").isdigit() else None,
            mentor_name=mentor,
            start_date=start,
            end_date=end,
            status=str(payload.get("status") or "PLANNED").strip().upper(),
        )
        if row.status not in {"PLANNED", "ACTIVE"}:
            raise AppException("VALIDATION_ERROR", "新建轮岗状态仅支持 PLANNED 或 ACTIVE")
        db.add(row)
        db.flush()

        project_rows = payload.get("projects") or []
        if not isinstance(project_rows, list):
            raise AppException("VALIDATION_ERROR", "projects 必须是数组")
        for index, item in enumerate(project_rows, start=1):
            name = str((item or {}).get("projectName") or "").strip()
            if len(name) < 2:
                raise AppException("VALIDATION_ERROR", f"第{index}个项目名称至少2个字符")
            p_start = _date_value((item or {}).get("startDate"), f"第{index}个项目开始日期", required=False)
            p_end = _date_value((item or {}).get("endDate"), f"第{index}个项目结束日期", required=False)
            if p_start and p_end and p_start > p_end:
                raise AppException("VALIDATION_ERROR", f"第{index}个项目结束日期不能早于开始日期")
            if p_start and (p_start < start or p_start > end) or p_end and (p_end < start or p_end > end):
                raise AppException("VALIDATION_ERROR", f"第{index}个项目日期必须在轮岗周期内")
            db.add(InternshipRotationProject(
                tenant_id=_tid(),
                rotation_id=row.id,
                project_seq=index,
                project_name=name,
                project_content=str((item or {}).get("projectContent") or "").strip() or None,
                start_date=p_start,
                end_date=p_end,
                status=str((item or {}).get("status") or "PLANNED").strip().upper(),
                mentor_note=str((item or {}).get("mentorNote") or "").strip()[:1000] or None,
            ))
        _trail(db, row, "ROTATION_CREATE", {
            "batchId": str(record.batch_id or ""),
            "internshipId": str(record.id),
            "rotationSeq": seq,
            "departmentName": department,
            "startDate": start.isoformat(),
            "endDate": end.isoformat(),
            "projectCount": len(project_rows),
        }, user)
        db.commit()
        return _view(db, row)


def list_for_record(record_id, user: dict, *, batch_id=None):
    with session() as db:
        record = assert_internship_record_scope(db, record_id, user, "查看轮岗记录")
        if batch_id not in (None, "") and int(record.batch_id or 0) != int(batch_id):
            raise AppException("DATA_CONFLICT", "学生记录不属于当前实习批次，请刷新后重试")
        rows = db.scalars(select(InternshipRotation).where(
            InternshipRotation.tenant_id == _tid(),
            InternshipRotation.internship_id == record.id,
            InternshipRotation.is_deleted.is_(False),
        ).order_by(InternshipRotation.rotation_seq, InternshipRotation.id)).all()
        return [_view(db, row) for row in rows]


def list_my(user: dict, *, batch_id, internship_id):
    with session() as db:
        record, _student, _batch = require_explicit_context(
            db, user, {"batchId": batch_id, "internshipId": internship_id}, for_write=False)
        rows = db.scalars(select(InternshipRotation).where(
            InternshipRotation.tenant_id == _tid(),
            InternshipRotation.internship_id == record.id,
            InternshipRotation.is_deleted.is_(False),
        ).order_by(InternshipRotation.rotation_seq, InternshipRotation.id)).all()
        return [_view(db, row) for row in rows]


def submit_self_evaluation(rotation_id, body: dict, user: dict):
    payload = body or {}
    text = str(payload.get("selfEvaluation") or "").strip()
    if len(text) < 20:
        raise AppException("VALIDATION_ERROR", "轮岗自评不少于20个字")
    try:
        rating = int(payload.get("selfRating"))
    except (TypeError, ValueError):
        raise AppException("VALIDATION_ERROR", "自评分必须为1-5") from None
    if rating < 1 or rating > 5:
        raise AppException("VALIDATION_ERROR", "自评分必须为1-5")

    with session() as db:
        record, student, _batch = require_explicit_context(db, user, payload, for_write=True)
        row = db.scalar(select(InternshipRotation).where(
            InternshipRotation.id == _as_id(rotation_id),
            InternshipRotation.tenant_id == _tid(),
            InternshipRotation.is_deleted.is_(False),
        ).with_for_update())
        if not row or row.internship_id != record.id or row.student_id != student.id:
            raise not_found("轮岗记录不存在")
        expected = payload.get("expectedVersion")
        if expected is None or int(expected) != int(row.version or 0):
            raise AppException("DATA_CONFLICT", "轮岗记录已变化，请刷新后重试")
        if row.status == "CANCELLED":
            raise AppException("DATA_CONFLICT", "已取消轮岗不能提交自评")
        row.student_self_evaluation = text
        row.student_self_rating = rating
        row.self_submitted_at = datetime.utcnow()
        row.version = int(row.version or 0) + 1
        _trail(db, row, "ROTATION_SELF_EVALUATE", {
            "selfRating": rating,
            "textLength": len(text),
        }, user)
        db.commit()
        return _view(db, row)


def evaluate_rotation(rotation_id, body: dict, user: dict):
    payload = body or {}
    theory = _score(payload.get("theoryScore"), "理论成绩")
    skill = _score(payload.get("skillScore"), "技能成绩")
    mentor = _score(payload.get("mentorScore"), "带教评价成绩")
    with session() as db:
        row = db.scalar(select(InternshipRotation).where(
            InternshipRotation.id == _as_id(rotation_id),
            InternshipRotation.tenant_id == _tid(),
            InternshipRotation.is_deleted.is_(False),
        ).with_for_update())
        if not row:
            raise not_found("轮岗记录不存在")
        record = assert_internship_record_scope(db, row.internship_id, user, "评定轮岗成绩", lock=True)
        requested_batch = payload.get("batchId")
        if requested_batch in (None, "") or int(record.batch_id or 0) != int(requested_batch):
            raise AppException("DATA_CONFLICT", "轮岗记录不属于当前实习批次，请刷新后重试")
        expected = payload.get("expectedVersion")
        if expected is None or int(expected) != int(row.version or 0):
            raise AppException("DATA_CONFLICT", "轮岗记录已变化，请刷新后重试")
        if row.status == "CANCELLED":
            raise AppException("DATA_CONFLICT", "已取消轮岗不能评定成绩")
        if not row.student_self_evaluation:
            raise AppException("DATA_CONFLICT", "学生尚未完成本轮岗自评，不能完成成绩评定")
        if not _projects(db, row.id):
            raise AppException("DATA_CONFLICT", "轮岗尚未登记项目，不能完成成绩评定")
        batch = db.get(InternshipBatch, record.batch_id) if record.batch_id else None
        weights = _weights(batch)
        total = (
            theory * Decimal(weights["theory"])
            + skill * Decimal(weights["skill"])
            + mentor * Decimal(weights["mentor"])
        ) / Decimal("100")
        row.theory_score = theory
        row.skill_score = skill
        row.mentor_score = mentor
        row.total_score = total.quantize(Decimal("0.01"))
        row.score_rule_snapshot_json = weights
        row.evaluator_name = _op(user)
        row.evaluated_at = datetime.utcnow()
        row.evaluation_comment = str(payload.get("comment") or "").strip()[:1000] or None
        row.status = "COMPLETED"
        row.version = int(row.version or 0) + 1
        _trail(db, row, "ROTATION_EVALUATE", {
            "theoryScore": float(theory),
            "skillScore": float(skill),
            "mentorScore": float(mentor),
            "totalScore": float(row.total_score),
            "scoreRule": weights,
        }, user)
        db.commit()
        return _view(db, row)
