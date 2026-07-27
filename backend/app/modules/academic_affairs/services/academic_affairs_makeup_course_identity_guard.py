"""V2-04 补考重修免修最终安全层。"""
from __future__ import annotations

import json

from app.core.exceptions import AppException, not_found
from . import academic_affairs_makeup_course_identity_facade as _base
from . import academic_affairs_makeup_facade as _scope
from . import academic_affairs_makeup_term_facade as _term
from . import academic_affairs_grade_identity_facade as _grade

_legacy = _base._legacy


def __getattr__(name):
    return getattr(_base, name)


def _visible_student_map(ctx, db, pairs):
    """把联查学生按当前教务数据范围裁剪；空范围必须返回空。"""
    raw_students = {
        int(student.id): student
        for _grade_row, student in (pairs or [])
        if student is not None
    }
    visible = _scope._filter_students_by_scope(ctx, db, list(raw_students.values()))
    return {int(student.id): student for student in visible}


def makeup_pending(user, term=None, page=1, page_size=50):
    """按统一有效成绩口径返回补考候选；稳定身份欠账显式展示但不可纳入。"""
    from app.models import AcademicGrade, AcademicStudent

    with _legacy.session() as db:
        ctx = _legacy._ctx(user, db)
        query = db.query(AcademicGrade, AcademicStudent).join(
            AcademicStudent,
            AcademicGrade.acad_student_id == AcademicStudent.id,
        ).filter(
            AcademicGrade.tenant_id == _legacy._tid(),
            AcademicGrade.record_status == "ACTIVE",
            AcademicGrade.is_deleted.is_(False),
            AcademicStudent.is_deleted.is_(False),
        )
        if term:
            query = query.filter(AcademicGrade.term == str(term))
        pairs = query.all()
        visible_students = _visible_student_map(ctx, db, pairs)
        effective = _grade.effective_grade_rows([grade for grade, _student in pairs])
        items = []
        for grade in effective:
            if str(grade.pass_status or "").upper() not in {"FAIL", "FAILED"}:
                continue
            student = visible_students.get(int(grade.acad_student_id))
            if not student:
                continue
            identity_ready = bool(
                grade.course_id and grade.course_code and grade.course_version and grade.attempt_no
            )
            items.append({
                "gradeId": str(grade.id),
                "acadStudentId": str(grade.acad_student_id),
                "studentNo": student.student_no,
                "studentName": student.name,
                "className": student.class_name,
                "courseId": str(grade.course_id or ""),
                "courseCode": grade.course_code or "",
                "courseVersion": int(grade.course_version or 0) or None,
                "attemptNo": int(grade.attempt_no or 0) or None,
                "courseName": grade.course_name,
                "termCode": grade.term or "",
                "score": grade.score,
                "identityReady": identity_ready,
                "blockReason": "" if identity_ready else "缺少courseId、课程版本或修读次数",
            })
        items.sort(key=lambda row: (
            row["studentNo"] or "",
            row["courseCode"] or row["courseName"] or "",
            int(row["attemptNo"] or 0),
        ))
        total = len(items)
        return items[(page - 1) * page_size: page * page_size], total


def exemption_apply(user, body):
    from app.models import AaCourse, AaExemption, AcademicGrade, FileObject

    with _legacy.session() as db:
        student = _legacy._student(db)
        current_term = _term._current_term(db)
        requested = str(getattr(body, "termCode", None) or "").strip()
        term_code = _term._term_code(current_term)
        if requested and requested != term_code:
            raise AppException("VALIDATION_ERROR", "免修申请只能绑定当前办理学期")

        course_id = getattr(body, "courseId", None)
        if not course_id:
            raise AppException("VALIDATION_ERROR", "免修申请必须选择课程库具体courseId")
        course = db.query(AaCourse).filter(
            AaCourse.id == int(course_id),
            AaCourse.tenant_id == _legacy._tid(),
            AaCourse.is_deleted.is_(False),
        ).first()
        if not course:
            raise not_found("课程版本不存在")
        if not (course.course_code or "").strip() or not int(course.version or 0):
            raise AppException("DATA_CONFLICT", "课程缺少稳定代码或版本号，暂不可申请免修", http_status=409)

        academic_student = _base._academic_student_for_profile(db, student.id)
        if academic_student:
            grades = db.query(AcademicGrade).filter(
                AcademicGrade.tenant_id == _legacy._tid(),
                AcademicGrade.acad_student_id == academic_student.id,
                AcademicGrade.course_code == course.course_code,
                AcademicGrade.record_status == "ACTIVE",
                AcademicGrade.is_deleted.is_(False),
            ).all()
            if any(
                str(row.pass_status or "").upper() == "PASSED"
                for row in _grade.effective_grade_rows(grades)
            ):
                raise _legacy._bad("该课程已获及格成绩，不可申请免修")

        maximum = int(_legacy._rule("exemption_max_count", 2))
        used = db.query(AaExemption).filter(
            AaExemption.tenant_id == _legacy._tid(),
            AaExemption.student_id == student.id,
            AaExemption.term_code == term_code,
            AaExemption.status.notin_([_legacy._EX_REJECTED, _legacy._EX_CANCELLED]),
            AaExemption.is_deleted.is_(False),
        ).count()
        if used >= maximum:
            raise _legacy._bad(f"本学期免修申请已达上限{maximum}门")

        values = list(getattr(body, "materialFileIds", None) or [])
        file_ids = [int(value) for value in values if str(value).isdigit()]
        if len(file_ids) != len(values):
            raise _legacy._bad("免修材料包含无效文件ID")
        if file_ids:
            found = db.query(FileObject).filter(
                FileObject.tenant_id == _legacy._tid(),
                FileObject.id.in_(file_ids),
            ).count()
            if found != len(file_ids):
                raise _legacy._bad("免修材料包含不存在或跨租户文件")
        material_json = json.dumps([str(value) for value in file_ids], ensure_ascii=False) if file_ids else None

        row = AaExemption(
            tenant_id=_legacy._tid(), student_id=student.id,
            student_no=student.student_no, student_name=student.real_name,
            course_id=course.id, course_name=course.course_name, term_code=term_code,
            college_id=getattr(student, "college_id", None),
            reason=getattr(body, "reason", None), material_file_ids=material_json,
            current_node=_legacy._EX_TEACHER, status=_legacy._EX_TEACHER,
        )
        db.add(row)
        db.flush()
        _legacy._audit(
            db, "AA_EXEMPTION", row.id, "EXEMPTION_APPLY_IDENTITY",
            f"courseId={course.id};code={course.course_code};version={course.version};files={len(file_ids)}",
        )
        db.commit()
        return _legacy._ex_dto(row)


# 完整路径与中间facade统一指向安全实现。
for module in (_base, _base._base, _term, _legacy):
    module.makeup_pending = makeup_pending
    module.exemption_apply = exemption_apply
