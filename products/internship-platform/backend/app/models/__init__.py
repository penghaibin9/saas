"""岗位实习 Standalone 最小模型出口。

禁止复制原 SaaS 全量 models/__init__.py；这里只暴露岗位实习及其最小公共底座。
"""

from app.models.tenant import Tenant
from app.models.org import College, Major, SchoolClass
from app.models.rbac import Permission, Role, RolePermission, User, UserRole
from app.models.student import StudentContact, StudentProfile
from app.models.student_account_link import StudentAccountLink
from app.models.student_parent import StudentParentLink
from app.models.teacher_scope import TeacherStudentScope
from app.models.message import MessageCampaign, MessageEventOutbox, UnifiedMessage
from app.models.approval import UnifiedTodo
from app.models.audit_outbox import AuditOutbox
from app.models.excel_import_job import ExcelImportJob
from app.models.file import (
    ArchiveManifest, ArchiveManifestItem, FileAsset, FileBinding, FileObject, FileVersion,
)
from app.models.enterprise import EmpCompany, InternshipEnterpriseContact

from app.models.internship import (
    AttendanceException, InternshipAgreement, InternshipArchive, InternshipAuditTrail,
    InternshipBatch, InternshipBatchParticipant, InternshipBatchPlan, InternshipBatchScopeRule,
    InternshipChangeRequest, InternshipCheckin, InternshipCheckinExemption, InternshipCommunicationLog, InternshipComplaint,
    InternshipEnterpriseEval, InternshipFinalScore, InternshipGuidance, InternshipInsurance,
    InternshipLeave, InternshipMakeup, InternshipPlanAck, InternshipPlanTaskProgress,
    InternshipProcessReport, InternshipRecord, InternshipScoreConfig, InternshipStudentEval,
    InternshipVisit, InternshipVisitPlan, RiskRecord, WeeklyReport,
)
from app.models.internship_agreement_template import InternshipAgreementTemplate
from app.models.internship_application_material_snapshot import InternshipApplicationMaterialSnapshot
from app.models.internship_compliance import (
    InternshipComplianceExemption, InternshipComplianceTemplate, InternshipConsent,
    InternshipEmergencyPlan, InternshipEnterpriseInspection, InternshipEvidencePackage,
    InternshipIncident, InternshipRemunerationRecord, InternshipSafetyCompletion,
    InternshipSafetyCourse, InternshipSpecialFiling,
)
from app.models.internship_enterprise_application_decision import InternshipEnterpriseApplicationDecision
from app.models.internship_enterprise_portal import (
    InternshipCampaignEnterprise, InternshipEnterpriseAccessGrant,
    InternshipEnterpriseMember, InternshipRecruitmentCampaign,
)
from app.models.internship_match import InternshipApplication, InternshipIntention, InternshipMatch
from app.models.internship_material_requirement import (
    InternshipMaterialRequirement,
    InternshipMaterialSubmission,
    InternshipMaterialSubmissionFile,
    InternshipMaterialTemplateVersion,
)
from app.models.internship_rotation_payroll import (
    InternshipPayrollStatement,
    InternshipPayrollVersion,
    InternshipRotation,
    InternshipRotationProject,
)
from app.models.internship_placement_snapshot import InternshipPlacementSnapshot
from app.models.internship_position import InternshipPosition
from app.models.internship_student_profile import StudentInternshipProfile, StudentInternshipProfileItem
from app.models.internship_volunteer_group import InternshipVolunteerGroup

from app.models.internship_score_appeal import InternshipScoreAppeal
