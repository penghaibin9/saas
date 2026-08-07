"""包 11：处分主档、服务学生投影、决定版本与申诉事务一致性守卫。"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import func, inspect, select, text
from sqlalchemy.exc import DBAPIError, IntegrityError

# 显式导入，使 fast-schema / metadata.create_all 也登记包 11 两张新表。
from app.models.affairs_discipline_integrity import (
    DisciplineDecisionVersion,
    DisciplineSubflowLock,
)
from app.core.context import get_current_user_ctx
from app.core.exceptions import AppException, not_found
from app.services.db_service import _iso, _tid, session

_INSTALLED = False
_ORIGINAL_SUBMIT_REMOVE: Any = None
_SUBFLOW_CONFLICT_MARKERS = {
    "DISCIPLINE_ACTIVE_SUBFLOW_EXISTS",
    "uk_disc_active_subflow",
    "Duplicate entry",
}


def _has_column(db, table: str, column: str) -> bool:
    return column in {item["name"] for item in inspect(db.get_bind()).get_columns(table)}


def _has_trigger(db, name: str) -> bool:
    if db.get_bind().dialect.name != "mysql":
        return False
    value = db.execute(text("""
        SELECT COUNT(*)
          FROM information_schema.TRIGGERS
         WHERE TRIGGER_SCHEMA = DATABASE()
           AND TRIGGER_NAME = :name
    """), {"name": name}).scalar() or 0
    return int(value) > 0


def _is_subflow_conflict(exc: BaseException) -> bool:
    message = str(getattr(exc, "orig", exc) or exc)
    return any(marker in message for marker in _SUBFLOW_CONFLICT_MARKERS)


def _ensure_cs_student(db, student_id: int):
    """同事务获取或创建真实 CsServiceStudent，绝不退回 StudentProfile.id。"""
    from app.models import CsServiceStudent, StudentProfile

    tenant_id = _tid()
    student_id = int(student_id)
    profile = db.scalars(select(StudentProfile).where(
        StudentProfile.tenant_id == tenant_id,
        StudentProfile.id == student_id,
        StudentProfile.is_deleted.is_(False),
    ).with_for_update()).first()
    if not profile:
        raise not_found("学生主档不存在，无法建立处分投影")

    existing = db.scalars(select(CsServiceStudent).where(
        CsServiceStudent.tenant_id == tenant_id,
        CsServiceStudent.student_id == student_id,
        CsServiceStudent.is_deleted.is_(False),
    ).order_by(CsServiceStudent.id).with_for_update()).first()
    if existing:
        return existing

    if db.get_bind().dialect.name == "mysql" and _has_column(
            db, "t_cs_service_student", "active_student_id"):
        db.execute(text("""
            INSERT INTO t_cs_service_student (
                tenant_id, student_no, student_id, name, gender, class_id, grade,
                care_level, risk_level, mental_flag, record_status,
                created_at, updated_at, is_deleted, version
            ) VALUES (
                :tenant_id, :student_no, :student_id, :name, :gender, :class_id, :grade,
                'NORMAL', 'LOW', 0, 'ACTIVE',
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 0, 0
            )
            ON DUPLICATE KEY UPDATE
                id = LAST_INSERT_ID(id), updated_at = updated_at
        """), {
            "tenant_id": tenant_id,
            "student_no": profile.student_no,
            "student_id": student_id,
            "name": profile.real_name,
            "gender": profile.gender,
            "class_id": str(profile.class_id) if profile.class_id is not None else None,
            "grade": profile.grade,
        })
        existing = db.scalars(select(CsServiceStudent).where(
            CsServiceStudent.tenant_id == tenant_id,
            CsServiceStudent.student_id == student_id,
            CsServiceStudent.is_deleted.is_(False),
        ).order_by(CsServiceStudent.id).with_for_update()).first()
        if existing:
            return existing
        raise AppException("DATA_CONFLICT", "服务学生台账并发创建失败，请重试")

    record = CsServiceStudent(
        tenant_id=tenant_id,
        student_no=profile.student_no,
        student_id=student_id,
        name=profile.real_name,
        gender=profile.gender,
        class_id=str(profile.class_id) if profile.class_id is not None else None,
        grade=profile.grade,
        record_status="ACTIVE",
        care_level="NORMAL",
        risk_level="LOW",
        mental_flag=False,
    )
    db.add(record)
    db.flush()
    return record


def _lock_case(db, case_id: int):
    from app.models import DisciplineCase, StudentProfile

    case = db.scalars(select(DisciplineCase).where(
        DisciplineCase.tenant_id == _tid(),
        DisciplineCase.id == int(case_id),
        DisciplineCase.is_deleted.is_(False),
    ).with_for_update()).first()
    if not case:
        raise not_found("处分记录不存在")
    student = db.get(StudentProfile, int(case.student_id)) if case.student_id else None
    return case, student


def _current_decision(db, case_id: int):
    return db.scalars(select(DisciplineDecisionVersion).where(
        DisciplineDecisionVersion.tenant_id == _tid(),
        DisciplineDecisionVersion.case_id == int(case_id),
    ).order_by(DisciplineDecisionVersion.version_no.desc()).with_for_update()).first()


def _append_decision(
    db,
    case,
    *,
    kind: str,
    source_type: str,
    source_id: int | None,
    disc_type: str,
    reason: str | None,
    doc_no: str | None,
) -> DisciplineDecisionVersion:
    """追加 ORIGINAL/REVISED/REVOKED；生产触发器同时锁死版本链与不可变性。"""
    from app.services import affairs_discipline_service as discipline

    kind = str(kind or "").upper()
    previous = _current_decision(db, int(case.id))
    if previous is None and kind != "ORIGINAL":
        previous = _append_decision(
            db,
            case,
            kind="ORIGINAL",
            source_type="LEGACY_RUNTIME_BACKFILL",
            source_id=int(case.id),
            disc_type=str(case.disc_type),
            reason=case.reason,
            doc_no=case.doc_no,
        )
    if previous is not None and kind == "ORIGINAL":
        return previous

    version = DisciplineDecisionVersion(
        tenant_id=_tid(),
        case_id=int(case.id),
        version_no=1 if previous is None else int(previous.version_no) + 1,
        decision_kind=kind,
        previous_version_id=int(previous.id) if previous else None,
        disc_type=disc_type,
        reason=reason,
        doc_no=doc_no,
        source_type=source_type,
        source_id=int(source_id) if source_id else None,
        decided_by=discipline._uid_int(get_current_user_ctx() or {}),
        decided_at=datetime.utcnow(),
    )
    db.add(version)
    db.flush()
    if _has_column(db, "t_affairs_discipline_case", "current_decision_version_id"):
        db.execute(text("""
            UPDATE t_affairs_discipline_case
               SET current_decision_version_id = :version_id,
                   current_decision_version_no = :version_no
             WHERE tenant_id = :tenant_id AND id = :case_id
        """), {
            "version_id": int(version.id),
            "version_no": int(version.version_no),
            "tenant_id": _tid(),
            "case_id": int(case.id),
        })
    return version


def _set_projection_decision(db, projection_id: int, decision: DisciplineDecisionVersion) -> None:
    if not _has_column(db, "t_cs_discipline", "decision_version_id"):
        return
    db.execute(text("""
        UPDATE t_cs_discipline
           SET decision_version_id = :version_id,
               decision_version_no = :version_no
         WHERE tenant_id = :tenant_id AND id = :projection_id
    """), {
        "version_id": int(decision.id),
        "version_no": int(decision.version_no),
        "tenant_id": _tid(),
        "projection_id": int(projection_id),
    })


def install() -> None:
    global _INSTALLED, _ORIGINAL_SUBMIT_REMOVE
    if _INSTALLED:
        return

    from app.models import (
        CsDiscipline, DisciplineAppeal, DisciplineCase, StudentProfile,
        StudentStageEvent,
    )
    from app.services import affairs_appeal_todo_service as appeal_todo
    from app.services import affairs_discipline_service as discipline
    from app.services import affairs_four_end_contract as contract
    from app.services.message_event_outbox_service import emit_receiver_notice

    old_predicate = contract._is_affairs_mobile_path
    old_row = discipline._row
    old_appeal_row = discipline._appeal_row
    old_message = discipline._msg
    _ORIGINAL_SUBMIT_REMOVE = discipline.submit_remove

    def request_context_path(path: str) -> bool:
        return old_predicate(path) or path.startswith(
            "/api/v1/student-affairs/discipline/appeals/")

    def students_by_ids(db, rows, attr="student_id"):
        ids = {int(getattr(row, attr)) for row in rows if getattr(row, attr, None)}
        if not ids:
            return {}
        students = db.scalars(select(StudentProfile).where(
            StudentProfile.tenant_id == _tid(),
            StudentProfile.id.in_(ids),
            StudentProfile.is_deleted.is_(False),
        )).all()
        return {int(row.id): row for row in students}

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
        data = old_appeal_row(appeal, student)
        data["version"] = int(appeal.version or 0)
        data["allowedActions"] = (
            ["REVIEW"] if appeal.status in ("SUBMITTED", "REVIEWING") else []
        )
        return data

    def message(db, receiver_id, title, content, message_type, biz_id):
        try:
            receiver = int(receiver_id or 0)
        except (TypeError, ValueError):
            receiver = 0
        if receiver <= 0:
            return None
        return old_message(db, receiver, title, content, message_type, biz_id)

    def make_effective(db, case, student):
        existing = db.scalars(select(CsDiscipline).where(
            CsDiscipline.tenant_id == _tid(),
            CsDiscipline.source_case_id == int(case.id),
            CsDiscipline.is_deleted.is_(False),
        ).with_for_update()).first()
        if existing:
            raise AppException(
                "DATA_INCONSISTENT",
                "该处分已存在投影，禁止重复生效，请先执行投影对账",
            )

        cs_student = _ensure_cs_student(db, int(case.student_id))
        decision = _append_decision(
            db,
            case,
            kind="ORIGINAL",
            source_type="APPROVAL",
            source_id=int(case.id),
            disc_type=str(case.disc_type),
            reason=case.reason,
            doc_no=case.doc_no,
        )
        projection = CsDiscipline(
            tenant_id=_tid(),
            cs_student_id=int(cs_student.id),
            disc_type=case.disc_type,
            reason=case.reason,
            decide_date=case.decide_date,
            doc_no=case.doc_no,
            status="EFFECTIVE",
            record_status="ACTIVE",
            source_case_id=case.id,
        )
        db.add(projection)
        db.flush()
        _set_projection_decision(db, int(projection.id), decision)
        case.cs_discipline_id = projection.id
        case.status = "EFFECTIVE"
        case.effective_at = datetime.utcnow()
        case.version = int(case.version or 0) + 1
        db.add(StudentStageEvent(
            tenant_id=_tid(), student_id=int(case.student_id), from_stage=None,
            to_stage="DISCIPLINE_EFFECTIVE",
            reason=f"处分生效（{case.disc_type}）",
            source_module="student-affairs",
        ))
        discipline._todo_done(db, case.id)
        discipline._msg(
            db, case.student_id, "处分决定送达",
            f"你的处分（{case.disc_type}）已生效", "WORKFLOW_RESULT", case.id,
        )
        discipline._audit(
            db, case.id, "EFFECTIVE",
            f"proj={projection.id};decisionVersion={decision.version_no}",
        )

    def submit_appeal(case_id, body, user, *, skip_scope_check=False):
        reason = str(getattr(body, "reason", None) or "").strip()
        if not 5 <= len(reason) <= 1000:
            raise AppException("VALIDATION_ERROR", "申诉理由需5-1000字")
        try:
            with session() as db:
                case, student = _lock_case(db, int(case_id))
                if not skip_scope_check:
                    discipline._scope_or_403(db, case.student_id, user)
                if case.status != "EFFECTIVE":
                    raise AppException("DATA_CONFLICT", "仅已生效处分可申诉")
                appeal_todo.require_submission_assignee(
                    db, "DISCIPLINE_APPEAL_REVIEW", int(case.student_id))
                prior = db.scalars(select(DisciplineAppeal).where(
                    DisciplineAppeal.tenant_id == _tid(),
                    DisciplineAppeal.case_id == int(case_id),
                    DisciplineAppeal.is_deleted.is_(False),
                ).with_for_update()).first()
                if prior:
                    raise AppException("DATA_CONFLICT", "该处分已提交过申诉，不可再次提起")
                appeal = DisciplineAppeal(
                    tenant_id=_tid(), case_id=int(case_id),
                    student_id=case.student_id, reason=reason, status="SUBMITTED",
                )
                db.add(appeal)
                db.flush()
                # 无迁移触发器的 fast-schema 也保留同样的唯一活动子流程语义。
                if not _has_trigger(db, "trg_disc_appeal_ai_pkg11"):
                    db.add(DisciplineSubflowLock(
                        tenant_id=_tid(), case_id=int(case.id),
                        flow_type="APPEAL", flow_id=int(appeal.id),
                    ))
                    db.flush()
                appeal_todo._ensure_todo(db, "DISCIPLINE_APPEAL_REVIEW", appeal)
                discipline._audit(
                    db, case.id, "DISCIPLINE_APPEAL_SUBMIT",
                    f"appeal={appeal.id}",
                )
                db.commit()
                discipline._drain_message_outbox()
                db.refresh(appeal)
                result = appeal_row(appeal, student)
                result["todoSyncStatus"] = "OK"
                return result
        except (DBAPIError, IntegrityError) as exc:
            if _is_subflow_conflict(exc):
                raise AppException(
                    "DATA_CONFLICT", "该处分已有进行中的申诉或解除流程") from exc
            raise

    def review_appeal(appeal_id, body, user):
        result = str(getattr(body, "result", None) or "").strip().upper()
        if result not in ("UPHELD", "REVISED", "REVOKED"):
            raise AppException("VALIDATION_ERROR", "复核结论非法")
        opinion = str(getattr(body, "opinion", None) or "").strip()
        if not 5 <= len(opinion) <= 1000:
            raise AppException("VALIDATION_ERROR", "复核意见需5-1000字")

        raw_body = contract._REQUEST_BODY.get({}) or {}
        revised_type = str(
            getattr(body, "revisedDiscType", None)
            or raw_body.get("revisedDiscType")
            or raw_body.get("targetDiscType")
            or ""
        ).strip().upper()
        revised_reason = str(
            getattr(body, "revisedReason", None)
            or raw_body.get("revisedReason")
            or raw_body.get("targetReason")
            or ""
        ).strip()
        revised_doc_no = (
            getattr(body, "revisedDocNo", None)
            or raw_body.get("revisedDocNo")
            or raw_body.get("targetDocNo")
        )

        with session() as db:
            appeal = db.scalars(select(DisciplineAppeal).where(
                DisciplineAppeal.tenant_id == _tid(),
                DisciplineAppeal.id == int(appeal_id),
                DisciplineAppeal.is_deleted.is_(False),
            ).with_for_update()).first()
            if not appeal:
                raise not_found("申诉不存在")
            discipline._scope_or_403(db, appeal.student_id, user)
            if appeal.status not in ("SUBMITTED", "REVIEWING"):
                raise AppException("APPROVAL_VERSION_CONFLICT", "该申诉已结案")
            discipline.atomic_claim_version(
                db, appeal, getattr(body, "version", None))
            case, student = _lock_case(db, int(appeal.case_id))
            if case.status != "EFFECTIVE":
                raise AppException("DATA_CONFLICT", "原处分已非生效状态，不能重复复核")

            projection = None
            if case.cs_discipline_id:
                projection = db.scalars(select(CsDiscipline).where(
                    CsDiscipline.tenant_id == _tid(),
                    CsDiscipline.id == int(case.cs_discipline_id),
                    CsDiscipline.source_case_id == int(case.id),
                    CsDiscipline.is_deleted.is_(False),
                ).with_for_update()).first()
                if not projection:
                    raise AppException(
                        "DATA_INCONSISTENT", "处分投影回链异常，禁止复核写入")

            decision = None
            if result == "UPHELD":
                title, content = "处分申诉复核完成", "复核结论：维持原处分"
            elif result == "REVISED":
                if revised_type not in discipline.DISC_TYPES:
                    raise AppException(
                        "VALIDATION_ERROR", "变更处分必须提交 revisedDiscType")
                if len(revised_reason) < 5:
                    raise AppException(
                        "VALIDATION_ERROR", "变更后的处分事实不少于5字")
                if not projection or projection.record_status != "ACTIVE":
                    raise AppException(
                        "DATA_CONFLICT", "仅投影正常的生效处分可变更")
                if revised_type == case.disc_type \
                        and revised_reason == (case.reason or "") \
                        and (revised_doc_no or "") == (case.doc_no or ""):
                    raise AppException("DATA_CONFLICT", "变更决定与原决定完全相同")
                before = case.disc_type
                decision = _append_decision(
                    db, case, kind="REVISED", source_type="APPEAL",
                    source_id=int(appeal.id), disc_type=revised_type,
                    reason=revised_reason, doc_no=revised_doc_no,
                )
                case.disc_type = revised_type
                case.reason = revised_reason
                case.doc_no = revised_doc_no
                case.version = int(case.version or 0) + 1
                projection.disc_type = revised_type
                projection.reason = revised_reason
                projection.doc_no = revised_doc_no
                projection.status = "EFFECTIVE"
                projection.record_status = "ACTIVE"
                projection.version = int(projection.version or 0) + 1
                db.flush()
                _set_projection_decision(db, int(projection.id), decision)
                db.add(StudentStageEvent(
                    tenant_id=_tid(), student_id=int(case.student_id), from_stage=None,
                    to_stage="DISCIPLINE_REVISED",
                    reason=f"处分由{before}变更为{revised_type}",
                    source_module="student-affairs",
                ))
                discipline._msg(
                    db, case.student_id, "处分决定已变更",
                    f"处分类型已由{before}变更为{revised_type}",
                    "WORKFLOW_RESULT", case.id,
                )
                title, content = "处分决定已变更", f"处分调整为{revised_type}"
            else:
                if not projection or projection.record_status != "ACTIVE":
                    raise AppException(
                        "DATA_CONFLICT", "原处分投影已非生效状态，不能重复撤销")
                decision = _append_decision(
                    db, case, kind="REVOKED", source_type="APPEAL",
                    source_id=int(appeal.id), disc_type=str(case.disc_type),
                    reason=case.reason, doc_no=case.doc_no,
                )
                case.status = "REVOKED"
                case.removed_at = datetime.utcnow()
                case.version = int(case.version or 0) + 1
                projection.status = "REVOKED"
                projection.record_status = "REVOKED"
                projection.revoke_date = datetime.utcnow()
                projection.revoke_reason = opinion
                projection.version = int(projection.version or 0) + 1
                db.flush()
                _set_projection_decision(db, int(projection.id), decision)
                db.add(StudentStageEvent(
                    tenant_id=_tid(), student_id=int(case.student_id), from_stage=None,
                    to_stage="DISCIPLINE_REVOKED",
                    reason="申诉复核撤销处分决定",
                    source_module="student-affairs",
                ))
                discipline._todo_done(db, case.id)
                discipline._msg(
                    db, case.student_id, "处分决定已撤销",
                    "你的申诉已获支持，原处分决定已撤销",
                    "WORKFLOW_RESULT", case.id,
                )
                title, content = "处分决定已撤销", "原处分决定已撤销"

            appeal.status = result
            appeal.result = result
            appeal.review_opinion = opinion
            appeal.reviewer = discipline._op()[0]
            appeal.reviewed_at = datetime.utcnow()
            appeal.version = int(appeal.version or 0) + 1
            db.flush()
            appeal_todo._ensure_todo(db, "DISCIPLINE_APPEAL_REVIEW", appeal)
            emit_receiver_notice(
                db,
                event_code="DISCIPLINE_APPEAL.RESULT",
                source_module="student-affairs",
                source_biz_type="discipline_appeal",
                source_biz_id=int(appeal.id),
                receiver_id=int(appeal.student_id),
                title=title,
                content=f"{content}；复核意见：{opinion}",
                receiver_as="student",
                dedup_extra=f"result:{result}",
            )
            if not _has_trigger(db, "trg_disc_appeal_au_pkg11"):
                db.execute(text("""
                    DELETE FROM t_affairs_discipline_subflow_lock
                     WHERE tenant_id = :tenant_id AND case_id = :case_id
                       AND flow_type = 'APPEAL' AND flow_id = :flow_id
                """), {
                    "tenant_id": _tid(), "case_id": int(case.id),
                    "flow_id": int(appeal.id),
                })
            discipline._audit(
                db, case.id, "DISCIPLINE_APPEAL_REVIEW",
                f"{result};decisionVersion={decision.version_no if decision else 'UNCHANGED'}",
            )
            db.commit()
            discipline._drain_message_outbox()
            db.refresh(appeal)
            response = appeal_row(appeal, student)
            response["notificationSyncStatus"] = "OK"
            response["decisionVersion"] = (
                int(decision.version_no) if decision else None)
            return response

    def submit_remove(case_id, user, reason="", expected_version=None):
        try:
            return _ORIGINAL_SUBMIT_REMOVE(
                case_id, user, reason, expected_version)
        except (DBAPIError, IntegrityError) as exc:
            if _is_subflow_conflict(exc):
                raise AppException(
                    "DATA_CONFLICT", "该处分已有进行中的申诉或解除流程") from exc
            raise

    def list_decisions(case_id: int, user):
        with session() as db:
            case, _student = _lock_case(db, int(case_id))
            discipline._scope_or_403(db, case.student_id, user)
            rows = db.scalars(select(DisciplineDecisionVersion).where(
                DisciplineDecisionVersion.tenant_id == _tid(),
                DisciplineDecisionVersion.case_id == int(case_id),
            ).order_by(DisciplineDecisionVersion.version_no)).all()
            return [{
                "decisionId": str(row.id),
                "caseId": str(row.case_id),
                "versionNo": int(row.version_no),
                "decisionKind": row.decision_kind,
                "previousVersionId": str(row.previous_version_id or ""),
                "discType": row.disc_type,
                "reason": row.reason or "",
                "docNo": row.doc_no or "",
                "sourceType": row.source_type,
                "sourceId": str(row.source_id or ""),
                "decidedBy": str(row.decided_by or ""),
                "decidedAt": _iso(row.decided_at),
            } for row in rows]

    def projection_reconcile():
        from app.services.affairs_dashboard_service import _allowed_class_ids
        user = get_current_user_ctx() or {}
        with session() as db:
            allowed, _ = _allowed_class_ids(db, user)
            conditions = [
                DisciplineCase.tenant_id == _tid(),
                DisciplineCase.is_deleted.is_(False),
                StudentProfile.tenant_id == _tid(),
                StudentProfile.is_deleted.is_(False),
            ]
            if allowed is not None:
                conditions.append(StudentProfile.class_id.in_(allowed or {-1}))
            case_rows = db.scalars(select(DisciplineCase).join(
                StudentProfile, StudentProfile.id == DisciplineCase.student_id,
            ).where(*conditions)).all()
            case_ids = {int(row.id) for row in case_rows}
            effective = sum(1 for row in case_rows if row.status == "EFFECTIVE")
            projections = int(db.scalar(select(func.count()).select_from(
                CsDiscipline).where(
                    CsDiscipline.tenant_id == _tid(),
                    CsDiscipline.source_case_id.in_(case_ids or {-1}),
                    CsDiscipline.record_status == "ACTIVE",
                    CsDiscipline.is_deleted.is_(False),
                )) or 0)
            return {
                "effectiveCases": effective,
                "activeProjections": projections,
                "consistent": effective == projections,
            }

    contract._is_affairs_mobile_path = request_context_path
    discipline._students_by_ids = students_by_ids
    discipline._cs_student_id = lambda db, student_id: int(
        _ensure_cs_student(db, int(student_id)).id)
    discipline._row = case_row
    discipline._appeal_row = appeal_row
    discipline._make_effective = make_effective
    discipline._msg = message
    discipline.submit_appeal = submit_appeal
    discipline.review_appeal = review_appeal
    discipline.submit_remove = submit_remove
    discipline.list_decision_versions = list_decisions
    discipline.projection_reconcile = projection_reconcile
    discipline.L_DISC["REVOKED"] = "申诉撤销"
    _INSTALLED = True
