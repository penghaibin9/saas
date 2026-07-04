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
