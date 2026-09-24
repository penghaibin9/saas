import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'
import vm from 'node:vm'
import { computed, reactive, ref, watch, nextTick } from 'vue'
import * as salesHelpers from '../src/modules/platform/lib/moduleCommerceSales.mjs'
import { safeBusinessMessage, safeEnumLabel, safeLocalizedText } from '../src/utils/presentationSafety.js'

const deferred = () => {
  let resolve, reject
  const promise = new Promise((yes, no) => { resolve = yes; reject = no })
  return { promise, resolve, reject }
}
const identity = { subjectId: 'operator', duties: ['order.manage', 'commercial.manage'] }
function workspace(name, names, overrides = {}, authorize = async () => identity, storageOverrides = {}) {
  const source = fs.readFileSync(new URL(`../src/modules/platform/views/control/${name}.vue`, import.meta.url), 'utf8')
    .replace(/\r\n/g, '\n').match(/<script setup>([\s\S]*?)<\/script>/)[1].replace(/^import .*\n/gm, '')
  const props = reactive({ tenantId: '101', locked: false })
  const stored = new Map(), cleanups = [], mounts = []
  const api = new Proxy(overrides, { get: (object, key) => object[key] || (async () => ({ items: [], total: 0, currencyConverted: false })) })
  const state = vm.runInNewContext(source + `\n;({${names},access,error,notice})`, {
    computed, ref, watch: (...args) => cleanups.push(watch(...args)), defineProps: () => props,
    onMounted: fn => mounts.push(fn), onBeforeUnmount: fn => cleanups.push(fn), api,
    ensurePlatformAccessContext: authorize, ...salesHelpers,
    defineEmits: () => () => {}, onBeforeRouteLeave: () => {}, window: { removeEventListener: () => {} },
    crypto: { randomUUID: () => 'stable-test-id' },
    safeBusinessMessage, safeEnumLabel, safeLocalizedText,
    sessionStorage: { getItem: k => stored.get(k) ?? null, setItem: (k,v) => stored.set(k,v), removeItem: k => stored.delete(k), ...storageOverrides }
  })
  state.access.value = identity
  return { state, stored, props, mount: () => Promise.all(mounts.map(fn => fn())), close: () => cleanups.forEach(fn => fn()),
    async select(id) { props.tenantId = id; await nextTick() } }
}

test('late service-cost response cannot overwrite the newly selected school', async t => {
  const old = deferred()
  const w = workspace('ModuleOperationsWorkspace', 'loadCosts,costs,costTotal,costSummary', {
    listServiceCosts: id => id === '101' ? old.promise : Promise.resolve({ items: [{ costId: 'new-school' }], total: 1, summaryByCurrency: { CNY: [] }, currencyConverted: false })
  })
  t.after(w.close)
  const pending = w.state.loadCosts()
  await w.select('202')
  await w.state.loadCosts()
  old.resolve({ items: [{ costId: 'old-school' }], total: 99, summaryByCurrency: { USD: [] }, currencyConverted: false })
  await pending
  assert.equal(w.state.costs.value[0].costId, 'new-school')
  assert.equal(w.state.costTotal.value, 1)
  assert.equal('USD' in w.state.costSummary.value, false)
})

test('switching school while refund identity is rechecked prevents the old write', async t => {
  const auth = deferred(), writes = []
  const w = workspace('ModuleFinanceWorkspace', 'submitRequest', { requestRefund: (...args) => { writes.push(args); return {} } }, () => auth.promise)
  t.after(w.close)
  const pending = w.state.submitRequest('refund', { orderId: 'old-order', amount: '1.00' })
  await w.select('202')
  auth.resolve(identity)
  await pending
  assert.equal(writes.length, 0)
})

test('switching school while cost identity is rechecked prevents the old write', async t => {
  const auth = deferred(), writes = []
  const w = workspace('ModuleOperationsWorkspace', 'submitCost,costForm', { recordServiceCost: (...args) => { writes.push(args); return {} } }, () => auth.promise)
  t.after(w.close)
  w.state.costForm.value = { costType: 'SUPPORT', amount: '1.00', currency: 'CNY', occurredAt: '2026-09-10T10:00:00', orderId: 'old-order' }
  const pending = w.state.submitCost()
  await w.select('202')
  // A new school may have its own valid draft while the previous check is pending.
  w.state.costForm.value = { costType: 'SUPPORT', amount: '2.00', currency: 'CNY', occurredAt: '2026-09-10T10:00:00', orderId: 'new-order' }
  auth.resolve(identity)
  await pending
  assert.equal(writes.length, 0)
})

test('newer refund pagination wins even when the previous page completes last', async t => {
  const old = deferred()
  const w = workspace('ModuleFinanceWorkspace', 'loadRefunds,refunds,refundPage', {
    listRefunds: (_id, { page }) => page === 1 ? old.promise : Promise.resolve({ items: [{ caseId: 'page-two' }], total: 21 })
  })
  t.after(w.close)
  const pending = w.state.loadRefunds(1)
  await w.state.loadRefunds(2)
  old.resolve({ items: [{ caseId: 'page-one' }], total: 21 })
  await pending
  assert.equal(w.state.refundPage.value, 2)
  assert.equal(w.state.refunds.value[0].caseId, 'page-two')
})

test('sales authorization cannot send a replacement school draft', async t => {
  const auth = deferred(), writes = []
  const w = workspace('ModuleSalesWorkspace', 'submitOrder,quote,confirmed', {
    createSalesOrder: (...args) => { writes.push(args); return {} }
  }, () => auth.promise)
  t.after(w.close)
  w.state.quote.value = { order: { tenantId: '101', items: [] } }
  w.state.confirmed.value = true
  const pending = w.state.submitOrder()
  await w.select('202')
  w.state.quote.value = { order: { tenantId: '202', items: [] } }
  auth.resolve(identity)
  await pending
  assert.equal(writes.length, 0)
})

test('late financial receipt preserves another school pending command and sending state', async t => {
  const old = deferred(), newer = deferred(), started = deferred(), secondStarted = deferred()
  const w = workspace('ModuleFinanceWorkspace', 'submitRequest,pendingCommand,sending', {
    requestRefund: id => { if(id === '101'){ started.resolve(); return old.promise } secondStarted.resolve(); return newer.promise }
  })
  t.after(w.close)
  const first = w.state.submitRequest('refund', { orderId: 'old-order' })
  await started.promise
  await w.select('202')
  const second = w.state.submitRequest('refund', { orderId: 'new-order' })
  await secondStarted.promise
  old.resolve({ caseId: 'old-case' })
  await first
  assert.equal(w.state.pendingCommand.value.body.orderId, 'new-order')
  assert.equal(w.state.sending.value, true)
  assert.equal(w.stored.size, 2)
  newer.resolve({ caseId: 'new-case', tenantId: '202', orderId: 'new-order' })
  await second
  assert.equal(w.stored.size, 1)
  assert.match([...w.stored.keys()][0], /:101$/)
})

test('unavailable durable request storage blocks refund creation', async t => {
  const writes = []
  const w = workspace('ModuleFinanceWorkspace', 'submitRequest', {
    requestRefund: (...args) => { writes.push(args); return {} }
  }, undefined, { setItem: () => { throw new Error('存储不可用') } })
  t.after(w.close)
  await w.state.submitRequest('refund', { orderId: 'order' })
  assert.equal(writes.length, 0)
  assert.ok(w.state.error.value)
})

test('malformed saved financial request is retained and disables new requests', t => {
  const w = workspace('ModuleFinanceWorkspace', 'loadPending,canManage')
  t.after(w.close)
  w.stored.set('gx_module_finance_pending_v1:operator:101', '{broken')
  w.state.loadPending()
  assert.equal(w.state.canManage.value, false)
  assert.equal(w.stored.size, 1)
  assert.ok(w.state.error.value)
})

test('refund inputs are frozen before asynchronous identity checks', async t => {
  const auth = deferred(), writes = []
  const w = workspace('ModuleFinanceWorkspace', 'submitRequest', {
    requestRefund: (...args) => { writes.push(args); return {} }
  }, () => auth.promise)
  t.after(w.close)
  const body = { orderId: 'original', amount: '1.00' }
  const pending = w.state.submitRequest('refund', body)
  body.orderId = 'changed'
  auth.resolve(identity)
  await pending
  assert.equal(writes[0][0], '101')
  assert.equal(writes[0][1].orderId, 'original')
})

test('school change while SLA approval is checked prevents policy write', async t => {
  const auth = deferred(), writes = []
  const w = workspace('ModuleOperationsWorkspace', 'saveSla,slaForm', {
    updateSlaPolicy: (...args) => { writes.push(args); return {} }
  }, () => auth.promise)
  t.after(w.close)
  w.state.slaForm.value = { policyVersion: 'v01', targets: { P0: '1', P1: '2', P2: '3', P3: '4' }, reason: '测试明确政策' }
  const pending = w.state.saveSla()
  await w.select('202')
  auth.resolve(identity)
  await pending
  assert.equal(writes.length, 0)
})

test('ambiguous financial receipt retains the exact original command for retry', async t => {
  const writes = []
  const w = workspace('ModuleFinanceWorkspace', 'submitRequest,pendingCommand,retryPending', {
    requestRefund: (...args) => { writes.push(args); return { tenantId: 'wrong-school', caseId: 'untrusted' } }
  })
  t.after(w.close)
  await w.state.submitRequest('refund', { orderId: 'original' })
  assert.ok(w.state.pendingCommand.value)
  assert.equal(w.state.notice.value, '')
  await w.state.retryPending()
  assert.equal(writes.length, 2)
  assert.equal(writes[0][2], writes[1][2])
  assert.equal(writes[0][1].orderId, writes[1][1].orderId)
})

test('initial school selection does not discard platform identity initialization', async t => {
  const auth = deferred()
  const w = workspace('ModuleOperationsWorkspace', 'canManage', {}, () => auth.promise)
  t.after(w.close)
  w.state.access.value = null
  const mounted = w.mount()
  await w.select('202')
  auth.resolve(identity)
  await mounted
  assert.equal(w.state.canManage.value, true)
})

function lifecycle(overrides = {}) {
  const source = fs.readFileSync(new URL('../src/modules/platform/views/control/PlatformCommercialControlView.vue', import.meta.url), 'utf8')
    .replace(/\r\n/g, '\n').match(/<script>([\s\S]*?)<\/script>/)[1]
    .replace(/^import .*\n/gm, '').replace('export default', 'const component =')
  const component = vm.runInNewContext(source + ';component', {
    ModulePageShell: {}, ModuleSalesWorkspace: {}, ModuleFinanceWorkspace: {},
    moduleCommerceApi: overrides, platformControlApi: {},
    window: { clearTimeout: () => {}, setTimeout: () => {} }
  })
  const state = component.data()
  for (const [key, fn] of Object.entries(component.methods)) state[key] = fn.bind(state)
  for (const [key, fn] of Object.entries(component.computed)) Object.defineProperty(state, key, { get: () => fn.call(state) })
  state.selectedTenantId = '101'
  state.selectedModuleKey = 'internship'
  state.portfolio = { modules: [{ moduleKey: 'internship', generation: 1 }, { moduleKey: 'studentAffairs', generation: 1 }] }
  return state
}

test('exit preview locks its module until the response is attached to the correct scope', async () => {
  const old = deferred()
  const state = lifecycle({ previewOffboarding: () => old.promise })
  const pending = state.loadOffboardPreview()
  await state.selectModule('studentAffairs')
  state.changeSalesSchool('202')
  assert.equal(state.selectedModuleKey, 'internship')
  assert.equal(state.selectedTenantId, '101')
  old.resolve({ canRequest: true })
  await pending
  await state.selectModule('studentAffairs')
  assert.equal(state.preview, null)
})

test('retention policy is never invented or carried across module selections', async () => {
  const writes = []
  const state = lifecycle({ requestOffboarding: (...args) => { writes.push(args); return {} } })
  state.preview = { canRequest: true }
  state.offboardForm.confirmed = true
  await state.requestOffboarding()
  assert.equal(writes.length, 0)
  assert.match(state.message, /已确认合同/)
  state.offboardForm.retentionDays = 30
  state.offboardForm.retentionPolicyVersion = 'EXPLICIT'
  await state.selectModule('studentAffairs')
  assert.equal(state.offboardForm.retentionDays, '')
  assert.equal(state.offboardForm.confirmed, false)
})
