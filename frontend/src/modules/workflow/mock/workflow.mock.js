/**
 * 11 权限与流程中心 — mock 数据源（唯一入口，页面禁止直引）
 * 边界：不伪造其他业务模块正文详情，业务对象只用
 * businessModule/businessType/businessId/title/initiator/currentNode/currentAssignee/status/records。
 * 接入场景样例覆盖：INTERNSHIP(internship_apply/weekly_report)、GRADUATION(material_review)、
 * ONBOARDING(student_material)、STUDENT(profile_change)。
 */
import {
  WORKFLOW_MODULE_CODE as M,
  PROCESS_STATUS,
  TASK_STATUS,
  PROCESS_INSTANCE_STATUS,
  NODE_TYPE,
  ROLE_CODE,
  DATA_SCOPE,
  PERMISSION_TYPE,
  LICENSE_VIEW_STATE,
  APPROVAL_ACTION
} from '../constants/workflow.constants'

/* ---------------- 结构化节点工厂 ---------------- */
const node = (id, name, type, opt = {}) => ({
  nodeId: id,
  nodeName: name,
  nodeType: type,
  candidateRoles: opt.roles || [],
  candidateUsers: opt.users || [],
  allowReject: opt.allowReject ?? type === NODE_TYPE.APPROVAL,
  allowWithdraw: opt.allowWithdraw ?? false,
  allowTransfer: opt.allowTransfer ?? false,
  requireComment: opt.requireComment ?? false,
  commentMinLength: opt.commentMinLength ?? 0,
  nextNodeIds: opt.next || []
})

/* ---------------- 流程模板（启用/停用/草稿） ---------------- */
export const processTemplates = [
  {
    templateId: 'tpl-001',
    templateCode: 'INTERNSHIP_APPLY',
    templateName: '岗位实习申请审批流',
    moduleCode: M.INTERNSHIP,
    businessType: 'internship_apply',
    version: 3,
    status: PROCESS_STATUS.ENABLED,
    publishedAt: '2026-06-20 10:00',
    updatedAt: '2026-06-28 15:30',
    updatedBy: '系统管理员',
    nodes: [
      node('n1', '学生提交', NODE_TYPE.START, { roles: [ROLE_CODE.STUDENT], allowWithdraw: true, next: ['n2'] }),
      node('n2', '指导教师审核', NODE_TYPE.APPROVAL, { roles: [ROLE_CODE.TEACHER], requireComment: false, allowTransfer: true, next: ['n3'] }),
      node('n3', '学院审核', NODE_TYPE.APPROVAL, { roles: [ROLE_CODE.COLLEGE_ADMIN], requireComment: true, commentMinLength: 5, next: ['n4'] }),
      node('n4', '辅导员抄送', NODE_TYPE.CC, { roles: [ROLE_CODE.COUNSELOR], next: ['n5'] }),
      node('n5', '结束', NODE_TYPE.END)
    ]
  },
  {
    templateId: 'tpl-002',
    templateCode: 'INTERNSHIP_WEEKLY_REPORT',
    templateName: '实习周报批阅流',
    moduleCode: M.INTERNSHIP,
    businessType: 'weekly_report',
    version: 2,
    status: PROCESS_STATUS.ENABLED,
    publishedAt: '2026-06-12 09:00',
    updatedAt: '2026-06-12 09:00',
    updatedBy: '系统管理员',
    nodes: [
      node('n1', '学生提交周报', NODE_TYPE.START, { roles: [ROLE_CODE.STUDENT], allowWithdraw: true, next: ['n2'] }),
      node('n2', '指导教师批阅', NODE_TYPE.APPROVAL, { roles: [ROLE_CODE.TEACHER], requireComment: false, next: ['n3'] }),
      node('n3', '结束', NODE_TYPE.END)
    ]
  },
  {
    templateId: 'tpl-003',
    templateCode: 'GD_MATERIAL_REVIEW',
    templateName: '毕业设计材料审阅流',
    moduleCode: M.GRADUATION,
    businessType: 'material_review',
    version: 1,
    status: PROCESS_STATUS.ENABLED,
    publishedAt: '2026-06-25 14:00',
    updatedAt: '2026-07-01 11:20',
    updatedBy: '教务管理员',
    nodes: [
      node('n1', '学生提交材料', NODE_TYPE.START, { roles: [ROLE_CODE.STUDENT], allowWithdraw: true, next: ['n2'] }),
      node('n2', '指导教师审阅', NODE_TYPE.APPROVAL, { roles: [ROLE_CODE.TEACHER], requireComment: true, commentMinLength: 5, next: ['n3'] }),
      node('n3', '是否需要学院复核', NODE_TYPE.CONDITION, { next: ['n4', 'n5'] }),
      node('n4', '学院复核', NODE_TYPE.APPROVAL, { roles: [ROLE_CODE.COLLEGE_ADMIN], next: ['n5'] }),
      node('n5', '结束', NODE_TYPE.END)
    ]
  },
  {
    templateId: 'tpl-004',
    templateCode: 'ONBOARDING_MATERIAL',
    templateName: '迎新入学材料审核流',
    moduleCode: M.ONBOARDING,
    businessType: 'student_material',
    version: 1,
    status: PROCESS_STATUS.DISABLED,
    publishedAt: '2026-05-10 09:00',
    updatedAt: '2026-06-01 16:00',
    updatedBy: '系统管理员',
    nodes: [
      node('n1', '新生提交材料', NODE_TYPE.START, { roles: [ROLE_CODE.STUDENT], next: ['n2'] }),
      node('n2', '辅导员初审', NODE_TYPE.APPROVAL, { roles: [ROLE_CODE.COUNSELOR], next: ['n3'] }),
      node('n3', '学院终审', NODE_TYPE.APPROVAL, { roles: [ROLE_CODE.COLLEGE_ADMIN], next: ['n4'] }),
      node('n4', '结束', NODE_TYPE.END)
    ]
  },
  {
    templateId: 'tpl-005',
    templateCode: 'STUDENT_PROFILE_CHANGE',
    templateName: '学生主档信息变更审批流',
    moduleCode: M.STUDENT,
    businessType: 'profile_change',
    version: 1,
    status: PROCESS_STATUS.DRAFT,
    publishedAt: '',
    updatedAt: '2026-07-02 10:00',
    updatedBy: '系统管理员',
    nodes: [
      node('n1', '学生发起变更', NODE_TYPE.START, { roles: [ROLE_CODE.STUDENT], allowWithdraw: true, next: ['n2'] }),
      node('n2', '辅导员审核', NODE_TYPE.APPROVAL, { roles: [ROLE_CODE.COUNSELOR], requireComment: true, commentMinLength: 5, next: ['n3'] }),
      node('n3', '学校管理员终审', NODE_TYPE.APPROVAL, { roles: [ROLE_CODE.SCHOOL_ADMIN], next: ['n4'] }),
      node('n4', '结束', NODE_TYPE.END)
    ]
  }
]

/* ---------------- 审批记录工厂 ---------------- */
let recSeq = 100
const rec = (time, operator, action, comment = '', nodeName = '') => ({
  recordId: `rec-${recSeq++}`,
  time,
  operator,
  action,
  comment,
  nodeName
})

/* ---------------- 审批任务（覆盖全部状态） ---------------- */
export const approvalTasks = [
  {
    taskId: 'task-001',
    title: '实习申请：华信智能科技·前端开发实习生',
    businessModule: M.INTERNSHIP,
    businessType: 'internship_apply',
    businessId: 'apply-2026-0301',
    templateId: 'tpl-001',
    templateName: '岗位实习申请审批流',
    initiator: '学生-王同学',
    initiatorRole: ROLE_CODE.STUDENT,
    currentNode: '学院审核',
    currentAssignee: '二级学院管理员',
    status: TASK_STATUS.PENDING,
    submittedAt: '2026-07-01 09:20',
    updatedAt: '2026-07-01 16:40',
    records: [
      rec('2026-07-01 09:20', '学生-王同学', APPROVAL_ACTION.SUBMIT, '', '学生提交'),
      rec('2026-07-01 16:40', '指导教师-刘老师', APPROVAL_ACTION.APPROVE, '同意，岗位与专业匹配', '指导教师审核')
    ]
  },
  {
    taskId: 'task-002',
    title: '第 4 周实习周报批阅',
    businessModule: M.INTERNSHIP,
    businessType: 'weekly_report',
    businessId: 'report-2026-w4-017',
    templateId: 'tpl-002',
    templateName: '实习周报批阅流',
    initiator: '学生-陈同学',
    initiatorRole: ROLE_CODE.STUDENT,
    currentNode: '指导教师批阅',
    currentAssignee: '指导教师',
    status: TASK_STATUS.PENDING,
    submittedAt: '2026-07-02 08:10',
    updatedAt: '2026-07-02 08:10',
    records: [rec('2026-07-02 08:10', '学生-陈同学', APPROVAL_ACTION.SUBMIT, '', '学生提交周报')]
  },
  {
    taskId: 'task-003',
    title: '毕业设计开题报告审阅',
    businessModule: M.GRADUATION,
    businessType: 'material_review',
    businessId: 'material-gd-0092',
    templateId: 'tpl-003',
    templateName: '毕业设计材料审阅流',
    initiator: '学生-李同学',
    initiatorRole: ROLE_CODE.STUDENT,
    currentNode: '结束',
    currentAssignee: '',
    status: TASK_STATUS.APPROVED,
    submittedAt: '2026-06-28 10:00',
    updatedAt: '2026-06-29 15:00',
    records: [
      rec('2026-06-28 10:00', '学生-李同学', APPROVAL_ACTION.SUBMIT, '', '学生提交材料'),
      rec('2026-06-29 15:00', '指导教师-王老师', APPROVAL_ACTION.APPROVE, '结构完整，同意通过', '指导教师审阅')
    ]
  },
  {
    taskId: 'task-004',
    title: '第 3 周实习周报批阅',
    businessModule: M.INTERNSHIP,
    businessType: 'weekly_report',
    businessId: 'report-2026-w3-017',
    templateId: 'tpl-002',
    templateName: '实习周报批阅流',
    initiator: '学生-陈同学',
    initiatorRole: ROLE_CODE.STUDENT,
    currentNode: '学生提交周报',
    currentAssignee: '学生-陈同学',
    status: TASK_STATUS.REJECTED,
    submittedAt: '2026-06-26 09:00',
    updatedAt: '2026-06-27 10:20',
    records: [
      rec('2026-06-26 09:00', '学生-陈同学', APPROVAL_ACTION.SUBMIT, '', '学生提交周报'),
      rec('2026-06-27 10:20', '指导教师-刘老师', APPROVAL_ACTION.REJECT, '周报内容过于简单，请补充本周工作内容与收获', '指导教师批阅')
    ]
  },
  {
    taskId: 'task-005',
    title: '迎新入学材料审核',
    businessModule: M.ONBOARDING,
    businessType: 'student_material',
    businessId: 'material-ob-2026-114',
    templateId: 'tpl-004',
    templateName: '迎新入学材料审核流',
    initiator: '新生-赵同学',
    initiatorRole: ROLE_CODE.STUDENT,
    currentNode: '学生提交材料',
    currentAssignee: '',
    status: TASK_STATUS.WITHDRAWN,
    submittedAt: '2026-06-20 14:00',
    updatedAt: '2026-06-20 18:30',
    records: [
      rec('2026-06-20 14:00', '新生-赵同学', APPROVAL_ACTION.SUBMIT, '', '新生提交材料'),
      rec('2026-06-20 18:30', '新生-赵同学', APPROVAL_ACTION.WITHDRAW, '材料上传有误，撤回重传', '新生提交材料')
    ]
  },
  {
    taskId: 'task-006',
    title: '学生主档联系方式变更',
    businessModule: M.STUDENT,
    businessType: 'profile_change',
    businessId: 'change-2026-0021',
    templateId: 'tpl-005',
    templateName: '学生主档信息变更审批流',
    initiator: '学生-周同学',
    initiatorRole: ROLE_CODE.STUDENT,
    currentNode: '结束',
    currentAssignee: '',
    status: TASK_STATUS.COMPLETED,
    submittedAt: '2026-06-18 09:00',
    updatedAt: '2026-06-19 11:00',
    records: [
      rec('2026-06-18 09:00', '学生-周同学', APPROVAL_ACTION.SUBMIT, '', '学生发起变更'),
      rec('2026-06-18 15:00', '辅导员-李老师', APPROVAL_ACTION.APPROVE, '已核对证明材料，属实', '辅导员审核'),
      rec('2026-06-19 11:00', '学校管理员', APPROVAL_ACTION.APPROVE, '', '学校管理员终审')
    ]
  }
]

/* ---------------- 流程实例 ---------------- */
export const processInstances = [
  { instanceId: 'ins-001', templateId: 'tpl-001', templateName: '岗位实习申请审批流', businessModule: M.INTERNSHIP, businessType: 'internship_apply', businessId: 'apply-2026-0301', status: PROCESS_INSTANCE_STATUS.RUNNING, currentNode: '学院审核', startedAt: '2026-07-01 09:20', endedAt: '' },
  { instanceId: 'ins-002', templateId: 'tpl-002', templateName: '实习周报批阅流', businessModule: M.INTERNSHIP, businessType: 'weekly_report', businessId: 'report-2026-w4-017', status: PROCESS_INSTANCE_STATUS.RUNNING, currentNode: '指导教师批阅', startedAt: '2026-07-02 08:10', endedAt: '' },
  { instanceId: 'ins-003', templateId: 'tpl-003', templateName: '毕业设计材料审阅流', businessModule: M.GRADUATION, businessType: 'material_review', businessId: 'material-gd-0092', status: PROCESS_INSTANCE_STATUS.APPROVED, currentNode: '结束', startedAt: '2026-06-28 10:00', endedAt: '2026-06-29 15:00' },
  { instanceId: 'ins-004', templateId: 'tpl-002', templateName: '实习周报批阅流', businessModule: M.INTERNSHIP, businessType: 'weekly_report', businessId: 'report-2026-w3-017', status: PROCESS_INSTANCE_STATUS.REJECTED, currentNode: '学生提交周报', startedAt: '2026-06-26 09:00', endedAt: '2026-06-27 10:20' },
  { instanceId: 'ins-005', templateId: 'tpl-005', templateName: '学生主档信息变更审批流', businessModule: M.STUDENT, businessType: 'profile_change', businessId: 'change-2026-0021', status: PROCESS_INSTANCE_STATUS.COMPLETED, currentNode: '结束', startedAt: '2026-06-18 09:00', endedAt: '2026-06-19 11:00' }
]

/* ---------------- 权限点 ---------------- */
let permSeq = 1
const perm = (key, name, moduleCode, type, status = 'ENABLED', description = '') => ({
  permissionId: `perm-${String(permSeq++).padStart(3, '0')}`,
  permissionKey: key,
  permissionName: name,
  moduleCode,
  type,
  status,
  description
})

export const permissions = [
  perm('workflow.center.menu', '权限与流程菜单', M.WORKFLOW, PERMISSION_TYPE.MENU),
  perm('workflow.home.view', '流程中心首页', M.WORKFLOW, PERMISSION_TYPE.PAGE),
  perm('workflow.process.view', '流程模板查看', M.WORKFLOW, PERMISSION_TYPE.PAGE),
  perm('workflow.process.toggle', '流程模板启停', M.WORKFLOW, PERMISSION_TYPE.BUTTON),
  perm('workflow.task.view', '审批任务查看', M.WORKFLOW, PERMISSION_TYPE.PAGE),
  perm('workflow.task.approve', '审批通过', M.WORKFLOW, PERMISSION_TYPE.BUTTON),
  perm('workflow.task.reject', '审批退回', M.WORKFLOW, PERMISSION_TYPE.BUTTON),
  perm('workflow.task.withdraw', '审批撤回', M.WORKFLOW, PERMISSION_TYPE.BUTTON),
  perm('workflow.role.view', '角色查看', M.WORKFLOW, PERMISSION_TYPE.PAGE),
  perm('workflow.role.edit', '角色权限编辑', M.WORKFLOW, PERMISSION_TYPE.BUTTON),
  perm('workflow.permission.view', '权限点查看', M.WORKFLOW, PERMISSION_TYPE.PAGE),
  perm('workflow.permission.toggle', '权限点启停', M.WORKFLOW, PERMISSION_TYPE.BUTTON),
  perm('workflow.audit.view', '审计日志查看', M.WORKFLOW, PERMISSION_TYPE.DATA),
  perm('student.profile.view', '学生主档查看', M.STUDENT, PERMISSION_TYPE.PAGE),
  perm('student.profile.edit', '学生主档编辑', M.STUDENT, PERMISSION_TYPE.BUTTON),
  perm('internship.apply.review', '实习申请审核', M.INTERNSHIP, PERMISSION_TYPE.BUTTON),
  perm('internship.report.review', '实习周报批阅', M.INTERNSHIP, PERMISSION_TYPE.BUTTON),
  perm('internship.report.reject', '实习周报退回', M.INTERNSHIP, PERMISSION_TYPE.BUTTON),
  perm('graduation.topic.approve', '毕设课题审核', M.GRADUATION, PERMISSION_TYPE.BUTTON),
  perm('graduation.material.review', '毕设材料审阅', M.GRADUATION, PERMISSION_TYPE.BUTTON, 'DISABLED', '示例：已停用权限点'),
  perm('onboarding.material.review', '迎新材料审核', M.ONBOARDING, PERMISSION_TYPE.BUTTON, 'DISABLED', '迎新模块未启用')
]

/* ---------------- 角色（7 个，含数据范围与权限绑定） ---------------- */
export const roles = [
  { roleId: 'role-001', roleCode: ROLE_CODE.PLATFORM_OPERATOR, roleName: '平台运营', description: 'SaaS 厂商运营人员，管租户与授权，不看学生业务明细', userCount: 2, dataScope: DATA_SCOPE.ALL, permissionKeys: ['workflow.audit.view'] },
  { roleId: 'role-002', roleCode: ROLE_CODE.SCHOOL_ADMIN, roleName: '学校管理员', description: '校级管理，全部业务模块管理权', userCount: 3, dataScope: DATA_SCOPE.SCHOOL, permissionKeys: permissions.map((p) => p.permissionKey) },
  { roleId: 'role-003', roleCode: ROLE_CODE.COLLEGE_ADMIN, roleName: '二级学院管理员', description: '学院范围内审核与管理', userCount: 8, dataScope: DATA_SCOPE.COLLEGE, permissionKeys: ['workflow.task.view', 'workflow.task.approve', 'workflow.task.reject', 'internship.apply.review', 'graduation.topic.approve', 'onboarding.material.review'] },
  { roleId: 'role-004', roleCode: ROLE_CODE.TEACHER, roleName: '指导教师', description: '指导学生的实习/毕设过程批阅', userCount: 46, dataScope: DATA_SCOPE.ASSIGNED, permissionKeys: ['workflow.task.view', 'workflow.task.approve', 'workflow.task.reject', 'internship.report.review', 'internship.report.reject', 'graduation.material.review'] },
  { roleId: 'role-005', roleCode: ROLE_CODE.COUNSELOR, roleName: '辅导员', description: '班级学生日常管理与流程抄送', userCount: 12, dataScope: DATA_SCOPE.CLASS, permissionKeys: ['workflow.task.view', 'student.profile.view'] },
  { roleId: 'role-006', roleCode: ROLE_CODE.STUDENT, roleName: '学生', description: '本人业务发起与撤回', userCount: 2140, dataScope: DATA_SCOPE.SELF, permissionKeys: ['workflow.task.withdraw', 'student.profile.view'] },
  { roleId: 'role-007', roleCode: ROLE_CODE.ENTERPRISE_MENTOR, roleName: '企业导师', description: '仅授权实习学生的评价与确认（不可见毕设材料）', userCount: 31, dataScope: DATA_SCOPE.ASSIGNED, permissionKeys: ['workflow.task.view'] }
]

/* ---------------- 当前用户 permissionContext（mock，P8 起替换真实来源） ---------------- */
export const currentPermissionContext = {
  userId: 'u-admin-001',
  userName: '学校管理员',
  roleCodes: [ROLE_CODE.SCHOOL_ADMIN],
  schoolId: 'tenant-demo-a',
  schoolName: '演示职业技术学院',
  collegeId: '',
  collegeName: '',
  classId: '',
  modules: [M.WORKFLOW, M.INTERNSHIP, M.GRADUATION, M.STUDENT, M.DASHBOARD],
  permissions: permissions.filter((p) => p.status === 'ENABLED').map((p) => p.permissionKey),
  dataScope: DATA_SCOPE.SCHOOL,
  menuPermissions: ['workflow.center.menu'],
  buttonPermissions: [
    'workflow.process.toggle',
    'workflow.task.approve',
    'workflow.task.reject',
    'workflow.task.withdraw',
    'workflow.role.edit',
    'workflow.permission.toggle'
  ]
}

/* ---------------- 操作审计 ---------------- */
let auditSeq = 1
export const auditLogs = [
  { logId: `audit-${String(auditSeq++).padStart(3, '0')}`, time: '2026-07-01 11:20', operator: '教务管理员', targetType: 'PROCESS_TEMPLATE', targetId: 'tpl-003', action: '更新模板节点', before: 'version=1', after: 'version=1（节点备注调整）' },
  { logId: `audit-${String(auditSeq++).padStart(3, '0')}`, time: '2026-06-27 10:20', operator: '指导教师-刘老师', targetType: 'APPROVAL_TASK', targetId: 'task-004', action: '退回', before: 'PENDING', after: 'REJECTED' },
  { logId: `audit-${String(auditSeq++).padStart(3, '0')}`, time: '2026-06-01 16:00', operator: '系统管理员', targetType: 'PROCESS_TEMPLATE', targetId: 'tpl-004', action: '停用模板', before: 'ENABLED', after: 'DISABLED' }
]

export function appendAuditLog(entry) {
  auditLogs.unshift({
    logId: `audit-${String(auditSeq++).padStart(3, '0')}`,
    time: nowText(),
    ...entry
  })
}

/* ---------------- 模块视图状态（licenseContext 预留关系） ----------------
 * 当前 licenseContext 为预留关系，本次不接真实授权中心（/platform 在 P6-2 落地）。
 * 冻结优先级：租户停用 > 到期只读 > 模块未授权 > 试用限制 > 功能开关 > 角色权限 > 按钮权限 > 数据范围。
 * 本 mock 仅提供 WORKFLOW 模块自身的视图状态，用于页面 readonly / noLicense 演示与验收。
 */
export const licenseState = { viewState: LICENSE_VIEW_STATE.NORMAL }

export function setLicenseViewState(state) {
  licenseState.viewState = state
}

/* ---------------- 模拟开关（错误/空态） ---------------- */
export const mockFlags = { forceError: false, forceEmpty: false }
export function setMockFlags(flags) {
  Object.assign(mockFlags, flags)
}

/* ---------------- 工具 ---------------- */
export function nowText() {
  const d = new Date()
  const p = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`
}
