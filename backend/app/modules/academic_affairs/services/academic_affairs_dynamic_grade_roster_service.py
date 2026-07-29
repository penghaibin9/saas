"""R10 动态成绩任务工作区名单与分项回显。"""
from __future__ import annotations

from collections import defaultdict

from sqlalchemy import select

from app.services.db_service import _tid, session

from . import academic_affairs_dynamic_grade_service as _dynamic
from .academic_affairs_roster_consumer_service import resolve_versioned_roster


def component_roster(task_id, user) -> dict:
    from app.models import AaGradeRecord
    from app.models.academic_affairs_r10 import AaGradeComponentScore

    with session() as db:
        task = _dynamic._task(db, task_id, user)
        scheme = _dynamic._scheme(db, task)
        components = _dynamic._components(scheme, task)
        if task.teaching_task_id:
            roster = resolve_versioned_roster(db, int(task.teaching_task_id))
        else:
            roster = _dynamic._grade._base._require_ready_roster(db, task)
            roster = {
                **roster,
                "rosterVersionId": roster.get("rosterVersionId") or "",
                "rosterVersionNo": roster.get("rosterVersionNo") or 0,
                "teachingClassId": roster.get("teachingClassId") or "",
            }

        records = db.scalars(select(AaGradeRecord).where(
            AaGradeRecord.tenant_id == _tid(),
            AaGradeRecord.task_id == task.id,
            AaGradeRecord.is_deleted.is_(False),
        )).all()
        record_by_student = {int(row.student_id): row for row in records}
        component_rows = db.scalars(select(AaGradeComponentScore).where(
            AaGradeComponentScore.tenant_id == _tid(),
            AaGradeComponentScore.grade_task_id == task.id,
            AaGradeComponentScore.is_deleted.is_(False),
        ).order_by(AaGradeComponentScore.id)).all()
        scores_by_student = defaultdict(dict)
        for row in component_rows:
            scores_by_student[int(row.student_id)][row.component_code] = row.score

        items = []
        for profile in roster.get("items") or []:
            student_id = int(profile["studentId"])
            record = record_by_student.get(student_id)
            items.append({
                "studentId": str(student_id),
                "studentNo": profile.get("studentNo") or "",
                "realName": profile.get("realName") or profile.get("studentName") or "",
                "classId": str(profile.get("classId") or ""),
                "className": profile.get("className") or "",
                "scores": scores_by_student.get(student_id, {}),
                "totalScore": record.total_score if record else None,
                "passStatus": record.pass_status if record else None,
                "exceptionFlag": (record.exception_flag or "NORMAL") if record else "NORMAL",
                "recordId": str(record.id) if record else "",
            })
        return {
            "gradeTaskId": str(task.id),
            "courseName": task.course_name or "",
            "status": task.status,
            "passLine": int(task.pass_line or 60),
            "scheme": {
                "schemeId": str(scheme.id) if scheme else "",
                "schemeVersion": int(scheme.scheme_version or 1) if scheme else 1,
                "status": scheme.status if scheme else "DEFAULT",
                "editable": task.status == "NOT_STARTED" and (not scheme or scheme.status == "DRAFT"),
                "components": components,
            },
            "rosterIdentity": {
                "source": roster.get("source") or "",
                "teachingClassId": str(roster.get("teachingClassId") or ""),
                "rosterVersionId": str(roster.get("rosterVersionId") or ""),
                "rosterVersionNo": int(roster.get("rosterVersionNo") or 0),
                "memberCount": len(items),
            },
            "items": items,
        }
