import test from 'node:test'
import assert from 'node:assert/strict'
import { page, deferred } from './academic-pc-parallel-b-harness.mjs'
import { textbookReturnPath, textbookQueuePage, textbookQueueReturnPath } from '../src/modules/academicAffairs/components/textbooks/textbookNavigation.js'

test('fee receivables exclude waived history while keeping actual collected amounts', () => {
  const { state } = page('AaTextbookConsoleView')
  state.tab = 'fee'; state.rows = [
    { amount: 49, paidAmount: 10, status: 'PARTIAL' },
    { amount: 46, paidAmount: 0, status: 'WAIVED' },
    { amount: 43, paidAmount: 43, status: 'PAID' }
  ]
  assert.equal(state.metricCards.find(card => card.label === '本页应收').value, '¥92.00')
  assert.equal(state.metricCards.find(card => card.label === '本页已收').value, '¥53.00')
})

test('partial fee keeps the original paid amount on an uncertain retry and prevents duplicate clicks', async () => {
  const first = deferred(); const calls = []
  const { state } = page('AaTextbookConsoleView', {
    academicAffairsTextbookApi: { markFee: (...args) => { calls.push(args); return calls.length === 1 ? first.promise : Promise.resolve({ code: 409, message: '记录已变化，本次未再次入账' }) } }
  })
  state.tab = 'fee'
  state.openPartial({ feeId: '31', amount: 49, paidAmount: 0 })
  state.partialAmount = 10
  const pending = state.submitPartial(); await state.submitPartial()
  assert.equal(calls.length, 1)
  first.reject(new Error('网络超时')); await pending
  assert.equal(state.partialVisible, true)
  await state.submitPartial()
  assert.deepEqual(calls.map(args => [args[0], args[1], args[2], args[4]]), [['31', 'PARTIAL', 10, 0], ['31', 'PARTIAL', 10, 0]])
  assert.equal(state.saving, false)
})

test('partial fee rejects sub-cent values, excessive amounts and a changed identity', async () => {
  let writes = 0
  const { state } = page('AaTextbookConsoleView', { academicAffairsTextbookApi: { markFee: async () => { writes++ } } })
  state.tab = 'fee'; state.openPartial({ feeId: '31', amount: 49, paidAmount: 10 })
  for (const value of [0.001, Infinity, -1, 40]) { state.partialAmount = value; await state.submitPartial() }
  state.partialAmount = 10; state.ctx = { changed: true }; await state.submitPartial()
  assert.equal(writes, 0)
})

test('receipt requires in-app confirmation and cannot submit after the object changes', async () => {
  const confirm = deferred(); let writes = 0
  const { state } = page('AaTextbookDistributionDetailView', {
    systemConfirm: () => confirm.promise,
    academicAffairsTextbookApi: { sign: async () => { writes++; return { code: 0 } } }
  }, { ctx: {}, $route: { params: { batchId: '7' }, query: {} } })
  const pending = state.sign({ recordId: '32', status: 'PENDING', studentName: '甲', textbookName: '教材', qty: 1 })
  assert.equal(writes, 0)
  state.$route.params.batchId = '8'
  confirm.resolve(true); await pending
  assert.equal(writes, 0)
})

test('canceling receipt confirmation does not create a fee and releases the button', async () => {
  let writes = 0
  const { state } = page('AaTextbookDistributionDetailView', {
    systemConfirm: async () => false,
    academicAffairsTextbookApi: { sign: async () => { writes++ } }
  }, { ctx: {}, $route: { params: { batchId: '7' }, query: {} } })
  await state.sign({ recordId: '32', status: 'PENDING' })
  assert.equal(writes, 0)
  assert.equal(state.acting, '')
})

test('append entry locks the original batch/class and keeps the source queue', async () => {
  let destination, sent
  const detail = page('AaTextbookDistributionDetailView', { textbookReturnPath }, {
    $route: { params: { batchId: '7' }, query: { returnTo: '/admin/academic-affairs/textbooks?tab=distribution&page=3' } },
    $router: { push: value => { destination = value } }
  })
  detail.state.loading = false; detail.state.batch = { orderBatchId: '50', classId: '4539' }
  detail.state.openAppend()
  assert.equal(destination.query.appendToBatchId, '7')
  assert.equal(destination.query.classId, '4539')
  const { state, definition } = page('AaTextbookDistributionGenerateView', { textbookReturnPath,
    academicAffairsTextbookApi: { generateDistribution: async body => { sent = body; return { code: 0, data: { distributionBatchId: '7', addedRecordCount: 2 } } } }
  }, { ctx: {}, $route: { query: destination.query }, $router: { push: value => { destination = value } } })
  definition.created.call(state)
  assert.equal(state.classId, '4539')
  state.studentIds = ['233444']; await state.submit()
  assert.equal(sent.appendToBatchId, '7')
  assert.equal(sent.classId, '4539')
  assert.equal(destination.params.batchId, '7')
  assert.equal(destination.query.returnTo, '/admin/academic-affairs/textbooks?tab=distribution&page=3')
  state.classId = '4538'
  assert.equal(state.canSubmit, false)
})

test('late append response cannot redirect a different original batch, and duplicate clicks send once', async () => {
  const pending = deferred(); let calls = 0, redirects = 0
  const { state } = page('AaTextbookDistributionGenerateView', { textbookReturnPath,
    academicAffairsTextbookApi: { generateDistribution: () => { calls++; return pending.promise } }
  }, { ctx: {}, $route: { query: { orderBatchId: '50', appendToBatchId: '7', classId: '4539' } }, $router: { push: () => { redirects++ } } })
  state.classId = '4539'; state.studentIds = ['233444']
  const operation = state.submit(); await state.submit()
  assert.equal(calls, 1)
  state.$route.query.appendToBatchId = '8'; state.resetScope()
  pending.resolve({ code: 0, data: { distributionBatchId: '7', addedRecordCount: 2 } })
  await operation
  assert.equal(redirects, 0)
  assert.equal(state.studentIds.length, 0)
  assert.equal(state.submitting, false)
})

test('distribution entry captures the current queue page and restores it in the formal API request', async () => {
  let destination, query
  const dependencies = {
    textbookQueuePage, textbookQueueReturnPath,
    academicAffairsApi: { getContext: async () => ({ code: 0, data: {} }), getCurrentTerm: async () => ({ code: 0, data: { termId: '52' } }) },
    textbookP0Api: { listDistributionBatches: async params => { query = params; return { code: 0, data: { list: [], total: 61 } } } }
  }
  const { state, definition } = page('AaTextbookConsoleView', dependencies, {
    $route: { fullPath: '/admin/academic-affairs/textbooks?tab=distribution', query: { tab: 'distribution' } },
    $router: { push: value => { destination = value } }
  })
  state.tab = 'distribution'; state.page = 3
  state.openDistribution({ distributionBatchId: '6' })
  assert.equal(destination.params.batchId, '6')
  assert.equal(destination.query.returnTo, '/admin/academic-affairs/textbooks?tab=distribution&page=3')
  const detail = page('AaTextbookDistributionDetailView', { textbookReturnPath }, { $route: { params: { batchId: '6' }, query: destination.query } })
  assert.equal(detail.state.returnPath, destination.query.returnTo)
  state.$route.query.page = '3'
  await definition.created.call(state)
  // 登录上下文响应会触发 Vue 的 identity watcher，不能把已恢复的页码重置为 1。
  definition.watch.identityKey.call(state)
  assert.equal(query.page, 3)
  assert.equal(query.termId, '52')
})

test('generation carries its original order queue through a successful write', async () => {
  let destination
  const { state } = page('AaTextbookDistributionGenerateView', {
    textbookReturnPath,
    academicAffairsTextbookApi: { generateDistribution: async () => ({ code: 0, data: { distributionBatchId: '6' } }) }
  }, { ctx: {}, $route: { query: { orderBatchId: '50', returnTo: '/admin/academic-affairs/textbooks?tab=order&page=2' } }, $router: { push: value => { destination = value } } })
  state.classId = '4538'; state.studentIds = ['233387']
  await state.submit()
  assert.equal(destination.params.batchId, '6')
  assert.equal(destination.query.returnTo, '/admin/academic-affairs/textbooks?tab=order&page=2')
})

test('textbook return links reject external addresses and unrelated business destinations', () => {
  for (const value of ['https://example.com', '//example.com', '/admin/academic-affairs/textbooks/../terms?tab=order', '/admin/academic-affairs/textbooks?tab=fee', ['bad'], null]) {
    assert.equal(textbookReturnPath(value), '/admin/academic-affairs/textbooks?tab=distribution')
  }
  for (const value of ['NaN', '-1', '0', '2.5', 'Infinity', '99999999999999999']) assert.equal(textbookQueuePage(value), 1)
})

test('textbook tab pagination goes to the server', async () => {
  let query
  const { state } = page('AaTextbookConsoleView', { academicAffairsTextbookApi: { listTextbooks: async params => { query = params; return { code: 0, data: { list: [], total: 61 } } } } })
  state.page = 3
  await state.reload()
  assert.equal(query.page, 3)
  assert.equal(state.total, 61)
})

test('late catalog response cannot overwrite the fee ledger', async () => {
  const old = deferred()
  const { state } = page('AaTextbookConsoleView', { academicAffairsTextbookApi: { listTextbooks: () => old.promise } })
  const pending = state.reload()
  state.tab = 'fee'; state.rows = [{ feeId: 'fee-b' }]
  old.resolve({ code: 0, data: { list: [{ textbookId: 'old' }], total: 1 } })
  await pending
  assert.equal(state.rows[0].feeId, 'fee-b')
})

test('old distribution request cannot replace a newly selected batch', async () => {
  const old = deferred()
  const { state } = page('AaTextbookDistributionDetailView', { textbookP0Api: { distributionRecords: () => old.promise } }, { ctx: {}, $route: { params: { batchId: 'a' }, query: {} } })
  const pending = state.load()
  state.$route.params.batchId = 'b'; state.rows = [{ recordId: 'record-b' }]
  old.resolve({ code: 0, data: { list: [{ recordId: 'old' }], batch: {}, total: 1 } })
  await pending
  assert.equal(state.rows[0].recordId, 'record-b')
})

test('stock reads the canonical items envelope and keeps local paging honest', async () => {
  const rows = Array.from({ length: 23 }, (_, index) => ({ textbookId: String(index + 1), stockQty: index }))
  const { state } = page('AaTextbookConsoleView', { academicAffairsTextbookApi: { stock: async () => ({ code: 0, data: { items: rows } }) } })
  state.tab = 'stock'
  await state.reload()
  assert.equal(state.total, 23)
  assert.equal(state.rows.length, 23)
  assert.equal(state.visibleRows.length, 20)
})

test('selection picker requests the complete enabled catalog for the sandbox inventory', async () => {
  let query
  const { state } = page('AaTextbookConsoleView', { academicAffairsTextbookApi: { listTextbooks: async params => { query = params; return { code: 0, data: { list: [] } } } } })
  await state.openSelection()
  assert.equal(query.status, 'ENABLED')
  assert.equal(query.page, 1)
  assert.equal(query.pageSize, 200)
})

test('selection confirmation stays locked to its original identity and tab', async () => {
  let submits = 0
  const { state } = page('AaTextbookConsoleView', { academicAffairsTextbookApi: { submitSelection: async () => { submits += 1; return { code: 0, data: {} } } } })
  state.tab = 'selection'
  state.confirmSelectionSubmit({ selectionId: '17', courseName: '软件测试' })
  state.tab = 'review'
  state.onConfirm()
  await Promise.resolve()
  assert.equal(submits, 0)
})

test('teacher textbook edit normalizes the route only after the write guard is released', async () => {
  const record = { selectionId: '301', taskId: '19', textbookId: '21', expectedQty: 30, remark: '教学使用教材', courseName: '课程甲', status: 'DRAFT' }
  const { state, definition } = page('AaTextbookConsoleView', {
    academicAffairsTextbookApi: {
      updateSelection: async () => ({ code: 0, data: record }),
      listSelections: async () => ({ code: 0, data: { list: [record], total: 1 } })
    }
  }, {
    $route: { path: '/admin/academic-affairs/textbooks', query: { tab: 'selection', selectionId: '301', action: 'edit' }, params: {} }
  })
  state.ctx = { currentRole: { roleCode: 'ACADEMIC_TEACHER' } }
  state.tab = 'selection'; state.editingSelectionId = '301'; state.selectionVisible = true
  state.selectionForm = { taskId: '19', textbookId: '21', expectedQty: 30, remark: '教学使用教材' }
  const savingStates = []
  state.$router.replace = async target => {
    savingStates.push(state.saving)
    assert.equal(definition.beforeRouteUpdate.call(state), true)
    state.$route.query = target.query
  }
  await state.submitSelection()
  assert.deepEqual(savingStates, [false])
  assert.equal(state.$route.query.action, undefined)
  assert.equal(state.selectionVisible, false)
  assert.equal(state.selectionDraftReceipt.id, '301')
})
