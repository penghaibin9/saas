"""公共文件冻结中心内置业务 resolver 注册。

该模块通过 registry 正式注册，不改写 file_service 函数，不使用运行时 monkey-patch。
"""
from __future__ import annotations

from typing import Any

from sqlalchemy import or_, select

from app.core.permissions import has_permission
from app.services.file_access_service import (
    _FILE_VIEW_PERMISSION,
    _actor_id,
    _actor_student_values,
    _binding_subject_allows,
    _is_file_admin,
    register_file_resolver,
)
from app.services.message_identity import resolve_message_user_id


def _owner_allows(file_obj, user: dict) -> bool:
    """兼容正式数字账号与 mock/历史字符串账号的统一 owner 判断。"""
    owner = str(file_obj.owner_user_id or file_obj.created_by or "").strip()
    if not owner:
        return False
    actor_values = {_actor_id(user)}
    resolved = resolve_message_user_id(user)
    if resolved:
        actor_values.add(str(resolved))
    return owner in {item for item in actor_values if item}


def _student_scope_values(db, file_obj, user: dict) -> set[str]:
    """补齐 studentNo、StudentProfile.id 与令牌 studentId 的等价身份。"""
    values = set(_actor_student_values(user))
    if db is None:
        return values
    try:
        from app.models import StudentProfile

        tenant_id = int(file_obj.tenant_id or 0)
        explicit_id = str(user.get("studentId") or "").strip()
        student_no = str(user.get("studentNo") or "").strip()
        row = None
        if explicit_id.isdigit():
            row = db.scalars(select(StudentProfile).where(
                StudentProfile.tenant_id == tenant_id,
                StudentProfile.id == int(explicit_id),
                StudentProfile.is_deleted.is_(False),
            )).first()
        if row is None and student_no:
            row = db.scalars(select(StudentProfile).where(
                StudentProfile.tenant_id == tenant_id,
                StudentProfile.student_no == student_no,
                StudentProfile.is_deleted.is_(False),
            )).first()
        if row is not None:
            values.add(str(row.id))
            values.add(str(row.student_no or "").strip())
    except Exception:
        # 身份补齐异常必须收窄为现有令牌值，不能放宽授权。
        pass
    return {item for item in values if item}


def _collect_internship_scope(file_obj, bindings: list[Any], db) -> tuple[set[int], set[int]]:
    """从文件对象、绑定与请假单中还原权威实习记录/学生范围。"""
    student_ids: set[int] = set()
    internship_ids: set[int] = set()
    tenant_id = int(file_obj.tenant_id or 0)

    def add_numeric(value, target: set[int]) -> None:
        raw = str(value or "").strip()
        if raw.isdigit():
            target.add(int(raw))

    biz_type = str(file_obj.biz_type or "").upper()
    if biz_type in {"INTERNSHIP", "ENT_EVAL"}:
        # 历史数据中 biz_id 可能是 StudentProfile.id，也可能是 InternshipRecord.id；
        # 下方查询同时按两种解释收敛，不直接据此放行。
        add_numeric(file_obj.biz_id, student_ids)
        add_numeric(file_obj.biz_id, internship_ids)

    leave_ids: set[int] = set()
    if biz_type == "LEAVE":
        add_numeric(file_obj.biz_id, leave_ids)

    for item in bindings:
        binding_type = str(item.biz_type or "").upper()
        if binding_type in {"INTERNSHIP", "ENT_EVAL"}:
            add_numeric(item.biz_id, student_ids)
            add_numeric(item.biz_id, internship_ids)
        elif binding_type == "LEAVE":
            add_numeric(item.biz_id, leave_ids)
        if str(item.subject_type or "").upper() == "STUDENT":
            add_numeric(item.subject_id, student_ids)
        scope = item.scope_json or {}
        add_numeric(scope.get("studentId"), student_ids)
        add_numeric(scope.get("internshipId"), internship_ids)

    if db is not None and leave_ids:
        try:
            from app.models import InternshipLeave

            rows = db.scalars(select(InternshipLeave).where(
                InternshipLeave.tenant_id == tenant_id,
                InternshipLeave.id.in_(leave_ids),
                InternshipLeave.is_deleted.is_(False),
            )).all()
            for row in rows:
                student_ids.add(int(row.student_id))
                internship_ids.add(int(row.internship_id))
        except Exception:
            return set(), set()
    return student_ids, internship_ids


def _internship_staff_scope_allows(db, file_obj, bindings: list[Any], user: dict) -> bool:
    """仅放行与文件目标学生存在真实指导关系的实习教师。"""
    if db is None or str(user.get("userType") or "").upper() != "TEACHER":
        return False
    student_ids, internship_ids = _collect_internship_scope(file_obj, bindings, db)
    if not student_ids and not internship_ids:
        return False
    try:
        from app.models import InternshipRecord

        clauses = []
        if student_ids:
            clauses.append(InternshipRecord.student_id.in_(student_ids))
        if internship_ids:
            clauses.append(InternshipRecord.id.in_(internship_ids))
        rows = db.scalars(select(InternshipRecord).where(
            InternshipRecord.tenant_id == int(file_obj.tenant_id),
            InternshipRecord.is_deleted.is_(False),
            or_(*clauses),
        )).all()
        actor_name = str(user.get("realName") or user.get("name") or "").strip()
        actor_user_id = resolve_message_user_id(user)
        return any(
            (actor_user_id and int(row.advisor_user_id or 0) == actor_user_id)
            or (actor_name and str(row.advisor_name or "").strip() == actor_name)
            for row in rows
        )
    except Exception:
        return False


@register_file_resolver(
    "GRADUATION_MATERIAL",
    "INTERNSHIP",
    "ENT_EVAL",
    "COURSE_MATERIAL",
    "ATTACHMENT",
    "LEAVE",
    "AID",
    "RISK",
    "MENTAL",
)
def scoped_binding_resolver(db, file_obj, bindings: list[Any], user: dict, action: str) -> bool:
    if _owner_allows(file_obj, user):
        return True
    if _is_file_admin(user):
        return True

    active = [item for item in bindings if not item.is_deleted and item.status == "ACTIVE"]
    if str(file_obj.biz_type or "").upper() in {"INTERNSHIP", "ENT_EVAL", "LEAVE"}:
        if _internship_staff_scope_allows(db, file_obj, active, user):
            return True

    if active:
        subject_allowed = any(_binding_subject_allows(item, user) for item in active)
        if not subject_allowed:
            return False
        if str(user.get("userType") or "").upper() == "STUDENT":
            return any(
                str(item.subject_type or "").upper() in {"STUDENT", "USER"}
                and _binding_subject_allows(item, user)
                for item in active
            )
        permission = _FILE_VIEW_PERMISSION.get(str(file_obj.biz_type or "").upper())
        if permission:
            return has_permission(user, permission)
        # 未映射的冻结业务类型仅允许显式绑定主体本人，不能按租户泛化授权。
        return subject_allowed

    # 历史对象没有绑定表时，仅兼容本人、学生本人业务归属或明确业务权限。
    if str(user.get("userType") or "").upper() == "STUDENT":
        biz_id = str(file_obj.biz_id or "").strip()
        return bool(biz_id and biz_id in _student_scope_values(db, file_obj, user))
    permission = _FILE_VIEW_PERMISSION.get(str(file_obj.biz_type or "").upper())
    return bool(permission and has_permission(user, permission))


@register_file_resolver("AFFAIRS_ARCHIVE")
def affairs_archive_resolver(db, file_obj, bindings: list[Any], user: dict, action: str) -> bool:
    """学工归档文件：archive.view 与目标学生数据范围必须同时成立。"""
    if not has_permission(user or {}, "studentAffairs.archive.view"):
        return False
    student_id = str(file_obj.biz_id or "").strip()
    if not student_id.isdigit() or db is None:
        return False
    try:
        from app.core.affairs_security import build_affairs_context

        build_affairs_context(user or {}, db).require_student(db, int(student_id))
        return True
    except Exception:
        return False


@register_file_resolver("MATERIAL_REQUIREMENT")
def material_requirement_resolver(db, file_obj, bindings: list[Any], user: dict, action: str) -> bool:
    """学工补材料附件：业务权限与材料目标学生范围必须同时成立。"""
    raw_id = str(file_obj.biz_id or "").strip()
    if not raw_id.isdigit() or db is None:
        return False
    try:
        from app.models.affairs_operations import AffairsMaterialRequirement
        from app.services import affairs_operations_service as operations

        requirement = db.scalars(select(AffairsMaterialRequirement).where(
            AffairsMaterialRequirement.tenant_id == int(file_obj.tenant_id),
            AffairsMaterialRequirement.id == int(raw_id),
            AffairsMaterialRequirement.is_deleted.is_(False),
        )).first()
        if not requirement:
            return False
        permissions = operations._BIZ_PERMISSIONS.get(requirement.biz_type, ())
        if not any(has_permission(user or {}, code) for code in permissions):
            return False
        operations._require_student_scope(db, requirement.student_id, user or {})
        return True
    except Exception:
        return False
