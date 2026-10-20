/** Test-only entry. Never imported by src/main.js or the production router. */
import { createApp, h } from 'vue'
import { createRouter, createMemoryHistory, RouterView } from 'vue-router'
import Overview from '../../src/modules/platform/views/control/PlatformControlOverview.vue'
import Tenants from '../../src/modules/platform/views/control/PlatformControlTenants.vue'
import Orders from '../../src/modules/platform/views/control/PlatformControlOrders.vue'
import Detail from '../../src/modules/platform/views/control/PlatformControlTenantDetail.vue'
import { platformControlHardeningApi } from '../../src/modules/platform/api/platformControlHardening.api'
import { setToken } from '../../src/services/http/client'
import { platformControlApi } from '../../src/modules/platform/api/platformControl.api'
import { setPermissionPatterns } from '../../src/security/permissionGate'
import '../../src/styles/tokens.css'

const query = new URLSearchParams(location.search)
const scenario = query.get('case') || 'normal'
const schoolNames = ['星河职业技术学校', '青禾职业中等专业学校', '明德职业技术学校', '云麓职业学校', '远山职业学校', '知行职业学校']
const statuses = ['active', 'trial', 'expired', 'active', 'disabled', 'active']
const tenants = Array.from({ length: scenario === 'long' ? 25 : 6 }, (_, index) => ({
  tenantId: String(1000000000000000003n + BigInt(index)), tenantCode: `VISUAL-${index + 1}`,
  tenantName: scenario === 'long' && index === 0 ? '星河职业技术学校产教融合与数字化校园建设协同服务校区' : schoolNames[index % 6],
  status: statuses[index % 6], environment: 'production', packageName: index % 2 ? '标准版' : '专业版',
  packageCode: index % 2 ? 'standard' : 'professional', expireAt: '2027-08-31', studentCount: 860 + index * 271,
  maxStudents: 3000, userCount: 84 + index * 7, maxUsers: 300, commercialAuthorityVerified: index !== 4,
  commercialAuthoritySource: index === 1 ? 'TRIAL' : 'PAID_ORDER', version: 4
}))
const orders = tenants.map((school, index) => ({ ...school, orderId: String(index + 1), orderNo: `VISUAL-20260907-${String(index + 1).padStart(3, '0')}`,
  amount: ['68000.00', '48000.00', '52000.00'][index % 3], orderType: index % 2 ? 'NEW' : 'RENEW',
  status: ['unpaid', 'paid', 'paid', 'paid', 'cancelled', 'unpaid'][index % 6], version: index === 0 ? 1 : 3,
  activationState: index === 1 ? 'REPAIR_REQUIRED' : 'ACTIVE', repairTaskRequired: index === 1, endAt: '2027-08-31' }))
const overview = {
  tenantTotal: 6, tenantActive: 3, tenantTrial: 1, tenantExpired: 1, tenantDisabled: 1, tenantUnresolved: 0,
  studentTotal: 9225, userTotal: 609, todayLogin: 326, weekLogin: 1840, todayImport: 8, todayExport: 16,
  todayUpload: 42, todayApproval: 28, todoPending: 18, approvalPending: 7, storageUsedBytes: 23622320128,
  systemHealth: 'UP', dbStatus: 'OK',
  dataQuality: { complete: true, sources: Object.fromEntries(['tenantLifecycle', 'fileFoundation', 'serviceCatalog', 'incidents', 'changes', 'customerSuccess'].map(key => [key, { status: 'OK' }])) },
  expiringTenants: [{ ...tenants[1], daysLeft: 7 }, { ...tenants[3], daysLeft: 21 }], abnormalTenants: [tenants[2], tenants[4]],
  operationalRisks: [{ level: 'HIGH', sourceCard: 'INCIDENT', text: '一项服务事件待责任人确认处理结果' }],
  recentAudits: [{ action: 'UPDATE', operator: '运营专员', at: '2026-09-07T09:42:00' }, { action: 'CREATE', operator: '交付专员', at: '2026-09-07T09:18:00' }]
}
if (scenario === 'missing') {
  overview.studentTotal = null; overview.storageUsedBytes = null; overview.expiringTenants = null
  overview.dataQuality.sources.fileFoundation = { status: 'UNKNOWN', message: '文件统计来源未取得' }
}
const calls = []
const copy = value => JSON.parse(JSON.stringify(value))
const ok = data => ({ code: 0, data: copy(data) })
const list = (rows, params = {}) => {
  if (scenario === 'error') return { code: 1, data: null, message: '测试场景：服务读取失败，请重试' }
  const filtered = scenario === 'empty' ? [] : rows.filter(row => (!params.status || row.status === params.status) && (!params.tenantId || row.tenantId === params.tenantId) && (!params.keyword || `${row.tenantName} ${row.tenantCode}`.includes(params.keyword)))
  return ok({ list: filtered, total: filtered.length })
}
// Only this isolated entry replaces API methods. The browser runner rejects all /api network traffic.
platformControlApi.getOverview = async () => scenario === 'error' ? { code: 1, message: '测试场景：总览读取失败，请重试' } : ok(overview)
platformControlApi.listTenants = async params => list(tenants, params)
platformControlApi.listOrders = async params => list(orders, params)
platformControlApi.listPackages = async () => ok({ list: [{ packageCode: 'standard', packageName: '标准版', price: '48000.00', durationDays: 365, enabled: true }] })
platformControlApi.orderAction = async (orderNo, action, body) => {
  calls.push({ orderNo, action, body })
  const row = orders.find(item => item.orderNo === orderNo)
  if (!row || row.version !== body.expectedVersion) return { code: 409, bizCode: 'DATA_CONFLICT' }
  row.status = action === 'cancel' ? 'cancelled' : 'paid'
  row.version += action === 'mark-paid' ? 2 : 1
  row.activationState = 'ACTIVE'; row.repairTaskRequired = false
  return ok({ orderNo, version: row.version, status: row.status, tenantActivated: true, repairTaskRequired: false })
}
// Per-school state belongs only to this network-isolated browser fixture.
const ruleState = new Map(tenants.map(row => [row.tenantId, { tenantId: row.tenantId, overrideVersion: 4,
  rules: { student: { studentNoRequired: true }, file: { uploadMaxSizeMb: 20, allowedFileTypes: ['pdf', 'png'] } }, override: {} }]))
platformControlApi.getTenant = async tenantId => {
  if (scenario === 'error') return { code: 1, message: '测试场景：学校读取失败，请重试' }
  const row = tenants.find(item => item.tenantId === tenantId)
  return row ? ok({ ...row, contactName: '学校联络人', contactPhone: '', province: '湖南省', city: '长沙市',
    tenant360: { tenantId, version: row.version, storage: { commercialStorageLimitBytes: 107374182400, schoolGovernanceQuotaBytes: 53687091200, actualOccupancyBytes: 21474836480 } } }) : { code: 404, message: '学校未找到' }
}
platformControlApi.getRules = async tenantId => ok(ruleState.get(tenantId))
platformControlApi.getFeatures = async tenantId => ok({ tenantId, authoritySource: 'PAID_ORDER', features: scenario === 'empty' ? {} : { academicAffairs: true, internship: true } })
platformControlApi.getWorkflows = async tenantId => ok({ tenantId, workflows: {} })
platformControlApi.getBrand = async tenantId => ok({ tenantId, authority: 'TENANT_BRAND_CONFIG', version: 3, brand: { schoolName: tenants.find(row => row.tenantId === tenantId)?.tenantName, brandColor: '#2563eb', platformDisplayName: '学校数字服务', watermarkText: '内部教学数据' } })
platformControlApi.listUsers = async () => ok({ list: [] })
platformControlApi.previewTenantTransition = async (tenantId, action, body) => {
  const row = tenants.find(item => item.tenantId === tenantId)
  return row && row.version === body.expectedVersion ? ok({ tenantId, action, expectedVersion: row.version, fromStatus: row.status, toStatus: action === 'disable' ? 'disabled' : row.status, warnings: ['学校登录权限将随状态变化，请核对办理对象。'] }) : { code: 409 }
}
platformControlApi.applyTenantTransition = async (tenantId, action, body) => {
  calls.push({ tenantId, action, body })
  const row = tenants.find(item => item.tenantId === tenantId)
  if (!row || row.version !== body.expectedVersion) return { code: 409 }
  row.version++; row.status = action === 'disable' ? 'disabled' : row.status
  return ok({ tenantId, version: row.version, runtimeMaterialized: true, cacheInvalidated: true, cacheRecoveryRequired: false })
}
platformControlHardeningApi.putRules = async (tenantId, patch, expectedVersion, reason) => {
  calls.push({ tenantId, patch, expectedVersion, reason })
  const current = ruleState.get(tenantId)
  if (!current || current.overrideVersion !== expectedVersion) return { code: 409, bizCode: 'DATA_CONFLICT' }
  for (const [group, fields] of Object.entries(patch)) {
    Object.assign(current.rules[group], fields)
    current.override[group] = { ...current.override[group], ...fields }
  }
  current.overrideVersion++
  return ok(current)
}
// Unsigned, test-only in-memory identity; the network guard prevents its use on a backend.
setToken(`visual.${btoa(JSON.stringify({ userId: 'visual-only', userType: query.get('readonly') ? 'PLATFORM_AUDITOR' : 'PLATFORM_OWNER' }))}.not-a-server-token`)
const ctx = { currentRole: { roleName: '平台运营' }, dataScope: { scopeName: '隔离测试学校' } }
setPermissionPatterns(query.get('readonly') ? ['platform.order.view', 'platform.tenant.view', 'platform.control.view'] : ['platform.*'])
const router = createRouter({ history: createMemoryHistory(), routes: [
  { path: '/admin/platform/overview', component: Overview, props: { ctx } },
  { path: '/admin/platform/tenants', component: Tenants },
  { path: '/admin/platform/orders', component: Orders },
  { path: '/admin/platform/tenants/:tenantId', component: Detail },
  { path: '/:pathMatch(.*)*', component: { render: () => h('p', { 'data-testid': 'destination' }, '已到达现有业务路由；本容器不代替详情页验收。') } }
] })
const style = document.createElement('style')
style.textContent = '*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--t1);font:14px/1.6 "Noto Sans CJK SC","Microsoft YaHei",sans-serif}button,input,textarea,select{font:inherit}button{cursor:pointer}a{color:var(--pri);text-decoration:none}.visual-banner{padding:9px 24px;background:var(--bg-card);border-bottom:1px solid var(--bd);color:var(--t2);font-size:12px}.visual-content{max-width:1440px;padding:24px 32px;margin:auto}@media(max-width:600px){.visual-content{padding:16px 12px}}'
document.head.append(style)
await router.push(query.get('page') === 'detail' ? `/admin/platform/tenants/${tenants[0].tenantId}?tab=${['info', 'rules', 'brand', 'users', 'workflows', 'features'].includes(query.get('tab')) ? query.get('tab') : 'info'}` : `/admin/platform/${['overview', 'tenants', 'orders'].includes(query.get('page')) ? query.get('page') : 'overview'}`)
await router.isReady()
createApp({ render: () => [h('div', { class: 'visual-banner' }, '跃科 · 平台工作区视觉验收 ｜ 真实 Vue 页面 · 隔离测试数据'), h('main', { class: 'visual-content' }, h(RouterView))] }).use(router).mount('#app')
window.__platformVisual = { calls, route: () => router.currentRoute.value.fullPath }
