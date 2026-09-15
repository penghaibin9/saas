"""Durable receipts for existing grade commands, scoped to their original actor.

The reservation and SUCCESS result belong to the caller's business transaction.
This namespace does not use the generic Redis reservation/TTL execution path.
No business state is reconstructed from a later object status or audit message.
"""
from __future__ import annotations

import hashlib
import re

from sqlalchemy import event, select
from sqlalchemy.exc import IntegrityError

from app.core.affairs_security import build_affairs_context, no_data_scope
from app.core.exceptions import AppException, no_permission
from app.core.idempotency import _fingerprint
from app.core.permissions import has_permission
from app.core.security import require_mobile_staff
from app.models.idempotency import IdempotencyRecord
from app.services.db_service import _tid, session

RESOURCE_PERMISSIONS = {
    "RESOURCE_CLASSROOM_BOOK": "academicAffairs.classroom.view",
    "RESOURCE_CLASSROOM_REVIEW": "academicAffairs.classroom.update",
    "RESOURCE_LAB_BOOK": "academicAffairs.lab.view",
    "RESOURCE_LAB_REVIEW": "academicAffairs.lab.update",
    "RESOURCE_LAB_BIND": "academicAffairs.lab.update",
}

MAKEUP_PERMISSIONS = {
    "MAKEUP_RETAKE_REVIEW": "academicAffairs.retake.review",
    "MAKEUP_RETAKE_ENROLL": "academicAffairs.retake.review",
    "MAKEUP_EXEMPTION_REVIEW": "academicAffairs.exemption.review",
    "MAKEUP_EXEMPTION_ARCHIVE": "academicAffairs.makeup.archive",
}

GRADE_ENTRY_PERMISSIONS = {
    "GRADE_COMPONENT_BATCH_SAVE": "academicAffairs.grade.input",
    "GRADE_TASK_SUBMIT": "academicAffairs.grade.submit",
}

# 工作量申报属于教师本人的移动端写命令。复用已发布且已经授予任课教师的
# 教学录入权限，避免凭空新增一条尚未进入学校角色模板的权限码而误伤正式账号。
WORKLOAD_PERMISSIONS = {
    "WORKLOAD_SUBMIT": "academicAffairs.grade.input",
}

PERMISSIONS = {
    "WARNING_FOLLOW_UP": "academicAffairs.warning.handle",
    **GRADE_ENTRY_PERMISSIONS,
    **WORKLOAD_PERMISSIONS,
    **RESOURCE_PERMISSIONS,
    **MAKEUP_PERMISSIONS,
    "RECHECK_REVIEW": "academicAffairs.grade.publish",
    "RECOGNITION_SUBMIT": "academicAffairs.gradeRecognition.manage",
    "RECOGNITION_REVIEW": "academicAffairs.gradeRecognition.manage",
    "GRADE_CHANGE_APPLY": "academicAffairs.gradeChange.apply",
    "GRADE_CHANGE_REVIEW": "academicAffairs.gradeChange.review",
}


def _authority(db, user, operation):
    permission = PERMISSIONS.get(operation)
    if permission is None:
        raise AppException("VALIDATION_ERROR", "不支持的教务命令类型")
    if operation == "WARNING_FOLLOW_UP":
        from .mobile_academic_warning_service import _staff
        _staff(user)
        if not has_permission(user, permission):
            raise no_permission("当前身份无权记录预警跟进")
        return
    if operation in WORKLOAD_PERMISSIONS:
        # 路由身份依赖不是唯一入口：历史命令回执会直接调用这里，故再次校验
        # 教师小程序签发端、教职工身份和既有教学职责权限。
        require_mobile_staff(user)
        if not has_permission(user, permission):
            raise no_permission("当前身份无权申报教师工作量")
        return
    if not user or not user.get("userId") or not has_permission(user, permission):
        raise no_permission("当前身份无权读取或办理该教务命令")
    if operation not in GRADE_ENTRY_PERMISSIONS and operation not in RESOURCE_PERMISSIONS and operation not in MAKEUP_PERMISSIONS and not operation.startswith("GRADE_CHANGE_") and build_affairs_context(user, db).scope_type != "TENANT_ALL":
        raise no_data_scope("仅教务处可读取或办理该教务命令")


def _require_result_scope(db, user, operation, result):
    if operation == "WARNING_FOLLOW_UP":
        from .academic_affairs_warning_service import _warning_or_404
        from .mobile_academic_warning_service import require_warning_scope
        warning = _warning_or_404(db, result.get("warningId"))
        require_warning_scope(db, user, warning, writing=True)
        return
    if operation in GRADE_ENTRY_PERMISSIONS:
        from . import academic_affairs_dynamic_grade_service as dynamic
        dynamic._task(db, int(result.get("gradeTaskId") or 0), user)
        return
    if operation in WORKLOAD_PERMISSIONS:
        from app.core.affairs_security import _derive_keys
        from app.models import AaWorkloadDeclaration

        try:
            declaration_id = int(result.get("declarationId") or 0)
        except (TypeError, ValueError):
            declaration_id = 0
        keys = sorted(str(value) for value in _derive_keys(user or {}) if str(value).strip())
        visible = declaration_id > 0 and db.scalar(select(AaWorkloadDeclaration.id).where(
            AaWorkloadDeclaration.id == declaration_id,
            AaWorkloadDeclaration.tenant_id == _tid(),
            AaWorkloadDeclaration.teacher_key.in_(keys or ["__none__"]),
            AaWorkloadDeclaration.is_deleted.is_(False),
        ))
        if not visible:
            raise no_data_scope("原工作量申报已不在当前本人范围，不能读取历史命令回执")
        return
    if operation in MAKEUP_PERMISSIONS:
        from app.models import AaRetakeApply, AaExemption
        from . import academic_affairs_makeup_service as makeup
        from . import academic_affairs_makeup_core_service as core
        ctx = core._ctx(user, db)
        if operation.startswith("MAKEUP_RETAKE_"):
            core._require_school(ctx)
            query = select(AaRetakeApply.id).where(
                AaRetakeApply.id == int(result.get("applyId") or 0),
                AaRetakeApply.tenant_id == _tid(), AaRetakeApply.is_deleted.is_(False),
            )
        else:
            query = select(AaExemption.id).where(
                AaExemption.id == int(result.get("exemptionId") or 0),
                AaExemption.tenant_id == _tid(), AaExemption.is_deleted.is_(False),
            )
            if operation == "MAKEUP_EXEMPTION_ARCHIVE":
                if ctx.scope_type not in {"TENANT_ALL", "COLLEGE"}:
                    raise no_data_scope("当前身份无权读取原材料归档回执")
                if ctx.scope_type == "COLLEGE":
                    query = query.where(AaExemption.college_id.in_(sorted(ctx.college_ids)))
            else:
                query = query.where(makeup._exemption_scope(ctx, user))
        if db.scalar(query) is None:
            raise no_data_scope("原申请已不在当前范围，不能读取历史命令回执")
        return
    if operation in RESOURCE_PERMISSIONS:
        from app.models import AaClassroomBooking, AaLabBooking, AaLabResource
        model = AaLabResource if operation == "RESOURCE_LAB_BIND" else (
            AaLabBooking if operation.startswith("RESOURCE_LAB_") else AaClassroomBooking)
        object_id = result.get("labId" if operation == "RESOURCE_LAB_BIND" else "bookingId")
        visible = db.scalar(select(model.id).where(
            model.id == int(object_id or 0), model.tenant_id == _tid(), model.is_deleted.is_(False),
        ))
        if visible is None:
            raise no_data_scope("原资源对象已不可读取，不能展示历史命令回执")
        return
    if not operation.startswith("GRADE_CHANGE_"):
        return
    from . import academic_affairs_grade_change_read_service as changes
    from app.models.academic_affairs_effective_grade import AaGradeChangeRequest

    request_id = result.get("changeRequestId")
    access = changes._access(db, user)
    visible = db.execute(changes._query(db, user, access).where(
        AaGradeChangeRequest.id == int(request_id or 0),
    )).first()
    if visible is None:
        raise no_data_scope("原成绩更正已不在当前权限范围，不能读取历史命令回执")


def _key(value):
    value = str(value or "").strip()
    if not re.fullmatch(r"[A-Za-z0-9_-]{8,128}", value):
        raise AppException("VALIDATION_ERROR", "教务命令键须为8至128位字母、数字、下划线或短横线")
    return value


def _require_transaction_store(db):
    # The supported acceptance environment is isolated MySQL. Do not let an
    # emulated SAVEPOINT/row-lock implementation acknowledge a durable result.
    if db.get_bind().dialect.name != "mysql":
        raise AppException("COMMAND_RECEIPT_STORE_UNAVAILABLE", "当前环境尚不能可靠保存命令回执", http_status=503)


def _require_finished(db, receipt):
    if not db.in_nested_transaction() and receipt.state != "SUCCESS":
        raise AppException("COMMAND_RESULT_UNRESOLVED", "命令结果尚未绑定正式事务，已阻止部分提交", http_status=503)


def _conditions(user, operation, key):
    # Refreshing an access token keeps the same authority context; another
    # role/context cannot read a previous context's command result.
    context = _fingerprint({"role": user.get("currentRoleCode"), "context": user.get("activeContextId")})[:20]
    prefix = "AA_RESOURCE_RECEIPT" if operation in RESOURCE_PERMISSIONS else (
        "AA_MAKEUP_RECEIPT" if operation in MAKEUP_PERMISSIONS else (
            "AA_WORKLOAD_RECEIPT" if operation in WORKLOAD_PERMISSIONS else "AA_GRADE_RECEIPT"))
    namespace = f"{prefix}:{operation}:{context}"
    return {
        "tenant_id": _tid(), "user_id": str(user["userId"]), "operation": namespace,
        "key_hash": hashlib.sha256(key.encode("utf-8")).hexdigest(),
    }


def begin(db, user, operation, key, payload):
    """Return (new receipt, None) or (None, previously committed result).

    Insert under a savepoint first: two missing-row SELECT FOR UPDATE probes
    would both take gap locks before competing to insert the same request key.
    The unique index arbitrates; a duplicate is then read with a current lock.
    Call this before acquiring business-object locks or changing business data.
    """
    if key is None:
        return None, None
    key = _key(key)
    _authority(db, user, operation)
    _require_transaction_store(db)
    identity = _conditions(user, operation, key)
    fingerprint = _fingerprint(payload)
    try:
        with db.begin_nested():
            row = IdempotencyRecord(**identity, fingerprint=fingerprint, state="PROCESSING",
                                    result_json=None, expires_at=None)
            db.add(row)
            db.flush()
        event.listen(db, "before_commit", lambda current: _require_finished(current, row))
        return row, None
    except IntegrityError:
        row = db.scalar(select(IdempotencyRecord).filter_by(**identity)
                        .with_for_update().execution_options(populate_existing=True))
        if row is None:
            raise AppException("COMMAND_RESULT_UNRESOLVED", "教务命令结果尚无法确认，请只读核对", http_status=503)
        if row.fingerprint != fingerprint:
            raise AppException("DATA_CONFLICT", "同一教务命令键不能用于不同对象或请求内容", http_status=409)
        if row.state == "SUCCESS" and isinstance(row.result_json, dict):
            _require_result_scope(db, user, operation, row.result_json)
            return None, dict(row.result_json)
        raise AppException("COMMAND_RESULT_UNRESOLVED", "教务命令结果尚无法确认，请勿重复提交", http_status=503)


def finish(db, receipt, result):
    if receipt is None:
        return
    receipt.state = "SUCCESS"
    receipt.result_json = dict(result)
    # No independent commit: any failure in the business commit rolls this back.
    db.flush()


def read(user, operation, key):
    key = _key(key)
    with session() as db:
        _authority(db, user, operation)
        _require_transaction_store(db)
        row = db.scalar(select(IdempotencyRecord).filter_by(**_conditions(user, operation, key)))
        resolved = row is not None and row.state == "SUCCESS" and isinstance(row.result_json, dict)
        if resolved:
            _require_result_scope(db, user, operation, row.result_json)
        return {"commandKey": key, "operation": operation, "state": "SUCCESS" if resolved else "UNRESOLVED",
                "result": dict(row.result_json) if resolved else None}


def record_grade_change_effect(user, key, committed_result, effect):
    """Enrich only the committed command's own side-effect receipt.

    The primary result is already durable. A crash here leaves its honest PENDING
    scan result; it cannot roll back the grade or turn a commit into a POST failure.
    """
    if key is None:
        return {**committed_result, **effect}
    try:
        with session() as db:
            row = db.scalar(select(IdempotencyRecord).filter_by(
                **_conditions(user, "GRADE_CHANGE_REVIEW", _key(key)),
            ).with_for_update().execution_options(populate_existing=True))
            if (row is None or row.state != "SUCCESS" or not isinstance(row.result_json, dict)
                    or row.result_json.get("correctedGradeId") != committed_result.get("correctedGradeId")
                    or row.result_json.get("warningScanJobId") != effect.get("warningScanJobId")):
                return committed_result
            fields = {k: effect[k] for k in ("warningScanJobId", "warningScanState", "warningScanOk",
                      "warningScanError", "warningScanResult", "notificationState") if k in effect}
            result = {**row.result_json, **fields}
            row.result_json = result
            db.commit()
            return result
    except Exception:
        import logging
        logging.getLogger(__name__).exception("Grade change committed; scan receipt update unavailable")
        return committed_result
