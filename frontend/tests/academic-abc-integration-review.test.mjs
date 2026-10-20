import test from 'node:test'
import assert from 'node:assert/strict'
import { page, deferred } from './academic-pc-parallel-b-harness.mjs'

const ok = (list, total = list.length) => ({ code: 0, data: { list, total } })

for (const [method, endpoint, pagination, rows, tab] of [
  ['loadBatches', 'listBatches', 'batchPagination', 'rows', 'batches'],
  ['loadArchived', 'archivedBatches', 'archivePagination', 'archivedRows', 'archive'],
  ['loadAppeals', 'listAppeals', 'appealPagination', 'appeals', 'appeals']
]) {
  test(`${method}: an older page cannot replace the newer page or total`, async () => {
    const old = deferred()
    const { state } = page('AaEvaluationConsoleView', { academicAffairsEvaluationApi: {
      [endpoint]: ({ page }) => page === 1 ? old.promise : Promise.resolve(ok([{ id: 22 }], 61))
    } })
    state.queryTab = tab
    const pending = state[method]()
    state[pagination].page = 2
    await state[method]()
    old.resolve(ok([{ id: 11 }], 20))
    await pending
    assert.equal(state[rows][0].id, 22)
    assert.equal(state[pagination].total, 61)
  })
}

test('switching evaluation views during loading starts the new read and ignores the old failure', async () => {
  const old = deferred()
  const { state } = page('AaEvaluationConsoleView', { academicAffairsEvaluationApi: {
    listBatches: () => old.promise,
    listAppeals: async () => ok([{ appealId: 32 }])
  } })
  state.queryTab = 'batches'
  const pending = state.reloadView()
  state.resetSelection()
  state.queryTab = 'appeals'
  await state.reloadView()
  assert.equal(state.appeals[0].appealId, 32)
  assert.equal(state.loading, false)
  old.reject(new Error('old batch network failure'))
  await pending
  assert.equal(state.readError, '')
  assert.equal(state.rows.length, 0)
})

test('evaluation identity change and unmount invalidate queue responses', async () => {
  for (const mode of ['identity', 'unmount']) {
    const old = deferred()
    const { state, definition } = page('AaEvaluationConsoleView', { academicAffairsEvaluationApi: { listBatches: () => old.promise } })
    const pending = state.loadBatches()
    if (mode === 'identity') { state.ctx = { tenantId: 'new-tenant' }; state.resetSelection() }
    else definition.beforeUnmount.call(state)
    old.resolve(ok([{ batchId: 'old-private-batch' }]))
    await pending
    assert.equal(state.rows.length, 0)
    assert.equal(state.batchPagination.total, 0)
  }
})

test('quality records use server pages and discard out-of-order pages', async () => {
  const old = deferred()
  const calls = []
  const { state } = page('AaQualityDashboardView', { academicAffairsQualityApi: {
    listRecords: (query) => { calls.push(query); return query.page === 1 ? old.promise : Promise.resolve(ok([{ recordId: 44 }], 83)) }
  } })
  state.tab = 'inspection'
  const pending = state.loadRecords()
  state.recPagination.page = 3
  await state.loadRecords()
  old.resolve(ok([{ recordId: 11 }], 20))
  await pending
  assert.equal(calls[1].page, 3)
  assert.equal(calls[1].pageSize, 20)
  assert.equal(state.recRows[0].recordId, 44)
  assert.equal(state.recPagination.total, 83)
})

test('rectification paging preserves a truthful total when the current follow-up page is closed', async () => {
  let query
  const { state } = page('AaQualityDashboardView', { academicAffairsQualityApi: {
    listRectifications: async (params) => { query = params; return ok([{ rectId: 12, status: 'CLOSED' }], 62) },
    listRecords: async () => ok([])
  } })
  state.tab = 'followUp'; state.rectPagination.page = 2
  await state.loadRectifications()
  assert.equal(query.page, 2)
  assert.equal(query.pageSize, 20)
  assert.equal(state.displayRectRows.length, 0)
  assert.equal(state.rectPagination.total, 62)
  assert.equal(state.panelError, '')
})

test('quality paging clears the previous object deep-link and keeps the return token', async () => {
  let target
  const { state } = page('AaQualityDashboardView')
  state.$route.query = { tab: 'inspection', recordId: '42', returnToken: 'origin', page: '2' }
  state.$router.replace = (route) => { target = route }
  state.onQueuePageChange({ page: 3 })
  assert.equal(target.query.page, '3')
  assert.equal(target.query.returnToken, 'origin')
  assert.equal(target.query.recordId, undefined)
})

test('quality responses without a total cannot masquerade as complete pages', async () => {
  const { state } = page('AaQualityDashboardView', { academicAffairsQualityApi: {
    listRecords: async () => ({ code: 0, data: { list: [] } })
  } })
  state.tab = 'inspection'
  await state.loadRecords()
  assert.match(state.panelError, /分页回执不完整/)
})
