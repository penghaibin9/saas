"""成绩服务官方名单兼容入口。

在有效成绩 facade 之上继续收口成绩录入名单：名单展示、单生录入、xlsx预校验、确认导入和提交审核
全部消费 ``resolve_teaching_task_roster``。存在选课关系但尚未锁定时 fail-closed，禁止退回行政班。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import select

from app.core.exceptions import AppException, not_found

from . import academic_affairs_grade_facade as _base
from .academic_affairs_teaching_roster_service import resolve_teaching_task_roster

_legacy = _base._legacy


def __getattr__(name):
    return getattr(_base, name)


def _official_roster(db, task) -> dict:
    from app.models import StudentProfile

    if getattr(task, "teaching_task_id", None):
        return resolve_teaching_task_roster(db, int(task.teaching_task_id))
    if getattr(task, "class_id", None):
        rows = db.scalars(select(StudentProfile).where(
            StudentProfile.tenant_id == _legacy._tid(),
            StudentProfile.class_id == int(task.class_id),
            StudentProfile.is_deleted.is_(False),
        ).order_by(StudentProfile.student_no)).all()
        return {
            "ready": bool(rows),
            "source": "ADMIN_SUPPLEMENT_CLASS",
            "studentIds": [int(row.id) for row in rows],
            "items": [{
                "studentId": str(row.id),
                "studentNo": row.student_no or "",
                "realName": row.real_name or "",
                "classId": str(row.class_id or ""),
            } for row in rows],
            "batchIds": [],
            "note": "管理员补录任务名单来自行政班",
        }
    return {
        "ready": False,
        "source": "ROSTER_MISSING",
        "studentIds": [],
        "items": [],
        "batchIds": [],
        "note": "成绩任务未关联教学任务或行政班",
    }


def _require_ready_roster(db, task) -> dict:
    roster_data = _official_roster(db, task)
    if not roster_data["ready"]:
        raise AppException(
            "DATA_CONFLICT",
            f"成绩名单尚不可用：{roster_data['note']}",
            details=roster_data,
            http_status=409,
        )
    return roster_data


def roster(task_id, user) -> dict:
    from app.models import AaGradeTask

    with _legacy.session() as db:
        task = db.get(AaGradeTask, int(task_id))
        if not task or task.is_deleted or task.tenant_id != _legacy._tid():
            raise not_found("成绩录入任务不存在")
        _legacy._check_course_scope(task, user)
        roster_data = _require_ready_roster(db, task)
        return {
            "items": [{
                "studentId": item["studentId"],
                "studentNo": item["studentNo"],
                "realName": item["realName"],
            } for item in roster_data["items"]],
            "source": roster_data["source"],
            "note": roster_data["note"],
            "total": len(roster_data["studentIds"]),
        }


def enter_score(task_id, user, body) -> dict:
    from app.models import AaGradeRecord, AaGradeTask
    from app.modules.academic_affairs.services.academic_affairs_archive_service import guard_term_writable

    with _legacy.session() as db:
        task = db.get(AaGradeTask, int(task_id))
        if not task or task.is_deleted or task.tenant_id != _legacy._tid():
            raise not_found("成绩录入任务不存在")
        guard_term_writable(db, task.term_id)
        _legacy._check_course_scope(task, user)
        if task.status not in ("NOT_STARTED", "INPUTTING", "RETURNED"):
            raise AppException("DATA_CONFLICT", "当前状态不可录入（已提交/已发布，如需修改请走成绩更正）")

        roster_data = _require_ready_roster(db, task)
        student_id = int(body.studentId)
        if student_id not in set(roster_data["studentIds"]):
            raise AppException("VALIDATION_ERROR", "该学生不在当前教学任务正式名单中")

        fields_set = getattr(body, "model_fields_set", None) or getattr(body, "__fields_set__", set())
        usual_in = getattr(body, "usualScore", None) if "usualScore" in fields_set else None
        mid_in = getattr(body, "midtermScore", None) if "midtermScore" in fields_set else None
        final_in = getattr(body, "finalScore", None) if "finalScore" in fields_set else None
        if not fields_set:
            usual_in = getattr(body, "usualScore", None)
            mid_in = getattr(body, "midtermScore", None)
            final_in = getattr(body, "finalScore", None)
            fields_set = {
                key for key in ("usualScore", "midtermScore", "finalScore", "exceptionFlag")
                if getattr(body, key, None) is not None or key == "exceptionFlag"
            }
        exception_flag = (getattr(body, "exceptionFlag", None) or "NORMAL").upper()
        if exception_flag not in ("NORMAL", "ABSENT", "DEFERRED", "EXEMPT", "CHEAT"):
            raise AppException("VALIDATION_ERROR", "异常标记非法")

        record = db.scalars(select(AaGradeRecord).where(
            AaGradeRecord.tenant_id == _legacy._tid(),
            AaGradeRecord.task_id == task.id,
            AaGradeRecord.student_id == student_id,
            AaGradeRecord.is_deleted.is_(False),
        )).first()
        if not record:
            record = AaGradeRecord(tenant_id=_legacy._tid(), task_id=task.id, student_id=student_id)
            db.add(record)
            usual = usual_in if "usualScore" in fields_set else None
            midterm = mid_in if "midtermScore" in fields_set else None
            final = final_in if "finalScore" in fields_set else None
        else:
            usual = usual_in if "usualScore" in fields_set else record.usual_score
            midterm = mid_in if "midtermScore" in fields_set else record.midterm_score
            final = final_in if "finalScore" in fields_set else record.final_score

        total = None
        if exception_flag == "NORMAL":
            if _legacy._scores_complete(task, usual, midterm, final):
                total = _legacy._compose_total(task, usual, midterm, final)
        else:
            usual = midterm = final = None
        record.usual_score = usual
        record.midterm_score = midterm
        record.final_score = final
        record.total_score = total
        record.exception_flag = exception_flag
        record.pass_status = (
            "PASSED" if total is not None and total >= task.pass_line
            else "FAILED" if total is not None
            else None
        )
        if task.status == "NOT_STARTED":
            task.status = "INPUTTING"
        db.flush()
        _legacy._audit(
            db,
            "AA_GRADE_TASK",
            task.id,
            "ENTER",
            f"student={student_id};roster={roster_data['source']}",
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
            "exceptionFlag": exception_flag,
        }


def grade_import_dry_run(task_id, user, rows) -> dict:
    from app.models import AaGradeTask

    with _legacy.session() as db:
        task = db.get(AaGradeTask, int(task_id))
        if not task or task.is_deleted or task.tenant_id != _legacy._tid():
            raise not_found("成绩录入任务不存在")
        _legacy._check_course_scope(task, user)
        if task.status not in ("NOT_STARTED", "INPUTTING", "RETURNED"):
            raise AppException("DATA_CONFLICT", "当前状态不可导入（已提交/已发布，如需修改请走成绩更正）")
        roster_data = _require_ready_roster(db, task)
        profiles = {item["studentNo"]: item for item in roster_data["items"]}
        need_midterm = (getattr(task, "midterm_ratio", 0) or 0) > 0
        errors = []
        seen = set()
        valid = 0
        for index, row in enumerate(rows or []):
            row_no = index + 1
            student_no = (row.get("studentNo") or "").strip()
            if not student_no:
                errors.append({"rowNo": row_no, "field": "studentNo", "message": "学号必填"})
                continue
            if student_no not in profiles:
                errors.append({
                    "rowNo": row_no,
                    "field": "studentNo",
                    "message": f"学生不在当前教学任务正式名单：{student_no}",
                })
                continue
            if student_no in seen:
                errors.append({"rowNo": row_no, "field": "studentNo", "message": f"文件内学号重复：{student_no}"})
                continue
            flag, bad_raw = _legacy._resolve_exception_flag(row.get("exceptionFlag"))
            if flag is None:
                errors.append({"rowNo": row_no, "field": "exceptionFlag", "message": f"异常标记非法：{bad_raw}"})
                continue
            usual = _legacy._parse_score(row.get("usualScore"))
            if usual is False:
                errors.append({"rowNo": row_no, "field": "usualScore", "message": "平时分须为 0-100 整数"})
                continue
            midterm = _legacy._parse_score(row.get("midtermScore"))
            if midterm is False:
                errors.append({"rowNo": row_no, "field": "midtermScore", "message": "期中分须为 0-100 整数"})
                continue
            final = _legacy._parse_score(row.get("finalScore"))
            if final is False:
                errors.append({"rowNo": row_no, "field": "finalScore", "message": "期末分须为 0-100 整数"})
                continue
            if need_midterm and flag == "NORMAL" and midterm is None and (usual is not None or final is not None):
                errors.append({"rowNo": row_no, "field": "midtermScore", "message": "本任务启用期中占比，期中分必填"})
                continue
            seen.add(student_no)
            valid += 1
        return {
            "total": len(rows or []),
            "validRows": valid,
            "invalidRows": len(errors),
            "errors": errors,
            "rosterSource": roster_data["source"],
        }


def grade_import_confirm(task_id, user, rows) -> dict:
    precheck = grade_import_dry_run(task_id, user, rows)
    if precheck["invalidRows"] > 0:
        raise AppException("DATA_CONFLICT", "存在未通过预校验的行，禁止确认导入")

    from app.models import AaGradeTask

    with _legacy.session() as db:
        task = db.get(AaGradeTask, int(task_id))
        if not task or task.is_deleted or task.tenant_id != _legacy._tid():
            raise not_found("成绩录入任务不存在")
        _legacy._check_course_scope(task, user)
        if task.status not in ("NOT_STARTED", "INPUTTING", "RETURNED"):
            raise AppException("DATA_CONFLICT", "当前状态不可导入（已提交/已发布，如需修改请走成绩更正）")
        roster_data = _require_ready_roster(db, task)
        profiles = {item["studentNo"]: item for item in roster_data["items"]}
        created = 0
        for row in rows or []:
            profile = profiles.get((row.get("studentNo") or "").strip())
            if not profile:
                raise AppException("APPROVAL_VERSION_CONFLICT", "导入期间正式名单已变化，请重新预校验")
            flag, _bad = _legacy._resolve_exception_flag(row.get("exceptionFlag"))
            usual = _legacy._parse_score(row.get("usualScore"))
            midterm = _legacy._parse_score(row.get("midtermScore"))
            final = _legacy._parse_score(row.get("finalScore"))
            _legacy._write_score_row(
                db,
                task,
                int(profile["studentId"]),
                usual,
                final,
                flag,
                mid=midterm,
            )
            created += 1
        _legacy._audit(
            db,
            "AA_GRADE_TASK",
            task.id,
            "IMPORT",
            f"imported={created};roster={roster_data['source']}",
        )
        db.commit()
        return {"created": created, "imported": created, "rosterSource": roster_data["source"]}


def submit_task(task_id, user) -> dict:
    from app.models import AaGradeRecord, AaGradeTask, WorkflowInstance, WorkflowTask
    from app.services.runtime_preset_install_service import ensure_workflow_enabled

    with _legacy.session() as db:
        task = db.get(AaGradeTask, int(task_id))
        if not task or task.is_deleted or task.tenant_id != _legacy._tid():
            raise not_found("成绩录入任务不存在")
        _legacy._check_course_scope(task, user)
        if task.status not in ("INPUTTING", "RETURNED"):
            raise AppException("DATA_CONFLICT", "当前状态不可提交")
        roster_data = _require_ready_roster(db, task)
        roster_ids = set(int(value) for value in roster_data["studentIds"])
        records = db.scalars(select(AaGradeRecord).where(
            AaGradeRecord.tenant_id == _legacy._tid(),
            AaGradeRecord.task_id == task.id,
            AaGradeRecord.is_deleted.is_(False),
        )).all()
        record_ids = {int(record.student_id) for record in records}
        missing = sorted(roster_ids - record_ids)
        extra = sorted(record_ids - roster_ids)
        if missing or extra:
            raise AppException(
                "DATA_CONFLICT",
                f"成绩名单不一致：未录 {len(missing)} 人，名单外记录 {len(extra)} 人",
                details={
                    "rosterSource": roster_data["source"],
                    "missingStudentIds": [str(value) for value in missing],
                    "extraStudentIds": [str(value) for value in extra],
                },
                http_status=409,
            )
        incomplete = [
            record for record in records
            if record.total_score is None and (record.exception_flag or "NORMAL") == "NORMAL"
        ]
        if incomplete:
            raise AppException("DATA_CONFLICT", f"仍有 {len(incomplete)} 名学生成绩未录全，不可提交")

        claimed = db.query(AaGradeTask).filter(
            AaGradeTask.id == task.id,
            AaGradeTask.tenant_id == _legacy._tid(),
            AaGradeTask.status.in_(["INPUTTING", "RETURNED"]),
        ).update({AaGradeTask.status: "SUBMITTED"}, synchronize_session=False)
        if not claimed:
            db.rollback()
            raise AppException("APPROVAL_VERSION_CONFLICT", "成绩任务已提交或状态已变更")
        task.status = "SUBMITTED"
        _name, _role, user_id = _legacy._op()
        first_node = "COLLEGE_REVIEW"
        ensure_workflow_enabled(db, _legacy._tid(), _legacy._WF_SUBMIT)
        instance = WorkflowInstance(
            tenant_id=_legacy._tid(),
            workflow_code=_legacy._WF_SUBMIT,
            source_module="academic-affairs",
            source_biz_type="AA_GRADE_TASK",
            source_biz_id=task.id,
            applicant_id=int(user_id) if user_id.isdigit() else 0,
            title=f"{task.course_name or ''} 成绩审核",
            status="RUNNING",
            current_node=first_node,
        )
        db.add(instance)
        db.flush()
        db.add(WorkflowTask(
            tenant_id=_legacy._tid(),
            instance_id=instance.id,
            node_code=first_node,
            assignee_id=0,
            status="PENDING",
        ))
        task.workflow_instance_id = instance.id
        task.submitted_at = datetime.utcnow()
        _legacy._todo_done_grade_entry(db, task.id)
        _legacy._audit(
            db,
            "AA_GRADE_TASK",
            task.id,
            "SUBMIT",
            f"roster={roster_data['source']};students={len(roster_ids)}",
        )
        db.commit()
        db.refresh(task)
        return {
            "gradeTaskId": str(task.id),
            "status": task.status,
            "rosterSource": roster_data["source"],
            "studentCount": len(roster_ids),
        }


# 包级和旧模块内部调用统一消费官方名单规则。
_legacy.roster = roster
_legacy.enter_score = enter_score
_legacy.grade_import_dry_run = grade_import_dry_run
_legacy.grade_import_confirm = grade_import_confirm
_legacy.submit_task = submit_task
