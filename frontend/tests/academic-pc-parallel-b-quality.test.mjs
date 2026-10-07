import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { page, deferred } from './academic-pc-parallel-b-harness.mjs'

const okList = (list = []) => ({ code: 0, data: { list, total: list.length } })

test('late evaluation results cannot replace another batch', async () => {
  const old = deferred()
  const { state } = page('AaEvaluationConsoleView', { academicAffairsEvaluationApi: { results: () => old.promise } })
  state.current = { batchId: 'a' }
  const pending = state.loadCurrentResults()
  state.current = { batchId: 'b' }; state.results = [{ resultId: 'b' }]
  old.resolve({ code: 0, data: { list: [{ resultId: 'a' }], total: 1 } })
  await pending
  assert.equal(state.results[0].resultId, 'b')
})

test('failed quality record request is visible as an error, not an empty list', async () => {
  const { state } = page('AaQualityDashboardView', { academicAffairsQualityApi: { listRecords: async () => ({ code: 503001, message: '服务不可用' }) } })
  state.tab = 'inspection'
  await state.loadRecords()
  assert.equal(state.panelError, '服务不可用')
})

test('AA-226 through AA-233 keep eight distinct business workspaces', () => {
  const source = readFileSync(new URL('../src/modules/academicAffairs/views/AaQualityDashboardView.vue', import.meta.url), 'utf8')
  for (const title of ['质量看板', '督导听课', '巡课记录', '教学检查', '教学事故', '质量整改', '整改跟进', '质量归档']) assert.match(source, new RegExp(`title: '${title}'`))
  for (const layout of ['aaql-overview-layout', 'aaql-form--record', 'aaql-kanban', 'aaql-follow-layout', 'archiveRows']) assert.match(source, new RegExp(layout))
})

test('rectification is created only from the frozen confirmed source record and read back', async () => {
  const source = { recordId: 31, recordType: 'INSPECTION', status: 'CONFIRMED', title: '期中材料检查', createdAt: '2026-09-09T09:00:00' }
  let called = 0
  const quality = {
    getRecord: async () => ({ code: 0, data: { ...source } }),
    rectifyFromRecord: async (recordId, body) => { called++; assert.equal(String(recordId), '31'); assert.equal(body.title, '期中材料检查整改'); return { code: 0, data: { rectId: 81 } } },
    getRectification: async () => ({ code: 0, data: { rectId: 81, sourceRecordId: 31, title: '期中材料检查整改', status: 'PENDING', responsibleName: '王老师' } }),
    listRectifications: async () => okList([]),
    listRecords: async () => okList([source])
  }
  const { state } = page('AaQualityDashboardView', { academicAffairsQualityApi: quality })
  state.tab = 'rectify'; state.rectSourceRecord = Object.freeze({ ...source }); state.rectForm = { title: '期中材料检查整改', requirement: '三日内补齐检查材料' }
  await state.submitRectCreate()
  assert.equal(called, 1)
  assert.equal(state.pendingWrite, null)
  assert.equal(state.actionReceipt.verified, true)
  assert.match(state.actionNotice, /正式整改状态/)
})

test('record confirmation refuses a changed object before issuing the command', async () => {
  const row = { recordId: 9, recordType: 'PATROL', status: 'SUBMITTED', title: '第一节巡课', createdAt: '2026-09-09T08:00:00' }
  let writes = 0
  const { state } = page('AaQualityDashboardView', { academicAffairsQualityApi: {
    getRecord: async () => ({ code: 0, data: { ...row, title: '已被他人修改' } }),
    confirmRecord: async () => { writes++; return { code: 0 } }
  } })
  state.tab = 'patrol'
  await state.confirmRec(row)
  assert.equal(writes, 0)
  assert.equal(state.pendingWrite, null)
  assert.equal(state.actionNotice, '')
})

test('an ambiguous progress response stays locked and read-only verification never replays it', async () => {
  const before = { rectId: 72, sourceRecordId: 31, status: 'PENDING', title: '课堂整改', createdAt: '2026-09-09T09:00:00', progressLog: [] }
  const after = { ...before, status: 'IN_PROGRESS', progressLog: [{ action: 'PROGRESS', note: '已完成第一轮整改' }] }
  let reads = 0, writes = 0
  const quality = {
    getRectification: async () => ({ code: 0, data: reads++ === 0 ? { ...before } : { ...after } }),
    addProgress: async () => { writes++; return { code: -1, message: '网络超时' } },
    listRectifications: async () => okList([after]),
    listRecords: async () => okList([])
  }
  const { state } = page('AaQualityDashboardView', { academicAffairsQualityApi: quality })
  state.tab = 'followUp'; state.openProgress(before); state.rectNoteText = '已完成第一轮整改'
  await state.submitRectNote()
  assert.equal(writes, 1)
  assert.ok(state.pendingWrite)
  await state.verifyPendingWrite()
  assert.equal(writes, 1)
  assert.equal(state.pendingWrite, null)
  assert.equal(state.actionReceipt.verified, true)
})

test('rectification queue keeps successful data visible when source lookup partially fails', async () => {
  const rows = [{ rectId: 4, status: 'PENDING', title: '整改任务' }]
  const { state } = page('AaQualityDashboardView', { academicAffairsQualityApi: {
    listRectifications: async () => okList(rows),
    listRecords: async () => ({ code: 503001, message: '来源服务不可用' })
  } })
  state.tab = 'rectify'
  await state.loadRectifications()
  assert.equal(state.rectRows.length, 1)
  assert.equal(state.panelError, '')
  assert.match(state.rectPartial, /来源服务不可用/)
})

test('archive composes traceable evidence rows and labels partial success honestly', async () => {
  const record = { recordId: 7, recordType: 'SUPERVISION', status: 'CLOSED', title: '课堂观察', conclusion: '完成改进', confirmedAt: '2026-09-09T10:00:00' }
  const rect = { rectId: 8, sourceRecordId: 7, sourceType: 'SUPERVISION', sourceTitle: '课堂观察', title: '课堂观察整改', resultNote: '复核通过', status: 'CLOSED', closedAt: '2026-09-09T11:00:00', progressLog: [{ action: 'APPROVE', note: '达到要求' }] }
  const { state } = page('AaQualityDashboardView', { academicAffairsQualityApi: {
    archiveOverview: async () => ({ code: 503001, message: '汇总暂不可用' }),
    listRecords: async () => okList([record]),
    listRectifications: async () => okList([rect])
  } })
  await state.loadArchive()
  assert.equal(state.panelError, '')
  assert.match(state.archivePartial, /汇总暂不可用/)
  assert.equal(state.archiveRows.length, 1)
  assert.equal(state.archiveRows[0].sourceTitle, '课堂观察')
  assert.equal(state.archiveRows[0].conclusion, '复核通过')
  assert.equal(state.archiveRows[0].timeline[0].title, '复核通过')
})

test('403 clears quality scope data instead of leaving a stale queue', async () => {
  const { state } = page('AaQualityDashboardView', { academicAffairsQualityApi: {
    listRectifications: async () => ({ code: 403, message: '禁止访问' }),
    listRecords: async () => okList([])
  } })
  state.tab = 'rectify'; state.rectRows = [{ rectId: 1 }]
  await state.loadRectifications()
  assert.equal(state.rectRows.length, 0)
  assert.match(state.panelError, /无权/)
})
