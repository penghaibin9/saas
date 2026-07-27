"""V2-04 补考、清考、重修、免修稳定课程身份最终层。"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import select

from app.core.exceptions import AppException, not_found

from . import academic_affairs_makeup_grade_identity_facade as _base
from . import academic_affairs_makeup_term_facade as _term
from . import academic_affairs_grade_identity_facade as _grade
from .academic_affairs_grade_identity_service import next_study_attempt_no, source_attempt_no

_legacy = _base._legacy


def __getattr__(name):
    return getattr(_base, name)


def _academic_student_for_profile(db, profile_id):
    from app.models import AcademicStudent

    return db.query(AcademicStudent).filter(
        AcademicStudent.tenant_id == _legacy._tid(),
        AcademicStudent.student_id == int(profile_id),
        AcademicStudent.is_deleted.is_(False),
    ).first()


def _effective_failed_grade(db, academic_student_id: int, grade_id: int):
    from app.models import AcademicGrade

    grade = db.query(AcademicGrade).filter(
        AcademicGrade.id == int(grade_id),
        AcademicGrade.tenant_id == _legacy._tid(),
        AcademicGrade.acad_student_id == int(academic_student_id),
        AcademicGrade.record_status == "ACTIVE",
        AcademicGrade.is_deleted.is_(False),
    ).first()
    if not grade or str(grade.pass_status or "").upper() not in {"FAIL", "FAILED"}:
        raise AppException("VALIDATION_ERROR", "请选择当前学生有效的挂科成绩")
    if not grade.course_id or not grade.course_code or not grade.course_version or not grade.attempt_no:
        raise AppException(
            "DATA_CONFLICT",
            "所选挂科成绩缺少courseId、课程版本或修读次数，请先完成成绩身份回填",
            details={"gradeId": str(grade.id)},
            http_status=409,
        )
    related = db.query(AcademicGrade).filter(
        AcademicGrade.tenant_id == _legacy._tid(),
        AcademicGrade.acad_student_id == int(academic_student_id),
        AcademicGrade.course_code == grade.course_code,
        AcademicGrade.record_status == "ACTIVE",
        AcademicGrade.is_deleted.is_(False),
    ).all()
    effective = _grade.effective_grade_rows(related)
    if len(effective) != 1 or int(effective[0].id) != int(grade.id):
        raise AppException(
            "APPROVAL_VERSION_CONFLICT",
            "所选成绩已不是该课程当前有效挂科结果，请刷新候选名单",
            details={"effectiveGradeIds": [str(row.id) for row in effective]},
            http_status=409,
        )
    return grade


def enroll_makeup_by_grade(user, batch_id, grade_id, acad_student_id, origin_score=None):
    from app.models import AcademicMakeup

    with _legacy.session() as db:
        _legacy._require_school(_legacy._ctx(user, db))
        batch = _legacy._get_mb(db, int(batch_id))
        _term._guard_batch(db, batch)
        if batch.status not in (_legacy._MB_DRAFT, _legacy._MB_ARRANGED):
            raise _legacy._invalid("仅DRAFT/ARRANGED批次可纳入名单")
        grade = _effective_failed_grade(db, int(acad_student_id), int(grade_id))
        duplicate = db.query(AcademicMakeup).filter(
            AcademicMakeup.tenant_id == _legacy._tid(),
            AcademicMakeup.batch_id == batch.id,
            AcademicMakeup.origin_grade_id == grade.id,
            AcademicMakeup.is_deleted.is_(False),
        ).first()
        if duplicate:
            return {"makeupId": str(duplicate.id), "status": duplicate.status, "originGradeId": str(grade.id)}

        row = AcademicMakeup(
            tenant_id=_legacy._tid(),
            acad_student_id=int(acad_student_id),
            kind=(batch.kind or "MAKEUP"),
            origin_grade_id=grade.id,
            course_id=grade.course_id,
            course_code=grade.course_code,
            course_version=grade.course_version,
            attempt_no=source_attempt_no(grade),
            course_name=grade.course_name,
            term=grade.term,
            origin_score=grade.score if origin_score is None else int(origin_score),
            batch_id=batch.id,
            status="PENDING_EXAM",
            record_status="ACTIVE",
        )
        db.add(row)
        db.flush()
        if batch.status == _legacy._MB_DRAFT:
            batch.status = _legacy._MB_ARRANGED
        _legacy._audit(
            db, "AA_MAKEUP", row.id, "MAKEUP_ENROLL_IDENTITY",
            f"originGradeId={grade.id};courseId={grade.course_id};version={grade.course_version};attemptNo={grade.attempt_no}",
        )
        db.commit()
        return {
            "makeupId": str(row.id), "status": row.status,
            "originGradeId": str(grade.id), "courseId": str(grade.course_id),
            "courseCode": grade.course_code, "courseVersion": grade.course_version,
            "attemptNo": grade.attempt_no,
        }


def enroll_makeup(user, batch_id, acad_student_id, course_name, origin_score=None):
    raise AppException(
        "VALIDATION_ERROR",
        "旧的按课程名称纳入补考入口已停用，请从补考候选名单提交gradeId",
    )


def _clearance_candidates_v2(db, grades):
    from app.models import AcademicGrade, AcademicStudent, StudentProfile

    profiles = db.query(StudentProfile).filter(
        StudentProfile.tenant_id == _legacy._tid(),
        StudentProfile.grade.in_(grades),
        StudentProfile.student_status == "NORMAL",
        StudentProfile.is_deleted.is_(False),
    ).all()
    profile_by_id = {int(row.id): row for row in profiles}
    academic_students = db.query(AcademicStudent).filter(
        AcademicStudent.tenant_id == _legacy._tid(),
        AcademicStudent.student_id.in_(list(profile_by_id) or [0]),
        AcademicStudent.is_deleted.is_(False),
    ).all()
    output = []
    for student in academic_students:
        rows = db.query(AcademicGrade).filter(
            AcademicGrade.tenant_id == _legacy._tid(),
            AcademicGrade.acad_student_id == student.id,
            AcademicGrade.record_status == "ACTIVE",
            AcademicGrade.is_deleted.is_(False),
        ).all()
        for grade in _grade.effective_grade_rows(rows):
            if str(grade.pass_status or "").upper() not in {"FAIL", "FAILED"}:
                continue
            ready = bool(grade.course_id and grade.course_code and grade.course_version and grade.attempt_no)
            profile = profile_by_id.get(int(student.student_id))
            output.append({
                "gradeId": str(grade.id),
                "acadStudentId": str(student.id),
                "studentNo": student.student_no,
                "studentName": student.name,
                "grade": profile.grade if profile else None,
                "courseId": str(grade.course_id or ""),
                "courseCode": grade.course_code or "",
                "courseVersion": grade.course_version,
                "attemptNo": grade.attempt_no,
                "courseName": grade.course_name,
                "bestScore": grade.score,
                "identityReady": ready,
            })
    output.sort(key=lambda row: (row["studentNo"] or "", row["courseCode"] or row["courseName"] or ""))
    return output


def clearance_scan(user, batch_id, dry_run=False):
    from app.models import AcademicMakeup

    with _legacy.session() as db:
        _legacy._require_school(_legacy._ctx(user, db))
        batch = _legacy._get_mb(db, int(batch_id))
        _term._guard_batch(db, batch)
        if (batch.kind or "MAKEUP") != "CLEARANCE":
            raise _legacy._invalid("仅清考批次可执行名单扫描")
        if batch.status not in (_legacy._MB_DRAFT, _legacy._MB_ARRANGED):
            raise _legacy._invalid("仅DRAFT/ARRANGED批次可圈定名单")
        target_grades = [value for value in (batch.target_grades or "").split(",") if value]
        candidates = _clearance_candidates_v2(db, target_grades)
        debts = [row for row in candidates if not row["identityReady"]]
        if debts and not dry_run:
            raise AppException(
                "DATA_CONFLICT",
                f"清考候选中有{len(debts)}条成绩缺少课程身份或修读次数，已取消圈定",
                details={"items": debts[:100]},
                http_status=409,
            )
        added = skipped = 0
        if not dry_run:
            for candidate in candidates:
                duplicate = db.query(AcademicMakeup).filter(
                    AcademicMakeup.tenant_id == _legacy._tid(),
                    AcademicMakeup.batch_id == batch.id,
                    AcademicMakeup.origin_grade_id == int(candidate["gradeId"]),
                    AcademicMakeup.is_deleted.is_(False),
                ).first()
                if duplicate:
                    skipped += 1
                    continue
                db.add(AcademicMakeup(
                    tenant_id=_legacy._tid(),
                    acad_student_id=int(candidate["acadStudentId"]),
                    kind="CLEARANCE",
                    origin_grade_id=int(candidate["gradeId"]),
                    course_id=int(candidate["courseId"]),
                    course_code=candidate["courseCode"],
                    course_version=int(candidate["courseVersion"]),
                    attempt_no=int(candidate["attemptNo"]),
                    course_name=candidate["courseName"],
                    origin_score=candidate["bestScore"],
                    batch_id=batch.id,
                    status="PENDING_EXAM",
                    record_status="ACTIVE",
                ))
                added += 1
            if added and batch.status == _legacy._MB_DRAFT:
                batch.status = _legacy._MB_ARRANGED
            _legacy._audit(db, "AA_MAKEUP", batch.id, "CLEARANCE_SCAN_IDENTITY", f"added={added};skipped={skipped}")
            db.commit()
        return {
            "batchId": str(batch.id), "dryRun": bool(dry_run), "candidates": len(candidates),
            "identityDebtCount": len(debts), "added": 0 if dry_run else added,
            "skipped": 0 if dry_run else skipped, "items": candidates,
        }


def _frozen_origin_grade(db, makeup):
    from app.models import AcademicGrade

    if not makeup.origin_grade_id:
        raise AppException(
            "DATA_CONFLICT", "补考名单未冻结originGradeId，请重新从候选名单纳入", http_status=409,
        )
    origin = db.query(AcademicGrade).filter(
        AcademicGrade.id == int(makeup.origin_grade_id),
        AcademicGrade.tenant_id == _legacy._tid(),
        AcademicGrade.is_deleted.is_(False),
    ).first()
    if not origin:
        raise not_found("补考名单对应的原成绩不存在")
    expected = (origin.course_id, origin.course_code, origin.course_version, origin.attempt_no)
    frozen = (makeup.course_id, makeup.course_code, makeup.course_version, makeup.attempt_no)
    if expected != frozen:
        raise AppException(
            "APPROVAL_VERSION_CONFLICT",
            "补考名单冻结身份与原成绩不一致，请先治理数据",
            details={"originGradeId": str(origin.id)},
            http_status=409,
        )
    source_attempt_no(origin)
    return origin


def finish_makeup_batch(user, batch_id):
    from app.models import AcademicGrade, AcademicMakeup, AcademicStudent

    with _legacy.session() as db:
        _legacy._require_school(_legacy._ctx(user, db))
        batch = _legacy._get_mb(db, int(batch_id))
        _term._guard_batch(db, batch)
        if batch.status == _legacy._MB_FINISHED:
            return _legacy._mb_dto(batch)
        if batch.status != _legacy._MB_REVIEWED:
            raise _legacy._invalid("仅学院审核通过(REVIEWED)的批次可教务发布回写")
        records = db.query(AcademicMakeup).filter(
            AcademicMakeup.batch_id == batch.id,
            AcademicMakeup.tenant_id == _legacy._tid(),
            AcademicMakeup.status == "SCORED",
            AcademicMakeup.is_deleted.is_(False),
        ).order_by(AcademicMakeup.id).all()
        cap = 60 if batch.score_rule == "CAP60" else 100
        source = "CLEARANCE" if batch.kind == "CLEARANCE" else "MAKEUP"
        affected = set()
        for makeup in records:
            origin = _frozen_origin_grade(db, makeup)
            final_score = makeup.final_score or 0
            passed = final_score >= 60
            recorded_score = min(final_score, cap) if passed else final_score
            grade = db.query(AcademicGrade).filter(
                AcademicGrade.tenant_id == _legacy._tid(),
                AcademicGrade.source_biz_type == source,
                AcademicGrade.source_biz_id == makeup.id,
                AcademicGrade.is_deleted.is_(False),
            ).with_for_update().first()
            if not grade:
                grade = AcademicGrade(
                    tenant_id=_legacy._tid(),
                    acad_student_id=makeup.acad_student_id,
                    course_id=origin.course_id,
                    course_code=origin.course_code,
                    course_version=origin.course_version,
                    attempt_no=origin.attempt_no,
                    grade_task_id=origin.grade_task_id,
                    teaching_task_id=origin.teaching_task_id,
                    teaching_class_id=origin.teaching_class_id,
                    roster_version_id=origin.roster_version_id,
                    source_biz_type=source,
                    source_biz_id=makeup.id,
                    course_name=origin.course_name,
                    term=batch.term_code,
                    nature=origin.nature,
                    credit_value=origin.credit_value,
                    score=recorded_score,
                    pass_status="PASSED" if passed else "FAILED",
                    exam_type=source,
                    source=source,
                    record_status="ACTIVE",
                )
                db.add(grade)
            else:
                grade.score = recorded_score
                grade.pass_status = "PASSED" if passed else "FAILED"
                grade.record_status = "ACTIVE"
            affected.add(int(makeup.acad_student_id))
            _legacy._audit(
                db, "AA_MAKEUP", makeup.id, "MAKEUP_GRADE_IDENTITY",
                f"originGradeId={origin.id};courseId={origin.course_id};attemptNo={origin.attempt_no};source={source}",
            )
        db.flush()
        for academic_student_id in affected:
            academic_student = db.get(AcademicStudent, academic_student_id)
            if academic_student and not academic_student.is_deleted:
                _grade._legacy._refresh_aggregates(db, academic_student)
        batch.status = _legacy._MB_FINISHED
        _legacy._audit(db, "AA_MAKEUP", batch.id, "MAKEUP_BATCH_FINISH", f"source={source};rows={len(records)}")
        db.commit()
        return {**_legacy._mb_dto(batch), "identityProjected": len(records), "source": source}


def retake_apply(user, body):
    from app.models import AaRetakeApply

    with _legacy.session() as db:
        student = _legacy._student(db)
        current_term = _term._current_term(db)
        requested = str(getattr(body, "termCode", None) or "").strip()
        term_code = _term._term_code(current_term)
        if requested and requested != term_code:
            raise AppException("VALIDATION_ERROR", "重修报名只能绑定当前办理学期")
        academic_student = _academic_student_for_profile(db, student.id)
        if not academic_student:
            raise not_found("学生学业档案不存在")
        grade_id = getattr(body, "gradeId", None)
        if not grade_id:
            raise AppException("VALIDATION_ERROR", "请从本人挂科成绩选择gradeId")
        grade = _effective_failed_grade(db, academic_student.id, int(grade_id))
        history = db.query(AaRetakeApply).filter(
            AaRetakeApply.tenant_id == _legacy._tid(),
            AaRetakeApply.student_id == student.id,
            AaRetakeApply.course_id == grade.course_id,
            AaRetakeApply.status.notin_([_legacy._RT_REJECTED]),
            AaRetakeApply.is_deleted.is_(False),
        ).all()
        if any(row.status in (_legacy._RT_SUBMITTED, _legacy._RT_REVIEW) for row in history):
            raise _legacy._conflict("该课程已有在途重修申请")
        maximum = int(_legacy._rule("retake_max_count", 2))
        if len(history) >= maximum:
            raise _legacy._bad(f"该课程重修次数已达上限{maximum}次")
        row = AaRetakeApply(
            tenant_id=_legacy._tid(), student_id=student.id, student_no=student.student_no,
            student_name=student.real_name, acad_student_id=academic_student.id,
            course_id=grade.course_id, course_name=grade.course_name, term_code=term_code,
            reason=getattr(body, "reason", None), retake_count=len(history) + 1,
            status=_legacy._RT_SUBMITTED,
        )
        db.add(row)
        db.flush()
        _legacy._audit(db, "AA_RETAKE", row.id, "RETAKE_APPLY_IDENTITY", f"gradeId={grade.id};courseId={grade.course_id}")
        db.commit()
        return _legacy._rt_dto(row)


def retake_enroll(user, apply_id, teaching_task_ref=None):
    from app.models import AaRetakeApply, AaTeachingTask, AaTeachingTaskBatch

    with _legacy.session() as db:
        _legacy._require_school(_legacy._ctx(user, db))
        row = db.query(AaRetakeApply).filter(
            AaRetakeApply.id == int(apply_id), AaRetakeApply.tenant_id == _legacy._tid(),
            AaRetakeApply.is_deleted.is_(False),
        ).with_for_update().first()
        if not row:
            raise not_found("重修申请不存在")
        term = _term._guard_code(db, row.term_code)
        if row.status != _legacy._RT_APPROVED:
            raise _legacy._invalid("仅APPROVED申请可编入跟班")
        if not row.course_id:
            raise AppException("DATA_CONFLICT", "重修申请缺少courseId，请退回后重新申请", http_status=409)
        if not teaching_task_ref:
            raise AppException("VALIDATION_ERROR", "重修必须编入真实教学任务")
        task = db.query(AaTeachingTask).filter(
            AaTeachingTask.id == int(teaching_task_ref), AaTeachingTask.tenant_id == _legacy._tid(),
            AaTeachingTask.is_deleted.is_(False),
        ).first()
        if not task:
            raise not_found("教学任务不存在")
        task_batch = db.query(AaTeachingTaskBatch).filter(
            AaTeachingTaskBatch.id == task.batch_id, AaTeachingTaskBatch.tenant_id == _legacy._tid(),
            AaTeachingTaskBatch.is_deleted.is_(False),
        ).first()
        if not task_batch or int(task_batch.term_id or 0) != int(term.id):
            raise AppException("DATA_CONFLICT", "重修申请与跟班教学任务不属于同一学期", http_status=409)
        if int(task.course_id or 0) != int(row.course_id):
            raise AppException("DATA_CONFLICT", "跟班教学任务课程版本与重修申请不一致", http_status=409)
        row.status = _legacy._RT_ENROLLED
        row.teaching_task_ref = task.id
        _legacy._audit(db, "AA_RETAKE", row.id, "RETAKE_ENROLL_IDENTITY", f"taskId={task.id};courseId={task.course_id}")
        db.commit()
        return _legacy._rt_dto(row)


def exemption_apply(user, body):
    from app.models import AaCourse, AaExemption

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
            AaCourse.id == int(course_id), AaCourse.tenant_id == _legacy._tid(),
            AaCourse.is_deleted.is_(False),
        ).first()
        if not course:
            raise not_found("课程版本不存在")
        academic_student = _academic_student_for_profile(db, student.id)
        if academic_student:
            rows = db.query(_grade.AcademicGrade if hasattr(_grade, "AcademicGrade") else __import__("app.models", fromlist=["AcademicGrade"]).AcademicGrade).filter()
            from app.models import AcademicGrade
            grades = db.query(AcademicGrade).filter(
                AcademicGrade.tenant_id == _legacy._tid(), AcademicGrade.acad_student_id == academic_student.id,
                AcademicGrade.course_code == course.course_code, AcademicGrade.record_status == "ACTIVE",
                AcademicGrade.is_deleted.is_(False),
            ).all()
            if any(str(row.pass_status or "").upper() == "PASSED" for row in _grade.effective_grade_rows(grades)):
                raise _legacy._bad("该课程已获及格成绩，不可申请免修")
        maximum = int(_legacy._rule("exemption_max_count", 2))
        used = db.query(AaExemption).filter(
            AaExemption.tenant_id == _legacy._tid(), AaExemption.student_id == student.id,
            AaExemption.term_code == term_code,
            AaExemption.status.notin_([_legacy._EX_REJECTED, _legacy._EX_CANCELLED]),
            AaExemption.is_deleted.is_(False),
        ).count()
        if used >= maximum:
            raise _legacy._bad(f"本学期免修申请已达上限{maximum}门")
        material_ids = _term.json.dumps([str(value) for value in (getattr(body, "materialFileIds", None) or [])], ensure_ascii=False) if getattr(body, "materialFileIds", None) else None
        row = AaExemption(
            tenant_id=_legacy._tid(), student_id=student.id, student_no=student.student_no,
            student_name=student.real_name, course_id=course.id, course_name=course.course_name,
            term_code=term_code, college_id=getattr(student, "college_id", None),
            reason=getattr(body, "reason", None), material_file_ids=material_ids,
            current_node=_legacy._EX_TEACHER, status=_legacy._EX_TEACHER,
        )
        db.add(row)
        db.flush()
        _legacy._audit(db, "AA_EXEMPTION", row.id, "EXEMPTION_APPLY_IDENTITY", f"courseId={course.id};version={course.version}")
        db.commit()
        return _legacy._ex_dto(row)


def exemption_review(user, exemption_id, action, reason=""):
    from app.models import AaCourse, AaExemption, AcademicGrade

    with _legacy.session() as db:
        _legacy._ctx(user, db)
        row = db.query(AaExemption).filter(
            AaExemption.id == int(exemption_id), AaExemption.tenant_id == _legacy._tid(),
            AaExemption.is_deleted.is_(False),
        ).with_for_update().first()
        if not row:
            raise not_found("免修申请不存在")
        _term._guard_code(db, row.term_code)
        if row.status not in _legacy._EX_CHAIN:
            raise AppException("APPROVAL_VERSION_CONFLICT", "该申请已处理", http_status=409)
        action_code = str(action or "").upper()
        if action_code in {"RETURN", "REJECT"}:
            reason_text = (reason or "").strip()
            if len(reason_text) < 5:
                raise _legacy._bad("退回/驳回原因必填且不少于5字")
            row.status = _legacy._EX_SUBMITTED if action_code == "RETURN" else _legacy._EX_REJECTED
            row.current_node = _legacy._EX_SUBMITTED if action_code == "RETURN" else None
            row.return_reason = reason_text
            _legacy._audit(db, "AA_EXEMPTION", row.id, "EXEMPTION_REVIEW", f"{action_code}->{row.status}")
            db.commit()
            return _legacy._ex_dto(row)
        if action_code != "APPROVE":
            raise _legacy._bad("非法审批动作")

        next_status = _legacy._EX_CHAIN[row.status]
        if next_status == _legacy._EX_APPROVED:
            if not row.course_id:
                raise AppException("DATA_CONFLICT", "免修申请缺少courseId，请退回后重新提交", http_status=409)
            course = db.query(AaCourse).filter(
                AaCourse.id == int(row.course_id), AaCourse.tenant_id == _legacy._tid(),
                AaCourse.is_deleted.is_(False),
            ).first()
            if not course or not course.course_code or not course.version:
                raise AppException("DATA_CONFLICT", "免修目标课程版本无效", http_status=409)
            academic_student = _academic_student_for_profile(db, row.student_id)
            if not academic_student:
                academic_student = _grade._legacy._acad_student_id(db, row.student_id, row.student_name or "")
            duplicate = db.query(AcademicGrade).filter(
                AcademicGrade.tenant_id == _legacy._tid(),
                AcademicGrade.source_biz_type == "EXEMPTION",
                AcademicGrade.source_biz_id == row.id,
                AcademicGrade.is_deleted.is_(False),
            ).first()
            if not duplicate:
                attempt_no = next_study_attempt_no(db, academic_student.id, course.course_code)
                db.add(AcademicGrade(
                    tenant_id=_legacy._tid(), acad_student_id=academic_student.id,
                    course_id=course.id, course_code=course.course_code,
                    course_version=int(course.version), attempt_no=attempt_no,
                    source_biz_type="EXEMPTION", source_biz_id=row.id,
                    course_name=course.course_name, term=row.term_code,
                    nature=course.nature or "REQUIRED", credit_value=course.credit or 0,
                    score=None, pass_status="PASSED", exam_type="EXEMPTION",
                    source="EXEMPTION", record_status="ACTIVE",
                ))
                db.flush()
                _grade._legacy._refresh_aggregates(db, academic_student)
        row.status = next_status
        row.current_node = None if next_status == _legacy._EX_APPROVED else next_status
        _legacy._audit(db, "AA_EXEMPTION", row.id, "EXEMPTION_REVIEW", f"APPROVE->{row.status};courseId={row.course_id}")
        db.commit()
        return _legacy._ex_dto(row)


# 全链替换。
for module in (_base, _term, _legacy):
    module.enroll_makeup = enroll_makeup
    module.enroll_makeup_by_grade = enroll_makeup_by_grade
    module.clearance_scan = clearance_scan
    module.finish_makeup_batch = finish_makeup_batch
    module.retake_apply = retake_apply
    module.retake_enroll = retake_enroll
    module.exemption_apply = exemption_apply
    module.exemption_review = exemption_review
