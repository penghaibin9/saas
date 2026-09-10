import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import vm from 'node:vm'
import test from 'node:test'
import { buildGradePublishReceipt, gradeWarningEffectState } from '../src/modules/academicAffairs/gradePublishReceipt.js'
import * as flow from '../src/modules/academicAffairs/academicFlowContext.js'

const response = data => ({ code: 0, data: { gradeTaskId: '42', status: 'PUBLISHED', projected: 40, failCount: 3, ...data } })
const defer = () => { let resolve; const promise = new Promise(done => { resolve = done }); return { promise, resolve } }

test('actual adapter keeps failed student count separate from unavailable warning count', () => {
  const r = buildGradePublishReceipt(response({ warningScanOk: true }))
  assert.equal(r.primary, 'COMMITTED'); assert.equal(r.warningRefresh, 'SUCCEEDED')
  assert.equal(r.failedGradeCount, 3); assert.equal(r.warningCount, null); assert.equal(r.tone, 'success')
})
test('scan failure never changes committed result or copies internal diagnostics', () => {
  const r = buildGradePublishReceipt(response({ warningScanOk: false, warningScanError: 'SELECT secret FROM /srv/mysql' }))
  assert.equal(r.primary, 'COMMITTED'); assert.equal(r.warningRefresh, 'FAILED'); assert.equal(r.tone, 'warning')
  assert.equal(r.diagnosticPresent, true); assert.equal(JSON.stringify(r).includes('SELECT'), false)
  assert.equal(r.mayReplayPublish, false)
})

test('invalid GPA policy is an explicit non-commit, without trusting server diagnostics', () => {
  const rejected = { code: 500001, httpStatus: 409, bizCode: 'GPA_POLICY_INVALID', message: 'SQL /private' }
  const result = buildGradePublishReceipt(rejected)
  assert.equal(result.primary, 'REJECTED')
  assert.equal(result.projectedCount, 0)
  assert.equal(result.warningRefresh, 'NOT_STARTED')
  assert.doesNotMatch(JSON.stringify(result), /SQL|private/)
  assert.equal(buildGradePublishReceipt({ ...rejected, httpStatus: 500 }).primary, 'UNKNOWN')
})
test('an explicit persisted failed scan remains failed even without the legacy boolean', () => {
  const r = buildGradePublishReceipt(response({ warningScanState: 'FAILED', warningScanOk: undefined }))
  assert.equal(r.primary, 'COMMITTED'); assert.equal(r.warningRefresh, 'FAILED'); assert.equal(r.tone, 'warning')
})
for (const value of [undefined, null, 'true', 'false', 0, 1]) {
  test(`scan field ${String(value)} (${typeof value}) is unknown, never green`, () => {
    const r = buildGradePublishReceipt(response({ warningScanOk: value }))
    assert.equal(r.warningRefresh, 'UNKNOWN'); assert.equal(r.tone, 'warning')
  })
}
test('real zero survives while missing or malformed numbers remain unknown', () => {
  assert.equal(buildGradePublishReceipt(response({ projected: 0, failCount: 0 })).projectedCount, 0)
  for (const value of [undefined, null, -1, NaN, Infinity, true, '3', 3.5, Number.MAX_SAFE_INTEGER + 1]) {
    const r = buildGradePublishReceipt(response({ projected: value, failCount: value }))
    assert.equal(r.projectedCount, null); assert.equal(r.failedGradeCount, null)
  }
})
test('confirmed scan with missing publication counts still requires attention', () => {
  assert.equal(buildGradePublishReceipt(response({ warningScanOk: true, projected: undefined })).tone, 'warning')
})
for (const envelope of [null, { code: 503001 }, { code: 409, data: { status: 'PUBLISHED' } }, { code: 0, data: { warningScanOk: true } }]) {
  test(`unconfirmed envelope ${JSON.stringify(envelope)} cannot imply commit or rollback`, () => {
    const r = buildGradePublishReceipt(envelope)
    assert.equal(r.primary, 'UNKNOWN'); assert.equal(r.tone, 'warning'); assert.equal(r.mayReplayPublish, false)
  })
}

function page(api) {
  const source = readFileSync(new URL('../src/modules/academicAffairs/views/AaGradePublishView.vue', import.meta.url), 'utf8')
  const script = source.match(/<script>([\s\S]*?)<\/script>/)[1]
    .replace(/^import (.*?) from .*$/gm, (_, binding) => `const ${binding} = dependencies`)
    .replace('export default', 'component =')
  const notices = []
  const context = { dependencies: { ...flow, buildGradePublishReceipt, gradeWarningEffectState,
    academicAffairsApi: { getGradeTasks: async () => ({ code: 0, data: { list: [], total: 0 } }), getGradePublicationEffect: async () => ({ code: 404 }), ...api },
    toast: Object.fromEntries(['success', 'warning', 'error'].map(tone => [tone, title => notices.push({ tone, title })])) } }
  vm.runInNewContext(script, context)
  const c = context.component
  const state = Object.assign(c.data(), c.methods, { $route: { fullPath: '/grade-publish', query: {}, path: '/grade-publish' },
    academicFlow: { identity: () => 'school:user:role', restorePosition() {} } })
  state.readGate = flow.createAcademicRequestGate(() => state.contextKey())
  return { state, notices }
}
for (const warningScanOk of [true, false, undefined]) {
  test(`actual page applies ${String(warningScanOk)} scan receipt and never offers publish replay`, async () => {
    let writes = 0
    const { state: s, notices } = page({ publishGrades: async id => {
      assert.equal(id, '42'); writes++; return response({ warningScanOk, warningScanError: 'SQL /private/internal' })
    } })
    s.openPublish({ gradeTaskId: '42', courseName: '测试课程' }); await s.doAction()
    assert.equal(writes, 1); assert.equal(s.dlg.visible, false)
    assert.equal(s.receipt.status, 'PUBLISHED'); assert.equal(s.receipt.warningCount, null)
    assert.match(s.receipt.projectedText, /不及格人数 3/); assert.doesNotMatch(s.receipt.projectedText, /3 条预警/)
    assert.equal(notices[0].tone, warningScanOk === true ? 'success' : 'warning')
    assert.equal(JSON.stringify(s.receipt).includes('/private'), false)
  })
}
test('timeout followed by an observed published state does not claim this request succeeded or retry it', async () => {
  let writes = 0, reads = 0
  const { state: s, notices } = page({ publishGrades: async () => { writes++; throw new Error('timeout') },
    getGradeTasks: async query => { reads++; assert.equal(query.taskId, '42'); return { code: 0, data: { list: [{ gradeTaskId: '42', status: 'PUBLISHED' }] } } } })
  s.openPublish({ gradeTaskId: '42', courseName: '测试课程' }); await s.doAction()
  assert.equal(s.receipt.primary, 'UNKNOWN'); assert.equal(notices[0].tone, 'warning')
  await s.checkReceiptStatus(); s.openPublish({ gradeTaskId: '42' }); await s.doAction()
  assert.equal(writes, 1); assert.equal(reads, 1); assert.equal(s.receipt.primary, 'UNKNOWN')
  assert.match(s.receipt.observedText, /不能据此认定上次发布请求成功/)
})
test('an uncertain publish locks only the same task in the same authenticated identity', async () => {
  let identity = 'school-a:user:role', writes = 0
  const { state: s } = page({ publishGrades: async () => { writes++; throw new Error('timeout') } })
  s.academicFlow.identity = () => identity
  const row = { gradeTaskId: '42', courseName: '测试课程' }
  s.openPublish(row); await s.doAction()
  assert.equal(s.publishPendingVerification(row), true)
  s.openPublish(row); assert.equal(s.dlg.visible, false)

  identity = 'school-b:user:role'
  assert.equal(s.publishPendingVerification(row), false)
  s.openPublish(row); await s.doAction()
  assert.equal(writes, 2)
})

test('querying an already published task reports the formal status without inventing an uncertain submission', async () => {
  const { state: s } = page({
    getGradeTasks: async () => ({ code: 0, data: { list: [{ gradeTaskId: '42', status: 'PUBLISHED' }] } }),
    getGradePublicationEffect: async () => ({ code: 0, data: { gradeTaskId: '42', warningScanState: 'SUCCEEDED' } })
  })
  await s.showUnconfirmedReceipt({ gradeTaskId: '42', status: 'PUBLISHED' })
  assert.equal(s.receipt.title, '任务正式状态：已发布')
  assert.equal(s.receipt.warningRefresh, 'SUCCEEDED')
  assert.doesNotMatch(s.receipt.observedText, /上次发布/)
  assert.equal(s.receipt.primary, 'UNKNOWN') // A read is still not proof that this browser submitted it.
})
test('success for another task is rejected before receipt construction', async () => {
  const { state: s } = page({ publishGrades: async () => response({ gradeTaskId: '43', warningScanOk: true }) })
  s.openPublish({ gradeTaskId: '42' }); await s.doAction()
  assert.equal(s.receipt.primary, 'UNKNOWN'); assert.equal(s.receipt.taskId, '42'); assert.equal(s.receipt.tone, 'warning')
})

test('known GPA policy rejection permits manual revalidation but never retries by itself', async () => {
  let writes = 0
  const { state: s } = page({ publishGrades: async () => {
    writes++; return { code: 500001, httpStatus: 409, bizCode: 'GPA_POLICY_INVALID' }
  } })
  const row = { gradeTaskId: '42', courseName: '测试课程' }
  s.openPublish(row); await s.doAction()
  assert.equal(writes, 1)
  assert.equal(s.receipt.primary, 'REJECTED')
  assert.equal(s.publishPendingVerification(row), false)
  assert.equal(s.dlg.visible, false)
  s.openPublish(row)
  assert.equal(s.dlg.visible, true)
  assert.equal(writes, 1)
})
test('double confirmation sends once and a route change suppresses the old receipt', async () => {
  const transport = defer(); let writes = 0
  const { state: s, notices } = page({ publishGrades: () => { writes++; return transport.promise } })
  s.openPublish({ gradeTaskId: '42' }); const pending = s.doAction(); await s.doAction()
  s.$route.fullPath = '/grade-publish?taskId=43'
  transport.resolve(response({ warningScanOk: true })); await pending
  assert.equal(writes, 1); assert.equal(s.receipt, null); assert.equal(notices.length, 0)
})
test('archive and return keep their own receipts with no publish adapter or scan claim', async () => {
  for (const action of ['return', 'archive']) {
    const { state: s } = page({ returnGradeTask: async () => ({ code: 0, data: { status: 'RETURNED' } }), archiveGradeTask: async () => ({ code: 0, data: { status: 'ARCHIVED' } }) })
    s[action === 'return' ? 'openReturn' : 'openArchive']({ gradeTaskId: '42', courseName: '测试课程' })
    await s.doAction({ reason: '核对后重新办理' })
    assert.equal(s.receipt.warningRefresh, undefined); assert.doesNotMatch(s.receipt.title, /发布/)
    assert.equal(s.receipt.projectedText, '未产生新的正式成绩投影')
  }
})
