"""公共文件冻结中心内置业务 resolver 注册。

该模块通过 registry 正式注册，不改写 file_service 函数，不使用运行时 monkey-patch。
毕业设计、岗位实习和学工强敏感材料均在公共文件对象授权之后叠加真实业务数据范围；
通用文件管理员权限不能自动绕过具体业务关系。
"""
from __future__ import annotations

from typing import Any

from app.core.context import current_tenant_id
from app.core.exceptions import AppException, not_found
from app.models import InternshipArchive, InternshipEvidencePackage
from app.models.file import ArchiveManifest, ArchiveManifestItem, FileObject, FileVersion

from sqlalchemy import or_, select

from app.core.permissions import has_permission
from app.modules.internship.services.internship_identity import stable_user_id
from app.services.file_access_service import (
    _FILE_VIEW_PERMISSION,
    _actor_id,
    _actor_student_values,
    _binding_subject_allows,
    _is_file_admin,
    register_file_resolver,
)
from app.services.message_identity import resolve_message_user_id


@register_file_resolver("AA_GRADE_CHANGE_REQUEST")
def grade_change_material_resolver(db, file_obj, bindings: list[Any], user: dict, action: str) -> bool:
    from app.modules.academic_affairs.services.academic_affairs_grade_change_material_service import file_access
    return file_access(db, file_obj, bindings, user, action)


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


@register_file_resolver("FUNDING")
def funding_evidence_resolver(db, file_obj, bindings: list[Any], user: dict, action: str) -> bool:
    """Student-submitted evidence stays readable by its applicant after formal binding."""
    if str(user.get("userType") or "").upper() != "STUDENT":
        from app.services.file_access_service import _student_affairs_resolver
        return _student_affairs_resolver(db, file_obj, bindings, user, action)
    if db is None or not str(file_obj.biz_id or "").isdigit():
        return False
    from app.models import FundingApplication
    from app.services.mobile_student_service import resolve_student
    student = resolve_student(db, user)
    row = db.get(FundingApplication, int(file_obj.biz_id))
    if not student or not row or row.is_deleted or row.tenant_id != file_obj.tenant_id or row.student_id != student.id:
        return False
    # Only evidence uploaded by this applicant. Staff investigation files do not
    # become student-visible merely because they reference the same application.
    return _owner_allows(file_obj, user) and any(
        not item.is_deleted and item.status == "ACTIVE" and item.is_current
        and item.biz_type == "FUNDING" and str(item.biz_id) == str(row.id)
        and item.relation_type == "BUSINESS_EVIDENCE" and item.subject_type == "STUDENT"
        and str(item.subject_id) == str(student.id)
        for item in bindings
    )


@register_file_resolver("LOAN")
def loan_receipt_resolver(db, file_obj, bindings: list[Any], user: dict, action: str) -> bool:
    """贷款回执按当前贷款记录授权，本人和经办教师读取同一份正式材料。"""
    if db is None or not str(file_obj.biz_id or "").isdigit():
        return False
    try:
        from app.models import StudentLoan

        loan = db.get(StudentLoan, int(file_obj.biz_id))
        if (not loan or loan.is_deleted or loan.tenant_id != file_obj.tenant_id
                or int(loan.receipt_file_id or 0) != int(file_obj.id)):
            return False
        if str(user.get("userType") or "").upper() == "STUDENT":
            from app.services.mobile_student_service import resolve_student
            student = resolve_student(db, user)
            return bool(student and int(student.id) == int(loan.student_id))
        if not has_permission(user or {}, "studentAffairs.funding.view"):
            return False
        from app.services.affairs_attachment_service import _require_biz_scope
        _require_biz_scope(db, "LOAN", loan.id, user)
        return True
    except Exception:
        return False


@register_file_resolver("REDUCTION")
def reduction_evidence_resolver(db, file_obj, bindings: list[Any], user: dict, action: str) -> bool:
    """减免/临补材料仅向申请本人和数据范围内经办教师开放。"""
    if db is None or not str(file_obj.biz_id or "").isdigit():
        return False
    try:
        from app.models import FeeReduction

        row = db.get(FeeReduction, int(file_obj.biz_id))
        if not row or row.is_deleted or row.tenant_id != file_obj.tenant_id:
            return False
        if str(user.get("userType") or "").upper() == "STUDENT":
            from app.services.mobile_student_service import resolve_student
            student = resolve_student(db, user)
            if not student or int(student.id) != int(row.student_id) or not _owner_allows(file_obj, user):
                return False
            return any(
                not item.is_deleted and item.status == "ACTIVE" and item.is_current
                and item.biz_type == "REDUCTION" and str(item.biz_id) == str(row.id)
                and item.relation_type == "BUSINESS_EVIDENCE" and item.subject_type == "STUDENT"
                and str(item.subject_id) == str(student.id)
                for item in bindings
            )
        if not has_permission(user or {}, "studentAffairs.funding.view"):
            return False
        from app.services.affairs_attachment_service import _require_biz_scope
        _require_biz_scope(db, "REDUCTION", row.id, user)
        return True
    except Exception:
        return False


@register_file_resolver("AFFAIRS_LEAVE")
def affairs_leave_evidence_resolver(db, file_obj, bindings: list[Any], user: dict, action: str) -> bool:
    """请假材料按既有 CsLeave 的学生本人和教师实时数据范围授权。

    不能沿用历史 ``LEAVE`` 的实习附件兼容 resolver：两种请假都叫 leave，
    但业务对象、教师范围和授权语义不同。这里仅接收正式 ``AFFAIRS_LEAVE``
    binding，避免凭猜测的 fileId、bizId 或通用查看权限越权读取材料。
    """
    if db is None or not str(file_obj.biz_id or "").isdigit():
        return False
    try:
        from app.models import CsLeave
        from app.services import affairs_leave_service as leave_svc
        from app.services.mobile_student_service import resolve_student

        leave = db.get(CsLeave, int(file_obj.biz_id))
        if not leave or leave.is_deleted or int(leave.tenant_id) != int(file_obj.tenant_id):
            return False
        active = [item for item in bindings if (
            not item.is_deleted and item.status == "ACTIVE" and item.is_current
            and str(item.biz_type or "").upper() == "AFFAIRS_LEAVE"
            and str(item.biz_id or "") == str(leave.id)
            and str(item.relation_type or "").upper() == "BUSINESS_EVIDENCE"
            and str(item.subject_type or "").upper() == "STUDENT"
            and str(item.subject_id or "") == str(leave.student_id or "")
        )]
        if not active:
            return False
        if str(user.get("userType") or "").upper() == "STUDENT":
            student = resolve_student(db, user or {})
            return bool(
                student
                and int(student.id) == int(leave.student_id or 0)
                and _owner_allows(file_obj, user or {})
            )
        if not has_permission(user or {}, "studentAffairs.leave.view"):
            return False
        leave_svc._scope_or_403(db, leave, user or {})
        return True
    except Exception:
        return False


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

    if not linked_leaves and not student_ids and not internship_ids:
        # Only legacy bindings without any authoritative subject/scope may interpret
        # the historical INTERNSHIP biz_id ambiguously. Once a current binding
        # carries student/internship scope, never union an unrelated numeric biz_id.
        student_ids.update(ambiguous_student_ids)
        internship_ids.update(ambiguous_internship_ids)
    return student_ids, internship_ids


def _internship_staff_scope_allows(db, file_obj, bindings: list[Any], user: dict) -> bool:
    """岗位实习内部人员必须命中绑定目标记录，并通过稳定导师身份或统一数据范围。"""
    actor_type = str((user or {}).get("userType") or "").upper()
    if db is None or actor_type not in {"TEACHER", "STAFF", "ADMIN", "SCHOOL_ADMIN"}:
        return False
    student_ids, internship_ids = _collect_internship_scope(file_obj, bindings, db)
    if not student_ids and not internship_ids:
        return False
    try:
        from app.models import InternshipRecord
        from app.modules.internship.services.internship_scope import assert_internship_record_scope

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

        # 指导教师授权只认稳定数字 userId；历史显示名字段永不参与授权。
        actor_user_id = stable_user_id(user)
        if actor_type == "TEACHER" and actor_user_id is not None:
            if any(
                row.advisor_user_id is not None
                and int(row.advisor_user_id) == actor_user_id
                for row in rows
            ):
                return True

        # 非直接导师以及学校内部管理角色继续走 #231 收口后的统一业务数据范围。
        for row in rows:
            try:
                assert_internship_record_scope(db, row.id, user or {}, "访问岗位实习业务文件")
                return True
            except Exception:
                continue
        return False
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


@register_file_resolver("ORIENTATION_MATERIAL", "ORIENTATION_GREEN_CHANNEL")
def orientation_file_resolver(db, file_obj, bindings: list[Any], user: dict, action: str) -> bool:
    """迎新材料只按父业务行的稳定 student_id 与实时教师数据范围授权。"""
    if db is None:
        return False
    try:
        from app.models import GreenChannelApplication, OrientationMaterial, OrientationStudent

        biz_type = str(file_obj.biz_type or "").upper()
        raw_id = str(file_obj.biz_id or "").strip()
        if not raw_id.isdigit():
            return False
        if biz_type == "ORIENTATION_MATERIAL":
            child = db.scalars(select(OrientationMaterial).where(
                OrientationMaterial.tenant_id == int(file_obj.tenant_id),
                OrientationMaterial.id == int(raw_id),
                OrientationMaterial.is_deleted.is_(False),
            )).first()
        else:
            child = db.scalars(select(GreenChannelApplication).where(
                GreenChannelApplication.tenant_id == int(file_obj.tenant_id),
                GreenChannelApplication.id == int(raw_id),
                GreenChannelApplication.is_deleted.is_(False),
            )).first()
        if not child:
            return False
        orientation = db.scalars(select(OrientationStudent).where(
            OrientationStudent.tenant_id == int(file_obj.tenant_id),
            OrientationStudent.id == int(child.ori_student_id),
            OrientationStudent.is_deleted.is_(False),
        )).first()
        if not orientation or not orientation.student_id:
            return False
        if str(user.get("userType") or "").upper() == "STUDENT":
            from app.services.mobile_student_service import resolve_student
            profile = resolve_student(db, user or {})
            return bool(profile and int(profile.id) == int(orientation.student_id))
        if not has_permission(user or {}, "studentAffairs.orientation.view"):
            return False
        from app.services.orientation_service import assert_orientation_student_scope
        assert_orientation_student_scope(db, orientation, user)
        return True
    except Exception:
        return False


@register_file_resolver("INTERNSHIP_ENTERPRISE_INSPECTION")
def enterprise_inspection_file_resolver(db, file_obj, bindings: list[Any], user: dict, action: str) -> bool:
    """学校考察材料仅随当前考察引用和学校查看权限开放，不进入学生/企业目录。"""
    if db is None or str(user.get("userType") or "").upper() in {"STUDENT", "ENTERPRISE"}:
        return False
    if not has_permission(user or {}, "internship.enterprise.inspection.view"):
        return False
    from app.models import EmpCompany, InternshipEnterpriseInspection
    raw_id = str(file_obj.biz_id or "")
    if not raw_id.isascii() or not raw_id.isdigit():
        return False
    tenant_id = int(file_obj.tenant_id)
    record = db.scalar(select(InternshipEnterpriseInspection).where(
        InternshipEnterpriseInspection.id == int(raw_id),
        InternshipEnterpriseInspection.tenant_id == tenant_id,
        InternshipEnterpriseInspection.is_deleted.is_(False),
    ))
    if not record or str(file_obj.id) not in {str(fid) for fid in (record.file_ids or [])}:
        return False
    company = db.scalar(select(EmpCompany).where(
        EmpCompany.id == record.company_id, EmpCompany.tenant_id == tenant_id, EmpCompany.is_deleted.is_(False),
    ))
    return bool(company and any(
        not b.is_deleted and b.status == "ACTIVE" and b.is_current
        and b.biz_type == "INTERNSHIP_ENTERPRISE_INSPECTION" and str(b.biz_id) == raw_id
        and int(b.tenant_id) == tenant_id and str(b.subject_id) == str(company.id)
        and b.subject_type == "ENTERPRISE" for b in bindings
    ))


@register_file_resolver("DORM_CHECK_RECORD", "DORM_RECTIFICATION")
def dorm_inspection_file_resolver(db, file_obj, bindings: list[Any], user: dict, action: str) -> bool:
    """宿舍巡检证据只按父业务行与实时楼栋/本人范围授权。"""
    if db is None:
        return False
    try:
        from app.models import DormCheckRecord, DormCheckTask, DormRectification

        biz_type = str(file_obj.biz_type or "").upper()
        raw_id = str(file_obj.biz_id or "").strip()
        if not raw_id.isdigit():
            return False
        tenant_id = int(file_obj.tenant_id)
        student_id = None
        if biz_type == "DORM_CHECK_RECORD":
            record = db.scalars(select(DormCheckRecord).where(
                DormCheckRecord.tenant_id == tenant_id,
                DormCheckRecord.id == int(raw_id),
                DormCheckRecord.is_deleted.is_(False),
            )).first()
            if not record:
                return False
            task = db.scalars(select(DormCheckTask).where(
                DormCheckTask.tenant_id == tenant_id,
                DormCheckTask.id == int(record.task_id),
                DormCheckTask.is_deleted.is_(False),
            )).first()
            if not task:
                return False
            building_id = int(task.building_id or 0)
            for item in bindings:
                if item.is_deleted or item.status != "ACTIVE":
                    continue
                scope = item.scope_json or {}
                raw_student = str(scope.get("studentId") or "").strip()
                if raw_student.isdigit():
                    student_id = int(raw_student)
                    break
        else:
            rect = db.scalars(select(DormRectification).where(
                DormRectification.tenant_id == tenant_id,
                DormRectification.id == int(raw_id),
                DormRectification.is_deleted.is_(False),
            )).first()
            if not rect:
                return False
            building_id = int(rect.building_id)
            student_id = int(rect.student_id) if rect.student_id else None

        if str(user.get("userType") or "").upper() == "STUDENT":
            if not student_id:
                return False
            from app.services.mobile_student_service import resolve_student
            profile = resolve_student(db, user or {})
            return bool(profile and int(profile.id) == student_id)

        if not has_permission(user or {}, "studentAffairs.dorm.view"):
            return False
        from app.services import affairs_dorm_service as dorm_service
        dorm_service._require_dorm_scope(db, building_id, user or {})
        return True
    except Exception:
        return False


@register_file_resolver("ARCHIVE_PACKAGE", "ARCHIVE_BATCH_PACKAGE")
def internship_archive_package_resolver(db, file_obj, bindings, user, action) -> bool:
    """归档包读取同时核验固定成员、文件版本和当前数据范围。"""
    try:
        return authorize_archive_package(db, file_obj, bindings, user or {}, action)
    except Exception:
        return False

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


# PLAT-A keeps its resolver beside the domain-neutral package adapter. Importing
# it here joins the existing File Center registry without creating an auth path.
from app.modules.platform_integrity import file_access_resolver as _platform_integrity_file_access_resolver  # noqa: E402,F401
from app.modules.platform.document_lifecycle.derived_access import document_derivative_resolver  # noqa: E402

register_file_resolver("DOCUMENT_DERIVATIVE")(document_derivative_resolver)


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
        return center._staff_can_read_content(db, requirement, user or {})
    except Exception:
        return False


@register_file_resolver("AA_STUDENT_CORRECTION")
def student_correction_file_resolver(db, file_obj, bindings: list[Any], user: dict, action: str) -> bool:
    """更正材料只允许有更正查看/审核权且命中学生范围的教职工读取。"""
    if db is None or str((user or {}).get("userType") or "").upper() == "STUDENT":
        return False
    if not any(has_permission(user or {}, code) for code in (
        "academicAffairs.roster.correction.view", "academicAffairs.roster.correction.review"
    )):
        return False
    biz_id = str(file_obj.biz_id or "")
    if not biz_id.isdigit():
        return False
    try:
        import json
        from app.models import AaStudentCorrection
        from app.core.affairs_security import build_affairs_context
        correction = db.scalar(select(AaStudentCorrection).where(
            AaStudentCorrection.id == int(biz_id),
            AaStudentCorrection.tenant_id == file_obj.tenant_id,
            AaStudentCorrection.is_deleted.is_(False),
        ))
        if not correction or str(file_obj.id) not in [str(value) for value in json.loads(correction.material_file_ids or "[]")]:
            return False
        if not any(
            not item.is_deleted and item.is_current and item.status == "ACTIVE"
            and item.tenant_id == file_obj.tenant_id and item.file_id == file_obj.id
            and item.biz_type == "AA_STUDENT_CORRECTION" and str(item.biz_id) == biz_id
            and item.subject_type == "STUDENT" and str(item.subject_id) == str(correction.student_id)
            and item.student_id == correction.student_id
            for item in bindings
        ):
            return False
        build_affairs_context(user, db).require_student(db, correction.student_id)
        return True
    except Exception:
        return False


ARCHIVE_FILE_TYPES = {"ARCHIVE_PACKAGE", "ARCHIVE_BATCH_PACKAGE"}


def _frozen_members_allow(db, package, payload, user, tenant_id):
    from app.modules.internship.services import internship_material_center_service as core
    from app.modules.internship.services.internship_scope import apply_internship_record_scope
    from app.models import InternshipRecord
    batch = package.package_type == "ARCHIVE_BATCH"
    records = payload.get("records") if batch else [payload]
    if not isinstance(records, list) or not records or len(records) != int(package.row_count or 0):
        return False
    if (batch and (len(records) > 20 or int(package.target_id) != int(package.batch_id or 0)
                   or str(payload.get("batchId")) != str(package.target_id)
                   or int(payload.get("rowCount") or 0) != len(records)
                   or int(payload.get("fileCount") or 0) != int(package.file_count or 0))):
        return False
    if not batch and int(package.row_count or 0) != 1:
        return False
    seen_records, count = set(), 0
    for entry in records:
        record = core._assert_scope(db, entry.get("internshipId"), user, "下载归档材料")
        scoped = apply_internship_record_scope(select(InternshipRecord.id).where(
            InternshipRecord.tenant_id == tenant_id, InternshipRecord.id == record.id,
            InternshipRecord.is_deleted.is_(False)), user)
        if not db.scalar(scoped):
            return False
        if (record.id in seen_records or int(record.batch_id or 0) != int(package.batch_id or 0)
                or str(entry.get("studentId")) != str(record.student_id)
                or (not batch and record.id != package.target_id)):
            return False
        seen_records.add(record.id)
        archived = db.scalar(select(InternshipArchive).where(
            InternshipArchive.tenant_id == tenant_id,
            InternshipArchive.internship_id == record.id,
            InternshipArchive.student_id == record.student_id,
            InternshipArchive.status == "ARCHIVED",
            InternshipArchive.is_deleted.is_(False),
        ))
        manifest = db.scalar(select(ArchiveManifest).where(
            ArchiveManifest.id == int(entry.get("manifestId") or 0),
            ArchiveManifest.tenant_id == tenant_id,
            ArchiveManifest.module_code == core.MODULE_CODE,
            ArchiveManifest.archive_type == core.ARCHIVE_TYPE,
            ArchiveManifest.target_type == core.TARGET_TYPE,
            ArchiveManifest.target_id == str(record.id),
            ArchiveManifest.status.in_(("FROZEN", "PACKAGED")),
            ArchiveManifest.is_deleted.is_(False),
        ))
        if (not archived or not manifest or int(entry.get("manifestRevision") or 0) != manifest.revision
                or entry.get("manifestSha256") != manifest.manifest_sha256):
            return False
        frozen = list(db.scalars(select(ArchiveManifestItem).where(
            ArchiveManifestItem.tenant_id == tenant_id,
            ArchiveManifestItem.manifest_id == manifest.id,
            ArchiveManifestItem.is_deleted.is_(False),
        ).order_by(ArchiveManifestItem.sort_no, ArchiveManifestItem.id)).all())
        entries = entry.get("items")
        if (not frozen or not isinstance(entries, list) or len(entries) != len(frozen)
                or core.manifest_digest(manifest, frozen) != manifest.manifest_sha256):
            return False
        expected = {(str(x.version_id), str(x.asset_id), str(x.file_object_id), x.sha256_snapshot,
                     int(x.size_snapshot or 0), x.material_code) for x in frozen}
        actual = {(str(x.get("versionId")), str(x.get("assetId")), str(x.get("fileObjectId")),
                   x.get("sha256"), int(x.get("sizeBytes") or 0), x.get("materialCode")) for x in entries}
        if len(actual) != len(entries) or actual != expected:
            return False
        versions = {v.id: (v, f) for v, f in db.execute(select(FileVersion, FileObject).join(
            FileObject, FileObject.id == FileVersion.file_object_id,
        ).where(
            FileVersion.tenant_id == tenant_id, FileObject.tenant_id == tenant_id,
            FileVersion.id.in_([x.version_id for x in frozen]),
            FileVersion.is_deleted.is_(False), FileObject.is_deleted.is_(False),
        )).all()}
        for item in frozen:
            pair = versions.get(item.version_id)
            if not pair:
                return False
            version, source = pair
            if (version.asset_id != item.asset_id or version.file_object_id != item.file_object_id
                    or version.status not in core.READY_VERSION_STATUS or not core._file_ready(source)
                    or source.sha256 != item.sha256_snapshot
                    or int(source.size_bytes or 0) != int(item.size_snapshot or 0)):
                return False
        count += len(entries)
    if count != int(package.file_count or 0):
        return False
    if batch:
        return package.included_items == [
            {"internshipId": x["internshipId"], "manifestId": x["manifestId"]} for x in records]
    return package.included_items == payload.get("items")


def authorize_archive_package(db, file_obj, bindings, user, action):
    """Fixed frozen members authorize packages before any uploader fallback."""
    if db is None or action not in {"meta", "download", "preview"} or not has_permission(user, "internship.archive.package"):
        return False
    tenant_id = int(current_tenant_id() or 0)
    packages = list(db.scalars(select(InternshipEvidencePackage).where(
        InternshipEvidencePackage.tenant_id == tenant_id,
        InternshipEvidencePackage.package_file_id == str(file_obj.id),
        InternshipEvidencePackage.package_type.in_(("ARCHIVE", "ARCHIVE_BATCH")),
        InternshipEvidencePackage.is_deleted.is_(False),
    ).limit(2)).all())
    if len(packages) != 1:
        return False
    package = packages[0]
    batch = package.package_type == "ARCHIVE_BATCH"
    biz_type = "ARCHIVE_BATCH_PACKAGE" if batch else "ARCHIVE_PACKAGE"
    biz_id = f"{package.package_type}:{package.target_id}"
    if (package.status != "READY" or package.invalidated_at or package.missing_items
            or file_obj.biz_type != biz_type or str(file_obj.biz_id) != biz_id
            or file_obj.sha256 != package.package_sha256
            or int(file_obj.size_bytes or 0) != int(package.package_size_bytes or 0)
            or not any(b.tenant_id == tenant_id and b.file_id == file_obj.id and not b.is_deleted
                       and b.status == "ACTIVE" and b.is_current and b.biz_type == biz_type
                       and str(b.biz_id) == biz_id for b in bindings)):
        return False
    payload = package.manifest_json
    schema = "INTERNSHIP_ARCHIVE_BATCH_FILE_VERSION_V1" if batch else "INTERNSHIP_ARCHIVE_PACKAGE_FILE_VERSION_V2"
    if (not isinstance(payload, dict) or payload.get("schemaVersion") != schema
            or str(payload.get("tenantId")) != str(tenant_id)
            or str(payload.get("packageFileId")) != str(file_obj.id)
            or payload.get("packageSha256") != package.package_sha256
            or int(payload.get("packageSizeBytes") or 0) != int(package.package_size_bytes or 0)
            or (batch and (str(payload.get("packageId")) != str(package.id)
                           or int(payload.get("packageVersion") or 0) != package.package_version))):
        return False
    # Bind scope metadata to the actual immutable ZIP manifest. Editing stored
    # records/included_items together must not splice a different member list.
    import json
    import zipfile
    from app.services.storage import get_backend
    path = get_backend().fetch_local(file_obj.file_key)
    if path is None or not path.is_file():
        return False
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)) or len(names) != int(package.file_count or 0) + 1:
            return False
        info = archive.getinfo("manifest.json")
        if info.file_size > (8 if batch else 2) * 1024 * 1024:
            return False
        embedded = json.loads(archive.read(info).decode("utf-8"))
    envelope = {"packageId", "packageFileId", "packageSha256", "packageSizeBytes"}
    if embedded != {k: v for k, v in payload.items() if k not in envelope}:
        return False
    return _frozen_members_allow(db, package, payload, user, tenant_id)


def require_archive_package_file(db, package, user):
    from app.services.file_access_service import _load_file_and_bindings, authorize_file_object
    file_obj, bindings = _load_file_and_bindings(db, int(current_tenant_id() or 0), int(package.package_file_id or 0))
    if (not file_obj or file_obj.biz_type not in ARCHIVE_FILE_TYPES
            or not authorize_file_object(file_obj, bindings, user or {}, "download", db=db)):
        raise not_found("归档包不存在或不可下载")
    return file_obj


def resolve_authorized_archive_download(db, package, user):
    """Same authority for dedicated package routes; stream-check bytes too."""
    from app.services.storage import get_backend
    from app.services.streaming_archive_service import sha256_path
    file_obj = require_archive_package_file(db, package, user)
    path = get_backend().fetch_local(file_obj.file_key)
    digest, size = sha256_path(path)
    if digest != package.package_sha256 or size != int(package.package_size_bytes or 0):
        raise AppException("FILE_INTEGRITY_ERROR", "归档包完整性校验失败，请联系学校管理员", http_status=409)
    return path, file_obj.file_name

