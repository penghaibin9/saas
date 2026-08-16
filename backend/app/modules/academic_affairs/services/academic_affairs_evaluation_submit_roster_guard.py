"""D-W3 evaluation submit-only roster/query guard.

The public evaluation service keeps the canonical submit transaction, anonymity token,
duplicate detection and state machine. This guard only tightens the hot read/lock shape:
- trust the current immutable TeachingClass roster version instead of materializing every member;
- preserve latest-selection-batch fail-closed semantics with a compact aggregate query;
- keep the existing TeachingClass SHARE + current member UPDATE lock order, but project only IDs;
- collapse the submission SHARE batch read and archived-term check into one statement.

Full roster materialization/hash verification remains in academic_affairs_roster_consumer_service
for attendance/grade/exam snapshot consumers that actually freeze an entire roster.
"""
from __future__ import annotations

from app.core.exceptions import AppException, no_permission, not_found

_public = None
_original_writable_batch = None


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
    """Resolve only the current immutable roster metadata needed by one evaluation submit."""
    from app.models import AaTeachingClass, AaTeachingClassRosterVersion

    tenant_id = _public._tid()
    row = (
        db.query(AaTeachingClass, AaTeachingClassRosterVersion)
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

    teaching_class, version = row
    selection = _latest_selection_authority(db, teaching_class)
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
        if (
            str(version.source_type or "").upper() != "SELECTION_LOCK"
            or int(version.source_id or 0) != int(selection["batchId"])
        ):
            raise AppException(
                "DATA_CONFLICT",
                "教学班当前名单版本与最新已锁定选课批次不一致，请重新执行选课名单投影",
                details={
                    "teachingTaskId": str(teaching_task_id),
                    "selectionBatchId": str(selection["batchId"]),
                    "rosterVersionId": str(version.id),
                    "rosterSourceId": str(version.source_id or ""),
                },
                http_status=409,
            )

    return {
        "ready": True,
        "source": str(version.source_type or ""),
        "teachingClassId": str(teaching_class.id),
        "rosterVersionId": str(version.id),
        "rosterVersionNo": int(version.version_no or 0),
        "rosterHash": str(version.roster_hash or ""),
        "memberCount": int(version.member_count or 0),
        "batchIds": [str(version.source_id)] if version.source_type == "SELECTION_LOCK" and version.source_id else [],
    }


def _student_submission_context(db, user, task) -> tuple[object, dict, str]:
    if not getattr(task, "teaching_task_id", None):
        raise AppException(
            "DATA_CONFLICT",
            "学生评教任务未绑定正式教学任务",
            http_status=409,
        )

    profile = _public._resolve_student(db, user)
    roster = resolve_submit_roster(db, int(task.teaching_task_id))
    token = _public._submission_token(int(task.id), int(profile.id))
    return profile, roster, token


def _lock_student_roster_member(db, task, profile, roster) -> None:
    """Preserve the canonical lock order while selecting only lock-key columns."""
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


def _share_writable_batch(db, batch_id, *, lock: str | None = None):
    """Collapse SHARE batch + archived-term guard into one SQL statement.

    UPDATE/no-lock callers keep the exact original implementation. The scalar term subquery is a
    non-locking read, matching the old guard_term_writable semantics while avoiding one round trip
    per high-frequency submission/appeal SHARE transaction.
    """
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


def install(public_service) -> None:
    global _public, _original_writable_batch
    _public = public_service
    public_service._student_submission_context = _student_submission_context
    public_service._lock_student_roster_member = _lock_student_roster_member

    term_facade = public_service._base
    original = getattr(term_facade, "_d_w3_original_writable_batch", None)
    if original is None:
        original = term_facade._writable_batch
        term_facade._d_w3_original_writable_batch = original
    _original_writable_batch = original
    term_facade._writable_batch = _share_writable_batch
    term_facade._d_w3_share_batch_hotpath_installed = True
