"""成绩服务学期写保护最终叠加层。

有效成绩口径、官方名单、单生录入均由 ``academic_affairs_grade_roster_facade`` 提供；本层只补两个
容易漏掉的写入口：xlsx确认导入与提交审核。两者均在实际写事务内调用 ``guard_term_writable``。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import select

from app.core.exceptions import AppException, not_found

from . import academic_affairs_grade_roster_facade as _base

_legacy = _base._legacy


def __getattr__(name):
    return getattr(_base, name)


def grade_import_confirm(task_id, user, rows) -> dict:
    precheck = _base.grade_import_dry_run(task_id, user, rows)
    if precheck["invalidRows"] > 0:
        raise AppException("DATA_CONFLICT", "存在未通过预校验的行，禁止确认导入")

    from app.models import AaGradeTask
    from app.modules.academic_affairs.services.academic_affairs_archive_service import guard_term_writable

    with _legacy.session() as db:
        task = db.get(AaGradeTask, int(task_id))
        if not task or task.is_deleted or task.tenant_id != _legacy._tid():
            raise not_found("成绩录入任务不存在")
        guard_term_writable(db, task.term_id)
        _legacy._check_course_scope(task, user)
        if task.status not in ("NOT_STARTED", "INPUTTING", "RETURNED"):
            raise AppException("DATA_CONFLICT", "当前状态不可导入（已提交/已发布，如需修改请走成绩更正）")
        roster_data = _base._require_ready_roster(db, task)
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
    from app.modules.academic_affairs.services.academic_affairs_archive_service import guard_term_writable
    from app.services.runtime_preset_install_service import ensure_workflow_enabled

    with _legacy.session() as db:
        task = db.get(AaGradeTask, int(task_id))
        if not task or task.is_deleted or task.tenant_id != _legacy._tid():
            raise not_found("成绩录入任务不存在")
        guard_term_writable(db, task.term_id)
        _legacy._check_course_scope(task, user)
        if task.status not in ("INPUTTING", "RETURNED"):
            raise AppException("DATA_CONFLICT", "当前状态不可提交")
        roster_data = _base._require_ready_roster(db, task)
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


# 上层与底层都替换，防包级导入和原模块内部调用出现两套写保护。
_base.grade_import_confirm = grade_import_confirm
_base.submit_task = submit_task
_legacy.grade_import_confirm = grade_import_confirm
_legacy.submit_task = submit_task
