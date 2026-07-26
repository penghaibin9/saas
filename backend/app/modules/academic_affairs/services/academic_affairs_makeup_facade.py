"""补考/清考服务兼容入口。

- 学生本人优先按稳定 ``studentId`` / 账号绑定解析，学号只保留迁移期兜底；
- 候选名单统一消费成绩中心 ``effective_grade_rows``；
- 已被补考、清考、更正或复查覆盖的旧失败行不再重复入池；
- 清考不再按课程名取历史最高分；
- 分数不参与有效成绩选择，候选只看统一口径后的最终结果。
其余补考、重修、缓考、免修状态机委托原服务。
"""
from __future__ import annotations

import re

from sqlalchemy import select

from app.core.context import get_current_user_ctx
from app.core.exceptions import AppException
from app.services.db_service import _tid, session
from app.services.student_account_link_service import get_student_id_by_user

from . import academic_affairs_makeup_service as _legacy
from .academic_affairs_grade_facade import effective_grade_rows


def __getattr__(name):
    return getattr(_legacy, name)


def _numeric_user_id(value):
    text = str(value or "").strip()
    if text.isdigit():
        return int(text)
    match = re.search(r"(\d+)$", text)
    return int(match.group(1)) if match else None


def _student(db):
    """当前学生主档：稳定ID → 账号绑定 → 学号迁移兜底。"""
    from app.models import StudentProfile

    ctx = get_current_user_ctx() or {}
    tenant_id = int(_tid())
    raw_student_id = str(ctx.get("studentId") or "")
    student_id = int(raw_student_id) if raw_student_id.isdigit() else None

    if student_id is None:
        user_id = _numeric_user_id(ctx.get("userId"))
        if user_id:
            student_id = get_student_id_by_user(
                db,
                tenant_id=tenant_id,
                user_id=user_id,
                allow_legacy_fallback=True,
                login_name=str(ctx.get("loginName") or ctx.get("studentNo") or ""),
            )

    if student_id is not None:
        student = db.scalars(select(StudentProfile).where(
            StudentProfile.id == int(student_id),
            StudentProfile.tenant_id == tenant_id,
            StudentProfile.is_deleted.is_(False),
        )).first()
        if student:
            return student

    # mock/迁移期最后兜底；真实DB账号应通过上方稳定绑定命中并持续监控本分支使用量。
    student_no = str(ctx.get("studentNo") or ctx.get("loginName") or "").strip()
    if student_no:
        student = db.scalars(select(StudentProfile).where(
            StudentProfile.tenant_id == tenant_id,
            StudentProfile.student_no == student_no,
            StudentProfile.is_deleted.is_(False),
        )).first()
        if student:
            return student
    raise AppException("VALIDATION_ERROR", "学生档案不存在或账号尚未绑定学生主档")


def _effective_failed_rows(rows):
    return [
        row for row in effective_grade_rows(rows)
        if str(getattr(row, "pass_status", None) or "").upper() in {"FAIL", "FAILED"}
    ]


def makeup_pending(user, term=None, page=1, page_size=50):
    """仅返回统一有效成绩仍不及格的学生课程。"""
    from app.models import AcademicGrade, AcademicStudent

    with session() as db:
        _legacy._ctx(user, db)
        query = db.query(AcademicGrade).filter(
            AcademicGrade.tenant_id == _tid(),
            AcademicGrade.record_status == "ACTIVE",
            AcademicGrade.is_deleted.is_(False),
        )
        if term:
            query = query.filter(AcademicGrade.term == term)
        effective_failed = _effective_failed_rows(query.all())

        student_ids = sorted({int(row.acad_student_id) for row in effective_failed})
        students = {
            student.id: student
            for student in db.query(AcademicStudent).filter(
                AcademicStudent.tenant_id == _tid(),
                AcademicStudent.id.in_(student_ids),
                AcademicStudent.is_deleted.is_(False),
            ).all()
        } if student_ids else {}

        items = []
        for grade in effective_failed:
            student = students.get(int(grade.acad_student_id))
            if not student:
                continue
            items.append({
                "gradeId": str(grade.id),
                "acadStudentId": str(grade.acad_student_id),
                "studentNo": student.student_no,
                "studentName": student.name,
                "courseName": grade.course_name,
                "score": grade.score,
                "className": student.class_name,
                "effectiveSource": grade.source,
            })
        items.sort(key=lambda row: (row["courseName"] or "", row["studentNo"] or ""))
        total = len(items)
        start = (max(1, int(page)) - 1) * int(page_size)
        return items[start:start + int(page_size)], total


def _clearance_candidates(db, grades):
    """毕业年级中统一有效成绩仍FAILED的课程，禁止历史最高分私有口径。"""
    from app.models import AcademicGrade, AcademicStudent, StudentProfile

    profiles = db.query(StudentProfile).filter(
        StudentProfile.tenant_id == _tid(),
        StudentProfile.grade.in_(grades),
        StudentProfile.student_status == "NORMAL",
        StudentProfile.is_deleted.is_(False),
    ).all()
    profile_by_id = {profile.id: profile for profile in profiles}
    if not profile_by_id:
        return []

    academic_students = db.query(AcademicStudent).filter(
        AcademicStudent.tenant_id == _tid(),
        AcademicStudent.student_id.in_(list(profile_by_id)),
        AcademicStudent.is_deleted.is_(False),
    ).all()
    output = []
    for academic_student in academic_students:
        rows = db.query(AcademicGrade).filter(
            AcademicGrade.tenant_id == _tid(),
            AcademicGrade.acad_student_id == academic_student.id,
            AcademicGrade.record_status == "ACTIVE",
            AcademicGrade.is_deleted.is_(False),
        ).all()
        profile = profile_by_id.get(academic_student.student_id)
        for grade in _effective_failed_rows(rows):
            output.append({
                "acadStudentId": str(academic_student.id),
                "studentNo": academic_student.student_no,
                "studentName": academic_student.name,
                "grade": profile.grade if profile else None,
                "courseName": grade.course_name,
                # 保留旧DTO字段名兼容前端；含义已改为“当前有效成绩”，不再是最高分。
                "bestScore": grade.score,
                "effectiveSource": grade.source,
            })
    output.sort(key=lambda row: (row["courseName"] or "", row["studentNo"] or ""))
    return output


# 原服务函数在自身globals中查找这两个名字；显式替换后无需复制补考/清考状态机。
_legacy._student = _student
_legacy._clearance_candidates = _clearance_candidates
