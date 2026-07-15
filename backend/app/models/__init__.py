"""ORM 模型聚合（第一批 19 张核心表，表名以冻结册 t_ 前缀为准）。"""
from app.models.base import Base  # noqa: F401
from app.models.tenant import Tenant, TenantBrandConfig  # noqa: F401
from app.models.org import College, Major, SchoolClass  # noqa: F401
from app.models.rbac import Permission, Role, RolePermission, User, UserRole  # noqa: F401
from app.models.student import StudentContact, StudentImportBatch, StudentProfile, StudentStageEvent  # noqa: F401
from app.models.approval import UnifiedTodo, WorkflowInstance, WorkflowTask  # noqa: F401
from app.models.message import UnifiedMessage  # noqa: F401
from app.models.notification_preference import NotificationPreference  # noqa: F401
from app.models.audit import ExportTask, SecurityAuditLog  # noqa: F401
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
                                      GraduationStudent, GraduationTaskBook, GraduationTemplate,
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
                                    AidLevelHistory, AidObjection, FundingApplication,
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
                                         AaMajorDirection,
                                         AaEvaluationAppeal, AaEvaluationBatch,
                                         AaEvaluationRecord, AaEvaluationResult,
                                         AaEvaluationTask, AaExemption,
                                         AaExamAuditTrail, AaExamBatch,
                                         AaMakeupBatch, AaRetakeApply,
                                         AaExamCourse, AaExamIncident,
                                         AaExamInvigilator, AaExamPatrol,
                                         AaExamRoom, AaExamRoomStudent,
                                         AaGradeRecord, AaGradeTask,
                                         AaGraduationAuditBatch,
                                         AaGraduationAuditResult, AaProgram,
                                         AaProgramBinding, AaProgramCourse,
                                         AaProgramGraduationRequirement,
                                         AaRegistration, AaRegistrationBatch,
                                         AaRegistrationDeferral,
                                         AaRegistrationException,
                                         AaScheduleBatch, AaScheduleChange,
                                         AaScheduleItem, AaSchedulePublish,
                                         AaScheduleRule,
                                         AaSelectionBatch,
                                         AaTeacherAvailability,
                                         AaSelectionCourse, AaSelectionRecord,
                                         AaStatusChange, AaTeachingTask,
                                         AaTeachingTaskBatch, AaTerm,
                                         AaTextbook, AaTextbookDistributionBatch,
                                         AaTextbookDistributionRecord,
                                         AaTextbookFeeLedger, AaTextbookOrderBatch,
                                         AaTextbookOrderItem, AaTextbookReviewBatch,
                                         AaTextbookReviewBatchItem,
                                         AaTextbookSelection, AaTimeSlot)
from app.models.notification import NotificationLog, NotificationTask, NotificationTemplate  # noqa: F401
from app.models.auth_token import AuthBlockedJti, AuthRefreshToken  # noqa: F401
from app.models.portal import TenantPortalConfig  # noqa: F401
