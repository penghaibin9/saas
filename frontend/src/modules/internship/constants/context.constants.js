/** 岗位实习前端展示常量。仅用于界面初始态；授权与数据范围始终以后端为准。 */
export const tenantBrandConfig = {
  tenantId: '', schoolName: '学校', platformDisplayName: '学生全生命周期管理平台',
  schoolLogo: '', schoolBadge: '', brandColor: '#2563eb', watermarkText: '内部数据'
}

export const currentRole = { userId: '', userName: '', roleCode: '', roleName: '实习管理员' }
export const dataScope = { scopeCode: '', scopeName: '按服务端授权范围' }

const deny = (reason) => ({ visible: true, allowed: false, reason })
const allow = { visible: true, allowed: true, reason: '' }
// 静态兜底态（离线/取不到 permissionPatterns 时用；正式构建下由 getContext 收紧为禁用）。
export const permissionActions = {
  createBatch: deny('请使用具备批次管理权限的账号'), importStudents: deny('请使用具备导入权限的账号'),
  exportGroup: allow, exportAll: deny('请使用具备全量导出权限的账号'), viewAuditLog: allow,
  createStudent: deny('请使用具备学生管理权限的账号'),
  batchAssignAdvisor: deny('请使用具备指导教师分配权限的账号'), batchRemind: allow,
  batchArchive: deny('请使用具备归档权限的账号'), editStudent: deny('请使用具备学生管理权限的账号'),
  handleException: allow, batchMarkReasonable: allow, exportExceptions: allow,
  reviewReport: allow, batchApproveReports: allow, exportReports: allow,
  manageRisk: allow, exportRiskList: allow, createEnterprise: allow, editEnterprise: allow,
  reviewEnterprise: deny('请使用具备企业审核权限的账号'), cooperationEnterprise: allow,
  blacklistEnterprise: deny('请使用具备企业黑名单权限的账号'), importEnterprises: allow,
  exportEnterprises: allow, manageEnterpriseContact: allow
}

/**
 * permissionActions 各动作 → 后端真实权限码（与 internship 各 router 的 require_permission 一致）。
 * getContext() 拿到 permissionPatterns 后据此逐项判定 allowed（matchPermission），
 * 取代旧的 userType==='TEACHER' 二分猜角色。无 permissionPatterns 时回落到上面的静态兜底态。
 * 权限码来源核验：backend/app/modules/internship/routers/*.py 的 require_permission / _P_* 常量。
 */
export const ACTION_PERMISSION_CODES = {
  createBatch: 'internship.batch.manage',
  importStudents: 'internship.student.manage',
  createStudent: 'internship.student.manage',
  editStudent: 'internship.student.manage',
  batchAssignAdvisor: 'internship.student.manage',
  batchArchive: 'internship.archive.manage',
  exportGroup: 'internship.stats.view', // 工作台“统计报表”快捷入口
  exportAll: 'internship.student.export',
  viewAuditLog: 'internship.match.log.view', // 分配/操作日志
  handleException: 'internship.attendance.review',
  batchMarkReasonable: 'internship.attendance.review',
  exportExceptions: 'internship.attendance.export',
  reviewReport: 'internship.report.review',
  batchApproveReports: 'internship.report.review',
  batchRemind: 'internship.report.review',
  exportReports: 'internship.report.export',
  manageRisk: 'internship.risk.handle',
  exportRiskList: 'internship.risk.export',
  createEnterprise: 'internship.enterprise.manage',
  editEnterprise: 'internship.enterprise.manage',
  reviewEnterprise: 'internship.enterprise.manage',
  cooperationEnterprise: 'internship.enterprise.manage',
  blacklistEnterprise: 'internship.enterprise.manage',
  importEnterprises: 'internship.enterprise.manage',
  exportEnterprises: 'internship.enterprise.export',
  manageEnterpriseContact: 'internship.enterprise.manage'
}

/** 静态兜底态下各动作的无权限提示（derive 时若无 patterns 走此文案）。 */
export const ACTION_DENY_REASONS = {
  createBatch: '请使用具备批次管理权限的账号',
  importStudents: '请使用具备学生管理权限的账号',
  createStudent: '请使用具备学生管理权限的账号',
  editStudent: '请使用具备学生管理权限的账号',
  batchAssignAdvisor: '请使用具备指导教师分配权限的账号',
  batchArchive: '请使用具备归档权限的账号',
  exportGroup: '请使用具备统计查看权限的账号',
  exportAll: '请使用具备全量导出权限的账号',
  viewAuditLog: '请使用具备日志查看权限的账号',
  handleException: '请使用具备考勤处理权限的账号',
  batchMarkReasonable: '请使用具备考勤处理权限的账号',
  exportExceptions: '请使用具备考勤导出权限的账号',
  reviewReport: '请使用具备周报批阅权限的账号',
  batchApproveReports: '请使用具备周报批阅权限的账号',
  batchRemind: '请使用具备周报批阅权限的账号',
  exportReports: '请使用具备周报导出权限的账号',
  manageRisk: '请使用具备风险处置权限的账号',
  exportRiskList: '请使用具备风险导出权限的账号',
  createEnterprise: '请使用具备企业管理权限的账号',
  editEnterprise: '请使用具备企业管理权限的账号',
  reviewEnterprise: '请使用具备企业审核权限的账号',
  cooperationEnterprise: '请使用具备企业管理权限的账号',
  blacklistEnterprise: '请使用具备企业黑名单权限的账号',
  importEnterprises: '请使用具备企业管理权限的账号',
  exportEnterprises: '请使用具备企业导出权限的账号',
  manageEnterpriseContact: '请使用具备企业管理权限的账号'
}

export const statusOptions = {
  internshipStatus: ['PREPARING:准备中', 'READY:待上岗', 'ONBOARD:在岗中', 'ASSESSING:考核中', 'ARCHIVED:已归档'],
  riskLevel: ['LOW:低风险', 'MEDIUM:中风险', 'HIGH:高风险'],
  exceptionType: ['OUT_OF_RANGE:超范围', 'MOCK_LOCATION:疑似定位异常', 'MISSING:缺卡'],
  reportStatus: ['PENDING_REVIEW:待批阅', 'APPROVED:已通过', 'RETURNED:已退回', 'OVERDUE:逾期未交'],
  coopStatus: ['PENDING:待审核', 'ACTIVE:合作中', 'REJECTED:已驳回', 'SUSPENDED:已暂停', 'BLACKLIST:黑名单', 'ARCHIVED:已归档'],
  enterpriseSource: ['SELF_BUILT:自建', 'SCHOOL_ENTERPRISE:校企合作', 'STUDENT_SELF:学生自主', 'RECOMMENDED:推荐'],
  enterpriseIndustry: ['软件:软件', '智能制造:智能制造', '电子商务:电子商务', '现代物流:现代物流'],
  batchStatus: ['DRAFT:草稿', 'RUNNING:进行中', 'CLOSED:已结束', 'ARCHIVED:已归档', 'VOIDED:已作废']
}

Object.keys(statusOptions).forEach((key) => {
  statusOptions[key] = statusOptions[key].map((item) => {
    const i = item.indexOf(':')
    return { value: item.slice(0, i), label: item.slice(i + 1) }
  })
})
