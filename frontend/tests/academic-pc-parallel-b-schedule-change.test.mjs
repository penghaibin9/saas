import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import vm from 'node:vm'
import { isDefiniteWriteRejection } from '../src/modules/academicAffairs/components/parallel-b/unconfirmedWrite.js'

function setup(api, name = 'AaScheduleChangeApplyView', markers = new Map()) {
  const source = readFileSync(new URL(`../src/modules/academicAffairs/views/${name}.vue`, import.meta.url), 'utf8')
  const script = source.match(/<script>([\s\S]*?)<\/script>/)[1]
    .replace(/^import (.*?) from .*$/gm, (_, binding) => `const ${binding} = dependencies${binding.startsWith('{') ? '' : '.' + binding}`)
    .replace('export default', 'component =')
  const sandbox = { dependencies: { scheduleChangeApi: api, academicAffairsApi: { getContext: async () => ({ code: 0, data: { tenantBrandConfig: { schoolName: '测试学校' } } }) }, CHANGE_TYPES: [], currentUserFromToken: () => ({ userId: 'teacher-a' }), toast: { success() {}, error() {} } } }
  Object.assign(sandbox.dependencies, {
    isDefiniteWriteRejection,
    readUnconfirmedWrite: key => markers.get(key) || null,
    markUnconfirmedWrite: (key, value) => markers.set(key, value),
    clearUnconfirmedWrite: key => markers.delete(key)
  })
  vm.runInNewContext(script, sandbox)
  const definition = sandbox.component
  const state = Object.assign(definition.data(), definition.methods, {
    ctx: { currentRole: { roleCode: 'TEACHER' }, dataScope: {} }, $route: { query: {}, params: {} }, $router: { replace() {}, push() {} }
  })
  for (const [key, getter] of Object.entries(definition.computed || {})) Object.defineProperty(state, key, { get: () => getter.call(state) })
  if (state.form) {
    Object.assign(state.form, { originItemId: 'slot-a', targetWeekday: 2, targetSlotNo: 1, targetStartWeek: 3, targetEndWeek: 3, targetWeekParity: 'ALL', reason: '测试调课申请原因' })
    state.adjustScope = 'OCCURRENCE'
  }
  state.origin = { itemId: 'slot-a', courseName: '课程甲', startWeek: 1, endWeek: 16, weekParity: 'ALL' }
  return { state, definition }
}
const deferred = () => { let resolve; const promise = new Promise(done => { resolve = done }); return { promise, resolve } }

test('late conflict result cannot certify a changed destination', async () => {
  const request = deferred()
  const { state } = setup({ conflictCheck: () => request.promise })
  const pending = state.checkConflict()
  state.form.targetWeekday = 4
  request.resolve({ code: 0, data: { conflict: null } })
  await pending
  assert.equal(state.conflictResult, undefined)
})

test('late origin response cannot overwrite a newly selected lesson', async () => {
  const request = deferred()
  const { state } = setup({ originItem: () => request.promise })
  const pending = state.loadOrigin()
  state.form.originItemId = 'slot-b'
  state.origin = { itemId: 'slot-b', courseName: '课程乙' }
  request.resolve({ code: 0, data: { itemId: 'slot-a', courseName: '课程甲', classroom: '旧教室' } })
  await pending
  assert.equal(state.origin.itemId, 'slot-b')
})

test('successful submit preserves edits made while waiting for its receipt', async () => {
  const request = deferred()
  const { state } = setup({ submit: () => request.promise })
  const pending = state.onSubmit()
  state.form.reason = '等待过程中继续修改的原因'
  request.resolve({ code: 0, data: { changeId: 'change-a', status: 'SUBMITTED' } })
  await pending
  assert.equal(state.form.reason, '等待过程中继续修改的原因')
})

test('approval pagination requests all pending stages from the server and keeps its total', async () => {
  let params
  const { state } = setup({ list: async query => { params = query; return { code: 0, data: { list: [], total: 21 } } } }, 'AaScheduleChangeApprovalView')
  await state.load()
  assert.equal(params.status, 'SUBMITTED,COLLEGE_REVIEW,ACADEMIC_REVIEW')
  assert.equal(state.total, 21)
})

test('approval confirmation captures the object and version when opened', async () => {
  let approved
  const { state } = setup({ approve: async (...args) => { approved = args; return { code: 1, message: '拒绝测试' } } }, 'AaScheduleChangeApprovalView')
  const row = { changeId: 'a', version: 2, status: 'SUBMITTED' }
  state.askApprove(row)
  row.changeId = 'b'; row.version = 9
  await state.onConfirm()
  assert.deepEqual(approved.slice(0, 2), ['a', 2])
})

test('ledger ignores an older list response after a new search completes', async () => {
  const old = deferred()
  let calls = 0
  const { state } = setup({ list: () => ++calls === 1 ? old.promise : Promise.resolve({ code: 0, data: { list: [{ changeId: 'b' }], total: 1 } }) }, 'AaScheduleChangeLedgerView')
  const pending = state.load()
  state.filters.status = 'APPLIED'
  await state.load()
  old.resolve({ code: 0, data: { list: [{ changeId: 'a' }], total: 99 } })
  await pending
  assert.equal(state.rows[0].changeId, 'b')
  assert.equal(state.total, 1)
})

test('approval after identity changes does not send the old confirmation', async () => {
  let calls = 0
  const { state } = setup({ approve: async () => { calls++; return { code: 1 } } }, 'AaScheduleChangeApprovalView')
  state.askApprove({ changeId: 'a', version: 1, status: 'SUBMITTED' })
  state.ctx.currentRole = { roleCode: 'OTHER' }
  await state.onConfirm()
  assert.equal(calls, 0)
})

test('notice refuses a mismatched document even when the returned status is applied', async () => {
  const { state } = setup({ detail: async () => ({ code: 0, data: { changeId: 'a', status: 'APPLIED' } }) }, 'AaScheduleChangeNoticePrintView')
  state.$route.params.id = 'b'
  await state.load()
  assert.equal(state.data, null)
  assert.equal(state.canPrint, false)
  assert.match(state.error, /身份不一致/)
})

test('old notice response cannot replace a newer document or enable printing', async () => {
  const old = deferred()
  const { state } = setup({ detail: () => old.promise }, 'AaScheduleChangeNoticePrintView')
  state.$route.params.id = 'a'
  const pending = state.load()
  state.$route.params.id = 'b'
  old.resolve({ code: 0, data: { changeId: 'a', status: 'APPLIED' } })
  await pending
  assert.equal(state.data, null)
  assert.equal(state.canPrint, false)
})

for (const outcome of [
  { code: 503002, message: '请求超时，请点击重试' },
  { code: 503001, message: '响应结构异常' },
  { code: 500000, message: '服务异常' },
  { code: 0, data: {} },
  new Error('network connection lost')
]) {
  test(`unconfirmed submit blocks repeat POST and survives remount: ${outcome.code || outcome.message}`, async () => {
    let calls = 0
    const markers = new Map()
    const api = { submit: async () => { calls++; if (outcome instanceof Error) throw outcome; return outcome } }
    const { state } = setup(api, 'AaScheduleChangeApplyView', markers)
    const reason = state.form.reason
    await state.onSubmit()
    assert.ok(state.unconfirmed)
    assert.equal(state.unconfirmed.originItemId, 'slot-a')
    assert.equal(state.form.reason, reason)
    await state.onSubmit()
    const remount = setup(api, 'AaScheduleChangeApplyView', markers).state
    await remount.onSubmit()
    assert.equal(calls, 1)
    assert.match(state.err, /未确认/)
    assert.equal(state.receipt, null)
  })
}

test('definite conflict rejection allows a corrected request', async () => {
  let calls = 0
  const { state } = setup({ submit: async () => { calls++; return { code: 409001, message: '目标冲突' } } })
  await state.onSubmit()
  assert.equal(state.unconfirmed, null)
  state.form.targetWeekday = 5
  await state.onSubmit()
  assert.equal(calls, 2)
})

test('approval 409001 invalidates confirmation, preserves reason and reloads latest list', async () => {
  let writes = 0, reads = 0
  const { state } = setup({ reject: async () => { writes++; return { code: 409001, message: '版本冲突' } }, list: async () => { reads++; return { code: 0, data: { list: [], total: 0 } } } }, 'AaScheduleChangeApprovalView')
  state.askReject({ changeId: 'a', version: 1, status: 'SUBMITTED' })
  await state.onConfirm({ reason: '保留的正式审核意见' })
  await state.onConfirm({ reason: '保留的正式审核意见' })
  assert.equal(writes, 1)
  assert.equal(reads, 1)
  assert.equal(state.confirm.visible, false)
  assert.equal(state.reviewDraft.reason, '保留的正式审核意见')
  assert.equal(state.evidence, null)
})

test('POST 403002 invalidates old action and rechecks without declaring read access revoked', async () => {
  let writes = 0, reads = 0
  const row = { changeId: 'a', version: 1, status: 'SUBMITTED' }
  const { state } = setup({ approve: async () => { writes++; return { code: 403002, message: '非当前受理人' } }, list: async () => { reads++; return { code: 0, data: { list: [row], total: 1 } } } }, 'AaScheduleChangeApprovalView')
  state.evidence = row
  state.askApprove(row)
  await state.onConfirm()
  state.askApprove(row)
  await state.onConfirm()
  assert.equal(writes, 1)
  assert.equal(reads, 1)
  assert.equal(state.confirm.visible, false)
  assert.equal(state.evidence, null)
  assert.equal(state.rows.length, 1)
})

test('GET 403 clears private evidence and invalidates an older pending list', async () => {
  const old = deferred(); let reads = 0
  const { state } = setup({ list: async () => ++reads === 1 ? old.promise : { code: 403002, message: '读取权限已变化' } }, 'AaScheduleChangeApprovalView')
  const pending = state.load()
  state.evidence = { changeId: 'a' }; state.rows = [{ changeId: 'a' }]
  await state.load()
  old.resolve({ code: 0, data: { list: [{ changeId: 'old' }], total: 1 } })
  await pending
  assert.equal(state.rows.length, 0)
  assert.equal(state.evidence, null)
  assert.equal(state.confirm.visible, false)
})

test('STOP final review does not promise a generated lesson or new attendance slot', async () => {
  const { state } = setup({ approve: async () => ({ code: 0, data: { status: 'APPLIED' } }), list: async () => ({ code: 0, data: { list: [], total: 0 } }) }, 'AaScheduleChangeApprovalView')
  state.askApprove({ changeId: 'a', version: 1, status: 'COLLEGE_REVIEW', changeType: 'STOP' })
  assert.doesNotMatch(state.confirm.message, /生成新课表项/)
  await state.onConfirm()
  assert.doesNotMatch(state.receipt.next, /新课位进入考勤/)
  assert.match(state.receipt.next, /停课/)
})

test('submitted receipt goes to the formal ledger detail, not an unprintable notice', () => {
  for (const name of ['AaScheduleChangeApplyView', 'AaScheduleChangeApprovalView']) {
    const { state } = setup({}, name)
    let target
    state.$router.push = value => { target = value }
    state.receipt = { changeId: 'a', status: 'SUBMITTED' }
    state.goReceipt()
    assert.equal(target, '/admin/academic-affairs/schedule-change?changeId=a')
  }
})
