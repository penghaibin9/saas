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
  getTenantUsage: (id) => real('tenant-usage', `/platform/tenants/${id}/usage`, {}),

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
  orderAction: (orderNo, action) =>
    real(`order-${action}`, `/platform/orders/${orderNo}/${action}`, { method: 'POST', body: {} }),

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
  putSettings: (settings) => real('settings-put', '/platform/settings', { method: 'PUT', body: { settings } })
}
