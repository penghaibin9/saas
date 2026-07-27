"""V2 R5 教师微信成绩录入最终闭环。

当前代码事实已经具备单生录入、异常标记和任务提交，本层只补移动端仍缺的生产能力：
- 单生与批量写入统一做 0-100 整数、异常标记和名单身份校验；
- 批量保存使用单事务，禁止逐生网络请求造成半成功；
- 提交前返回可解释质量报告，明确未录、未录全、名单外记录和特殊状态；
- 提交仍复用既有成绩审核状态机，不重开第二套业务流程。
"""
from __future__ import annotations

from collections import Counter

from app.core.exceptions import AppException, no_permission, not_found

from . import academic_affairs_grade_identity_facade as _grade
from . import mobile_academic_affairs_facade as _base

_ALLOWED_FLAGS = {"NORMAL", "ABSENT", "DEFERRED", "EXEMPT", "CHEAT"}
_EDITABLE_STATUSES = {"NOT_STARTED", "INPUTTING", "RETURNED"}


def __getattr__(name):
    return getattr(_base, name)


def _score(value, label: str):
    """移动端原始值 → 0-100 整数或 None；布尔、浮点小数和越界一律拒绝。"""
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
        raise AppException("VALIDATION_ERROR", "studentId 必填且须为有效数字") from exc
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


def build_grade_quality_report(roster_items, record_items, *, usual_ratio=0, midterm_ratio=0,
                               final_ratio=0, status="") -> dict:
    """纯函数：按权威名单核对成绩记录，供接口与回归测试共用。"""
    roster = list(roster_items or [])
    records = list(record_items or [])
    record_by_student = {
        str(row.get("studentId")): row
        for row in records
        if row.get("studentId") not in (None, "")
    }
    roster_ids = {str(row.get("studentId")) for row in roster if row.get("studentId") not in (None, "")}

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
            issues.append({**identity, "code": "NOT_RECORDED", "message": "尚未录入成绩或特殊状态"})
            continue

        recorded_count += 1
        flag = str(record.get("exceptionFlag") or "NORMAL").upper()
        if flag != "NORMAL":
            special[flag] += 1
            continue

        missing_parts = [label for key, label in required_parts if record.get(key) in (None, "")]
        if missing_parts or record.get("totalScore") in (None, ""):
            incomplete_count += 1
            message = "、".join(missing_parts) + "未填写" if missing_parts else "总评尚未生成"
            issues.append({**identity, "code": "INCOMPLETE", "message": message})
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
    ready = bool(roster_count) and missing_count == 0 and incomplete_count == 0 and not extra_ids
    editable = str(status or "").upper() in _EDITABLE_STATUSES
    special_total = sum(special.values())
    if ready:
        summary = f"名单{roster_count}人已全部完成，其中特殊状态{special_total}人"
    else:
        summary = (
            f"名单{roster_count}人：未录{missing_count}人、未录全{incomplete_count}人、"
            f"名单外记录{len(extra_ids)}人"
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
    """覆盖旧移动入口：即使绕过前端直调，也必须通过后端同口径校验。"""
    normalized = normalize_mobile_grade_row(body or {})
    return _base.teacher_grade_enter_score(task_id, user, normalized)


def teacher_grade_batch_save(task_id, user, rows) -> dict:
    """移动端批量保存：整批校验、单事务写入、一次审计。"""
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

    with _grade._legacy.session() as db:
        from app.models import AaGradeTask
        from app.modules.academic_affairs.services.academic_affairs_archive_service import guard_term_writable

        task = db.query(AaGradeTask).filter(
            AaGradeTask.id == int(task_id),
            AaGradeTask.tenant_id == _grade._legacy._tid(),
            AaGradeTask.is_deleted.is_(False),
        ).with_for_update().first()
        if not task:
            raise not_found("成绩录入任务不存在")
        guard_term_writable(db, task.term_id)
        _grade._legacy._check_course_scope(task, user)
        if task.status not in _EDITABLE_STATUSES:
            raise AppException("DATA_CONFLICT", "当前状态不可录入（已提交/已发布，如需修改请走成绩更正）")

        roster_data = _grade._base._require_ready_roster(db, task)
        roster_ids = {int(value) for value in (roster_data.get("studentIds") or [])}
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
            record = _grade._legacy._write_score_row(
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

        _grade._legacy._audit(
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
    """提交前质量检查：只读，不改变任务状态。"""
    roster = _base.teacher_grade_roster(task_id, user)
    records = _base.teacher_grade_records(task_id, user)
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
    """移动提交前先给出与页面一致的质量门禁，最终状态迁移仍交给既有服务。"""
    report = teacher_grade_quality_report(task_id, user)
    if not report["canSubmit"]:
        raise AppException(
            "DATA_CONFLICT",
            report["summary"] + "，暂不可提交学院审核",
            details=report,
            http_status=409,
        )
    result = _base.teacher_grade_submit_task(task_id, user)
    return {**result, "qualityReport": report}
