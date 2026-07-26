"""补考/清考/重修/免修最终学期写保护层。

- 批次型写动作通过上下文标记，使原 ``_get_mb`` 在同一事务内校验批次termCode；
- 新建补考/清考批次必须绑定正式未归档学期；
- 重修/免修申请绑定当前办理学期，不再误用原挂科学期；
- 审批和编班按申请记录termCode再次校验，禁止学期封存后继续流转。
"""
from __future__ import annotations

from contextvars import ContextVar

from app.core.exceptions import AppException, not_found

from . import academic_affairs_makeup_facade as _base

_legacy = _base._legacy
_BATCH_WRITE = ContextVar("aa_makeup_batch_write", default=False)
_original_get_mb = _legacy._get_mb


def __getattr__(name):
    return getattr(_base, name)


def _term_code(term) -> str:
    return f"{term.year_code}-{term.term_no}"


def _current_term(db):
    from app.models import AaTerm

    term = db.query(AaTerm).filter(
        AaTerm.tenant_id == _legacy._tid(),
        AaTerm.is_current.is_(True),
        AaTerm.is_deleted.is_(False),
    ).first()
    if not term:
        raise AppException("DATA_CONFLICT", "学校尚未设置当前办理学期", http_status=409)
    return term


def _guard_code(db, term_code):
    from app.modules.academic_affairs.services.academic_affairs_archive_service import (
        guard_term_code_writable,
    )

    return guard_term_code_writable(db, term_code)


def _get_mb(db, batch_id):
    batch = _original_get_mb(db, batch_id)
    if _BATCH_WRITE.get():
        _guard_code(db, batch.term_code)
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
    from app.models import AaMakeupBatch

    with _legacy.session() as db:
        _legacy._require_school(_legacy._ctx(user, db))
        name = (getattr(body, "batchName", None) or "").strip()
        if not name:
            raise _legacy._bad("批次名称必填")
        code = str(getattr(body, "termCode", None) or "").strip()
        _guard_code(db, code)
        batch = AaMakeupBatch(
            tenant_id=_legacy._tid(),
            batch_name=name,
            term_code=code,
            exam_batch_ref=(
                int(body.examBatchRef) if getattr(body, "examBatchRef", None) else None
            ),
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
            str(value).strip()
            for value in (getattr(body, "targetGrades", None) or [])
            if str(value).strip()
        ]
        if not grades:
            raise _legacy._bad("清考必须限定毕业年级（如 2022）")
        code = str(getattr(body, "termCode", None) or "").strip()
        _guard_code(db, code)
        batch = AaMakeupBatch(
            tenant_id=_legacy._tid(),
            batch_name=name,
            kind="CLEARANCE",
            target_grades=",".join(grades),
            term_code=code,
            score_rule="CAP60",
            status=_legacy._MB_DRAFT,
        )
        db.add(batch)
        db.flush()
        _legacy._audit(
            db,
            "AA_MAKEUP",
            batch.id,
            "CLEARANCE_BATCH_CREATE",
            f"{name} 年级{grades}",
        )
        db.commit()
        return _legacy._mb_dto(batch)


def retake_apply(user, body):
    """申请绑定当前办理学期；gradeId只确定挂科课程，不决定重修学期。"""
    from app.models import AaRetakeApply, AcademicGrade, AcademicStudent

    with _legacy.session() as db:
        student = _legacy._student(db)
        if not student:
            raise not_found("学生档案不存在")
        current = _current_term(db)
        requested_code = str(getattr(body, "termCode", None) or "").strip()
        code = requested_code or _term_code(current)
        if code != _term_code(current):
            raise AppException("VALIDATION_ERROR", "重修报名只能绑定当前办理学期")
        _guard_code(db, code)

        course_name = (getattr(body, "courseName", None) or "").strip()
        grade_id = getattr(body, "gradeId", None)
        if grade_id:
            grade = db.get(AcademicGrade, int(grade_id))
            academic_student = db.query(AcademicStudent).filter(
                AcademicStudent.tenant_id == _legacy._tid(),
                AcademicStudent.student_id == student.id,
                AcademicStudent.is_deleted.is_(False),
            ).first()
            if (
                not grade or grade.is_deleted or grade.tenant_id != _legacy._tid()
                or not academic_student or grade.acad_student_id != academic_student.id
                or (grade.pass_status or "").upper() not in ("FAIL", "FAILED")
            ):
                raise _legacy._bad("请从挂科课程列表选择有效成绩后再报名重修")
            course_name = (grade.course_name or "").strip()
        if not course_name:
            raise _legacy._bad("请从挂科课程列表选择课程（课程名必填）")

        maximum = int(_legacy._rule("retake_max_count", 2))
        history = db.query(AaRetakeApply).filter(
            AaRetakeApply.tenant_id == _legacy._tid(),
            AaRetakeApply.student_id == student.id,
            AaRetakeApply.course_name == course_name,
            AaRetakeApply.status.notin_([_legacy._RT_REJECTED]),
            AaRetakeApply.is_deleted.is_(False),
        ).all()
        active = [
            row for row in history
            if row.status in (_legacy._RT_SUBMITTED, _legacy._RT_REVIEW)
        ]
        if active:
            raise _legacy._conflict("该课程已有在途重修申请")
        if len(history) >= maximum:
            raise _legacy._bad(f"该课程重修次数已达上限 {maximum} 次")
        row = AaRetakeApply(
            tenant_id=_legacy._tid(),
            student_id=student.id,
            student_no=student.student_no,
            student_name=student.real_name,
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
        if row.status != _legacy._RT_APPROVED:
            raise _legacy._invalid("仅 APPROVED 申请可编入跟班")
        row.status = _legacy._RT_ENROLLED
        row.teaching_task_ref = int(teaching_task_ref) if teaching_task_ref else None
        _legacy._audit(db, "AA_RETAKE", row.id, "RETAKE_ENROLL", "编入跟班")
        db.commit()
        return _legacy._rt_dto(row)


def exemption_apply(user, body):
    from app.models import AaExemptionApply, AcademicStudent

    with _legacy.session() as db:
        student = _legacy._student(db)
        if not student:
            raise not_found("学生档案不存在")
        current = _current_term(db)
        requested_code = str(getattr(body, "termCode", None) or "").strip()
        code = requested_code or _term_code(current)
        if code != _term_code(current):
            raise AppException("VALIDATION_ERROR", "免修申请只能绑定当前办理学期")
        _guard_code(db, code)
        course_name = (getattr(body, "courseName", None) or "").strip()
        if not course_name:
            raise _legacy._bad("课程名必填")
        maximum = int(_legacy._rule("exemption_max_count", 2))
        used = db.query(AaExemptionApply).filter(
            AaExemptionApply.tenant_id == _legacy._tid(),
            AaExemptionApply.student_id == student.id,
            AaExemptionApply.term_code == code,
            AaExemptionApply.status.notin_([_legacy._EX_REJECTED, _legacy._EX_CANCELLED]),
            AaExemptionApply.is_deleted.is_(False),
        ).count()
        if used >= maximum:
            raise _legacy._bad(f"本学期免修申请已达上限 {maximum} 门")
        academic_student = db.query(AcademicStudent).filter(
            AcademicStudent.tenant_id == _legacy._tid(),
            AcademicStudent.student_id == student.id,
            AcademicStudent.is_deleted.is_(False),
        ).first()
        row = AaExemptionApply(
            tenant_id=_legacy._tid(),
            student_id=student.id,
            student_no=student.student_no,
            student_name=student.real_name,
            acad_student_id=academic_student.id if academic_student else None,
            course_name=course_name,
            term_code=code,
            reason=getattr(body, "reason", None),
            material_file_ids=getattr(body, "materialFileIds", None),
            current_node=_legacy._EX_TEACHER,
            status=_legacy._EX_SUBMITTED,
        )
        db.add(row)
        db.flush()
        _legacy._audit(db, "AA_EXEMPTION", row.id, "EXEMPTION_APPLY", course_name)
        db.commit()
        return _legacy._ex_dto(row)


def exemption_review(user, exemption_id, action, reason=""):
    from app.models import AaExemptionApply

    with _legacy.session() as db:
        row = db.query(AaExemptionApply).filter(
            AaExemptionApply.id == int(exemption_id),
            AaExemptionApply.tenant_id == _legacy._tid(),
            AaExemptionApply.is_deleted.is_(False),
        ).first()
        if not row:
            raise not_found("免修申请不存在")
        _guard_code(db, row.term_code)
        _legacy._require_exemption_node_scope(user, row.current_node, db)
        if row.status in (_legacy._EX_APPROVED, _legacy._EX_REJECTED, _legacy._EX_CANCELLED):
            raise AppException("APPROVAL_VERSION_CONFLICT", "申请已终结", http_status=409)
        action = str(action or "").upper()
        if action in ("REJECT", "RETURN"):
            reason = (reason or "").strip()
            if len(reason) < 5:
                raise _legacy._bad("退回/驳回原因必填且不少于5字")
            if action == "REJECT":
                row.status = _legacy._EX_REJECTED
                row.current_node = None
            else:
                row.status = _legacy._EX_SUBMITTED
                row.current_node = _legacy._EX_TEACHER
                row.return_reason = reason
            _legacy._audit(db, "AA_EXEMPTION", row.id, f"EXEMPTION_{action}", reason)
        elif action == "APPROVE":
            next_node = _legacy._EX_CHAIN.get(row.current_node)
            if next_node == _legacy._EX_APPROVED:
                row.status = _legacy._EX_APPROVED
                row.current_node = None
            else:
                row.current_node = next_node
                row.status = next_node
            _legacy._audit(db, "AA_EXEMPTION", row.id, "EXEMPTION_APPROVE", str(next_node))
        else:
            raise _legacy._bad("非法审批动作")
        db.commit()
        return _legacy._ex_dto(row)


# 批次型写动作均会经_get_mb，使用上下文标记在原事务内执行termCode校验。
_legacy._get_mb = _get_mb
for _name in (
    "link_exam_batch",
    "enroll_makeup",
    "publish_makeup_batch",
    "enter_makeup_score",
    "college_review_scores",
    "finish_makeup_batch",
    "merge_deferred_into_batch",
):
    _wrapped = _batch_write(getattr(_legacy, _name))
    globals()[_name] = _wrapped
    setattr(_legacy, _name, _wrapped)


def clearance_scan(user, batch_id, dry_run=False):
    if dry_run:
        return _legacy._clearance_scan_original(user, batch_id, dry_run=True)
    token = _BATCH_WRITE.set(True)
    try:
        return _legacy._clearance_scan_original(user, batch_id, dry_run=False)
    finally:
        _BATCH_WRITE.reset(token)


if not hasattr(_legacy, "_clearance_scan_original"):
    _legacy._clearance_scan_original = _legacy.clearance_scan
_legacy.clearance_scan = clearance_scan
_legacy.create_makeup_batch = create_makeup_batch
_legacy.create_clearance_batch = create_clearance_batch
_legacy.retake_apply = retake_apply
_legacy.retake_review = retake_review
_legacy.retake_enroll = retake_enroll
_legacy.exemption_apply = exemption_apply
_legacy.exemption_review = exemption_review
