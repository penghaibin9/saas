import fs from 'node:fs'
import vm from 'node:vm'
import * as workspace from '../src/modules/platform/utils/tenantWorkspace.mjs'

export function deferred() {
  let resolve, reject
  const promise = new Promise((yes, no) => { resolve = yes; reject = no })
  return { promise, resolve, reject }
}
export function optionsInstance(relativePath, supplied = {}, dependencies = {}) {
  const source = fs.readFileSync(new URL(relativePath, import.meta.url), 'utf8')
  const match = source.match(/<script>([\s\S]*?)<\/script>/)
  if (!match) throw new Error('Missing options script')
  const script = match[1].replace(/^import\s+[\s\S]*?\sfrom\s+['"][^'"]+['"]\s*;?/gm, '')
    .replace('export default', 'globalThis.definition =')
  const notices = [], calls = []
  const context = vm.createContext({
    ...workspace, ...Object.fromEntries(['AppButton','AppCard','AppSectionHeader','DataTable','EmptyState','ErrorState','LoadingState','ModulePageShell','StatusTag','StudentPortalConfigPanel','TenantOffboardingPanel','TenantLifecycleWorkspace'].map(name => [name, {}])),
    PLATFORM_FEATURE_LABELS: {}, PLATFORM_RULE_GROUP_LABELS: {}, PLATFORM_RULE_LABELS: {},
    platformControlApi: {}, platformControlHardeningApi: {},
    getPermissionPatterns: () => ['platform.*'], getRbacLoadFailed: () => '', canEnterRoute: () => true,
    isPlatformRoot: () => true, toPlatformUiContext: () => null, platformRoleLabel: v => v,
    toast: { error: x => notices.push(['error', x]), success: x => notices.push(['success', x]), warning: x => notices.push(['warning', x]) },
    window: { prompt: () => '真实操作原因' }, ...dependencies
  })
  vm.runInContext(script, context, { filename: relativePath })
  const definition = context.definition
  const state = { ...definition.data(), $route: { path: '/admin/platform/tenants', query: {}, params: {} },
    $router: { replace: x => { calls.push(['replace', x]); return Promise.resolve() }, push: x => { calls.push(['push', x]); return Promise.resolve() } }, $emit: (...args) => calls.push(['emit', ...args]), ...supplied }
  for (const [key, method] of Object.entries(definition.methods || {})) state[key] = method.bind(state)
  for (const [key, getter] of Object.entries(definition.computed || {})) Object.defineProperty(state, key, { configurable: true, get: getter.bind(state) })
  return { state, definition, source, notices, calls }
}
export const plain = value => JSON.parse(JSON.stringify(value))
export const tenant = (id = '1000000000000000003') => ({ tenantId: id, tenantName: '测试学校', tenantCode: 'SCHOOL-A', status: 'trial', version: 4 })
