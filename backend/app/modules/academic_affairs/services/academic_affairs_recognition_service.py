"""成绩认定/课程替代服务（对标商业教务 6-2）。

转专业/转学/证书折算场景：学生（或教务代录）申请用原修课程成绩替代现计划课程 →
教务审核 → 通过写 t_acad_grade(source=RECOGNIZED) 并刷新学生台账聚合。

V2-04 纪律：
- 目标课程必须选择 AaCourse 具体版本，不再允许仅手填课程名生成正式成绩；
- 已通过与重复申请按稳定 course_code 判断，不按名称混并；
- 审核通过保存 course_id/course_code/course_version/attempt_no；
- course_name、学分、课程性质保留为所选版本的快照。
"""
from __future__ import annotations

from datetime import datetime

from app.core.affairs_security import build_affairs_context, no_data_scope
from app.core.context import get_current_user_ctx
from app.core.exceptions import AppException, not_found
from app.services.db_service import _iso, _tid, session


def _bad(message):
    return AppException("VALIDATION_ERROR", message)


def _invalid(message):
    return AppException("DATA_CONFLICT", message, http_status=409)


def _op():
    ctx = get_current_user_ctx() or {}
    return str(ctx.get("realName") or ctx.get("loginName") or ctx.get("userId") or "")


def _role():
    ctx = get_current_user_ctx() or {}
    return str(ctx.get("currentRoleCode") or "")


def _audit(db, biz_id, action, detail=""):
    from app.models import AffairsAuditTrail
    db.add(AffairsAuditTrail(
        tenant_id=_tid(), biz_type="AA_GRADE_RECOGNITION", biz_id=biz_id,
        action=action, operator=_op(), role_name=_role(), detail=detail[:990],
        occurred_at=datetime.utcnow(),
    ))


def _require_school(user, db):
    ctx = build_affairs_context(user, db)
    if ctx.scope_type != "TENANT_ALL":
        raise no_data_scope("仅教务处可审核成绩认定")
    return ctx


def _dto(row):
    import json as _json
    attachments = []
    if getattr(row, "attachment_file_ids", None):
        try:
            attachments = _json.loads(row.attachment_file_ids) or []
        except (ValueError, TypeError):
            attachments = []
    return {
        "recognitionId": str(row.id),
        "studentId": str(row.student_id),
        "studentNo": row.student_no,
        "studentName": row.student_name,
        "sourceCourseName": row.source_course_name,
        "sourceScore": row.source_score,
        "sourceCredit": float(row.source_credit) if row.source_credit is not None else None,
        "sourceOrigin": row.source_origin,
        "targetCourseId": str(row.target_course_id) if getattr(row, "target_course_id", None) else None,
        "targetCourseName": row.target_course_name,
        "attachmentFileIds": [str(value) for value in attachments],
        "reason": row.reason,
        "reviewReason": row.review_reason,
        "reviewedBy": row.reviewed_by,
        "reviewedAt": _iso(row.reviewed_at),
        "status": row.status,
    }


def _resolve_student(db, *, student_no=None):
    from app.models import StudentProfile
    ctx = get_current_user_ctx() or {}
    number = student_no or ctx.get("studentNo")
    profile = db.query(StudentProfile).filter(
        StudentProfile.tenant_id == _tid(),
        StudentProfile.student_no == number,
        StudentProfile.is_deleted.is_(False),
    ).first()
    if not profile:
        raise not_found("学生档案不存在")
    return profile


def _academic_student(db, profile_id):
    from app.models import AcademicStudent
    return db.query(AcademicStudent).filter(
        AcademicStudent.tenant_id == _tid(),
        AcademicStudent.student_id == int(profile_id),
        AcademicStudent.is_deleted.is_(False),
    ).first()


def _passed_course_codes(db, profile_id) -> set[str]:
    from app.models import AcademicGrade
    from app.modules.academic_affairs.services.academic_affairs_grade_service import effective_grade_rows

    academic_student = _academic_student(db, profile_id)
    if not academic_student:
        return set()
    rows = db.query(AcademicGrade).filter(
        AcademicGrade.tenant_id == _tid(),
        AcademicGrade.acad_student_id == academic_student.id,
        AcademicGrade.record_status == "ACTIVE",
        AcademicGrade.is_deleted.is_(False),
    ).all()
    return {
        str(grade.course_code or "").strip()
        for grade in effective_grade_rows(rows)
        if str(grade.pass_status or "").upper() == "PASSED" and str(grade.course_code or "").strip()
    }


def _resolve_target(db, body):
    """目标正式课程必须来自课程库具体版本。"""
    from app.models import AaCourse

    course_id = getattr(body, "targetCourseId", None)
    if not course_id or not str(course_id).isdigit():
        raise _bad("成绩认定必须选择课程库中的目标课程具体版本")
    course = db.query(AaCourse).filter(
        AaCourse.id == int(course_id),
        AaCourse.tenant_id == _tid(),
        AaCourse.is_deleted.is_(False),
    ).first()
    if not course:
        raise _bad("所选目标课程不存在")
    if not (course.course_code or "").strip() or not int(course.version or 0):
        raise _invalid("目标课程缺少课程代码或版本号，暂不可用于成绩认定")
    return course


def _validate_attachments(db, file_ids):
    import json as _json
    from app.models import FileObject

    if not file_ids:
        return None
    values = file_ids if isinstance(file_ids, list) else [file_ids]
    int_ids = [int(value) for value in values if str(value).isdigit()]
    if len(int_ids) != len(values):
        raise _bad("佐证附件包含无效文件，请重新上传")
    found = db.query(FileObject).filter(
        FileObject.tenant_id == _tid(),
        FileObject.id.in_(int_ids or [0]),
    ).count()
    if found != len(int_ids):
        raise _bad("佐证附件包含无效文件，请重新上传")
    return _json.dumps([str(value) for value in int_ids], ensure_ascii=False)


def submit(user, body, *, student_no=None) -> dict:
    """提交认定申请（学生自助时取token学号；教务代录显式传学号）。"""
    from app.models import AaGradeRecognition

    with session() as db:
        if student_no is not None:
            _require_school(user, db)
        profile = _resolve_student(db, student_no=student_no)
        source_name = (getattr(body, "sourceCourseName", None) or "").strip()
        target_course = _resolve_target(db, body)
        score = getattr(body, "sourceScore", None)
        if not source_name:
            raise _bad("原课程必填")
        if score is None or not (0 <= int(score) <= 100):
            raise _bad("原成绩必填（0-100）")
        if int(score) < 60:
            raise _bad("原成绩未及格，不可用于课程替代认定")
        target_code = str(target_course.course_code).strip()
        if target_code in _passed_course_codes(db, profile.id):
            raise _invalid("目标课程已通过，无需认定")

        attachment_json = _validate_attachments(db, getattr(body, "attachmentFileIds", None))
        duplicate = db.query(AaGradeRecognition).filter(
            AaGradeRecognition.tenant_id == _tid(),
            AaGradeRecognition.student_id == profile.id,
            AaGradeRecognition.target_course_id == int(target_course.id),
            AaGradeRecognition.status.in_(("SUBMITTED", "APPROVED")),
            AaGradeRecognition.is_deleted.is_(False),
        ).first()
        if duplicate:
            raise _invalid("该目标课程版本已有在途或已通过的认定记录")

        row = AaGradeRecognition(
            tenant_id=_tid(),
            student_id=profile.id,
            student_no=profile.student_no,
            student_name=profile.real_name,
            source_course_name=source_name,
            source_score=int(score),
            source_credit=getattr(body, "sourceCredit", None),
            source_origin=getattr(body, "sourceOrigin", None),
            target_course_id=int(target_course.id),
            target_course_name=target_course.course_name,
            attachment_file_ids=attachment_json,
            reason=getattr(body, "reason", None),
            status="SUBMITTED",
        )
        db.add(row)
        db.flush()
        _audit(
            db,
            row.id,
            "RECOG_SUBMIT",
            f"{profile.student_no} {source_name}→{target_code}@v{target_course.version}",
        )
        db.commit()
        return _dto(row)


def review(user, recognition_id, action, reason="") -> dict:
    """教务审核：通过时写入完整正式成绩身份；驳回原因不少于5字。"""
    from app.models import AaCourse, AaGradeRecognition, AcademicGrade
    from app.modules.academic_affairs.services.academic_affairs_grade_service import (
        _acad_student_id,
        _refresh_aggregates,
    )
    from app.modules.academic_affairs.services.academic_affairs_grade_identity_service import (
        next_study_attempt_no,
    )

    with session() as db:
        _require_school(user, db)
        row = db.query(AaGradeRecognition).filter(
            AaGradeRecognition.id == int(recognition_id),
            AaGradeRecognition.tenant_id == _tid(),
            AaGradeRecognition.is_deleted.is_(False),
        ).with_for_update().first()
        if not row:
            raise not_found("认定记录不存在")
        if row.status != "SUBMITTED":
            raise _invalid("仅待审核记录可审核")
        action_code = (action or "").upper()
        if action_code == "REJECT":
            if not reason or len(reason.strip()) < 5:
                raise _bad("驳回原因必填且不少于5字")
            row.status = "REJECTED"
            row.review_reason = reason.strip()
            row.reviewed_by = _op()
            row.reviewed_at = datetime.utcnow()
            _audit(db, row.id, "RECOG_REJECT", reason.strip()[:100])
            db.commit()
            return _dto(row)
        if action_code != "APPROVE":
            raise _bad("无效操作")
        if not row.target_course_id:
            raise _invalid("历史认定记录未绑定目标课程版本，请退回后重新提交")

        course = db.query(AaCourse).filter(
            AaCourse.id == int(row.target_course_id),
            AaCourse.tenant_id == _tid(),
            AaCourse.is_deleted.is_(False),
        ).first()
        if not course:
            raise _invalid("目标课程版本已不存在，禁止生成正式成绩")
        course_code = str(course.course_code or "").strip()
        if not course_code or not int(course.version or 0):
            raise _invalid("目标课程缺少课程代码或版本号")

        academic_student = _acad_student_id(db, row.student_id, row.student_name or "")
        if course_code in _passed_course_codes(db, row.student_id):
            raise _invalid("审核期间目标课程已取得及格成绩，认定申请不再有效")
        attempt_no = next_study_attempt_no(db, academic_student.id, course_code)
        grade = AcademicGrade(
            tenant_id=_tid(),
            acad_student_id=academic_student.id,
            course_id=course.id,
            course_code=course_code,
            course_version=int(course.version),
            attempt_no=attempt_no,
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
        row.reviewed_by = _op()
        row.reviewed_at = datetime.utcnow()
        _refresh_aggregates(db, academic_student)
        _audit(
            db,
            row.id,
            "RECOG_APPROVE",
            (
                f"{row.student_no} {row.source_course_name}→{course_code}@v{course.version};"
                f"attemptNo={attempt_no};score={row.source_score}"
            ),
        )
        db.commit()
        return _dto(row)


def list_all(user, status=None, page=1, page_size=50):
    from app.models import AaGradeRecognition
    with session() as db:
        _require_school(user, db)
        query = db.query(AaGradeRecognition).filter(
            AaGradeRecognition.tenant_id == _tid(),
            AaGradeRecognition.is_deleted.is_(False),
        )
        if status:
            query = query.filter(AaGradeRecognition.status == status)
        rows = query.order_by(AaGradeRecognition.id.desc()).all()
        return [_dto(row) for row in rows[(page - 1) * page_size: page * page_size]], len(rows)


def my(user):
    from app.models import AaGradeRecognition
    with session() as db:
        profile = _resolve_student(db)
        rows = db.query(AaGradeRecognition).filter(
            AaGradeRecognition.tenant_id == _tid(),
            AaGradeRecognition.student_id == profile.id,
            AaGradeRecognition.is_deleted.is_(False),
        ).order_by(AaGradeRecognition.id.desc()).all()
        return [_dto(row) for row in rows]
