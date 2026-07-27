"""补考、清考、重修、免修唯一公开 Service。

原统计、提醒、导出等兼容能力保存在 ``academic_affairs_makeup_core_service``；本文件显式收口：
- 学生本人只通过稳定账号绑定解析；
- 补考/清考候选只消费统一有效成绩；
- 名单只按 gradeId/courseId 纳入，禁止课程名猜测；
- 补考、清考和缓考结果保存稳定课程、修读次数、来源业务、教学任务与名单版本；
- 正式成绩写入时显式冻结有效成绩策略并刷新学业聚合；
- 重修编班在同一事务生成新的正式教学班名单版本；
- 所有写动作在同一事务校验学期未归档。

不修改其它模块函数，不依赖 Facade 导入顺序。
"""
from __future__ import annotations

import json
from datetime import datetime

from sqlalchemy import select

from app.core.context import get_current_user_ctx
from app.core.exceptions import AppException, no_data_scope, not_found

from . import academic_affairs_grade_service as grade_service
from . import academic_affairs_makeup_core_service as _core
from . import academic_affairs_teaching_class_service as teaching_class_service
from .academic_affairs_effective_grade_policy_service import freeze_effective_grade_policy
from .academic_affairs_grade_identity_service import next_study_attempt_no, source_attempt_no
from .academic_affairs_roster_consumer_service import consumer_counts, get_consumer_snapshot

_ELIGIBLE_STUDENT_STATUSES = {"NORMAL", "REGISTERED", "ON_CAMPUS"}


def __getattr__(name):
    """未重写的统计、提醒和导出能力显式复用稳定 core。"""
    return getattr(_core, name)


def _value(body, name, default=None):
    if isinstance(body, dict):
        return body.get(name, default)
    return getattr(body, name, default)


def _term_code(term) -> str:
    return f"{term.year_code}-{term.term_no}"


def _guard_term_id(db, term_id):
    from . import academic_affairs_archive_service as archive_service

    if not term_id:
        raise AppException("DATA_CONFLICT", "业务记录未绑定正式学期termId", http_status=409)
    archive_service.guard_term_writable(db, int(term_id))


def _guard_code(db, term_code):
    from . import academic_affairs_archive_service as archive_service

    return archive_service.guard_term_code_writable(db, str(term_code or "").strip())


def _current_term(db):
    from app.models import AaTerm

    term = db.query(AaTerm).filter(
        AaTerm.tenant_id == _core._tid(),
        AaTerm.is_current.is_(True),
        AaTerm.is_deleted.is_(False),
    ).first()
    if not term:
        raise AppException("DATA_CONFLICT", "学校尚未设置当前办理学期", http_status=409)
    _guard_term_id(db, term.id)
    return term


def _selected_term(db, requested_code=None):
    code = str(requested_code or "").strip()
    return _guard_code(db, code) if code else _current_term(db)


def _guard_batch(db, batch):
    term = None
    if getattr(batch, "term_code", None):
        term = _guard_code(db, batch.term_code)
    if getattr(batch, "term_id", None):
        _guard_term_id(db, batch.term_id)
        if term is not None and int(term.id) != int(batch.term_id):
            raise AppException(
                "DATA_CONFLICT",
                "补考批次termId与termCode指向不同学期，请先修复基础数据",
                http_status=409,
            )
    elif term is not None:
        batch.term_id = term.id
    else:
        raise AppException("DATA_CONFLICT", "补考批次未绑定正式学期", http_status=409)
    return term


def _student(db, user=None):
    """学生本人只认稳定studentId/账号绑定；无法证明唯一身份时fail-closed。"""
    from app.services.mobile_student_identity_facade import resolve_student

    profile = resolve_student(db, user or get_current_user_ctx() or {})
    if not profile:
        raise not_found("当前账号尚未绑定唯一学生档案")
    return profile


def _academic_student_for_profile(db, profile_id):
    from app.models import AcademicStudent

    return db.query(AcademicStudent).filter(
        AcademicStudent.tenant_id == _core._tid(),
        AcademicStudent.student_id == int(profile_id),
        AcademicStudent.is_deleted.is_(False),
    ).first()


def _scope_students(ctx, db, students):
    allowed = ctx.allowed_class_ids(db)
    if allowed is None:
        return list(students or [])
    allowed_ids = {str(int(value)) for value in allowed if str(value).isdigit()}
    if not allowed_ids:
        return []
    return [row for row in (students or []) if str(row.class_id or "") in allowed_ids]


def _effective_failed_rows(rows):
    return [
        row for row in grade_service.effective_grade_rows(rows)
        if str(row.pass_status or "").upper() in {"FAIL", "FAILED"}
    ]


def _effective_failed_grade(db, academic_student_id: int, grade_id: int):
    from app.models import AcademicGrade

    rows = db.query(AcademicGrade).filter(
        AcademicGrade.tenant_id == _core._tid(),
        AcademicGrade.acad_student_id == int(academic_student_id),
        AcademicGrade.record_status == "ACTIVE",
        AcademicGrade.is_deleted.is_(False),
    ).all()
    effective = _effective_failed_rows(rows)
    selected = next((row for row in effective if int(row.id) == int(grade_id)), None)
    if not selected:
        raise AppException(
            "APPROVAL_VERSION_CONFLICT",
            "所选成绩已不是当前有效挂科结果，请刷新候选名单",
            details={"effectiveFailedGradeIds": [str(row.id) for row in effective]},
            http_status=409,
        )
    if not selected.course_id or not selected.course_code or not selected.course_version or not selected.attempt_no:
        raise AppException(
            "DATA_CONFLICT",
            "所选挂科成绩缺少courseId、课程版本或修读次数，请先完成成绩身份治理",
            details={"gradeId": str(selected.id)},
            http_status=409,
        )
    source_attempt_no(selected)
    return selected


def makeup_pending(user, term=None, page=1, page_size=50):
    """范围内当前有效挂科成绩；已被补考/清考/更正覆盖的旧失败行不再出现。"""
    from app.models import AcademicGrade, AcademicStudent

    with _core.session() as db:
        ctx = _core._ctx(user, db)
        students = _scope_students(
            ctx,
            db,
            db.query(AcademicStudent).filter(
                AcademicStudent.tenant_id == _core._tid(),
                AcademicStudent.is_deleted.is_(False),
            ).all(),
        )
        student_by_id = {int(row.id): row for row in students}
        query = db.query(AcademicGrade).filter(
            AcademicGrade.tenant_id == _core._tid(),
            AcademicGrade.acad_student_id.in_(list(student_by_id) or [0]),
            AcademicGrade.record_status == "ACTIVE",
            AcademicGrade.is_deleted.is_(False),
        )
        if term:
            query = query.filter(AcademicGrade.term == term)
        failed = _effective_failed_rows(query.all())
        items = []
        for grade in failed:
            student = student_by_id.get(int(grade.acad_student_id))
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
                "courseVersion": grade.course_version,
                "attemptNo": grade.attempt_no,
                "courseName": grade.course_name,
                "score": grade.score,
                "effectiveSource": grade.source,
                "identityReady": identity_ready,
            })
        items.sort(key=lambda row: (row["courseCode"] or row["courseName"] or "", row["studentNo"] or ""))
        total = len(items)
        start = (max(1, int(page)) - 1) * int(page_size)
        return items[start:start + int(page_size)], total


def create_makeup_batch(user, body):
    from app.models import AaExamBatch, AaMakeupBatch

    with _core.session() as db:
        _core._require_school(_core._ctx(user, db))
        name = str(_value(body, "batchName") or "").strip()
        if not name:
            raise _core._bad("批次名称必填")
        term = _selected_term(db, _value(body, "termCode"))
        exam_ref = int(_value(body, "examBatchRef")) if _value(body, "examBatchRef") else None
        if exam_ref:
            exam = db.query(AaExamBatch).filter(
                AaExamBatch.id == exam_ref,
                AaExamBatch.tenant_id == _core._tid(),
                AaExamBatch.is_deleted.is_(False),
            ).first()
            if not exam:
                raise not_found("考务批次不存在")
            if int(exam.term_id or 0) != int(term.id):
                raise AppException("DATA_CONFLICT", "补考批次与考务批次不属于同一学期", http_status=409)
        batch = AaMakeupBatch(
            tenant_id=_core._tid(),
            batch_name=name,
            term_id=term.id,
            term_code=_term_code(term),
            exam_batch_ref=exam_ref,
            score_rule=_core._rule("makeup_score_rule", "CAP60"),
            status=_core._MB_DRAFT,
        )
        db.add(batch)
        db.flush()
        _core._audit(db, "AA_MAKEUP", batch.id, "MAKEUP_BATCH_CREATE", name)
        db.commit()
        return _core._mb_dto(batch)


def create_clearance_batch(user, body):
    from app.models import AaMakeupBatch

    with _core.session() as db:
        _core._require_school(_core._ctx(user, db))
        name = str(_value(body, "batchName") or "").strip()
        if not name:
            raise _core._bad("批次名称必填")
        grades = [
            str(value).strip() for value in (_value(body, "targetGrades", []) or [])
            if str(value).strip()
        ]
        if not grades:
            raise _core._bad("清考必须限定毕业年级（如2022）")
        term = _selected_term(db, _value(body, "termCode"))
        batch = AaMakeupBatch(
            tenant_id=_core._tid(),
            batch_name=name,
            kind="CLEARANCE",
            target_grades=",".join(grades),
            term_id=term.id,
            term_code=_term_code(term),
            score_rule="CAP60",
            status=_core._MB_DRAFT,
        )
        db.add(batch)
        db.flush()
        _core._audit(db, "AA_MAKEUP", batch.id, "CLEARANCE_BATCH_CREATE", f"{name} 年级{grades}")
        db.commit()
        return _core._mb_dto(batch)


def link_exam_batch(user, batch_id, exam_batch_id):
    from app.models import AaExamBatch

    with _core.session() as db:
        _core._require_school(_core._ctx(user, db))
        batch = _core._get_mb(db, int(batch_id))
        term = _guard_batch(db, batch)
        if batch.status not in {_core._MB_DRAFT, _core._MB_ARRANGED}:
            raise _core._invalid("仅DRAFT/ARRANGED补考批次可挂考务编排")
        exam = db.query(AaExamBatch).filter(
            AaExamBatch.id == int(exam_batch_id),
            AaExamBatch.tenant_id == _core._tid(),
            AaExamBatch.is_deleted.is_(False),
        ).first()
        if not exam:
            raise not_found("考务批次不存在")
        if int(exam.term_id or 0) != int((term.id if term else batch.term_id) or 0):
            raise AppException("DATA_CONFLICT", "补考批次与考务批次不属于同一学期", http_status=409)
        batch.exam_batch_ref = exam.id
        if batch.status == _core._MB_DRAFT:
            batch.status = _core._MB_ARRANGED
        _core._audit(db, "AA_MAKEUP", batch.id, "MAKEUP_LINK_EXAM", f"挂考务批次{exam.batch_name}")
        db.commit()
        return _core._mb_dto(batch)


def enroll_makeup_by_grade(user, batch_id, grade_id, acad_student_id, origin_score=None):
    from app.models import AcademicMakeup

    with _core.session() as db:
        _core._require_school(_core._ctx(user, db))
        batch = _core._get_mb(db, int(batch_id))
        _guard_batch(db, batch)
        if batch.status not in {_core._MB_DRAFT, _core._MB_ARRANGED}:
            raise _core._invalid("仅DRAFT/ARRANGED批次可纳入名单")
        grade = _effective_failed_grade(db, int(acad_student_id), int(grade_id))
        duplicate = db.query(AcademicMakeup).filter(
            AcademicMakeup.tenant_id == _core._tid(),
            AcademicMakeup.batch_id == batch.id,
            AcademicMakeup.origin_grade_id == grade.id,
            AcademicMakeup.is_deleted.is_(False),
        ).first()
        if duplicate:
            return {
                "makeupId": str(duplicate.id),
                "status": duplicate.status,
                "originGradeId": str(grade.id),
                "idempotent": True,
            }
        row = AcademicMakeup(
            tenant_id=_core._tid(),
            acad_student_id=int(acad_student_id),
            kind=batch.kind or "MAKEUP",
            origin_grade_id=grade.id,
            course_id=grade.course_id,
            course_code=grade.course_code,
            course_version=grade.course_version,
            attempt_no=source_attempt_no(grade),
            teaching_task_id=grade.teaching_task_id,
            teaching_class_id=grade.teaching_class_id,
            roster_version_id=grade.roster_version_id,
            course_name=grade.course_name,
            term=grade.term,
            origin_score=grade.score if origin_score is None else int(origin_score),
            batch_id=batch.id,
            status="PENDING_EXAM",
            record_status="ACTIVE",
        )
        db.add(row)
        db.flush()
        if batch.status == _core._MB_DRAFT:
            batch.status = _core._MB_ARRANGED
        _core._audit(
            db,
            "AA_MAKEUP",
            row.id,
            "MAKEUP_ENROLL_IDENTITY",
            (
                f"originGradeId={grade.id};courseId={grade.course_id};version={grade.course_version};"
                f"attemptNo={grade.attempt_no}"
            ),
        )
        db.commit()
        return {
            "makeupId": str(row.id),
            "status": row.status,
            "originGradeId": str(grade.id),
            "courseId": str(grade.course_id),
            "courseCode": grade.course_code,
            "courseVersion": grade.course_version,
            "attemptNo": grade.attempt_no,
            "idempotent": False,
        }


def enroll_makeup(user, batch_id, acad_student_id, course_name, origin_score=None):
    raise AppException(
        "VALIDATION_ERROR",
        "旧的按课程名称纳入补考入口已停用，请从补考候选名单提交gradeId",
    )


def _clearance_candidates(db, target_grades):
    from app.models import AcademicGrade, AcademicStudent, StudentProfile

    profiles = db.query(StudentProfile).filter(
        StudentProfile.tenant_id == _core._tid(),
        StudentProfile.grade.in_(target_grades or ["__none__"]),
        StudentProfile.student_status.in_(sorted(_ELIGIBLE_STUDENT_STATUSES)),
        StudentProfile.is_deleted.is_(False),
    ).all()
    profile_by_id = {int(row.id): row for row in profiles}
    students = db.query(AcademicStudent).filter(
        AcademicStudent.tenant_id == _core._tid(),
        AcademicStudent.student_id.in_(list(profile_by_id) or [0]),
        AcademicStudent.is_deleted.is_(False),
    ).all()
    output = []
    for student in students:
        rows = db.query(AcademicGrade).filter(
            AcademicGrade.tenant_id == _core._tid(),
            AcademicGrade.acad_student_id == student.id,
            AcademicGrade.record_status == "ACTIVE",
            AcademicGrade.is_deleted.is_(False),
        ).all()
        for grade in _effective_failed_rows(rows):
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
                "effectiveScore": grade.score,
                "identityReady": ready,
            })
    output.sort(key=lambda row: (row["studentNo"] or "", row["courseCode"] or row["courseName"] or ""))
    return output


def clearance_scan(user, batch_id, dry_run=False):
    from app.models import AcademicMakeup

    with _core.session() as db:
        _core._require_school(_core._ctx(user, db))
        batch = _core._get_mb(db, int(batch_id))
        _guard_batch(db, batch)
        if (batch.kind or "MAKEUP") != "CLEARANCE":
            raise _core._invalid("仅清考批次可执行名单扫描")
        if batch.status not in {_core._MB_DRAFT, _core._MB_ARRANGED}:
            raise _core._invalid("仅DRAFT/ARRANGED批次可圈定名单")
        target_grades = [value for value in str(batch.target_grades or "").split(",") if value]
        candidates = _clearance_candidates(db, target_grades)
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
                    AcademicMakeup.tenant_id == _core._tid(),
                    AcademicMakeup.batch_id == batch.id,
                    AcademicMakeup.origin_grade_id == int(candidate["gradeId"]),
                    AcademicMakeup.is_deleted.is_(False),
                ).first()
                if duplicate:
                    skipped += 1
                    continue
                db.add(AcademicMakeup(
                    tenant_id=_core._tid(),
                    acad_student_id=int(candidate["acadStudentId"]),
                    kind="CLEARANCE",
                    origin_grade_id=int(candidate["gradeId"]),
                    course_id=int(candidate["courseId"]),
                    course_code=candidate["courseCode"],
                    course_version=int(candidate["courseVersion"]),
                    attempt_no=int(candidate["attemptNo"]),
                    course_name=candidate["courseName"],
                    origin_score=candidate["effectiveScore"],
                    batch_id=batch.id,
                    status="PENDING_EXAM",
                    record_status="ACTIVE",
                ))
                added += 1
            if added and batch.status == _core._MB_DRAFT:
                batch.status = _core._MB_ARRANGED
            _core._audit(
                db,
                "AA_MAKEUP",
                batch.id,
                "CLEARANCE_SCAN_IDENTITY",
                f"added={added};skipped={skipped};identityDebt={len(debts)}",
            )
            db.commit()
        return {
            "batchId": str(batch.id),
            "dryRun": bool(dry_run),
            "candidates": len(candidates),
            "identityDebtCount": len(debts),
            "added": 0 if dry_run else added,
            "skipped": 0 if dry_run else skipped,
            "items": candidates,
        }


def publish_makeup_batch(user, batch_id):
    from app.models import AcademicMakeup

    with _core.session() as db:
        _core._require_school(_core._ctx(user, db))
        batch = _core._get_mb(db, int(batch_id))
        _guard_batch(db, batch)
        if batch.status != _core._MB_ARRANGED:
            raise _core._invalid("仅ARRANGED批次可发布")
        records = db.query(AcademicMakeup).filter(
            AcademicMakeup.tenant_id == _core._tid(),
            AcademicMakeup.batch_id == batch.id,
            AcademicMakeup.is_deleted.is_(False),
        ).all()
        if not records:
            raise AppException("DATA_CONFLICT", "补考批次没有有效名单，不可发布", http_status=409)
        identity_debt = [
            row for row in records
            if not row.course_id or not row.course_code or not row.course_version or not row.attempt_no
        ]
        if identity_debt:
            raise AppException(
                "DATA_CONFLICT",
                f"补考名单有{len(identity_debt)}条缺少稳定课程身份，禁止发布",
                details={"makeupIds": [str(row.id) for row in identity_debt[:100]]},
                http_status=409,
            )
        batch.status = _core._MB_PUBLISHED
        batch.published_at = datetime.utcnow()
        _core._audit(db, "AA_MAKEUP", batch.id, "MAKEUP_BATCH_PUBLISH", f"名单{len(records)}条")
        db.commit()
        return _core._mb_dto(batch)


def enter_makeup_score(user, makeup_id, score):
    from app.models import AcademicMakeup

    if isinstance(score, bool):
        raise AppException("VALIDATION_ERROR", "补考成绩须为0-100整数")
    try:
        numeric = float(score)
    except (TypeError, ValueError) as exc:
        raise AppException("VALIDATION_ERROR", "补考成绩须为0-100整数") from exc
    if not numeric.is_integer() or numeric < 0 or numeric > 100:
        raise AppException("VALIDATION_ERROR", "补考成绩须为0-100整数")

    with _core.session() as db:
        _core._require_school(_core._ctx(user, db))
        row = db.query(AcademicMakeup).filter(
            AcademicMakeup.id == int(makeup_id),
            AcademicMakeup.tenant_id == _core._tid(),
            AcademicMakeup.is_deleted.is_(False),
        ).with_for_update().first()
        if not row:
            raise not_found("补考记录不存在")
        batch = _core._get_mb(db, int(row.batch_id))
        _guard_batch(db, batch)
        if batch.status not in {_core._MB_PUBLISHED, _core._MB_SCORING}:
            raise _core._invalid("批次未发布，不可录入")
        row.final_score = int(numeric)
        row.status = "SCORED"
        if batch.status == _core._MB_PUBLISHED:
            batch.status = _core._MB_SCORING
        _core._audit(db, "AA_MAKEUP", row.id, "MAKEUP_SCORE", f"成绩{row.final_score}")
        db.commit()
        return {"makeupId": str(row.id), "finalScore": row.final_score, "status": row.status}


def college_review_scores(user, batch_id):
    from app.models import AcademicMakeup

    with _core.session() as db:
        _core._require_school(_core._ctx(user, db))
        batch = _core._get_mb(db, int(batch_id))
        _guard_batch(db, batch)
        if batch.status != _core._MB_SCORING:
            raise _core._invalid("仅SCORING批次可学院审核")
        records = db.query(AcademicMakeup).filter(
            AcademicMakeup.tenant_id == _core._tid(),
            AcademicMakeup.batch_id == batch.id,
            AcademicMakeup.is_deleted.is_(False),
        ).all()
        if not records:
            raise AppException("DATA_CONFLICT", "批次没有成绩记录", http_status=409)
        pending = [row for row in records if row.status != "SCORED" or row.final_score is None]
        if pending:
            raise _core._invalid(f"尚有{len(pending)}条补考成绩未录入，不可提交学院审核")
        batch.status = _core._MB_REVIEWED
        _core._audit(db, "AA_MAKEUP", batch.id, "MAKEUP_COLLEGE_REVIEW", f"审核{len(records)}条")
        db.commit()
        return _core._mb_dto(batch)


def _regular_origin(db, row):
    if not row.origin_grade_id:
        raise AppException("DATA_CONFLICT", "补考/清考名单未冻结originGradeId", http_status=409)
    origin = _effective_failed_grade(db, int(row.acad_student_id), int(row.origin_grade_id))
    expected = (
        int(origin.course_id or 0),
        str(origin.course_code or ""),
        int(origin.course_version or 0),
        int(origin.attempt_no or 0),
    )
    frozen = (
        int(row.course_id or 0),
        str(row.course_code or ""),
        int(row.course_version or 0),
        int(row.attempt_no or 0),
    )
    if expected != frozen:
        raise AppException(
            "APPROVAL_VERSION_CONFLICT",
            "补考名单冻结课程身份与原成绩不一致，请先治理数据",
            details={"makeupId": str(row.id), "originGradeId": str(origin.id)},
            http_status=409,
        )
    return {
        "courseId": int(origin.course_id),
        "courseCode": origin.course_code,
        "courseVersion": int(origin.course_version),
        "attemptNo": int(origin.attempt_no),
        "courseName": origin.course_name,
        "nature": origin.nature,
        "credit": origin.credit_value,
        "gradeTaskId": origin.grade_task_id,
        "teachingTaskId": origin.teaching_task_id,
        "teachingClassId": origin.teaching_class_id,
        "rosterVersionId": origin.roster_version_id,
        "sourceBizType": "CLEARANCE" if row.kind == "CLEARANCE" else "MAKEUP",
        "sourceBizId": int(row.id),
        "gradeSource": "CLEARANCE" if row.kind == "CLEARANCE" else "MAKEUP",
        "examType": "CLEARANCE" if row.kind == "CLEARANCE" else "MAKEUP",
    }


def _deferred_identity(db, row):
    from app.models import AaCourse

    if row.kind != "DEFERRED" or row.source_biz_type != "DEFERRED_EXAM" or not row.source_biz_id:
        raise AppException("DATA_CONFLICT", "缓考后续考试缺少精确来源回链", http_status=409)
    if not all((row.course_id, row.course_code, row.course_version, row.attempt_no,
                row.teaching_task_id, row.teaching_class_id, row.roster_version_id)):
        raise AppException("DATA_CONFLICT", "缓考后续考试缺少课程或名单版本身份", http_status=409)
    course = db.query(AaCourse).filter(
        AaCourse.id == int(row.course_id),
        AaCourse.tenant_id == _core._tid(),
        AaCourse.is_deleted.is_(False),
    ).first()
    if not course:
        raise not_found("缓考对应课程版本不存在")
    if str(course.course_code or "") != str(row.course_code or "") or int(course.version or 0) != int(row.course_version):
        raise AppException("APPROVAL_VERSION_CONFLICT", "缓考冻结课程版本与课程库当前行不一致", http_status=409)
    return {
        "courseId": int(row.course_id),
        "courseCode": row.course_code,
        "courseVersion": int(row.course_version),
        "attemptNo": int(row.attempt_no),
        "courseName": row.course_name,
        "nature": course.nature or "REQUIRED",
        "credit": course.credit or 0,
        "gradeTaskId": None,
        "teachingTaskId": int(row.teaching_task_id),
        "teachingClassId": int(row.teaching_class_id),
        "rosterVersionId": int(row.roster_version_id),
        "sourceBizType": "DEFERRED_EXAM",
        "sourceBizId": int(row.source_biz_id),
        "gradeSource": "DEFERRED",
        "examType": "DEFERRED",
    }


def finish_makeup_batch(user, batch_id):
    """REVIEWED→FINISHED：按冻结来源幂等生成正式成绩并显式冻结策略快照。"""
    from app.models import AcademicGrade, AcademicMakeup, AcademicStudent

    with _core.session() as db:
        _core._require_school(_core._ctx(user, db))
        batch = _core._get_mb(db, int(batch_id))
        _guard_batch(db, batch)
        if batch.status == _core._MB_FINISHED:
            return _core._mb_dto(batch)
        if batch.status != _core._MB_REVIEWED:
            raise _core._invalid("仅学院审核通过(REVIEWED)的批次可教务发布回写")
        records = db.query(AcademicMakeup).filter(
            AcademicMakeup.tenant_id == _core._tid(),
            AcademicMakeup.batch_id == batch.id,
            AcademicMakeup.status == "SCORED",
            AcademicMakeup.is_deleted.is_(False),
        ).order_by(AcademicMakeup.id).all()
        if not records:
            raise AppException("DATA_CONFLICT", "批次没有已审核成绩，禁止结束", http_status=409)

        cap = 60 if batch.score_rule == "CAP60" else 100
        affected = set()
        projected = 0
        source_counts = {}
        for row in records:
            identity = _deferred_identity(db, row) if row.kind == "DEFERRED" else _regular_origin(db, row)
            final_score = int(row.final_score or 0)
            passed = final_score >= 60
            recorded_score = min(final_score, cap) if passed else final_score
            grade = db.query(AcademicGrade).filter(
                AcademicGrade.tenant_id == _core._tid(),
                AcademicGrade.source_biz_type == identity["sourceBizType"],
                AcademicGrade.source_biz_id == identity["sourceBizId"],
                AcademicGrade.is_deleted.is_(False),
            ).with_for_update().first()
            if not grade:
                grade = AcademicGrade(
                    tenant_id=_core._tid(),
                    acad_student_id=row.acad_student_id,
                    course_id=identity["courseId"],
                    course_code=identity["courseCode"],
                    course_version=identity["courseVersion"],
                    attempt_no=identity["attemptNo"],
                    grade_task_id=identity["gradeTaskId"],
                    source_biz_type=identity["sourceBizType"],
                    source_biz_id=identity["sourceBizId"],
                    teaching_task_id=identity["teachingTaskId"],
                    teaching_class_id=identity["teachingClassId"],
                    roster_version_id=identity["rosterVersionId"],
                    course_name=identity["courseName"],
                    term=batch.term_code,
                    nature=identity["nature"],
                    credit_value=identity["credit"],
                    score=recorded_score,
                    pass_status="PASSED" if passed else "FAILED",
                    exam_type=identity["examType"],
                    source=identity["gradeSource"],
                    record_status="ACTIVE",
                )
                db.add(grade)
                db.flush()
            else:
                grade.acad_student_id = row.acad_student_id
                grade.course_id = identity["courseId"]
                grade.course_code = identity["courseCode"]
                grade.course_version = identity["courseVersion"]
                grade.attempt_no = identity["attemptNo"]
                grade.grade_task_id = identity["gradeTaskId"]
                grade.teaching_task_id = identity["teachingTaskId"]
                grade.teaching_class_id = identity["teachingClassId"]
                grade.roster_version_id = identity["rosterVersionId"]
                grade.course_name = identity["courseName"]
                grade.term = batch.term_code
                grade.nature = identity["nature"]
                grade.credit_value = identity["credit"]
                grade.score = recorded_score
                grade.pass_status = "PASSED" if passed else "FAILED"
                grade.exam_type = identity["examType"]
                grade.source = identity["gradeSource"]
                grade.record_status = "ACTIVE"
            freeze_effective_grade_policy(
                db,
                grade,
                event_type=identity["gradeSource"],
                source_biz_type=identity["sourceBizType"],
                source_biz_id=identity["sourceBizId"],
            )
            row.status = "FINISHED"
            affected.add(int(row.acad_student_id))
            projected += 1
            source_counts[identity["gradeSource"]] = source_counts.get(identity["gradeSource"], 0) + 1
            _core._audit(
                db,
                "AA_MAKEUP",
                row.id,
                "MAKEUP_GRADE_IDENTITY",
                (
                    f"source={identity['gradeSource']};sourceBiz={identity['sourceBizType']}:{identity['sourceBizId']};"
                    f"courseId={identity['courseId']};attemptNo={identity['attemptNo']};"
                    f"rosterVersionId={identity['rosterVersionId'] or ''}"
                ),
            )

        for academic_student_id in affected:
            student = db.get(AcademicStudent, academic_student_id)
            if student and not student.is_deleted:
                grade_service._refresh_aggregates(db, student)
        batch.status = _core._MB_FINISHED
        _core._audit(
            db,
            "AA_MAKEUP",
            batch.id,
            "MAKEUP_BATCH_FINISH",
            f"projected={projected};students={len(affected)};sources={source_counts}",
        )
        db.commit()
        return {
            **_core._mb_dto(batch),
            "identityProjected": projected,
            "sourceCounts": source_counts,
        }


def retake_apply(user, body):
    from app.models import AaRetakeApply

    with _core.session() as db:
        student = _student(db, user)
        term = _current_term(db)
        requested = str(_value(body, "termCode") or "").strip()
        code = _term_code(term)
        if requested and requested != code:
            raise AppException("VALIDATION_ERROR", "重修报名只能绑定当前办理学期")
        academic_student = _academic_student_for_profile(db, student.id)
        if not academic_student:
            raise not_found("学生学业档案不存在")
        grade_id = _value(body, "gradeId")
        if not grade_id:
            raise AppException("VALIDATION_ERROR", "请从本人当前有效挂科成绩选择gradeId")
        grade = _effective_failed_grade(db, academic_student.id, int(grade_id))
        history = db.query(AaRetakeApply).filter(
            AaRetakeApply.tenant_id == _core._tid(),
            AaRetakeApply.student_id == student.id,
            AaRetakeApply.course_id == grade.course_id,
            AaRetakeApply.status.notin_([_core._RT_REJECTED]),
            AaRetakeApply.is_deleted.is_(False),
        ).all()
        if any(row.status in {_core._RT_SUBMITTED, _core._RT_REVIEW, _core._RT_APPROVED} for row in history):
            raise _core._conflict("该课程已有在途重修申请")
        maximum = int(_core._rule("retake_max_count", 2))
        if len(history) >= maximum:
            raise _core._bad(f"该课程重修次数已达上限{maximum}次")
        row = AaRetakeApply(
            tenant_id=_core._tid(),
            student_id=student.id,
            student_no=student.student_no,
            student_name=student.real_name,
            acad_student_id=academic_student.id,
            course_id=grade.course_id,
            course_name=grade.course_name,
            term_code=code,
            reason=_value(body, "reason"),
            retake_count=len(history) + 1,
            status=_core._RT_SUBMITTED,
        )
        db.add(row)
        db.flush()
        _core._audit(
            db,
            "AA_RETAKE",
            row.id,
            "RETAKE_APPLY_IDENTITY",
            (
                f"originGradeId={grade.id};courseId={grade.course_id};courseCode={grade.course_code};"
                f"courseVersion={grade.course_version};attemptNo={grade.attempt_no}"
            ),
        )
        db.commit()
        result = _core._rt_dto(row)
        result.update({
            "originGradeId": str(grade.id),
            "courseId": str(grade.course_id),
            "courseCode": grade.course_code,
            "courseVersion": grade.course_version,
            "originAttemptNo": grade.attempt_no,
        })
        return result


def retake_review(user, apply_id, action, reason=""):
    from app.models import AaRetakeApply

    with _core.session() as db:
        _core._require_school(_core._ctx(user, db))
        row = db.query(AaRetakeApply).filter(
            AaRetakeApply.id == int(apply_id),
            AaRetakeApply.tenant_id == _core._tid(),
            AaRetakeApply.is_deleted.is_(False),
        ).with_for_update().first()
        if not row:
            raise not_found("重修申请不存在")
        _guard_code(db, row.term_code)
        if row.status not in {_core._RT_SUBMITTED, _core._RT_REVIEW}:
            raise AppException("APPROVAL_VERSION_CONFLICT", "该申请已处理", http_status=409)
        action_code = str(action or "").upper()
        if action_code == "APPROVE":
            row.status = _core._RT_APPROVED
        elif action_code == "REJECT":
            reason_text = str(reason or "").strip()
            if len(reason_text) < 5:
                raise _core._bad("驳回原因必填且不少于5字")
            row.status = _core._RT_REJECTED
            row.review_reason = reason_text
        else:
            raise _core._bad("非法审批动作")
        _core._audit(db, "AA_RETAKE", row.id, "RETAKE_REVIEW", action_code)
        db.commit()
        return _core._rt_dto(row)


def retake_enroll(user, apply_id, teaching_task_ref=None):
    """重修编班同时生成新名单版本；已有下游消费者时禁止静默换版。"""
    from app.models import AaRetakeApply, AaTeachingTask, AaTeachingTaskBatch

    if not teaching_task_ref:
        raise AppException("VALIDATION_ERROR", "重修必须编入真实教学任务")
    with _core.session() as db:
        _core._require_school(_core._ctx(user, db))
        row = db.query(AaRetakeApply).filter(
            AaRetakeApply.id == int(apply_id),
            AaRetakeApply.tenant_id == _core._tid(),
            AaRetakeApply.is_deleted.is_(False),
        ).with_for_update().first()
        if not row:
            raise not_found("重修申请不存在")
        term = _guard_code(db, row.term_code)
        if row.status == _core._RT_ENROLLED and int(row.teaching_task_ref or 0) == int(teaching_task_ref):
            roster = teaching_class_service.resolve_teaching_task_roster(db, int(teaching_task_ref))
            return {**_core._rt_dto(row), "rosterIdentity": roster, "idempotent": True}
        if row.status != _core._RT_APPROVED:
            raise _core._invalid("仅APPROVED申请可编入跟班")
        if not row.course_id:
            raise AppException("DATA_CONFLICT", "重修申请缺少courseId，请退回后重新申请", http_status=409)
        task = db.query(AaTeachingTask).filter(
            AaTeachingTask.id == int(teaching_task_ref),
            AaTeachingTask.tenant_id == _core._tid(),
            AaTeachingTask.is_deleted.is_(False),
        ).first()
        if not task:
            raise not_found("教学任务不存在")
        task_batch = db.query(AaTeachingTaskBatch).filter(
            AaTeachingTaskBatch.id == task.batch_id,
            AaTeachingTaskBatch.tenant_id == _core._tid(),
            AaTeachingTaskBatch.is_deleted.is_(False),
        ).first()
        if not task_batch or int(task_batch.term_id or 0) != int(term.id):
            raise AppException("DATA_CONFLICT", "重修申请与跟班教学任务不属于同一学期", http_status=409)
        if int(task.course_id or 0) != int(row.course_id):
            raise AppException("DATA_CONFLICT", "跟班教学任务课程版本与重修申请不一致", http_status=409)

        teaching_class = teaching_class_service.ensure_teaching_class_for_task(db, int(task.id))
        current = teaching_class_service.resolve_teaching_task_roster(db, int(task.id))
        current_ids = {int(value) for value in current.get("studentIds") or []}
        if int(row.student_id) not in current_ids:
            consumers = consumer_counts(db, teaching_class_id=int(teaching_class.id))
            if int(consumers.get("TOTAL") or 0) > 0:
                raise AppException(
                    "DATA_CONFLICT",
                    "该教学班名单已被考勤、考务或成绩消费，不能静默加入重修学生；请先退回下游任务并走名单换版流程",
                    details={"consumers": consumers, "teachingClassId": str(teaching_class.id)},
                    http_status=409,
                )
            version, _created = teaching_class_service.create_roster_version(
                db,
                teaching_class,
                sorted(current_ids | {int(row.student_id)}),
                source_type="RETAKE",
                source_id=int(row.id),
                member_source_ids={int(row.student_id): int(row.id)},
                reason=f"重修申请{row.id}编入教学任务{task.id}",
            )
        else:
            from app.models import AaTeachingClassRosterVersion

            version = db.get(AaTeachingClassRosterVersion, int(current["rosterVersionId"]))
        row.status = _core._RT_ENROLLED
        row.teaching_task_ref = task.id
        _core._audit(
            db,
            "AA_RETAKE",
            row.id,
            "RETAKE_ENROLL_IDENTITY",
            (
                f"taskId={task.id};courseId={task.course_id};teachingClassId={teaching_class.id};"
                f"rosterVersionId={version.id}"
            ),
        )
        db.commit()
        result = _core._rt_dto(row)
        result.update({
            "teachingClassId": str(teaching_class.id),
            "rosterVersionId": str(version.id),
            "rosterVersionNo": version.version_no,
            "memberCount": version.member_count,
            "idempotent": False,
        })
        return result


def retake_list(user, status=None, student_only=False, page=1, page_size=50):
    from app.models import AaRetakeApply

    with _core.session() as db:
        _core._ctx(user, db)
        query = db.query(AaRetakeApply).filter(
            AaRetakeApply.tenant_id == _core._tid(),
            AaRetakeApply.is_deleted.is_(False),
        )
        if student_only:
            student = _student(db, user)
            query = query.filter(AaRetakeApply.student_id == int(student.id))
        if status:
            query = query.filter(AaRetakeApply.status == status)
        rows = query.order_by(AaRetakeApply.id.desc()).all()
        total = len(rows)
        start = (max(1, int(page)) - 1) * int(page_size)
        return [_core._rt_dto(row) for row in rows[start:start + int(page_size)]], total


def exemption_apply(user, body):
    from app.models import AaCourse, AaExemption, AcademicGrade, FileObject

    with _core.session() as db:
        student = _student(db, user)
        term = _current_term(db)
        requested = str(_value(body, "termCode") or "").strip()
        term_code = _term_code(term)
        if requested and requested != term_code:
            raise AppException("VALIDATION_ERROR", "免修申请只能绑定当前办理学期")
        course_id = _value(body, "courseId")
        if not course_id:
            raise AppException("VALIDATION_ERROR", "免修申请必须选择课程库具体courseId")
        course = db.query(AaCourse).filter(
            AaCourse.id == int(course_id),
            AaCourse.tenant_id == _core._tid(),
            AaCourse.is_deleted.is_(False),
        ).first()
        if not course or not course.course_code or not course.version:
            raise not_found("课程版本不存在或缺少稳定课程身份")
        academic_student = _academic_student_for_profile(db, student.id)
        if academic_student:
            grades = db.query(AcademicGrade).filter(
                AcademicGrade.tenant_id == _core._tid(),
                AcademicGrade.acad_student_id == academic_student.id,
                AcademicGrade.record_status == "ACTIVE",
                AcademicGrade.is_deleted.is_(False),
            ).all()
            passed = [
                row for row in grade_service.effective_grade_rows(grades)
                if str(row.pass_status or "").upper() == "PASSED"
                and (
                    int(row.course_id or 0) == int(course.id)
                    or str(row.course_code or "") == str(course.course_code)
                )
            ]
            if passed:
                raise _core._bad("该课程已获及格成绩，不可申请免修")
        maximum = int(_core._rule("exemption_max_count", 2))
        used = db.query(AaExemption).filter(
            AaExemption.tenant_id == _core._tid(),
            AaExemption.student_id == student.id,
            AaExemption.term_code == term_code,
            AaExemption.status.notin_([_core._EX_REJECTED, _core._EX_CANCELLED]),
            AaExemption.is_deleted.is_(False),
        ).count()
        if used >= maximum:
            raise _core._bad(f"本学期免修申请已达上限{maximum}门")
        raw_ids = _value(body, "materialFileIds", []) or []
        ids = raw_ids if isinstance(raw_ids, list) else [raw_ids]
        int_ids = [int(value) for value in ids if str(value).isdigit()]
        if len(int_ids) != len(ids):
            raise _core._bad("免修材料附件ID格式不正确")
        if int_ids:
            found = db.query(FileObject).filter(
                FileObject.tenant_id == _core._tid(),
                FileObject.id.in_(int_ids),
            ).count()
            if found != len(set(int_ids)):
                raise _core._bad("免修材料附件包含无效文件，请重新上传")
        row = AaExemption(
            tenant_id=_core._tid(),
            student_id=student.id,
            student_no=student.student_no,
            student_name=student.real_name,
            course_id=course.id,
            course_name=course.course_name,
            term_code=term_code,
            college_id=getattr(student, "college_id", None),
            reason=_value(body, "reason"),
            material_file_ids=json.dumps([str(value) for value in int_ids], ensure_ascii=False) if int_ids else None,
            current_node=_core._EX_TEACHER,
            status=_core._EX_TEACHER,
        )
        db.add(row)
        db.flush()
        _core._audit(
            db,
            "AA_EXEMPTION",
            row.id,
            "EXEMPTION_APPLY_IDENTITY",
            f"courseId={course.id};courseCode={course.course_code};version={course.version}",
        )
        db.commit()
        result = _core._ex_dto(row)
        result.update({
            "courseId": str(course.id),
            "courseCode": course.course_code,
            "courseVersion": course.version,
        })
        return result


def exemption_review(user, exemption_id, action, reason=""):
    from app.models import AaCourse, AaExemption, AcademicGrade

    with _core.session() as db:
        _core._ctx(user, db)
        row = db.query(AaExemption).filter(
            AaExemption.id == int(exemption_id),
            AaExemption.tenant_id == _core._tid(),
            AaExemption.is_deleted.is_(False),
        ).with_for_update().first()
        if not row:
            raise not_found("免修申请不存在")
        _guard_code(db, row.term_code)
        if row.status not in _core._EX_CHAIN:
            raise AppException("APPROVAL_VERSION_CONFLICT", "该申请已处理", http_status=409)
        action_code = str(action or "").upper()
        if action_code in {"RETURN", "REJECT"}:
            reason_text = str(reason or "").strip()
            if len(reason_text) < 5:
                raise _core._bad("退回/驳回原因必填且不少于5字")
            row.status = _core._EX_SUBMITTED if action_code == "RETURN" else _core._EX_REJECTED
            row.current_node = _core._EX_SUBMITTED if action_code == "RETURN" else None
            row.return_reason = reason_text
            _core._audit(db, "AA_EXEMPTION", row.id, "EXEMPTION_REVIEW", f"{action_code}->{row.status}")
            db.commit()
            return _core._ex_dto(row)
        if action_code != "APPROVE":
            raise _core._bad("非法审批动作")

        next_status = _core._EX_CHAIN[row.status]
        if next_status == _core._EX_APPROVED:
            if not row.course_id:
                raise AppException("DATA_CONFLICT", "免修申请缺少courseId，请退回后重新提交", http_status=409)
            course = db.query(AaCourse).filter(
                AaCourse.id == int(row.course_id),
                AaCourse.tenant_id == _core._tid(),
                AaCourse.is_deleted.is_(False),
            ).first()
            if not course or not course.course_code or not course.version:
                raise AppException("DATA_CONFLICT", "免修目标课程版本无效", http_status=409)
            academic_student = _academic_student_for_profile(db, row.student_id)
            if not academic_student:
                academic_student = grade_service._core._acad_student_id(db, row.student_id, row.student_name or "")
            active = db.query(AcademicGrade).filter(
                AcademicGrade.tenant_id == _core._tid(),
                AcademicGrade.acad_student_id == academic_student.id,
                AcademicGrade.record_status == "ACTIVE",
                AcademicGrade.is_deleted.is_(False),
            ).all()
            if any(
                str(item.pass_status or "").upper() == "PASSED"
                and (
                    int(item.course_id or 0) == int(course.id)
                    or str(item.course_code or "") == str(course.course_code)
                )
                for item in grade_service.effective_grade_rows(active)
            ):
                raise AppException("APPROVAL_VERSION_CONFLICT", "审批期间该课程已取得及格成绩，申请不再有效", http_status=409)
            grade = db.query(AcademicGrade).filter(
                AcademicGrade.tenant_id == _core._tid(),
                AcademicGrade.source_biz_type == "EXEMPTION",
                AcademicGrade.source_biz_id == row.id,
                AcademicGrade.is_deleted.is_(False),
            ).with_for_update().first()
            if not grade:
                attempt_no = next_study_attempt_no(db, academic_student.id, course.course_code)
                grade = AcademicGrade(
                    tenant_id=_core._tid(),
                    acad_student_id=academic_student.id,
                    course_id=course.id,
                    course_code=course.course_code,
                    course_version=int(course.version),
                    attempt_no=attempt_no,
                    source_biz_type="EXEMPTION",
                    source_biz_id=row.id,
                    course_name=course.course_name,
                    term=row.term_code,
                    nature=course.nature or "REQUIRED",
                    credit_value=course.credit or 0,
                    score=None,
                    pass_status="PASSED",
                    exam_type="EXEMPTION",
                    source="EXEMPTION",
                    record_status="ACTIVE",
                )
                db.add(grade)
                db.flush()
            freeze_effective_grade_policy(
                db,
                grade,
                event_type="EXEMPTION",
                source_biz_type="EXEMPTION",
                source_biz_id=row.id,
            )
            grade_service._refresh_aggregates(db, academic_student)
        row.status = next_status
        row.current_node = None if next_status == _core._EX_APPROVED else next_status
        _core._audit(
            db,
            "AA_EXEMPTION",
            row.id,
            "EXEMPTION_REVIEW",
            f"APPROVE->{row.status};courseId={row.course_id}",
        )
        db.commit()
        return _core._ex_dto(row)


def exemption_list(user, status=None, student_only=False, page=1, page_size=50):
    from app.models import AaExemption

    with _core.session() as db:
        _core._ctx(user, db)
        query = db.query(AaExemption).filter(
            AaExemption.tenant_id == _core._tid(),
            AaExemption.is_deleted.is_(False),
        )
        if student_only:
            student = _student(db, user)
            query = query.filter(AaExemption.student_id == int(student.id))
        if status:
            query = query.filter(AaExemption.status == status)
        rows = query.order_by(AaExemption.id.desc()).all()
        total = len(rows)
        start = (max(1, int(page)) - 1) * int(page_size)
        return [_core._ex_dto(row) for row in rows[start:start + int(page_size)]], total


def merge_deferred(user, defer_id, batch_id):
    """缓考并入后续考试：冻结缓考来源、课程版本、当前修读次数和考试课程名单版本。"""
    from app.models import (
        AaCourse,
        AaDeferredExam,
        AaExamBatch,
        AaExamCourse,
        AaTeachingTask,
        AcademicMakeup,
    )

    with _core.session() as db:
        _core._require_school(_core._ctx(user, db))
        deferred = db.query(AaDeferredExam).filter(
            AaDeferredExam.id == int(defer_id),
            AaDeferredExam.tenant_id == _core._tid(),
            AaDeferredExam.is_deleted.is_(False),
        ).with_for_update().first()
        if not deferred:
            raise not_found("缓考记录不存在")
        if deferred.status != "APPROVED":
            raise _core._invalid("仅APPROVED缓考可并入补考批次")
        batch = _core._get_mb(db, int(batch_id))
        _guard_batch(db, batch)
        if batch.status not in {_core._MB_DRAFT, _core._MB_ARRANGED}:
            raise _core._invalid("仅DRAFT/ARRANGED批次可并入缓考")

        duplicate = db.query(AcademicMakeup).filter(
            AcademicMakeup.tenant_id == _core._tid(),
            AcademicMakeup.source_biz_type == "DEFERRED_EXAM",
            AcademicMakeup.source_biz_id == deferred.id,
            AcademicMakeup.is_deleted.is_(False),
        ).first()
        if duplicate:
            if int(duplicate.batch_id or 0) != int(batch.id):
                raise AppException("DATA_CONFLICT", "该缓考已并入其它后续考试批次", http_status=409)
            return {
                "deferId": str(deferred.id),
                "batchId": str(batch.id),
                "makeupId": str(duplicate.id),
                "merged": True,
                "idempotent": True,
            }

        exam_course = db.query(AaExamCourse).filter(
            AaExamCourse.id == int(deferred.exam_course_id),
            AaExamCourse.tenant_id == _core._tid(),
            AaExamCourse.is_deleted.is_(False),
        ).first()
        if not exam_course or not exam_course.teaching_task_id:
            raise AppException("DATA_CONFLICT", "缓考对应考试课程未关联教学任务", http_status=409)
        exam_batch = db.query(AaExamBatch).filter(
            AaExamBatch.id == int(exam_course.batch_id),
            AaExamBatch.tenant_id == _core._tid(),
            AaExamBatch.is_deleted.is_(False),
        ).first()
        if not exam_batch or int(exam_batch.term_id or 0) != int(batch.term_id or 0):
            raise AppException("DATA_CONFLICT", "缓考原考试与后续考试批次不属于同一学期", http_status=409)
        if batch.exam_batch_ref and int(batch.exam_batch_ref) != int(exam_batch.id):
            raise AppException("DATA_CONFLICT", "补考批次已绑定其它考务批次，不能混入该缓考", http_status=409)
        task = db.query(AaTeachingTask).filter(
            AaTeachingTask.id == int(exam_course.teaching_task_id),
            AaTeachingTask.tenant_id == _core._tid(),
            AaTeachingTask.is_deleted.is_(False),
        ).first()
        if not task:
            raise not_found("缓考对应教学任务不存在")
        course = db.query(AaCourse).filter(
            AaCourse.id == int(task.course_id),
            AaCourse.tenant_id == _core._tid(),
            AaCourse.is_deleted.is_(False),
        ).first()
        if not course or not course.course_code or not course.version:
            raise AppException("DATA_CONFLICT", "缓考对应课程缺少稳定身份", http_status=409)
        exam_roster = get_consumer_snapshot(db, "EXAM_COURSE", int(exam_course.id))
        if not exam_roster:
            raise AppException("DATA_CONFLICT", "缓考原考试课程缺少冻结名单版本，禁止按当前行政班猜测", http_status=409)
        if int(deferred.student_id) not in {int(value) for value in exam_roster.get("studentIds") or []}:
            raise AppException("DATA_CONFLICT", "缓考学生不在原考试课程冻结名单中", http_status=409)
        academic_student = _academic_student_for_profile(db, deferred.student_id)
        if not academic_student:
            raise not_found("缓考学生学业档案不存在")
        attempt_no = next_study_attempt_no(db, academic_student.id, course.course_code)
        row = AcademicMakeup(
            tenant_id=_core._tid(),
            acad_student_id=academic_student.id,
            kind="DEFERRED",
            source_biz_type="DEFERRED_EXAM",
            source_biz_id=deferred.id,
            course_id=course.id,
            course_code=course.course_code,
            course_version=int(course.version),
            attempt_no=attempt_no,
            teaching_task_id=task.id,
            teaching_class_id=int(exam_roster["teachingClassId"]),
            roster_version_id=int(exam_roster["rosterVersionId"]),
            course_name=course.course_name,
            term=batch.term_code,
            batch_id=batch.id,
            status="PENDING_EXAM",
            record_status="ACTIVE",
        )
        db.add(row)
        db.flush()
        deferred.next_batch_ref = str(batch.id)
        if batch.status == _core._MB_DRAFT:
            batch.status = _core._MB_ARRANGED
        _core._audit(
            db,
            "AA_MAKEUP",
            row.id,
            "DEFERRED_MERGE_IDENTITY",
            (
                f"deferId={deferred.id};examCourseId={exam_course.id};courseId={course.id};"
                f"attemptNo={attempt_no};rosterVersionId={exam_roster['rosterVersionId']}"
            ),
        )
        db.commit()
        return {
            "deferId": str(deferred.id),
            "batchId": str(batch.id),
            "makeupId": str(row.id),
            "courseId": str(course.id),
            "attemptNo": attempt_no,
            "rosterVersionId": str(exam_roster["rosterVersionId"]),
            "merged": True,
            "idempotent": False,
        }
