/**
 * P6 · 平台总控 API 桥（真实优先 /api/v1/platform/*，失败回退演示数据，页面不白屏）。
 * 契约：所有方法返回 Promise<{ code, data, message }>，code=0 成功。
 * 仅 PLATFORM_SUPER_ADMIN 可用；后端强校验，403 时返回错误消息由页面展示。
 */
import { request, shouldTryReal } from '@/services/http/client'

/* ── 演示兜底数据（后端不可达时用于演示，不写回） ── */
const MOCK_TENANTS = [
  { tenantId: '1000000000000000001', tenantCode: 'demo', tenantName: '示范职业技术学院', status: 'active', environment: 'production', packageCode: 'professional', packageName: '专业版', studentCount: 100, userCount: 20, maxStudents: 30000, maxUsers: 1000, storageLimitMb: 51200, usedStorageMb: 0, expireAt: '2027-07-04T00:00:00', province: '广东省', city: '广州市', contactName: '陈校办', contactPhone: '13549666867' },
  { tenantId: '1000000000000000003', tenantCode: 'demo-school', tenantName: '演示职业技术学院', status: 'active', environment: 'demo', packageCode: 'standard', packageName: '标准版', studentCount: 5, userCount: 4, maxStudents: 10000, maxUsers: 300, storageLimitMb: 20480, usedStorageMb: 0, expireAt: '2027-07-04T00:00:00', province: '广东省', city: '深圳市', contactName: '平台演示', contactPhone: '13549666867' },
  { tenantId: '1000000000000000004', tenantCode: 'trial-school', tenantName: '试点职业技术学院', status: 'trial', environment: 'production', packageCode: 'trial', packageName: '试用版', studentCount: 2, userCount: 1, maxStudents: 200, maxUsers: 20, storageLimitMb: 512, usedStorageMb: 0, expireAt: '2026-07-11T00:00:00' },
  { tenantId: '1000000000000000005', tenantCode: 'expired-school', tenantName: '到期职业技术学院', status: 'expired', environment: 'production', packageCode: 'basic', packageName: '基础版', studentCount: 2, userCount: 1, maxStudents: 3000, maxUsers: 100, storageLimitMb: 5120, usedStorageMb: 0, expireAt: '2026-07-01T00:00:00' },
  { tenantId: '1000000000000000006', tenantCode: 'disabled-school', tenantName: '停用职业技术学院', status: 'disabled', environment: 'production', packageCode: 'basic', packageName: '基础版', studentCount: 2, userCount: 1, maxStudents: 3000, maxUsers: 100, storageLimitMb: 5120, usedStorageMb: 0, expireAt: '2026-12-31T00:00:00' }
]

const MOCK_OVERVIEW = {
  tenantTotal: 6, tenantTrial: 1, tenantActive: 3, tenantExpired: 1, tenantDisabled: 1,
  studentTotal: 111, userTotal: 28, todayLogin: 12, weekLogin: 86, todayImport: 2,
  todayExport: 3, todayUpload: 5, todayApproval: 8, storageUsedMb: 36.2,
  expiringTenants: [{ tenantName: '试点职业技术学院', expireAt: '2026-07-11T00:00:00', daysLeft: 7 }],
  abnormalTenants: [{ tenantName: '到期职业技术学院', status: 'expired' }, { tenantName: '停用职业技术学院', status: 'disabled' }],
  recentAudits: [{ action: 'LOGIN', operator: '平台老板', at: '2026-07-04T09:00:00' }],
  systemHealth: 'UP', dbStatus: 'OK', fileDirStatus: 'OK', todoPending: 25, approvalPending: 20
}

function ok(data) {
  return Promise.resolve({ code: 0, data: JSON.parse(JSON.stringify(data)), message: 'ok（演示数据）' })
}

/** 真实优先；失败回退 mock；无 mock 时返回错误消息（403 等业务错误直接透出，不再回退） */
async function real(label, path, options = {}, mockData = undefined) {
  if (shouldTryReal()) {
    try {
      const data = await request(path, options)
      return { code: 0, data, message: 'ok' }
    } catch (e) {
      if (e.biz) return { code: e.code || 1, data: null, message: e.message }
      // eslint-disable-next-line no-console
      console.warn(`[platformControl] ${label} 回退演示数据：`, e.message)
    }
  }
  if (mockData !== undefined) return ok(mockData)
  return { code: 1, data: null, message: '后端服务不可达，且该操作无演示兜底（写操作仅真实模式可用）' }
}

export const platformControlApi = {
  /* §二 总览 */
  getOverview: () => real('overview', '/platform/overview', {}, MOCK_OVERVIEW),

  /* §三 租户 */
  listTenants: (params = {}) =>
    real('tenants', '/platform/tenants', { params }, { list: MOCK_TENANTS, total: MOCK_TENANTS.length }),
  getTenant: (id) =>
    real('tenant', `/platform/tenants/${id}`, {}, MOCK_TENANTS.find((t) => t.tenantId === String(id)) || MOCK_TENANTS[0]),
  createTenant: (body) => real('tenant-create', '/platform/tenants', { method: 'POST', body }),
  updateTenant: (id, body) => real('tenant-update', `/platform/tenants/${id}`, { method: 'PUT', body }),
  tenantAction: (id, action, body = {}) =>
    real(`tenant-${action}`, `/platform/tenants/${id}/${action}`, { method: 'POST', body }),
  resetSandboxData: (id) =>
    real('tenant-reset-sandbox', `/platform/tenants/${id}/reset-sandbox-data`, { method: 'POST', body: {} }),
  getTenantUsage: (id) => real('tenant-usage', `/platform/tenants/${id}/usage`, {}),
  getTenant360: (id) => real('tenant-360', `/platform/tenants/${id}/360`, {}),
  previewTenantTransition: (id, action, body = {}) =>
    real(`tenant-transition-preview-${action}`, `/platform/tenants/${id}/transitions/${action}/preview`, { method: 'POST', body }),
  applyTenantTransition: (id, action, body) =>
    real(`tenant-transition-${action}`, `/platform/tenants/${id}/transitions/${action}`, { method: 'POST', body }),
  /* 租户数据迁移进度（老系统数据迁移·跨租户只读聚合；无演示兜底，后端不可达时给空列表） */
  getTenantMigrationProgress: () => real('tenant-migration', '/platform/migration/overview', {}, []),

  /* §四 套餐 */
  listPackages: () => real('packages', '/platform/packages', {}, {
    list: [
      { packageCode: 'trial', packageName: '试用版', price: 0, durationDays: 30, maxStudents: 200, maxUsers: 20, storageLimitMb: 512, enabled: true, features: {} },
      { packageCode: 'basic', packageName: '基础版', price: 19800, durationDays: 365, maxStudents: 3000, maxUsers: 100, storageLimitMb: 5120, enabled: true, features: {} },
      { packageCode: 'standard', packageName: '标准版', price: 49800, durationDays: 365, maxStudents: 10000, maxUsers: 300, storageLimitMb: 20480, enabled: true, features: {} },
      { packageCode: 'professional', packageName: '专业版', price: 99800, durationDays: 365, maxStudents: 30000, maxUsers: 1000, storageLimitMb: 51200, enabled: true, features: {} },
      { packageCode: 'private', packageName: '私有化版', price: 0, durationDays: 3650, maxStudents: 100000, maxUsers: 5000, storageLimitMb: 204800, enabled: true, features: {} }
    ]
  }),
  updatePackage: (code, body) => real('package-update', `/platform/packages/${code}`, { method: 'PUT', body }),

  /* §五 功能开关 */
  getFeatures: (tenantId) => real('features', `/platform/tenants/${tenantId}/features`, {}),
  putFeatures: (tenantId, features) =>
    real('features-put', `/platform/tenants/${tenantId}/features`, { method: 'PUT', body: features }),

  /* §六 规则中心 */
  getRuleDefaults: () => real('rule-defaults', '/platform/rules/defaults', {}),
  getRules: (tenantId) => real('rules', `/platform/tenants/${tenantId}/rules`, {}),
  putRules: (tenantId, rules) =>
    real('rules-put', `/platform/tenants/${tenantId}/rules`, { method: 'PUT', body: { rules } }),

  /* §七 流程 */
  getWorkflows: (tenantId) => real('workflows', `/platform/tenants/${tenantId}/workflows`, {}),
  putWorkflow: (tenantId, code, body) =>
    real('workflow-put', `/platform/tenants/${tenantId}/workflows/${code}`, { method: 'PUT', body }),

  /* §八 字典 */
  getDictionaries: (tenantId) =>
    real('dicts', '/platform/dictionaries', { params: tenantId ? { tenantId } : {} }),
  putDictionary: (dictCode, items, tenantId = 0) =>
    real('dict-put', `/platform/dictionaries/${dictCode}`, { method: 'PUT', body: { items, tenantId } }),

  /* §九 品牌 */
  getBrand: (tenantId) => real('brand', `/platform/tenants/${tenantId}/brand`, {}),
  putBrand: (tenantId, brand) =>
    real('brand-put', `/platform/tenants/${tenantId}/brand`, { method: 'PUT', body: brand }),

  /* §十 账号 */
  listUsers: (tenantId) => real('users', `/platform/tenants/${tenantId}/users`, {}),
  createUser: (tenantId, body) =>
    real('user-create', `/platform/tenants/${tenantId}/users`, { method: 'POST', body }),
  userAction: (userId, action) =>
    real(`user-${action}`, `/platform/users/${userId}/${action}`, { method: 'POST', body: {} }),

  /* §十一 订单 */
  listOrders: (params = {}) => real('orders', '/platform/orders', { params }, { list: [], total: 0 }),
  createOrder: (body) => real('order-create', '/platform/orders', { method: 'POST', body }),
  orderAction: (orderNo, action, body) =>
    real(`order-${action}`, `/platform/orders/${orderNo}/${action}`, { method: 'POST', body }),

  /* §十二 公告 */
  listNotices: () => real('notices', '/platform/notices', {}, { list: [] }),
  createNotice: (body) => real('notice-create', '/platform/notices', { method: 'POST', body }),
  noticeAction: (id, action) =>
    real(`notice-${action}`, `/platform/notices/${id}/${action}`, { method: 'POST', body: {} }),

  /* §十三 安全 */
  getSecurity: () => real('security', '/platform/security', {}),
  putSecurity: (security) => real('security-put', '/platform/security', { method: 'PUT', body: { security } }),

  /* §十四 审计 */
  listAuditLogs: (params = {}) =>
    real('audit', '/platform/audit-logs', { params }, { items: [], total: 0, page: 1, pageSize: 20 }),

  /* 系统参数 */
  getSettings: () => real('settings', '/platform/settings', {}),
  putSettings: (settings) => real('settings-put', '/platform/settings', { method: 'PUT', body: { settings } }),

  /* 文件存储（本地 / 腾讯云 COS） */
  getFileStorage: () => real('file-storage', '/platform/file-storage', {}),
  putFileStorage: (config) => real('file-storage-put', '/platform/file-storage', { method: 'PUT', body: { config } }),
  testFileStorage: () => real('file-storage-test', '/platform/file-storage/test', { method: 'POST', body: {} }),

  /* PLAT-15 平台职责、临时提升与受控协助 */
  listAccessAssignments: () => real('access-assignments', '/platform/access-assignments', {}),
  saveAccessAssignment: (body) => real('access-assignment-save', '/platform/access-assignments', { method: 'POST', body }),
  listElevationSessions: () => real('elevation-sessions', '/platform/elevation-sessions', {}),
  createElevationSession: (body) => real('elevation-session-create', '/platform/elevation-sessions', { method: 'POST', body }),
  listSupportSessions: (params = {}) => real('support-sessions', '/platform/support-sessions', { params }),
  createSupportSession: (body) => real('support-session-create', '/platform/support-sessions', { method: 'POST', body }),
  listAccessReviews: () => real('access-reviews', '/platform/access-reviews', {}),

  /* PLAT-03 商业授权与真实消费对账 */
  listReconciliations: (params = {}) => real('reconciliations', '/platform/reconciliations', { params }),

  /* PLAT-08 服务目录、依赖与租户影响地图（新页面，无演示兜底，后端不可达直接报错） */
  getServiceCatalogOverview: () => real('service-catalog-overview', '/platform/services/overview', {}),
  bootstrapServiceCatalog: () => real('service-catalog-bootstrap', '/platform/services/bootstrap', { method: 'POST', body: {} }),
  listServices: () => real('services-list', '/platform/services', {}),
  saveService: (body) => real('service-save', '/platform/services', { method: 'POST', body }),
  listServiceDependencies: (serviceCode) =>
    real('service-dependencies', '/platform/service-dependencies', { params: serviceCode ? { serviceCode } : {} }),
  addServiceDependency: (body) => real('service-dependency-add', '/platform/service-dependencies', { method: 'POST', body }),
  removeServiceDependency: (id) => real('service-dependency-remove', `/platform/service-dependencies/${id}`, { method: 'DELETE' }),
  getServiceImpact: (serviceCode, releaseId) =>
    real('service-impact', '/platform/service-impact', { params: { serviceCode, releaseId: releaseId || undefined } }),

  /* PLAT-06 公共底座运行中心（新页面，无演示兜底） */
  getFoundationOverview: () => real('foundation-overview', '/platform/foundations/overview', {}),

  /* PLAT-14 数据治理、集成目录与合规证据（新页面，无演示兜底） */
  getPlatformGovernanceOverview: () => real('governance-overview', '/platform/governance/overview', {}),

  /* PLAT-05 客户健康、工单、培训与续费（新页面，无演示兜底） */
  getCustomerSuccessOverview: () => real('customer-success-overview', '/platform/customer-success/overview', {}),
  getTenantHealthScore: (tenantId) => real('tenant-health-score', `/platform/tenants/${tenantId}/health-score`, {}),
  listSupportTickets: (params = {}) => real('support-tickets-list', '/platform/support-tickets', { params }),
  createSupportTicket: (body) => real('support-ticket-create', '/platform/support-tickets', { method: 'POST', body }),
  transitionSupportTicket: (ticketId, body) => real('support-ticket-transition', `/platform/support-tickets/${ticketId}/transition`, { method: 'POST', body }),
  listTrainings: (params = {}) => real('trainings-list', '/platform/trainings', { params }),
  createTraining: (body) => real('training-create', '/platform/trainings', { method: 'POST', body }),
  completeTraining: (trainingId, body) => real('training-complete', `/platform/trainings/${trainingId}/complete`, { method: 'POST', body }),
  listRenewalTasks: (params = {}) => real('renewal-tasks-list', '/platform/renewal-tasks', { params }),
  createRenewalTask: (body) => real('renewal-task-create', '/platform/renewal-tasks', { method: 'POST', body }),
  transitionRenewalTask: (taskId, body) => real('renewal-task-transition', `/platform/renewal-tasks/${taskId}/transition`, { method: 'POST', body }),

  /* PLAT-04 租户自动开通、初始化与上线验收（新页面，无演示兜底） */
  getProvisioningOverview: () => real('provisioning-overview', '/platform/provisioning-jobs/overview', {}),
  listProvisioningJobs: () => real('provisioning-jobs-list', '/platform/provisioning-jobs', {}),
  getProvisioningJob: (jobId) => real('provisioning-job-get', `/platform/provisioning-jobs/${jobId}`, {}),
  startProvisioningJob: (body) => real('provisioning-job-start', '/platform/provisioning-jobs', { method: 'POST', body }),
  resumeProvisioningJob: (jobId) => real('provisioning-job-resume', `/platform/provisioning-jobs/${jobId}/resume`, { method: 'POST', body: {} }),
  retryProvisioningStep: (jobId, stepCode) => real('provisioning-job-retry-step', `/platform/provisioning-jobs/${jobId}/retry-step`, { method: 'POST', body: { stepCode } }),
  compensateProvisioningStep: (jobId, stepCode, reason) => real('provisioning-job-compensate', `/platform/provisioning-jobs/${jobId}/compensate`, { method: 'POST', body: { stepCode, reason } }),
  flagProvisioningManualReview: (jobId, stepCode, reason) => real('provisioning-job-flag-manual', `/platform/provisioning-jobs/${jobId}/flag-manual-review`, { method: 'POST', body: { stepCode, reason } }),
  cancelProvisioningJob: (jobId, reason) => real('provisioning-job-cancel', `/platform/provisioning-jobs/${jobId}/cancel`, { method: 'POST', body: { reason } }),

  /* PLAT-09 事件、状态页与统一学校通知（新页面，无演示兜底） */
  getIncidentsOverview: () => real('incidents-overview', '/platform/incidents/overview', {}),
  listIncidents: (params = {}) => real('incidents-list', '/platform/incidents', { params }),
  getIncident: (incidentId) => real('incident-get', `/platform/incidents/${incidentId}`, {}),
  createIncident: (body) => real('incident-create', '/platform/incidents', { method: 'POST', body }),
  getIncidentAffectedTenants: (incidentId) => real('incident-affected-tenants', `/platform/incidents/${incidentId}/affected-tenants`, {}),
  transitionIncidentStatus: (incidentId, status) => real('incident-status', `/platform/incidents/${incidentId}/status`, { method: 'POST', body: { status } }),
  addIncidentUpdate: (incidentId, body) => real('incident-update-add', `/platform/incidents/${incidentId}/updates`, { method: 'POST', body }),
  publishIncidentUpdate: (incidentId, updateId) => real('incident-update-publish', `/platform/incidents/${incidentId}/updates/${updateId}/publish`, { method: 'POST', body: {} }),
  requestIncidentProblemConversion: (incidentId) => real('incident-problem-conversion', `/platform/incidents/${incidentId}/request-problem-conversion`, { method: 'POST', body: {} }),

  /* PLAT-10 问题管理、已知错误与事故复盘（新页面，无演示兜底） */
  getProblemsOverview: () => real('problems-overview', '/platform/problems/overview', {}),
  listProblems: (params = {}) => real('problems-list', '/platform/problems', { params }),
  getProblem: (problemId) => real('problem-get', `/platform/problems/${problemId}`, {}),
  createProblem: (body) => real('problem-create', '/platform/problems', { method: 'POST', body }),
  updateProblemRootCause: (problemId, body) => real('problem-root-cause-update', `/platform/problems/${problemId}/root-cause`, { method: 'PUT', body }),
  transitionProblem: (problemId, body) => real('problem-transition', `/platform/problems/${problemId}/status`, { method: 'POST', body }),
  linkProblemPermanentFix: (problemId, body) => real('problem-permanent-fix-link', `/platform/problems/${problemId}/permanent-fix`, { method: 'POST', body }),
  createPostmortem: (problemId, body) => real('postmortem-create', `/platform/problems/${problemId}/postmortems`, { method: 'POST', body }),
  publishPostmortem: (postmortemId, body) => real('postmortem-publish', `/platform/postmortems/${postmortemId}/publish`, { method: 'POST', body }),

  /* PLAT-11 变更、发布、兼容性、灰度与回滚（新页面，无演示兜底） */
  getChangesOverview: () => real('changes-overview', '/platform/changes/overview', {}),
  listChanges: (params = {}) => real('changes-list', '/platform/changes', { params }),
  getChange: (changeId) => real('change-get', `/platform/changes/${changeId}`, {}),
  createChange: (body) => real('change-create', '/platform/changes', { method: 'POST', body }),
  assessChange: (changeId) => real('change-assess', `/platform/changes/${changeId}/assess`, { method: 'POST', body: {} }),
  approveChange: (changeId, reason) => real('change-approve', `/platform/changes/${changeId}/approve`, { method: 'POST', body: { reason } }),
  scheduleChange: (changeId, scheduledAt) => real('change-schedule', `/platform/changes/${changeId}/schedule`, { method: 'POST', body: { scheduledAt } }),
  startChangeWave: (changeId, waveNo, tenantIds) => real('change-wave-start', `/platform/changes/${changeId}/start-wave`, { method: 'POST', body: { waveNo, tenantIds } }),
  reportChangeWave: (changeId, waveNo, status, error) => real('change-wave-report', `/platform/changes/${changeId}/waves/${waveNo}/report`, { method: 'POST', body: { status, error } }),
  verifyChange: (changeId) => real('change-verify', `/platform/changes/${changeId}/verify`, { method: 'POST', body: {} }),
  failChange: (changeId, reason) => real('change-fail', `/platform/changes/${changeId}/fail`, { method: 'POST', body: { reason } }),
  rollbackChange: (changeId, reason) => real('change-rollback', `/platform/changes/${changeId}/rollback`, { method: 'POST', body: { reason } }),
  listMaintenanceWindows: () => real('maintenance-windows-list', '/platform/maintenance-windows', {}),
  createMaintenanceWindow: (body) => real('maintenance-window-create', '/platform/maintenance-windows', { method: 'POST', body })
}
