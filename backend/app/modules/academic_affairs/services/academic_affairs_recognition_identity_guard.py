"""V2-04 成绩认定最终来源回链与学生身份守卫层。"""
from __future__ import annotations

from datetime import datetime

from app.core.context import get_current_user_ctx
from app.core.exceptions import AppException, not_found
from app.services.db_service import _tid, session

from . import academic_affairs_recognition_service as _base
from . import academic_affairs_grade_identity_facade as _grade
from .academic_affairs_grade_identity_service import next_study_attempt_no


def _resolve_student(db, *, student_no=None):
    """学生自助使用稳定账号绑定；教务代录可按显式学号精确定位。"""
    if student_no is None:
        from app.services.mobile_student_identity_facade import resolve_student

        profile = resolve_student(db, get_current_user_ctx() or {})
        if not profile:
            raise not_found("当前账号尚未绑定唯一学生档案")
        return profile

    from app.models import StudentProfile
    rows = db.query(StudentProfile).filter(
        StudentProfile.tenant_id == _tid(),
        StudentProfile.student_no == str(student_no).strip(),
        StudentProfile.is_deleted.is_(False),
    ).all()
    if not rows:
        raise not_found("代录学号对应的学生档案不存在")
    if len(rows) != 1:
        raise AppException(
            "DATA_CONFLICT",
            "代录学号命中多份学生档案，请先修复学生主档唯一性",
            http_status=409,
        )
    return rows[0]


def review(user, recognition_id, action, reason="") -> dict:
    from app.models import AaCourse, AaGradeRecognition, AcademicGrade

    with session() as db:
        _base._require_school(user, db)
        row = db.query(AaGradeRecognition).filter(
            AaGradeRecognition.id == int(recognition_id),
            AaGradeRecognition.tenant_id == _tid(),
            AaGradeRecognition.is_deleted.is_(False),
        ).with_for_update().first()
        if not row:
            raise not_found("认定记录不存在")
        if row.status != "SUBMITTED":
            raise _base._invalid("仅待审核记录可审核")
        action_code = str(action or "").upper()
        if action_code == "REJECT":
            reason_text = (reason or "").strip()
            if len(reason_text) < 5:
                raise _base._bad("驳回原因必填且不少于5字")
            row.status = "REJECTED"
            row.review_reason = reason_text
            row.reviewed_by = _base._op()
            row.reviewed_at = datetime.utcnow()
            _base._audit(db, row.id, "RECOG_REJECT", reason_text[:100])
            db.commit()
            return _base._dto(row)
        if action_code != "APPROVE":
            raise _base._bad("无效操作")
        if not row.target_course_id:
            raise _base._invalid("历史认定记录未绑定目标课程版本，请退回后重新提交")

        course = db.query(AaCourse).filter(
            AaCourse.id == int(row.target_course_id),
            AaCourse.tenant_id == _tid(),
            AaCourse.is_deleted.is_(False),
        ).first()
        if not course or not (course.course_code or "").strip() or not int(course.version or 0):
            raise _base._invalid("目标课程版本不存在或缺少稳定身份")
        academic_student = _grade._legacy._acad_student_id(db, row.student_id, row.student_name or "")
        if str(course.course_code).strip() in _base._passed_course_codes(db, row.student_id):
            raise _base._invalid("审核期间目标课程已取得及格成绩，认定申请不再有效")

        existing = db.query(AcademicGrade).filter(
            AcademicGrade.tenant_id == _tid(),
            AcademicGrade.source_biz_type == "RECOGNITION",
            AcademicGrade.source_biz_id == row.id,
            AcademicGrade.is_deleted.is_(False),
        ).first()
        if existing:
            raise AppException("APPROVAL_VERSION_CONFLICT", "该认定申请已生成正式成绩", http_status=409)

        attempt_no = next_study_attempt_no(db, academic_student.id, course.course_code)
        grade = AcademicGrade(
            tenant_id=_tid(),
            acad_student_id=academic_student.id,
            course_id=course.id,
            course_code=str(course.course_code).strip(),
            course_version=int(course.version),
            attempt_no=attempt_no,
            source_biz_type="RECOGNITION",
            source_biz_id=row.id,
            course_name=course.course_name,
            nature=course.nature or "REQUIRED",
            credit_value=(row.source_credit if row.source_credit is not None else course.credit or 0),
            score=row.source_score,
            pass_status="PASSED",
            exam_type="RECOGNIZED",
            source="RECOGNIZED",
            record_status="ACTIVE",
        )
        db.add(grade)
        db.flush()
        row.acad_grade_id = grade.id
        row.status = "APPROVED"
        row.review_reason = (reason or "").strip() or None
        row.reviewed_by = _base._op()
        row.reviewed_at = datetime.utcnow()
        _grade._legacy._refresh_aggregates(db, academic_student)
        _base._audit(
            db, row.id, "RECOG_APPROVE",
            f"courseId={course.id};version={course.version};attemptNo={attempt_no};gradeId={grade.id}",
        )
        db.commit()
        return _base._dto(row)


# 学生提交、我的列表和审核均共享安全解析/来源回链。
_base._resolve_student = _resolve_student
_base.review = review
