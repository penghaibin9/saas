"""公共文件冻结中心内置业务 resolver 注册。

该模块通过 registry 正式注册，不改写 file_service 函数，不使用运行时 monkey-patch。
毕业设计、岗位实习和学工强敏感材料均在公共文件对象授权之后叠加真实业务数据范围；
通用文件管理员权限不能自动绕过具体业务关系。
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
        pass
    return {item for item in values if item}


def _collect_internship_scope(file_obj, bindings: list[Any], db) -> tuple[set[int], set[int]]:
    """从文件对象、绑定与请假单中还原权威实习记录/学生范围。"""
    student_ids: set[int] = set()
    internship_ids: set[int] = set()
    ambiguous_student_ids: set[int] = set()
    ambiguous_internship_ids: set[int] = set()
    tenant_id = int(file_obj.tenant_id or 0)

    def add_numeric(value, target: set[int]) -> None:
        raw = str(value or "").strip()
        if raw.isdigit():
            target.add(int(raw))

    biz_type = str(file_obj.biz_type or "").upper()
    if biz_type in {"INTERNSHIP", "ENT_EVAL"}:
        add_numeric(file_obj.biz_id, ambiguous_student_ids)
        add_numeric(file_obj.biz_id, ambiguous_internship_ids)

    leave_ids: set[int] = set()
    if biz_type == "LEAVE":
        add_numeric(file_obj.biz_id, leave_ids)

    for item in bindings:
        binding_type = str(item.biz_type or "").upper()
        if binding_type in {"INTERNSHIP", "ENT_EVAL"}:
            add_numeric(item.biz_id, ambiguous_student_ids)
            add_numeric(item.biz_id, ambiguous_internship_ids)
        elif binding_type == "LEAVE":
            add_numeric(item.biz_id, leave_ids)
        if str(item.subject_type or "").upper() == "STUDENT":
            add_numeric(item.subject_id, student_ids)
        scope = item.scope_json or {}
        add_numeric(scope.get("studentId"), student_ids)
        add_numeric(scope.get("internshipId"), internship_ids)

    linked_leaves = []
    if db is not None:
        try:
            from app.models import InternshipLeave

            leave_clauses = [InternshipLeave.file_id == str(file_obj.id)]
            if leave_ids:
                leave_clauses.append(InternshipLeave.id.in_(leave_ids))
            linked_leaves = db.scalars(select(InternshipLeave).where(
                InternshipLeave.tenant_id == tenant_id,
                InternshipLeave.is_deleted.is_(False),
                or_(*leave_clauses),
            )).all()
            for row in linked_leaves:
                student_ids.add(int(row.student_id))
                internship_ids.add(int(row.internship_id))
        except Exception:
            return set(), set()

    if not linked_leaves:
        student_ids.update(ambiguous_student_ids)
        internship_ids.update(ambiguous_internship_ids)
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

    biz_type = str(file_obj.biz_type or "").upper()
    permission = _FILE_VIEW_PERMISSION.get(biz_type)
    subject_allowed = any(_binding_subject_allows(item, user) for item in active)

    if str(user.get("userType") or "").upper() == "STUDENT":
        biz_id = str(file_obj.biz_id or "").strip()
        if biz_id and biz_id in _student_scope_values(db, file_obj, user):
            return True
        return any(
            str(item.subject_type or "").upper() in {"STUDENT", "USER"}
            and _binding_subject_allows(item, user)
            for item in active
        )

    if permission and has_permission(user, permission):
        # 上传者 USER 绑定只表示来源；普通业务台账由明确业务权限放行。
        # 通用附件、资助、风险和心理材料仍必须同时命中具体绑定范围。
        if biz_type in {"ATTACHMENT", "AID", "RISK", "MENTAL"}:
            return subject_allowed
        return True
    return subject_allowed


def _graduation_student_ids(bindings: list[Any]) -> set[int]:
    explicit: set[int] = set()
    legacy: set[int] = set()
    for binding in bindings:
        if binding.is_deleted:
            continue
        scope = binding.scope_json or {}
        gd_student_id = str(scope.get("gdStudentId") or "").strip()
        if gd_student_id.isdigit():
            explicit.add(int(gd_student_id))
            continue
        student_id = str(getattr(binding, "student_id", None) or "").strip()
        if student_id.isdigit():
            legacy.add(int(student_id))
    # Current bindings carry both GraduationStudent.id in scope_json and the
    # StudentProfile.id column. They are different namespaces, so never mix them.
    return explicit or legacy


def _graduation_staff_permission(user: dict, action: str) -> bool:
    permissions = {
        "graduationDesign.view",
        "graduationDesign.student.view",
        "graduationDesign.proposal.review",
        "graduationDesign.final.review",
        "graduationDesign.archive.view",
        "graduationDesign.archive.file",
        "graduationDesign.archive.export",
    }
    if action in {"submit", "bind"}:
        permissions.update({"graduationDesign.material.manage", "graduationDesign.student.manage"})
    return any(has_permission(user or {}, permission) for permission in permissions)


@register_file_resolver("GRADUATION_MATERIAL")
def graduation_material_resolver(db, file_obj, bindings: list[Any], user: dict, action: str) -> bool:
    """毕业设计材料必须同时满足租户文件授权与具体学生/导师/组织范围。"""
    if db is None:
        return False
    # A new upload has no business binding until its first material submission.
    # Only that uploader may cross this narrow bind/submit bridge; all later
    # access continues through the authoritative Asset/Version binding below.
    if not bindings and action in {"bind", "submit"}:
        return _owner_allows(file_obj, user or {})
    valid = [
        item for item in bindings
        if not item.is_deleted and str(item.module_code or "").upper() == "GRADUATION"
        and item.status in {"ACTIVE", "SUPERSEDED", "ARCHIVED"}
        and item.version_id and item.asset_id
    ]
    # Stage 2 historical bindings predate Asset/Version columns. Keep a narrow
    # compatibility adapter until backfill completes: the binding must carry a
    # concrete student/user/batch/role scope, and staff still need graduation
    # permission. A generic BUSINESS_OBJECT binding without batch scope is never
    # enough, and systemAdmin.file.manage does not bypass this resolver.
    if not valid:
        scoped_legacy = [
            item for item in bindings
            if not item.is_deleted and item.status == "ACTIVE"
            and (
                str(item.subject_type or "").upper() in {"STUDENT", "USER", "BATCH", "ROLE"}
                or bool(str(item.batch_id or "").strip())
            )
        ]
        if not scoped_legacy:
            return False
        if str(user.get("userType") or "").upper() == "STUDENT":
            return any(
                str(item.subject_type or "").upper() in {"STUDENT", "USER"}
                and _binding_subject_allows(item, user)
                for item in scoped_legacy
            )
        return bool(
            _graduation_staff_permission(user or {}, action)
            and any(_binding_subject_allows(item, user) for item in scoped_legacy)
        )
    gd_student_ids = _graduation_student_ids(valid)
    if len(gd_student_ids) != 1:
        return False
    gd_student_id = next(iter(gd_student_ids))
    try:
        from app.models import GraduationStudent
        from app.modules.graduation.services.graduation_record_resolver import resolve_current_gd_student
        from app.modules.graduation.services.graduation_scope_service import assert_student_access

        student = db.scalars(select(GraduationStudent).where(
            GraduationStudent.id == gd_student_id,
            GraduationStudent.tenant_id == int(file_obj.tenant_id),
            GraduationStudent.is_deleted.is_(False),
            GraduationStudent.record_status == "ACTIVE",
        )).first()
        if not student:
            return False
        if str(user.get("userType") or "").upper() == "STUDENT":
            current = resolve_current_gd_student(db, user or {})
            return bool(current and int(current.id) == int(student.id))
        # systemAdmin.file.manage 不是毕业设计数据范围；必须具备毕设动作权限并通过学生范围。
        if not _graduation_staff_permission(user or {}, action):
            return False
        assert_student_access(db, student, f"file.{action}")
        return True
    except Exception:
        return False


@register_file_resolver("GRADUATION_TEMPLATE")
def graduation_template_resolver(db, file_obj, bindings: list[Any], user: dict, action: str) -> bool:
    if db is None:
        return False
    try:
        from app.models.graduation_material import GraduationTemplateAssetPolicy
        from app.modules.graduation.services.graduation_record_resolver import resolve_current_gd_student

        asset_ids = {int(item.asset_id) for item in bindings if item.asset_id and not item.is_deleted}
        if len(asset_ids) != 1:
            return False
        policy = db.scalars(select(GraduationTemplateAssetPolicy).where(
            GraduationTemplateAssetPolicy.tenant_id == int(file_obj.tenant_id),
            GraduationTemplateAssetPolicy.asset_id.in_(asset_ids),
            GraduationTemplateAssetPolicy.is_deleted.is_(False),
        )).first()
        if not policy:
            return False
        if str(user.get("userType") or "").upper() == "STUDENT":
            student = resolve_current_gd_student(db, user or {})
            if not student or not policy.enabled or policy.status != "ENABLED":
                return False
            if policy.batch_id and int(policy.batch_id) != int(student.batch_id or 0):
                return False
            if policy.college_id and str(policy.college_id) != str(student.college_id or ""):
                return False
            if policy.major_id and str(policy.major_id) != str(student.major_id or ""):
                return False
            return True
        return any(has_permission(user or {}, code) for code in (
            "graduationDesign.template.view",
            "graduationDesign.template.manage",
            "graduationDesign.view",
        ))
    except Exception:
        return False


@register_file_resolver("GRADUATION_ARCHIVE_PACKAGE", "GRADUATION_ARCHIVE_INDEX")
def graduation_archive_file_resolver(db, file_obj, bindings: list[Any], user: dict, action: str) -> bool:
    if db is None:
        return False
    try:
        from app.models import GraduationBatch, GraduationStudent
        from app.modules.graduation.services.graduation_record_resolver import resolve_current_gd_student
        from app.modules.graduation.services.graduation_scope_service import accessible_student_ids, assert_student_access

        biz_id = str(file_obj.biz_id or "").strip()
        if not biz_id.isdigit():
            return False
        if str(user.get("userType") or "").upper() == "STUDENT":
            if str(file_obj.biz_type or "").upper() != "GRADUATION_ARCHIVE_PACKAGE":
                return False
            current = resolve_current_gd_student(db, user or {})
            return bool(current and int(current.id) == int(biz_id))
        if not any(has_permission(user or {}, code) for code in (
            "graduationDesign.archive.view",
            "graduationDesign.archive.file",
            "graduationDesign.archive.export",
        )):
            return False
        if str(file_obj.biz_type or "").upper() == "GRADUATION_ARCHIVE_INDEX":
            batch = db.scalars(select(GraduationBatch).where(
                GraduationBatch.tenant_id == int(file_obj.tenant_id),
                GraduationBatch.id == int(biz_id),
                GraduationBatch.is_deleted.is_(False),
            )).first()
            return bool(batch and accessible_student_ids(db, int(file_obj.tenant_id), batch_id=int(batch.id)))
        student = db.scalars(select(GraduationStudent).where(
            GraduationStudent.tenant_id == int(file_obj.tenant_id),
            GraduationStudent.id == int(biz_id),
            GraduationStudent.is_deleted.is_(False),
        )).first()
        if student:
            assert_student_access(db, student, f"archive.file.{action}")
            return True
        batch = db.scalars(select(GraduationBatch).where(
            GraduationBatch.tenant_id == int(file_obj.tenant_id),
            GraduationBatch.id == int(biz_id),
            GraduationBatch.is_deleted.is_(False),
        )).first()
        return bool(batch and accessible_student_ids(db, int(file_obj.tenant_id), batch_id=int(batch.id)))
    except Exception:
        return False


@register_file_resolver("AFFAIRS_ARCHIVE")
def affairs_archive_resolver(db, file_obj, bindings: list[Any], user: dict, action: str) -> bool:
    """学工学生档案文件：archive.view 与目标学生数据范围必须同时成立。"""
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


@register_file_resolver("AFFAIRS_ARCHIVE_MANIFEST")
def affairs_archive_manifest_resolver(db, file_obj, bindings: list[Any], user: dict, action: str) -> bool:
    """批次级归档清单不含学生明文详情入口，但仅归档授权角色可访问。"""
    return bool(has_permission(user or {}, "studentAffairs.archive.view"))


@register_file_resolver("MATERIAL_REQUIREMENT")
def material_requirement_resolver(db, file_obj, bindings: list[Any], user: dict, action: str) -> bool:
    """学工补交材料：本人或业务授权角色；心理/困难再叠加强敏感范围。"""
    raw_id = str(file_obj.biz_id or "").strip()
    if not raw_id.isdigit() or db is None:
        return False
    try:
        from app.models.affairs_operations import AffairsMaterialRequirement
        from app.modules.student_affairs.services import affairs_material_center_service as center

        requirement = db.scalars(select(AffairsMaterialRequirement).where(
            AffairsMaterialRequirement.tenant_id == int(file_obj.tenant_id),
            AffairsMaterialRequirement.id == int(raw_id),
            AffairsMaterialRequirement.is_deleted.is_(False),
        )).first()
        if not requirement:
            return False

        # 学生本人可以查看自己提交的强敏感材料；不能通过 userId owner 偶然碰撞放行他人。
        if str(user.get("userType") or "").upper() == "STUDENT":
            return str(requirement.student_id) in _student_scope_values(db, file_obj, user)

        # 强敏感不接受 systemAdmin.file.manage 之类通用文件管理员越权。
        if not center._has_biz_permission(user or {}, requirement.biz_type):
            return False
        if requirement.material_scope == "PSY_STUDENT":
            return center._psy_scope_allows(db, requirement.student_id, user or {})
        center._require_student_scope(db, requirement.student_id, user or {}, hide=True)
        return True
    except Exception:
        return False
