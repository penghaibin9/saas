/** Test-only API substitutes. No credentials, sessions, live API or purge calls. */
import { createApp, h, ref } from 'vue'
import StudentPortalConfigPanel from '../../src/modules/platform/components/StudentPortalConfigPanel.vue'
import TenantOffboardingPanel from '../../src/modules/platform/components/TenantOffboardingPanel.vue'
import { studentPortalConfigApi } from '../../src/modules/platform/api/studentPortalConfig.api'
import { platformSecurityOpsApi } from '../../src/modules/platform/api/platformSecurityOps.api'
import '../../src/styles/tokens.css'

const params = new URLSearchParams(location.search)
const mode = params.get('case') || 'normal'
const moduleKeys = ['dashboard','profile','orientation','campusService','academic','internship','graduation','employment','messages']
const featureKeys = ['upload','export','proofDownload','profileCorrection','messageReceipt','materialCenter','workItems','aiAssistant']
const tenantId = ref('1000000000000000003'), generation = ref(0)
const calls = [], states = new Map()
const copy = value => JSON.parse(JSON.stringify(value))
const makeConfig = () => ({ enabled: true, portalName: '学校门户', portalUrl: '/portal/', package: { code: 'standard' },
  modules: Object.fromEntries(moduleKeys.map(key => [key, true])), features: Object.fromEntries(featureKeys.map(key => [key, key !== 'aiAssistant'])) })
studentPortalConfigApi.get = async id => {
  if (mode === 'read-error') throw new Error('测试场景：配置读取失败')
  if (mode === 'malformed') return { enabled: true }
  return copy(states.get(id) || makeConfig())
}
studentPortalConfigApi.save = async (id, body) => {
  calls.push({ operation: 'portal-save', tenantId: id, body: copy(body) })
  if (mode === 'save-error') throw new Error('测试场景：保存结果未确认')
  // Match the API response shape, not the draft. Simulate server normalization.
  const accepted = { ...copy(body), package: { code: body.requiredPackage }, features: { ...body.features, aiAssistant: false } }
  delete accepted.requiredPackage
  states.set(id, accepted)
  return copy(accepted)
}
let exitJob = mode === 'missing-hold' ? { tenantId: tenantId.value, jobId: '11', state: 'RETENTION', cancellable: true,
  retentionUntil: '2020-01-01T00:00:00Z', finalExportSha256: 'a'.repeat(64), steps: [] } : null
platformSecurityOpsApi.previewTenantOffboarding = async id => {
  if (mode === 'read-error') throw new Error('测试场景：退出服务证据未取得')
  return { tenantId: id, tenantName: '隔离验证学校', effectiveState: { version: 4 },
    counts: { studentCount: 0, userCount: 0, fileCount: 0, fileBytes: 0, legalHoldFileCount: mode === 'missing-hold' ? null : 0, activeFileJobCount: 0 },
    registry: { complete: true, registryVersion: 'test-only', purgeTableCount: 0, retainTableCount: 0 }, blockers: [] }
}
platformSecurityOpsApi.getTenantOffboarding = async () => copy(exitJob)
platformSecurityOpsApi.getMfaStatus = async () => ({ enabled: false, status: 'NONE' })
platformSecurityOpsApi.requestTenantOffboarding = async (id, body) => {
  calls.push({ operation: 'offboard-request', tenantId: id, body: copy(body) })
  if (mode === 'save-error') throw new Error('测试场景：退出申请响应未确认')
  exitJob = { tenantId: id, jobId: '11', state: 'FROZEN_READONLY', cancellable: true, reason: body.reason, tenantVersion: 5, steps: [] }
  return copy(exitJob)
}
platformSecurityOpsApi.cancelTenantOffboarding = async (jobId, reason) => {
  calls.push({ operation: 'offboard-cancel', jobId, reason })
  exitJob = { ...exitJob, state: 'CANCELLED', cancellable: false }
  return copy(exitJob)
}
platformSecurityOpsApi.approveTenantPurge = async () => { throw new Error('This fixture never supports irreversible commands') }
const css = document.createElement('style')
css.textContent = '*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--t1);font:14px/1.6 "Noto Sans CJK SC","Microsoft YaHei",sans-serif}.test-note{padding:12px;background:var(--bg-card);font-size:12px}.test-content{max-width:1200px;padding:24px;margin:auto;background:var(--bg-card)}button,input,select{font:inherit}@media(max-width:600px){.test-content{padding:12px}}'
document.head.append(css)
createApp({ setup() { return () => [h('p', { class: 'test-note' }, '实际 Vue 组件 · 无网络隔离验证 · 合成测试数据，不是生产后端'),
  h('button', { type: 'button', onClick: () => { tenantId.value = '7' } }, '测试切换学校'),
  h('main', { class: 'test-content' }, params.get('panel') === 'exit'
    ? h(TenantOffboardingPanel, { key: `${tenantId.value}-${generation.value}`, tenantId: tenantId.value, onChanged: () => generation.value++ })
    : h(StudentPortalConfigPanel, { tenantId: tenantId.value }))] } }).mount('#app')
window.__auditSafety = { calls }
