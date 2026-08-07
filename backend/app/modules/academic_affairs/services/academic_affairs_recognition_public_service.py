"""成绩认定/课程替代唯一公开入口。

学生自助只接受稳定账号绑定；教务代录按显式学号唯一命中。审核通过生成带课程版本、
修读次数和来源业务回链的正式成绩，不通过导入副作用替换原 Service。
"""
from __future__ import annotations

import json
from datetime import datetime

from app.core.context import get_current_user_ctx
from app.core.exceptions import AppException, not_found

from . import academic_affairs_exemption_evidence_service as evidence_service
from . import academic_affairs_recognition_service as _base
from .academic_affairs_grade_identity_service import lock_grade_identity, next_study_attempt_no


def __getattr__(name):
    return getattr(_base, name)


def _fresh_read(query):
    """加锁读，读到最新已提交版本；SQLite 无共享行锁时退回普通读。

    按方言判断，不用 try/except 兜底：那样会把 MySQL 的锁等待超时也一并吞掉，静默退回
    普通读，守卫恰好在高并发（唯一真正需要它的时候）自动失效。
    """
    try:
        is_mysql = query.session.get_bind().dialect.name == "mysql"
    except Exception:  # noqa: BLE001  取不到方言时保守走普通读
        is_mysql = False
    return query.with_for_update(read=True).first() if is_mysql else query.first()


def _resolve_student(db, *, student_no=None):
    if student_no is None:
        from app.services.mobile_student_identity_facade import resolve_student

        profile = resolve_student(db, get_current_user_ctx() or {})
        if not profile:
            raise not_found("当前账号尚未绑定唯一学生档案")
        return profile

    from app.models import StudentProfile

    number = str(student_no or "").strip()
    if not number:
        raise _base._bad("代录学号必填")
    rows = db.query(StudentProfile).filter(
        StudentProfile.tenant_id == _base._tid(),
        StudentProfile.student_no == number,
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


def submit(user, body, *, student_no=None) -> dict:
    from app.models import AaGradeRecognition

    with _base.session() as db:
        if student_no is not None:
            _base._require_school(user, db)
        profile = _resolve_student(db, student_no=student_no)
        source_name = (getattr(body, "sourceCourseName", None) or "").strip()
        target_course = _base._resolve_target(db, body)
        score = getattr(body, "sourceScore", None)
        if not source_name:
            raise _base._bad("原课程必填")
        if score is None or not (0 <= int(score) <= 100):
            raise _base._bad("原成绩必填（0-100）")
        if int(score) < 60:
            raise _base._bad("原成绩未及格，不可用于课程替代认定")
        target_code = str(target_course.course_code).strip()
        if target_code in _base._passed_course_codes(db, profile.id):
            raise _base._invalid("目标课程已通过，无需认定")

        # 先锁学生主档行，再做查重。原来是 SELECT-then-INSERT 无锁：两个并发申请都查不到在途
        # 记录，于是双双落库，最后各自终审生成两条都 PASSED 的正式成绩。锁必须早于查重。
        #
        # 这里锁 StudentProfile 而不是成绩身份头：身份头按 acad_student_id 定位，而
        # _acad_student_id() 在学业台账缺失时会新建一行——两个并发事务会各建一条、拿到不同的
        # acad_student_id，于是锁到两把不同的锁，等于没锁。StudentProfile 是必然已存在的稳定行。
        from app.models import StudentProfile as _Profile

        db.query(_Profile).filter(
            _Profile.id == int(profile.id),
            _Profile.tenant_id == _base._tid(),
        ).with_for_update().first()

        raw_files = getattr(body, "attachmentFileIds", None) or []
        file_ids = raw_files if isinstance(raw_files, list) else [raw_files]
        int_ids = [int(value) for value in file_ids if str(value).isdigit()]
        if len(int_ids) != len(file_ids):
            raise _base._bad("佐证附件ID格式不正确")
        if len(set(int_ids)) != len(int_ids):
            raise _base._bad("佐证附件重复提交")
        attachment_json = (
            json.dumps([str(value) for value in int_ids], ensure_ascii=False) if int_ids else None
        )
        # 查重必须用加锁读。MySQL 默认 REPEATABLE READ：本事务在拿锁之前已经做过普通读
        # （解析学生、解析目标课程），读视图就定格了；此后即使拿到了学生主档行锁，普通读依然
        # 看不见并发提交刚落库的那条申请，于是两边都"查无在途记录"，双双插入。
        # 加锁读总是读最新已提交版本，锁 + 新鲜读两者缺一不可。
        duplicate_query = db.query(AaGradeRecognition).filter(
            AaGradeRecognition.tenant_id == _base._tid(),
            AaGradeRecognition.student_id == profile.id,
            AaGradeRecognition.target_course_id == int(target_course.id),
            AaGradeRecognition.status.in_(("SUBMITTED", "APPROVED")),
            AaGradeRecognition.is_deleted.is_(False),
        )
        duplicate = _fresh_read(duplicate_query)
        if duplicate:
            raise _base._invalid("该目标课程版本已有在途或已通过的认定记录")

        row = AaGradeRecognition(
            tenant_id=_base._tid(),
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
        # 佐证绑定到这条申请本身（要先 flush 拿到 id），归属与安全状态由文件中心统一把关；
        # 与免修共用同一套守卫，终审前会逐项复验。
        evidence = evidence_service.freeze_manifest(
            db, row, int_ids,
            actor=get_current_user_ctx() or {},
            student=profile,
            kind="RECOGNITION",
            scope={"targetCourseId": str(target_course.id), "targetCourseCode": target_code},
        )
        _base._audit(
            db,
            row.id,
            "RECOG_SUBMIT",
            (
                f"{profile.student_no} {source_name}→{target_code}@v{target_course.version};"
                f"evidence={evidence['count']};manifestHash={evidence['manifestHash'][:16]}"
            ),
        )
        db.commit()
        return _base._dto(row)


def review(user, recognition_id, action, reason="") -> dict:
    from app.models import AaCourse, AaGradeRecognition, AcademicGrade
    from app.modules.academic_affairs.services import academic_affairs_grade_service as grade_service

    with _base.session() as db:
        _base._require_school(user, db)
        row = db.query(AaGradeRecognition).filter(
            AaGradeRecognition.id == int(recognition_id),
            AaGradeRecognition.tenant_id == _base._tid(),
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
            AaCourse.tenant_id == _base._tid(),
            AaCourse.is_deleted.is_(False),
        ).first()
        if not course or not (course.course_code or "").strip() or not int(course.version or 0):
            raise _base._invalid("目标课程版本不存在或缺少稳定身份")

        academic_student = grade_service._acad_student_id(
            db,
            row.student_id,
            row.student_name or "",
        )
        # 锁 (学生, 课程) 身份头：与免修、正常发布、补考等所有正式成绩写入互斥，
        # 之后的"已通过"判断和 attempt_no 分配才是在同一把锁下做的。
        course_code = str(course.course_code).strip()
        lock_grade_identity(db, academic_student.id, course_code)
        # 已通过判断必须在拿到锁之后、用加锁读重做一次。MySQL 默认 REPEATABLE READ：本事务
        # 在拿锁前已经做过普通读，读视图就定格了，普通读看不见并发终审刚提交的那条 PASSED，
        # 于是两条认定各自"查无及格成绩"，双双发学分。加锁读总是读最新已提交版本。
        passed_query = db.query(AcademicGrade).filter(
            AcademicGrade.tenant_id == _base._tid(),
            AcademicGrade.acad_student_id == academic_student.id,
            AcademicGrade.course_code == course_code,
            AcademicGrade.pass_status == "PASSED",
            AcademicGrade.record_status == "ACTIVE",
            AcademicGrade.is_deleted.is_(False),
        )
        already_passed = _fresh_read(passed_query)
        if already_passed or course_code in _base._passed_course_codes(db, row.student_id):
            raise _base._invalid("审核期间目标课程已取得及格成绩，认定申请不再有效")

        existing = db.query(AcademicGrade).filter(
            AcademicGrade.tenant_id == _base._tid(),
            AcademicGrade.source_biz_type == "RECOGNITION",
            AcademicGrade.source_biz_id == row.id,
            AcademicGrade.is_deleted.is_(False),
        ).first()
        if existing:
            raise AppException(
                "APPROVAL_VERSION_CONFLICT",
                "该认定申请已生成正式成绩",
                http_status=409,
            )

        # 终审要凭这些佐证生成一条正式的、计学分的及格成绩，写成绩前重新验一遍证据链。
        evidence = evidence_service.require_valid_manifest(db, row, kind="RECOGNITION")
        attempt_no = next_study_attempt_no(
            db,
            academic_student.id,
            course.course_code,
            source_biz_type="RECOGNITION",
        )
        grade = AcademicGrade(
            tenant_id=_base._tid(),
            acad_student_id=academic_student.id,
            course_id=course.id,
            course_code=str(course.course_code).strip(),
            course_version=int(course.version),
            attempt_no=attempt_no,
            source_biz_type="RECOGNITION",
            source_biz_id=row.id,
            course_name=course.course_name,
            nature=course.nature or "REQUIRED",
            credit_value=(
                row.source_credit
                if row.source_credit is not None
                else course.credit or 0
            ),
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
        grade_service._refresh_aggregates(db, academic_student)
        _base._audit(
            db,
            row.id,
            "RECOG_APPROVE",
            (
                f"courseId={course.id};version={course.version};"
                f"attemptNo={attempt_no};gradeId={grade.id};"
                f"manifestHash={str(evidence['manifestHash'] or '')[:16]}"
            ),
        )
        db.commit()
        return _base._dto(row)


def my(user):
    from app.models import AaGradeRecognition

    with _base.session() as db:
        profile = _resolve_student(db)
        rows = db.query(AaGradeRecognition).filter(
            AaGradeRecognition.tenant_id == _base._tid(),
            AaGradeRecognition.student_id == profile.id,
            AaGradeRecognition.is_deleted.is_(False),
        ).order_by(AaGradeRecognition.id.desc()).all()
        return [_base._dto(row) for row in rows]
