"""ORM 模型聚合（第一批 19 张核心表，表名以冻结册 t_ 前缀为准）。"""
from app.models.base import Base  # noqa: F401
from app.models.tenant import Tenant, TenantBrandConfig  # noqa: F401
from app.models.org import College, Major, SchoolClass  # noqa: F401
from app.models.rbac import Permission, Role, RolePermission, User, UserRole, WxAccountBinding  # noqa: F401
from app.models.student import StudentContact, StudentImportBatch, StudentProfile, StudentStageEvent  # noqa: F401
from app.models.student_parent import StudentParentLink  # noqa: F401  (学生PC门户·家长授权代理)
from app.models.portal_otp import PortalLoginOtp  # noqa: F401  (学生PC门户·登录验证码)
from app.models.portal_sign import PortalSignRecord  # noqa: F401  (学生PC门户·电子签署留痕)
from app.models.approval import (UnifiedTodo, WorkflowDefinition, WorkflowInstance,  # noqa: F401
                                 WorkflowNodeDefinition, WorkflowTask)
from app.models.message import (  # noqa: F401
    MessageAttachment,
    MessageAudience,
    MessageCampaign,
    MessageDeliveryJob,
    MessageEventOutbox,
    UnifiedMessage,
)
from app.models.notification_preference import NotificationPreference  # noqa: F401
from app.models.user_preference import UserPreference  # noqa: F401
from app.models.audit import ExportTask, SecurityAuditLog  # noqa: F401
from app.models.system_config import DataScopeRule, MenuNode, SysConfig  # noqa: F401  (系统管理·可编辑配置)
from app.models.system_governance import SystemJsonDoc  # noqa: F401  (系统管理·治理 JSON 文档)
from app.models.file import FileObject  # noqa: F401
from app.models.platform import PlatformConfig, PlatformNotice, PlatformOrder  # noqa: F401
from app.models.internship import (AttendanceException, InternshipAgreement,  # noqa: F401
                                    InternshipArchive, InternshipAuditTrail, InternshipBatch,
                                    InternshipBatchPlan, InternshipChangeRequest,
                                    InternshipCheckin, InternshipEnterpriseEval,
                                    InternshipFinalScore, InternshipGuidance, InternshipInsurance,
                                    InternshipLeave, InternshipMakeup, InternshipPlanAck,
                                    InternshipPlanTaskProgress, InternshipProcessReport,
                                    InternshipRecord, InternshipScoreConfig,
                                    InternshipCommunicationLog, InternshipComplaint,
                                    InternshipStudentEval, InternshipVisit, InternshipVisitPlan,
                                    RiskRecord, WeeklyReport)
from app.models.internship_position import InternshipPosition  # noqa: F401  (岗位库·独立文件)
from app.models.internship_match import InternshipApplication, InternshipIntention, InternshipMatch  # noqa: F401  (岗位匹配/申请)
from app.models.excel_import_job import ExcelImportJob  # noqa: F401  (公共 Excel 底座·通用导入记录)
from app.models.identity_import_batch import IdentityImportBatch  # noqa: F401
from app.models.shared_import_batch import SharedImportBatch  # noqa: F401
from app.models.internship_agreement_template import InternshipAgreementTemplate  # noqa: F401  (实习协议模板库·独立文件)
from app.models.orientation import (GreenChannelApplication, OrientationArchive,  # noqa: F401
                                     OrientationAuditTrail, OrientationBatch,
                                     OrientationCheckinPoint, OrientationException,
                                     OrientationExceptionFollowup, OrientationFlowConfig,
                                     OrientationMaterial, OrientationNoticeTask,
                                     OrientationStudent)
from app.models.campus_service import (CsAuditTrail, CsDiscipline, CsDormException,  # noqa: F401
                                        CsDormRecord, CsGrant, CsLeave, CsMentalRecord,
                                        CsServiceStudent, CsWorkOrder)
from app.models.academic import (AcademicAuditTrail, AcademicGrade, AcademicIntervention,  # noqa: F401
                                    AcademicMakeup, AcademicRetake, AcademicStudent, AcademicWarning)
from app.models.graduation import (GraduationArchiveRecord, GraduationAuditTrail,  # noqa: F401
                                      GraduationBatch, GraduationDefenseGroup, GraduationDefenseScore,
                                      GraduationFinal, GraduationGrade, GraduationGuidance,
                                      GraduationDefenseExpert, GraduationGradeAppeal,
                                      GraduationMentor, GraduationMentorAssignment,
                                      GraduationMentorEval, GraduationMidterm, GraduationPeerReview,
                                      GraduationPlagiarismCheck, GraduationProposal, GraduationReview,
                                      GraduationRiskCase,
                                      GraduationStudent, GraduationStudentEval, GraduationGuidancePlan,
                                      GraduationTaskBook, GraduationTemplate,
                                      GraduationTopic, GraduationTopicChangeRequest,
                                      GraduationTopicChoice, GraduationTopicRound)
from app.models.employment import (EmpAuditTrail, EmpCompany, EmpFollowup,  # noqa: F401
                                     EmpJob, EmpMaterial, EmpStudent,
                                     InternshipEnterpriseContact)
from app.models.teacher_scope import TeacherStudentScope  # noqa: F401
from app.models.affairs import (AffairsAuditTrail, AffairsClassCadre,  # noqa: F401
                                AffairsLeaveCancelRecord, AffairsLeaveExtension)
from app.models.affairs_class import (AffairsClassMaterial,  # noqa: F401
                                      AffairsCounselorAssessment,
                                      AffairsCounselorAssessmentPeriod)
from app.models.affairs_aid import (AidApply, AidBatch, AidFamilyEconomy,  # noqa: F401
                                    AidLevelHistory, AidObjection, FundingAppeal,
                                    FundingApplication,
                                    FundingBatch, FundingDisbursement, FundingProject)
from app.models.affairs_discipline import (AffairsRiskHandle,  # noqa: F401
                                           AffairsRiskRecord, DisciplineAppeal,
                                           DisciplineCase, DisciplineRemoveApply)
from app.models.affairs_talk import (FamilyContactLog, TalkPlan,  # noqa: F401
                                     TalkRecord)
from app.models.affairs_mental import PsyReferral  # noqa: F401
from app.models.affairs_psy_survey import PsySurveySubmission  # noqa: F401  (心理健康自评·独立新文件)
from app.models.affairs_dorm import (DormBed, DormBuilding,  # noqa: F401
                                     DormCheckRecord, DormCheckTask, DormRoom,
                                     DormTransfer)
from app.models.affairs_archive import ArchiveBatch, ArchivePackage  # noqa: F401
from app.models.affairs_activity import (AffairsActivity,  # noqa: F401
                                         AffairsActivityCredit,
                                         AffairsActivitySignup,
                                         AffairsCreditAppeal,
                                         AffairsCreditCategory,
                                         AffairsVolunteerRecord)
from app.models.affairs_attachment import AffairsAttachment  # noqa: F401
from app.models.affairs_club import (AffairsClub,  # noqa: F401
                                     AffairsClubAnnualReview,
                                     AffairsClubMember)
from app.models.affairs_org import (AffairsOrgPosition,  # noqa: F401
                                    AffairsStudentOrg)
from app.models.affairs_league import (AffairsLeagueDev,  # noqa: F401
                                       AffairsLeagueDevStage)
from app.models.affairs_counselor_eval import (CounselorEval,  # noqa: F401
                                               CounselorEvalIndicator)
from app.models.affairs_funding_ext import (FeeReduction,  # noqa: F401
                                            StudentLoan, WorkStudyMonthly,
                                            WorkStudyPost, WorkStudyRecord)
from app.models.academic_affairs import (AaArchiveBatch,  # noqa: F401
                                         AaArchiveItem, AaAttendanceSession,
                                         AaCalendarEvent,
                                         AaClassAdjustmentRequest, AaClassTimeBand,
                                         AaClassroom, AaClassroomBooking,
                                         AaCourse, AaCourseMaterial, AaDeferredExam,
                                         AaLabResource, AaEquipment,
                                         AaLabBooking, AaResourceRepair,
                                         AaMajorDirection,
                                         AaEvaluationAppeal, AaEvaluationBatch,
                                         AaEvaluationRecord, AaEvaluationResult,
                                         AaEvaluationTask, AaExemption,
                                         AaExamAuditTrail, AaExamBatch,
                                         AaMakeupBatch, AaRetakeApply,
                                         AaExamCourse, AaExamIncident,
                                         AaExamInvigilator, AaExamPatrol,
                                         AaExamRoom, AaExamRoomStudent,
                                         AaGradeRecheck, AaWorkloadDeclaration,
                                         AaGradeRecord, AaGradeTask,
                                         AaGraduationAuditBatch,
                                         AaGraduationAuditResult, AaProgram,
                                         AaProgramBinding, AaProgramCourse,
                                         AaProgramGraduationRequirement,
                                         AaProgramPracticeSegment,
                                         AaQualityRecord, AaQualityRectification,
                                         AaRegistration, AaRegistrationBatch,
                                         AaRegistrationDeferral,
                                         AaRegistrationException,
                                         AaScheduleBatch, AaScheduleChange,
                                         AaScheduleItem, AaSchedulePublish,
                                         AaScheduleRule,
                                         AaSelectionBatch,
                                         AaTeacherAvailability,
                                         AaGradeRecognition, AaGraduationCertificate,
                                         AaLevelExam, AaLevelExamReg,
                                         AaMajorSplitBatch, AaMajorSplitOption,
                                         AaMajorSplitVolunteer,
                                         AaSelectionCourse, AaSelectionRecord,
                                         AaSelectionRound,
                                         AaStatusChange, AaStudentCorrection,
                                         AaTeachingTask,
                                         AaTeachingTaskBatch, AaTerm,
                                         AaTextbook, AaTextbookDistributionBatch,
                                         AaTextbookDistributionRecord,
                                         AaTextbookFeeLedger, AaTextbookOrderBatch,
                                         AaTextbookOrderItem, AaTextbookReviewBatch,
                                         AaTextbookReviewBatchItem,
                                         AaTextbookSelection, AaTimeSlot)
from app.models.notification import NotificationLog, NotificationTask, NotificationTemplate  # noqa: F401
from app.models.workbench import RoleWorkbenchConfig  # noqa: F401
from app.models.auth_token import AuthBlockedJti, AuthRefreshToken  # noqa: F401
from app.models.portal import TenantPortalConfig  # noqa: F401
from app.models.sandbox import SandboxBaseline  # noqa: F401
from app.models.feedback import Feedback  # noqa: F401  (帮助与反馈·独立新文件)
from app.models.system_implementation import (SystemImplementationCheck,  # noqa: F401
                                               SystemBusinessRelationBatch,
                                               SystemBusinessRelationInstallItem,
                                               SystemImplementationProject,
                                               SystemImplementationSection,
                                               SystemPresetInstallation)
from app.models.national_standard import (NationalMajorCatalog,  # noqa: F401
                                          NationalStandardDocument,
                                          NationalStandardSection,
                                          NationalStandardSource,
                                          SchoolMajorStandardBinding)
