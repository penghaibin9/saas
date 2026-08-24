"""AA-05 teacher grade write transaction guard.

The teacher execution adapter validates the *live* AaTeachingTask owner. Older code delegated the
actual score/submit write to ``academic_affairs_grade_service`` while still holding a row lock in a
different Session. Canonical roster resolution may synchronise teaching-class facts, so the nested
Session can wait on the outer transaction until the browser request times out.

This guard keeps the existing permission/state/roster/workflow rules but performs teacher score writes
and ordinary teaching-task submits in one MySQL transaction. It does not relax authorization, deadline,
roster, workflow, audit or browser timeout rules.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import select

from app.core.exceptions import AppException

from . import academic_affairs_grade_core_service as _core
from . import academic_affairs_grade_execution_service as _exec
from . import academic_affairs_grade_service as _grade

_INSTALLED = False


def _enter_score_single_session(task_id: int, user, body) -> dict:
    from app.models import AaGradeRecord
    from app.modules.academic_affairs.services.academic_affairs_archive_service import (
        guard_term_writable,
    )

    with _core.session() as db:
        task = _grade._load_task(db, int(task_id), lock=True)
        guard_term_writable(db, task.term_id)
        _exec._require_live_teacher(db, task, user, lock_owner=True)
        delegated_user = _exec._canonical_scope_user(task, user)
        _core._check_course_scope(task, delegated_user)
        if str(task.status or "").upper() not in _exec._EDITABLE:
            raise AppException(
                "DATA_CONFLICT",
                "当前状态不可录入（已提交/已发布，如需修改请走成绩更正）",
            )

        roster = _grade._require_ready_roster(db, task)
        try:
            student_id = int(_grade._body_value(body, "studentId"))
        except (TypeError, ValueError) as exc:
            raise AppException("VALIDATION_ERROR", "studentId必填且须为有效数字") from exc
        roster_ids = {int(value) for value in roster.get("studentIds") or []}
        if student_id not in roster_ids:
            raise AppException("VALIDATION_ERROR", "该学生不在当前教学任务正式名单中")

        record = db.scalars(
            select(AaGradeRecord).where(
                AaGradeRecord.tenant_id == _core._tid(),
                AaGradeRecord.task_id == task.id,
                AaGradeRecord.student_id == student_id,
                AaGradeRecord.is_deleted.is_(False),
            )
        ).first()
        if not record:
            record = AaGradeRecord(
                tenant_id=_core._tid(),
                task_id=task.id,
                student_id=student_id,
            )
            db.add(record)

        fields = _grade._body_fields(body)
        if isinstance(body, dict):
            fields = set(body)
        clear_usual = bool(_grade._body_value(body, "clearUsual", False))
        clear_midterm = bool(_grade._body_value(body, "clearMidterm", False))
        clear_final = bool(_grade._body_value(body, "clearFinal", False))
        if clear_usual:
            fields.add("usualScore")
        if clear_midterm:
            fields.add("midtermScore")
        if clear_final:
            fields.add("finalScore")

        usual = record.usual_score
        midterm = record.midterm_score
        final = record.final_score
        if "usualScore" in fields:
            usual = None if clear_usual else _grade._strict_score(
                _grade._body_value(body, "usualScore"), "平时"
            )
        if "midtermScore" in fields:
            midterm = None if clear_midterm else _grade._strict_score(
                _grade._body_value(body, "midtermScore"), "期中"
            )
        if "finalScore" in fields:
            final = None if clear_final else _grade._strict_score(
                _grade._body_value(body, "finalScore"), "期末"
            )

        if "exceptionFlag" in fields:
            flag = str(_grade._body_value(body, "exceptionFlag") or "NORMAL").strip().upper()
        else:
            flag = str(record.exception_flag or "NORMAL").upper()
        if flag not in _exec._SPECIAL_FLAGS:
            raise AppException("VALIDATION_ERROR", "异常标记非法")

        total = None
        if flag == "NORMAL":
            if _core._scores_complete(task, usual, midterm, final):
                total = _core._compose_total(task, usual, midterm, final)
        else:
            usual = midterm = final = None

        record.usual_score = usual
        record.midterm_score = midterm
        record.final_score = final
        record.total_score = total
        record.exception_flag = flag
        record.pass_status = (
            "PASSED"
            if total is not None and total >= int(task.pass_line or 60)
            else "FAILED" if total is not None else None
        )
        if task.status == "NOT_STARTED":
            task.status = "INPUTTING"

        db.flush()
        _core._audit(
            db,
            "AA_GRADE_TASK",
            task.id,
            "ENTER",
            f"student={student_id};roster={roster.get('source')}",
        )
        db.commit()
        return {
            "recordId": str(record.id),
            "studentId": str(student_id),
            "usualScore": usual,
            "midtermScore": midterm,
            "finalScore": final,
            "totalScore": total,
            "passStatus": record.pass_status,
            "exceptionFlag": flag,
        }


def _submit_task_single_session(task_id: int, user) -> dict:
    """Submit one teacher-owned grade task without a nested Session.

    The canonical submit semantics are intentionally kept in lock-step with
    ``academic_affairs_grade_service.submit_task``. The only execution-layer addition is the live
    teacher pin and canonical-scope compatibility inside the *same* Session as roster freezing and the
    workflow transition.
    """
    from app.models import AaGradeRecord, AaGradeTask, WorkflowInstance, WorkflowTask
    from app.modules.academic_affairs.services.academic_affairs_archive_service import (
        guard_term_writable,
    )
    from app.modules.academic_affairs.services.academic_affairs_grade_task_assignee_guard import (
        resolve_grade_task_assignee,
    )
    from app.services.runtime_preset_install_service import ensure_workflow_enabled

    with _core.session() as db:
        task = _grade._load_task(db, int(task_id), lock=True)
        guard_term_writable(db, task.term_id)
        _exec._require_live_teacher(db, task, user, lock_owner=True)
        delegated_user = _exec._canonical_scope_user(task, user)
        _core._check_course_scope(task, delegated_user)

        if task.status not in {"INPUTTING", "RETURNED"}:
            raise AppException("DATA_CONFLICT", "当前状态不可提交")
        was_returned = task.status == "RETURNED"
        if not task.teaching_task_id:
            raise AppException(
                "DATA_CONFLICT",
                "管理员特殊补录不可走普通教学任务提交链；请使用补录复核专用流程",
                http_status=409,
            )

        data = _grade.resolve_versioned_roster(db, int(task.teaching_task_id))
        roster_ids = {int(value) for value in data.get("studentIds") or []}
        if not roster_ids:
            raise AppException("DATA_CONFLICT", "正式教学名单为空，不可提交成绩任务", http_status=409)

        records = db.scalars(
            select(AaGradeRecord).where(
                AaGradeRecord.tenant_id == _core._tid(),
                AaGradeRecord.task_id == task.id,
                AaGradeRecord.is_deleted.is_(False),
            )
        ).all()
        record_ids = {int(row.student_id) for row in records}
        missing = sorted(roster_ids - record_ids)
        extra = sorted(record_ids - roster_ids)
        if missing or extra:
            raise AppException(
                "DATA_CONFLICT",
                f"成绩名单不一致：未录 {len(missing)} 人，名单外记录 {len(extra)} 人",
                details={
                    "rosterSource": data.get("source"),
                    "rosterVersionId": str(data.get("rosterVersionId") or ""),
                    "missingStudentIds": [str(value) for value in missing],
                    "extraStudentIds": [str(value) for value in extra],
                },
                http_status=409,
            )
        incomplete = [
            row
            for row in records
            if row.total_score is None and str(row.exception_flag or "NORMAL").upper() == "NORMAL"
        ]
        if incomplete:
            raise AppException("DATA_CONFLICT", f"仍有 {len(incomplete)} 名学生成绩未录全，不可提交")

        snapshot = _grade.freeze_consumer_snapshot(
            db,
            "GRADE_TASK",
            int(task.id),
            int(task.teaching_task_id),
            roster=data,
            allow_replace=was_returned,
            replace_reason="成绩任务退回后按当前正式名单重新提交" if was_returned else "",
        )
        claimed = (
            db.query(AaGradeTask)
            .filter(
                AaGradeTask.id == task.id,
                AaGradeTask.tenant_id == _core._tid(),
                AaGradeTask.status.in_(["INPUTTING", "RETURNED"]),
            )
            .update({AaGradeTask.status: "SUBMITTED"}, synchronize_session=False)
        )
        if not claimed:
            db.rollback()
            raise AppException("APPROVAL_VERSION_CONFLICT", "成绩任务已提交或状态已变化", http_status=409)
        task.status = "SUBMITTED"

        _name, _role, user_id = _core._op()
        ensure_workflow_enabled(db, _core._tid(), _core._WF_SUBMIT)
        instance = WorkflowInstance(
            tenant_id=_core._tid(),
            workflow_code=_core._WF_SUBMIT,
            source_module="academic-affairs",
            source_biz_type="AA_GRADE_TASK",
            source_biz_id=task.id,
            applicant_id=int(user_id) if str(user_id).isdigit() else 0,
            title=f"{task.course_name or ''} 成绩审核",
            status="RUNNING",
            current_node="COLLEGE_REVIEW",
        )
        db.add(instance)
        db.flush()
        db.add(
            WorkflowTask(
                tenant_id=_core._tid(),
                instance_id=instance.id,
                node_code="COLLEGE_REVIEW",
                assignee_id=resolve_grade_task_assignee(db, "COLLEGE_REVIEW", task),
                status="PENDING",
            )
        )
        task.workflow_instance_id = instance.id
        task.submitted_at = datetime.utcnow()
        _core._todo_done_grade_entry(db, task.id)
        _core._audit(
            db,
            "AA_GRADE_TASK",
            task.id,
            "SUBMIT",
            (
                f"students={len(roster_ids)};teachingClassId={snapshot['teachingClassId']};"
                f"rosterVersionId={snapshot['rosterVersionId']};snapshotVersion={snapshot['snapshotVersion']}"
            ),
        )
        db.commit()
        return {
            "gradeTaskId": str(task.id),
            "status": "SUBMITTED",
            "studentCount": len(roster_ids),
            "rosterIdentity": snapshot,
        }


def install() -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    _exec.teacher_enter_score = _enter_score_single_session
    _enter_score_single_session.__grade_single_session_guard__ = True
    _exec.teacher_submit_task = _submit_task_single_session
    _submit_task_single_session.__grade_single_session_guard__ = True
    _INSTALLED = True
