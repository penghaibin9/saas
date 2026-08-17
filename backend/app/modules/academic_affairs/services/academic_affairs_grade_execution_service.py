"""Academic C W5 grade execution authority.

Teacher-facing grade execution must follow the *current* formal teaching task owner,
not the teacher_key snapshot copied onto AaGradeTask when it was created.  This
module is deliberately C-owned and small: it does not register routes globally or
own schema/migrations, and it reuses the canonical grade/roster/archive primitives.
"""
from __future__ import annotations

from sqlalchemy import select

from app.core.exceptions import AppException

from . import academic_affairs_grade_core_service as _core
from . import academic_affairs_grade_service as _grade

_EDITABLE = {"NOT_STARTED", "INPUTTING", "RETURNED"}
_SPECIAL_FLAGS = {"NORMAL", "ABSENT", "DEFERRED", "EXEMPT", "CHEAT"}


def _require_live_teacher(db, task, user) -> None:
    """Fail closed against the current AaTeachingTask teacher assignment.

    Review/admin roles keep their existing canonical scope semantics.  A normal
    teacher with a linked teaching task is authorized only by the live teaching
    task row.  Missing/deleted/cross-tenant teaching tasks are a data conflict,
    never a reason to fall back to the stale grade-task snapshot.
    """
    role = str((user or {}).get("currentRoleCode") or "").upper()
    if (
        role in _core._REVIEW_ROLES
        or role == "COLLEGE_ADMIN"
        or (user or {}).get("userType") == "PLATFORM_SUPER_ADMIN"
    ):
        return

    teaching_task_id = getattr(task, "teaching_task_id", None)
    if not teaching_task_id:
        _core._check_course_scope(task, user)
        return

    from app.models import AaTeachingTask

    teaching_task = db.get(AaTeachingTask, int(teaching_task_id))
    if (
        not teaching_task
        or teaching_task.is_deleted
        or teaching_task.tenant_id != _core._tid()
    ):
        raise AppException(
            "DATA_CONFLICT",
            "成绩任务关联的正式教学任务已失效，禁止按历史教师快照继续写入",
            http_status=409,
        )
    if not teaching_task.teacher_key:
        raise AppException(
            "NO_DATA_SCOPE",
            "当前教学任务未绑定任课教师，请联系教务处处理",
            http_status=403,
        )
    if teaching_task.teacher_key not in _core._user_keys(user or {}):
        raise AppException(
            "NO_DATA_SCOPE",
            "任课教师已发生变更，当前账号不再具有该成绩任务写权限",
            http_status=403,
        )


def require_live_teacher(task_id: int, user) -> None:
    """Public preflight for legacy-compatible wrappers."""
    with _core.session() as db:
        task = _grade._load_task(db, int(task_id))
        _require_live_teacher(db, task, user)


def _record_map(db, task_id: int):
    from app.models import AaGradeRecord

    records = db.scalars(
        select(AaGradeRecord).where(
            AaGradeRecord.tenant_id == _core._tid(),
            AaGradeRecord.task_id == int(task_id),
            AaGradeRecord.is_deleted.is_(False),
        )
    ).all()
    return {int(row.student_id): row for row in records}


def _quality_report_in_session(db, task, roster: dict) -> dict:
    roster_items = list(roster.get("items") or [])
    records = _record_map(db, int(task.id))
    issues: list[dict] = []
    missing = 0
    incomplete = 0
    special = 0

    need_usual = int(task.usual_ratio or 0) > 0
    need_midterm = int(getattr(task, "midterm_ratio", 0) or 0) > 0
    need_final = int(task.final_ratio or 0) > 0

    for item in roster_items:
        sid = int(item["studentId"])
        row = records.get(sid)
        identity = {
            "studentId": str(sid),
            "studentNo": item.get("studentNo") or "",
            "realName": item.get("realName") or "",
        }
        if row is None:
            missing += 1
            issues.append({**identity, "code": "MISSING", "message": "尚未录入成绩"})
            continue

        flag = str(row.exception_flag or "NORMAL").upper()
        if flag != "NORMAL":
            special += 1
            continue

        lacks = []
        if need_usual and row.usual_score is None:
            lacks.append("平时")
        if need_midterm and row.midterm_score is None:
            lacks.append("期中")
        if need_final and row.final_score is None:
            lacks.append("期末")
        if lacks:
            incomplete += 1
            issues.append(
                {
                    **identity,
                    "code": "INCOMPLETE",
                    "message": f"{'/'.join(lacks)}成绩未录全",
                }
            )

    roster_count = len(roster_items)
    ready = roster_count > 0 and missing == 0 and incomplete == 0
    if ready:
        summary = f"正式名单{roster_count}人已全部录入，可提交学院审核"
    else:
        summary = (
            f"正式名单{roster_count}人：未录{missing}人，未录全{incomplete}人；"
            "请处理后再提交"
        )
    return {
        "ready": ready,
        "summary": summary,
        "rosterCount": roster_count,
        "missingCount": missing,
        "incompleteCount": incomplete,
        "specialCount": special,
        "issues": issues,
        "rosterSource": roster.get("source"),
        "rosterHash": roster.get("rosterHash"),
        "rosterVersionId": str(roster.get("rosterVersionId") or ""),
    }


def teacher_grade_quality_report(task_id: int, user) -> dict:
    with _core.session() as db:
        task = _grade._load_task(db, int(task_id))
        _require_live_teacher(db, task, user)
        roster = _grade._require_ready_roster(db, task)
        return _quality_report_in_session(db, task, roster)


def _score(raw, label: str):
    if raw in (None, ""):
        return None
    if isinstance(raw, bool):
        raise AppException("VALIDATION_ERROR", f"{label}分须为0-100整数")
    try:
        value = int(raw)
    except (TypeError, ValueError) as exc:
        raise AppException("VALIDATION_ERROR", f"{label}分须为0-100整数") from exc
    if value < 0 or value > 100:
        raise AppException("VALIDATION_ERROR", f"{label}分须为0-100整数")
    return value


def teacher_grade_batch_save(task_id: int, user, rows: list[dict]) -> dict:
    """Save all edited mobile rows in one transaction.

    All validation happens before the first score write.  The grade task is locked,
    the current teaching-task owner is checked in the same session, and every
    student must belong to the current versioned formal roster.
    """
    from app.modules.academic_affairs.services.academic_affairs_archive_service import (
        guard_term_writable,
    )

    rows = list(rows or [])
    if not rows:
        raise AppException("VALIDATION_ERROR", "至少提交一行成绩")
    if len(rows) > 500:
        raise AppException("VALIDATION_ERROR", "单次最多保存500人成绩")

    with _core.session() as db:
        task = _grade._load_task(db, int(task_id), lock=True)
        guard_term_writable(db, task.term_id)
        _require_live_teacher(db, task, user)
        if str(task.status or "").upper() not in _EDITABLE:
            raise AppException("DATA_CONFLICT", "当前状态不可录入（已提交/已发布，如需修改请走成绩更正）")

        roster = _grade._require_ready_roster(db, task)
        roster_ids = {int(value) for value in roster.get("studentIds") or []}
        prepared = []
        seen: set[int] = set()
        for index, raw in enumerate(rows, start=1):
            try:
                sid = int((raw or {}).get("studentId"))
            except (TypeError, ValueError) as exc:
                raise AppException("VALIDATION_ERROR", f"第{index}行 studentId 不合法") from exc
            if sid in seen:
                raise AppException("VALIDATION_ERROR", f"第{index}行学生重复：{sid}")
            if sid not in roster_ids:
                raise AppException("VALIDATION_ERROR", f"第{index}行学生不在当前正式名单：{sid}")
            seen.add(sid)

            flag = str((raw or {}).get("exceptionFlag") or "NORMAL").upper()
            if flag not in _SPECIAL_FLAGS:
                raise AppException("VALIDATION_ERROR", f"第{index}行异常标记非法")
            usual = _score((raw or {}).get("usualScore"), "平时")
            midterm = _score((raw or {}).get("midtermScore"), "期中")
            final = _score((raw or {}).get("finalScore"), "期末")
            prepared.append((sid, usual, midterm, final, flag))

        for sid, usual, midterm, final, flag in prepared:
            _core._write_score_row(
                db,
                task,
                sid,
                usual,
                final,
                flag,
                mid=midterm,
            )

        _core._audit(
            db,
            "AA_GRADE_TASK",
            task.id,
            "MOBILE_BATCH_ENTER",
            f"saved={len(prepared)};roster={roster.get('source')};hash={roster.get('rosterHash')}",
        )
        db.flush()
        report = _quality_report_in_session(db, task, roster)
        db.commit()
        return {
            "saved": len(prepared),
            "status": task.status,
            "rosterVersionId": str(roster.get("rosterVersionId") or ""),
            "rosterHash": roster.get("rosterHash"),
            "qualityReport": report,
        }


def teacher_enter_score(task_id: int, user, body) -> dict:
    """Legacy-compatible single-row entry with a live-owner preflight."""
    require_live_teacher(task_id, user)
    return _grade.enter_score(task_id, user, body)


def teacher_submit_task(task_id: int, user) -> dict:
    """Legacy-compatible submit with live-owner preflight."""
    require_live_teacher(task_id, user)
    return _grade.submit_task(task_id, user)


def teacher_roster(task_id: int, user) -> dict:
    require_live_teacher(task_id, user)
    return _grade.roster(task_id, user)
