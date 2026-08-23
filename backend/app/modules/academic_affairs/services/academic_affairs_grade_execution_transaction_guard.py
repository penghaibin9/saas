"""AA-05 teacher grade write transaction guard.

The teacher execution adapter validates the *live* AaTeachingTask owner.  Older
code delegated the actual score write to ``academic_affairs_grade_service`` while
still holding a row lock in a different Session.  Canonical roster resolution may
synchronise teaching-class facts, so the nested Session can wait on the outer
transaction until the browser request times out.

This guard keeps the existing permission/state/roster rules but performs a single
row score write in one MySQL transaction: GradeTask lock -> term guard -> live
teacher pin -> canonical snapshot-scope compatibility -> authoritative roster ->
GradeRecord mutation -> audit -> commit.
"""
from __future__ import annotations

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


def install() -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    _exec.teacher_enter_score = _enter_score_single_session
    _enter_score_single_session.__grade_single_session_guard__ = True
    _INSTALLED = True
