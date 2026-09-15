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
    from app.services.mobile_student_service import _require_student

    profile = resolve_student(db, _require_student(get_current_user_ctx() or {}))
    if not profile:
        raise not_found("当前账号尚未绑定唯一学生档案")
    return profile


def submit(user, body) -> dict:
    """学生本人对某门已发布成绩发起复查，只能操作自己的正式成绩。"""
    from app.models import AaGradeRecheck, AcademicGrade, AcademicStudent, StudentProfile
    with session() as db:
        profile = _resolve_student(db)
        # 首次提交前没有 AaGradeRecheck 行可锁，先锁定稳定的学生主档，再按
        # “复查单 → 成绩”顺序读取当前值。该顺序与审核侧一致，既能让首次
        # 双击串行，也避免审核更正旧成绩时，旧页面再把申请写到已退位成绩上。
        profile = db.query(StudentProfile).filter(
            StudentProfile.id == int(profile.id),
            StudentProfile.tenant_id == _tid(),
            StudentProfile.is_deleted.is_(False),
        ).with_for_update().execution_options(populate_existing=True).first()
        if not profile:
            raise not_found("当前账号尚未绑定唯一学生档案")
        acad_grade_id = _field(body, "acadGradeId")
        if not acad_grade_id or not str(acad_grade_id).isdigit():
            raise _bad("请指定要复查的成绩")
        reason = (_field(body, "reason") or "").strip()
        if len(reason) < 5:
            raise _bad("复查理由必填且不少于 5 字")
        existing = db.query(AaGradeRecheck).filter(
            AaGradeRecheck.tenant_id == _tid(),
            AaGradeRecheck.student_id == profile.id,
            AaGradeRecheck.acad_grade_id == int(acad_grade_id),
            AaGradeRecheck.status == "SUBMITTED",
            AaGradeRecheck.is_deleted.is_(False),
        ).with_for_update().execution_options(populate_existing=True).first()
        if existing:
            raise _invalid("该成绩已有在途复查申请，不可重复发起")
        grade = db.query(AcademicGrade).filter(
            AcademicGrade.id == int(acad_grade_id),
            AcademicGrade.tenant_id == _tid(),
            AcademicGrade.is_deleted.is_(False),
        ).with_for_update().execution_options(populate_existing=True).first()
        if not grade or grade.record_status != "ACTIVE":
            raise _invalid("该成绩已更新，请刷新后重新发起复查")
        academic_student = db.get(AcademicStudent, int(grade.acad_student_id)) if grade.acad_student_id else None
        if not academic_student or academic_student.student_id != profile.id:
            raise no_data_scope("只能复查本人成绩")
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


def _page_args(page, page_size):
    if isinstance(page, bool) or isinstance(page_size, bool):
        raise _bad("复查记录页码不合法")
    try:
        resolved_page, resolved_size = int(page), int(page_size)
    except (TypeError, ValueError) as exc:
        raise _bad("复查记录页码不合法") from exc
    if not 1 <= resolved_page <= 100000 or not 1 <= resolved_size <= 100:
        raise _bad("复查记录页码须在1至100000、每页条数须在1至100之间")
    return resolved_page, resolved_size


def my(user, page=1, page_size=20):
    """我的复查申请列表；只做本人 SQL 分页，不能把全部历史交给手机截断。"""
    from app.models import AaGradeRecheck
    page, page_size = _page_args(page, page_size)
    with session() as db:
        profile = _resolve_student(db)
        query = db.query(AaGradeRecheck).filter(
            AaGradeRecheck.tenant_id == _tid(),
            AaGradeRecheck.student_id == profile.id,
            AaGradeRecheck.is_deleted.is_(False),
        )
        total = int(query.count() or 0)
        rows = query.order_by(AaGradeRecheck.id.desc()).offset(
            (page - 1) * page_size
        ).limit(page_size).all()
        return [_dto(row) for row in rows], total


def eligible_grade(user, acad_grade_id) -> dict:
    """读取深链所指向的一门本人成绩，供学生从成绩单精确发起复查。

    不能用前端翻页或学号猜测目标成绩；这里复用提交前的 tenant、ACTIVE 和
    AcademicStudent 归属条件，确保“查看与复查”链接的对象与真正可提交对象一致。
    """
    from app.models import AcademicGrade, AcademicStudent

    raw_id = str(acad_grade_id or "").strip()
    if not raw_id.isdecimal() or int(raw_id) <= 0:
        raise _bad("成绩编号不合法")
    with session() as db:
        profile = _resolve_student(db)
        grade = db.query(AcademicGrade).filter(
            AcademicGrade.id == int(raw_id),
            AcademicGrade.tenant_id == _tid(),
            AcademicGrade.record_status == "ACTIVE",
            AcademicGrade.is_deleted.is_(False),
        ).first()
        if not grade:
            raise not_found("成绩不存在")
        academic_student = db.get(AcademicStudent, int(grade.acad_student_id)) if grade.acad_student_id else None
        if not academic_student or academic_student.tenant_id != _tid() or academic_student.student_id != profile.id:
            raise no_data_scope("只能查看本人成绩")
        return {
            "gradeId": str(grade.id),
            "courseName": grade.course_name or "未命名课程",
            "term": grade.term or "",
            "score": grade.score,
            "credit": float(grade.credit_value or 0),
            "passStatus": grade.pass_status or "",
        }


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


def review(user, recheck_id, action, note="", new_score=None, *, command_key=None) -> dict:
    """教务复审：维持/调整/拒绝；调整与正式成绩、规则快照同事务。"""
    from app.models import AaGradeRecheck, AcademicGrade, AcademicStudent
    from app.modules.academic_affairs.services.academic_affairs_grade_service import _refresh_aggregates
    from . import academic_affairs_grade_command_receipt as receipt_service
    with session() as db:
        _require_school(user, db)
        receipt, cached = receipt_service.begin(db, user, "RECHECK_REVIEW", command_key, {
            "recheckId": str(recheck_id), "action": str(action or "").upper(),
            "note": str(note or "").strip(), "newScore": new_score,
        })
        if cached is not None:
            return cached
        # 申请行必须先上排他锁再判状态。原来这里是无锁 db.get()，两个教务员并发时可以双双读到
        # SUBMITTED：一个 REJECT、一个 ADJUST，两边各自 commit，结果是「驳回成功」的回执和被
        # 改掉的正式成绩同时成立。ADJUST 分支后面虽然锁了成绩行，但那时决策早已分叉。
        # 锁顺序统一为 AaGradeRecheck → AcademicGrade → AaGradeTask，全流程不得反向加锁。
        row = db.query(AaGradeRecheck).filter(
            AaGradeRecheck.id == int(recheck_id),
            AaGradeRecheck.tenant_id == _tid(),
            AaGradeRecheck.is_deleted.is_(False),
        ).with_for_update().first()
        if not row:
            raise not_found("复查申请不存在")
        if row.status != "SUBMITTED":
            raise AppException(
                "APPROVAL_VERSION_CONFLICT",
                "该成绩复查申请已被处理",
                http_status=409,
            )
        act = (action or "").upper()
        if act == "REJECT":
            if not note or len(note.strip()) < 5:
                raise _bad("不予受理原因必填且不少于 5 字")
            row.status, row.review_note = "REJECTED", note.strip()
            row.reviewed_by, row.reviewed_at = _op(), datetime.utcnow()
            _audit(db, row.id, "RECHECK_REJECT", note.strip()[:100])
            db.flush()
            receipt_service.finish(db, receipt, _dto(row))
            db.commit()
            return _dto(row)
        if act == "UPHOLD":
            row.status, row.review_note = "UPHELD", (note or "").strip() or None
            row.reviewed_by, row.reviewed_at = _op(), datetime.utcnow()
            _audit(db, row.id, "RECHECK_UPHOLD", "维持原成绩")
            db.flush()
            receipt_service.finish(db, receipt, _dto(row))
            db.commit()
            return _dto(row)
        if act != "ADJUST":
            raise _bad("无效操作（UPHOLD/ADJUST/REJECT）")
        if len((note or "").strip()) < 5:
            raise _bad("调整成绩的核验依据必填且不少于 5 字")
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
            "gpa_point", "gpa_policy_code", "gpa_policy_version",
        }
        payload = {
            attr.key: getattr(grade, attr.key)
            for attr in AcademicGrade.__mapper__.column_attrs
            if attr.key not in excluded
        }
        # 必须先让原行退位再插新行：uk_acad_grade_active_record 只允许同一成绩明细存在
        # 一条 ACTIVE 版本，顺序反了会在 flush 时自己撞自己的唯一键。
        grade.record_status = "SUPERSEDED"
        grade.void_reason = "成绩复查更正，已由后继版本接管"
        db.flush()

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
        grade.void_reason = f"成绩复查更正，后继成绩ID={corrected.id}"

        grade_record = db.scalars(select(AaGradeRecord).where(
            AaGradeRecord.tenant_id == _tid(),
            AaGradeRecord.acad_grade_id == grade.id,
            AaGradeRecord.is_deleted.is_(False),
        ).with_for_update()).first()
        if grade_record:
            grade_record.prev_usual_score = grade_record.usual_score
            grade_record.prev_midterm_score = grade_record.midterm_score
            grade_record.prev_final_score = grade_record.final_score
            grade_record.prev_total_score = grade_record.total_score
            grade_record.total_score = score
            grade_record.pass_status = pass_status
            grade_record.acad_grade_id = corrected.id
            grade_record.source = "RECHECK"
            grade_record.version_no = int(grade_record.version_no or 1) + 1
            grade_record.change_reason = note.strip()
            from .academic_affairs_grade_correction_command import _current_user_id
            grade_record.change_by = _current_user_id(db)
            grade_record.change_at = datetime.utcnow()

        correction = AaGradeCorrection(
            tenant_id=_tid(),
            source_type="RECHECK",
            source_ref_id=row.id,
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

        academic_student = db.query(AcademicStudent).filter(AcademicStudent.id == int(grade.acad_student_id), AcademicStudent.tenant_id == _tid()).first() if grade.acad_student_id else None
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
        receipt_service.finish(db, receipt, _dto(row))
        db.commit()
        from app.services.message_event_outbox_service import try_process_pending_outbox
        try_process_pending_outbox(worker_id="aa-grade-recheck-inline")
        return _dto(row)
