/** 岗位实习前端展示常量。仅用于界面初始态；授权与数据范围始终以后端为准。 */
export const tenantBrandConfig = {
  tenantId: '', schoolName: '学校', platformDisplayName: '学生全生命周期管理平台',
  schoolLogo: '', schoolBadge: '', brandColor: '#2563eb', watermarkText: '内部数据'
}

export const currentRole = { userId: '', userName: '', roleCode: '', roleName: '实习管理员' }
export const dataScope = { scopeCode: '', scopeName: '按服务端授权范围' }

const deny = (reason) => ({ visible: true, allowed: false, reason })
const allow = { visible: true, allowed: true, reason: '' }
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
