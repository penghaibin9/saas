"""007 标准学校的组织治理、审批和控制面演示事实。

这不是为覆盖率填空：每条记录都挂在已经存在的 007 管理员、组织、学期或业务单据上，
供系统管理、审批中心和工作台实际读取。所有键均以 ``007-GOV-2026`` 为可重复执行标记。
"""
from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
import json

from sqlalchemy import func, select

REFERENCE_NOW = datetime(2026, 8, 28, 10, 30)
MARKER = "007-GOV-2026"


def _one(db, model, tenant_id: int, **where):
    clauses = [model.tenant_id == tenant_id]
    if hasattr(model, "is_deleted"):
        clauses.append(model.is_deleted.is_(False))
    clauses.extend(getattr(model, key) == value for key, value in where.items())
    return db.scalars(select(model).where(*clauses)).first()


def _put(db, model, tenant_id: int, key: dict, values: dict):
    row = _one(db, model, tenant_id, **key)
    if row is None:
        row = model(tenant_id=tenant_id, **key, **values)
        db.add(row)
        db.flush()
    return row


def _count(db, model, tenant_id: int) -> int:
    clauses = [model.tenant_id == tenant_id]
    if hasattr(model, "is_deleted"):
        clauses.append(model.is_deleted.is_(False))
    return int(db.scalar(select(func.count()).select_from(model).where(*clauses)) or 0)


def seed_governance_coverage(db, tenant_id: int) -> dict:
    """写入 007 学校真正可展示的共用治理与审批链，重复执行不重复造行。"""
    from app.models import (
        AaTerm, College, CsLeave, DataScopeRule, MenuNode, Permission, Role, RolePermission, SchoolClass, SysConfig,
        TenantCapabilitySetting, UnifiedTodo, User, UserRole, WorkflowDefinition, WxAccountBinding,
        WorkflowInstance, WorkflowNodeDefinition, WorkflowTask,
    )
    from app.models.access_governance import (
        AccessDecisionTrace, AccessReviewCampaign, AccessReviewItem, EmergencyAccessSession,
        SodRule, SodViolation,
    )
    from app.models.academic_calendar import AcademicCalendarGovernance, CalendarTransitionEvent, CalendarWindow
    from app.models.config_governance import ConfigActivation, ConfigOverride
    from app.models.master_data_governance import DataDomain, DataOwner, DataQualityIssue, DataQualityRule, MasterMergeEvent
    from app.models.organization_version import OrgVersion, OrgVersionItem, StaffAssignment
    from app.models.permission_governance import (
        CustomRoleSource, PermissionBundle, PermissionBundleItem, RoleTemplate,
        RoleTemplatePermission, WildcardRetirement,
    )
    from app.models.role_assignment import RoleAssignmentValidity
    from app.models.scope_policy import ScopePolicyDecisionLog, ScopePolicyTarget
    from app.models.security_change import SecurityActivation, SecurityChangeItem, SecurityChangeSet
    from app.models.system_implementation import (
        SystemBusinessRelationBatch, SystemBusinessRelationInstallItem, SystemImplementationCheck,
        SystemImplementationProject, SystemImplementationSection, SystemPresetInstallation,
    )
    from app.models.workflow_security_policy import WorkflowActionPolicy, WorkflowVersionMigrationEvent
    from app.models.workbench import RoleWorkbenchConfig
    from app.models.file import (ArchiveManifest, ArchiveManifestItem, FileAsset, FileBinding, FileObject,
                                 FileRetentionPolicy, FileScanRecord, FileUploadSession, FileVersion,
                                 TenantStorageQuota)
    from app.models.message import (MessageAttachment, MessageAudience, MessageCampaign,
                                    MessageChannelDelivery, UnifiedMessage)
    from app.models.notification import NotificationLog, NotificationTask, NotificationTemplate
    from app.models.notification_preference import NotificationPreference

    admin = _one(db, User, tenant_id, login_name="admin2")
    teacher = _one(db, User, tenant_id, login_name="teacher2")
    student = _one(db, User, tenant_id, login_name="student2")
    college = db.scalars(select(College).where(College.tenant_id == tenant_id, College.is_deleted.is_(False)).order_by(College.id)).first()
    clazz = db.scalars(select(SchoolClass).where(SchoolClass.tenant_id == tenant_id, SchoolClass.is_deleted.is_(False)).order_by(SchoolClass.id)).first()
    term = db.scalars(select(AaTerm).where(AaTerm.tenant_id == tenant_id, AaTerm.is_deleted.is_(False), AaTerm.is_current.is_(True))).first()
    leave = db.scalars(select(CsLeave).where(CsLeave.tenant_id == tenant_id, CsLeave.is_deleted.is_(False)).order_by(CsLeave.id)).first()
    if not all((admin, teacher, student, college, clazz, term, leave)):
        raise RuntimeError("007 governance seed requires existing admin2/teacher2/student2, organization, current term and leave facts")

    project = _put(db, SystemImplementationProject, tenant_id, {"project_no": MARKER}, {
        "project_name": "跃科职业技术学院 007 正式演示实施验收", "profile_code": "HIGHER_VOCATIONAL",
        "status": "ACCEPTED", "owner_id": admin.id, "target_date": REFERENCE_NOW.date(),
        "preview_json": {"school": "跃科职业技术学院（演示）", "scope": "全生命周期标准演示"},
        "preview_hash": "007gov20260828preview", "applied_at": REFERENCE_NOW - timedelta(days=30),
        "accepted_at": REFERENCE_NOW - timedelta(days=1), "accepted_by": admin.id,
        "acceptance_comment": "组织、学工、教务、实习、毕业设计演示链路已验收。",
        "acceptance_digest": "007gov20260828acceptance", "acceptance_summary": {"modules": 5, "result": "PASS"},
    })
    for code, detail in (("ORG", "组织与角色"), ("AFFAIRS", "学工"), ("ACADEMIC", "教务"), ("INTERNSHIP", "岗位实习"), ("GRADUATION", "毕业设计")):
        _put(db, SystemImplementationSection, tenant_id, {"project_id": project.id, "section_code": code}, {
            "schema_version": "2026.1", "source": "RECOMMENDED", "status": "CONFIGURED",
            "config_json": {"marker": MARKER, "name": detail, "accepted": True},
        })
    install = _put(db, SystemPresetInstallation, tenant_id, {"installation_no": f"{MARKER}-INITIAL"}, {
        "project_id": project.id, "change_type": "INITIAL", "source_profile": "HIGHER_VOCATIONAL",
        "source_version": "2026.1", "snapshot_json": {"projectNo": MARKER, "sections": 5},
        "snapshot_hash": "007gov20260828install", "status": "APPLIED", "reason": "007 标准演示学校首次预设安装",
        "applied_at": REFERENCE_NOW - timedelta(days=30),
    })
    for code, name in (("ORG_READY", "组织架构已核验"), ("ROLE_READY", "三角色权限已核验"), ("DEMO_READY", "核心演示流程已核验")):
        _put(db, SystemImplementationCheck, tenant_id, {"project_id": project.id, "check_code": code}, {
            "category_code": "ACCEPTANCE", "check_name": name, "severity": "BLOCKER", "result": "PASS",
            "evidence_json": {"marker": MARKER, "verifiedAt": REFERENCE_NOW.isoformat()}, "owner_role": "SCHOOL_ADMIN",
            "confirmed_by": admin.id, "confirmed_at": REFERENCE_NOW - timedelta(days=1), "comment": "007 本地沙箱可复核证据。",
        })
    relation_batch = _put(db, SystemBusinessRelationBatch, tenant_id, {"batch_no": f"{MARKER}-REL"}, {
        "project_id": project.id, "source_import_batch_no": MARKER, "source_hash": "007gov20260828relations",
        "status": "APPLIED", "candidates_json": [{"type": "CLASS_COUNSELOR", "classId": clazz.id}],
        "decisions_json": [{"decision": "CONFIRMED", "by": admin.id}], "summary_json": {"applied": 1},
        "confirmed_at": REFERENCE_NOW - timedelta(days=29), "applied_at": REFERENCE_NOW - timedelta(days=29),
    })
    _put(db, SystemBusinessRelationInstallItem, tenant_id, {"project_id": project.id, "relation_key": f"CLASS-{clazz.id}-COUNSELOR"}, {
        "relation_batch_id": relation_batch.id, "relation_type": "CLASS_COUNSELOR", "subject_ref": f"class:{clazz.id}",
        "object_ref": f"user:{clazz.counselor_id or teacher.id}", "context_ref": f"college:{college.id}",
        "target_table": "t_class", "target_row_id": clazz.id, "before_json": {},
        "after_json": {"counselorId": clazz.counselor_id or teacher.id}, "status": "APPLIED",
        "applied_at": REFERENCE_NOW - timedelta(days=29),
    })

    # 真实模块清单驱动的学校能力设置，而不是手写虚构模块名。
    manifest = json.loads((Path(__file__).resolve().parents[3] / "shared" / "contracts" / "module-manifest.json").read_text(encoding="utf-8"))
    for module in manifest["modules"]:
        if module["schoolVisible"] and not module["platformOnly"]:
            _put(db, TenantCapabilitySetting, tenant_id, {"capability_key": module["moduleKey"]}, {
                "enabled": True, "reason": "007 标准演示学校已启用", "last_changed_at": REFERENCE_NOW - timedelta(days=30), "last_changed_by": admin.id,
            })
    for key, group, name, value in (("SEC_LOCK_MAX_FAIL", "SECURITY", "连续失败锁定阈值", "5"), ("DEMO_SCHOOL_TIMEZONE", "GENERAL", "学校时区", "Asia/Shanghai")):
        _put(db, SysConfig, tenant_id, {"config_key": key}, {"config_group": group, "config_name": name, "value_text": value, "sensitive": False, "remark": f"{MARKER} 正式演示配置"})
    _put(db, DataScopeRule, tenant_id, {"rule_name": f"{MARKER}-COUNSELOR-CLASS"}, {
        "role_code": "COUNSELOR", "scope_type": "CLASS", "target_json": {"classIds": [clazz.id]}, "status": "ACTIVE", "remark": "辅导员仅查看本人带班学生。",
    })
    for code, title, path, module, permission, order in (("workbench", "工作台", "/", "workbench", "workbench.view", 10), ("approval", "审批中心", "/admin/approval", "approval", "approval.view", 20), ("academicAffairs", "教务中心", "/admin/academic-affairs", "academicAffairs", "academicAffairs.view", 30), ("internship", "岗位实习", "/admin/internship", "internship", "internship.view", 40), ("graduationDesign", "毕业设计", "/admin/graduation", "graduationDesign", "graduation.view", 50)):
        _put(db, MenuNode, tenant_id, {"menu_code": code}, {"title": title, "path": path, "module_code": module, "permission_key": permission, "sort_order": order, "status": "ACTIVE", "is_builtin": True})

    bundle = _put(db, PermissionBundle, tenant_id, {"bundle_code": f"{MARKER}-COUNSELOR"}, {
        "bundle_name": "007 辅导员演示权限包", "owner_domain": "studentAffairs", "risk_level": "NORMAL", "delivered": True, "template_version": 1, "description": "班级学生事务和风险处置的最小权限集合", "status": "ACTIVE",
    })
    for permission in ("student.profile.view", "campusService.leave.approve", "approval.task.act"):
        _put(db, PermissionBundleItem, tenant_id, {"bundle_id": bundle.id, "permission_code": permission, "effect": "ALLOW"}, {})
    template = _put(db, RoleTemplate, tenant_id, {"template_code": f"{MARKER}-COUNSELOR", "template_version": 1}, {
        "template_name": "007 辅导员标准角色模板", "template_plane": "TENANT", "template_category": "SYSTEM_ROLE", "publish_status": "PUBLISHED", "permission_digest": "007govcounselor", "effective_at": REFERENCE_NOW - timedelta(days=30), "published_at": REFERENCE_NOW - timedelta(days=30), "published_by": admin.id, "delivered": True, "bundle_codes_json": {"codes": [bundle.bundle_code]}, "permission_ceiling_json": {"allowed": ["student.profile.view", "campusService.leave.approve", "approval.task.act"]}, "status": "ACTIVE",
    })
    for permission in ("student.profile.view", "campusService.leave.approve", "approval.task.act"):
        _put(db, RoleTemplatePermission, tenant_id, {"role_template_id": template.id, "permission_code": permission, "effect": "ALLOW"}, {})
    counselor_role = _one(db, Role, tenant_id, role_code="COUNSELOR")
    admin_role = _one(db, Role, tenant_id, role_code="SCHOOL_ADMIN")
    if admin_role:
        permission = db.scalars(select(Permission).order_by(Permission.id)).first()
        if permission:
            _put(db, RolePermission, tenant_id, {"role_id": admin_role.id, "permission_id": permission.id}, {"status": "ACTIVE"})
    _put(db, WxAccountBinding, tenant_id, {"wx_openid": "wx_sandbox_school_student2_007"}, {"user_id": student.id, "status": "ACTIVE", "last_used_at": REFERENCE_NOW - timedelta(days=1)})
    if counselor_role:
        _put(db, CustomRoleSource, tenant_id, {"role_code": f"{MARKER}-COUNSELOR-VIEW"}, {
            "role_id": counselor_role.id, "source_template_code": template.template_code, "source_template_version": 1, "permission_codes_json": {"codes": ["student.profile.view"]}, "drift_json": {"reason": "演示只读视图"}, "status": "PUBLISHED",
        })
    _put(db, WildcardRetirement, tenant_id, {"role_code": "COUNSELOR", "wildcard_code": "campusService:*"}, {"expanded_count": 3, "expanded_json": {"permissions": ["campusService.leave.approve", "campusService.risk.view", "campusService.talk.create"]}, "replacement_json": {"mode": "explicit"}, "status": "RETIRED", "note": "007 演示租户已使用明确权限替代通配符。"})

    _put(db, ScopePolicyTarget, tenant_id, {"role_code": "COUNSELOR", "effect": "ALLOW", "target_type": "CLASS", "target_id": str(clazz.id), "effective_at": REFERENCE_NOW - timedelta(days=30)}, {"include_children": True, "status": "ACTIVE", "reason": "辅导员班级学生事务处置", "sensitive_domain": None})
    _put(db, ScopePolicyTarget, tenant_id, {"role_code": "COUNSELOR", "effect": "DENY", "target_type": "DOMAIN", "target_id": "PSYCHOLOGY", "effective_at": REFERENCE_NOW - timedelta(days=30)}, {"include_children": False, "status": "ACTIVE", "reason": "心理专项由心理中心授权，不随辅导员常规范围扩大。", "sensitive_domain": "PSYCHOLOGY"})
    if _one(db, ScopePolicyDecisionLog, tenant_id, trace_id=f"{MARKER}-SCOPE") is None:
        db.add(ScopePolicyDecisionLog(tenant_id=tenant_id, role_code="COUNSELOR", target_type="CLASS", target_id=str(clazz.id), decision="ALLOW", reason_code="DIRECT_ALLOW", detail_json={"policy": "class scope"}, trace_id=f"{MARKER}-SCOPE"))

    # 在已存在的请假单上建立真实审批实例、已办/待办任务与工作台待办。
    definition = _put(db, WorkflowDefinition, tenant_id, {"workflow_code": "CS_LEAVE_007"}, {
        "workflow_name": "学生请假审批（007 标准）", "source_module": "campusService", "source_biz_type": "CsLeave", "definition_version": "2026.1", "status": "ENABLED", "policy_confirmed": True, "policy_confirmed_by": admin.id, "policy_confirmed_at": REFERENCE_NOW - timedelta(days=30), "timeout_hours": 48, "allow_transfer": True, "allow_reject": True, "allow_withdraw": True, "starter_role_codes_json": ["STUDENT"], "cc_role_codes_json": ["COUNSELOR"], "policy_snapshot_json": {"marker": MARKER}, "source_profile": "HIGHER_VOCATIONAL", "installed_project_id": project.id, "description": "学生提交、辅导员审批、超时预警。",
    })
    for node, name, seq in (("COUNSELOR_REVIEW", "辅导员审核", 1), ("COLLEGE_CONFIRM", "学院复核", 2)):
        _put(db, WorkflowNodeDefinition, tenant_id, {"workflow_definition_id": definition.id, "node_code": node}, {"node_name": name, "sequence_no": seq, "approver_role_code": "COUNSELOR" if seq == 1 else "COLLEGE_ADMIN", "assignee_strategy": "ROLE_AND_SCOPE", "data_scope_code": "ASSIGNED", "timeout_hours": 48, "condition_json": {}, "status": "ACTIVE"})
    instance = _put(db, WorkflowInstance, tenant_id, {"workflow_code": "CS_LEAVE_007", "source_biz_id": leave.id}, {"source_module": "campusService", "source_biz_type": "CsLeave", "applicant_id": student.id, "title": "007 演示学生请假审批", "status": "RUNNING", "current_node": "COUNSELOR_REVIEW", "remark": "关联真实学工请假单的在办审批。"})
    _put(db, WorkflowTask, tenant_id, {"instance_id": instance.id, "assignee_id": teacher.id}, {"node_code": "COUNSELOR_REVIEW", "status": "PENDING", "deadline_at": REFERENCE_NOW + timedelta(hours=18), "remark": "待辅导员审核；用于管理员与教师工作台演示。"})
    _put(db, UnifiedTodo, tenant_id, {"source_module": "campusService", "source_biz_id": leave.id, "todo_type": "LEAVE_APPROVAL", "assignee_id": teacher.id}, {"source_biz_type": "CsLeave", "student_id": getattr(leave, "student_id", None), "title": "待审核：学生请假申请", "status": "PENDING", "due_at": REFERENCE_NOW + timedelta(hours=18), "remark": "007 审批中心真实待办。"})
    _put(db, WorkflowActionPolicy, tenant_id, {"workflow_code": definition.workflow_code, "node_code": "COUNSELOR_REVIEW", "policy_type": "NODE_ACTION"}, {"status": "ACTIVE", "action_permission_code": "approval.task.act", "version_strategy": "DYNAMIC", "reason": "仅被指派辅导员或具备审批动作权限者可办理。", "submitted_by": admin.id, "submitted_at": REFERENCE_NOW - timedelta(days=29), "reviewed_by": admin.id, "reviewed_at": REFERENCE_NOW - timedelta(days=29)})
    _put(db, WorkflowActionPolicy, tenant_id, {"workflow_code": definition.workflow_code, "node_code": "", "policy_type": "VERSION_STRATEGY"}, {"status": "ACTIVE", "version_strategy": "SNAPSHOT", "reason": "在办请假审批固定使用提交时流程版本。", "submitted_by": admin.id, "submitted_at": REFERENCE_NOW - timedelta(days=29), "reviewed_by": admin.id, "reviewed_at": REFERENCE_NOW - timedelta(days=29)})
    if _one(db, WorkflowVersionMigrationEvent, tenant_id, workflow_code=definition.workflow_code) is None:
        db.add(WorkflowVersionMigrationEvent(tenant_id=tenant_id, workflow_code=definition.workflow_code, from_definition_version="2026.0", to_definition_version="2026.1", affected_instance_count=0, affected_instance_ids_json=[], reason="流程安全策略启用前的基线版本留痕。"))

    _put(db, OrgVersion, tenant_id, {"version_code": f"{MARKER}-ORG-01"}, {"version_name": "2026 秋季组织调整预案", "status": "VALIDATED", "effective_at": REFERENCE_NOW + timedelta(days=4), "reason": "秋季班级辅导员任职核对", "impact_json": {"classes": [clazz.id], "students": 52}})
    org_ver = _one(db, OrgVersion, tenant_id, version_code=f"{MARKER}-ORG-01")
    _put(db, OrgVersionItem, tenant_id, {"version_id": org_ver.id, "org_type": "CLASS", "org_node_id": clazz.id}, {"change_type": "RENAME", "payload_json": {"className": clazz.class_name}, "before_json": {"className": clazz.class_name}, "applied_at": None})
    _put(db, StaffAssignment, tenant_id, {"user_id": teacher.id, "org_type": "CLASS", "org_node_id": clazz.id, "assignment_type": "COUNSELOR", "effective_at": REFERENCE_NOW - timedelta(days=180)}, {"is_primary": True, "source_type": "PROJECTED", "source_id": f"class:{clazz.id}", "expires_at": None, "status": "ACTIVE", "reason": "与行政班辅导员字段对账后的任职事实。"})
    ur = db.scalars(select(UserRole).where(UserRole.tenant_id == tenant_id, UserRole.user_id == teacher.id, UserRole.is_deleted.is_(False)).order_by(UserRole.id)).first()
    if ur and counselor_role:
        _put(db, RoleAssignmentValidity, tenant_id, {"user_role_id": ur.id}, {"user_id": teacher.id, "role_code": counselor_role.role_code, "effective_at": REFERENCE_NOW - timedelta(days=180), "expires_at": None, "source_type": "IMPLEMENTATION", "source_id": project.project_no, "reason": "007 实施验收时复核的辅导员角色授权。", "granted_by": admin.id, "status": "ACTIVE", "last_reviewed_at": REFERENCE_NOW - timedelta(days=1), "last_reviewed_term": getattr(term, "term_name", None)})

    _put(db, ConfigOverride, tenant_id, {"config_key": "SEC_LOCK_MAX_FAIL", "scope_type": "TENANT", "scope_id": "", "effective_at": REFERENCE_NOW - timedelta(days=30)}, {"value_json": {"value": 5}, "expires_at": None, "status": "ACTIVE", "reason": "007 演示环境安全阈值。"})
    if _one(db, ConfigActivation, tenant_id, trace_id=f"{MARKER}-CONFIG") is None:
        db.add(ConfigActivation(tenant_id=tenant_id, config_key="SEC_LOCK_MAX_FAIL", scope_type="TENANT", scope_id="", before_json={"value": 5}, after_json={"value": 5}, actor_user_id=admin.id, reason="初始化后校验配置解析链路。", trace_id=f"{MARKER}-CONFIG"))
    _put(db, AcademicCalendarGovernance, tenant_id, {"term_id": term.id}, {"calendar_type": "ACADEMIC", "timezone": "Asia/Shanghai", "governance_status": "ACTIVE", "active_key": "ACTIVE", "scheduled_at": REFERENCE_NOW - timedelta(days=30), "activated_at": REFERENCE_NOW - timedelta(days=30), "last_transition_reason": "当前学期与教务事实源已对齐。"})
    for wtype, module in (("INTERNSHIP", "internship"), ("GRADUATION", "graduationDesign"), ("EMPLOYMENT", "employment")):
        _put(db, CalendarWindow, tenant_id, {"term_id": term.id, "window_type": wtype, "module_code": module}, {"start_at": REFERENCE_NOW - timedelta(days=30), "end_at": REFERENCE_NOW + timedelta(days=90), "config_json": {"marker": MARKER, "status": "OPEN"}})
    if _one(db, CalendarTransitionEvent, tenant_id, trace_id=f"{MARKER}-CAL") is None:
        db.add(CalendarTransitionEvent(tenant_id=tenant_id, term_id=term.id, from_status="SCHEDULED", to_status="ACTIVE", actor_user_id=admin.id, reason="007 当前演示学期激活", blockers_json={"passed": True}, trace_id=f"{MARKER}-CAL"))

    for code, name, table, module in (("STUDENT", "学生主数据", "t_student_profile", "studentAffairs"), ("ORGANIZATION", "组织主数据", "t_college", "systemAdmin"), ("COURSE", "课程主数据", "t_aa_course", "academicAffairs")):
        _put(db, DataDomain, tenant_id, {"domain_code": code}, {"domain_name": name, "owner_module": module, "authoritative_table": table, "description": "007 演示学校已绑定真实权威表。", "status": "ACTIVE"})
        _put(db, DataOwner, tenant_id, {"domain_code": code, "owner_user_id": admin.id}, {"owner_role_code": "SCHOOL_ADMIN", "is_primary": True, "effective_at": REFERENCE_NOW - timedelta(days=30), "expires_at": None, "status": "ACTIVE"})
        _put(db, DataQualityRule, tenant_id, {"rule_code": f"{code}_BROKEN_LINK"}, {"domain_code": code, "rule_name": f"{name}关联完整性检查", "rule_type": "BROKEN_LINK", "severity": "P1", "executor_key": "sandbox_link_audit", "sla_hours": None, "params_json": {"marker": MARKER}, "status": "ACTIVE"})
    _put(db, DataQualityIssue, tenant_id, {"issue_key": f"{MARKER}-QUALITY-CLOSED"}, {"domain_code": "STUDENT", "rule_code": "STUDENT_BROKEN_LINK", "severity": "P2", "status": "VERIFIED", "object_type": "StudentProfile", "object_id": str(getattr(leave, "student_id", "")), "summary": "演示前学生组织关联复扫通过", "evidence_json": {"orphanCount": 0}, "owner_user_id": admin.id, "first_seen_at": REFERENCE_NOW - timedelta(days=7), "last_seen_at": REFERENCE_NOW - timedelta(days=1), "resolved_at": REFERENCE_NOW - timedelta(days=2), "resolved_by": admin.id, "resolve_note": "关联修复后复扫。", "verified_at": REFERENCE_NOW - timedelta(days=1), "verified_by": admin.id, "verify_result": "GONE", "scan_batch_no": MARKER})
    if _one(db, MasterMergeEvent, tenant_id, domain_code="STUDENT", preview_hash="007govmergepreview") is None:
        db.add(MasterMergeEvent(tenant_id=tenant_id, domain_code="STUDENT", primary_object_id=str(getattr(leave, "student_id", "")), merged_object_id="DUPLICATE-CANDIDATE-ARCHIVED", preview_hash="007govmergepreview", references_json={"previewOnly": True, "referencingTables": 0}, status="REJECTED", reason="候选记录已确认不是同一学生，保留主档，不执行合并。", decided_at=REFERENCE_NOW - timedelta(days=6), decided_by=admin.id))

    _put(db, RoleWorkbenchConfig, tenant_id, {"role_code": "COUNSELOR"}, {"title": "辅导员工作台", "subtitle": "待办、风险、谈心与班级学情", "layout_code": "STANDARD", "card_keys_json": ["todo", "risk", "leave"], "quick_entries_json": ["campusService.leave", "studentAffairs.talk"], "alert_keys_json": ["riskOverdue"], "source_profile": "HIGHER_VOCATIONAL", "installed_project_id": project.id, "status": "ENABLED"})

    _put(db, SodRule, tenant_id, {"rule_code": f"{MARKER}-SOD"}, {"role_a": "SCHOOL_ADMIN", "role_b": "FINANCE_AUDITOR", "severity": "HIGH", "reason": "演示学校权限复核需展示职责分离规则。", "status": "ACTIVE"})
    campaign = _put(db, AccessReviewCampaign, tenant_id, {"campaign_code": f"{MARKER}-ACCESS"}, {"title": "2026 秋季角色权限复核", "scope_json": {"roles": ["COUNSELOR", "SCHOOL_ADMIN"]}, "status": "CLOSED", "due_at": REFERENCE_NOW - timedelta(days=2), "closed_at": REFERENCE_NOW - timedelta(days=1)})
    _put(db, AccessReviewItem, tenant_id, {"campaign_id": campaign.id, "subject_user_id": teacher.id, "role_code": "COUNSELOR"}, {"decision": "KEEP", "decided_by": admin.id, "decided_at": REFERENCE_NOW - timedelta(days=1), "note": "辅导员班级范围与当前任职一致。", "follow_up_change_set_id": None})
    _put(db, SodViolation, tenant_id, {"rule_code": f"{MARKER}-SOD", "subject_user_id": admin.id}, {"detected_roles_json": {"roles": ["SCHOOL_ADMIN"]}, "status": "RESOLVED", "resolution": "未授予财务审核角色，复核无职责冲突。"})
    _put(db, EmergencyAccessSession, tenant_id, {"session_code": f"{MARKER}-EMERGENCY-CLOSED"}, {"subject_user_id": admin.id, "granted_role_code": "SCHOOL_ADMIN", "ticket_ref": "DEMO-007-ACCESS-001", "reason": "演示环境历史紧急访问闭环样例。", "started_at": REFERENCE_NOW - timedelta(days=10), "expires_at": REFERENCE_NOW - timedelta(days=9), "revoked_at": REFERENCE_NOW - timedelta(days=9), "status": "REVOKED"})
    _put(db, AccessDecisionTrace, tenant_id, {"trace_id": f"{MARKER}-TRACE"}, {"subject_user_id": teacher.id, "active_role_code": "COUNSELOR", "action_code": "campusService.leave.approve", "resource_type": "CsLeave", "resource_id_hash": str(leave.id), "decision": "ALLOW", "reason_code": "ROLE_AND_SCOPE", "security_revision": 1, "decision_json": {"role": "ALLOW", "scope": "ALLOW", "result": "ALLOW"}, "expires_at": REFERENCE_NOW + timedelta(days=180)})

    change = _put(db, SecurityChangeSet, tenant_id, {"change_code": f"{MARKER}-SECURITY"}, {"title": "辅导员数据范围策略上线", "status": "ACTIVATED", "risk_level": "HIGH", "reason": "实施验收时启用辅导员班级范围与心理专项拒绝策略。", "impact_json": {"roles": ["COUNSELOR"]}, "submitted_at": REFERENCE_NOW - timedelta(days=29), "reviewed_at": REFERENCE_NOW - timedelta(days=29), "activated_at": REFERENCE_NOW - timedelta(days=29), "created_by_user": admin.id, "reviewed_by_user": admin.id, "activated_by_user": admin.id, "review_note": "007 单管理员演示环境自复核留痕", "self_review_ack": "已核对影响范围", "activated_revision": 1})
    _put(db, SecurityChangeItem, tenant_id, {"change_set_id": change.id, "target_type": "SCOPE_POLICY", "target_id": str(clazz.id)}, {"before_json": {}, "after_json": {"roleCode": "COUNSELOR", "effect": "ALLOW", "classId": clazz.id}, "applied_at": REFERENCE_NOW - timedelta(days=29)})
    _put(db, SecurityActivation, tenant_id, {"revision": 1}, {"change_set_id": change.id, "action": "ACTIVATE", "snapshot_json": {"changeCode": change.change_code, "items": 1}, "actor_user_id": admin.id, "trace_id": f"{MARKER}-SEC-ACT"})

    # 消息、通知、材料均关联同一条真实请假审批，便于三角色从工作台追溯到审批实例。
    file_row = _put(db, FileObject, tenant_id, {"file_key": f"{MARKER}/leave-approval-evidence.md"}, {
        "file_name": "学生请假审批说明.md", "ext": "md", "mime_type": "text/markdown", "size_bytes": 386,
        "sha256": "007govleaveevidence20260828", "biz_type": "CsLeave", "biz_id": str(leave.id), "owner_user_id": admin.id,
        "visibility": "SCHOOL", "security_level": "NORMAL", "status": "AVAILABLE", "remark": "007 请假审批的可追溯说明材料。",
        "storage_backend": "local", "storage_zone": "ACTIVE", "bucket_name": "sandbox-school", "object_key": f"{MARKER}/leave-approval-evidence.md",
        "storage_verified_at": REFERENCE_NOW, "upload_source": "SYSTEM", "scan_required": True, "scan_status": "PASSED", "scan_attempts": 1,
        "scan_engine": "DEMO-STATIC", "scan_engine_version": "1.0", "scan_signature_version": "2026.08", "scanned_at": REFERENCE_NOW, "available_at": REFERENCE_NOW,
    })
    asset = _put(db, FileAsset, tenant_id, {"asset_code": f"{MARKER}-LEAVE-EVIDENCE"}, {"title": "学生请假审批说明材料", "category_code": "APPROVAL_EVIDENCE", "owner_type": "CsLeave", "owner_id": str(leave.id), "lifecycle_status": "ACTIVE", "version_count": 1, "sensitivity_level": "INTERNAL"})
    version = _put(db, FileVersion, tenant_id, {"asset_id": asset.id, "version_no": 1}, {"file_object_id": file_row.id, "source_channel": "SYSTEM_SEED", "uploader_user_id": str(admin.id), "uploader_name_snapshot": admin.real_name, "submit_comment": "审批说明材料已随演示初始数据生成。", "status": "APPROVED", "is_current": True, "submitted_at": REFERENCE_NOW - timedelta(days=2)})
    asset.current_version_id = version.id
    _put(db, FileScanRecord, tenant_id, {"file_id": file_row.id, "attempt": 1}, {"engine": "DEMO-STATIC", "engine_version": "1.0", "signature_version": "2026.08", "result": "PASSED", "started_at": REFERENCE_NOW - timedelta(days=2), "completed_at": REFERENCE_NOW - timedelta(days=2), "details_json": {"marker": MARKER, "bytesVerified": 386}})
    _put(db, FileUploadSession, tenant_id, {"session_key": f"{MARKER}-FILE-UPLOAD"}, {"file_id": file_row.id, "status": "COMPLETED", "source": "SYSTEM_SEED", "file_name": file_row.file_name, "expected_size": 386, "received_size": 386, "expires_at": REFERENCE_NOW - timedelta(days=2), "completed_at": REFERENCE_NOW - timedelta(days=2), "metadata_json": {"bizType": "CsLeave", "bizId": leave.id}})
    _put(db, FileBinding, tenant_id, {"file_id": file_row.id, "biz_type": "CsLeave", "biz_id": str(leave.id), "relation_type": "APPROVAL_EVIDENCE"}, {"subject_type": "WORKFLOW_INSTANCE", "subject_id": str(instance.id), "batch_id": MARKER, "version_no": 1, "is_current": True, "status": "ACTIVE", "scope_json": {"roles": ["COUNSELOR", "SCHOOL_ADMIN"]}, "asset_id": asset.id, "version_id": version.id, "module_code": "campusService", "student_id": getattr(leave, "student_id", None), "college_id": college.id, "class_id": clazz.id, "data_scope_snapshot_json": {"classId": clazz.id}})
    _put(db, FileRetentionPolicy, tenant_id, {"policy_code": f"{MARKER}-APPROVAL"}, {"module_code": "campusService", "biz_type": "CsLeave", "storage_zone": "ACTIVE", "retention_days": 1095, "cleanup_action": "ARCHIVE_THEN_DELETE_BYTES", "priority": 50, "is_active": True, "description": "请假审批材料按学籍档案口径保存三年。"})
    _put(db, TenantStorageQuota, tenant_id, {}, {"total_quota_bytes": 107374182400, "warning_percent": 80, "hard_limit_enabled": True, "module_quota_json": {"campusService": 10737418240, "graduationDesign": 32212254720}, "description": "007 标准演示学校材料存储配额。"})
    manifest = _put(db, ArchiveManifest, tenant_id, {"module_code": "campusService", "archive_type": "LEAVE_CASE", "target_type": "CsLeave", "target_id": str(leave.id), "revision": 1}, {"status": "FROZEN", "rule_version": "2026.1", "manifest_sha256": "007govleavemanifest", "package_file_id": file_row.id, "created_by_name": admin.real_name, "frozen_at": REFERENCE_NOW - timedelta(days=1)})
    _put(db, ArchiveManifestItem, tenant_id, {"manifest_id": manifest.id, "version_id": version.id, "material_code": "LEAVE_EXPLANATION"}, {"asset_id": asset.id, "file_object_id": file_row.id, "file_name_snapshot": file_row.file_name, "size_snapshot": file_row.size_bytes, "sha256_snapshot": file_row.sha256, "review_status": "APPROVED", "scan_result": "PASSED", "uploader_snapshot": admin.real_name, "submitted_at_snapshot": version.submitted_at, "sort_no": 1})

    campaign = _put(db, MessageCampaign, tenant_id, {"idempotency_key": f"{MARKER}-LEAVE-NOTICE"}, {"title": "待审核：学生请假申请", "content_plain": "您有一条学生请假申请待审核，请在截止时间前办理。", "summary": "请假审批待办提醒", "category": "BUSINESS", "priority": "IMPORTANT", "status": "PUBLISHED", "source_kind": "BUSINESS_EVENT", "source_module": "campusService", "source_biz_type": "CsLeave", "source_biz_id": leave.id, "content_mode": "SHARED", "sender_user_id": admin.id, "sender_context_id": "GLOBAL", "sender_org_id": college.id, "sender_name_snapshot": admin.real_name, "sender_role_snapshot": "SCHOOL_ADMIN", "org_name_snapshot": college.college_name, "publish_mode": "IMMEDIATE", "published_at": REFERENCE_NOW - timedelta(hours=2), "effective_at": REFERENCE_NOW - timedelta(hours=2), "require_ack": True, "pinned": True, "emergency": False, "action_key": "approval.task", "action_params_json": {"instanceId": instance.id}, "workflow_instance_id": instance.id, "recipient_count": 1, "delivered_count": 1, "read_count": 0, "ack_count": 0, "failure_count": 0, "content_version": 1, "audience_fingerprint": f"user:{teacher.id}", "channels_json": ["IN_APP"], "remark": "007 工作台可点击的真实业务提醒。", "ack_deadline_at": REFERENCE_NOW + timedelta(hours=18), "delivery_mode": "SYNC"})
    _put(db, MessageAudience, tenant_id, {"campaign_id": campaign.id, "audience_type": "PERSON", "target_id": teacher.id}, {"include_or_exclude": "INCLUDE", "target_code": teacher.login_name, "include_children": False, "rule_json": {"userId": teacher.id}, "rule_version": "1", "resolved_count": 1, "resolved_at": REFERENCE_NOW - timedelta(hours=2)})
    _put(db, MessageAttachment, tenant_id, {"campaign_id": campaign.id, "file_id": file_row.id, "sort_no": 1}, {"file_name_snapshot": file_row.file_name})
    _put(db, MessageChannelDelivery, tenant_id, {"campaign_id": campaign.id, "channel": "IN_APP", "receiver_user_id": teacher.id}, {"status": "SENT", "attempt_count": 1, "provider_request_id": f"{MARKER}-INAPP", "sent_at": REFERENCE_NOW - timedelta(hours=2)})
    _put(db, UnifiedMessage, tenant_id, {"campaign_id": campaign.id, "receiver_user_id": teacher.id, "receiver_context_key": "GLOBAL"}, {"receiver_id": teacher.id, "source_module": "campusService", "source_biz_id": leave.id, "title": campaign.title, "content": campaign.content_plain, "message_type": "TODO_NOTICE", "status": "UNREAD", "remark": "与审批实例及待办关联。", "receiver_type": "STAFF", "priority": "IMPORTANT", "category": "TODO", "delivered_at": REFERENCE_NOW - timedelta(hours=2), "require_ack": True, "action_key": "approval.task", "action_params_json": {"instanceId": instance.id}, "delivery_status": "DELIVERED", "rendered_title": campaign.title, "rendered_content_plain": campaign.content_plain, "sender_org_name_snapshot": college.college_name, "pinned": True})
    _put(db, NotificationTemplate, tenant_id, {"template_code": f"{MARKER}-TODO", "channel": "IN_APP"}, {"title": "待办提醒", "content": "{name}，您有待审核事项：{title}", "enabled": True, "event_code": "TODO_CREATED", "template_version": "2026.1", "receiver_rule_json": {"role": "COUNSELOR"}, "variables_json": ["name", "title"], "deep_link": "/admin/approval", "locked_fields_json": ["eventCode"], "source_profile": "HIGHER_VOCATIONAL", "installed_project_id": project.id})
    task_notice = _put(db, NotificationTask, tenant_id, {"biz_type": "TODO", "template_code": f"{MARKER}-TODO", "receiver_name": teacher.real_name}, {"channel": "IN_APP", "receiver_phone_masked": None, "payload_json": {"name": teacher.real_name, "title": campaign.title}, "status": "SENT", "retry_count": 0})
    if _one(db, NotificationLog, tenant_id, request_id=f"{MARKER}-NOTIFY") is None:
        db.add(NotificationLog(tenant_id=tenant_id, task_id=task_notice.id, biz_type="TODO", channel="IN_APP", provider="in_app", phone_masked=None, result="SUCCESS", reason="已写入教师消息中心", request_id=f"{MARKER}-NOTIFY", sent_at=REFERENCE_NOW - timedelta(hours=2)))
    _put(db, NotificationPreference, tenant_id, {"user_key": str(teacher.id), "category": "todo"}, {"enabled": True})

    db.commit()
    return validate_governance_coverage(db, tenant_id)


def validate_governance_coverage(db, tenant_id: int) -> dict:
    """只读验证该模块最关键的真实关联，不以记录数替代关联完整性。"""
    from app.models import WorkflowDefinition, WorkflowInstance, WorkflowTask
    from app.models.system_implementation import SystemImplementationProject
    from app.models.tenant_capability import TenantCapabilitySetting
    project = _one(db, SystemImplementationProject, tenant_id, project_no=MARKER)
    definition = _one(db, WorkflowDefinition, tenant_id, workflow_code="CS_LEAVE_007")
    instance = _one(db, WorkflowInstance, tenant_id, workflow_code="CS_LEAVE_007")
    task = _one(db, WorkflowTask, tenant_id, instance_id=instance.id) if instance else None
    report = {
        "implementationProject": bool(project), "workflowDefinition": bool(definition),
        "workflowInstance": bool(instance), "workflowTask": bool(task),
        "capabilitySettings": _count(db, TenantCapabilitySetting, tenant_id),
        "workflowProjectLinked": bool(definition and project and definition.installed_project_id == project.id),
        "taskInstanceLinked": bool(task and instance and task.instance_id == instance.id),
    }
    report["passed"] = all((report["implementationProject"], report["workflowDefinition"], report["workflowInstance"], report["workflowTask"], report["capabilitySettings"], report["workflowProjectLinked"], report["taskInstanceLinked"]))
    if not report["passed"]:
        raise RuntimeError(f"007 governance coverage invalid: {report}")
    return report
