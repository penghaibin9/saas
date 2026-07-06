"""ORM 模型聚合（第一批 19 张核心表，表名以冻结册 t_ 前缀为准）。"""
from app.models.base import Base  # noqa: F401
from app.models.tenant import Tenant, TenantBrandConfig  # noqa: F401
from app.models.org import College, Major, SchoolClass  # noqa: F401
from app.models.rbac import Permission, Role, RolePermission, User, UserRole  # noqa: F401
from app.models.student import StudentContact, StudentImportBatch, StudentProfile, StudentStageEvent  # noqa: F401
from app.models.approval import UnifiedTodo, WorkflowInstance, WorkflowTask  # noqa: F401
from app.models.message import UnifiedMessage  # noqa: F401
from app.models.audit import ExportTask, SecurityAuditLog  # noqa: F401
from app.models.file import FileObject  # noqa: F401
from app.models.platform import PlatformConfig, PlatformNotice, PlatformOrder  # noqa: F401
from app.models.internship import (AttendanceException, InternshipAuditTrail, InternshipBatch,  # noqa: F401
                                    InternshipCheckin, InternshipRecord, RiskRecord, WeeklyReport)
from app.models.orientation import (GreenChannelApplication, OrientationAuditTrail,  # noqa: F401
                                     OrientationException, OrientationExceptionFollowup,
                                     OrientationMaterial, OrientationStudent)
from app.models.campus_service import (CsAuditTrail, CsDiscipline, CsDormException,  # noqa: F401
                                        CsDormRecord, CsGrant, CsLeave, CsMentalRecord,
                                        CsServiceStudent, CsWorkOrder)
from app.models.academic import (AcademicAuditTrail, AcademicGrade, AcademicIntervention,  # noqa: F401
                                    AcademicMakeup, AcademicRetake, AcademicStudent, AcademicWarning)
from app.models.graduation import (GraduationAuditTrail, GraduationDefenseGroup,  # noqa: F401
                                      GraduationFinal, GraduationProposal, GraduationStudent,
                                      GraduationTopic)
from app.models.employment import (EmpAuditTrail, EmpCompany, EmpFollowup, EmpJob,  # noqa: F401
                                     EmpMaterial, EmpStudent)
from app.models.teacher_scope import TeacherStudentScope  # noqa: F401
from app.models.affairs import (AffairsAuditTrail, AffairsClassCadre,  # noqa: F401
                                AffairsLeaveCancelRecord, AffairsLeaveExtension)
from app.models.affairs_aid import (AidApply, AidBatch, AidFamilyEconomy,  # noqa: F401
                                    AidLevelHistory, FundingApplication,
                                    FundingBatch, FundingProject)
from app.models.affairs_discipline import (AffairsRiskHandle,  # noqa: F401
                                           AffairsRiskRecord, DisciplineCase,
                                           DisciplineRemoveApply)
from app.models.affairs_talk import (FamilyContactLog, TalkPlan,  # noqa: F401
                                     TalkRecord)
from app.models.affairs_dorm import (DormBed, DormBuilding,  # noqa: F401
                                     DormCheckRecord, DormCheckTask, DormRoom,
                                     DormTransfer)
from app.models.affairs_archive import ArchiveBatch, ArchivePackage  # noqa: F401
from app.models.notification import NotificationLog, NotificationTask, NotificationTemplate  # noqa: F401
from app.models.auth_token import AuthBlockedJti, AuthRefreshToken  # noqa: F401
from app.models.portal import TenantPortalConfig  # noqa: F401
