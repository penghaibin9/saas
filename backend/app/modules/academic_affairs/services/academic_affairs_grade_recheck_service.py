"""成绩复查申请服务：本人稳定身份、正式更正来源和策略快照统一收口。"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import select

from app.core.affairs_security import build_affairs_context, no_data_scope
from app.core.context import get_current_user_ctx
from app.core.exceptions import AppException, not_found
from app.services.db_service import _iso, _tid, session


def _bad(message):
    return AppException("VALIDATION_ERROR", message)


def _invalid(message):
    return AppException("DATA_CONFLICT", message, http_status=409)


def _op():
    ctx = get_current_user_ctx() or {}
    return str(ctx.get("realName") or ctx.get("loginName") or ctx.get("userId") or "")


def _role():
    ctx = get_current_user_ctx() or {}
    return str(ctx.get("currentRoleCode") or "")


def _audit(db, biz_id, action, detail=""):
    from app.models import AffairsAuditTrail
    db.add(AffairsAuditTrail(
        tenant_id=_tid(), biz_type="AA_GRADE_RECHECK", biz_id=biz_id,
        action=action, operator=_op(), role_name=_role(), detail=detail[:990],
        occurred_at=datetime.utcnow(),
    ))


def _require_school(user, db):
    ctx = build_affairs_context(user, db)
    if ctx.scope_type != "TENANT_ALL":
        raise no_data_scope("仅教务处可复审成绩复查")
    return ctx


def _field(body, key, default=None):
    if isinstance(body, dict):
        return body.get(key, default)
    return getattr(body, key, default)


def _dto(row):
    return {
        "recheckId": str(row.id), "studentId": str(row.student_id), "studentNo": row.student_no,
        "studentName": row.student_name, "acadGradeId": str(row.acad_grade_id),
        "courseName": row.course_name, "term": row.term, "originalScore": row.original_score,
        "reason": row.reason, "status": row.status, "newScore": row.new_score,
        "reviewNote": row.review_note, "reviewedBy": row.reviewed_by,
        "reviewedAt": _iso(row.reviewed_at), "createdAt": _iso(row.created_at),
    }


def _resolve_student(db):
    """使用四端统一解析器；真实账号未绑定时fail-closed，不按学号/姓名猜人。"""
    from app.services.mobile_student_identity_facade import resolve_student

    profile = resolve_student(db, get_current_user_ctx() or {})
    if not profile:
        raise not_found("当前账号尚未绑定唯一学生档案")
    return profile


def submit(user, body) -> dict:
    """学生本人对某门已发布成绩发起复查，只能操作自己的正式成绩。"""
    from app.models import AaGradeRecheck, AcademicGrade, AcademicStudent
    with session() as db:
        profile = _resolve_student(db)
        acad_grade_id = _field(body, "acadGradeId")
        if not acad_grade_id or not str(acad_grade_id).isdigit():
            raise _bad("请指定要复查的成绩")
        reason = (_field(body, "reason") or "").strip()
        if len(reason) < 5:
            raise _bad("复查理由必填且不少于 5 字")
        grade = db.get(AcademicGrade, int(acad_grade_id))
        if not grade or grade.is_deleted or grade.tenant_id != _tid() or grade.record_status != "ACTIVE":
            raise not_found("成绩不存在")
        academic_student = db.get(AcademicStudent, int(grade.acad_student_id)) if grade.acad_student_id else None
        if not academic_student or academic_student.student_id != profile.id:
            raise no_data_scope("只能复查本人成绩")
        existing = db.query(AaGradeRecheck).filter(
            AaGradeRecheck.tenant_id == _tid(),
            AaGradeRecheck.acad_grade_id == grade.id,
            AaGradeRecheck.status == "SUBMITTED",
            AaGradeRecheck.is_deleted.is_(False),
        ).first()
        if existing:
            raise _invalid("该成绩已有在途复查申请，不可重复发起")
        row = AaGradeRecheck(
            tenant_id=_tid(), student_id=profile.id, student_no=profile.student_no,
            student_name=profile.real_name, acad_grade_id=grade.id, course_name=grade.course_name,
            term=grade.term, original_score=grade.score, reason=reason, status="SUBMITTED",
        )
        db.add(row)
        db.flush()
        _audit(db, row.id, "RECHECK_SUBMIT", f"{grade.course_name or ''} 原{grade.score}分")
        db.commit()
        return _dto(row)


def my(user):
    """我的复查申请列表。"""
    from app.models import AaGradeRecheck
    with session() as db:
        profile = _resolve_student(db)
        rows = db.query(AaGradeRecheck).filter(
            AaGradeRecheck.tenant_id == _tid(),
            AaGradeRecheck.student_id == profile.id,
            AaGradeRecheck.is_deleted.is_(False),
        ).order_by(AaGradeRecheck.id.desc()).all()
        return [_dto(row) for row in rows]


def list_all(user, status=None, page=1, page_size=50):
    """成绩复查台账（教务处全校范围）。"""
    from app.models import AaGradeRecheck
    with session() as db:
        _require_school(user, db)
        query = db.query(AaGradeRecheck).filter(
            AaGradeRecheck.tenant_id == _tid(),
            AaGradeRecheck.is_deleted.is_(False),
        )
        if status:
            query = query.filter(AaGradeRecheck.status == status)
        rows = query.order_by(AaGradeRecheck.id.desc()).all()
        return [_dto(row) for row in rows[(page - 1) * page_size: page * page_size]], len(rows)


def review(user, recheck_id, action, note="", new_score=None) -> dict:
    """教务复审：维持/调整/拒绝；调整与正式成绩、规则快照同事务。"""
    from app.models import AaGradeRecheck, AcademicGrade, AcademicStudent
    from app.modules.academic_affairs.services.academic_affairs_grade_service import _refresh_aggregates
    with session() as db:
        _require_school(user, db)
        row = db.get(AaGradeRecheck, int(recheck_id))
        if not row or row.is_deleted or row.tenant_id != _tid():
            raise not_found("复查申请不存在")
        if row.status != "SUBMITTED":
            raise _invalid("仅待复查记录可处理")
        act = (action or "").upper()
        if act == "REJECT":
            if not note or len(note.strip()) < 5:
                raise _bad("不予受理原因必填且不少于 5 字")
            row.status, row.review_note = "REJECTED", note.strip()
            row.reviewed_by, row.reviewed_at = _op(), datetime.utcnow()
            _audit(db, row.id, "RECHECK_REJECT", note.strip()[:100])
            db.commit()
            return _dto(row)
        if act == "UPHOLD":
            row.status, row.review_note = "UPHELD", (note or "").strip() or None
            row.reviewed_by, row.reviewed_at = _op(), datetime.utcnow()
            _audit(db, row.id, "RECHECK_UPHOLD", "维持原成绩")
            db.commit()
            return _dto(row)
        if act != "ADJUST":
            raise _bad("无效操作（UPHOLD/ADJUST/REJECT）")
        if new_score is None or not (0 <= int(new_score) <= 100):
            raise _bad("调整后成绩必须为 0-100")
        grade = db.query(AcademicGrade).filter(
            AcademicGrade.id == int(row.acad_grade_id),
            AcademicGrade.tenant_id == _tid(),
            AcademicGrade.is_deleted.is_(False),
        ).with_for_update().first()
        if not grade or grade.record_status != "ACTIVE":
            raise not_found("被复查成绩不存在或已失效")

        from app.models import AaGradeRecord, AaGradeTask
        from app.models.academic_affairs_effective_grade import AaGradeCorrection
        from app.modules.academic_affairs.services.academic_affairs_archive_service import guard_term_writable
        from app.modules.academic_affairs.services.academic_affairs_effective_grade_policy_service import (
            freeze_effective_grade_policy,
            policy_payload,
        )

        if not grade.grade_task_id:
            raise _invalid("历史成绩缺少发布任务快照，无法安全判定及格线，请先完成数据治理")
        grade_task = db.query(AaGradeTask).filter(
            AaGradeTask.id == int(grade.grade_task_id),
            AaGradeTask.tenant_id == _tid(),
            AaGradeTask.is_deleted.is_(False),
        ).with_for_update().first()
        if not grade_task or not grade_task.term_id:
            raise _invalid("成绩发布任务或学期快照缺失，禁止直接更正正式成绩")
        guard_term_writable(db, int(grade_task.term_id))
        if not grade.effective_attempt_strategy or not grade.effective_policy_code:
            raise _invalid("历史成绩缺少冻结的有效成绩策略，必须治理后才能更正")

        pass_line = int(grade.pass_line_snapshot if grade.pass_line_snapshot is not None else grade_task.pass_line)
        score = int(new_score)
        pass_status = "PASSED" if score >= pass_line else "FAILED"

        excluded = {
            "id", "created_at", "created_by", "updated_at", "updated_by",
            "is_deleted", "version", "score", "pass_status", "record_status",
            "void_reason", "source", "source_biz_type", "source_biz_id",
        }
        payload = {
            attr.key: getattr(grade, attr.key)
            for attr in AcademicGrade.__mapper__.column_attrs
            if attr.key not in excluded
        }
        corrected = AcademicGrade(
            **payload,
            score=score,
            pass_status=pass_status,
            record_status="ACTIVE",
            void_reason=None,
            source="RECHECK",
            source_biz_type="RECHECK",
            source_biz_id=row.id,
        )
        db.add(corrected)
        db.flush()

        grade.record_status = "SUPERSEDED"
        grade.void_reason = f"成绩复查更正，后继成绩ID={corrected.id}"

        grade_record = db.scalars(select(AaGradeRecord).where(
            AaGradeRecord.tenant_id == _tid(),
            AaGradeRecord.acad_grade_id == grade.id,
            AaGradeRecord.is_deleted.is_(False),
        ).with_for_update()).first()
        if grade_record:
            grade_record.total_score = score
            grade_record.pass_status = pass_status
            grade_record.acad_grade_id = corrected.id
            grade_record.version_no = int(grade_record.version_no or 1) + 1
            grade_record.change_reason = (note or "成绩复查更正").strip()
            grade_record.change_at = datetime.utcnow()

        correction = AaGradeCorrection(
            tenant_id=_tid(),
            recheck_id=row.id,
            original_grade_id=grade.id,
            corrected_grade_id=corrected.id,
            before_score=grade.score,
            after_score=score,
            pass_line=pass_line,
            rule_snapshot_json=__import__("json").dumps(
                {
                    "passLine": pass_line,
                    "policy": policy_payload(corrected),
                    "gradeTaskId": str(grade_task.id),
                    "termId": str(grade_task.term_id),
                },
                ensure_ascii=False, sort_keys=True,
            ),
            reason=(note or "").strip() or None,
            operator=_op(),
            effective_at=datetime.utcnow(),
            status="ACTIVE",
        )
        db.add(correction)

        row.new_score, row.status = score, "ADJUSTED"
        row.review_note = (note or "").strip() or None
        row.reviewed_by, row.reviewed_at = _op(), datetime.utcnow()

        academic_student = db.get(AcademicStudent, int(grade.acad_student_id)) if grade.acad_student_id else None
        if academic_student:
            _refresh_aggregates(db, academic_student)

        from app.services.message_event_outbox_service import emit_receiver_notice
        emit_receiver_notice(
            db,
            event_code="GRADE.RECHECK_RESULT",
            source_module="academic-affairs",
            source_biz_type="aa_grade_recheck",
            source_biz_id=row.id,
            receiver_id=int(row.student_id),
            title="成绩复查结果",
            content=f"{row.course_name or ''} 经复查成绩由 {row.original_score} 调整为 {score}",
            receiver_as="student",
        )
        _audit(
            db, row.id, "RECHECK_ADJUST",
            f"{row.course_name or ''} {row.original_score}→{score};passLine={pass_line};newGradeId={corrected.id}",
        )
        freeze_effective_grade_policy(
            db, corrected, event_type="RECHECK", source_biz_type="RECHECK", source_biz_id=row.id,
        )
        db.flush()
        db.commit()
        from app.services.message_event_outbox_service import try_process_pending_outbox
        try_process_pending_outbox(worker_id="aa-grade-recheck-inline")
        return _dto(row)
