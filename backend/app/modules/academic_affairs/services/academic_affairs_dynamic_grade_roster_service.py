"""Version-bound dynamic roster response, reusing the formal roster authority.

Only component/record rows for the requested page are fetched. Formal membership
validation currently scans the canonical roster; this is bounded transport, not a
claim of fully paginated roster-authority DB work.
"""
from collections import defaultdict
from sqlalchemy import select
from app.services.db_service import _tid, session
from app.core.exceptions import AppException
from .academic_affairs_archive_service import guard_term_writable
from . import academic_affairs_dynamic_grade_service as dynamic


def component_roster(task_id, user, *, page=None, page_size=30, expected_roster_version_id=None):
    from app.models import AaGradeRecord
    from app.models.academic_affairs_r10 import AaGradeComponentScore
    with session() as db:
        task = dynamic._task(db, task_id, user)
        scheme = dynamic._scheme(db, task)
        roster = dynamic.formal_roster(db, task)
        if expected_roster_version_id is not None and str(expected_roster_version_id) != str(roster["rosterVersionId"]):
            raise dynamic._conflict("翻页期间正式名单已换版，请重新载入第一页")
        if page is not None and (page < 1 or page_size < 1 or page_size > 100):
            raise dynamic._conflict("名单分页参数无效")
        if page is not None and page > 1 and expected_roster_version_id is None:
            raise dynamic._conflict("后续页必须携带首屏正式名单版本")
        profiles = sorted(roster.get("items") or [], key=lambda row: int(row["studentId"]))
        total = len(profiles)
        term_writable = True
        try:
            guard_term_writable(db, task.term_id)
        except AppException:
            term_writable = False
        overdue = bool(task.deadline_at and dynamic.datetime.utcnow() > task.deadline_at)
        fixed_records = not scheme and db.scalar(select(AaGradeRecord.id).where(
            AaGradeRecord.tenant_id == _tid(), AaGradeRecord.task_id == task.id,
            AaGradeRecord.is_deleted.is_(False)).limit(1)) is not None
        selected = profiles if page is None else profiles[(page - 1) * page_size:page * page_size]
        ids = [int(row["studentId"]) for row in selected]
        records = db.scalars(select(AaGradeRecord).where(AaGradeRecord.tenant_id == _tid(),
            AaGradeRecord.task_id == task.id, AaGradeRecord.student_id.in_(ids or [0]),
            AaGradeRecord.is_deleted.is_(False))).all()
        by_student = {int(row.student_id): row for row in records}
        if len(by_student) != len(records):
            raise dynamic._conflict("正式成绩记录存在重复学生，请先核对")
        components = db.scalars(select(AaGradeComponentScore).where(AaGradeComponentScore.tenant_id == _tid(),
            AaGradeComponentScore.grade_task_id == task.id, AaGradeComponentScore.student_id.in_(ids or [0]),
            AaGradeComponentScore.is_deleted.is_(False)).order_by(AaGradeComponentScore.id)).all()
        scores = defaultdict(dict)
        for row in components:
            if row.component_code in scores[int(row.student_id)]:
                raise dynamic._conflict("同一学生存在重复成绩项证据")
            scores[int(row.student_id)][row.component_code] = row.score
        items = []
        for profile in selected:
            sid = int(profile["studentId"])
            record = by_student.get(sid)
            items.append({"studentId": str(sid), "studentNo": profile.get("studentNo") or "",
                "realName": profile.get("realName") or profile.get("studentName") or "",
                "classId": str(profile.get("classId") or ""), "className": profile.get("className") or "",
                "scores": scores[sid], "totalScore": record.total_score if record else None,
                "passStatus": record.pass_status if record else None,
                "exceptionFlag": (record.exception_flag or "NORMAL") if record else "NORMAL",
                "recordId": str(record.id) if record else "", "rowVersion": int(record.version or 0) if record else None})
        return {"gradeTaskId": str(task.id), "taskVersion": int(task.version or 0),
            "courseName": task.course_name or "", "status": task.status, "passLine": int(task.pass_line or 60),
            "entryMode": "FIXED" if fixed_records else "COMPONENTS",
            "canWriteComponents": not fixed_records and task.status in dynamic._EDITABLE and term_writable and not overdue and not task.publish_at,
            "termWritable": term_writable, "isOverdue": overdue,
            "scheme": {"schemeId": str(scheme.id) if scheme else "", "schemeVersion": int(scheme.scheme_version or 1) if scheme else 1,
                "status": scheme.status if scheme else "DEFAULT",
                "editable": task.status == "NOT_STARTED" and (not scheme or scheme.status == "DRAFT"),
                "components": dynamic._components(scheme, task)},
            "rosterIdentity": dynamic.roster_identity(roster), "total": total,
            "page": page or 1, "pageSize": page_size if page is not None else total,
            "hasMore": bool(page is not None and page * page_size < total), "items": items}
