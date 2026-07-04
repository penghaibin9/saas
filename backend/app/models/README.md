# app/models · 第一批 ORM（19 张核心表）

表名与字段以 `docs/database/00-数据库设计冻结总册.md` 为唯一依据（t_ 前缀）；
冻结册仅给"表卡"的表，字段为第一批骨架 + TODO 注释（细节以 01/11 中心深化文档为准）。

| 分组 | 模型（表） |
| --- | --- |
| 租户品牌 | Tenant(t_tenant)、TenantBrandConfig(t_tenant_brand_config) |
| 组织 | College(t_college)、Major(t_major)、SchoolClass(t_class) |
| 用户与RBAC | User(t_user)、Role(t_role)、Permission(t_permission·无tenant_id)、UserRole(t_user_role)、RolePermission(t_role_permission) |
| 学生主档 | StudentProfile(t_student_profile)、StudentContact(t_student_contact)、StudentStageEvent(t_student_stage_event·append-only)、StudentImportBatch(t_student_import_batch) |
| 审批待办消息 | WorkflowInstance(t_workflow_instance)、WorkflowTask(t_workflow_task)、UnifiedTodo(t_unified_todo)、UnifiedMessage(t_unified_message) |
| 审计导出 | SecurityAuditLog(t_security_audit_log·append-only)、ExportTask(t_export_task) |

注：冻结册无 t_org / t_menu（组织=三级实体表；菜单由 RBAC 配置推导，不建表）。
敏感字段一律 `*_encrypted` + `*_hash`（§17.2），库中不存明文。
