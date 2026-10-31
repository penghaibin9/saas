"""招标新增实习文件类型接入公共文件中心的业务授权注册表。"""
from importlib import import_module

from sqlalchemy import select

from app.core.permissions import has_permission
from app.services.file_access_service import register_file_resolver

_DOMAIN_RESOLVERS = {
    'INTERNSHIP_PLAN': ('internship_plan_service', 'authorize_plan_file'),
    'INTERNSHIP_VISIT': ('internship_visit_service', 'authorize_visit_file'),
    'INTERNSHIP_GUIDANCE': ('internship_guidance_service', 'authorize_guidance_file'),
    'INTERNSHIP_LEAVE': ('internship_leave_service', 'authorize_leave_file'),
    'INTERNSHIP_NOTICE': ('internship_teacher_activity_service', 'authorize_notice_file'),
    'INTERNSHIP_EMPLOYMENT': ('internship_employment_service', 'authorize_employment_file'),
    'INTERNSHIP_TEACHER_PERIOD_REPORT': ('internship_teacher_activity_service', 'authorize_teacher_period_file'),
    'INTERNSHIP_TEACHER_CHECKIN': ('internship_teacher_activity_service', 'authorize_teacher_checkin_file'),
    'INTERNSHIP_CHECKIN': ('internship_checkin_evidence_service', 'authorize_student_evidence'),
    'INTERNSHIP_CHECKIN_EXEMPTION': ('internship_checkin_evidence_service', 'authorize_student_evidence'),
    'INTERNSHIP_FEEDBACK': ('internship_student_feedback_service', 'authorize_feedback_file'),
    'INTERNSHIP_MAKEUP': ('internship_makeup_service', 'authorize_makeup_file'),
    'INTERNSHIP_APPLICATION_EVIDENCE': ('internship_application_service', 'authorize_application_file'),
    'INTERNSHIP_APPLICATION_AGREEMENT': ('internship_application_service', 'authorize_application_file'),
}


@register_file_resolver('INTERNSHIP_REPORT', 'INTERNSHIP_WEEKLY_REPORT', 'INTERNSHIP_REPORT_HISTORY')
def process_report_file(db, file_obj, bindings, user, action):
    from app.services.file_public_acl_guard import strict_scoped_binding_resolver
    if str(user.get('userType') or '').upper() != 'STUDENT' and not has_permission(user, 'internship.report.view'):
        return False
    return strict_scoped_binding_resolver(db, file_obj, bindings, user, action)


@register_file_resolver(*_DOMAIN_RESOLVERS)
def domain_evidence(db, file_obj, bindings, user, action):
    module, function = _DOMAIN_RESOLVERS[str(file_obj.biz_type).upper()]
    try:
        service = import_module('app.modules.internship.services.' + module)
        return bool(getattr(service, function)(db, file_obj, bindings, user or {}, action))
    except Exception:
        return False


@register_file_resolver('COMPLIANCE_EVIDENCE')
def compliance_package(db, file_obj, bindings, user, action):
    from app.modules.internship.services.internship_evidence_package_service import authorize_package_file
    if db is None or action not in {'meta', 'preview', 'download'}:
        return False
    try:
        return bool(authorize_package_file(db, file_obj, user or {}))
    except Exception:
        return False


@register_file_resolver('INTERNSHIP_MATERIAL_TEMPLATE')
def material_template(db, file_obj, bindings, user, action):
    if db is None or action not in {'meta', 'preview', 'download'}:
        return False
    from app.models import InternshipMaterialRequirement, InternshipMaterialTemplateVersion, InternshipRecord
    from app.modules.internship.services.internship_material_requirement_service import _applies, _scoped_student_query
    from app.services.mobile_student_service import resolve_student
    try:
        template = db.scalar(select(InternshipMaterialTemplateVersion).where(
            InternshipMaterialTemplateVersion.tenant_id == file_obj.tenant_id,
            InternshipMaterialTemplateVersion.file_id == file_obj.id,
            InternshipMaterialTemplateVersion.status.in_(('ACTIVE', 'SUPERSEDED')),
            InternshipMaterialTemplateVersion.is_deleted.is_(False)))
        requirement = db.get(InternshipMaterialRequirement, template.requirement_id) if template else None
        if not requirement or requirement.is_deleted or requirement.tenant_id != file_obj.tenant_id:
            return False
        if template.sha256_snapshot != file_obj.sha256 or not any(
            b.tenant_id == file_obj.tenant_id and not b.is_deleted and b.status == 'ACTIVE'
            and b.biz_type == 'INTERNSHIP_MATERIAL_TEMPLATE' and str(b.biz_id) == str(requirement.id)
            and b.file_id == file_obj.id for b in bindings
        ):
            return False
        if str(user.get('userType') or '').upper() == 'STUDENT':
            student = resolve_student(db, user)
            return bool(student and requirement.status == 'PUBLISHED' and _applies(requirement, student)
                        and db.scalar(select(InternshipRecord.id).where(
                            InternshipRecord.tenant_id == file_obj.tenant_id,
                            InternshipRecord.student_id == student.id,
                            InternshipRecord.batch_id == requirement.batch_id,
                            InternshipRecord.is_deleted.is_(False)).limit(1)))
        if not any(has_permission(user, code) for code in (
            'internship.archive.view', 'internship.student.material.view', 'internship.material.manage',
        )):
            return False
        return bool(db.scalar(_scoped_student_query(requirement, user).with_only_columns(
            InternshipRecord.id, maintain_column_froms=True).limit(1)))
    except Exception:
        return False


@register_file_resolver('INTERNSHIP_CUSTOM_MATERIAL', 'INTERNSHIP_PAYROLL_VERSION')
def student_material(db, file_obj, bindings, user, action):
    if db is None or action not in {'meta', 'preview', 'download', 'archive'}:
        return False
    from app.models import InternshipRecord, InternshipMaterialSubmissionFile, InternshipMaterialSubmission
    from app.models import InternshipPayrollVersion, InternshipPayrollStatement
    from app.models.file import FileVersion
    from app.services.mobile_student_service import resolve_student
    from app.modules.internship.services.internship_scope import assert_internship_record_scope
    try:
        payroll = file_obj.biz_type == 'INTERNSHIP_PAYROLL_VERSION'
        if payroll:
            version = db.scalar(select(InternshipPayrollVersion).where(
                InternshipPayrollVersion.tenant_id == file_obj.tenant_id,
                InternshipPayrollVersion.evidence_file_id == file_obj.id,
                InternshipPayrollVersion.is_deleted.is_(False)))
            business = db.get(InternshipPayrollStatement, version.statement_id) if version else None
            correct_binding = (version and str(file_obj.biz_id) == str(version.id)
                               and version.evidence_sha256 == file_obj.sha256)
            permission = 'internship.payroll.view'
        else:
            version = db.scalar(select(InternshipMaterialSubmissionFile).join(
                FileVersion, FileVersion.asset_id == InternshipMaterialSubmissionFile.asset_id).where(
                InternshipMaterialSubmissionFile.tenant_id == file_obj.tenant_id,
                FileVersion.tenant_id == file_obj.tenant_id,
                FileVersion.file_object_id == file_obj.id,
                FileVersion.is_deleted.is_(False)))
            business = db.get(InternshipMaterialSubmission, version.submission_id) if version else None
            correct_binding = version and str(file_obj.biz_id) == f'{version.submission_id}:{version.slot_no}'
            permission = 'internship.student.material.view'
        if not business or business.is_deleted or business.tenant_id != file_obj.tenant_id or not correct_binding:
            return False
        record = db.get(InternshipRecord, business.internship_id)
        if not record or record.is_deleted or record.tenant_id != file_obj.tenant_id:
            return False
        if not any(b.tenant_id == file_obj.tenant_id and not b.is_deleted
                   and b.status in {'ACTIVE', 'SUPERSEDED', 'ARCHIVED'}
                   and b.biz_type == file_obj.biz_type and str(b.biz_id) == str(file_obj.biz_id)
                   and b.file_id == file_obj.id for b in bindings):
            return False
        if str(user.get('userType') or '').upper() == 'STUDENT':
            student = resolve_student(db, user)
            return bool(student and student.id == record.student_id)
        if not has_permission(user, permission):
            return False
        assert_internship_record_scope(db, record.id, user, '查看实习材料')
        return True
    except Exception:
        return False


@register_file_resolver('INTERNSHIP_FORMAL_DOCUMENT')
def formal_document(db, file_obj, bindings, user, action):
    if db is None or action not in {'meta', 'preview', 'download', 'archive'}:
        return False
    from app.models import InternshipFormalDocument
    from app.services.mobile_student_service import resolve_student
    from app.modules.internship.services.internship_scope import assert_internship_record_scope
    try:
        if not _retained_binding(file_obj, bindings):
            return False
        row = db.scalar(select(InternshipFormalDocument).where(
            InternshipFormalDocument.tenant_id == file_obj.tenant_id,
            InternshipFormalDocument.file_id == str(file_obj.id),
            InternshipFormalDocument.is_deleted.is_(False),
            InternshipFormalDocument.status.in_(('GENERATED', 'SUPERSEDED'))))
        if not row or str(file_obj.biz_id) != str(row.id) or row.file_sha256 != file_obj.sha256:
            return False
        if str(user.get('userType') or '').upper() == 'STUDENT':
            student = resolve_student(db, user)
            return bool(student and student.id == row.student_id)
        if not has_permission(user, 'internship.archive.view'):
            return False
        assert_internship_record_scope(db, row.internship_id, user, '读取正式实习文书')
        return True
    except Exception:
        return False


@register_file_resolver('INTERNSHIP_TEACHER_MAKEUP', 'INTERNSHIP_TEACHER_WORK_REPORT')
def teacher_work_evidence(db, file_obj, bindings, user, action):
    if db is None or action not in {'meta', 'preview', 'download', 'archive'}:
        return False
    from app.models import InternshipTeacherMakeup, InternshipTeacherWorkReport
    from app.modules.internship.services.internship_identity import stable_user_id
    from app.modules.internship.services.internship_teacher_activity_service import _scope_mode, _assert_teacher_batch_scope
    try:
        is_makeup = file_obj.biz_type == 'INTERNSHIP_TEACHER_MAKEUP'
        model = InternshipTeacherMakeup if is_makeup else InternshipTeacherWorkReport
        raw_id = str(file_obj.biz_id or '')
        if not raw_id.isdigit():
            return False
        row = db.get(model, int(raw_id))
        if not row or row.is_deleted or row.tenant_id != file_obj.tenant_id:
            return False
        file_ids = [row.evidence_file_id] if is_makeup else row.attachment_file_ids_json or []
        if str(file_obj.id) not in {str(value) for value in file_ids} or not any(
            b.tenant_id == file_obj.tenant_id and not b.is_deleted and b.status == 'ACTIVE'
            and b.biz_type == file_obj.biz_type and str(b.biz_id) == raw_id and b.file_id == file_obj.id
            for b in bindings
        ):
            return False
        if _scope_mode(user) == 'ADMIN_TENANT':
            return has_permission(user, 'internship.stats.view')
        if row.teacher_user_id != stable_user_id(user) or not has_permission(user, 'internship.guidance.view'):
            return False
        _assert_teacher_batch_scope(db, row.batch_id, user)
        return True
    except Exception:
        return False


@register_file_resolver('INTERNSHIP_REGULATORY_TEMPLATE', 'INTERNSHIP_REGULATORY_ERROR', 'INTERNSHIP_REGULATORY_EXPORT')
def regulatory_file(db, file_obj, bindings, user, action):
    if db is None or action not in {'meta', 'preview', 'download'}:
        return False
    from app.models import InternshipRegulatoryTemplateVersion, InternshipRegulatoryTask
    from app.modules.internship.services.internship_student_service import _current_scope
    try:
        if not _retained_binding(file_obj, bindings):
            return False
        if _current_scope(user).get('mode') != 'ADMIN_TENANT':
            return False
        if not has_permission(user, 'internship.reporting.view'):
            return False
        if file_obj.biz_type == 'INTERNSHIP_REGULATORY_TEMPLATE':
            row = db.scalar(select(InternshipRegulatoryTemplateVersion).where(
                InternshipRegulatoryTemplateVersion.tenant_id == file_obj.tenant_id,
                InternshipRegulatoryTemplateVersion.source_file_id == file_obj.id,
                InternshipRegulatoryTemplateVersion.is_deleted.is_(False)))
            return bool(row and str(file_obj.biz_id) == str(row.id) and row.source_file_sha256 == file_obj.sha256)
        if not has_permission(user, 'internship.reporting.export'):
            return False
        output = file_obj.biz_type == 'INTERNSHIP_REGULATORY_EXPORT'
        file_field = InternshipRegulatoryTask.output_file_id if output else InternshipRegulatoryTask.error_file_id
        row = db.scalar(select(InternshipRegulatoryTask).where(
            InternshipRegulatoryTask.tenant_id == file_obj.tenant_id, file_field == file_obj.id,
            InternshipRegulatoryTask.is_deleted.is_(False)))
        return bool(row and str(file_obj.biz_id) == str(row.id)
                    and (row.output_sha256 if output else row.error_sha256) == file_obj.sha256)
    except Exception:
        return False


def _retained_binding(file_obj, bindings):
    return any(b.tenant_id == file_obj.tenant_id and not b.is_deleted
               and b.status in {'ACTIVE', 'SUPERSEDED', 'ARCHIVED'}
               and b.biz_type == file_obj.biz_type and str(b.biz_id) == str(file_obj.biz_id)
               and b.file_id == file_obj.id for b in bindings)
