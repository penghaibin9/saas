import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { createRequire } from 'node:module'
import { resolve } from 'node:path'
import process from 'node:process'
import { fileURLToPath, pathToFileURL } from 'node:url'
import vm from 'node:vm'
import test from 'node:test'

const root = process.env.AA_REGISTRATION_TEST_ROOT || fileURLToPath(new URL('../', import.meta.url))
const sourcePath = process.env.AA_REGISTRATION_TEST_SOURCE || resolve(root, 'src/modules/academicAffairs/components/AaRegistrationBulkPanel.vue')
const source = readFileSync(sourcePath, 'utf8')
const { matchPermission } = await import(pathToFileURL(resolve(root, 'src/config/navPlan.js')))
const { academicStatusLabel } = await import(pathToFileURL(resolve(root, 'src/modules/academicAffairs/constants/academic-display.constants.js')))
const require = createRequire(resolve(root, 'package.json'))
const { createSSRApp, h } = require('vue')
const { renderToString } = require('vue/server-renderer')
const batchId = '1000000000000033669'
const studentA = '1000000000000033671'
const studentB = '1000000000000033672'
const deferred = () => { let resolve; const promise = new Promise(done => { resolve = done }); return { promise, resolve } }
const forbidden = () => ({ code: 403002, bizCode: 'NO_DATA_SCOPE', message: '当前范围不再允许办理' })
const candidates = () => ({ code: 0, data: { list: [], total: 0 } })

function mount(api = {}) {
  const script = source.match(/<script>([\s\S]*?)<\/script>/)[1]
    .replace(/^import (.*?) from .*$/gm, (_, binding) => `const ${binding} = dependencies${binding.startsWith('{') ? '' : '.' + binding}`)
    .replace('export default', 'component =')
  const sandbox = { dependencies: { matchPermission, academicStatusLabel, rosterRegistrationConvenienceApi: { getCandidates: async () => candidates(), ...api }, toast: { info() {}, error() {}, success() {} } } }
  vm.runInNewContext(script, sandbox)
  const component = sandbox.component
  const events = []
  const state = { ...component.data(), batchId, batchState: 'OPEN', ctx: { currentRole: { roleId: 'role-a' }, userId: 'actor-a', permissionPatterns: ['academicAffairs.registration.manage'], dataScope: { scope: 'SCHOOL' } }, $emit: (...args) => events.push(args) }
  for (const [name, fn] of Object.entries(component.methods)) state[name] = fn.bind(state)
  for (const [name, fn] of Object.entries(component.computed)) Object.defineProperty(state, name, { get: () => fn.call(state) })
  return { state, component, events }
}
function ready(state, ids = [studentA]) {
  state.rows = ids.map((studentId, index) => ({ studentId, realName: `PRIVATE-STUDENT-${index}`, studentNo: `PRIVATE-NO-${index}` }))
  state.total = ids.length
  state.selectedIds = [...ids]
  state.preview = { batchId: state.batchId, batchName: 'PRIVATE-BATCH', selected: ids.length, ready: ids.length, blocked: 0, previewToken: 'private-reviewed-token', items: state.rows.map(row => ({ ...row, status: 'READY', message: '可注册' })) }
  state.previewSignature = state.selectionSignature
  state.reviewed = true
}
function receipt(ids = [studentA]) {
  return { code: 0, data: { batchId, selected: ids.length, succeeded: ids.length, failed: 0, items: ids.map((studentId, index) => ({ studentId, ok: true, code: '', message: '注册成功', registrationId: `10000000000000336${81 + index}`, studentStatus: 'REGISTERED' })) } }
}
async function render(mounted) {
  const data = { ...mounted.state }
  for (const key of Object.keys(mounted.component.methods)) delete data[key]
  delete data.batchId; delete data.batchState; delete data.ctx; delete data.$emit
  const app = createSSRApp({ ...mounted.component, watch: {}, created: undefined, beforeUnmount: undefined, components: { AppButton: { render() { return h('button', this.$slots.default?.()) } } }, template: source.match(/<template>([\s\S]*?)<\/template>\s*<script>/)[1], data: () => data }, { batchId: mounted.state.batchId, batchState: mounted.state.batchState, ctx: mounted.state.ctx })
  return renderToString(app)
}

test('candidate 403 erases private preview, selection, receipt and invalidates a late preview', async () => {
  const preview = deferred()
  const mounted = mount({ getCandidates: async () => forbidden(), previewBulkRegistration: () => preview.promise })
  const { state } = mounted
  ready(state)
  const inFlight = state.makePreview()
  const oldPreview = { batchId, selected: 1, ready: 1, previewToken: 'late-private-token', items: [{ studentId: studentA, realName: 'PRIVATE-STUDENT-0' }] }
  await state.load()
  preview.resolve({ code: 0, data: oldPreview }); await inFlight
  assert.equal(state.preview, null)
  assert.equal(state.reviewed, false)
  assert.equal(state.selectedIds.length, 0)
  assert.equal(state.rows.length, 0)
  assert.equal(state.total, 0)
  assert.doesNotMatch(await render(mounted), /PRIVATE-STUDENT|PRIVATE-NO|private-token/)
})

test('preview 403 clears candidates and an old result without issuing a confirm', async () => {
  let writes = 0
  const mounted = mount({ previewBulkRegistration: async () => forbidden(), confirmBulkRegistration: async () => { writes++; return receipt() } })
  ready(mounted.state)
  mounted.state.result = receipt().data
  await mounted.state.makePreview(); await mounted.state.apply()
  assert.equal(writes, 0)
  assert.equal(mounted.state.rows.length, 0)
  assert.equal(mounted.state.selectedIds.length, 0)
  assert.equal(mounted.state.result, null)
  assert.doesNotMatch(await render(mounted), /PRIVATE-STUDENT|PRIVATE-NO/)
})

for (const error of [
  { code: 409001, bizCode: 'DATA_CONFLICT', message: '后续学生注册互斥锁超时' },
  { code: 503002, bizCode: 'REQUEST_TIMEOUT', message: '响应超时' },
  forbidden()
]) test(`confirm ${error.code} keeps exact original command pending and rechecks without replay`, async () => {
  let writes = 0, previews = 0
  const mounted = mount({ confirmBulkRegistration: async () => { writes++; return error }, previewBulkRegistration: async () => { previews++; return { code: 0 } } })
  const { state, events } = mounted
  ready(state, [studentA, studentB])
  await state.apply(); await state.apply(); await state.makePreview()
  assert.equal(writes, 1); assert.equal(previews, 0)
  assert.equal(state.unknownReceipt.batchId, batchId)
  assert.equal(state.unknownReceipt.token, 'private-reviewed-token')
  assert.deepEqual(Array.from(state.unknownReceipt.studentIds), [studentA, studentB])
  assert.equal(state.result, null)
  assert.equal(events.filter(([name]) => name === 'recheck').length, 1)
  assert.equal(events.filter(([name]) => name === 'applied').length, 0)
  state.recheckRegistration()
  assert.equal(events.filter(([name]) => name === 'recheck').length, 2)
  assert.equal(state.unknownReceipt.batchId, batchId)
  if (error.code === 403002) {
    assert.equal(state.rows.length, 0); assert.equal(state.selectedIds.length, 0)
    assert.doesNotMatch(await render(mounted), /PRIVATE-STUDENT|PRIVATE-NO/)
  }
})

test('partial receipt renders exact success/failure IDs, formal reason and supplied state', async () => {
  const data = receipt([studentA, studentB]).data
  data.succeeded = 1; data.failed = 1
  data.items[1] = { studentId: studentB, ok: false, code: 'INELIGIBLE', message: '资格已变更：学籍审核未完成' }
  const mounted = mount({ confirmBulkRegistration: async () => ({ code: 0, data }) })
  ready(mounted.state, [studentA, studentB]); await mounted.state.apply()
  const html = await render(mounted)
  assert.equal(mounted.state.unknownReceipt, null)
  assert.match(html, new RegExp(studentA)); assert.match(html, new RegExp(studentB))
  assert.match(html, /资格已变更：学籍审核未完成/); assert.doesNotMatch(html, /INELIGIBLE/)
  assert.match(html, /1000000000000033681/); assert.match(html, /本次回执学籍状态：已注册/)
  assert.doesNotMatch(html, /全部学生均已|下一状态|下一责任人/)
  assert.equal(mounted.events.filter(([name]) => name === 'applied').length, 1)
})

test('incomplete or adjacent-ID success receipts remain unresolved and cannot claim completion', async () => {
  const cases = [
    { batchId, succeeded: 1, failed: 0 },
    { ...receipt().data, items: [{ studentId: studentB, ok: true }] },
    { ...receipt([studentA, studentB]).data, items: [{ studentId: studentA, ok: true }, { studentId: studentA, ok: true }] },
    { ...receipt().data, succeeded: 0 }
  ]
  for (const data of cases) {
    const mounted = mount({ confirmBulkRegistration: async () => ({ code: 0, data }) })
    ready(mounted.state, data.selected === 2 ? [studentA, studentB] : [studentA])
    await mounted.state.apply()
    assert.equal(mounted.state.result, null)
    assert.ok(mounted.state.unknownReceipt)
    assert.doesNotMatch(await render(mounted), /data-testid="bulk-registration-result"/)
    assert.equal(mounted.events.filter(([name]) => name === 'recheck').length, 1)
  }
})

test('late error after batch or identity switch retains original lock without leaking old names', async () => {
  for (const kind of ['batch', 'identity']) {
    const reply = deferred(), writes = []
    const mounted = mount({ confirmBulkRegistration: (...args) => { writes.push(args); return reply.promise } })
    const { state, events } = mounted
    ready(state); const pending = state.apply()
    if (kind === 'batch') state.batchId = '1000000000000033670'
    else state.ctx = { ...state.ctx, userId: 'actor-b' }
    state.resetContext()
    reply.resolve({ code: 503002, message: 'PRIVATE-STUDENT-0 写入回执超时' }); await pending
    assert.equal(state.unknownReceipt.batchId, batchId)
    assert.equal(state.unknownReceiptCurrent, false)
    assert.equal(state.result, null); assert.equal(state.commandError, '')
    ready(state); await state.apply()
    assert.equal(writes.length, 1)
    state.recheckRegistration()
    assert.equal(events.filter(([name]) => name === 'recheck').length, 0)
    state.rows = []; state.preview = null
    const html = await render(mounted)
    assert.doesNotMatch(html, /PRIVATE-STUDENT|PRIVATE-NO|写入回执超时/)
    if (kind === 'batch') assert.doesNotMatch(html, new RegExp(batchId))
  }
})

test('duplicate clicks use the frozen token and complete receipt exactly once', async () => {
  const reply = deferred(), writes = []
  const mounted = mount({ confirmBulkRegistration: (...args) => { writes.push(args); return reply.promise } })
  ready(mounted.state)
  const pending = mounted.state.apply(); await mounted.state.apply()
  reply.resolve(receipt()); await pending
  assert.deepEqual(writes, [[batchId, 'private-reviewed-token']])
  assert.equal(mounted.state.result.succeeded, 1)
  assert.equal(mounted.events.filter(([name]) => name === 'applied').length, 1)
})

test('a candidate 403 after a complete command clears old rows/result and requests the formal list', async () => {
  const mounted = mount({ confirmBulkRegistration: async () => receipt(), getCandidates: async () => forbidden() })
  ready(mounted.state); await mounted.state.apply()
  assert.equal(mounted.state.rows.length, 0)
  assert.equal(mounted.state.result, null)
  assert.equal(mounted.events.filter(([name]) => name === 'recheck').length, 1)
  assert.doesNotMatch(await render(mounted), /PRIVATE-STUDENT|1000000000000033681/)
})
