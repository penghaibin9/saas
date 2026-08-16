"""D-W3 evaluation submit-only roster/query guard.

The public evaluation service keeps the canonical state machine, anonymity contract and role-task
write path. This guard only tightens the high-fan-in STUDENT submit/read shape:
- trust the current immutable TeachingClass roster version instead of materializing every member;
- preserve latest-selection-batch fail-closed semantics with a compact aggregate query;
- keep EvaluationBatch SHARE -> TeachingClass SHARE -> member UPDATE lock order;
- collapse the SHARE batch + archived-term check into one statement;
- project only the columns needed by the student submit path for task, batch, identity and duplicate
  checks, while legacy/role submissions still delegate to the canonical public implementation.

Full roster materialization/hash verification remains in academic_affairs_roster_consumer_service
for attendance/grade/exam snapshot consumers that actually freeze an entire roster.
"""
from __future__ import annotations

from types import SimpleNamespace

from app.core.exceptions import AppException, no_permission, not_found

_public = None
_original_writable_batch = None
_original_submit_evaluation = None
_canonical_resolve_student = None


def _status(value) -> str:
    return str(value or "").strip().upper()


def _latest_selection_authority(db, teaching_class):
    """Return the latest same-term selection source without loading selection records/members."""
    from sqlalchemy import case, func
    from app.models import AaSelectionBatch, AaSelectionCourse

    tenant_id = _public._tid()
    has_open_course = func.max(
        case((AaSelectionCourse.status == "OPEN", 1), else_=0)
    ).label("has_open_course")
    row = (
        db.query(AaSelectionBatch.id, AaSelectionBatch.status, has_open_course)
        .join(AaSelectionCourse, AaSelectionCourse.batch_id == AaSelectionBatch.id)
        .filter(
            AaSelectionCourse.tenant_id == tenant_id,
            AaSelectionCourse.teaching_task_id == int(teaching_class.teaching_task_id),
            AaSelectionCourse.is_deleted.is_(False),
            AaSelectionBatch.tenant_id == tenant_id,
            AaSelectionBatch.term_id == int(teaching_class.term_id),
            AaSelectionBatch.is_deleted.is_(False),
        )
        .group_by(AaSelectionBatch.id, AaSelectionBatch.status)
        .order_by(AaSelectionBatch.id.desc())
        .first()
    )
    if not row:
        return None
    return {
        "batchId": int(row[0]),
        "status": _status(row[1]),
        "hasOpenCourse": bool(int(row[2] or 0)),
    }


def resolve_submit_roster(db, teaching_task_id: int) -> dict:
    """Resolve only immutable roster metadata needed by one evaluation submit."""
    from app.models import AaTeachingClass, AaTeachingClassRosterVersion

    tenant_id = _public._tid()
    row = (
        db.query(
            AaTeachingClass.id.label("teaching_class_id"),
            AaTeachingClass.teaching_task_id.label("teaching_task_id"),
            AaTeachingClass.term_id.label("term_id"),
            AaTeachingClassRosterVersion.id.label("roster_version_id"),
            AaTeachingClassRosterVersion.version_no.label("roster_version_no"),
            AaTeachingClassRosterVersion.source_type.label("roster_source_type"),
            AaTeachingClassRosterVersion.source_id.label("roster_source_id"),
            AaTeachingClassRosterVersion.roster_hash.label("roster_hash"),
            AaTeachingClassRosterVersion.member_count.label("member_count"),
        )
        .join(
            AaTeachingClassRosterVersion,
            AaTeachingClassRosterVersion.id == AaTeachingClass.current_roster_version_id,
        )
        .filter(
            AaTeachingClass.tenant_id == tenant_id,
            AaTeachingClass.teaching_task_id == int(teaching_task_id),
            AaTeachingClass.roster_status == "LOCKED",
            AaTeachingClass.status == "ACTIVE",
            AaTeachingClass.is_deleted.is_(False),
            AaTeachingClassRosterVersion.tenant_id == tenant_id,
            AaTeachingClassRosterVersion.teaching_class_id == AaTeachingClass.id,
            AaTeachingClassRosterVersion.status == "LOCKED",
            AaTeachingClassRosterVersion.is_deleted.is_(False),
        )
        .first()
    )
    if not row:
        raise AppException(
            "DATA_CONFLICT",
            "正式教学班名单尚未形成锁定版本，禁止提交评教",
            details={"teachingTaskId": str(teaching_task_id)},
            http_status=409,
        )

    teaching_class = SimpleNamespace(
        id=int(row.teaching_class_id),
        teaching_task_id=int(row.teaching_task_id),
        term_id=int(row.term_id),
    )
    selection = _latest_selection_authority(db, teaching_class)
    source_type = str(row.roster_source_type or "")
    source_id = int(row.roster_source_id or 0)
    if selection:
        from .academic_affairs_teaching_roster_service import _SELECTION_FINAL_STATUSES

        if selection["status"] not in _SELECTION_FINAL_STATUSES:
            raise AppException(
                "DATA_CONFLICT",
                "最新选课批次尚未锁定正式名单，禁止使用旧教学班名单提交评教",
                details={
                    "teachingTaskId": str(teaching_task_id),
                    "selectionBatchId": str(selection["batchId"]),
                    "selectionStatus": selection["status"] or "UNKNOWN",
                },
                http_status=409,
            )
        if not selection["hasOpenCourse"]:
            raise AppException(
                "DATA_CONFLICT",
                "最新正式选课批次已取消该教学任务课程供给，禁止提交评教",
                details={
                    "teachingTaskId": str(teaching_task_id),
                    "selectionBatchId": str(selection["batchId"]),
                },
                http_status=409,
            )
        if source_type.upper() != "SELECTION_LOCK" or source_id != int(selection["batchId"]):
            raise AppException(
                "DATA_CONFLICT",
                "教学班当前名单版本与最新已锁定选课批次不一致，请重新执行选课名单投影",
                details={
                    "teachingTaskId": str(teaching_task_id),
                    "selectionBatchId": str(selection["batchId"]),
                    "rosterVersionId": str(row.roster_version_id),
                    "rosterSourceId": str(source_id or ""),
                },
                http_status=409,
            )

    return {
        "ready": True,
        "source": source_type,
        "teachingClassId": str(row.teaching_class_id),
        "rosterVersionId": str(row.roster_version_id),
        "rosterVersionNo": int(row.roster_version_no or 0),
        "rosterHash": str(row.roster_hash or ""),
        "memberCount": int(row.member_count or 0),
        "batchIds": [str(source_id)] if source_type == "SELECTION_LOCK" and source_id else [],
    }


def _resolve_student_hot(db, user):
    """Use the stable studentId as an ID-only lookup; preserve canonical fallbacks otherwise."""
    if not _public._is_student_user(user):
        raise no_permission("学生评教任务仅允许学生本人访问")

    student_id = (user or {}).get("studentId")
    if student_id:
        from app.models import StudentProfile

        row = db.query(StudentProfile.id).filter(
            StudentProfile.id == int(student_id),
            StudentProfile.tenant_id == _public._tid(),
            StudentProfile.is_deleted.is_(False),
        ).first()
        if row:
            return SimpleNamespace(id=int(row[0]))

    profile = _canonical_resolve_student(db, user or {})
    if not profile:
        raise not_found("当前账号尚未绑定唯一学生档案")
    return profile


def _student_submission_context(db, user, task) -> tuple[object, dict, str]:
    if not getattr(task, "teaching_task_id", None):
        raise AppException(
            "DATA_CONFLICT",
            "学生评教任务未绑定正式教学任务",
            http_status=409,
        )

    profile = _resolve_student_hot(db, user)
    roster = resolve_submit_roster(db, int(task.teaching_task_id))
    token = _public._submission_token(int(task.id), int(profile.id))
    return profile, roster, token


def _lock_student_roster_member(db, task, profile, roster) -> None:
    """Preserve canonical lock order while selecting only lock-key columns."""
    from app.models import AaTeachingClass, AaTeachingClassMember

    teaching_class_id = int(roster.get("teachingClassId") or 0)
    roster_version_id = int(roster.get("rosterVersionId") or 0)
    if not teaching_class_id or not roster_version_id:
        raise AppException(
            "DATA_CONFLICT",
            "正式教学班名单缺少版本标识，禁止提交评教",
            http_status=409,
        )

    teaching_class_row = db.query(AaTeachingClass.id).filter(
        AaTeachingClass.id == teaching_class_id,
        AaTeachingClass.tenant_id == _public._tid(),
        AaTeachingClass.teaching_task_id == int(task.teaching_task_id),
        AaTeachingClass.current_roster_version_id == roster_version_id,
        AaTeachingClass.roster_status == "LOCKED",
        AaTeachingClass.status == "ACTIVE",
        AaTeachingClass.is_deleted.is_(False),
    ).with_for_update(read=True).first()
    if not teaching_class_row:
        raise AppException(
            "APPROVAL_VERSION_CONFLICT",
            "正式教学班名单已换版，请刷新后重试",
            details={
                "teachingTaskId": str(task.teaching_task_id),
                "requestedRosterVersionId": str(roster_version_id),
            },
            http_status=409,
        )

    member_row = db.query(AaTeachingClassMember.id).filter(
        AaTeachingClassMember.tenant_id == _public._tid(),
        AaTeachingClassMember.teaching_class_id == teaching_class_id,
        AaTeachingClassMember.roster_version_id == roster_version_id,
        AaTeachingClassMember.student_id == int(profile.id),
        AaTeachingClassMember.status == "ACTIVE",
        AaTeachingClassMember.is_deleted.is_(False),
    ).with_for_update().first()
    if not member_row:
        raise no_permission("当前学生不在该课程当前正式教学班名单中")


def _share_batch_projection(db, batch_id: int):
    """Lock one evaluation batch SHARE while checking archived-term status in the same statement."""
    from sqlalchemy import select
    from app.models import AaEvaluationBatch, AaTerm

    tenant_id = _public._tid()
    term_status = select(AaTerm.status).where(
        AaTerm.id == AaEvaluationBatch.term_id,
        AaTerm.tenant_id == tenant_id,
    ).scalar_subquery()
    row = (
        db.query(
            AaEvaluationBatch.id.label("batch_id"),
            AaEvaluationBatch.term_id.label("term_id"),
            AaEvaluationBatch.anonymous.label("anonymous"),
            AaEvaluationBatch.status.label("status"),
            term_status.label("term_status"),
        )
        .filter(
            AaEvaluationBatch.id == int(batch_id),
            AaEvaluationBatch.tenant_id == tenant_id,
            AaEvaluationBatch.is_deleted.is_(False),
        )
        .with_for_update(read=True)
        .first()
    )
    if not row:
        raise not_found("评教批次不存在")
    if not row.term_id:
        raise AppException("DATA_CONFLICT", "评教业务未绑定正式学期termId", http_status=409)
    if _status(row.term_status) == "ARCHIVED":
        raise AppException("TERM_ARCHIVED", "该学期已归档封存，禁止修改", http_status=409)
    return SimpleNamespace(
        id=int(row.batch_id),
        term_id=int(row.term_id),
        anonymous=bool(row.anonymous),
        status=str(row.status or ""),
    )


def _share_writable_batch(db, batch_id, *, lock: str | None = None):
    """Keep legacy SHARE callers fast without changing UPDATE/no-lock state transitions."""
    if lock != "share":
        return _original_writable_batch(db, batch_id, lock=lock)

    from sqlalchemy import select
    from app.models import AaEvaluationBatch, AaTerm

    tenant_id = _public._tid()
    term_status = select(AaTerm.status).where(
        AaTerm.id == AaEvaluationBatch.term_id,
        AaTerm.tenant_id == tenant_id,
    ).scalar_subquery()
    row = (
        db.query(AaEvaluationBatch, term_status.label("_term_status"))
        .filter(
            AaEvaluationBatch.id == int(batch_id),
            AaEvaluationBatch.tenant_id == tenant_id,
            AaEvaluationBatch.is_deleted.is_(False),
        )
        .populate_existing()
        .with_for_update(read=True)
        .first()
    )
    if not row:
        raise not_found("评教批次不存在")
    batch, current_term_status = row
    if not batch.term_id:
        raise AppException("DATA_CONFLICT", "评教业务未绑定正式学期termId", http_status=409)
    if _status(current_term_status) == "ARCHIVED":
        raise AppException("TERM_ARCHIVED", "该学期已归档封存，禁止修改", http_status=409)
    return batch


def _submit_evaluation(user, task_id, answers, objective_score, comment=None):
    """Student-only minimal-column submit path; all role submissions delegate canonically."""
    if not _public._is_student_user(user):
        return _original_submit_evaluation(user, task_id, answers, objective_score, comment)

    from app.models import AaEvaluationRecord, AaEvaluationTask

    delegate_role_task = False
    with _public.session() as db:
        db.connection(execution_options={"isolation_level": "READ COMMITTED"})
        _public._legacy._ctx(user, db)
        row = db.query(
            AaEvaluationTask.id.label("task_id"),
            AaEvaluationTask.batch_id.label("batch_id"),
            AaEvaluationTask.teaching_task_id.label("teaching_task_id"),
            AaEvaluationTask.teacher_key.label("teacher_key"),
            AaEvaluationTask.evaluator_type.label("evaluator_type"),
        ).filter(
            AaEvaluationTask.id == int(task_id),
            AaEvaluationTask.tenant_id == _public._tid(),
            AaEvaluationTask.is_deleted.is_(False),
        ).first()
        if not row:
            raise not_found("应评任务不存在")
        if _status(row.evaluator_type) != "STUDENT":
            delegate_role_task = True
        else:
            task = SimpleNamespace(
                id=int(row.task_id),
                batch_id=int(row.batch_id),
                teaching_task_id=(int(row.teaching_task_id) if row.teaching_task_id else None),
                teacher_key=row.teacher_key,
                evaluator_type="STUDENT",
            )
            batch = _share_batch_projection(db, task.batch_id)
            if batch.status != _public._legacy._B_OPEN:
                raise _public._legacy._invalid("评教窗口未开放")
            _public._require_anonymous_student_batch(batch)

            profile, roster, token = _student_submission_context(db, user, task)
            _lock_student_roster_member(db, task, profile, roster)
            duplicate = db.query(AaEvaluationRecord.id).filter(
                AaEvaluationRecord.tenant_id == _public._tid(),
                AaEvaluationRecord.task_id == task.id,
                AaEvaluationRecord.evaluator_type == "STUDENT",
                AaEvaluationRecord.answers_json.like(_public._token_pattern(task.id, profile.id)),
                AaEvaluationRecord.is_deleted.is_(False),
            ).first()
            if duplicate:
                raise _public._legacy._invalid("该课程评教已提交，不可重复提交")

            record = AaEvaluationRecord(
                tenant_id=_public._tid(),
                batch_id=batch.id,
                task_id=task.id,
                teacher_key=task.teacher_key,
                evaluator_type="STUDENT",
                answers_json=_public._encode_student_answers(answers, token),
                objective_score=objective_score,
                comment=comment,
            )
            db.add(record)
            _public._anonymous_audit(db, task.id)
            db.flush()
            db.commit()
            return {"taskId": str(task.id), "submitted": True, "submittedCount": None}

    if delegate_role_task:
        return _original_submit_evaluation(user, task_id, answers, objective_score, comment)
    raise RuntimeError("unreachable evaluation submit path")


def install(public_service) -> None:
    global _public, _original_writable_batch, _original_submit_evaluation, _canonical_resolve_student
    _public = public_service

    canonical_resolver = getattr(public_service, "_d_w3_canonical_resolve_student", None)
    if canonical_resolver is None:
        canonical_resolver = public_service._resolve_student
        public_service._d_w3_canonical_resolve_student = canonical_resolver
    _canonical_resolve_student = canonical_resolver
    public_service._resolve_student = _resolve_student_hot
    public_service._student_submission_context = _student_submission_context
    public_service._lock_student_roster_member = _lock_student_roster_member

    canonical_submit = getattr(public_service, "_d_w3_original_submit_evaluation", None)
    if canonical_submit is None:
        canonical_submit = public_service.submit_evaluation
        public_service._d_w3_original_submit_evaluation = canonical_submit
    _original_submit_evaluation = canonical_submit
    public_service.submit_evaluation = _submit_evaluation

    term_facade = public_service._base
    original = getattr(term_facade, "_d_w3_original_writable_batch", None)
    if original is None:
        original = term_facade._writable_batch
        term_facade._d_w3_original_writable_batch = original
    _original_writable_batch = original
    term_facade._writable_batch = _share_writable_batch
    term_facade._d_w3_share_batch_hotpath_installed = True
