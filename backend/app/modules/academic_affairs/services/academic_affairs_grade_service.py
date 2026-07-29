"""成绩域唯一公开 Service。

旧审核、更正、审计和辅助读能力保存在 ``academic_affairs_grade_core_service``；本文件显式收口：
- 成绩任务绑定课程库具体版本；
- 录入、导入、提交只消费正式教学名单；
- 提交冻结 R9 名单消费者快照，退回重提保留历史版本；
- 发布前校验冻结名单仍为当前版本；
- 正式成绩冻结课程身份、修读次数、教学班、名单版本和来源回链；
- 成绩单、挂科清单、成绩分析和学生聚合统一消费有效成绩策略。

不修改其它模块函数，不依赖 Facade 导入顺序。
"""
from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

from sqlalchemy import select

from app.core.context import get_current_user_ctx
from app.core.exceptions import AppException, not_found

from . import academic_affairs_grade_core_service as _core
from .academic_affairs_effective_grade_policy_service import (
    freeze_effective_grade_policy,
    policy_snapshot_debt,
    resolve_effective_grade,
)
from .academic_affairs_grade_identity_service import (
    course_snapshot,
    grade_identity_debt,
    next_study_attempt_no,
    resolve_grade_task_course,
)
from .academic_affairs_roster_consumer_service import (
    freeze_consumer_snapshot,
    require_consumer_snapshot_current,
    resolve_versioned_roster,
    roster_hash,
)

_EDITABLE = {"NOT_STARTED", "INPUTTING", "RETURNED"}
_SPECIAL_FLAGS = {"NORMAL", "ABSENT", "DEFERRED", "EXEMPT", "CHEAT"}


def __getattr__(name):
    """未重写的审核、更正、审计及兼容读能力显式复用稳定 core。"""
    return getattr(_core, name)


def effective_grade_rows(rows):
    return resolve_effective_grade(rows)


def _body_value(body, name, default=None):
    if isinstance(body, dict):
        return body.get(name, default)
    return getattr(body, name, default)


def _body_fields(body) -> set[str]:
    if isinstance(body, dict):
        return set(body)
    return set(
        getattr(body, "model_fields_set", None)
        or getattr(body, "__fields_set__", None)
        or set()
    )


def _body_proxy(body, **updates):
    if isinstance(body, dict):
        payload = dict(body)
    elif hasattr(body, "model_dump"):
        payload = body.model_dump()
    else:
        payload = dict(vars(body or {}))
    payload.update(updates)
    return SimpleNamespace(**payload)


def _strict_score(value, label: str):
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


def _task_row(task) -> dict:
    row = _core._task_row(task)
    row["courseId"] = str(task.course_id or "")
    row["teachingTaskId"] = str(task.teaching_task_id or "")
    row["termId"] = str(task.term_id or "")
    return row


def _load_task(db, task_id: int, *, lock=False):
    from app.models import AaGradeTask

    query = db.query(AaGradeTask).filter(
        AaGradeTask.id == int(task_id),
        AaGradeTask.tenant_id == _core._tid(),
        AaGradeTask.is_deleted.is_(False),
    )
    if lock:
        query = query.with_for_update()
    task = query.first()
    if not task:
        raise not_found("成绩录入任务不存在")
    return task


def _official_roster(db, task) -> dict:
    """正常任务消费独立教学班名单；管理员历史补录只可使用显式行政班名单。"""
    from app.models import StudentProfile

    if task.teaching_task_id:
        return resolve_versioned_roster(db, int(task.teaching_task_id))
    if task.class_id:
        students = db.scalars(select(StudentProfile).where(
            StudentProfile.tenant_id == _core._tid(),
            StudentProfile.class_id == int(task.class_id),
            StudentProfile.is_deleted.is_(False),
        ).order_by(StudentProfile.student_no, StudentProfile.id)).all()
        ids = [int(row.id) for row in students]
        return {
            "ready": bool(ids),
            "source": "ADMIN_SUPPLEMENT_CLASS",
            "studentIds": ids,
            "items": [{
                "studentId": str(row.id),
                "studentNo": row.student_no or "",
                "realName": row.real_name or "",
                "classId": str(row.class_id or ""),
            } for row in students],
            "memberCount": len(ids),
            "rosterHash": roster_hash(ids),
            "teachingClassId": None,
            "rosterVersionId": None,
            "rosterVersionNo": None,
            "note": "管理员特殊补录名单来自显式行政班；不可走普通教学任务发布链",
        }
    return {
        "ready": False,
        "source": "ROSTER_MISSING",
        "studentIds": [],
        "items": [],
        "memberCount": 0,
        "note": "成绩任务未关联教学任务或行政班",
    }


def _require_ready_roster(db, task) -> dict:
    result = _official_roster(db, task)
    if not result.get("ready"):
        raise AppException(
            "DATA_CONFLICT",
            f"成绩名单尚不可用：{result.get('note') or '未知原因'}",
            details=result,
            http_status=409,
        )
    return result


def _validate_task_course(db, body):
    from app.models import AaCourse, AaTeachingTask

    teaching_task_id = _body_value(body, "teachingTaskId")
    requested_course_id = _body_value(body, "courseId")
    teaching_task = None
    if teaching_task_id:
        teaching_task = db.query(AaTeachingTask).filter(
            AaTeachingTask.id == int(teaching_task_id),
            AaTeachingTask.tenant_id == _core._tid(),
            AaTeachingTask.is_deleted.is_(False),
        ).first()
        if not teaching_task:
            raise not_found("教学任务不存在或不在当前租户范围")
        requested_course_id = teaching_task.course_id
    if requested_course_id in (None, ""):
        raise AppException(
            "VALIDATION_ERROR",
            "成绩任务必须绑定课程库具体courseId；管理员特殊补录请使用稳定课程身份入口",
        )
    course = db.query(AaCourse).filter(
        AaCourse.id == int(requested_course_id),
        AaCourse.tenant_id == _core._tid(),
        AaCourse.is_deleted.is_(False),
    ).first()
    if not course:
        raise not_found("选择的课程版本不存在")
    if not str(course.course_code or "").strip() or not int(course.version or 0):
        raise AppException("DATA_CONFLICT", "课程缺少稳定课程代码或版本号，不能建立成绩任务", http_status=409)
    if teaching_task and int(teaching_task.course_id or 0) != int(course.id):
        raise AppException("DATA_CONFLICT", "教学任务课程与请求课程版本不一致", http_status=409)
    return course


def create_grade_task(body, user) -> dict:
    """创建成绩任务并绑定稳定课程版本；保留原任务唯一性、权限和比例校验。"""
    with _core.session() as db:
        course = _validate_task_course(db, body)
        course_meta = course_snapshot(course)

    proxy = body
    if not _body_value(body, "teachingTaskId"):
        proxy = _body_proxy(
            body,
            courseId=course_meta["courseId"],
            courseName=course_meta["courseName"],
            credit=course_meta["credit"],
        )
    result = _core.create_grade_task(proxy, user)

    with _core.session() as db:
        task = _load_task(db, int(result["gradeTaskId"]), lock=True)
        task.course_id = int(course_meta["courseId"])
        if not str(task.course_name or "").strip():
            task.course_name = course_meta["courseName"]
        if task.credit is None:
            task.credit = course_meta["credit"]
        _core._audit(
            db,
            "AA_GRADE_TASK",
            task.id,
            "COURSE_IDENTITY_BIND",
            (
                f"courseId={course_meta['courseId']};courseCode={course_meta['courseCode']};"
                f"courseVersion={course_meta['courseVersion']}"
            ),
        )
        db.commit()
        result.update(course_meta)
        return result


def list_tasks(user, status=None, page=1, page_size=20):
    from app.models import AaGradeTask

    with _core.session() as db:
        conditions = [
            AaGradeTask.tenant_id == _core._tid(),
            AaGradeTask.is_deleted.is_(False),
        ]
        if status:
            conditions.append(AaGradeTask.status == status)
        role = str((user or {}).get("currentRoleCode") or "").upper()
        if role in _core._REVIEW_ROLES or (user or {}).get("userType") == "PLATFORM_SUPER_ADMIN":
            pass
        elif role == "COLLEGE_ADMIN":
            from app.core.affairs_security import build_affairs_context

            context = build_affairs_context(user, db)
            allowed = context.allowed_class_ids(db)
            if allowed is not None:
                conditions.append(AaGradeTask.class_id.in_(list(allowed) or [0]))
        else:
            conditions.append(AaGradeTask.teacher_key.in_(list(_core._user_keys(user)) or ["__none__"]))
        rows = db.scalars(select(AaGradeTask).where(*conditions).order_by(AaGradeTask.id.desc())).all()
        items = [_task_row(row) for row in rows]
        start = (max(1, int(page)) - 1) * int(page_size)
        return items[start:start + int(page_size)], len(items)


def roster(task_id, user) -> dict:
    with _core.session() as db:
        task = _load_task(db, int(task_id))
        _core._check_course_scope(task, user)
        data = _require_ready_roster(db, task)
        return {
            "items": [{
                "studentId": item["studentId"],
                "studentNo": item.get("studentNo") or "",
                "realName": item.get("realName") or "",
            } for item in data.get("items") or []],
            "source": data.get("source"),
            "note": data.get("note"),
            "total": len(data.get("studentIds") or []),
            "teachingClassId": str(data.get("teachingClassId") or ""),
            "rosterVersionId": str(data.get("rosterVersionId") or ""),
            "rosterVersionNo": data.get("rosterVersionNo"),
            "rosterHash": data.get("rosterHash"),
        }


def enter_score(task_id, user, body) -> dict:
    """单生成绩合并保存；服务端再次校验分数、异常状态和正式名单。"""
    from app.models import AaGradeRecord
    from app.modules.academic_affairs.services.academic_affairs_archive_service import guard_term_writable

    with _core.session() as db:
        task = _load_task(db, int(task_id), lock=True)
        guard_term_writable(db, task.term_id)
        _core._check_course_scope(task, user)
        if str(task.status or "").upper() not in _EDITABLE:
            raise AppException("DATA_CONFLICT", "当前状态不可录入（已提交/已发布，如需修改请走成绩更正）")
        data = _require_ready_roster(db, task)
        try:
            student_id = int(_body_value(body, "studentId"))
        except (TypeError, ValueError) as exc:
            raise AppException("VALIDATION_ERROR", "studentId必填且须为有效数字") from exc
        if student_id not in {int(value) for value in data.get("studentIds") or []}:
            raise AppException("VALIDATION_ERROR", "该学生不在当前教学任务正式名单中")

        record = db.scalars(select(AaGradeRecord).where(
            AaGradeRecord.tenant_id == _core._tid(),
            AaGradeRecord.task_id == task.id,
            AaGradeRecord.student_id == student_id,
            AaGradeRecord.is_deleted.is_(False),
        )).first()
        if not record:
            record = AaGradeRecord(tenant_id=_core._tid(), task_id=task.id, student_id=student_id)
            db.add(record)

        fields = _body_fields(body)
        if isinstance(body, dict):
            fields = set(body)
        clear_usual = bool(_body_value(body, "clearUsual", False))
        clear_midterm = bool(_body_value(body, "clearMidterm", False))
        clear_final = bool(_body_value(body, "clearFinal", False))
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
            usual = None if clear_usual else _strict_score(_body_value(body, "usualScore"), "平时")
        if "midtermScore" in fields:
            midterm = None if clear_midterm else _strict_score(_body_value(body, "midtermScore"), "期中")
        if "finalScore" in fields:
            final = None if clear_final else _strict_score(_body_value(body, "finalScore"), "期末")

        if "exceptionFlag" in fields:
            flag = str(_body_value(body, "exceptionFlag") or "NORMAL").strip().upper()
        else:
            flag = str(record.exception_flag or "NORMAL").upper()
        if flag not in _SPECIAL_FLAGS:
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
            "PASSED" if total is not None and total >= int(task.pass_line or 60)
            else "FAILED" if total is not None
            else None
        )
        if task.status == "NOT_STARTED":
            task.status = "INPUTTING"
        db.flush()
        _core._audit(
            db,
            "AA_GRADE_TASK",
            task.id,
            "ENTER",
            f"student={student_id};roster={data.get('source')}",
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


def grade_import_dry_run(task_id, user, rows) -> dict:
    with _core.session() as db:
        task = _load_task(db, int(task_id))
        _core._check_course_scope(task, user)
        if str(task.status or "").upper() not in _EDITABLE:
            raise AppException("DATA_CONFLICT", "当前状态不可导入（已提交/已发布，如需修改请走成绩更正）")
        data = _require_ready_roster(db, task)
        profiles = {str(item.get("studentNo") or "").strip(): item for item in data.get("items") or []}
        need_midterm = int(task.midterm_ratio or 0) > 0
        errors, seen, valid = [], set(), 0
        for index, row in enumerate(rows or [], start=1):
            student_no = str((row or {}).get("studentNo") or "").strip()
            if not student_no:
                errors.append({"rowNo": index, "field": "studentNo", "message": "学号必填"})
                continue
            if student_no not in profiles:
                errors.append({
                    "rowNo": index,
                    "field": "studentNo",
                    "message": f"学生不在当前教学任务正式名单：{student_no}",
                })
                continue
            if student_no in seen:
                errors.append({"rowNo": index, "field": "studentNo", "message": f"文件内学号重复：{student_no}"})
                continue
            flag, bad_raw = _core._resolve_exception_flag((row or {}).get("exceptionFlag"))
            if flag is None:
                errors.append({"rowNo": index, "field": "exceptionFlag", "message": f"异常标记非法：{bad_raw}"})
                continue
            try:
                usual = _strict_score((row or {}).get("usualScore"), "平时")
                midterm = _strict_score((row or {}).get("midtermScore"), "期中")
                final = _strict_score((row or {}).get("finalScore"), "期末")
            except AppException as exc:
                message = exc.message
                field = "usualScore" if "平时" in message else "midtermScore" if "期中" in message else "finalScore"
                errors.append({"rowNo": index, "field": field, "message": message})
                continue
            if need_midterm and flag == "NORMAL" and midterm is None and (usual is not None or final is not None):
                errors.append({"rowNo": index, "field": "midtermScore", "message": "本任务启用期中占比，期中分必填"})
                continue
            seen.add(student_no)
            valid += 1
        return {
            "total": len(rows or []),
            "validRows": valid,
            "invalidRows": len(errors),
            "errors": errors,
            "rosterSource": data.get("source"),
            "rosterHash": data.get("rosterHash"),
            "rosterVersionId": str(data.get("rosterVersionId") or ""),
        }


def grade_import_confirm(task_id, user, rows) -> dict:
    precheck = grade_import_dry_run(task_id, user, rows)
    if precheck["invalidRows"]:
        raise AppException("DATA_CONFLICT", "存在未通过预校验的行，禁止确认导入")

    from app.modules.academic_affairs.services.academic_affairs_archive_service import guard_term_writable

    with _core.session() as db:
        task = _load_task(db, int(task_id), lock=True)
        guard_term_writable(db, task.term_id)
        _core._check_course_scope(task, user)
        if str(task.status or "").upper() not in _EDITABLE:
            raise AppException("DATA_CONFLICT", "当前状态不可导入（已提交/已发布，如需修改请走成绩更正）")
        data = _require_ready_roster(db, task)
        if precheck.get("rosterHash") and data.get("rosterHash") != precheck["rosterHash"]:
            raise AppException("APPROVAL_VERSION_CONFLICT", "预校验后正式名单已变化，请重新上传校验", http_status=409)
        profiles = {str(item.get("studentNo") or "").strip(): item for item in data.get("items") or []}
        imported = 0
        for row in rows or []:
            profile = profiles.get(str((row or {}).get("studentNo") or "").strip())
            if not profile:
                raise AppException("APPROVAL_VERSION_CONFLICT", "导入期间正式名单已变化，请重新预校验", http_status=409)
            flag, _bad = _core._resolve_exception_flag((row or {}).get("exceptionFlag"))
            _core._write_score_row(
                db,
                task,
                int(profile["studentId"]),
                _strict_score((row or {}).get("usualScore"), "平时"),
                _strict_score((row or {}).get("finalScore"), "期末"),
                flag,
                mid=_strict_score((row or {}).get("midtermScore"), "期中"),
            )
            imported += 1
        _core._audit(
            db,
            "AA_GRADE_TASK",
            task.id,
            "IMPORT",
            f"imported={imported};roster={data.get('source')};hash={data.get('rosterHash')}",
        )
        db.commit()
        return {
            "created": imported,
            "imported": imported,
            "rosterSource": data.get("source"),
            "rosterVersionId": str(data.get("rosterVersionId") or ""),
        }


def submit_task(task_id, user) -> dict:
    """普通教学任务提交学院审核，并在同一事务冻结 R9 正式名单快照。"""
    from app.models import AaGradeRecord, AaGradeTask, WorkflowInstance, WorkflowTask
    from app.modules.academic_affairs.services.academic_affairs_archive_service import guard_term_writable
    from app.services.runtime_preset_install_service import ensure_workflow_enabled

    with _core.session() as db:
        task = _load_task(db, int(task_id), lock=True)
        guard_term_writable(db, task.term_id)
        _core._check_course_scope(task, user)
        if task.status not in {"INPUTTING", "RETURNED"}:
            raise AppException("DATA_CONFLICT", "当前状态不可提交")
        was_returned = task.status == "RETURNED"
        if not task.teaching_task_id:
            raise AppException(
                "DATA_CONFLICT",
                "管理员特殊补录不可走普通教学任务提交链；请使用补录复核专用流程",
                http_status=409,
            )

        data = resolve_versioned_roster(db, int(task.teaching_task_id))
        roster_ids = {int(value) for value in data.get("studentIds") or []}
        if not roster_ids:
            raise AppException("DATA_CONFLICT", "正式教学名单为空，不可提交成绩任务", http_status=409)
        records = db.scalars(select(AaGradeRecord).where(
            AaGradeRecord.tenant_id == _core._tid(),
            AaGradeRecord.task_id == task.id,
            AaGradeRecord.is_deleted.is_(False),
        )).all()
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
            row for row in records
            if row.total_score is None and str(row.exception_flag or "NORMAL").upper() == "NORMAL"
        ]
        if incomplete:
            raise AppException("DATA_CONFLICT", f"仍有 {len(incomplete)} 名学生成绩未录全，不可提交")

        snapshot = freeze_consumer_snapshot(
            db,
            "GRADE_TASK",
            int(task.id),
            int(task.teaching_task_id),
            roster=data,
            allow_replace=was_returned,
            replace_reason="成绩任务退回后按当前正式名单重新提交" if was_returned else "",
        )
        claimed = db.query(AaGradeTask).filter(
            AaGradeTask.id == task.id,
            AaGradeTask.tenant_id == _core._tid(),
            AaGradeTask.status.in_(["INPUTTING", "RETURNED"]),
        ).update({AaGradeTask.status: "SUBMITTED"}, synchronize_session=False)
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
        db.add(WorkflowTask(
            tenant_id=_core._tid(),
            instance_id=instance.id,
            node_code="COLLEGE_REVIEW",
            assignee_id=0,
            status="PENDING",
        ))
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


def _refresh_aggregates(db, academic_student) -> None:
    from app.models import AcademicGrade

    all_rows = db.scalars(select(AcademicGrade).where(
        AcademicGrade.tenant_id == _core._tid(),
        AcademicGrade.acad_student_id == academic_student.id,
        AcademicGrade.record_status == "ACTIVE",
        AcademicGrade.is_deleted.is_(False),
    )).all()
    rows = resolve_effective_grade(all_rows)
    scored = [row for row in rows if row.score is not None]
    academic_student.avg_score = (
        round(sum(float(row.score) for row in scored) / len(scored)) if scored else 0
    )
    academic_student.failed_count = sum(
        1 for row in rows if str(row.pass_status or "").upper() in {"FAIL", "FAILED"}
    )
    academic_student.obtained_credits = sum(
        float(row.credit_value or 0)
        for row in rows
        if str(row.pass_status or "").upper() == "PASSED"
    )
    if not scored:
        academic_student.gpa = 0
        return
    total_credit = sum(float(row.credit_value or 0) for row in scored)
    if total_credit > 0:
        academic_student.gpa = round(
            sum(
                _core._course_point(row.score) * float(row.credit_value or 0)
                for row in scored
            ) / total_credit,
            2,
        )
    else:
        academic_student.gpa = round(
            sum(_core._course_point(row.score) for row in scored) / len(scored),
            2,
        )


def publish_grades(task_id, user) -> dict:
    """教务终审发布：冻结课程身份、修读次数和已提交名单版本。"""
    from app.models import (
        AaGradeRecord,
        AaGradeTask,
        AcademicGrade,
        AffairsRiskRecord,
        StudentProfile,
    )
    from app.modules.academic_affairs.services.academic_affairs_archive_service import guard_term_writable

    _core._require_review_role(user)
    with _core.session() as db:
        task = _load_task(db, int(task_id), lock=True)
        guard_term_writable(db, task.term_id)
        if task.status == "PUBLISHED":
            raise AppException("APPROVAL_VERSION_CONFLICT", "成绩已发布")
        if task.status != "ACADEMIC_REVIEW":
            raise AppException("DATA_CONFLICT", "仅学院审核通过（教务终审中）的任务可发布")
        if not task.teaching_task_id:
            raise AppException("DATA_CONFLICT", "管理员特殊补录不能通过普通发布入口生成正式成绩", http_status=409)

        frozen, current = require_consumer_snapshot_current(
            db,
            "GRADE_TASK",
            int(task.id),
            int(task.teaching_task_id),
        )
        records = db.scalars(select(AaGradeRecord).where(
            AaGradeRecord.tenant_id == _core._tid(),
            AaGradeRecord.task_id == task.id,
            AaGradeRecord.is_deleted.is_(False),
        ).order_by(AaGradeRecord.id)).all()
        frozen_ids = {int(value) for value in frozen.get("studentIds") or []}
        record_ids = {int(row.student_id) for row in records}
        missing = sorted(frozen_ids - record_ids)
        extra = sorted(record_ids - frozen_ids)
        incomplete = [
            row for row in records
            if row.total_score is None and str(row.exception_flag or "NORMAL").upper() == "NORMAL"
        ]
        if not records or missing or extra or incomplete:
            raise AppException(
                "DATA_CONFLICT",
                (
                    f"发布前成绩名单未收口：未录{len(missing)}人、名单外{len(extra)}人、"
                    f"未录全{len(incomplete)}人"
                ),
                details={
                    "frozenSnapshot": frozen,
                    "currentRoster": current,
                    "missingStudentIds": [str(value) for value in missing],
                    "extraStudentIds": [str(value) for value in extra],
                },
                http_status=409,
            )

        course = resolve_grade_task_course(db, task)
        course_meta = course_snapshot(course)
        duplicate = db.scalars(select(AcademicGrade.grade_record_id).where(
            AcademicGrade.tenant_id == _core._tid(),
            AcademicGrade.grade_record_id.in_([int(row.id) for row in records]),
            AcademicGrade.is_deleted.is_(False),
        )).first()
        if duplicate is not None:
            raise AppException("APPROVAL_VERSION_CONFLICT", "成绩明细已存在正式投影，禁止重复发布", http_status=409)

        claimed = db.query(AaGradeTask).filter(
            AaGradeTask.id == task.id,
            AaGradeTask.tenant_id == _core._tid(),
            AaGradeTask.status == "ACADEMIC_REVIEW",
        ).update({AaGradeTask.status: "PUBLISHED"}, synchronize_session=False)
        if not claimed:
            db.rollback()
            raise AppException("APPROVAL_VERSION_CONFLICT", "成绩任务状态已变化，请刷新", http_status=409)
        task.status = "PUBLISHED"

        projected = 0
        fail_count = 0
        for record in records:
            profile = db.get(StudentProfile, int(record.student_id))
            academic_student = _core._acad_student_id(
                db,
                record.student_id,
                profile.real_name if profile else "",
            )
            attempt_no = next_study_attempt_no(db, academic_student.id, course_meta["courseCode"])
            grade = AcademicGrade(
                tenant_id=_core._tid(),
                acad_student_id=academic_student.id,
                course_id=course_meta["courseId"],
                course_code=course_meta["courseCode"],
                course_version=course_meta["courseVersion"],
                attempt_no=attempt_no,
                grade_task_id=task.id,
                grade_record_id=record.id,
                source_biz_type="GRADE_RECORD",
                source_biz_id=record.id,
                teaching_task_id=task.teaching_task_id,
                teaching_class_id=int(frozen["teachingClassId"]),
                roster_version_id=int(frozen["rosterVersionId"]),
                course_name=course_meta["courseName"],
                term=task.term_code,
                nature=course_meta["nature"],
                credit_value=course_meta["credit"],
                score=record.total_score,
                pass_status=record.pass_status or "PENDING",
                exam_type="FINAL",
                record_status="ACTIVE",
                source="PUBLISH",
            )
            db.add(grade)
            db.flush()
            freeze_effective_grade_policy(
                db,
                grade,
                event_type="PUBLISH",
                source_biz_type="GRADE_RECORD",
                source_biz_id=record.id,
            )
            record.acad_grade_id = grade.id
            record.source = "PUBLISH"
            _refresh_aggregates(db, academic_student)
            projected += 1
            if record.pass_status == "FAILED":
                fail_count += 1
                exists = db.scalars(select(AffairsRiskRecord).where(
                    AffairsRiskRecord.tenant_id == _core._tid(),
                    AffairsRiskRecord.source == "ACADEMIC_WARNING",
                    AffairsRiskRecord.source_ref_id == record.id,
                )).first()
                if not exists:
                    db.add(AffairsRiskRecord(
                        tenant_id=_core._tid(),
                        student_id=record.student_id,
                        source="ACADEMIC_WARNING",
                        source_ref_id=record.id,
                        risk_level="MEDIUM",
                        title=f"{course_meta['courseName']} 课程不及格",
                        detail=f"总评 {record.total_score}，及格线 {task.pass_line}",
                        status="NEW",
                    ))

        task.publish_at = datetime.utcnow()
        task.academic_reviewed_at = datetime.utcnow()
        _name, _role, user_id = _core._op()
        task.academic_reviewer_id = int(user_id) if str(user_id).isdigit() else None
        _core._audit(
            db,
            "AA_GRADE_TASK",
            task.id,
            "PUBLISH",
            (
                f"projected={projected};fail={fail_count};courseId={course_meta['courseId']};"
                f"courseVersion={course_meta['courseVersion']};teachingClassId={frozen['teachingClassId']};"
                f"rosterVersionId={frozen['rosterVersionId']};snapshotVersion={frozen['snapshotVersion']}"
            ),
        )
        db.commit()

    warning_scan_ok = True
    warning_scan_error = None
    try:
        from app.modules.academic_affairs.services.academic_affairs_warning_service import scan_warnings

        scan_warnings(user)
    except Exception as exc:
        import logging

        warning_scan_ok = False
        warning_scan_error = str(exc)[:200]
        logging.getLogger(__name__).exception("grade publish -> scan_warnings failed")
    return {
        "gradeTaskId": str(task_id),
        "status": "PUBLISHED",
        "projected": projected,
        "failCount": fail_count,
        "courseId": str(course_meta["courseId"]),
        "courseCode": course_meta["courseCode"],
        "courseVersion": course_meta["courseVersion"],
        "teachingClassId": frozen["teachingClassId"],
        "rosterVersionId": frozen["rosterVersionId"],
        "snapshotVersion": frozen["snapshotVersion"],
        "warningScanOk": warning_scan_ok,
        "warningScanError": warning_scan_error,
    }


def _scoped_academic_students(db, user):
    from app.models import AcademicStudent, StudentProfile

    query = db.query(AcademicStudent).filter(
        AcademicStudent.tenant_id == _core._tid(),
        AcademicStudent.is_deleted.is_(False),
    )
    role = str((user or {}).get("currentRoleCode") or "").upper()
    if role == "COLLEGE_ADMIN":
        from app.core.affairs_security import build_affairs_context

        context = build_affairs_context(user, db)
        allowed = context.allowed_class_ids(db)
        if allowed is not None:
            profile_ids = select(StudentProfile.id).where(
                StudentProfile.tenant_id == _core._tid(),
                StudentProfile.class_id.in_(list(allowed) or [0]),
                StudentProfile.is_deleted.is_(False),
            )
            query = query.filter(AcademicStudent.student_id.in_(profile_ids))
    return query.all()


def transcript(student_id, user) -> dict:
    from app.models import AcademicGrade, AcademicStudent

    with _core.session() as db:
        academic_student = db.scalars(select(AcademicStudent).where(
            AcademicStudent.tenant_id == _core._tid(),
            AcademicStudent.student_id == int(student_id),
            AcademicStudent.is_deleted.is_(False),
        )).first()
        if not academic_student:
            return {"items": [], "earnedCredits": 0, "gpa": None, "failCount": 0, "note": "无学业记录"}
        rows = db.scalars(select(AcademicGrade).where(
            AcademicGrade.tenant_id == _core._tid(),
            AcademicGrade.acad_student_id == academic_student.id,
            AcademicGrade.record_status == "ACTIVE",
            AcademicGrade.is_deleted.is_(False),
        )).all()
        effective = sorted(
            resolve_effective_grade(rows),
            key=lambda row: (str(row.term or ""), str(row.course_code or row.course_name or ""), int(row.id)),
        )
        items = [{
            "gradeId": str(row.id),
            "courseId": str(row.course_id or ""),
            "courseCode": row.course_code or "",
            "courseVersion": row.course_version,
            "attemptNo": row.attempt_no,
            "courseName": row.course_name,
            "term": row.term or "",
            "credit": float(row.credit_value or 0),
            "score": row.score,
            "passStatus": row.pass_status,
            "source": row.source or "LEGACY",
        } for row in effective]
        earned = sum(
            float(row.credit_value or 0)
            for row in effective
            if str(row.pass_status or "").upper() == "PASSED"
        )
        return {
            "items": items,
            "earnedCredits": earned,
            "gpa": float(academic_student.gpa or 0),
            "failCount": sum(
                1 for row in effective if str(row.pass_status or "").upper() in {"FAIL", "FAILED"}
            ),
            "policyCode": "LATEST_FORMAL_SOURCE_V1",
        }


def export_transcript_xlsx(user, student_id, purpose="") -> bytes:
    purpose = str(purpose or "").strip()
    if len(purpose) < 5:
        raise AppException("VALIDATION_ERROR", "导出用途必填（≥5 字）")
    from app.models import StudentProfile
    from app.services.xlsx_util import build_ledger_xlsx

    data = transcript(student_id, user)
    with _core.session() as db:
        student = db.get(StudentProfile, int(student_id))
        label = (
            f"{student.real_name}（学号 {student.student_no}）"
            if student else f"学生ID {student_id}"
        )
    name, _role, _uid = _core._op()
    watermark = (
        f"{label} 成绩查询件  导出人：{name or '-'}  "
        f"时间：{datetime.utcnow().strftime('%Y-%m-%d %H:%M')}  用途：{purpose}  非正式证明"
    )
    headers = ["课程代码", "课程名称", "学期", "学分", "成绩", "结果", "来源"]
    labels = {"PASSED": "及格", "FAILED": "不及格", "FAIL": "不及格", "PENDING": "待定"}
    rows = [[
        item["courseCode"],
        item["courseName"],
        item["term"],
        item["credit"],
        item["score"] if item["score"] is not None else "",
        labels.get(item["passStatus"], item["passStatus"] or "—"),
        item["source"],
    ] for item in data["items"]]
    content = build_ledger_xlsx("个人成绩查询件", headers, rows, watermark=watermark)
    with _core.session() as db:
        _core._audit(db, "AA_GRADE_TRANSCRIPT", int(student_id), "EXPORT_QUERY_COPY", f"用途={purpose[:100]}")
        db.commit()
    return content


def fail_list(user, term=None, page=1, page_size=50):
    from app.models import AcademicGrade

    with _core.session() as db:
        students = _scoped_academic_students(db, user)
        student_by_id = {int(row.id): row for row in students}
        query = db.query(AcademicGrade).filter(
            AcademicGrade.tenant_id == _core._tid(),
            AcademicGrade.acad_student_id.in_(list(student_by_id) or [0]),
            AcademicGrade.record_status == "ACTIVE",
            AcademicGrade.is_deleted.is_(False),
        )
        if term:
            query = query.filter(AcademicGrade.term == term)
        effective = resolve_effective_grade(query.all())
        rows = [
            row for row in effective
            if str(row.pass_status or "").upper() in {"FAIL", "FAILED"}
        ]
        rows.sort(key=lambda row: (str(row.term or ""), str(row.course_code or row.course_name or ""), int(row.id)), reverse=True)
        items = []
        for row in rows:
            student = student_by_id.get(int(row.acad_student_id))
            items.append({
                "gradeId": str(row.id),
                "studentName": student.name if student else "",
                "studentId": str(student.student_id or "") if student else "",
                "courseId": str(row.course_id or ""),
                "courseCode": row.course_code or "",
                "courseName": row.course_name,
                "term": row.term or "",
                "score": row.score,
                "source": row.source or "LEGACY",
            })
        start = (max(1, int(page)) - 1) * int(page_size)
        return items[start:start + int(page_size)], len(items)


def grade_analysis(user, term=None, dimension=None):
    from app.models import AcademicGrade

    with _core.session() as db:
        students = _scoped_academic_students(db, user)
        student_by_id = {int(row.id): row for row in students}
        query = db.query(AcademicGrade).filter(
            AcademicGrade.tenant_id == _core._tid(),
            AcademicGrade.acad_student_id.in_(list(student_by_id) or [0]),
            AcademicGrade.score.is_not(None),
            AcademicGrade.record_status == "ACTIVE",
            AcademicGrade.is_deleted.is_(False),
        )
        if term:
            query = query.filter(AcademicGrade.term == term)
        effective = [row for row in resolve_effective_grade(query.all()) if row.score is not None]
        all_scores = [int(row.score) for row in effective]
        passed = sum(1 for row in effective if str(row.pass_status or "").upper() == "PASSED")
        result = _core._score_stats(all_scores, passed)
        if dimension in {"course", "class"}:
            groups = {}
            for row in effective:
                if dimension == "class":
                    student = student_by_id.get(int(row.acad_student_id))
                    name = str(getattr(student, "class_id", None) or "未分班")
                else:
                    name = str(row.course_code or row.course_name or "未命名课程")
                groups.setdefault(name, []).append(row)
            result["dimension"] = dimension
            result["rows"] = []
            for name, group in groups.items():
                stats = _core._score_stats(
                    [int(row.score) for row in group],
                    sum(1 for row in group if str(row.pass_status or "").upper() == "PASSED"),
                )
                stats["name"] = name
                result["rows"].append(stats)
            result["rows"].sort(key=lambda row: (-row["total"], row["name"]))
        result["policyCode"] = "LATEST_FORMAL_SOURCE_V1"
        return result


def export_grade_analysis_xlsx(user, term=None, dimension="course", purpose="") -> bytes:
    purpose = str(purpose or "").strip()
    if len(purpose) < 5:
        raise AppException("VALIDATION_ERROR", "导出用途必填（≥5 字）")
    if dimension not in {"course", "class"}:
        dimension = "course"
    from app.services.xlsx_util import build_ledger_xlsx

    data = grade_analysis(user, term, dimension)
    current = get_current_user_ctx() or {}
    watermark = (
        f"导出人：{current.get('realName') or current.get('loginName') or '-'}  "
        f"时间：{datetime.utcnow().strftime('%Y-%m-%d %H:%M')}  用途：{purpose}"
    )
    label = "按课程" if dimension == "course" else "按班级"
    title = f"成绩分析统计表（{label}{('·' + term) if term else ''}）"
    headers = [
        "名称", "记录数", "平均分", "最高分", "最低分", "及格率(%)", "优秀率(%)",
        "90-100", "80-89", "70-79", "60-69", "0-59",
    ]
    rows = []
    for row in data.get("rows", []):
        distribution = {item["range"]: item["count"] for item in row["distribution"]}
        rows.append([
            row["name"], row["total"], row["avgScore"], row["maxScore"], row["minScore"],
            round(row["passRate"] * 100, 1), round(row["excellentRate"] * 100, 1),
            distribution["90-100"], distribution["80-89"], distribution["70-79"],
            distribution["60-69"], distribution["0-59"],
        ])
    content = build_ledger_xlsx(title, headers, rows, watermark=watermark)
    with _core.session() as db:
        _core._audit(db, "AC_GRADE_ANALYSIS", None, "GRADE_ANALYSIS_EXPORT", f"{title} 用途={purpose[:100]}")
        db.commit()
    return content


def change_academic_review(record_id, user, action, reason="") -> dict:
    """复用既有更正审批后，以统一有效成绩口径刷新聚合并冻结策略事件。"""
    result = _core.change_academic_review(record_id, user, action, reason)
    if str(action or "").upper() != "APPROVE":
        return result

    from app.models import AaGradeRecord, AcademicGrade, AcademicStudent

    with _core.session() as db:
        record = db.get(AaGradeRecord, int(record_id))
        grade = db.get(AcademicGrade, int(record.acad_grade_id)) if record and record.acad_grade_id else None
        academic_student = db.get(AcademicStudent, int(grade.acad_student_id)) if grade and grade.acad_student_id else None
        if grade:
            freeze_effective_grade_policy(
                db,
                grade,
                event_type="CHANGE",
                source_biz_type="GRADE_RECORD",
                source_biz_id=int(record_id),
            )
        if academic_student:
            _refresh_aggregates(db, academic_student)
        db.commit()
    return result


def identity_debt(user, term=None) -> dict:
    role = str((user or {}).get("currentRoleCode") or "").upper()
    if role not in {"ACADEMIC_ADMIN", "SCHOOL_ADMIN"} and (user or {}).get("userType") != "PLATFORM_SUPER_ADMIN":
        raise AppException("NO_PERMISSION", "仅教务处可查看正式成绩身份欠账", http_status=403)
    with _core.session() as db:
        identity = grade_identity_debt(db, term=term)
        policy = policy_snapshot_debt(db, term=term)
        return {
            **identity,
            "missingPolicySnapshot": policy["missingPolicySnapshot"],
            "legacyNameKey": policy["legacyNameKey"],
            "policyReady": policy["ready"],
            "policyCode": "LATEST_FORMAL_SOURCE_V1",
            "ready": bool(identity.get("ready")) and bool(policy.get("ready")),
            "samplePolicyDebtGradeIds": policy["sampleGradeIds"],
        }
