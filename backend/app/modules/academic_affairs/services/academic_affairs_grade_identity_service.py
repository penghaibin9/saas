"""V2-04 正式成绩课程身份与修读次数解析。

原则：
- ``course_id`` 指向具体 AaCourse 版本行，``course_code + course_version``作为不可变快照；
- 新教学任务发布代表一次新的修读，attempt_no 在同一学生+稳定课程代码下递增；
- 补考/清考不增加修读次数，后续写入口必须继承原成绩 attempt_no；
- 历史无ID成绩只进入欠账报告，不在运行时按课程名静默合并。
"""
from __future__ import annotations

from sqlalchemy import func, select

from app.core.exceptions import AppException, not_found
from app.services.db_service import _tid


def resolve_grade_task_course(db, grade_task):
    """解析成绩任务对应的具体课程版本，并兼容回填 AaGradeTask.course_id。"""
    from app.models import AaCourse, AaTeachingTask

    course_id = int(grade_task.course_id) if getattr(grade_task, "course_id", None) else None
    if course_id is None and getattr(grade_task, "teaching_task_id", None):
        teaching_task = db.query(AaTeachingTask).filter(
            AaTeachingTask.id == int(grade_task.teaching_task_id),
            AaTeachingTask.tenant_id == _tid(),
            AaTeachingTask.is_deleted.is_(False),
        ).first()
        if not teaching_task:
            raise not_found("成绩任务关联的教学任务不存在")
        course_id = int(teaching_task.course_id) if teaching_task.course_id else None
        if course_id:
            grade_task.course_id = course_id
    if course_id is None:
        raise AppException(
            "DATA_CONFLICT",
            "成绩任务没有稳定courseId，禁止发布正式成绩；请先绑定课程库具体版本",
            http_status=409,
        )

    course = db.query(AaCourse).filter(
        AaCourse.id == course_id,
        AaCourse.tenant_id == _tid(),
        AaCourse.is_deleted.is_(False),
    ).first()
    if not course:
        raise not_found("成绩任务绑定的课程版本不存在或已删除")
    if not (course.course_code or "").strip() or not int(course.version or 0):
        raise AppException("DATA_CONFLICT", "课程库版本缺少课程代码或版本号，禁止发布正式成绩", http_status=409)

    # 任务展示快照可保留历史名称，但缺失的名称/学分必须从具体课程版本补齐。
    if not (grade_task.course_name or "").strip():
        grade_task.course_name = course.course_name
    if grade_task.credit is None:
        grade_task.credit = course.credit
    return course


def next_study_attempt_no(db, acad_student_id: int, course_code: str) -> int:
    """同一学生、同一稳定课程代码的下一次修读编号。

    course_id 指向版本行，同一课程改版后ID会变化，因此修读次数按稳定 course_code 聚合。
    历史 NULL attempt_no 不参与自动推断，避免按课程名猜测；回填后才进入正式序列。
    """
    from app.models import AcademicGrade

    max_no = db.scalar(select(func.max(AcademicGrade.attempt_no)).where(
        AcademicGrade.tenant_id == _tid(),
        AcademicGrade.acad_student_id == int(acad_student_id),
        AcademicGrade.course_code == str(course_code).strip(),
        AcademicGrade.attempt_no.is_not(None),
        AcademicGrade.is_deleted.is_(False),
    ))
    return int(max_no or 0) + 1


def source_attempt_no(source_grade) -> int:
    """补考/清考继承原修读次数；原成绩未治理时fail-closed。"""
    value = getattr(source_grade, "attempt_no", None)
    if value is None or int(value) <= 0:
        raise AppException(
            "DATA_CONFLICT",
            "原成绩缺少修读次数，禁止生成新的补考/清考正式成绩；请先完成成绩身份回填",
            http_status=409,
        )
    return int(value)


def course_snapshot(course) -> dict:
    return {
        "courseId": int(course.id),
        "courseCode": str(course.course_code or "").strip(),
        "courseVersion": int(course.version or 0),
        "courseName": course.course_name or "",
        "nature": course.nature or "REQUIRED",
        "credit": float(course.credit or 0),
    }


def roster_snapshot(roster_data: dict) -> dict:
    def _int_or_none(value):
        try:
            return int(value) if value not in (None, "") else None
        except (TypeError, ValueError):
            return None

    return {
        "teachingClassId": _int_or_none(roster_data.get("teachingClassId")),
        "rosterVersionId": _int_or_none(roster_data.get("rosterVersionId")),
        "rosterVersionNo": _int_or_none(roster_data.get("rosterVersionNo")),
        "rosterSource": roster_data.get("source") or "",
    }


def grade_identity_debt(db, *, term: str | None = None) -> dict:
    """历史正式成绩身份欠账只读汇总，不猜测回填。"""
    from app.models import AcademicGrade

    query = db.query(AcademicGrade).filter(
        AcademicGrade.tenant_id == _tid(),
        AcademicGrade.record_status == "ACTIVE",
        AcademicGrade.is_deleted.is_(False),
    )
    if term:
        query = query.filter(AcademicGrade.term == term)
    rows = query.all()
    missing_course = [row for row in rows if not row.course_id or not row.course_code or not row.course_version]
    missing_attempt = [row for row in rows if not row.attempt_no]
    return {
        "total": len(rows),
        "missingCourseIdentity": len(missing_course),
        "missingAttemptNo": len(missing_attempt),
        "ready": not missing_course and not missing_attempt,
        "sampleGradeIds": [str(row.id) for row in (missing_course + missing_attempt)[:50]],
    }
