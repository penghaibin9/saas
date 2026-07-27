"""移动教务单一公开入口。

复用原移动教务 Service 的其余能力，集中收口稳定教师身份、当前学期课表、
学生考务读取、稳定成绩身份、教师微信批量成绩保存和提交质量门禁。
本模块不修改其它模块函数对象。
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime

from sqlalchemy import select

from app.core.affairs_security import _derive_keys
from app.core.exceptions import AppException, no_permission, not_found
from app.services.db_service import _tid

from . import mobile_academic_affairs_service as _legacy

_ALLOWED_FLAGS = {"NORMAL", "ABSENT", "DEFERRED", "EXEMPT", "CHEAT"}
_EDITABLE_STATUSES = {"NOT_STARTED", "INPUTTING", "RETURNED"}


def __getattr__(name):
    return getattr(_legacy, name)


def stable_teacher_keys(user) -> set[str]:
    return set(_derive_keys(user or {}))


def stable_teacher_key(user) -> str:
    user = user or {}
    login = str(user.get("loginName") or "").strip()
    if login:
        return login
    context_id = str(user.get("activeContextId") or "").strip()
    if context_id.startswith("ctx_") and len(context_id) > 4:
        return context_id[4:]
    uid = str(user.get("userId") or "").strip()
    if uid.startswith("u_") and len(uid) > 2:
        return uid[2:]
    return uid


def _current_term_and_batch(db):
    from app.models import AaScheduleBatch, AaTerm

    term = db.scalars(select(AaTerm).where(
        AaTerm.tenant_id == _tid(),
        AaTerm.is_current.is_(True),
        AaTerm.is_deleted.is_(False),
    )).first()
    if not term:
        return None, None
    batch = db.scalars(select(AaScheduleBatch).where(
        AaScheduleBatch.tenant_id == _tid(),
        AaScheduleBatch.term_id == term.id,
        AaScheduleBatch.status == "PUBLISHED",
        AaScheduleBatch.is_deleted.is_(False),
    ).order_by(
        AaScheduleBatch.publish_at.desc(),
        AaScheduleBatch.id.desc(),
    )).first()
    return term, batch


def teaching_week_from_dates(start_date, today):
    if not start_date or not today:
        return None
    start = start_date.date() if isinstance(start_date, datetime) else start_date
    current = today.date() if isinstance(today, datetime) else today
    if current < start:
        return 0
    return ((current - start).days // 7) + 1


def _current_teaching_week(db, term, now=None):
    from app.modules.academic_affairs.services.student_exam_read_service import _tenant_timezone

    if not term or not term.start_date:
        return None, None
    zone, zone_name = _tenant_timezone(db)
    current = now or datetime.now(zone)
    if current.tzinfo is None:
        current = current.replace(tzinfo=zone)
    return teaching_week_from_dates(
        term.start_date,
        current.astimezone(zone).date(),
    ), zone_name


def _value(row, name, default=None):
    if isinstance(row, dict):
        return row.get(name, default)
    return getattr(row, name, default)


def _as_date(value):
    if value is None:
        return None
    return value.date() if isinstance(value, datetime) else value


def resolve_schedule_time_bands(slots, bands, on_date) -> list[dict]:
    current = _as_date(on_date)
    output = []
    for slot in sorted(slots or [], key=lambda row: int(_value(row, "slot_no", 0) or 0)):
        if not bool(_value(slot, "enabled", True)):
            continue
        if str(_value(slot, "status", "ENABLED") or "ENABLED").upper() == "DISABLED":
            continue
        slot_id = int(_value(slot, "id", 0) or 0)
        slot_no = int(_value(slot, "slot_no", 0) or 0)
        active = []
        for band in bands or []:
            if int(_value(band, "slot_id", 0) or 0) != slot_id:
                continue
            if str(_value(band, "status", "ENABLED") or "ENABLED").upper() != "ENABLED":
                continue
            start = _as_date(_value(band, "effective_start"))
            end = _as_date(_value(band, "effective_end"))
            if current and start and current < start:
                continue
            if current and end and current > end:
                continue
            active.append(band)
        if active:
            active.sort(key=lambda row: (
                str(_value(row, "campus_code", "") or ""),
                _as_date(_value(row, "effective_start")) or current,
                int(_value(row, "id", 0) or 0),
            ))
            for band in active:
                output.append({
                    "slotNo": slot_no,
                    "slotName": _value(slot, "slot_name") or f"第{slot_no}节",
                    "startTime": _value(band, "start_time") or _value(slot, "start_time") or "",
                    "endTime": _value(band, "end_time") or _value(slot, "end_time") or "",
                    "bandName": _value(band, "band_name") or "",
                    "campusCode": _value(band, "campus_code") or _value(slot, "campus_code") or "",
                    "source": "TIME_BAND",
                })
        else:
            output.append({
                "slotNo": slot_no,
                "slotName": _value(slot, "slot_name") or f"第{slot_no}节",
                "startTime": _value(slot, "start_time") or "",
                "endTime": _value(slot, "end_time") or "",
                "bandName": "",
                "campusCode": _value(slot, "campus_code") or "",
                "source": "TIME_SLOT",
            })
    return output


def _schedule_time_bands(db, now=None) -> list[dict]:
    from app.models import AaClassTimeBand, AaTimeSlot
    from app.modules.academic_affairs.services.student_exam_read_service import _tenant_timezone

    zone, _zone_name = _tenant_timezone(db)
    current = now or datetime.now(zone)
    if current.tzinfo is None:
        current = current.replace(tzinfo=zone)
    slots = db.scalars(select(AaTimeSlot).where(
        AaTimeSlot.tenant_id == _tid(),
        AaTimeSlot.is_deleted.is_(False),
    )).all()
    bands = db.scalars(select(AaClassTimeBand).where(
        AaClassTimeBand.tenant_id == _tid(),
        AaClassTimeBand.is_deleted.is_(False),
    )).all()
    return resolve_schedule_time_bands(
        slots,
        bands,
        current.astimezone(zone).date(),
    )


def _schedule_meta(db, term, batch):
    current_week, timezone_name = _current_teaching_week(db, term)
    return {
        "batchId": str(batch.id) if batch else "",
        "termId": str(term.id) if term else "",
        "termCode": f"{term.year_code}-{term.term_no}" if term else "",
        "currentWeek": current_week,
        "teachingWeeks": getattr(term, "teaching_weeks", None) if term else None,
        "timezone": timezone_name,
        "timeBands": _schedule_time_bands(db) if term else [],
    }


def schedule_my(user) -> dict:
    from app.modules.academic_affairs.services import academic_affairs_schedule_service as schedule

    with _legacy.session() as db:
        student = _legacy._me(db, user)
        term, batch = _current_term_and_batch(db)
        meta = _schedule_meta(db, term, batch)
        student_id = student.id
    if not term:
        return {**meta, "items": [], "note": "学校尚未设置当前学期"}
    if not batch:
        return {**meta, "items": [], "note": "当前学期暂无已发布课表"}
    data = schedule.student_view(batch.id, user, student_id)
    return {**meta, **data}


def teacher_schedule_my(user) -> dict:
    from app.modules.academic_affairs.services import academic_affairs_schedule_service as schedule

    if (user or {}).get("userType") == "STUDENT":
        raise no_permission("该接口仅教职工可用")
    teacher_key = stable_teacher_key(user)
    if not teacher_key:
        raise no_permission("当前教师账号缺少稳定工号，请联系管理员")
    with _legacy.session() as db:
        term, batch = _current_term_and_batch(db)
        meta = _schedule_meta(db, term, batch)
    if not term:
        return {**meta, "items": [], "note": "学校尚未设置当前学期"}
    if not batch:
        return {**meta, "items": [], "note": "当前学期暂无已发布课表"}
    data = schedule.teacher_view(batch.id, user, teacher_key)
    return {**meta, **data}


def teacher_attendance_class_options(user) -> dict:
    from app.models import AaTeachingTask, AaTeachingTaskBatch, AaTerm, SchoolClass

    if (user or {}).get("userType") == "STUDENT":
        raise no_permission("该接口仅教职工可用")
    role = str((user or {}).get("currentRoleCode") or "").upper()
    keys = stable_teacher_keys(user)
    if role not in {"ACADEMIC_ADMIN", "SCHOOL_ADMIN"} and not keys:
        return {"items": [], "hasData": False, "note": "当前账号缺少稳定教师工号"}

    with _legacy.session() as db:
        current_term = db.scalars(select(AaTerm).where(
            AaTerm.tenant_id == _tid(),
            AaTerm.is_current.is_(True),
            AaTerm.is_deleted.is_(False),
        )).first()
        if not current_term:
            return {"items": [], "hasData": False, "note": "当前学校尚未设置当前学期"}

        conditions = [
            AaTeachingTask.tenant_id == _tid(),
            AaTeachingTask.is_deleted.is_(False),
            AaTeachingTask.status.notin_(["PENDING_ASSIGN", "REJECTED_BY_TEACHER", "MERGED"]),
            AaTeachingTask.class_id.is_not(None),
        ]
        if role not in {"ACADEMIC_ADMIN", "SCHOOL_ADMIN"}:
            conditions.append(AaTeachingTask.teacher_key.in_(sorted(keys)))
        tasks = db.scalars(select(AaTeachingTask).where(*conditions)).all()

        items = []
        for task in tasks:
            batch = db.get(AaTeachingTaskBatch, int(task.batch_id))
            if not batch or batch.is_deleted or batch.tenant_id != _tid():
                continue
            if int(batch.term_id or 0) != int(current_term.id):
                continue
            school_class = db.get(SchoolClass, int(task.class_id))
            if not school_class or school_class.is_deleted or school_class.tenant_id != _tid():
                continue
            items.append({
                "teachingTaskId": str(task.id),
                "classId": str(school_class.id),
                "className": school_class.class_name,
                "grade": school_class.grade or "",
                "courseName": task.course_name or "",
                "teacherKey": task.teacher_key or "",
                "termId": str(current_term.id),
                "termCode": f"{current_term.year_code}-{current_term.term_no}",
                "taskStatus": task.status,
                "source": "TEACHING_TASK",
            })
        items.sort(key=lambda item: (
            item["courseName"],
            item["className"],
            int(item["teachingTaskId"]),
        ))
        return {
            "items": items,
            "hasData": bool(items),
            "termId": str(current_term.id),
            "termCode": f"{current_term.year_code}-{current_term.term_no}",
            "note": "仅展示当前学期本人真实教学任务",
        }


def exam_my(user) -> dict:
    from . import student_exam_read_service as safe_exam
    return safe_exam.exam_my(user)


def exam_defer_options_my(user) -> dict:
    from . import student_exam_read_service as safe_exam
    return safe_exam.deferrable_courses(user)


def exam_defer_apply_my(user, body) -> dict:
    from . import student_exam_read_service as safe_exam

    if not isinstance(body, dict):
        body = vars(body) if body is not None and hasattr(body, "__dict__") else {}
    return safe_exam.defer_apply(user, body or {})


def _identity_options(user) -> dict:
    from app.models import AcademicGrade
    from app.modules.academic_affairs.services import academic_affairs_grade_service as grade_service
    from app.modules.academic_affairs.services import mobile_academic_gaps_service as gaps

    with _legacy.session() as db:
        student = _legacy._me(db, user)
        academic_student = gaps._best_grades_for_me(db, student)[1]
        if not academic_student:
            return {
                "retakeOptions": [],
                "exemptionOptions": [],
                "retakeTotal": 0,
                "exemptionTotal": 0,
                "identityDebtCount": 0,
                "note": "尚未建立学业成绩台账",
            }
        rows = db.query(AcademicGrade).filter(
            AcademicGrade.tenant_id == _legacy._tid(),
            AcademicGrade.acad_student_id == academic_student.id,
            AcademicGrade.record_status == "ACTIVE",
            AcademicGrade.is_deleted.is_(False),
        ).all()
        effective = grade_service.effective_grade_rows(rows)
        retakes, exemptions, debts = [], [], []
        for row in effective:
            identity_ready = bool(
                row.course_id
                and row.course_code
                and row.course_version
                and row.attempt_no
            )
            item = {
                "gradeId": str(row.id),
                "courseId": str(row.course_id or ""),
                "courseCode": row.course_code or "",
                "courseVersion": int(row.course_version or 0) or None,
                "attemptNo": int(row.attempt_no or 0) or None,
                "courseName": row.course_name,
                "termCode": row.term or "",
                "score": row.score,
                "credit": float(row.credit_value or 0),
                "passStatus": row.pass_status,
                "identityReady": identity_ready,
            }
            status = str(row.pass_status or "").upper()
            if status in {"FAIL", "FAILED"}:
                (retakes if identity_ready else debts).append(item)
                if identity_ready:
                    exemptions.append(item)
            elif status != "PASSED":
                (exemptions if identity_ready else debts).append(item)
        key = lambda item: (
            item.get("termCode") or "",
            item.get("courseCode") or "",
            int(item.get("attemptNo") or 0),
        )
        retakes.sort(key=key)
        exemptions.sort(key=key)
        return {
            "retakeOptions": retakes,
            "exemptionOptions": exemptions,
            "retakeTotal": len(retakes),
            "exemptionTotal": len(exemptions),
            "identityDebtCount": len(debts),
            "identityDebtItems": debts[:50],
            "note": (
                f"有{len(debts)}条历史成绩缺少课程身份，暂不能用于重修或免修"
                if debts else "请从稳定课程身份候选中选择"
            ),
        }


def makeup_options_my(user) -> dict:
    return _identity_options(user)


def retake_apply_my(user, body) -> dict:
    from app.modules.academic_affairs.services import academic_affairs_makeup_service as makeup

    payload = body or {}
    grade_id = payload.get("gradeId")
    if not grade_id:
        raise AppException("VALIDATION_ERROR", "请从本人当前有效挂科成绩选择gradeId")
    options = {
        str(item["gradeId"]): item
        for item in _identity_options(user)["retakeOptions"]
    }
    if str(grade_id) not in options:
        raise AppException(
            "APPROVAL_VERSION_CONFLICT",
            "所选挂科成绩已失效，请刷新候选列表",
            http_status=409,
        )
    return makeup.retake_apply(user, _legacy._ns({
        "gradeId": int(grade_id),
        "termCode": payload.get("termCode"),
        "reason": payload.get("reason"),
    }))


def exemption_apply_my(user, body) -> dict:
    from app.modules.academic_affairs.services import academic_affairs_makeup_service as makeup

    payload = body or {}
    course_id = payload.get("courseId")
    if not course_id:
        raise AppException("VALIDATION_ERROR", "请从可申请课程选择courseId")
    options = {
        str(item["courseId"]): item
        for item in _identity_options(user)["exemptionOptions"]
    }
    if str(course_id) not in options:
        raise AppException(
            "APPROVAL_VERSION_CONFLICT",
            "所选课程已不满足免修候选条件，请刷新",
            http_status=409,
        )
    return makeup.exemption_apply(user, _legacy._ns({
        "courseId": int(course_id),
        "termCode": payload.get("termCode"),
        "reason": payload.get("reason"),
        "materialFileIds": payload.get("materialFileIds") or [],
    }))


def recognition_submit_my(user, body) -> dict:
    from app.modules.academic_affairs.services import academic_affairs_recognition_service as recognition

    payload = body or {}
    if not payload.get("sourceCourseName"):
        raise AppException("VALIDATION_ERROR", "原课程名称必填")
    if not payload.get("targetCourseId"):
        raise AppException(
            "VALIDATION_ERROR",
            "目标课程必须选择课程库具体targetCourseId",
        )
    return recognition.submit(user, _legacy._ns(payload))


def _score(value, label: str):
    if value in (None, ""):
        return None
    if isinstance(value, bool):
        raise AppException("VALIDATION_ERROR", f"{label}成绩须为0-100整数")
    try:
        numeric = float(value)
    except (TypeError, ValueError) as exc:
        raise AppException("VALIDATION_ERROR", f"{label}成绩须为0-100整数") from exc
    if not numeric.is_integer() or numeric < 0 or numeric > 100:
        raise AppException("VALIDATION_ERROR", f"{label}成绩须为0-100整数")
    return int(numeric)


def normalize_mobile_grade_row(row: dict) -> dict:
    payload = dict(row or {})
    student_id = payload.get("studentId")
    try:
        student_id = int(student_id)
    except (TypeError, ValueError) as exc:
        raise AppException(
            "VALIDATION_ERROR",
            "studentId 必填且须为有效数字",
        ) from exc
    if student_id <= 0:
        raise AppException("VALIDATION_ERROR", "studentId 必填且须为有效数字")
    flag = str(payload.get("exceptionFlag") or "NORMAL").strip().upper()
    if flag not in _ALLOWED_FLAGS:
        raise AppException("VALIDATION_ERROR", "异常标记非法")
    usual = _score(payload.get("usualScore"), "平时")
    midterm = _score(payload.get("midtermScore"), "期中")
    final = _score(payload.get("finalScore"), "期末")
    if flag != "NORMAL":
        usual = midterm = final = None
    return {
        "studentId": student_id,
        "usualScore": usual,
        "midtermScore": midterm,
        "finalScore": final,
        "exceptionFlag": flag,
    }


def build_grade_quality_report(
    roster_items,
    record_items,
    *,
    usual_ratio=0,
    midterm_ratio=0,
    final_ratio=0,
    status="",
) -> dict:
    roster = list(roster_items or [])
    records = list(record_items or [])
    record_by_student = {
        str(row.get("studentId")): row
        for row in records
        if row.get("studentId") not in (None, "")
    }
    roster_ids = {
        str(row.get("studentId"))
        for row in roster
        if row.get("studentId") not in (None, "")
    }
    issues = []
    complete_normal = 0
    special = Counter()
    pass_count = 0
    fail_count = 0
    recorded_count = 0
    missing_count = 0
    incomplete_count = 0
    required_parts = []
    if int(usual_ratio or 0) > 0:
        required_parts.append(("usualScore", "平时分"))
    if int(midterm_ratio or 0) > 0:
        required_parts.append(("midtermScore", "期中分"))
    if int(final_ratio or 0) > 0:
        required_parts.append(("finalScore", "期末分"))

    for student in roster:
        sid = str(student.get("studentId") or "")
        record = record_by_student.get(sid)
        identity = {
            "studentId": sid,
            "studentNo": student.get("studentNo") or "",
            "realName": student.get("realName") or student.get("studentName") or "",
        }
        if not record:
            missing_count += 1
            issues.append({
                **identity,
                "code": "NOT_RECORDED",
                "message": "尚未录入成绩或特殊状态",
            })
            continue
        recorded_count += 1
        flag = str(record.get("exceptionFlag") or "NORMAL").upper()
        if flag != "NORMAL":
            special[flag] += 1
            continue
        missing_parts = [
            label
            for key, label in required_parts
            if record.get(key) in (None, "")
        ]
        if missing_parts or record.get("totalScore") in (None, ""):
            incomplete_count += 1
            issues.append({
                **identity,
                "code": "INCOMPLETE",
                "message": (
                    "、".join(missing_parts) + "未填写"
                    if missing_parts else "总评尚未生成"
                ),
            })
            continue
        complete_normal += 1
        pass_status = str(record.get("passStatus") or "").upper()
        if pass_status == "PASSED":
            pass_count += 1
        elif pass_status in {"FAIL", "FAILED"}:
            fail_count += 1

    extra_ids = sorted(set(record_by_student) - roster_ids)
    for sid in extra_ids:
        record = record_by_student[sid]
        issues.append({
            "studentId": sid,
            "studentNo": record.get("studentNo") or "",
            "realName": record.get("realName") or record.get("studentName") or "",
            "code": "OUTSIDE_ROSTER",
            "message": "存在名单外成绩记录，请联系教务处核对名单版本",
        })

    roster_count = len(roster)
    ready = (
        bool(roster_count)
        and missing_count == 0
        and incomplete_count == 0
        and not extra_ids
    )
    editable = str(status or "").upper() in _EDITABLE_STATUSES
    special_total = sum(special.values())
    summary = (
        f"名单{roster_count}人已全部完成，其中特殊状态{special_total}人"
        if ready
        else (
            f"名单{roster_count}人：未录{missing_count}人、"
            f"未录全{incomplete_count}人、名单外记录{len(extra_ids)}人"
        )
    )
    return {
        "status": str(status or ""),
        "rosterCount": roster_count,
        "recordedCount": recorded_count,
        "completeNormalCount": complete_normal,
        "specialCount": special_total,
        "specialByType": dict(special),
        "missingCount": missing_count,
        "incompleteCount": incomplete_count,
        "outsideRosterCount": len(extra_ids),
        "passCount": pass_count,
        "failCount": fail_count,
        "ready": ready,
        "canSubmit": ready and editable,
        "readOnly": not editable,
        "summary": summary,
        "issues": issues[:100],
    }


def teacher_grade_enter_score(task_id, user, body) -> dict:
    normalized = normalize_mobile_grade_row(body or {})
    return _legacy.teacher_grade_enter_score(task_id, user, normalized)


def teacher_grade_batch_save(task_id, user, rows) -> dict:
    from app.models import AaGradeTask
    from app.modules.academic_affairs.services import academic_affairs_grade_service as grade_service
    from app.modules.academic_affairs.services.academic_affairs_archive_service import (
        guard_term_writable,
    )

    if (user or {}).get("userType") == "STUDENT":
        raise no_permission("该接口仅教职工可用")
    payload = list(rows or [])
    if not payload:
        raise AppException("VALIDATION_ERROR", "至少提交一条成绩")
    if len(payload) > 500:
        raise AppException("VALIDATION_ERROR", "单次最多保存500条成绩")
    normalized = [normalize_mobile_grade_row(row) for row in payload]
    ids = [row["studentId"] for row in normalized]
    duplicate_ids = sorted({sid for sid in ids if ids.count(sid) > 1})
    if duplicate_ids:
        raise AppException(
            "VALIDATION_ERROR",
            "同一批次内 studentId 不可重复",
            details={"duplicateStudentIds": [str(value) for value in duplicate_ids]},
        )

    with grade_service.session() as db:
        task = db.query(AaGradeTask).filter(
            AaGradeTask.id == int(task_id),
            AaGradeTask.tenant_id == grade_service._tid(),
            AaGradeTask.is_deleted.is_(False),
        ).with_for_update().first()
        if not task:
            raise not_found("成绩录入任务不存在")
        guard_term_writable(db, task.term_id)
        grade_service._check_course_scope(task, user)
        if task.status not in _EDITABLE_STATUSES:
            raise AppException(
                "DATA_CONFLICT",
                "当前状态不可录入（已提交/已发布，如需修改请走成绩更正）",
            )
        roster_data = grade_service._require_ready_roster(db, task)
        roster_ids = {int(value) for value in roster_data.get("studentIds") or []}
        outside = sorted(set(ids) - roster_ids)
        if outside:
            raise AppException(
                "APPROVAL_VERSION_CONFLICT",
                "成绩名单已变化，存在不属于当前正式名单的学生",
                details={
                    "rosterSource": roster_data.get("source"),
                    "outsideRosterStudentIds": [str(value) for value in outside],
                },
                http_status=409,
            )
        saved_items = []
        for row in normalized:
            record = grade_service._write_score_row(
                db,
                task,
                row["studentId"],
                row["usualScore"],
                row["finalScore"],
                row["exceptionFlag"],
                mid=row["midtermScore"],
            )
            saved_items.append({
                "recordId": str(record.id),
                "studentId": str(record.student_id),
                "usualScore": record.usual_score,
                "midtermScore": record.midterm_score,
                "finalScore": record.final_score,
                "totalScore": record.total_score,
                "passStatus": record.pass_status,
                "exceptionFlag": record.exception_flag or "NORMAL",
            })
        grade_service._audit(
            db,
            "AA_GRADE_TASK",
            task.id,
            "MOBILE_BATCH_SAVE",
            f"saved={len(saved_items)};rosterSource={roster_data.get('source') or ''}",
        )
        db.commit()
        status = task.status

    report = teacher_grade_quality_report(task_id, user)
    return {
        "gradeTaskId": str(task_id),
        "status": status,
        "savedCount": len(saved_items),
        "items": saved_items,
        "qualityReport": report,
    }


def teacher_grade_quality_report(task_id, user) -> dict:
    roster = _legacy.teacher_grade_roster(task_id, user)
    records = _legacy.teacher_grade_records(task_id, user)
    report = build_grade_quality_report(
        roster.get("items") or [],
        records.get("items") or [],
        usual_ratio=records.get("usualRatio", roster.get("usualRatio", 0)),
        midterm_ratio=records.get("midtermRatio", roster.get("midtermRatio", 0)),
        final_ratio=records.get("finalRatio", roster.get("finalRatio", 0)),
        status=records.get("status") or roster.get("status") or "",
    )
    return {"gradeTaskId": str(task_id), **report}


def teacher_grade_submit_task(task_id, user) -> dict:
    report = teacher_grade_quality_report(task_id, user)
    if not report["canSubmit"]:
        raise AppException(
            "DATA_CONFLICT",
            report["summary"] + "，暂不可提交学院审核",
            details=report,
            http_status=409,
        )
    result = _legacy.teacher_grade_submit_task(task_id, user)
    return {**result, "qualityReport": report}
