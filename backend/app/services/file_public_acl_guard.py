"""包 6：公共文件入口、事务绑定与默认对象 ACL 的 fail-closed 安全层。

通用上传只产生 TEMP_PRIVATE 文件。正式业务文件必须由业务事务建立 ACTIVE binding
并通过业务 resolver；上传者身份、通用模块 view 权限或无范围 BUSINESS_OBJECT
绑定均不能单独授予正式文件读取权限。
"""
from __future__ import annotations

from typing import Any

from sqlalchemy import select

from app.core.permissions import has_permission
from app.services import file_access_service as access
from app.services import file_access_resolvers as resolvers


_INSTALLED = False


def _is_temporary_private(file_obj) -> bool:
    """只识别无正式目标的临时对象；正式业务类型绝不能因 owner 放行。"""
    biz_type = str(getattr(file_obj, "biz_type", "") or "").upper()
    visibility = str(getattr(file_obj, "visibility", "") or "PRIVATE").upper()
    status = str(getattr(file_obj, "status", "") or "").upper()
    storage_zone = str(getattr(file_obj, "storage_zone", "") or "").upper()
    no_target = not str(getattr(file_obj, "biz_id", "") or "").strip()
    explicit_temp = biz_type == "TEMP_PRIVATE"
    import_staging = bool(
        biz_type.endswith("_IMPORT_SOURCE")
        and (status in {"UPLOADED", "QUARANTINED", "STORED"} or storage_zone == "QUARANTINE")
    )
    return bool(no_target and visibility == "PRIVATE" and (explicit_temp or import_staging))


def _active_bindings(bindings: list[Any]) -> list[Any]:
    return [
        item
        for item in bindings
        if not bool(getattr(item, "is_deleted", False))
        and str(getattr(item, "status", "") or "").upper() == "ACTIVE"
        and bool(getattr(item, "is_current", True))
    ]


def _text(value: Any) -> str:
    return str(value or "").strip()


def _student_internship_binding_allows(db, binding, actor: dict) -> bool:
    """把学生 token 解析到稳定 StudentProfile.id，再核对实习对象与批次。

    学生号只用于在当前租户内解析稳定主键，绝不直接充当业务文件授权主键；
    因此即使请求未携带批次头，也不会因为 binding.batch_id 而误拒本人材料。
    """
    if str(actor.get("userType") or "").upper() != "STUDENT":
        return False
    if str(getattr(binding, "subject_type", "") or "").upper() != "STUDENT":
        return False
    subject_id = _text(getattr(binding, "subject_id", None))
    if not subject_id.isdigit():
        return False

    from app.models import InternshipRecord, StudentProfile

    student = None
    actor_student_id = _text(actor.get("studentId"))
    if actor_student_id.isdigit():
        student = db.scalar(select(StudentProfile).where(
            StudentProfile.id == int(actor_student_id),
            StudentProfile.tenant_id == int(getattr(binding, "tenant_id", 0) or 0),
            StudentProfile.is_deleted.is_(False),
        ))
    if student is None:
        student_no = _text(actor.get("studentNo"))
        if not student_no:
            return False
        student = db.scalar(select(StudentProfile).where(
            StudentProfile.tenant_id == int(getattr(binding, "tenant_id", 0) or 0),
            StudentProfile.student_no == student_no,
            StudentProfile.is_deleted.is_(False),
        ))
    if not student or int(subject_id) != int(student.id):
        return False

    scope = dict(getattr(binding, "scope_json", None) or getattr(binding, "data_scope_snapshot_json", None) or {})
    scope_student_id = _text(scope.get("studentId"))
    if scope_student_id and scope_student_id != str(student.id):
        return False
    scope_student_no = _text(scope.get("studentNo"))
    if scope_student_no and scope_student_no != _text(student.student_no):
        return False

    internship_id = _text(scope.get("internshipId"))
    if not internship_id.isdigit():
        # 新合同中的实习文件必须冻结权威实习记录；缺失时默认拒绝。
        return False
    record = db.scalar(select(InternshipRecord).where(
        InternshipRecord.id == int(internship_id),
        InternshipRecord.tenant_id == student.tenant_id,
        InternshipRecord.student_id == student.id,
        InternshipRecord.is_deleted.is_(False),
    ))
    if not record:
        return False
    binding_batch = _text(getattr(binding, "batch_id", None))
    if binding_batch and binding_batch != _text(record.batch_id):
        return False
    scope_batch = _text(scope.get("batchId"))
    if scope_batch and scope_batch != _text(record.batch_id):
        return False
    return True


def strict_default_resolver(db, file_obj, bindings: list[Any], user: dict, action: str) -> bool:
    """未知业务类型没有权威 resolver 时仅允许管理临时私有文件。"""
    if _is_temporary_private(file_obj):
        return resolvers._owner_allows(file_obj, user or {})
    active = _active_bindings(bindings)
    return bool(active and any(access._binding_subject_allows(item, user or {}) for item in active))


def strict_scoped_binding_resolver(
    db,
    file_obj,
    bindings: list[Any],
    user: dict,
    action: str,
) -> bool:
    """普通业务文件必须同时具备动作权限与具体对象关系。"""
    if _is_temporary_private(file_obj):
        return resolvers._owner_allows(file_obj, user or {})

    active = _active_bindings(bindings)
    if not active:
        return False

    biz_type = str(getattr(file_obj, "biz_type", "") or "").upper()
    actor = user or {}
    internship_type = bool(
        biz_type in {"INTERNSHIP", "ENT_EVAL", "LEAVE"}
        or biz_type.startswith("INTERNSHIP_")
    )

    # 所有岗位实习正式文件都按绑定中的学生/实习记录做对象范围裁决。
    if internship_type:
        if str(actor.get("userType") or "").upper() == "STUDENT":
            return any(_student_internship_binding_allows(db, item, actor) for item in active)
        if resolvers._internship_staff_scope_allows(db, file_obj, active, actor):
            return True
        return False

    if str(actor.get("userType") or "").upper() == "STUDENT":
        return any(
            str(getattr(item, "subject_type", "") or "").upper() in {"STUDENT", "USER"}
            and access._binding_subject_allows(item, actor)
            for item in active
        )

    permission = access._FILE_VIEW_PERMISSION.get(biz_type)
    if not permission or not has_permission(actor, permission):
        return False
    return any(access._binding_subject_allows(item, actor) for item in active)


def install() -> None:
    """幂等安装公共 ACL 与事务绑定钩子；由权威 file contract 加载。"""
    global _INSTALLED
    if _INSTALLED:
        return
    access._default_resolver = strict_default_resolver
    scoped_types = {
        "INTERNSHIP",
        "ENT_EVAL",
        "LEAVE",
        "INTERNSHIP_AGREEMENT",
        "INTERNSHIP_APPLICATION",
        "INTERNSHIP_INSURANCE",
        "INTERNSHIP_ENTERPRISE_EVAL",
        "INTERNSHIP_STUDENT_EVAL",
        "INTERNSHIP_GUIDANCE",
        "INTERNSHIP_VISIT",
        "INTERNSHIP_LEAVE",
        "INTERNSHIP_ATTENDANCE_APPEAL",
        "INTERNSHIP_PLAN_TASK",
        "INTERNSHIP_SAFETY",
        "COURSE_MATERIAL",
        "ATTACHMENT",
        "AID",
        "RISK",
        "MENTAL",
    }
    for biz_type in scoped_types:
        access._RESOLVERS[biz_type] = strict_scoped_binding_resolver

    from app.services.file_business_binding_service import install_internship_binding_hooks

    install_internship_binding_hooks()
    _INSTALLED = True
