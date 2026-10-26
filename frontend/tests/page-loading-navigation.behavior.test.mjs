import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'
import vm from 'node:vm'
import { restoreOrientationBatch } from '../src/modules/orientation/routeContext.js'
import { withInternshipBatch } from '../src/modules/internship/navigation.js'
import { workspaceRouteOwner, activeWorkspacePage } from '../src/components/workspace/workspaceRouting.js'

test('实习菜单保留批次后仍高亮岗位模块，而不是被首页前缀抢占', () => {
  const path = '/admin/internship/positions'
  const route = { path, fullPath: path + '?panel=list&batchId=47', query: { panel: 'list', batchId: '47' } }
  assert.equal(workspaceRouteOwner(path, route.fullPath).modKey, 'in-enterprise-position')
  const pages = [{ path: '/admin/internship', moduleKey: 'home' }, { path: path + '?panel=list', moduleKey: 'positions' }]
  assert.equal(activeWorkspacePage(pages, route, 'home').moduleKey, 'positions')
})

test('公共菜单、最近访问与跨中心导航使用业务批次解析器', async () => {
  const source = readFileSync(new URL('../src/components/workspace/TeacherWorkspaceFrame.vue', import.meta.url), 'utf8')
  const body = source.slice(source.indexOf('async function navigate('), source.indexOf('\nfunction selectItem('))
  const pushed = []
  const route = { fullPath: '/admin/internship?batchId=47' }
  const sandbox = {
    pages: { value: [{ id: 'positions', path: '/admin/internship/positions?panel=list' }] },
    destinations: new Map(), route, mobileOpen: { value: true },
    restoreOrientationBatch, sessionStorage: { getItem: () => null },
    props: { resolveDestination: path => withInternshipBatch(path, '47') },
    router: {
      resolve(to) { return { fullPath: typeof to === 'string' ? to : to.path + (Object.keys(to.query).length ? '?' + new URLSearchParams(to.query) : '') + to.hash } },
      async push(to) { pushed.push(to) }
    }
  }
  vm.runInNewContext(body, sandbox)
  await sandbox.navigate('positions')
  assert.equal(pushed[0].query.batchId, '47')
  assert.equal(pushed[0].query.panel, 'list')
  sandbox.destinations.set('positions', '/admin/internship/positions?panel=list&page=2&batchId=47')
  await sandbox.navigate('positions')
  assert.equal(pushed[1].query.page, '2')
  await sandbox.navigate('/admin/system/overview')
  assert.equal(pushed[2].query.batchId, undefined)
  assert.equal(sandbox.mobileOpen.value, false)
})

test('风险标签缺失字典时仍能显示明确状态', () => {
  const source = readFileSync(new URL('../src/views/admin/student/StudentRiskTagListView.vue', import.meta.url), 'utf8')
  const match = source.match(/statusLabel\(v\)\s*\{([\s\S]*?)\r?\n {4}\}/)
  assert.ok(match)
  const label = new Function('v', match[1])
  assert.equal(label.call({ ctx: { statusOptions: {} } }, 'NEW'), '状态待确认')
  assert.equal(label.call({ ctx: { statusOptions: { riskTagStatus: [{ value: 'NEW', label: '新建' }] } } }, 'NEW'), '新建')
})

test('历史已安装关系缺少推荐时可读取，不能自动生成安装决定', () => {
  const source = readFileSync(new URL('../src/modules/system/views/SystemImplementationView.vue', import.meta.url), 'utf8')
  const body = source.split('hydrateRelation(raw) {')[1].split('\n    async load()')[0].replace(/},\s*$/, '')
  const hydrate = new Function('raw', body)
  const historical = { status: 'APPLIED', candidates: [{ type: 'CLASS', classId: '1000000000000000999' }] }
  assert.equal(hydrate(historical).candidates[0].uiAction, '')
  const current = { status: 'DISCOVERED', candidates: [{ recommendation: { action: 'REVIEW' } }, { recommendation: { action: 'KEEP' } }] }
  assert.deepEqual(hydrate(current).candidates.map(item => item.uiAction), ['', 'KEEP'])
})

test('日常沙箱明确禁用模拟回退时，开发构建也必须遵守', () => {
  const source = readFileSync(new URL('../src/services/http/config.js', import.meta.url), 'utf8')
  const code = source.slice(source.indexOf('export function allowMockFallback()'), source.indexOf('export function realApiEnabled()'))
    .replace('export ', '').replaceAll('import.meta', 'meta')
  const allowed = new Function('meta', code + ';return allowMockFallback()')
  assert.equal(allowed({ env: { DEV: true, VITE_ALLOW_MOCK_FALLBACK: 'false' } }), false)
  assert.equal(allowed({ env: { DEV: false, VITE_ALLOW_MOCK_FALLBACK: 'true' } }), false)
  assert.equal(allowed({ env: { DEV: true, VITE_ALLOW_MOCK_FALLBACK: 'true' } }), true)
})

test('单接口超时不会熔断后续页面，断网仍进入离线状态', async () => {
  const source = readFileSync(new URL('../src/services/http/client.js', import.meta.url), 'utf8')
  const code = source.slice(source.indexOf('async function rawRequest('), source.indexOf('function newBrowserSessionId('))
  let offline = false, calls = 0
  const env = {
    fetch: async path => { calls++; if (path === '/slow') throw Object.assign(new Error('timeout'), { name: 'AbortError' }); if (path === '/offline') throw new TypeError('network'); return { status: 200, json: async () => ({ code: 0, data: 'real' }) } },
    state: { token: '' }, REQUEST_TIMEOUT_MS: 500,
    isBackendOffline: () => offline, canUseMockFallback: () => true,
    isWriteMethod: method => method !== 'GET', API_BASE_URL: '', API_PREFIX: '',
    normalizeUiError: value => ({ userMessage: value.message }),
    clearOfflineState() { offline = false }, markOffline() { offline = true },
    transportFailure: (source, details) => Object.assign(new Error(details.message), details),
    throwOfflineSkip() { throw new Error('unexpected cooldown') }
  }
  const raw = new Function(...Object.keys(env), code + ';return rawRequest')(...Object.values(env))
  await assert.rejects(raw('/slow'), /请求超时/)
  assert.equal(offline, false)
  assert.equal(await raw('/healthy'), 'real')
  assert.equal(calls, 2)
  await assert.rejects(raw('/offline'))
  assert.equal(offline, true)
})

// Actual rawRequest/transportFailure, with declared HTTP200/json collaborators.
// No token, real HTTP, app import, global replacement, or fake clock.
import { normalizeUiError as bodyReadNormalizeUiError } from '../src/utils/presentationSafety.js'
function bodyReadClientFixture(fetcher) {
  const source = readFileSync(new URL('../src/services/http/client.js', import.meta.url), 'utf8')
  const rawSource = source.slice(source.indexOf('async function rawRequest('), source.indexOf('function newBrowserSessionId('))
  const failureSource = source.slice(source.indexOf('function transportFailure('), source.indexOf('function markOffline('))
  const transportFailure = new Function(failureSource + ';return transportFailure')()
  const stats = { fetch: 0, json: 0, markOffline: 0, clearOffline: 0, offline: false }
  const env = {
    fetch: async (url, options) => {
      stats.fetch++; assert.equal(options.method, 'GET'); assert.equal(options.headers.Authorization, undefined)
      const response = await fetcher(url, options)
      return { status: response.status, json: async () => { stats.json++; return response.json() } }
    },
    state: { token: '' }, REQUEST_TIMEOUT_MS: 4000,
    isBackendOffline: () => stats.offline, canUseMockFallback: () => false,
    isWriteMethod: method => !['GET', 'HEAD', 'OPTIONS'].includes(String(method).toUpperCase()),
    API_BASE_URL: '', API_PREFIX: '', normalizeUiError: bodyReadNormalizeUiError,
    clearOfflineState() { stats.clearOffline++; stats.offline = false },
    markOffline() { stats.markOffline++; stats.offline = true },
    throwOfflineSkip() { throw new Error('Unexpected mock-only cooldown in declared production fixture') },
    transportFailure
  }
  return { raw: new Function(...Object.keys(env), rawSource + ';return rawRequest')(...Object.values(env)), stats }
}

test('HTTP200 body AbortError and TimeoutError retain timeout metadata and cause without marking the service offline', async () => {
  for (const name of ['AbortError', 'TimeoutError']) {
    const original = new DOMException('Declared body read cancellation', name)
    let healthy = false
    const f = bodyReadClientFixture(async () => ({ status: 200, json: async () => { if (!healthy) throw original; return { code: 0, data: { ready: true } } } }))
    await assert.rejects(f.raw('/declared/body'), error => {
      assert.equal(error.bizCode, 'REQUEST_TIMEOUT'); assert.equal(error.code, 503001); assert.equal(error.biz, true)
      assert.equal(error.transportErrorName, name); assert.equal(error.cause, original); return true
    })
    assert.equal(f.stats.fetch, 1); assert.equal(f.stats.json, 1); assert.equal(f.stats.markOffline, 0); assert.equal(f.stats.offline, false)
    healthy = true
    assert.deepEqual(await f.raw('/declared/healthy'), { ready: true })
    assert.equal(f.stats.fetch, 2); assert.equal(f.stats.json, 2); assert.equal(f.stats.clearOffline, 1)
  }
})

test('ordinary invalid JSON preserves structure-error classification and production GET remains reachable', async () => {
  const original = new SyntaxError('Declared malformed JSON')
  let healthy = false
  const f = bodyReadClientFixture(async () => ({ status: 200, json: async () => { if (!healthy) throw original; return { code: 0, data: 'declared healthy' } } }))
  await assert.rejects(f.raw('/declared/malformed'), error => {
    assert.equal(error.code, 503001); assert.equal(error.biz, true); assert.equal(error.bizCode, undefined)
    assert.match(error.cause.message, /^响应结构异常（HTTP 200）$/); assert.equal(error.cause.name, 'Error')
    assert.notEqual(error.cause, original); return true
  })
  assert.equal(f.stats.markOffline, 1); assert.equal(f.stats.offline, true)
  healthy = true
  assert.equal(await f.raw('/declared/healthy'), 'declared healthy')
  assert.equal(f.stats.fetch, 2); assert.equal(f.stats.json, 2); assert.equal(f.stats.offline, false)
})
