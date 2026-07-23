"""流程、角色工作台和通知模板预设安装到真实运行主表。"""
from __future__ import annotations

import re
from datetime import datetime

from sqlalchemy import func, select

from app.core.context import current_tenant_id
from app.core.exceptions import AppException
from app.db.session import get_sessionmaker
from app.models import (NotificationTemplate, Role, RoleWorkbenchConfig,
                        SystemImplementationProject, SystemImplementationSection,
                        UserRole, WorkflowDefinition, WorkflowNodeDefinition)
from app.services import audit_log


def _node(code, name, role, scope="ASSIGNED", hours=48, condition=None):
    return {"code": code, "name": name, "role": role, "scope": scope,
            "hours": hours, "condition": condition or {}}


WORKFLOW_PRESETS = (
    {"code": "AFFAIRS_LEAVE", "name": "短期请假审批", "module": "STUDENT_AFFAIRS", "biz": "LEAVE",
     "starters": ["STUDENT"], "nodes": [_node("COUNSELOR_REVIEW", "辅导员审核", "COUNSELOR", "COUNSELOR_CLASSES", 24)]},
    {"code": "AFFAIRS_LEAVE_LONG", "name": "中长期请假审批", "module": "STUDENT_AFFAIRS", "biz": "LEAVE",
     "starters": ["STUDENT"], "nodes": [_node("COUNSELOR_REVIEW", "辅导员审核", "COUNSELOR", "COUNSELOR_CLASSES", 24), _node("COLLEGE_REVIEW", "学院审核", "COLLEGE_ADMIN", "COLLEGE", 48)]},
    {"code": "AFFAIRS_LEAVE_MAJOR", "name": "重大长期请假审批", "module": "STUDENT_AFFAIRS", "biz": "LEAVE",
     "starters": ["STUDENT"], "nodes": [_node("COUNSELOR_REVIEW", "辅导员审核", "COUNSELOR", "COUNSELOR_CLASSES", 24), _node("COLLEGE_REVIEW", "学院审核", "COLLEGE_ADMIN", "COLLEGE", 48), _node("SCHOOL_FINAL", "学工终审", "STUDENT_AFFAIRS_ADMIN", "SCHOOL", 48)]},
    {"code": "AFFAIRS_AID_IDENTIFY", "name": "家庭经济困难认定", "module": "STUDENT_AFFAIRS", "biz": "AID",
     "starters": ["STUDENT"], "nodes": [_node("COUNSELOR_REVIEW", "班级评议/辅导员审核", "COUNSELOR", "COUNSELOR_CLASSES", 48), _node("COLLEGE_REVIEW", "学院审核", "COLLEGE_ADMIN", "COLLEGE", 72), _node("SCHOOL_FINAL", "学工终审", "STUDENT_AFFAIRS_ADMIN", "SCHOOL", 72)]},
    {"code": "AFFAIRS_GRANT", "name": "助学金申请审批", "module": "STUDENT_AFFAIRS", "biz": "FUNDING",
     "starters": ["STUDENT"], "nodes": [_node("COUNSELOR_REVIEW", "辅导员审核", "COUNSELOR", "COUNSELOR_CLASSES", 48), _node("COLLEGE_REVIEW", "学院审核", "COLLEGE_ADMIN", "COLLEGE", 72), _node("SCHOOL_REVIEW", "学工审核", "STUDENT_AFFAIRS_ADMIN", "SCHOOL", 72)]},
    {"code": "AFFAIRS_SCHOLARSHIP", "name": "奖学金申请审批", "module": "STUDENT_AFFAIRS", "biz": "FUNDING",
     "starters": ["STUDENT"], "nodes": [_node("COUNSELOR_REVIEW", "辅导员审核", "COUNSELOR", "COUNSELOR_CLASSES", 48), _node("COLLEGE_REVIEW", "学院审核", "COLLEGE_ADMIN", "COLLEGE", 72), _node("SCHOOL_REVIEW", "学工审核", "STUDENT_AFFAIRS_ADMIN", "SCHOOL", 72)]},
    {"code": "AFFAIRS_DISCIPLINE", "name": "违纪处分审批", "module": "STUDENT_AFFAIRS", "biz": "DISCIPLINE",
     "starters": ["COUNSELOR", "STUDENT_AFFAIRS"], "nodes": [_node("COLLEGE_REVIEW", "学院审核", "COLLEGE_ADMIN", "COLLEGE", 72), _node("SCHOOL_REVIEW", "学工/学校终审", "STUDENT_AFFAIRS_ADMIN", "SCHOOL", 72)]},
    {"code": "AFFAIRS_DISCIPLINE_REMOVE", "name": "处分解除审批", "module": "STUDENT_AFFAIRS", "biz": "DISCIPLINE_REMOVE",
     "starters": ["STUDENT", "COUNSELOR"], "nodes": [_node("COLLEGE_REVIEW", "学院审核", "COLLEGE_ADMIN", "COLLEGE", 72), _node("SCHOOL_REVIEW", "学工终审", "STUDENT_AFFAIRS_ADMIN", "SCHOOL", 72)]},
    {"code": "AC_GRADE_REVIEW", "name": "成绩审核发布", "module": "ACADEMIC_AFFAIRS", "biz": "GRADE_REVIEW",
     "starters": ["ACADEMIC_TEACHER"], "nodes": [_node("COLLEGE_REVIEW", "学院审核", "COLLEGE_ADMIN", "COLLEGE", 48), _node("ACADEMIC_REVIEW", "教务终审", "ACADEMIC_ADMIN", "SCHOOL", 48)]},
    {"code": "AC_GRADE_CHANGE", "name": "成绩更正审批", "module": "ACADEMIC_AFFAIRS", "biz": "GRADE_CHANGE",
     "starters": ["ACADEMIC_TEACHER"], "nodes": [_node("COLLEGE_REVIEW", "学院审核", "COLLEGE_ADMIN", "COLLEGE", 48), _node("ACADEMIC_REVIEW", "教务终审", "ACADEMIC_ADMIN", "SCHOOL", 48)]},
    {"code": "ACAD_SCHEDULE_CHANGE", "name": "调停课审批", "module": "ACADEMIC_AFFAIRS", "biz": "SCHEDULE_CHANGE",
     "starters": ["ACADEMIC_TEACHER"], "nodes": [_node("COLLEGE_REVIEW", "学院审核", "COLLEGE_ADMIN", "COLLEGE", 24), _node("ACADEMIC_REVIEW", "教务终审与冲突校验", "ACADEMIC_ADMIN", "SCHOOL", 24)]},
    {"code": "ACAD_STATUS_CHANGE", "name": "学籍异动审批族", "module": "ACADEMIC_AFFAIRS", "biz": "STATUS_CHANGE",
     "starters": ["STUDENT", "COUNSELOR", "ACADEMIC_ADMIN"], "nodes": [_node("COUNSELOR_REVIEW", "辅导员审核", "COUNSELOR", "COUNSELOR_CLASSES", 48), _node("COLLEGE_REVIEW", "学院审核", "COLLEGE_ADMIN", "COLLEGE", 72), _node("AA_OFFICE_FINAL", "教务处终审", "ACADEMIC_ADMIN", "SCHOOL", 72)]},
    {"code": "ACAD_PROGRAM_APPROVAL", "name": "培养方案审核发布", "module": "ACADEMIC_AFFAIRS", "biz": "PROGRAM",
     "starters": ["GD_MAJOR_ADMIN", "COLLEGE_ADMIN"], "nodes": [_node("COLLEGE_REVIEW", "学院审核", "COLLEGE_ADMIN", "COLLEGE", 72), _node("ACADEMIC_REVIEW", "教务发布", "ACADEMIC_ADMIN", "SCHOOL", 72)]},
    {"code": "INTERNSHIP_APPLICATION", "name": "实习申请审批", "module": "INTERNSHIP", "biz": "INTERNSHIP_APPLICATION",
     "starters": ["STUDENT"], "nodes": [_node("ADVISOR_REVIEW", "指导教师审核", "INTERN_MENTOR", "INTERN_STUDENTS", 48), _node("COLLEGE_REVIEW", "学院审核", "COLLEGE_ADMIN", "COLLEGE", 72)]},
    {"code": "INTERNSHIP_CHANGE", "name": "实习单位/岗位变更", "module": "INTERNSHIP", "biz": "INTERNSHIP_CHANGE",
     "starters": ["STUDENT", "INTERN_MENTOR"], "nodes": [_node("ADVISOR_REVIEW", "指导教师审核", "INTERN_MENTOR", "INTERN_STUDENTS", 48), _node("COLLEGE_REVIEW", "学院审核", "COLLEGE_ADMIN", "COLLEGE", 72), _node("INTERNSHIP_FINAL", "实习管理终审", "STUDENT_AFFAIRS_ADMIN", "SCHOOL", 72)]},
    {"code": "GD_TOPIC_APPROVAL", "name": "毕设题目审核", "module": "GRADUATION", "biz": "GD_TOPIC",
     "starters": ["GD_MENTOR"], "nodes": [_node("MAJOR_REVIEW", "专业审核", "GD_MAJOR_ADMIN", "MAJOR", 72), _node("COLLEGE_REVIEW", "学院审核", "GD_COLLEGE_ADMIN", "COLLEGE", 72)]},
    {"code": "GD_PROPOSAL_APPROVAL", "name": "毕设开题审核", "module": "GRADUATION", "biz": "GD_PROPOSAL",
     "starters": ["STUDENT"], "nodes": [_node("MENTOR_REVIEW", "导师审核", "GD_MENTOR", "GD_STUDENTS", 72), _node("MAJOR_REVIEW", "专业审核", "GD_MAJOR_ADMIN", "MAJOR", 72)]},
    {"code": "GD_FINAL_APPROVAL", "name": "毕设成果与答辩资格审核", "module": "GRADUATION", "biz": "GD_FINAL",
     "starters": ["STUDENT", "GD_MENTOR"], "nodes": [_node("MENTOR_REVIEW", "导师审核", "GD_MENTOR", "GD_STUDENTS", 72), _node("COLLEGE_REVIEW", "学院终审", "GD_COLLEGE_ADMIN", "COLLEGE", 72)]},
)


def _entry(key, label, path, permission):
    return {"key": key, "label": label, "path": path, "permissionCode": permission}


COMMON_CARDS = ["students", "todos", "approvals", "messages", "warning"]
WORKBENCH_PRESETS = (
    ("SCHOOL_ADMIN", "学校管理工作台", [_entry("implementation", "实施与预设", "/admin/system/implementation", "systemAdmin.implementation.view"), _entry("users", "账号管理", "/admin/system/users", "systemAdmin.user.view"), _entry("audit", "安全审计", "/admin/system/logs", "systemAdmin.audit.view")], ["security", "import", "interface"]),
    ("SYS_ADMIN", "系统管理工作台", [_entry("users", "账号管理", "/admin/system/users", "systemAdmin.user.view"), _entry("roles", "角色权限", "/admin/system/roles", "systemAdmin.role.view"), _entry("implementation", "实施中心", "/admin/system/implementation", "systemAdmin.implementation.view")], ["security", "import"]),
    ("SECURITY_AUDITOR", "安全审计工作台", [_entry("audit", "审计日志", "/admin/system/logs", "systemAdmin.audit.view"), _entry("login", "登录日志", "/admin/system/logs?tab=login", "systemAdmin.audit.view")], ["security"]),
    ("LEADER", "领导驾驶舱", [_entry("cockpit", "领导驾驶舱", "/admin/data-center", "dataCenter.dashboard.view"), _entry("approval", "审批中心", "/admin/approval", "approval.dashboard.view")], ["risk", "overdue"]),
    ("COLLEGE_ADMIN", "学院管理工作台", [_entry("approval", "学院待审", "/admin/approval", "approval.dashboard.view"), _entry("students", "学院学生", "/admin/students", "student.list.view")], ["risk", "overdue"]),
    ("ACADEMIC_ADMIN", "教务管理工作台", [_entry("academic", "教务工作台", "/admin/academic-affairs", "academicAffairs.dashboard.view"), _entry("schedule", "排课管理", "/admin/academic-affairs/schedule", "academicAffairs.schedule.view"), _entry("grades", "成绩管理", "/admin/academic-affairs/grades", "academicAffairs.grade.view")], ["schedule", "grade", "exam"]),
    ("STUDENT_AFFAIRS_ADMIN", "学工管理工作台", [_entry("affairs", "学工工作台", "/admin/student-affairs", "studentAffairs.dashboard.view"), _entry("leave", "请假管理", "/admin/student-affairs/leave", "studentAffairs.leave.view"), _entry("risk", "风险处置", "/admin/student-affairs/risks", "studentAffairs.risk.view")], ["risk", "funding", "discipline"]),
    ("COUNSELOR", "辅导员工作台", [_entry("counselor", "辅导员工作台", "/admin/student-affairs/workbench", "studentAffairs.dashboard.view"), _entry("students", "我的学生", "/admin/students", "student.list.view"), _entry("approval", "我的待办", "/admin/approval", "approval.dashboard.view")], ["studentRisk", "leave", "talk"]),
    ("ACADEMIC_TEACHER", "任课教师工作台", [_entry("tasks", "教学任务", "/admin/academic-affairs/teaching-tasks", "academicAffairs.teachingTask.view"), _entry("grades", "成绩录入", "/admin/academic-affairs/grades", "academicAffairs.grade.view"), _entry("change", "调停课", "/admin/academic-affairs/schedule-change", "academicAffairs.scheduleChange.view")], ["course", "grade", "schedule"]),
    ("GD_MENTOR", "毕设导师工作台", [_entry("graduation", "毕设工作台", "/admin/graduation", "graduation.dashboard.view"), _entry("students", "指导学生", "/admin/graduation/students", "graduation.student.view")], ["gdOverdue", "gdReview"]),
    ("INTERN_MENTOR", "实习指导教师工作台", [_entry("internship", "实习工作台", "/admin/internship", "internship.dashboard.view"), _entry("students", "指导学生", "/admin/internship/students", "internship.student.view")], ["checkin", "weekly", "internRisk"]),
    ("DORM_MANAGER", "宿管工作台", [_entry("dorm", "宿舍管理", "/admin/student-affairs/dorm", "studentAffairs.dorm.view"), _entry("checks", "宿舍检查", "/admin/student-affairs/dorm/checks", "studentAffairs.dorm.check.view")], ["dormException"]),
)


NOTIFICATION_PRESETS = (
    ("ACCOUNT_CREATED", "账号已创建", "账号 {accountNo} 已创建，请在首次登录后修改初始密码。", ["accountNo"], "/login", {"type": "ACCOUNT_OWNER"}),
    ("IMPORT_VALIDATED", "导入预检完成", "导入批次 {batchNo} 预检完成：有效 {validCount} 条，错误 {invalidCount} 条。", ["batchNo", "validCount", "invalidCount"], "/admin/system/implementation/mapping", {"role": "SCHOOL_ADMIN"}),
    ("IMPORT_COMPLETED", "导入完成", "导入批次 {batchNo} 已完成，共处理 {totalCount} 条。", ["batchNo", "totalCount"], "/admin/system/implementation/mapping", {"role": "SCHOOL_ADMIN"}),
    ("TODO_CREATED", "您有新的待办", "{bizName} 已提交，请于 {deadline} 前处理。", ["bizName", "deadline"], "/admin/approval", {"type": "TASK_ASSIGNEE"}),
    ("TODO_DUE_SOON", "待办即将超时", "待办 {bizName} 将于 {deadline} 到期，请及时处理。", ["bizName", "deadline"], "/admin/approval", {"type": "TASK_ASSIGNEE"}),
    ("TODO_OVERDUE", "待办已经超时", "待办 {bizName} 已超时，请立即处理。", ["bizName"], "/admin/approval", {"type": "TASK_ASSIGNEE"}),
    ("APPROVAL_APPROVED", "申请已通过", "您提交的 {bizName} 已审核通过。", ["bizName"], "/admin/approval", {"type": "APPLICANT"}),
    ("APPROVAL_RETURNED", "申请已退回", "您提交的 {bizName} 已退回，请登录系统查看意见并修改。", ["bizName"], "/admin/approval", {"type": "APPLICANT"}),
    ("APPROVAL_REJECTED", "申请未通过", "您提交的 {bizName} 未通过，请登录系统查看审核意见。", ["bizName"], "/admin/approval", {"type": "APPLICANT"}),
    ("ACADEMIC_PUBLISHED", "教务信息已发布", "{bizName} 已发布，请登录系统查看。", ["bizName"], "/admin/academic-affairs", {"type": "BUSINESS_AUDIENCE"}),
    ("STUDENT_WARNING", "学生预警提醒", "学生 {studentName} 出现 {warningType}，请按职责范围跟进。", ["studentName", "warningType"], "/admin/student-affairs/risks", {"type": "RESPONSIBLE_TEACHER"}),
    ("INTERNSHIP_EXCEPTION", "实习异常提醒", "学生 {studentName} 出现实习异常，请及时核实处理。", ["studentName"], "/admin/internship", {"type": "INTERNSHIP_ADVISOR"}),
    ("INTERNSHIP_WEEKLY_OVERDUE", "实习周报逾期", "学生 {studentName} 的第 {weekNo} 周周报尚未提交。", ["studentName", "weekNo"], "/admin/internship", {"type": "INTERNSHIP_ADVISOR"}),
    ("GRADUATION_OVERDUE", "毕设任务逾期", "学生 {studentName} 的 {stageName} 材料已逾期。", ["studentName", "stageName"], "/admin/graduation", {"type": "GRADUATION_MENTOR"}),
    ("SECURITY_ALERT", "安全告警", "检测到账号 {accountNo} 的 {alertType}，请及时核查。", ["accountNo", "alertType"], "/admin/system/logs", {"role": "SECURITY_AUDITOR"}),
    ("SERVICE_EXPIRING", "服务即将到期", "服务 {serviceName} 将于 {expireDate} 到期，请提前处理。", ["serviceName", "expireDate"], "/admin/system", {"role": "SCHOOL_ADMIN"}),
)


def _actor(user: dict) -> int | None:
    raw = user.get("userId") or user.get("id")
    try: return int(raw)
    except (TypeError, ValueError): return None


def _tid() -> int:
    value = current_tenant_id()
    if value is None: raise AppException("TENANT_NOT_FOUND", "当前请求没有学校租户上下文")
    return int(value)


def _modules(sections) -> set[str]:
    config = next((x.config_json for x in sections if x.section_code == "module_business"), {}) or {}
    return set(config.get("modules") or [])


def _expanded_workflows():
    for preset in WORKFLOW_PRESETS:
        if preset["code"] != "ACAD_STATUS_CHANGE":
            yield preset
            continue
        for suffix, label in (("SUSPEND", "休学"), ("WITHDRAW", "退学"), ("RESUME", "复学"),
                              ("PRESERVE", "保留学籍"), ("RETAIN", "留级"),
                              ("TRANSFER_MAJOR", "转专业"), ("TRANSFER_CLASS", "转班")):
            yield {**preset, "code": f"ACAD_STATUS_{suffix}", "name": f"{label}审批"}


def install_in_session(db, user: dict, project, sections) -> dict:
    tenant_id = int(project.tenant_id); actor = _actor(user); modules = _modules(sections)
    workflow_stats = {"created": 0, "skipped": 0, "nodesCreated": 0}
    for preset in _expanded_workflows():
        if modules and preset["module"] not in modules: continue
        row = db.scalars(select(WorkflowDefinition).where(
            WorkflowDefinition.tenant_id == tenant_id,
            WorkflowDefinition.workflow_code == preset["code"],
            WorkflowDefinition.is_deleted.is_(False))).first()
        if row:
            workflow_stats["skipped"] += 1; continue
        row = WorkflowDefinition(tenant_id=tenant_id, workflow_code=preset["code"],
            workflow_name=preset["name"], source_module=preset["module"], source_biz_type=preset["biz"],
            definition_version="2026.1", status="PENDING_CONFIRMATION", policy_confirmed=False,
            timeout_hours=max(n["hours"] for n in preset["nodes"]), allow_transfer=True,
            allow_reject=True, allow_withdraw=True, starter_role_codes_json=preset["starters"],
            cc_role_codes_json=[], policy_snapshot_json={}, source_profile=project.profile_code,
            installed_project_id=project.id, description="平台推荐模板；学校确认政策后启用",
            created_by=actor, updated_by=actor)
        db.add(row); db.flush(); workflow_stats["created"] += 1
        for index, node in enumerate(preset["nodes"], 1):
            db.add(WorkflowNodeDefinition(tenant_id=tenant_id, workflow_definition_id=row.id,
                node_code=node["code"], node_name=node["name"], sequence_no=index,
                approver_role_code=node["role"], assignee_strategy="ROLE_AND_SCOPE",
                data_scope_code=node["scope"], timeout_hours=node["hours"],
                condition_json=node["condition"], status="ACTIVE", created_by=actor, updated_by=actor))
            workflow_stats["nodesCreated"] += 1

    workbench_stats = {"created": 0, "skipped": 0}
    for role_code, title, entries, alerts in WORKBENCH_PRESETS:
        row = db.scalars(select(RoleWorkbenchConfig).where(
            RoleWorkbenchConfig.tenant_id == tenant_id, RoleWorkbenchConfig.role_code == role_code,
            RoleWorkbenchConfig.is_deleted.is_(False))).first()
        if row: workbench_stats["skipped"] += 1; continue
        db.add(RoleWorkbenchConfig(tenant_id=tenant_id, role_code=role_code, title=title,
            subtitle="按当前激活角色与数据范围实时聚合", layout_code="STANDARD",
            card_keys_json=COMMON_CARDS, quick_entries_json=entries, alert_keys_json=alerts,
            source_profile=project.profile_code, installed_project_id=project.id,
            status="ENABLED", created_by=actor, updated_by=actor))
        workbench_stats["created"] += 1

    notification_stats = {"created": 0, "skipped": 0}
    for code, title, content, variables, link, receiver in NOTIFICATION_PRESETS:
        row = db.scalars(select(NotificationTemplate).where(
            NotificationTemplate.tenant_id == tenant_id,
            NotificationTemplate.template_code == code, NotificationTemplate.channel == "IN_APP",
            NotificationTemplate.is_deleted.is_(False))).first()
        if row: notification_stats["skipped"] += 1; continue
        db.add(NotificationTemplate(tenant_id=tenant_id, template_code=code, event_code=code,
            channel="IN_APP", title=title, content=content, enabled=True, template_version="2026.1",
            receiver_rule_json=receiver, variables_json=variables, deep_link=link,
            locked_fields_json=["template_code", "event_code", "variables_json"],
            source_profile=project.profile_code, installed_project_id=project.id,
            created_by=actor, updated_by=actor))
        notification_stats["created"] += 1

    summary = {"workflows": workflow_stats, "workbenches": workbench_stats,
               "notifications": notification_stats, "workflowPolicyStatus": "PENDING_CONFIRMATION"}
    for section in sections:
        if section.section_code in {"workflow", "menu_workbench", "message_notification"}:
            config = dict(section.config_json or {})
            key = {"workflow": "workflows", "menu_workbench": "workbenches",
                   "message_notification": "notifications"}[section.section_code]
            config["installedSummary"] = summary[key]; config["installedVersion"] = "2026.1"
            section.config_json = config; section.status = "APPLIED"; section.version += 1; section.updated_by = actor
    return summary


def ensure_workflow_enabled(db, tenant_id: int, workflow_code: str) -> None:
    """业务服务启动流程前调用；未安装定义时兼容历史，已安装则必须经学校确认启用。"""
    row = db.scalars(select(WorkflowDefinition).where(
        WorkflowDefinition.tenant_id == tenant_id,
        WorkflowDefinition.workflow_code == workflow_code,
        WorkflowDefinition.is_deleted.is_(False))).first()
    if row and (row.status != "ENABLED" or not row.policy_confirmed):
        raise AppException("DATA_CONFLICT", f"流程“{row.workflow_name}”尚未完成学校政策确认，暂不能发起")


def status(project_id: int) -> dict:
    tenant_id = _tid(); db = get_sessionmaker()()
    try:
        def count(model, *conditions):
            return int(db.scalar(select(func.count(model.id)).where(
                model.tenant_id == tenant_id, model.is_deleted.is_(False), *conditions)) or 0)
        workflows = db.scalars(select(WorkflowDefinition).where(
            WorkflowDefinition.tenant_id == tenant_id,
            WorkflowDefinition.installed_project_id == project_id,
            WorkflowDefinition.is_deleted.is_(False)).order_by(WorkflowDefinition.id)).all()
        workbenches = db.scalars(select(RoleWorkbenchConfig).where(
            RoleWorkbenchConfig.tenant_id == tenant_id,
            RoleWorkbenchConfig.installed_project_id == project_id,
            RoleWorkbenchConfig.is_deleted.is_(False)).order_by(RoleWorkbenchConfig.id)).all()
        notifications = db.scalars(select(NotificationTemplate).where(
            NotificationTemplate.tenant_id == tenant_id,
            NotificationTemplate.installed_project_id == project_id,
            NotificationTemplate.is_deleted.is_(False)).order_by(NotificationTemplate.id)).all()
        workflow_ids = [x.id for x in workflows]
        node_count = int(db.scalar(select(func.count(WorkflowNodeDefinition.id)).where(
            WorkflowNodeDefinition.tenant_id == tenant_id,
            WorkflowNodeDefinition.workflow_definition_id.in_(workflow_ids or [-1]),
            WorkflowNodeDefinition.is_deleted.is_(False))) or 0)
        return {"counts": {"workflows": len(workflows), "workflowNodes": node_count,
                           "workbenches": len(workbenches), "notifications": len(notifications)},
                "workflows": [{"code": x.workflow_code, "name": x.workflow_name, "status": x.status,
                               "policyConfirmed": x.policy_confirmed, "timeoutHours": x.timeout_hours}
                              for x in workflows],
                "workbenches": [{"roleCode": x.role_code, "title": x.title, "subtitle": x.subtitle,
                                  "layoutCode": x.layout_code, "cardKeys": x.card_keys_json or [],
                                  "quickEntries": x.quick_entries_json or [], "alertKeys": x.alert_keys_json or [],
                                  "status": x.status, "version": x.version}
                                 for x in workbenches],
                "notifications": [{"templateCode": x.template_code, "channel": x.channel,
                                    "title": x.title, "content": x.content, "enabled": x.enabled,
                                    "deepLink": x.deep_link, "variables": x.variables_json or [],
                                    "version": x.version}
                                   for x in notifications]}
    finally: db.close()


def confirm_policy(user: dict, project_id: int, body: dict) -> dict:
    if str(body.get("confirmText") or "").strip() != "确认启用学校流程政策":
        raise AppException("VALIDATION_ERROR", "请输入“确认启用学校流程政策”")
    reason = str(body.get("reason") or "").strip()
    if len(reason) < 2: raise AppException("VALIDATION_ERROR", "请填写政策确认说明")
    tenant_id = _tid(); actor = _actor(user); selected = set(body.get("workflowCodes") or [])
    db = get_sessionmaker()()
    try:
        project = db.scalars(select(SystemImplementationProject).where(
            SystemImplementationProject.id == project_id,
            SystemImplementationProject.tenant_id == tenant_id,
            SystemImplementationProject.is_deleted.is_(False))).first()
        if not project: raise AppException("DATA_NOT_FOUND", "实施项目不存在")
        if project.status == "ACCEPTED":
            raise AppException("DATA_CONFLICT", "验收摘要已封板，不能修改流程策略")
        rows = db.scalars(select(WorkflowDefinition).where(
            WorkflowDefinition.tenant_id == tenant_id,
            WorkflowDefinition.installed_project_id == project_id,
            WorkflowDefinition.is_deleted.is_(False))).all()
        if selected:
            unknown = selected - {x.workflow_code for x in rows}
            if unknown: raise AppException("VALIDATION_ERROR", f"流程编码不存在：{','.join(sorted(unknown))}")
        targets = [x for x in rows if not selected or x.workflow_code in selected]
        missing = []
        for flow in targets:
            nodes = db.scalars(select(WorkflowNodeDefinition).where(
                WorkflowNodeDefinition.tenant_id == tenant_id,
                WorkflowNodeDefinition.workflow_definition_id == flow.id,
                WorkflowNodeDefinition.is_deleted.is_(False))).all()
            for node in nodes:
                role = db.scalars(select(Role).where(Role.tenant_id == tenant_id,
                    Role.role_code == node.approver_role_code, Role.is_deleted.is_(False),
                    Role.status == "ACTIVE")).first()
                members = int(db.scalar(select(func.count(UserRole.id)).where(
                    UserRole.tenant_id == tenant_id, UserRole.role_id == role.id,
                    UserRole.is_deleted.is_(False), UserRole.status == "ACTIVE")) or 0) if role else 0
                if not role or members == 0:
                    missing.append({"workflowCode": flow.workflow_code, "nodeCode": node.node_code,
                                    "roleCode": node.approver_role_code,
                                    "reason": "角色不存在" if not role else "角色没有启用成员"})
        if missing:
            raise AppException("DATA_CONFLICT", "流程责任角色尚未就绪，不能启用", {"missingApprovers": missing})
        now = datetime.utcnow()
        for flow in targets:
            flow.status = "ENABLED"; flow.policy_confirmed = True
            flow.policy_confirmed_by = actor; flow.policy_confirmed_at = now
            flow.policy_snapshot_json = {"confirmedAt": str(now), "confirmedBy": actor,
                                         "reason": reason, "definitionVersion": flow.definition_version}
            flow.version += 1; flow.updated_by = actor
        section = db.scalars(select(SystemImplementationSection).where(
            SystemImplementationSection.tenant_id == tenant_id,
            SystemImplementationSection.project_id == project_id,
            SystemImplementationSection.section_code == "workflow",
            SystemImplementationSection.is_deleted.is_(False))).first()
        if section:
            config = dict(section.config_json or {}); config["policyConfirmed"] = True
            config["enabledWorkflowCount"] = len(targets); section.config_json = config
            section.version += 1; section.updated_by = actor
        project.version += 1; project.updated_by = actor; db.commit()
        audit_log.record("IMPLEMENTATION_WORKFLOW_POLICY_CONFIRMED", f"implementation-project:{project_id}",
                         {"workflowCodes": [x.workflow_code for x in targets], "reason": reason})
        return {"enabled": len(targets), "workflowCodes": [x.workflow_code for x in targets],
                "projectVersion": project.version}
    except Exception:
        db.rollback(); raise
    finally: db.close()


def _load_project(db, tenant_id: int, project_id: int):
    row = db.scalars(select(SystemImplementationProject).where(
        SystemImplementationProject.id == project_id,
        SystemImplementationProject.tenant_id == tenant_id,
        SystemImplementationProject.is_deleted.is_(False))).first()
    if not row: raise AppException("DATA_NOT_FOUND", "实施项目不存在")
    if row.status == "ACCEPTED":
        raise AppException("DATA_CONFLICT", "验收摘要已封板，不能修改运行预设")
    return row


def update_workflow(user: dict, project_id: int, workflow_code: str, body: dict) -> dict:
    tenant_id = _tid(); actor = _actor(user); db = get_sessionmaker()()
    try:
        project = _load_project(db, tenant_id, project_id)
        if body.get("projectVersion") is not None and int(body["projectVersion"]) != project.version:
            raise AppException("DATA_CONFLICT", "项目版本已变化，请刷新后再保存流程")
        row = db.scalars(select(WorkflowDefinition).where(
            WorkflowDefinition.tenant_id == tenant_id,
            WorkflowDefinition.installed_project_id == project_id,
            WorkflowDefinition.workflow_code == workflow_code,
            WorkflowDefinition.is_deleted.is_(False))).first()
        if not row: raise AppException("DATA_NOT_FOUND", "流程定义不存在")
        changed_policy = False
        for source, attr in (("workflowName", "workflow_name"), ("timeoutHours", "timeout_hours"),
                             ("allowTransfer", "allow_transfer"), ("allowReject", "allow_reject"),
                             ("allowWithdraw", "allow_withdraw"), ("ccRoleCodes", "cc_role_codes_json")):
            if source not in body: continue
            value = body[source]
            if source == "timeoutHours" and (isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= 720):
                raise AppException("VALIDATION_ERROR", "流程时限须为 1—720 小时")
            if source.startswith("allow") and not isinstance(value, bool):
                raise AppException("VALIDATION_ERROR", f"{source} 必须是布尔值")
            if source == "ccRoleCodes" and not isinstance(value, list):
                raise AppException("VALIDATION_ERROR", "抄送角色必须是数组")
            setattr(row, attr, value); changed_policy = True
        nodes = body.get("nodes")
        if nodes is not None:
            if not isinstance(nodes, list) or not nodes:
                raise AppException("VALIDATION_ERROR", "流程节点必须是非空数组")
            existing = {x.node_code: x for x in db.scalars(select(WorkflowNodeDefinition).where(
                WorkflowNodeDefinition.tenant_id == tenant_id,
                WorkflowNodeDefinition.workflow_definition_id == row.id,
                WorkflowNodeDefinition.is_deleted.is_(False))).all()}
            for index, item in enumerate(nodes, 1):
                node = existing.get(str(item.get("nodeCode") or ""))
                if not node: raise AppException("VALIDATION_ERROR", "不得通过修改接口新增未知流程节点")
                role_code = str(item.get("approverRoleCode") or node.approver_role_code).strip().upper()
                role = db.scalars(select(Role).where(Role.tenant_id == tenant_id,
                    Role.role_code == role_code, Role.is_deleted.is_(False))).first()
                if not role: raise AppException("VALIDATION_ERROR", f"责任角色不存在：{role_code}")
                hours = int(item.get("timeoutHours") or node.timeout_hours)
                if not 1 <= hours <= 720: raise AppException("VALIDATION_ERROR", "节点时限须为 1—720 小时")
                node.sequence_no = index; node.approver_role_code = role_code
                node.data_scope_code = str(item.get("dataScopeCode") or node.data_scope_code).upper()
                node.timeout_hours = hours; node.version += 1; node.updated_by = actor
            changed_policy = True
        if body.get("status") == "DISABLED":
            row.status = "DISABLED"
        elif body.get("status") not in (None, ""):
            raise AppException("VALIDATION_ERROR", "启用流程必须走学校政策确认，修改接口只允许停用")
        if changed_policy:
            row.status = "PENDING_CONFIRMATION"; row.policy_confirmed = False
            row.policy_confirmed_by = None; row.policy_confirmed_at = None; row.policy_snapshot_json = {}
        row.version += 1; row.updated_by = actor; project.version += 1; project.updated_by = actor
        db.commit(); audit_log.record("IMPLEMENTATION_WORKFLOW_UPDATED", f"workflow:{workflow_code}",
                                      {"projectId": project_id, "policyReconfirmationRequired": changed_policy})
        return {"code": row.workflow_code, "name": row.workflow_name, "status": row.status,
                "policyConfirmed": row.policy_confirmed, "projectVersion": project.version}
    except Exception:
        db.rollback(); raise
    finally: db.close()


def update_workbench(user: dict, project_id: int, role_code: str, body: dict) -> dict:
    tenant_id = _tid(); actor = _actor(user); db = get_sessionmaker()()
    try:
        project = _load_project(db, tenant_id, project_id)
        if body.get("projectVersion") is not None and int(body["projectVersion"]) != project.version:
            raise AppException("DATA_CONFLICT", "项目版本已变化，请刷新后再保存工作台")
        row = db.scalars(select(RoleWorkbenchConfig).where(
            RoleWorkbenchConfig.tenant_id == tenant_id,
            RoleWorkbenchConfig.installed_project_id == project_id,
            RoleWorkbenchConfig.role_code == role_code.upper(),
            RoleWorkbenchConfig.is_deleted.is_(False))).first()
        if not row: raise AppException("DATA_NOT_FOUND", "角色工作台不存在")
        mapping = {"title": "title", "subtitle": "subtitle", "layoutCode": "layout_code",
                   "cardKeys": "card_keys_json", "quickEntries": "quick_entries_json",
                   "alertKeys": "alert_keys_json", "status": "status"}
        for key, attr in mapping.items():
            if key not in body: continue
            value = body[key]
            if key in {"cardKeys", "quickEntries", "alertKeys"} and not isinstance(value, list):
                raise AppException("VALIDATION_ERROR", f"{key} 必须是数组")
            if key == "status" and value not in {"ENABLED", "DISABLED"}:
                raise AppException("VALIDATION_ERROR", "工作台状态无效")
            setattr(row, attr, value)
        row.version += 1; row.updated_by = actor; project.version += 1; project.updated_by = actor
        db.commit(); audit_log.record("IMPLEMENTATION_WORKBENCH_UPDATED", f"workbench:{role_code}",
                                      {"projectId": project_id, "keys": sorted(body)})
        return {"roleCode": row.role_code, "title": row.title, "status": row.status,
                "projectVersion": project.version}
    except Exception:
        db.rollback(); raise
    finally: db.close()


def update_notification(user: dict, project_id: int, template_code: str, channel: str, body: dict) -> dict:
    tenant_id = _tid(); actor = _actor(user); db = get_sessionmaker()()
    try:
        project = _load_project(db, tenant_id, project_id)
        if body.get("projectVersion") is not None and int(body["projectVersion"]) != project.version:
            raise AppException("DATA_CONFLICT", "项目版本已变化，请刷新后再保存通知")
        row = db.scalars(select(NotificationTemplate).where(
            NotificationTemplate.tenant_id == tenant_id,
            NotificationTemplate.installed_project_id == project_id,
            NotificationTemplate.template_code == template_code,
            NotificationTemplate.channel == channel.upper(),
            NotificationTemplate.is_deleted.is_(False))).first()
        if not row: raise AppException("DATA_NOT_FOUND", "通知模板不存在")
        title = str(body.get("title", row.title) or "").strip()
        content = str(body.get("content", row.content) or "").strip()
        if not title or not content: raise AppException("VALIDATION_ERROR", "通知标题和正文不能为空")
        allowed = set(row.variables_json or [])
        used = set(re.findall(r"\{([A-Za-z][A-Za-z0-9_]*)\}", content))
        if used - allowed:
            raise AppException("VALIDATION_ERROR", f"正文包含未授权变量：{','.join(sorted(used - allowed))}")
        row.title = title; row.content = content
        if "deepLink" in body: row.deep_link = str(body["deepLink"] or "").strip() or None
        if "enabled" in body:
            if not isinstance(body["enabled"], bool): raise AppException("VALIDATION_ERROR", "enabled 必须是布尔值")
            if row.template_code == "SECURITY_ALERT" and not body["enabled"]:
                raise AppException("VALIDATION_ERROR", "必要安全告警模板不能停用")
            row.enabled = body["enabled"]
        row.version += 1; row.updated_by = actor; project.version += 1; project.updated_by = actor
        db.commit(); audit_log.record("IMPLEMENTATION_NOTIFICATION_UPDATED",
            f"notification-template:{template_code}:{channel}", {"projectId": project_id, "keys": sorted(body)})
        return {"templateCode": row.template_code, "channel": row.channel, "title": row.title,
                "enabled": row.enabled, "projectVersion": project.version}
    except Exception:
        db.rollback(); raise
    finally: db.close()
