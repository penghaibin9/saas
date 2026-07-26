"""处分闭环安全门：正确学生投影、范围对账、真实变更申诉与DTO动作。"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select

from app.core.context import get_current_user_ctx
from app.core.exceptions import AppException, not_found
from app.services.db_service import _iso, _tid, session

_INSTALLED = False


def install() -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    from app.models import (
        CsDiscipline, CsServiceStudent, DisciplineAppeal, DisciplineCase,
        StudentProfile, StudentStageEvent,
    )
    from app.services import affairs_discipline_service as discipline
    from app.services import affairs_four_end_contract as contract
    from app.services import shadow_student_service as shadow

    old_predicate = contract._is_affairs_mobile_path
    old_row = discipline._row
    old_make_effective = discipline._make_effective
    old_submit_appeal = discipline.submit_appeal
    old_message = discipline._msg

    def request_context_path(path: str) -> bool:
        return old_predicate(path) or path.startswith("/api/v1/student-affairs/discipline/appeals/")

    def students_by_ids(db, rows, attr="student_id"):
        ids = {int(getattr(row, attr)) for row in rows if getattr(row, attr, None)}
        if not ids:
            return {}
        students = db.scalars(select(StudentProfile).where(
            StudentProfile.tenant_id == _tid(), StudentProfile.id.in_(ids),
            StudentProfile.is_deleted.is_(False),
        )).all()
        return {int(row.id): row for row in students}

    def ensure_service_student(db, student_id):
        profile = db.scalars(select(StudentProfile).where(
            StudentProfile.tenant_id == _tid(), StudentProfile.id == int(student_id),
            StudentProfile.is_deleted.is_(False),
        ).with_for_update()).first()
        if not profile:
            raise not_found("学生主档不存在")
        existing = db.scalars(select(CsServiceStudent).where(
            CsServiceStudent.tenant_id == _tid(), CsServiceStudent.student_id == int(profile.id),
            CsServiceStudent.is_deleted.is_(False),
        ).order_by(CsServiceStudent.id)).first()
        if existing:
            return int(existing.id)
        snapshot = shadow.identity_snapshot(db, profile)
        record = CsServiceStudent(
            tenant_id=_tid(), record_status="ACTIVE", care_level="NORMAL",
            risk_level="LOW", mental_flag=False,
            **{key: value for key, value in snapshot.items() if value is not None},
        )
        db.add(record); db.flush()
        return int(record.id)

    def case_row(row, student=None):
        data = old_row(row, student)
        data["allowedActions"] = {
            "REGISTERED": ["SUBMIT", "CANCEL"],
            "RETURNED": ["SUBMIT", "CANCEL"],
            "COLLEGE_REVIEW": ["APPROVE", "RETURN", "REJECT"],
            "STUDENT_AFFAIRS_REVIEW": ["APPROVE", "RETURN", "REJECT"],
            "SCHOOL_REVIEW": ["APPROVE", "RETURN", "REJECT"],
            "EFFECTIVE": ["DELIVER", "REMOVE", "APPEAL"],
            "REMOVE_REVIEW": ["REMOVE_APPROVE", "REMOVE_REJECT"],
        }.get(row.status, [])
        return data

    def appeal_row(appeal, student=None):
        return {
            "appealId": str(appeal.id), "caseId": str(appeal.case_id),
            "studentId": str(appeal.student_id or ""),
            "studentNo": student.student_no if student else "",
            "realName": student.real_name if student else "",
            "reason": appeal.reason or "", "status": appeal.status,
            "statusLabel": discipline._L_APPEAL.get(appeal.status, appeal.status),
            "result": appeal.result or "", "reviewOpinion": appeal.review_opinion or "",
            "reviewer": appeal.reviewer or "", "reviewedAt": _iso(appeal.reviewed_at),
            "version": int(appeal.version or 0),
            "allowedActions": ["REVIEW"] if appeal.status in ("SUBMITTED", "REVIEWING") else [],
        }

    def make_effective(db, case, student):
        existing = db.scalars(select(CsDiscipline).where(
            CsDiscipline.tenant_id == _tid(), CsDiscipline.source_case_id == int(case.id),
            CsDiscipline.is_deleted.is_(False),
        ).with_for_update()).first()
        if existing:
            raise AppException("DATA_INCONSISTENT", "该处分已存在投影，禁止重复生效，请先执行投影对账")
        return old_make_effective(db, case, student)

    def message(db, receiver_id, title, content, message_type, biz_id):
        try:
            receiver = int(receiver_id or 0)
        except (TypeError, ValueError):
            receiver = 0
        if receiver <= 0:
            return None
        return old_message(db, receiver, title, content, message_type, biz_id)

    def submit_appeal(case_id, body, user, *, skip_scope_check=False):
        reason = str(getattr(body, "reason", None) or "").strip()
        if not 5 <= len(reason) <= 1000:
            raise AppException("VALIDATION_ERROR", "申诉理由需5-1000字")
        body.reason = reason
        return old_submit_appeal(case_id, body, user, skip_scope_check=skip_scope_check)

    def review_appeal(appeal_id, body, user):
        result = str(getattr(body, "result", None) or "").upper()
        if result not in ("UPHELD", "REVISED", "REVOKED"):
            raise AppException("VALIDATION_ERROR", "复核结论非法")
        opinion = str(getattr(body, "opinion", None) or "").strip()
        if not 5 <= len(opinion) <= 1000:
            raise AppException("VALIDATION_ERROR", "复核意见需5-1000字")
        raw_body = contract._REQUEST_BODY.get({}) or {}
        revised_type = str(
            getattr(body, "revisedDiscType", None)
            or raw_body.get("revisedDiscType") or raw_body.get("targetDiscType") or ""
        ).upper()
        if result == "REVISED" and revised_type not in discipline.DISC_TYPES:
            raise AppException("VALIDATION_ERROR", "变更处分必须提交 revisedDiscType")

        with session() as db:
            appeal = db.scalars(select(DisciplineAppeal).where(
                DisciplineAppeal.tenant_id == _tid(), DisciplineAppeal.id == int(appeal_id),
                DisciplineAppeal.is_deleted.is_(False),
            ).with_for_update()).first()
            if not appeal:
                raise not_found("申诉不存在")
            discipline._scope_or_403(db, appeal.student_id, user)
            if appeal.status not in ("SUBMITTED", "REVIEWING"):
                raise AppException("APPROVAL_VERSION_CONFLICT", "该申诉已结案")
            discipline.atomic_claim_version(db, appeal, getattr(body, "version", None))
            case = db.scalars(select(DisciplineCase).where(
                DisciplineCase.tenant_id == _tid(), DisciplineCase.id == int(appeal.case_id),
                DisciplineCase.is_deleted.is_(False),
            ).with_for_update()).first()
            if not case:
                raise not_found("原处分不存在")
            projection = None
            if case.cs_discipline_id:
                projection = db.scalars(select(CsDiscipline).where(
                    CsDiscipline.tenant_id == _tid(), CsDiscipline.id == int(case.cs_discipline_id),
                    CsDiscipline.source_case_id == int(case.id), CsDiscipline.is_deleted.is_(False),
                ).with_for_update()).first()
                if not projection:
                    raise AppException("DATA_INCONSISTENT", "处分投影回链异常，禁止复核写入")

            if result == "UPHELD":
                appeal.status = appeal.result = "UPHELD"
                title, content = "处分申诉复核完成", "复核结论：维持原处分"
            elif result == "REVISED":
                if case.status != "EFFECTIVE" or not projection or projection.record_status != "ACTIVE":
                    raise AppException("DATA_CONFLICT", "仅有效且投影正常的处分可变更")
                if revised_type == case.disc_type:
                    raise AppException("VALIDATION_ERROR", "新处分类型不能与原处分相同")
                before = case.disc_type
                case.disc_type = revised_type
                case.version = int(case.version or 0) + 1
                projection.disc_type = revised_type
                projection.version = int(projection.version or 0) + 1
                appeal.status = appeal.result = "REVISED"
                db.add(StudentStageEvent(
                    tenant_id=_tid(), student_id=int(case.student_id), from_stage=None,
                    to_stage="DISCIPLINE_REVISED",
                    reason=f"处分由{before}变更为{revised_type}", source_module="student-affairs",
                ))
                title, content = "处分决定已变更", f"处分类型已由{before}变更为{revised_type}"
            else:
                if case.status != "EFFECTIVE" or not projection or projection.record_status != "ACTIVE":
                    raise AppException("DATA_CONFLICT", "原处分已非生效状态，不能重复撤销")
                case.status, case.removed_at = "REMOVED", datetime.utcnow()
                case.version = int(case.version or 0) + 1
                projection.record_status = "REVOKED"
                projection.revoke_date, projection.revoke_reason = datetime.utcnow(), opinion
                projection.version = int(projection.version or 0) + 1
                appeal.status = appeal.result = "REVOKED"
                db.add(StudentStageEvent(
                    tenant_id=_tid(), student_id=int(case.student_id), from_stage=None,
                    to_stage="DISCIPLINE_REMOVED", reason="申诉复核撤销处分",
                    source_module="student-affairs",
                ))
                discipline._todo_done(db, case.id)
                title, content = "处分已撤销", "你的申诉已获支持，原处分决定已撤销"

            appeal.review_opinion, appeal.reviewer = opinion, discipline._op()[0]
            appeal.reviewed_at, appeal.version = datetime.utcnow(), int(appeal.version or 0) + 1
            discipline._msg(db, appeal.student_id, title, content, "WORKFLOW_RESULT", case.id)
            discipline._audit(db, case.id, "DISCIPLINE_APPEAL_REVIEW", f"{result}:{revised_type}")
            db.commit(); db.refresh(appeal)
            student = db.get(StudentProfile, int(appeal.student_id)) if appeal.student_id else None
            return appeal_row(appeal, student)

    def projection_reconcile():
        from app.services.affairs_dashboard_service import _allowed_class_ids
        user = get_current_user_ctx() or {}
        with session() as db:
            allowed, _ = _allowed_class_ids(db, user)
            conds = [
                DisciplineCase.tenant_id == _tid(), DisciplineCase.is_deleted.is_(False),
                StudentProfile.tenant_id == _tid(), StudentProfile.is_deleted.is_(False),
            ]
            if allowed is not None:
                conds.append(StudentProfile.class_id.in_(allowed or {-1}))
            case_rows = db.scalars(select(DisciplineCase).join(
                StudentProfile, StudentProfile.id == DisciplineCase.student_id,
            ).where(*conds)).all()
            case_ids = {int(row.id) for row in case_rows}
            effective = sum(1 for row in case_rows if row.status == "EFFECTIVE")
            projections = int(db.scalar(select(func.count()).select_from(CsDiscipline).where(
                CsDiscipline.tenant_id == _tid(),
                CsDiscipline.source_case_id.in_(case_ids or {-1}),
                CsDiscipline.record_status == "ACTIVE", CsDiscipline.is_deleted.is_(False),
            )) or 0)
            return {
                "effectiveCases": effective, "activeProjections": projections,
                "consistent": effective == projections,
            }

    contract._is_affairs_mobile_path = request_context_path
    discipline._students_by_ids = students_by_ids
    discipline._cs_student_id = ensure_service_student
    discipline._row = case_row
    discipline._appeal_row = appeal_row
    discipline._make_effective = make_effective
    discipline._msg = message
    discipline.submit_appeal = submit_appeal
    discipline.review_appeal = review_appeal
    discipline.projection_reconcile = projection_reconcile
    _INSTALLED = True
