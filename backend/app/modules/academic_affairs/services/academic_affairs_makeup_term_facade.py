"""补考/清考/重修/免修最终学期写保护层。

- 补考/清考批次同时保存termId与termCode；历史仅termCode批次在首次写入时安全回填termId；
- 批次写动作在同一事务内执行学期封存校验；
- 重修/免修申请绑定当前办理学期，审批、编班和材料归档再次校验；
- 补考挂考务批次、重修编入教学任务均要求同一学期。
"""
from __future__ import annotations

import json
from contextvars import ContextVar

from app.core.exceptions import AppException, not_found

from . import academic_affairs_makeup_facade as _base

_legacy = _base._legacy
_BATCH_WRITE = ContextVar("aa_makeup_batch_write", default=False)
_original_get_mb = _legacy._get_mb
_original_clearance_scan = _legacy.clearance_scan


def __getattr__(name):
    return getattr(_base, name)


def _term_code(term) -> str:
    return f"{term.year_code}-{term.term_no}"


def _guard_term_id(db, term_id):
    from app.modules.academic_affairs.services.academic_affairs_archive_service import guard_term_writable

    if not term_id:
        raise AppException("DATA_CONFLICT", "业务记录未绑定正式学期termId", http_status=409)
    guard_term_writable(db, int(term_id))


def _guard_code(db, term_code):
    from app.modules.academic_affairs.services.academic_affairs_archive_service import guard_term_code_writable

    return guard_term_code_writable(db, term_code)


def _current_term(db):
    from app.models import AaTerm

    term = db.query(AaTerm).filter(
        AaTerm.tenant_id == _legacy._tid(),
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


def _get_mb(db, batch_id):
    batch = _original_get_mb(db, int(batch_id))
    if _BATCH_WRITE.get():
        _guard_batch(db, batch)
    return batch


def _batch_write(fn):
    def wrapped(*args, **kwargs):
        token = _BATCH_WRITE.set(True)
        try:
            return fn(*args, **kwargs)
        finally:
            _BATCH_WRITE.reset(token)
    wrapped.__name__ = fn.__name__
    wrapped.__doc__ = fn.__doc__
    wrapped.__module__ = __name__
    return wrapped


def create_makeup_batch(user, body):
    from app.models import AaExamBatch, AaMakeupBatch

    with _legacy.session() as db:
        _legacy._require_school(_legacy._ctx(user, db))
        name = (getattr(body, "batchName", None) or "").strip()
        if not name:
            raise _legacy._bad("批次名称必填")
        term = _selected_term(db, getattr(body, "termCode", None))
        exam_ref = int(body.examBatchRef) if getattr(body, "examBatchRef", None) else None
        if exam_ref:
            exam = db.query(AaExamBatch).filter(
                AaExamBatch.id == exam_ref,
                AaExamBatch.tenant_id == _legacy._tid(),
                AaExamBatch.is_deleted.is_(False),
            ).first()
            if not exam:
                raise not_found("考务批次不存在")
            if int(exam.term_id or 0) != int(term.id):
                raise AppException("DATA_CONFLICT", "补考批次与考务批次不属于同一学期", http_status=409)
        batch = AaMakeupBatch(
            tenant_id=_legacy._tid(),
            batch_name=name,
            term_id=term.id,
            term_code=_term_code(term),
            exam_batch_ref=exam_ref,
            score_rule=_legacy._rule("makeup_score_rule", "CAP60"),
            status=_legacy._MB_DRAFT,
        )
        db.add(batch)
        db.flush()
        _legacy._audit(db, "AA_MAKEUP", batch.id, "MAKEUP_BATCH_CREATE", name)
        db.commit()
        return _legacy._mb_dto(batch)


def create_clearance_batch(user, body):
    from app.models import AaMakeupBatch

    with _legacy.session() as db:
        _legacy._require_school(_legacy._ctx(user, db))
        name = (getattr(body, "batchName", None) or "").strip()
        if not name:
            raise _legacy._bad("批次名称必填")
        grades = [
            str(value).strip() for value in (getattr(body, "targetGrades", None) or [])
            if str(value).strip()
        ]
        if not grades:
            raise _legacy._bad("清考必须限定毕业年级（如 2022）")
        term = _selected_term(db, getattr(body, "termCode", None))
        batch = AaMakeupBatch(
            tenant_id=_legacy._tid(),
            batch_name=name,
            kind="CLEARANCE",
            target_grades=",".join(grades),
            term_id=term.id,
            term_code=_term_code(term),
            score_rule="CAP60",
            status=_legacy._MB_DRAFT,
        )
        db.add(batch)
        db.flush()
        _legacy._audit(db, "AA_MAKEUP", batch.id, "CLEARANCE_BATCH_CREATE", f"{name} 年级{grades}")
        db.commit()
        return _legacy._mb_dto(batch)


def link_exam_batch(user, batch_id, exam_batch_id):
    from app.models import AaExamBatch

    with _legacy.session() as db:
        _legacy._require_school(_legacy._ctx(user, db))
        batch = _original_get_mb(db, int(batch_id))
        term = _guard_batch(db, batch)
        if batch.status not in (_legacy._MB_DRAFT, _legacy._MB_ARRANGED):
            raise _legacy._invalid("仅 DRAFT/ARRANGED 补考批次可挂考务编排")
        exam = db.query(AaExamBatch).filter(
            AaExamBatch.id == int(exam_batch_id),
            AaExamBatch.tenant_id == _legacy._tid(),
            AaExamBatch.is_deleted.is_(False),
        ).first()
        if not exam:
            raise not_found("考务批次不存在")
        if int(exam.term_id or 0) != int((term.id if term else batch.term_id) or 0):
            raise AppException("DATA_CONFLICT", "补考批次与考务批次不属于同一学期", http_status=409)
        batch.exam_batch_ref = exam.id
        if batch.status == _legacy._MB_DRAFT:
            batch.status = _legacy._MB_ARRANGED
        _legacy._audit(db, "AA_MAKEUP", batch.id, "MAKEUP_LINK_EXAM", f"挂考务批次 {exam.batch_name}")
        db.commit()
        return _legacy._mb_dto(batch)


def retake_apply(user, body):
    """gradeId只确定挂科课程；申请学期始终是当前办理学期。"""
    from app.models import AaRetakeApply, AcademicGrade, AcademicStudent

    with _legacy.session() as db:
        student = _legacy._student(db)
        current = _current_term(db)
        requested = str(getattr(body, "termCode", None) or "").strip()
        code = _term_code(current)
        if requested and requested != code:
            raise AppException("VALIDATION_ERROR", "重修报名只能绑定当前办理学期")
        course_name = (getattr(body, "courseName", None) or "").strip()
        course_id = None
        academic_student = db.query(AcademicStudent).filter(
            AcademicStudent.tenant_id == _legacy._tid(),
            AcademicStudent.student_id == student.id,
            AcademicStudent.is_deleted.is_(False),
        ).first()
        grade_id = getattr(body, "gradeId", None)
        if grade_id:
            grade = db.get(AcademicGrade, int(grade_id))
            if (
                not grade or grade.is_deleted or grade.tenant_id != _legacy._tid()
                or not academic_student or grade.acad_student_id != academic_student.id
                or str(grade.pass_status or "").upper() not in {"FAIL", "FAILED"}
            ):
                raise _legacy._bad("请从挂科课程列表选择有效成绩后再报名重修")
            course_name = (grade.course_name or "").strip()
            course_id = getattr(grade, "course_id", None)
        if not course_name:
            raise _legacy._bad("请从挂科课程列表选择课程（课程名必填）")
        history = db.query(AaRetakeApply).filter(
            AaRetakeApply.tenant_id == _legacy._tid(),
            AaRetakeApply.student_id == student.id,
            AaRetakeApply.course_name == course_name,
            AaRetakeApply.status.notin_([_legacy._RT_REJECTED]),
            AaRetakeApply.is_deleted.is_(False),
        ).all()
        if any(row.status in (_legacy._RT_SUBMITTED, _legacy._RT_REVIEW) for row in history):
            raise _legacy._conflict("该课程已有在途重修申请")
        maximum = int(_legacy._rule("retake_max_count", 2))
        if len(history) >= maximum:
            raise _legacy._bad(f"该课程重修次数已达上限 {maximum} 次")
        row = AaRetakeApply(
            tenant_id=_legacy._tid(),
            student_id=student.id,
            student_no=student.student_no,
            student_name=student.real_name,
            acad_student_id=academic_student.id if academic_student else None,
            course_id=course_id,
            course_name=course_name,
            term_code=code,
            reason=getattr(body, "reason", None),
            retake_count=len(history) + 1,
            status=_legacy._RT_SUBMITTED,
        )
        db.add(row)
        db.flush()
        _legacy._audit(db, "AA_RETAKE", row.id, "RETAKE_APPLY", f"重修报名 {course_name}")
        db.commit()
        return _legacy._rt_dto(row)


def retake_review(user, apply_id, action, reason=""):
    from app.models import AaRetakeApply

    with _legacy.session() as db:
        _legacy._require_school(_legacy._ctx(user, db))
        row = db.query(AaRetakeApply).filter(
            AaRetakeApply.id == int(apply_id),
            AaRetakeApply.tenant_id == _legacy._tid(),
            AaRetakeApply.is_deleted.is_(False),
        ).first()
        if not row:
            raise not_found("重修申请不存在")
        _guard_code(db, row.term_code)
        if row.status not in (_legacy._RT_SUBMITTED, _legacy._RT_REVIEW):
            raise AppException("APPROVAL_VERSION_CONFLICT", "该申请已处理", http_status=409)
        action = str(action or "").upper()
        if action == "APPROVE":
            row.status = _legacy._RT_APPROVED
        elif action == "REJECT":
            reason = (reason or "").strip()
            if len(reason) < 5:
                raise _legacy._bad("驳回原因必填且不少于5字")
            row.status = _legacy._RT_REJECTED
            row.review_reason = reason
        else:
            raise _legacy._bad("非法审批动作")
        _legacy._audit(db, "AA_RETAKE", row.id, "RETAKE_REVIEW", action)
        db.commit()
        return _legacy._rt_dto(row)


def retake_enroll(user, apply_id, teaching_task_ref=None):
    from app.models import AaRetakeApply, AaTeachingTask, AaTeachingTaskBatch

    with _legacy.session() as db:
        _legacy._require_school(_legacy._ctx(user, db))
        row = db.query(AaRetakeApply).filter(
            AaRetakeApply.id == int(apply_id),
            AaRetakeApply.tenant_id == _legacy._tid(),
            AaRetakeApply.is_deleted.is_(False),
        ).first()
        if not row:
            raise not_found("重修申请不存在")
        term = _guard_code(db, row.term_code)
        if row.status != _legacy._RT_APPROVED:
            raise _legacy._invalid("仅 APPROVED 申请可编入跟班")
        task_id = int(teaching_task_ref) if teaching_task_ref else None
        if task_id:
            task = db.query(AaTeachingTask).filter(
                AaTeachingTask.id == task_id,
                AaTeachingTask.tenant_id == _legacy._tid(),
                AaTeachingTask.is_deleted.is_(False),
            ).first()
            if not task:
                raise not_found("教学任务不存在")
            task_batch = db.query(AaTeachingTaskBatch).filter(
                AaTeachingTaskBatch.id == task.batch_id,
                AaTeachingTaskBatch.tenant_id == _legacy._tid(),
                AaTeachingTaskBatch.is_deleted.is_(False),
            ).first()
            if not task_batch or int(task_batch.term_id) != int(term.id):
                raise AppException("DATA_CONFLICT", "重修申请与跟班教学任务不属于同一学期", http_status=409)
        row.status = _legacy._RT_ENROLLED
        row.teaching_task_ref = task_id
        _legacy._audit(db, "AA_RETAKE", row.id, "RETAKE_ENROLL", "编入跟班")
        db.commit()
        return _legacy._rt_dto(row)


def exemption_apply(user, body):
    from app.models import AaExemption, AcademicGrade, AcademicStudent, FileObject

    with _legacy.session() as db:
        student = _legacy._student(db)
        current = _current_term(db)
        requested = str(getattr(body, "termCode", None) or "").strip()
        code = _term_code(current)
        if requested and requested != code:
            raise AppException("VALIDATION_ERROR", "免修申请只能绑定当前办理学期")
        course_name = (getattr(body, "courseName", None) or "").strip()
        if not course_name:
            raise _legacy._bad("课程名必填")
        academic_student = db.query(AcademicStudent).filter(
            AcademicStudent.tenant_id == _legacy._tid(),
            AcademicStudent.student_id == student.id,
            AcademicStudent.is_deleted.is_(False),
        ).first()
        if academic_student:
            passed = db.query(AcademicGrade).filter(
                AcademicGrade.tenant_id == _legacy._tid(),
                AcademicGrade.acad_student_id == academic_student.id,
                AcademicGrade.course_name == course_name,
                AcademicGrade.pass_status == "PASSED",
                AcademicGrade.is_deleted.is_(False),
            ).first()
            if passed:
                raise _legacy._bad("该课程已获及格成绩，不可申请免修")
        maximum = int(_legacy._rule("exemption_max_count", 2))
        used = db.query(AaExemption).filter(
            AaExemption.tenant_id == _legacy._tid(),
            AaExemption.student_id == student.id,
            AaExemption.term_code == code,
            AaExemption.status.notin_([_legacy._EX_REJECTED, _legacy._EX_CANCELLED]),
            AaExemption.is_deleted.is_(False),
        ).count()
        if used >= maximum:
            raise _legacy._bad(f"本学期免修申请已达上限 {maximum} 门")
        raw_materials = getattr(body, "materialFileIds", None)
        material_ids = None
        if raw_materials:
            values = raw_materials if isinstance(raw_materials, list) else [raw_materials]
            ids = [int(value) for value in values if str(value).isdigit()]
            if len(ids) != len(values):
                raise _legacy._bad("免修材料附件包含无效文件，请重新上传")
            found = db.query(FileObject).filter(
                FileObject.tenant_id == _legacy._tid(), FileObject.id.in_(ids),
            ).count() if ids else 0
            if found != len(ids):
                raise _legacy._bad("免修材料附件包含无效文件，请重新上传")
            material_ids = json.dumps([str(value) for value in ids], ensure_ascii=False)
        row = AaExemption(
            tenant_id=_legacy._tid(),
            student_id=student.id,
            student_no=student.student_no,
            student_name=student.real_name,
            course_name=course_name,
            term_code=code,
            college_id=getattr(student, "college_id", None),
            reason=getattr(body, "reason", None),
            material_file_ids=material_ids,
            current_node=_legacy._EX_TEACHER,
            status=_legacy._EX_TEACHER,
        )
        db.add(row)
        db.flush()
        _legacy._audit(db, "AA_EXEMPTION", row.id, "EXEMPTION_APPLY", f"免修申请 {course_name}")
        db.commit()
        return _legacy._ex_dto(row)


def exemption_review(user, exemption_id, action, reason=""):
    from app.models import AaExemption

    with _legacy.session() as db:
        _legacy._ctx(user, db)
        row = db.query(AaExemption).filter(
            AaExemption.id == int(exemption_id),
            AaExemption.tenant_id == _legacy._tid(),
            AaExemption.is_deleted.is_(False),
        ).first()
        if not row:
            raise not_found("免修申请不存在")
        _guard_code(db, row.term_code)
        if row.status not in _legacy._EX_CHAIN:
            raise AppException("APPROVAL_VERSION_CONFLICT", "该申请已处理", http_status=409)
        action = str(action or "").upper()
        if action == "APPROVE":
            next_status = _legacy._EX_CHAIN[row.status]
            row.status = next_status
            row.current_node = None if next_status == _legacy._EX_APPROVED else next_status
        elif action in {"RETURN", "REJECT"}:
            reason = (reason or "").strip()
            if len(reason) < 5:
                raise _legacy._bad("退回/驳回原因必填且不少于5字")
            row.status = _legacy._EX_SUBMITTED if action == "RETURN" else _legacy._EX_REJECTED
            row.current_node = _legacy._EX_SUBMITTED if action == "RETURN" else None
            row.return_reason = reason
        else:
            raise _legacy._bad("非法审批动作")
        _legacy._audit(db, "AA_EXEMPTION", row.id, "EXEMPTION_REVIEW", f"{action}->{row.status}")
        db.commit()
        return _legacy._ex_dto(row)


def mark_archived(user, exemption_id):
    from app.core.affairs_security import no_data_scope
    from app.models import AaExemption

    with _legacy.session() as db:
        ctx = _legacy._ctx(user, db)
        row = db.query(AaExemption).filter(
            AaExemption.id == int(exemption_id),
            AaExemption.tenant_id == _legacy._tid(),
            AaExemption.is_deleted.is_(False),
        ).first()
        if not row:
            raise not_found("免修申请不存在")
        _guard_code(db, row.term_code)
        if ctx.scope_type == "COLLEGE" and row.college_id and int(row.college_id) not in ctx.college_ids:
            raise no_data_scope("该学生不在您的数据范围内")
        if row.status not in (_legacy._EX_APPROVED, _legacy._EX_REJECTED, _legacy._EX_CANCELLED):
            raise _legacy._invalid("仅审批已终态的免修申请可标记归档")
        if row.archive_status == "ARCHIVED":
            return {"exemptionId": str(row.id), "archiveStatus": row.archive_status}
        row.archive_status = "ARCHIVED"
        _legacy._audit(db, "AA_EXEMPTION", row.id, "EXEMPTION_ARCHIVE", "标记材料已归档")
        db.commit()
        return {"exemptionId": str(row.id), "archiveStatus": row.archive_status}


_legacy._get_mb = _get_mb
for _name in (
    "enroll_makeup",
    "publish_makeup_batch",
    "enter_makeup_score",
    "college_review_scores",
    "finish_makeup_batch",
    "merge_deferred",
):
    _wrapped = _batch_write(getattr(_legacy, _name))
    globals()[_name] = _wrapped
    setattr(_legacy, _name, _wrapped)


def clearance_scan(user, batch_id, dry_run=False):
    if dry_run:
        return _original_clearance_scan(user, batch_id, dry_run=True)
    token = _BATCH_WRITE.set(True)
    try:
        return _original_clearance_scan(user, batch_id, dry_run=False)
    finally:
        _BATCH_WRITE.reset(token)


_legacy.clearance_scan = clearance_scan
_legacy.create_makeup_batch = create_makeup_batch
_legacy.create_clearance_batch = create_clearance_batch
_legacy.link_exam_batch = link_exam_batch
_legacy.retake_apply = retake_apply
_legacy.retake_review = retake_review
_legacy.retake_enroll = retake_enroll
_legacy.exemption_apply = exemption_apply
_legacy.exemption_review = exemption_review
_legacy.mark_archived = mark_archived
