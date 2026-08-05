"""包 6：正式业务文件对象绑定门面与岗位实习兼容接管。

通用上传只能产生 TEMP_PRIVATE。业务命令完成对象范围校验并写入业务对象后，
本模块在同一个 SQLAlchemy 事务中把安全可用的临时/历史文件绑定到权威对象。
绑定失败会使业务事务整体回滚；本模块从不自行 commit。
"""
from __future__ import annotations

from typing import Any

from sqlalchemy import event, select
from sqlalchemy.orm import Session as OrmSession

from app.core.context import get_current_user_ctx
from app.core.exceptions import AppException, no_permission, not_found
from app.services.db_service import _tid

_READY_FILE_STATUS = {"AVAILABLE", "STORED"}
_READY_SCAN_STATUS = {"CLEAN", "NOT_REQUIRED"}
_PENDING_KEY = "file_business_bindings_pending"
_PROCESSING_KEY = "file_business_bindings_processing"
_INSTALLED = False


def _text(value: Any) -> str:
    return str(value or "").strip()


def _actor_student_values(actor: dict) -> set[str]:
    values = {
        _text(actor.get("studentId")),
        _text(actor.get("studentNo")),
    }
    return {value for value in values if value}


def _file_ready(file_obj) -> bool:
    return bool(
        str(file_obj.status or "").upper() in _READY_FILE_STATUS
        and str(file_obj.scan_status or "NOT_REQUIRED").upper() in _READY_SCAN_STATUS
    )


def _temporary_private(file_obj) -> bool:
    return bool(
        str(file_obj.biz_type or "").upper() == "TEMP_PRIVATE"
        and not _text(file_obj.biz_id)
        and str(file_obj.visibility or "PRIVATE").upper() == "PRIVATE"
    )


def _require_actor_scope(db, record, student, actor: dict) -> None:
    user_type = str(actor.get("userType") or "").upper()
    if user_type == "STUDENT":
        allowed = _actor_student_values(actor)
        actual = {_text(student.id), _text(student.student_no)}
        if not allowed.intersection(actual):
            raise no_permission("只能绑定本人的实习材料")
        return
    from app.modules.internship.services.internship_scope import assert_internship_record_scope

    assert_internship_record_scope(db, record.id, actor, "绑定实习业务文件")


def _legacy_target_values(record, student, target_id: str) -> set[str]:
    return {
        _text(target_id),
        _text(record.id),
        _text(record.student_id),
        _text(student.id),
        _text(student.student_no),
    }


def bind_file_to_business(
    db,
    *,
    file_id,
    biz_type: str,
    biz_id,
    actor: dict,
    subject_type: str,
    subject_id,
    relation_type: str = "BUSINESS_EVIDENCE",
    module_code: str | None = None,
    student_id: int | None = None,
    batch_id: str | None = None,
    college_id: int | None = None,
    class_id: int | None = None,
    scope: dict | None = None,
    legacy_target_values: set[str] | None = None,
):
    """在调用方事务中建立 ACTIVE binding；禁止任意重定向与未扫描文件。"""
    from app.models.file import FileBinding, FileObject
    from app.services import file_access_resolvers as resolvers

    fid = _text(file_id)
    target_type = _text(biz_type).upper()
    target_id = _text(biz_id)
    target_subject = _text(subject_type).upper()
    target_subject_id = _text(subject_id)
    if not fid.isdigit() or not target_type or not target_id or not target_subject_id:
        raise AppException("VALIDATION_ERROR", "文件绑定参数不完整")

    file_obj = db.scalar(select(FileObject).where(
        FileObject.id == int(fid),
        FileObject.tenant_id == _tid(),
        FileObject.is_deleted.is_(False),
    ).with_for_update())
    if not file_obj:
        raise not_found("文件不存在或不在当前数据范围内")
    if not _file_ready(file_obj):
        raise AppException(
            "FILE_NOT_READY",
            "文件仍在安全扫描、扫描失败或不可用，禁止绑定正式业务",
            details={"fileId": fid, "status": file_obj.status, "scanStatus": file_obj.scan_status},
        )

    active = list(db.scalars(select(FileBinding).where(
        FileBinding.tenant_id == _tid(),
        FileBinding.file_id == int(fid),
        FileBinding.status == "ACTIVE",
        FileBinding.is_current.is_(True),
        FileBinding.is_deleted.is_(False),
    ).with_for_update()).all())
    exact = next((row for row in active if (
        str(row.biz_type or "").upper() == target_type
        and _text(row.biz_id) == target_id
        and str(row.relation_type or "").upper() == relation_type.upper()
    )), None)
    if exact:
        return exact
    if active:
        raise AppException("FILE_ALREADY_BOUND", "文件已绑定其他正式业务对象，禁止重新指向")

    if _temporary_private(file_obj):
        if not resolvers._owner_allows(file_obj, actor or {}):
            raise no_permission("只能绑定本人上传的临时文件")
    else:
        # 历史文件接管只接受其旧 bizId 与权威对象/学生/实习记录一致，不能任意改绑。
        declared = _text(file_obj.biz_id)
        allowed = {value for value in (legacy_target_values or set()) if value}
        declared_type = str(file_obj.biz_type or "").upper()
        compatible_type = (
            declared_type == target_type
            or declared_type in {"INTERNSHIP", "ENT_EVAL", "LEAVE", "ATTACHMENT"}
            or (declared_type.startswith("INTERNSHIP_") and target_type.startswith("INTERNSHIP_"))
        )
        if (
            str(file_obj.visibility or "").upper() != "BIZ_SCOPED"
            or not compatible_type
            or not declared
            or declared not in allowed
        ):
            raise no_permission("历史文件声明与当前权威业务对象不一致，禁止接管")

    binding = FileBinding(
        tenant_id=_tid(),
        file_id=int(fid),
        biz_type=target_type,
        biz_id=target_id,
        relation_type=relation_type.upper(),
        subject_type=target_subject,
        subject_id=target_subject_id,
        batch_id=_text(batch_id) or None,
        version_no=1,
        is_current=True,
        status="ACTIVE",
        module_code=_text(module_code).upper() or None,
        student_id=student_id,
        college_id=college_id,
        class_id=class_id,
        scope_json=dict(scope or {}),
        data_scope_snapshot_json=dict(scope or {}),
    )
    db.add(binding)
    file_obj.biz_type = target_type
    file_obj.biz_id = target_id
    file_obj.visibility = "BIZ_SCOPED"
    file_obj.storage_zone = "ACTIVE"
    return binding


def _spec_for(obj):
    """返回 (file_field, biz_type, record_field)；只覆盖已确认的岗位实习正式证据。"""
    from app.models import (
        AttendanceException,
        InternshipAgreement,
        InternshipApplication,
        InternshipEnterpriseEval,
        InternshipGuidance,
        InternshipInsurance,
        InternshipLeave,
        InternshipPlanTaskProgress,
        InternshipSafetyCompletion,
        InternshipStudentEval,
        InternshipVisit,
    )

    specs = (
        (InternshipAgreement, "file_id", "INTERNSHIP_AGREEMENT", "internship_id"),
        (InternshipApplication, "evidence_file_id", "INTERNSHIP_APPLICATION", "record_id"),
        (InternshipInsurance, "file_id", "INTERNSHIP_INSURANCE", "internship_id"),
        (InternshipEnterpriseEval, "file_id", "INTERNSHIP_ENTERPRISE_EVAL", "internship_id"),
        (InternshipStudentEval, "file_id", "INTERNSHIP_STUDENT_EVAL", "internship_id"),
        (InternshipGuidance, "file_id", "INTERNSHIP_GUIDANCE", "internship_id"),
        (InternshipVisit, "file_id", "INTERNSHIP_VISIT", "internship_id"),
        (InternshipLeave, "file_id", "INTERNSHIP_LEAVE", "internship_id"),
        (AttendanceException, "appeal_file_id", "INTERNSHIP_ATTENDANCE_APPEAL", "internship_id"),
        (InternshipPlanTaskProgress, "evidence_file_id", "INTERNSHIP_PLAN_TASK", "internship_id"),
        (InternshipSafetyCompletion, "evidence_file_id", "INTERNSHIP_SAFETY", "internship_id"),
    )
    for model, file_field, biz_type, record_field in specs:
        if isinstance(obj, model):
            return file_field, biz_type, record_field
    return None


def _before_flush(db, flush_context, instances) -> None:
    if db.info.get(_PROCESSING_KEY):
        return
    pending = []
    for obj in list(db.new) + list(db.dirty):
        spec = _spec_for(obj)
        if not spec:
            continue
        file_field, biz_type, record_field = spec
        if _text(getattr(obj, file_field, None)):
            pending.append((obj, file_field, biz_type, record_field))
    if pending:
        db.info[_PENDING_KEY] = pending


def _after_flush_postexec(db, flush_context) -> None:
    pending = db.info.pop(_PENDING_KEY, [])
    if not pending or db.info.get(_PROCESSING_KEY):
        return
    actor = get_current_user_ctx() or {}
    if not actor:
        raise AppException("FILE_BINDING_ACTOR_REQUIRED", "正式业务文件绑定缺少操作人上下文")

    from app.models import InternshipRecord, StudentProfile

    db.info[_PROCESSING_KEY] = True
    try:
        for obj, file_field, biz_type, record_field in pending:
            file_id = _text(getattr(obj, file_field, None))
            target_id = _text(getattr(obj, "id", None))
            record_id = _text(getattr(obj, record_field, None))
            if not file_id or not target_id or not record_id.isdigit():
                raise AppException("FILE_BINDING_TARGET_REQUIRED", "正式业务文件缺少已落库的权威目标")
            record = db.scalar(select(InternshipRecord).where(
                InternshipRecord.id == int(record_id),
                InternshipRecord.tenant_id == _tid(),
                InternshipRecord.is_deleted.is_(False),
            ).with_for_update())
            if not record:
                raise not_found("实习记录不存在或不在当前数据范围内")
            student = db.scalar(select(StudentProfile).where(
                StudentProfile.id == record.student_id,
                StudentProfile.tenant_id == _tid(),
                StudentProfile.is_deleted.is_(False),
            ))
            if not student:
                raise not_found("学生档案不存在或不在当前数据范围内")
            _require_actor_scope(db, record, student, actor)
            scope = {
                "internshipId": str(record.id),
                "studentId": str(student.id),
                "studentNo": str(student.student_no or ""),
                "batchId": str(record.batch_id or ""),
                "advisorUserId": str(record.advisor_user_id or ""),
                "businessType": biz_type,
                "businessId": target_id,
            }
            bind_file_to_business(
                db,
                file_id=file_id,
                biz_type=biz_type,
                biz_id=target_id,
                actor=actor,
                subject_type="STUDENT",
                subject_id=str(student.id),
                relation_type="BUSINESS_EVIDENCE",
                module_code="INTERNSHIP",
                student_id=student.id,
                batch_id=str(record.batch_id or "") or None,
                college_id=getattr(student, "college_id", None),
                class_id=getattr(student, "class_id", None),
                scope=scope,
                legacy_target_values=_legacy_target_values(record, student, target_id),
            )
    finally:
        db.info.pop(_PROCESSING_KEY, None)


def install_internship_binding_hooks() -> None:
    """幂等安装；绑定仍发生在原业务 session/commit 内。"""
    global _INSTALLED
    if _INSTALLED:
        return
    event.listen(OrmSession, "before_flush", _before_flush)
    event.listen(OrmSession, "after_flush_postexec", _after_flush_postexec)
    _INSTALLED = True
