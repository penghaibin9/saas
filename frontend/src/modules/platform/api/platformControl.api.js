/**
 * A5 / P0-07 平台总控正式 API 桥。
 *
 * 正式平台控制面只允许读取 /api/v1/platform/* 与真实认证/RBAC；
 * 后端不可达、403/409/5xx 时必须明确失败，禁止回退演示租户、演示 KPI 或浏览器内存写入。
 */
import { request } from '@/services/http/client'

function errorResult(error, fallback = '平台服务请求失败') {
  return {
    code: error?.code || 1,
    bizCode: error?.bizCode || error?.biz,
    data: null,
    message: error?.message || fallback
  }
}

async function real(label, path, options = {}) {
  try {
    const data = await request(path, options)
    return { code: 0, data, message: 'ok' }
  } catch (error) {
    return errorResult(error, `${label}请求失败`)
  }
}

async function getContext() {
  try {
    // /platform/overview 是平台角色强校验门；/authz/me 提供真实当前身份与 dataScope。
    const [overview, me] = await Promise.all([
      request('/platform/overview'),
      request('/authz/me')
    ])
    const role = me?.currentRole || {}
    const roleCode = String(role.roleCode || role.contextType || '').toUpperCase()
    if (!['PLATFORM_SUPER_ADMIN', 'PLATFORM_OWNER'].includes(roleCode)) {
      return { code: 403001, bizCode: 'NO_PERMISSION', data: null, message: '当前身份不是平台超级管理员' }
    }
    return {
      code: 0,
      message: 'ok',
      data: {
        tenantBrandConfig: {
          tenantId: '0',
          operatorName: me.realName || me.loginName || '平台超级管理员',
          schoolName: '',
          platformDisplayName: '高校学生全生命周期管理平台',
          schoolLogo: '',
          schoolBadge: '',
          brandColor: '#2563eb',
          watermarkText: '平台运营数据 · 严禁外传'
        },
        currentRole: {
          userId: me.userId || '',
          userName: me.realName || me.loginName || '平台超级管理员',
          roleCode,
          roleName: role.roleName || role.contextName || '平台超级管理员'
        },
        dataScope: {
          scopeCode: role.dataScope || 'PLATFORM_ALL',
          scopeName: role.scopeLabel || role.dataScope || '全平台租户控制面'
        },
        platformOverview: overview
      }
    }
  } catch (error) {
    return errorResult(error, '平台身份或数据范围加载失败')
  }
}

export const platformControlApi = {
  getContext,

  /* §二 总览 */
  getOverview: () => real('overview', '/platform/overview'),

  /* §三 租户 */
  listTenants: (params = {}) => real('tenants', '/platform/tenants', { params }),
  getTenant: (id) => real('tenant', `/platform/tenants/${id}`),
  createTenant: (body) => real('tenant-create', '/platform/tenants', { method: 'POST', body }),
  updateTenant: (id, body) => real('tenant-update', `/platform/tenants/${id}`, { method: 'PUT', body }),
  tenantAction: (id, action, body = {}) => real(`tenant-${action}`, `/platform/tenants/${id}/${action}`, { method: 'POST', body }),
  resetSandboxData: (id) => real('tenant-reset-sandbox', `/platform/tenants/${id}/reset-sandbox-data`, { method: 'POST', body: {} }),
  getTenantUsage: (id) => real('tenant-usage', `/platform/tenants/${id}/usage`),
  getTenant360: (id) => real('tenant-360', `/platform/tenants/${id}/360`),
  previewTenantTransition: (id, action, body = {}) => real(`tenant-transition-preview-${action}`, `/platform/tenants/${id}/transitions/${action}/preview`, { method: 'POST', body }),
  applyTenantTransition: (id, action, body) => real(`tenant-transition-${action}`, `/platform/tenants/${id}/transitions/${action}`, { method: 'POST', body }),
  getTenantMigrationProgress: () => real('tenant-migration', '/platform/migration/overview'),

  /* §四 套餐 */
  listPackages: () => real('packages', '/platform/packages'),
  updatePackage: (code, body) => real('package-update', `/platform/packages/${code}`, { method: 'PUT', body }),

  /* §五 功能开关 */
  getFeatures: (tenantId) => real('features', `/platform/tenants/${tenantId}/features`),
  putFeatures: (tenantId, features) => real('features-put', `/platform/tenants/${tenantId}/features`, { method: 'PUT', body: features }),

  /* §六 规则中心 */
  getRuleDefaults: () => real('rule-defaults', '/platform/rules/defaults'),
  getRules: (tenantId) => real('rules', `/platform/tenants/${tenantId}/rules`),
  putRules: (tenantId, rules) => real('rules-put', `/platform/tenants/${tenantId}/rules`, { method: 'PUT', body: { rules } }),

  /* §七 流程 */
  getWorkflows: (tenantId) => real('workflows', `/platform/tenants/${tenantId}/workflows`),
  putWorkflow: (tenantId, code, body) => real('workflow-put', `/platform/tenants/${tenantId}/workflows/${code}`, { method: 'PUT', body }),

  /* §八 字典 */
  getDictionaries: (tenantId) => real('dicts', '/platform/dictionaries', { params: tenantId ? { tenantId } : {} }),
  putDictionary: (dictCode, items, tenantId = 0) => real('dict-put', `/platform/dictionaries/${dictCode}`, { method: 'PUT', body: { items, tenantId } }),

  /* §九 品牌 */
  getBrand: (tenantId) => real('brand', `/platform/tenants/${tenantId}/brand`),
  putBrand: (tenantId, brand) => real('brand-put', `/platform/tenants/${tenantId}/brand`, { method: 'PUT', body: brand }),

  /* §十 账号 */
  listUsers: (tenantId) => real('users', `/platform/tenants/${tenantId}/users`),
  createUser: (tenantId, body) => real('user-create', `/platform/tenants/${tenantId}/users`, { method: 'POST', body }),
  userAction: (userId, action) => real(`user-${action}`, `/platform/users/${userId}/${action}`, { method: 'POST', body: {} }),

  /* §十一 订单 */
  listOrders: (params = {}) => real('orders', '/platform/orders', { params }),
  createOrder: (body) => real('order-create', '/platform/orders', { method: 'POST', body }),
  orderAction: (orderNo, action, body) => real(`order-${action}`, `/platform/orders/${orderNo}/${action}`, { method: 'POST', body }),

  /* §十二 公告 */
  listNotices: () => real('notices', '/platform/notices'),
  createNotice: (body) => real('notice-create', '/platform/notices', { method: 'POST', body }),
  noticeAction: (id, action) => real(`notice-${action}`, `/platform/notices/${id}/${action}`, { method: 'POST', body: {} }),

  /* §十三 安全 */
  getSecurity: () => real('security', '/platform/security'),
  putSecurity: (security) => real('security-put', '/platform/security', { method: 'PUT', body: { security } }),

  /* §十四 审计 */
  listAuditLogs: (params = {}) => real('audit', '/platform/audit-logs', { params }),

  /* 系统参数 */
  getSettings: () => real('settings', '/platform/settings'),
  putSettings: (settings) => real('settings-put', '/platform/settings', { method: 'PUT', body: { settings } }),

  /* 文件存储 */
  getFileStorage: () => real('file-storage', '/platform/file-storage'),
  putFileStorage: (config) => real('file-storage-put', '/platform/file-storage', { method: 'PUT', body: { config } }),
  testFileStorage: () => real('file-storage-test', '/platform/file-storage/test', { method: 'POST', body: {} }),

  /* PLAT-15 平台职责、临时提升与受控协助 */
  listAccessAssignments: () => real('access-assignments', '/platform/access-assignments'),
  saveAccessAssignment: (body) => real('access-assignment-save', '/platform/access-assignments', { method: 'POST', body }),
  listElevationSessions: () => real('elevation-sessions', '/platform/elevation-sessions'),
  createElevationSession: (body) => real('elevation-session-create', '/platform/elevation-sessions', { method: 'POST', body }),
  listSupportSessions: (params = {}) => real('support-sessions', '/platform/support-sessions', { params }),
  createSupportSession: (body) => real('support-session-create', '/platform/support-sessions', { method: 'POST', body }),
  listAccessReviews: () => real('access-reviews', '/platform/access-reviews'),

  /* PLAT-03 商业授权与真实消费对账 */
  listReconciliations: (params = {}) => real('reconciliations', '/platform/reconciliations', { params }),

  /* PLAT-08 服务目录、依赖与租户影响地图 */
  getServiceCatalogOverview: () => real('service-catalog-overview', '/platform/services/overview'),
  bootstrapServiceCatalog: () => real('service-catalog-bootstrap', '/platform/services/bootstrap', { method: 'POST', body: {} }),
  listServices: () => real('services-list', '/platform/services'),
  saveService: (body) => real('service-save', '/platform/services', { method: 'POST', body }),
  listServiceDependencies: (serviceCode) => real('service-dependencies', '/platform/service-dependencies', { params: serviceCode ? { serviceCode } : {} }),
  addServiceDependency: (body) => real('service-dependency-add', '/platform/service-dependencies', { method: 'POST', body }),
  removeServiceDependency: (id) => real('service-dependency-remove', `/platform/service-dependencies/${id}`, { method: 'DELETE' }),
  getServiceImpact: (serviceCode, releaseId) => real('service-impact', '/platform/service-impact', { params: { serviceCode, releaseId: releaseId || undefined } }),

  /* PLAT-06 公共底座运行中心 */
  getFoundationOverview: () => real('foundation-overview', '/platform/foundations/overview'),

  /* PLAT-14 数据治理、集成目录与合规证据 */
  getPlatformGovernanceOverview: () => real('governance-overview', '/platform/governance/overview'),

  /* PLAT-05 客户健康、工单、培训与续费 */
  getCustomerSuccessOverview: () => real('customer-success-overview', '/platform/customer-success/overview'),
  getTenantHealthScore: (tenantId) => real('tenant-health-score', `/platform/tenants/${tenantId}/health-score`),
  listSupportTickets: (params = {}) => real('support-tickets-list', '/platform/support-tickets', { params }),
  createSupportTicket: (body) => real('support-ticket-create', '/platform/support-tickets', { method: 'POST', body }),
  transitionSupportTicket: (ticketId, body) => real('support-ticket-transition', `/platform/support-tickets/${ticketId}/transition`, { method: 'POST', body }),
  listTrainings: (params = {}) => real('trainings-list', '/platform/trainings', { params }),
  createTraining: (body) => real('training-create', '/platform/trainings', { method: 'POST', body }),
  completeTraining: (trainingId, body) => real('training-complete', `/platform/trainings/${trainingId}/complete`, { method: 'POST', body }),
  listRenewalTasks: (params = {}) => real('renewal-tasks-list', '/platform/renewal-tasks', { params }),
  createRenewalTask: (body) => real('renewal-task-create', '/platform/renewal-tasks', { method: 'POST', body }),
  transitionRenewalTask: (taskId, body) => real('renewal-task-transition', `/platform/renewal-tasks/${taskId}/transition`, { method: 'POST', body }),

  /* PLAT-04 租户自动开通、初始化与上线验收 */
  getProvisioningOverview: () => real('provisioning-overview', '/platform/provisioning-jobs/overview'),
  listProvisioningJobs: () => real('provisioning-jobs-list', '/platform/provisioning-jobs'),
  getProvisioningJob: (jobId) => real('provisioning-job-get', `/platform/provisioning-jobs/${jobId}`),
  startProvisioningJob: (body) => real('provisioning-job-start', '/platform/provisioning-jobs', { method: 'POST', body }),
  resumeProvisioningJob: (jobId) => real('provisioning-job-resume', `/platform/provisioning-jobs/${jobId}/resume`, { method: 'POST', body: {} }),
  retryProvisioningStep: (jobId, stepCode) => real('provisioning-job-retry-step', `/platform/provisioning-jobs/${jobId}/retry-step`, { method: 'POST', body: { stepCode } }),
  compensateProvisioningStep: (jobId, stepCode, reason) => real('provisioning-job-compensate', `/platform/provisioning-jobs/${jobId}/compensate`, { method: 'POST', body: { stepCode, reason } }),
  flagProvisioningManualReview: (jobId, stepCode, reason) => real('provisioning-job-flag-manual', `/platform/provisioning-jobs/${jobId}/flag-manual-review`, { method: 'POST', body: { stepCode, reason } }),
  cancelProvisioningJob: (jobId, reason) => real('provisioning-job-cancel', `/platform/provisioning-jobs/${jobId}/cancel`, { method: 'POST', body: { reason } }),

  /* PLAT-09 事件、状态页与统一学校通知 */
  getIncidentsOverview: () => real('incidents-overview', '/platform/incidents/overview'),
  listIncidents: (params = {}) => real('incidents-list', '/platform/incidents', { params }),
  getIncident: (incidentId) => real('incident-get', `/platform/incidents/${incidentId}`),
  createIncident: (body) => real('incident-create', '/platform/incidents', { method: 'POST', body }),
  getIncidentAffectedTenants: (incidentId) => real('incident-affected-tenants', `/platform/incidents/${incidentId}/affected-tenants`),
  transitionIncidentStatus: (incidentId, status) => real('incident-status', `/platform/incidents/${incidentId}/status`, { method: 'POST', body: { status } }),
  addIncidentUpdate: (incidentId, body) => real('incident-update-add', `/platform/incidents/${incidentId}/updates`, { method: 'POST', body }),
  publishIncidentUpdate: (incidentId, updateId) => real('incident-update-publish', `/platform/incidents/${incidentId}/updates/${updateId}/publish`, { method: 'POST', body: {} }),
  requestIncidentProblemConversion: (incidentId) => real('incident-problem-conversion', `/platform/incidents/${incidentId}/request-problem-conversion`, { method: 'POST', body: {} }),

  /* PLAT-10 问题管理、已知错误与事故复盘 */
  getProblemsOverview: () => real('problems-overview', '/platform/problems/overview'),
  listProblems: (params = {}) => real('problems-list', '/platform/problems', { params }),
  getProblem: (problemId) => real('problem-get', `/platform/problems/${problemId}`),
  createProblem: (body) => real('problem-create', '/platform/problems', { method: 'POST', body }),
  updateProblemRootCause: (problemId, body) => real('problem-root-cause-update', `/platform/problems/${problemId}/root-cause`, { method: 'PUT', body }),
  transitionProblem: (problemId, body) => real('problem-transition', `/platform/problems/${problemId}/status`, { method: 'POST', body }),
  linkProblemPermanentFix: (problemId, body) => real('problem-permanent-fix-link', `/platform/problems/${problemId}/permanent-fix`, { method: 'POST', body }),
  createPostmortem: (problemId, body) => real('postmortem-create', `/platform/problems/${problemId}/postmortems`, { method: 'POST', body }),
  publishPostmortem: (postmortemId, body) => real('postmortem-publish', `/platform/postmortems/${postmortemId}/publish`, { method: 'POST', body }),

  /* PLAT-13 租户用量、容量、成本与公平使用 */
  getFairUseOverview: () => real('fair-use-overview', '/platform/fair-use/overview'),
  getTenantUsageSnapshots: (tenantId, days) => real('tenant-usage-snapshots', `/platform/tenants/${tenantId}/usage-snapshots`, { params: { days } }),
  captureTenantUsageSnapshot: (tenantId) => real('tenant-usage-capture', `/platform/tenants/${tenantId}/usage-snapshots/capture`, { method: 'POST', body: {} }),
  getTenantFairUseLimits: (tenantId) => real('tenant-fair-use-limits', `/platform/tenants/${tenantId}/fair-use-limits`),
  setTenantFairUseLimit: (tenantId, body) => real('tenant-fair-use-limit-set', `/platform/tenants/${tenantId}/fair-use-limits`, { method: 'PUT', body }),
  evaluateTenantFairUse: (tenantId) => real('tenant-fair-use-evaluate', `/platform/tenants/${tenantId}/fair-use/evaluate`, { method: 'POST', body: {} }),
  listFairUseViolations: (params = {}) => real('fair-use-violations', '/platform/fair-use/violations', { params }),

  /* PLAT-12 备份恢复验证与灾备 */
  getDisasterRecoveryOverview: () => real('disaster-recovery-overview', '/platform/disaster-recovery/overview'),
  listBackupEvidence: (params = {}) => real('backup-evidence-list', '/platform/backup-evidence', { params }),
  createBackupEvidence: (body) => real('backup-evidence-create', '/platform/backup-evidence', { method: 'POST', body }),
  runSchemaIntegrityCheck: () => real('schema-integrity-check', '/platform/disaster-recovery/schema-check', { method: 'POST', body: {} }),
  listRestoreDrills: () => real('restore-drills-list', '/platform/restore-drills'),
  createRestoreDrill: (body) => real('restore-drill-create', '/platform/restore-drills', { method: 'POST', body }),

  /* PLAT-11 变更、发布、兼容性、灰度与回滚 */
  getChangesOverview: () => real('changes-overview', '/platform/changes/overview'),
  listChanges: (params = {}) => real('changes-list', '/platform/changes', { params }),
  getChange: (changeId) => real('change-get', `/platform/changes/${changeId}`),
  createChange: (body) => real('change-create', '/platform/changes', { method: 'POST', body }),
  assessChange: (changeId) => real('change-assess', `/platform/changes/${changeId}/assess`, { method: 'POST', body: {} }),
  approveChange: (changeId, reason) => real('change-approve', `/platform/changes/${changeId}/approve`, { method: 'POST', body: { reason } }),
  scheduleChange: (changeId, scheduledAt) => real('change-schedule', `/platform/changes/${changeId}/schedule`, { method: 'POST', body: { scheduledAt } }),
  startChangeWave: (changeId, waveNo, tenantIds) => real('change-wave-start', `/platform/changes/${changeId}/start-wave`, { method: 'POST', body: { waveNo, tenantIds } }),
  reportChangeWave: (changeId, waveNo, status, error) => real('change-wave-report', `/platform/changes/${changeId}/waves/${waveNo}/report`, { method: 'POST', body: { status, error } }),
  verifyChange: (changeId) => real('change-verify', `/platform/changes/${changeId}/verify`, { method: 'POST', body: {} }),
  failChange: (changeId, reason) => real('change-fail', `/platform/changes/${changeId}/fail`, { method: 'POST', body: { reason } }),
  rollbackChange: (changeId, reason) => real('change-rollback', `/platform/changes/${changeId}/rollback`, { method: 'POST', body: { reason } }),
  listMaintenanceWindows: () => real('maintenance-windows-list', '/platform/maintenance-windows'),
  createMaintenanceWindow: (body) => real('maintenance-window-create', '/platform/maintenance-windows', { method: 'POST', body })
}

export default platformControlApi
