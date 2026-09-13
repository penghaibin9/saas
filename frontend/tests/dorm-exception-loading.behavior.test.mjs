import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import vm from 'node:vm'
import test from 'node:test'
import { setImmediate } from 'node:timers/promises'

function deferred() { let resolve, reject; const promise = new Promise((a, b) => { resolve = a; reject = b }); return { promise, resolve, reject } }
function page(overrides = {}) {
  const script = readFileSync(new URL('../src/modules/studentAffairs/views/dorm/DormExceptionView.vue', import.meta.url), 'utf8')
    .match(/<script>([\s\S]*?)<\/script>/)[1]
    .replace(/^import\s+([\s\S]*?)\s+from\s+['"][^'"]+['"]\s*$/gm, (_, binding) => `const ${binding} = dependencies`)
    .replace('export default', 'component =')
  const api = {
    listDormExceptions: async () => ({ data: { items: [{ exceptionId: '90071992547409933' }], total: 1 } }),
    getDormPresenceProvider: async () => ({ data: { configured: false } }),
    listDormPresence: async () => ({ data: { items: [], total: 0, statusCounts: {} } }), ...overrides
  }
  const sandbox = { dependencies: { studentAffairsApi: api } }
  vm.runInNewContext(script, sandbox)
  const component = sandbox.component
  return { component, state: { ...component.data(), ...component.methods, $route: { query: {} } } }
}

test('slow or failed presence does not block ready exceptions and can retry independently', async () => {
  const slow = deferred(); let exceptionReads = 0, presenceReads = 0
  const { state } = page({
    listDormExceptions: async () => { exceptionReads++; return { data: { items: [{ exceptionId: '1' }], total: 1 } } },
    listDormPresence: () => ++presenceReads === 1 ? slow.promise : Promise.resolve({ data: { items: [], total: 0 } })
  })
  const loading = state.load(); await setImmediate()
  assert.equal(state.loading, false); assert.equal(state.items.length, 1); assert.equal(state.presenceLoading, true)
  slow.reject(new Error('归寝连接超时')); await loading
  assert.equal(state.errorMessage, ''); assert.equal(state.presenceError, '归寝连接超时')
  await state.loadPresence()
  assert.equal(state.presenceError, ''); assert.equal(exceptionReads, 1)
})

test('late pages and responses after unmount cannot overwrite current records', async () => {
  const old = deferred(); let reads = 0
  const { state, component } = page({ listDormPresence: () => ++reads === 1 ? old.promise : Promise.resolve({ data: { items: [{ studentId: 'new' }], total: 100 } }) })
  const loading = state.loadPresence(); state.onPresencePageChange(2); await setImmediate()
  assert.equal(state.presencePagination.page, 2); assert.equal(state.presencePagination.total, 100)
  old.resolve({ data: { items: [{ studentId: 'old' }], total: 1 } }); await loading
  assert.equal(state.presenceItems[0].studentId, 'new')
  const pending = deferred(); const next = page({ listDormExceptions: () => pending.promise })
  const waiting = next.state.loadExceptions(); component.beforeUnmount.call(next.state)
  pending.resolve({ data: { items: [{ exceptionId: 'stale' }], total: 1 } }); await waiting
  assert.equal(next.state.items.length, 0)
})

test('exception pagination never reloads presence; context switch immediately clears old school facts', async () => {
  let presenceReads = 0
  const pending = deferred()
  const { state, component } = page({ listDormPresence: () => { presenceReads++; return pending.promise } })
  state.onPageChange(2); await setImmediate(); assert.equal(presenceReads, 0)
  state.presenceItems = [{ studentId: 'previous-school' }]; state.provider = { configured: true }
  component.watch['ctx.ctxKey'].call(state)
  assert.equal(state.items.length, 0); assert.equal(state.presenceItems.length, 0); assert.equal(state.provider.configured, undefined)
  assert.equal(state.presencePagination.page, 1)
  pending.resolve({ data: { items: [], total: 0 } }); await setImmediate()
})
