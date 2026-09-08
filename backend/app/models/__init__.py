"""ORM æ¨¡åž‹èšåˆï¼ˆç¬¬ä¸€æ‰¹ 19 å¼ æ ¸å¿ƒè¡¨ï¼Œè¡¨åä»¥å†»ç»“å†Œ t_ å‰ç¼€ä¸ºå‡†ï¼‰ã€‚"""
from app.models.base import Base  # noqa: F401
from app.models.tenant import Tenant, TenantBrandConfig  # noqa: F401
from app.models.org import College, Major, SchoolClass  # noqa: F401
from app.models.rbac import Permission, Role, RolePermission, User, UserRole, WxAccountBinding  # noqa: F401
from app.models.student import StudentContact, StudentImportBatch, StudentProfile, StudentStageEvent  # noqa: F401
from app.models.student_account_link import StudentAccountLink  # noqa: F401  (å­¦ç”Ÿä¸»æ¡£â†”ç™»å½•è´¦å·ç¨³å®šç»‘å®š)
from app.models.student_parent import StudentParentLink  # noqa: F401  (å­¦ç”ŸPCé—¨æˆ·Â·å®¶é•¿æŽˆæƒä»£ç†)
from app.models.portal_otp import PortalLoginOtp  # noqa: F401  (å­¦ç”ŸPCé—¨æˆ·Â·ç™»å½•éªŒè¯ç )
from app.models.portal_sign import PortalSignRecord  # noqa: F401  (å­¦ç”ŸPCé—¨æˆ·Â·ç”µå­ç­¾ç½²ç•™ç—•)
from app.models.approval import (UnifiedTodo, WorkflowDefinition, WorkflowInstance,  # noqa: F401
                                 WorkflowNodeDefinition, WorkflowTask)
from app.models.message import (  # noqa: F401
    MessageAttachment,
    MessageAudience,
    MessageCampaign,
    MessageChannelDelivery,
    MessageDeliveryJob,
    MessageEventOutbox,
    UnifiedMessage,
)
from app.models.notification_preference import NotificationPreference  # noqa: F401
from app.models.user_preference import UserPreference  # noqa: F401
from app.models.audit import ExportTask, SecurityAuditLog  # noqa: F401
from app.models.audit_outbox import AuditOutbox  # noqa: F401
from app.models.idempotency import IdempotencyRecord  # noqa: F401
from app.models.system_config import DataScopeRule, MenuNode, SysConfig  # noqa: F401  (ç³»ç»Ÿç®¡ç†Â·å¯ç¼–è¾‘é…ç½®)
from app.models.system_governance import SystemJsonDoc  # noqa: F401  (ç³»ç»Ÿç®¡ç†Â·æ²»ç† JSON æ–‡æ¡£)
from app.models.file import FileObject  # noqa: F401
from app.models.platform_integrity import IntegrityException  # noqa: F401
from app.models.data_exchange import ExportJob, ImportJob, ImportRowError  # noqa: F401
from app.models.platform import PlatformConfig, PlatformNotice, PlatformOrder  # noqa: F401
from app.models.commercial import (CommercialOrderItem, CommercialSkuVersion,  # noqa: F401
    TenantCommercialProfile, TenantModuleState, TenantModuleSubscriptionSource)
from app.models.internship import (AttendanceException, InternshipAgreement,  # noqa: F401
                                    InternshipArchive, InternshipAuditTrail, InternshipBatch,
                                    InternshipBatchParticipant, InternshipBatchPlan,
                                    InternshipBatchScopeRule, InternshipChangeRequest,
                                    InternshipCheckin, InternshipEnterpriseEval,
                                    InternshipFinalScore, InternshipGuidance, InternshipInsurance,
                                    InternshipLeave, InternshipMakeup, InternshipPlanAck,
                                    InternshipPlanTaskProgress, InternshipProcessReport,
                                    InternshipRecord, InternshipScoreConfig,
                                    InternshipCommunicationLog, InternshipComplaint,
                                    InternshipStudentEval, InternshipVisit, InternshipVisitPlan,
                                    RiskRecord, WeeklyReport)
from app.models.internship_position import InternshipPosition  # noqa: F401  (å²—ä½åº“Â·ç‹¬ç«‹æ–‡ä»¶)
from app.models.internship_enterprise_portal import (  # noqa: F401
    InternshipCampaignEnterprise,
    InternshipEnterpriseAccessGrant,
    InternshipEnterpriseMember,
    InternshipRecruitmentCampaign,
)
from app.models.internship_compliance import (  # noqa: F401
    InternshipComplianceExemption, InternshipComplianceTemplate, InternshipConsent,
    InternshipEmergencyPlan, InternshipEnterpriseInspection, InternshipEvidencePackage,
    InternshipIncident, InternshipRemunerationRecord, InternshipSafetyCompletion,
    InternshipSafetyCourse, InternshipSpecialFiling,
)
from app.models.internship_match import InternshipApplication, InternshipIntention, InternshipMatch  # noqa: F401  (å²—ä½åŒ¹é…/ç”³è¯·)
from app.models.excel_import_job import ExcelImportJob  # noqa: F401  (å…¬å…± Excel åº•åº§Â·é€šç”¨å¯¼å…¥è®°å½•)
from app.models.identity_import_batch import IdentityImportBatch  # noqa: F401
from app.models.shared_import_batch import SharedImportBatch  # noqa: F401
from app.models.internship_agreement_template import InternshipAgreementTemplate  # noqa: F401  (å®žä¹ åè®®æ¨¡æ¿åº“Â·ç‹¬ç«‹æ–°æ–‡ä»¶)
from app.models.orientation import (GreenChannelApplication, OrientationArchive,  # noqa: F401
                                     OrientationActivationChallenge, OrientationAuditTrail, OrientationBatch,
                                     OrientationCheckinPoint, OrientationCheckinRecord,
                                     OrientationCheckinToken, OrientationEnrollmentFinalize,
                                     OrientationException,
                                     OrientationExceptionFollowup, OrientationFlowConfig,
                                     OrientationArrivalPlan, OrientationFlowStep, OrientationFlowVersion,
                                     OrientationMaterial, OrientationMaterialRequirement,
                                     OrientationNoticeTask, OrientationO1BackfillIssue,
                                     OrientationPaymentAccount, OrientationQualificationDecision,
                                     OrientationStudent, OrientationStudentStep)
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
from app.models.graduation_material import (  # noqa: F401
    GraduationMaterialBackfillCheckpoint,
    GraduationMaterialItem,
    GraduationMaterialRule,
    GraduationStudentMaterial,
    GraduationTemplateAssetPolicy,
)
from app.models.employment import (EmpAuditTrail, EmpCompany,  # noqa: F401
                                     EmpDestinationSubmission, EmpFollowup,
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
# åŒ… 10 çš„ä¸§å¼ å®Œæ•´æ€§è¡¨ã€æ–‡ä»¶é…é¢é¢„è¡¨ï¼šmodel æ–‡ä»¶éƒ½å·²å†™å¥¼ï¼Œä¸€ç›´æ²£åœ¨è¿™å¯¿å…¤ï¼Œ(Œµ•Ñ…‘…Ñ„ƒ¦3žr/’â7–"Ã–º’î³¾ò1‘É½Á}…±°½É•…Ñ•}…±°ƒ’â;¢þžžï–âO’â¢ÓšŸšŽš~—–£¦÷šò?š:'žjŠ"SŠ"S¢†—’â+šÎ£–3Ž)™É½´…ÁÀ¹µ½‘•±Ì¹…™™…¥ÉÍ}‘¥Í¥Á±¥¹•}¥¹Ñ•É¥Ñä¥µÁ½ÉÐ€¡¥Í¥Á±¥¹••¥Í¥½¹Y•ÉÍ¥½¸°€€Œ¹½Å„èÐÀÄ(€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€¥Í¥Á±¥¹•MÕ‰™±½Ý1½¬¤)™É½´…ÁÀ¹µ½‘•±Ì¹™¥±•}ÅÕ½Ñ„¥µÁ½ÉÐ¥±•MÑ½É…•EÕ½Ñ…I•Í•ÉÙ…Ñ¥½¸€€Œ¹½Å„èÐÀÄ)™É½´…ÁÀ¹µ½‘•±Ì¹…™™…¥ÉÍ}Ñ…±¬¥µÁ½ÉÐ€¡…µ¥±å½¹Ñ…Ñ1½œ°Q…±­A±…¸°€€Œ¹½Å„èÐÀÄ(€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€Q…±­I•½É¤)™É½´…ÁÀ¹µ½‘•±Ì¹…™™…¥ÉÍ}µ•¹Ñ…°¥µÁ½ÉÐAÍåI•™•ÉÉ…°€€Œ¹½Å„èÐÀÄ)™É½´…ÁÀ¹µ½‘•±Ì¹…™™…¥ÉÍ}ÁÍå}ÍÕÉÙ•ä¥µÁ½ÉÐAÍåMÕÉÙ•åMÕ‰µ¥ÍÍ¥½¸€€Œ¹½Å„èÐÀÄ€€£–þžB–—–êß’öO¢¾
ßž¾³’âšZÃšZ’îØ¤)™É½´…ÁÀ¹µ½‘•±Ì¹…™™…¥ÉÍ}‘½É´¥µÁ½ÉÐ€¡½Éµ•ÍÍÙ•¹Ð°½Éµ±±½…Ñ¥½¹	…Ñ °€€Œ¹½Å„èÐÀÄ(€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€½Éµ±±½…Ñ¥½¹%Ñ•´°½Éµ	•°½Éµ	Õ¥±‘¥¹œ°(€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€½Éµ¡•­½ÕÑI•ÅÕ•ÍÐ°(€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€½Éµ¡•­I•½É°½Éµ¡•­Q…Í¬°(€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€½ÉµI•Ñ¥™¥…Ñ¥½¸°½ÉµI½½´°(€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€½ÉµMÑ…ä°½ÉµQÉ…¹Í™•È¤)™É½´…ÁÀ¹µ½‘•±Ì¹…™™…¥ÉÍ}…É¡¥Ù”¥µÁ½ÉÐÉ¡¥Ù•	…Ñ °É¡¥Ù•A…­…”€€Œ¹½Å„èÐÀÄ)™É½´…ÁÀ¹µ½‘•±Ì¹…™™…¥ÉÍ}…Ñ¥Ù¥Ñä¥µÁ½ÉÐ€¡™™…¥ÉÍÑ¥Ù¥Ñä°€€Œ¹½Å„èÐÀÄ(€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€™™…¥ÉÍÑ¥Ù¥ÑåÉ•‘¥Ð°(€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€™™…¥ÉÍÑ¥Ù¥ÑåM¥¹ÕÀ°(€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€™™…¥ÉÍÉ•‘¥ÑÁÁ•…°°(€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€™™…¥ÉÍÉ•‘¥Ñ…Ñ•½Éä°(€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€™™…¥ÉÍY½±Õ¹Ñ••ÉI•½É¤)™É½´…ÁÀ¹µ½‘•±Ì¹…™™…¥ÉÍ}…ÑÑ…¡µ•¹Ð¥µÁ½ÉÐ™™…¥ÉÍÑÑ…¡µ•¹Ð€€Œ¹½Å„èÐÀÄ)™É½´…ÁÀ¹µ½‘•±Ì¹…™™…¥ÉÍ}±Õˆ¥µÁ½ÉÐ€¡™™…¥ÉÍ±Õˆ°€€Œ¹½Å„èÐÀÄ(€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€™™…¥ÉÍ±Õ‰¹¹Õ…±I•Ù¥•Ü°(€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€™™…¥ÉÍ±Õ‰5•µ‰•È¤)™É½´…ÁÀ¹µ½‘•±Ì¹…™™…¥ÉÍ}½Éœ¥µÁ½ÉÐ€¡™™…¥ÉÍ=ÉA½Í¥Ñ¥½¸°€€Œ¹½Å„èÐÀÄ(€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€™™…¥ÉÍMÑÕ‘•¹Ñ=Éœ¤)™É½´…ÁÀ¹µ½‘•±Ì¹…™™…¥ÉÍ}±•…Õ”¥µÁ½ÉÐ€¡™™…¥ÉÍ1•…Õ••Ø°€€Œ¹½Å„èÐÀÄ(€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€™™…¥ÉÍ1•…Õ••ÙMÑ…”¤)™É½´…ÁÀ¹µ½‘•±Ì¹…™™…¥ÉÍ}½Õ¹Í•±½É}•Ù…°¥µÁ½ÉÐ€¡½Õ¹Í•±½ÉÙ…°°€€Œ¹½Å„èÐÀÄ(€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€½Õ¹Í•±½ÉÙ…±%¹‘¥…Ñ½È¤)™É½´…ÁÀ¹µ½‘•±Ì¹…™™…¥ÉÍ}½Õ¹Í•±½É}…ÍÍ¥¹µ•¹Ð¥µÁ½ÉÐ™™…¥ÉÍ½Õ¹Í•±½ÉÍÍ¥¹µ•¹Ð€€Œ¹½Å„èÐÀÄ)™É½´…ÁÀ¹µ½‘•±Ì¹…™™…¥ÉÍ}™Õ¹‘¥¹}•áÐ¥µÁ½ÉÐ€¡••I•‘ÕÑ¥½¸°€€Œ¹½Å„èÐÀÄ(€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€MÑÕ‘•¹Ñ1½…¸°]½É­MÑÕ‘å5½¹Ñ¡±ä°(€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€]½É­MÑÕ‘åA½ÍÐ°]½É­MÑÕ‘åI•½É¤)™É½´…ÁÀ¹µ½‘•±Ì¹……‘•µ¥}…™™…¥ÉÌ¥µÁ½ÉÐ€¡…É¡¥Ù•	…Ñ °€€Œ¹½Å„èÐÀÄ(€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€…É¡¥Ù•%Ñ•´°…ÑÑ•¹‘…¹•M•ÍÍ¥½¸°(€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€……±•¹‘…ÉÙ•¹Ð°(€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€…±…ÍÍ‘©ÕÍÑµ•¹ÑI•ÅÕ•ÍÐ°…±…ÍÍQ¥µ•	…¹°(€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€…±…ÍÍÉ½½´°…±…ÍÍÉ½½µ	½½­¥¹œ°(€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€…½ÕÉÍ”°…½ÕÉÍ•5…Ñ•É¥…°°…•™•ÉÉ•‘á…´°(€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€…1…‰I•Í½ÕÉ”°…ÅÕ¥Áµ•¹Ð°(€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€…1…‰	½½­¥¹œ°…I•Í½ÕÉ•I•Á…¥È°(€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€…5…©½É¥É•Ñ¥½¸°(€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€…Ù…±Õ…Ñ¥½¹ÁÁ•…°°…Ù…±Õ…Ñ¥½¹	…Ñ °(€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€…Ù…±Õ…Ñ¥½¹I•½É°…Ù…±Õ…Ñ¥½¹I•ÍÕ±Ð°(€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€…Ù…±Õ…Ñ¥½¹Q…Í¬°…á•µÁÑ¥½¸°(€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€…á…µÕ‘¥ÑQÉ…¥°°…á…µ	…Ñ °(€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€…5…­•ÕÁ	…Ñ °…I•Ñ…­•ÁÁ±ä°(€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€…á…µ½ÕÉÍ”°…á…µ%¹¥‘•¹Ð°(€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€…á…µ%¹Ù¥¥±…Ñ½È°…á…µA…ÑÉ½°°(€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€…á…µI½½´°…á…µI½½µMÑÕ‘•¹Ð°(€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€…á…µQ•…¡•É1½¬°(€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€…É…‘•I•¡•¬°…]½É­±½…‘•±…É…Ñ¥½¸°(€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€…É…‘•I•½É°…É…‘•Q…Í¬°(€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€…É…‘Õ…Ñ¥½¹Õ‘¥Ñ	…Ñ °(€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€…É…‘Õ…Ñ¥½¹Õ‘¥ÑI•ÍÕ±Ð°…AÉ½É…´°(€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€…AÉ½É…µ	¥¹‘¥¹œ°…AÉ½É…µ½ÕÉÍ”°(€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€…AÉ½É…µÉ…‘Õ…Ñ¥½¹I•ÅÕ¥É•µ•¹Ð°(€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€…AÉ½É…µAÉ…Ñ¥•M•µ•¹Ð°(€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€…EÕ…±¥ÑåI•½É°…EÕ…±¥ÑåI•Ñ¥™¥…Ñ¥½¸°(€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€…I•¥ÍÑÉ…Ñ¥½¸°…I•¥ÍÑÉ…Ñ¥½¹	…Ñ °(€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€…I•¥ÍÑÉ…Ñ¥½¹•™•ÉÉ…°°(€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€…I•¥ÍÑÉ…Ñ¥½¹á•ÁÑ¥½¸°(€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€…M¡•‘Õ±•	…Ñ °…M¡•‘Õ±•¡…¹”°(€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€…M¡•‘Õ±•%Ñ•´°…M¡•‘Õ±•AÕ‰±¥Í °(€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€…M¡•‘Õ±•IÕ±”°…M¡•‘Õ±•M½Á•!•…°(€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€…M•±•Ñ¥½¹	…Ñ °(€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€…Q•…¡•ÉÙ…¥±…‰¥±¥Ñä°(€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€…É…‘•I•½¹¥Ñ¥½¸°…É…‘Õ…Ñ¥½¹•ÉÑ¥™¥…Ñ”°(€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€…1•Ù•±á…´°…1•Ù•±á…µI•œ°(€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€…5…©½ÉMÁ±¥Ñ	…Ñ °…5…©½ÉMÁ±¥Ñ=ÁÑ¥½¸°(€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€…5…©½ÉMÁ±¥ÑY½±Õ¹Ñ••È°(€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€…M•±•Ñ¥½¹½ÕÉÍ”°…M•±•Ñ¥½¹I•½É°(€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€…M•±•Ñ¥½¹I½Õ¹°(€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€…MÑ…ÑÕÍ¡…¹”°…MÑÕ‘•¹Ñ½ÉÉ•Ñ¥½¸°(€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€…Q•…¡¥¹Q…Í¬°(€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€…Q•…¡¥¹Q…Í­	…Ñ °…Q•É´°(€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€…Q•áÑ‰½½¬°…Q•áÑ‰½½­¥ÍÑÉ¥‰ÕÑ¥½¹	…Ñ °(€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€…Q•áÑ‰½½­¥ÍÑÉ¥‰ÕÑ¥½¹I•½É°(€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€…Q•áÑ‰½½­••1•‘•È°…Q•áÑ‰½½­=É‘•É	…Ñ °(€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€…Q•áÑ‰½½­=É‘•É%Ñ•´°…Q•áÑ‰½½­I•Ù¥•Ý	…Ñ °(€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€…Q•áÑ‰½½­I•Ù¥•Ý	…Ñ¡%Ñ•´°(€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€…Q•áÑ‰½½­M•±•Ñ¥½¸°…Q¥µ•M±½Ð¤)™É½´…ÁÀ¹µ½‘•±Ì¹……‘•µ¥}…™™…¥ÉÍ}É•¥ÍÑÉä¥µÁ½ÉÐ€¨€€Œ¹½Å„èÐÀÄ±ÐÀÌ)™É½´…ÁÀ¹µ½‘•±Ì¹……‘•µ¥}…±•¹‘…È¥µÁ½ÉÐ€¡…‘•µ¥…±•¹‘…É½Ù•É¹…¹”°€€Œ¹½Å„èÐÀÄ€€¡MeL´ÄÈƒ–¶›šršÊïžBš*W–öÄ¤(€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€…±•¹‘…ÉQÉ…¹Í¥Ñ¥½¹Ù•¹Ð°…±•¹‘…É]¥¹‘½Ü¤)™É½´…ÁÀ¹µ½‘•±Ì¹½É…¹¥é…Ñ¥½¹}Ù•ÉÍ¥½¸¥µÁ½ÉÐ€¡=ÉY•ÉÍ¥½¸°=ÉY•ÉÍ¥½¹%Ñ•´°€€Œ¹½Å„èÐÀÄ€€¡MeL´ÀÐƒžîžîž&#šr³’â;’îï¢0¤(€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€MÑ…™™ÍÍ¥¹µ•¹Ð¤)™É½´…ÁÀ¹µ½‘•±Ì¹½¹™¥}½Ù•É¹…¹”¥µÁ½ÉÐ€¡½¹™¥Ñ¥Ù…Ñ¥½¸°€€Œ¹½Å„èÐÀÄ€€¡MeL´ÄÄƒ¦7žö»šÊïžB¤(€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€½¹™¥•™¥¹¥Ñ¥½¸°½¹™¥=Ù•ÉÉ¥‘”¤)™É½´…ÁÀ¹µ½‘•±Ì¹Á•Éµ¥ÍÍ¥½¹}½Ù•É¹…¹”¥µÁ½ÉÐ€¡ÕÍÑ½µI½±•M½ÕÉ”°€€Œ¹½Å„èÐÀÄ€€¡MeL´ÀØƒšv¦fC–2’â;¢žK¢&Ëš¢‡švü¤(€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€A•Éµ¥ÍÍ¥½¹	Õ¹‘±”°(€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€A•Éµ¥ÍÍ¥½¹	Õ¹‘±•%Ñ•´°(€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€I½±•Q•µÁ±…Ñ”°I½±•Q•µÁ±…Ñ•A•Éµ¥ÍÍ¥½¸°(€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€]¥±‘…É‘I•Ñ¥É•µ•¹Ð¤)™É½´…ÁÀ¹µ½‘•±Ì¹Í½Á•}Á½±¥ä¥µÁ½ÉÐ€¡M½Á•A½±¥å•¥Í¥½¹1½œ°€€Œ¹½Å„èÐÀÄ€€¡MeL´Ààƒžîžî–º'–£š‚G’â;šbû–ò=9d¤(€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€M½Á•A½±¥åQ…É•Ð¤)™É½´…ÁÀ¹µ½‘•±Ì¹Í•ÕÉ¥Ñå}¡…¹”¥µÁ½ÉÐ€¡M•ÕÉ¥ÑåÑ¥Ù…Ñ¥½¸°€€Œ¹½Å„èÐÀÄ€€¡MeL´Àäƒ–º'–£–>cšnÓ’â;šþšÒì¤(€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€M•ÕÉ¥Ñå¡…¹•%Ñ•´°M•ÕÉ¥Ñå¡…¹•M•Ð¤)™É½´…ÁÀ¹µ½‘•±Ì¹…•ÍÍ}½Ù•É¹…¹”¥µÁ½ÉÐ€¡•ÍÍ•¥Í¥½¹QÉ…”°€€Œ¹½Å„èÐÀÄ€€¡MeL´ÄÀƒ¢ºÿ¦^»¢ž¦+’â;šÊïžB¤(€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€•ÍÍI•Ù¥•Ý…µÁ…¥¸°•ÍÍI•Ù¥•Ý%Ñ•´°(€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€µ•É•¹å•ÍÍM•ÍÍ¥½¸°M½‘IÕ±”°M½‘Y¥½±…Ñ¥½¸¤)™É½´…ÁÀ¹µ½‘•±Ì¹Ñ•¹…¹Ñ}…Á…‰¥±¥Ñä¥µÁ½ÉÐQ•¹…¹Ñ…Á…‰¥±¥ÑåM•ÑÑ¥¹œ€€Œ¹½Å„èÐÀÄ€€¡MeL´ÄÌƒ–¶›š‚‡¢÷–*o–B¿žR ¤)™É½´…ÁÀ¹µ½‘•±Ì¹É½±•}…ÍÍ¥¹µ•¹Ð¥µÁ½ÉÐI½±•ÍÍ¥¹µ•¹ÑY…±¥‘¥Ñä€€Œ¹½Å„èÐÀÄ€€¡MeL´ÀÜƒ¢žK¢&Ëš"C–Fcšr'šV#šr|¤)™É½´…ÁÀ¹µ½‘•±Ì¹É½±•}…ÍÍ¥¹µ•¹Ñ}Í½Á”¥µÁ½ÉÐI½±•ÍÍ¥¹µ•¹ÑM½Á”€€Œ¹½Å„èÐÀÄ)™É½´…ÁÀ¹µ½‘•±Ì¹µ…ÍÑ•É}‘…Ñ…}½Ù•É¹…¹”¥µÁ½ÉÐ€¡…Ñ…½µ…¥¸°€€Œ¹½Å„èÐÀÄ€€¡MeL´ÄÜƒ’âïšVÃš6»šÊïžB¤(€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€…Ñ…=Ý¹•È°…Ñ…EÕ…±¥Ñå%ÍÍÕ”°(€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€…Ñ…EÕ…±¥ÑåIÕ±”°5…ÍÑ•É5•É•Ù•¹Ð¤)™É½´…ÁÀ¹µ½‘•±Ì¹Ý½É­™±½Ý}Í•ÕÉ¥Ñå}Á½±¥ä¥µÁ½ÉÐ€¡]½É­™±½ÝÑ¥½¹A½±¥ä°€€Œ¹½Å„èÐÀÄ€€¡MeL´ÄÐƒšÖž¢/–º'–£ž¶[žV”¤(€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€]½É­™±½ÝY•ÉÍ¥½¹5¥É…Ñ¥½¹Ù•¹Ð¤)™É½´…ÁÀ¹µ½‘•±Ì¹¹½Ñ¥™¥…Ñ¥½¸¥µÁ½ÉÐ9½Ñ¥™¥…Ñ¥½¹1½œ°9½Ñ¥™¥…Ñ¥½¹Q…Í¬°9½Ñ¥™¥…Ñ¥½¹Q•µÁ±…Ñ”€€Œ¹½Å„èÐÀÄ)™É½´…ÁÀ¹µ½‘•±Ì¹Ý½É­‰•¹ ¥µÁ½ÉÐI½±•]½É­‰•¹¡½¹™¥œ€€Œ¹½Å„èÐÀÄ)™É½´…ÁÀ¹µ½‘•±Ì¹…ÕÑ¡}Ñ½­•¸¥µÁ½ÉÐÕÑ¡	±½­•‘)Ñ¤°ÕÑ¡I•™É•Í¡Q½­•¸€€Œ¹½Å„èÐÀÄ)™É½´…ÁÀ¹µ½‘•±Ì¹Á½ÉÑ…°¥µÁ½ÉÐQ•¹…¹ÑA½ÉÑ…±½¹™¥œ€€Œ¹½Å„èÐÀÄ)™É½´…ÁÀ¹µ½‘•±Ì¹Í…¹‘‰½à¥µÁ½ÉÐM…¹‘‰½á	…Í•±¥¹”€€Œ¹½Å„èÐÀÄ)™É½´…ÁÀ¹µ½‘•±Ì¹™••‘‰…¬¥µÁ½ÉÐ••‘‰…¬€€Œ¹½Å„èÐÀÄ€€£–â»–*§’â;–>7¦š#
ßž.³ž®/šZÃšZ’îØ¤)™É½´…ÁÀ¹µ½‘•±Ì¹ÍåÍÑ•µ}¥µÁ±•µ•¹Ñ…Ñ¥½¸¥µÁ½ÉÐ€¡MåÍÑ•µ%µÁ±•µ•¹Ñ…Ñ¥½¹¡•¬°€€Œ¹½Å„èÐÀÄ(€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€MåÍÑ•µ	ÕÍ¥¹•ÍÍI•±…Ñ¥½¹	…Ñ °(€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€MåÍÑ•µ	ÕÍ¥¹•ÍÍI•±…Ñ¥½¹%¹ÍÑ…±±%Ñ•´°(€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€MåÍÑ•µ%µÁ±•µ•¹Ñ…Ñ¥½¹AÉ½©•Ð°(€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€MåÍÑ•µ%µÁ±•µ•¹Ñ…Ñ¥½¹M•Ñ¥½¸°(€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€MåÍÑ•µAÉ•Í•Ñ%¹ÍÑ…±±…Ñ¥½¸¤)™É½´…ÁÀ¹µ½‘•±Ì¹¹…Ñ¥½¹…±}ÍÑ…¹‘…É¥µÁ½ÉÐ€¡9…Ñ¥½¹…±5…©½É…Ñ…±½œ°9…Ñ¥½¹…±MÑ…¹‘…É‘½Õµ•¹Ð°€€Œ¹½Å„èÐÀÄ(€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€9…Ñ¥½¹…±MÑ…¹‘…É‘M•Ñ¥½¸°9…Ñ¥½¹…±MÑ…¹‘…É‘M½ÕÉ”°(€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€M¡½½±5…©½ÉMÑ…¹‘…É‘	¥¹‘¥¹œ¤()™É½´…ÁÀ¹µ½‘•±Ì¹…™™…¥ÉÍ}É•Á…¥É}©½ˆ¥µÁ½ÉÐ™™…¥ÉÍI•Á…¥É)½ˆ€€Œ¹½Å„èÐÀÄ€€£–¶›–Þ—žRÏ¢¾'¢†—–ÿžžžê›’îï–*„¤)™É½´…ÁÀ¹µ½‘•±Ì¹Á…ÍÍÝ½É‘}É•Í•Ð¥µÁ½ÉÐA…ÍÍÝ½É‘I•Í•ÑMµÍ)½ˆ€€Œ¹½Å„èÐÀÄ)™É½´…ÁÀ¹µ½‘Õ±•Ì¹Á±…Ñ™½É´¹‰ÕÍ¥¹•ÍÍ}™½ÉµÌ¹µ½‘•±Ì¥µÁ½ÉÐ€ €€Œ¹½Å„èÐÀÄ(€€€	ÕÍ¥¹•ÍÍ½Éµ•™¥¹¥Ñ¥½¸°(€€€	ÕÍ¥¹•ÍÍ½ÉµY•ÉÍ¥½¸°(¤)™É½´…ÁÀ¹µ½‘Õ±•Ì¹Á±…Ñ™½É´¹‘½Õµ•¹Ñ}±¥™•å±”¹µ½‘•±Ì¥µÁ½ÉÐ€ €€Œ¹½Å„èÐÀÄ(€€€½Õµ•¹Ñ½µÁ…É•I•ÍÕ±Ð°(€€€¥±••É¥Ù•‘ÉÑ¥™…Ð°(€€€MÑÕ‘•¹Ñ1¥™•å±•…Ð°(¤(